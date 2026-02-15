"""
R20: Job Manager & Checkpoint Persistence.

Manages long-running async jobs (enrichment) with atomic checkpoint persistence.
Supports resume, cancel, status queries, and stale job garbage collection.
Ensures idempotency and recoverability across server restarts.
"""

import copy
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobCheckpoint:
    # Core identity
    job_id: str
    provider_id: str
    
    # State tracking
    status: JobStatus
    cursor: str  # opaque resume token provided by adapter
    
    # Metadata
    created_at: float
    updated_at: float
    meta: Dict[str, Any] = field(default_factory=dict)
    version: int = 1  # R20: Schema versioning


    def to_dict(self) -> Dict:
        return {
            "v": self.version,
            "job_id": self.job_id,
            "provider_id": self.provider_id,
            "status": self.status.value,
            "cursor": self.cursor,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "meta": self.meta
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'JobCheckpoint':
        return cls(
            job_id=data["job_id"],
            provider_id=data["provider_id"],
            status=JobStatus(data["status"]),
            cursor=data.get("cursor", ""),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
            meta=data.get("meta", {}),
            version=data.get("v", 1)
        )


class JobManager:
    def __init__(self, data_dir: Path):
        self.checkpoint_dir = data_dir / "checkpoints"
        self._jobs: Dict[str, JobCheckpoint] = {}
        self._ensure_dir()
        self._load_checkpoints()

    def _ensure_dir(self):
        try:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create checkpoint dir: {e}")

    def _load_checkpoints(self):
        """Load all valid checkpoints from disk on startup."""
        if not self.checkpoint_dir.exists():
            return
            
        for f in self.checkpoint_dir.glob("job_*.json"):
            try:
                content = f.read_text(encoding="utf-8")
                if not content.strip():
                    continue
                    
                try:
                    data = json.loads(content)
                    # Basic validation
                    if "job_id" in data and "provider_id" in data:
                        # Deserialize
                        job = JobCheckpoint.from_dict(data)
                        self._jobs[job.job_id] = job
                except Exception as e:
                    logger.error(f"Failed to load checkpoint {f}: {e}")
                    self._rotate_and_rebuild(f)

            except Exception as e:
                logger.error(f"Failed to access checkpoint {f}: {e}")

    def create_job(self, provider_id: str, meta: Optional[Dict[str, Any]] = None) -> str:
        """Create a new job and persist initial checkpoint."""
        job_id = str(uuid.uuid4())
        now = time.time()
        
        checkpoint = JobCheckpoint(
            job_id=job_id,
            provider_id=provider_id,
            status=JobStatus.PENDING,
            cursor="",
            created_at=now,
            updated_at=now,
            meta=meta or {}
        )
        
        self._save_checkpoint(checkpoint)
        self._jobs[job_id] = checkpoint
        logger.info(f"Created job {job_id} for provider {provider_id}")
        return job_id

    def update_job(
        self, 
        job_id: str, 
        status: Optional[JobStatus] = None, 
        cursor: Optional[str] = None, 
        meta_update: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update job state and persist changes atomically."""
        if job_id not in self._jobs:
            logger.warning(f"Update failed: Job {job_id} not found")
            return False
        
        # Modify in-place
        checkpoint = self._jobs[job_id]
        changed = False

        if status and status != checkpoint.status:
            checkpoint.status = status
            changed = True
            
        if cursor is not None and cursor != checkpoint.cursor:
            checkpoint.cursor = cursor
            changed = True
            
        if meta_update:
            checkpoint.meta.update(meta_update)
            changed = True
        
        if changed:
            checkpoint.updated_at = time.time()
            self._save_checkpoint(checkpoint)
            
        return True

    def get_job(self, job_id: str) -> Optional[JobCheckpoint]:
        """Get job state (read-only view)."""
        if job_id in self._jobs:
            return copy.deepcopy(self._jobs[job_id])
        return None

    def list_jobs(self, limit: int = 50) -> List[JobCheckpoint]:
        """List recent jobs."""
        sorted_jobs = sorted(self._jobs.values(), key=lambda x: x.updated_at, reverse=True)
        return sorted_jobs[:limit]

    def _save_checkpoint(self, checkpoint: JobCheckpoint):
        """Atomic write: write to temp file then rename."""
        file_path = self.checkpoint_dir / f"job_{checkpoint.job_id}.json"
        temp_path = file_path.with_suffix(".tmp")
        
        try:
            # Prepare data
            data = asdict(checkpoint)
            
            # Write to temp
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                # Ensure disk sync (best effort)
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
                
            # Atomic rename
            if file_path.exists():
                 # Handle existing file (Windows atomic replace needs care, but replace() usually works)
                 pass
            temp_path.replace(file_path)
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint {checkpoint.job_id}: {e}")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def _rotate_and_rebuild(self, file_path: Path):
        """
        R20: Handle corrupt checkpoint by rotating it and ensuring specific cleanup.
        We cannot 'rebuild' strictly without source of truth, but we isolate the bad file.
        """
        try:
            timestamp = int(time.time())
            new_name = file_path.name + f".corrupt.{timestamp}"
            new_path = file_path.parent / new_name
            file_path.rename(new_path)
            logger.warning(f"Rotated corrupt checkpoint to {new_name}")
        except Exception as e:
            logger.error(f"Failed to rotate corrupt checkpoint {file_path}: {e}")

    def cleanup_stale_jobs(self, max_age_seconds: int = 86400) -> int:
        """Remove old terminated jobs. Returns count of removed jobs."""
        now = time.time()
        to_delete = []
        
        for job_id, cp in self._jobs.items():
            if cp.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                if now - cp.updated_at > max_age_seconds:
                    to_delete.append(job_id)
        
        count = 0
        for job_id in to_delete:
            if self._delete_checkpoint(job_id):
                count += 1
        return count
            
    def _delete_checkpoint(self, job_id: str) -> bool:
        file_path = self.checkpoint_dir / f"job_{job_id}.json"
        try:
            if file_path.exists():
                file_path.unlink()
            if job_id in self._jobs:
                del self._jobs[job_id]
            logger.info(f"Deleted stale job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint {job_id}: {e}")
            return False


def get_job_manager():
    """
    Singleton accessor for JobManager.
    Lazy-loads to verify server instance availability.
    """
    try:
        import server
        if not hasattr(server.PromptServer.instance, "_doctor_job_manager"):
            # Avoid circular import if possible, but we need doctor_paths
            from services.doctor_paths import get_doctor_data_dir
            server.PromptServer.instance._doctor_job_manager = JobManager(Path(get_doctor_data_dir()))
        return server.PromptServer.instance._doctor_job_manager
    except ImportError:
        # Fallback for testing/standalone
        if not hasattr(get_job_manager, "_instance"):
            from services.doctor_paths import get_doctor_data_dir
            get_job_manager._instance = JobManager(Path(get_doctor_data_dir()))
        return get_job_manager._instance

