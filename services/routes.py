"""
API Routes for ComfyUI-Doctor.
Refactored from __init__.py for testability.
"""
import logging
import time
from pathlib import Path

import aiohttp.web as web

try:
    from config import CONFIG
    from .job_manager import get_job_manager, JobStatus
    from .providers.registry import ProviderRegistry
    # We need to import pipeline.plugins scan_plugins.
    # Since we are in services/routes.py, pipeline is ../pipeline
    # But imports in ComfyUI execution context can be tricky.
    # We will try relative import, if fails, we rely on sys.path hack or assumption.
    # Actually, config is in root, so from config import CONFIG works if root is in path.
    # services is a package.
except ImportError:
    # Fallback for when running tests where package structure might differ
    # or if we are not in a full package context.
    import sys
    # Only if we really can't find them, but usually unrelated to runtime
    pass


logger = logging.getLogger("ComfyUI-Doctor.routes")

async def api_plugins(request):
    """
    Plugin trust report (scan-only).
    Returns the trust classification for each discovered community plugin without importing code.
    """
    try:
        # Import lazily if needed to avoid top-level import issues during startup
        from pathlib import Path
        # Handle import of pipeline/config based on context
        try:
            from ..pipeline.plugins import scan_plugins
            from ..config import CONFIG
        except ImportError:
            # If running as script or different context
            from pipeline.plugins import scan_plugins
            from config import CONFIG
        
        # We need to find the plugin dir relative to this file?
        # This file is services/routes.py.
        # Plugin dir is ../pipeline/plugins/community
        plugin_dir = Path(__file__).resolve().parent.parent / "pipeline" / "plugins" / "community"
        report = scan_plugins(plugin_dir)

        def sanitize_manifest(manifest):
            if not isinstance(manifest, dict):
                return None
            keys = [
                "id",
                "name",
                "version",
                "author",
                "min_doctor_version",
                "signature_alg",
            ]
            out = {k: manifest.get(k) for k in keys if k in manifest}
            if "signature" in manifest:
                out["has_signature"] = bool(manifest.get("signature"))
            return out

        plugins = []
        trust_counts = {}
        for entry in report:
            trust = entry.get("trust")
            trust_counts[trust] = trust_counts.get(trust, 0) + 1
            plugins.append(
                {
                    "file": getattr(entry.get("file"), "name", str(entry.get("file"))),
                    "plugin_id": entry.get("plugin_id"),
                    "trust": trust,
                    "reason": entry.get("reason"),
                    "manifest": sanitize_manifest(entry.get("manifest")),
                }
            )

        payload = {
            "config": {
                "enabled": bool(getattr(CONFIG, "enable_community_plugins", False)),
                "allowlist_count": len(getattr(CONFIG, "plugin_allowlist", []) or []),
                "blocklist_count": len(getattr(CONFIG, "plugin_blocklist", []) or []),
                "signature_required": bool(getattr(CONFIG, "plugin_signature_required", False)),
                "signature_alg": getattr(CONFIG, "plugin_signature_alg", "hmac-sha256"),
                "signature_key_configured": bool(getattr(CONFIG, "plugin_signature_key", "") or ""),
            },
            "trust_counts": trust_counts,
            "plugins": plugins,
        }
        return web.json_response({"success": True, "plugins": payload})
    except Exception as e:
        logger.error(f"Plugins API error: {str(e)}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def api_get_job(request):
    """
    Get job status and details.
    """
    job_id = request.match_info.get("job_id", "")
    from services.job_manager import get_job_manager
    job = get_job_manager().get_job(job_id)
    if not job:
        return web.json_response({"success": False, "error": "Job not found"}, status=404)
    
    return web.json_response({
        "success": True,
        "job": job.to_dict()
    })


async def api_resume_job(request):
    """
    Resume a suspended/failed job.
    Note: Actual resume logic depends on provider implementation.
    """
    job_id = request.match_info.get("job_id", "")
    from services.job_manager import get_job_manager, JobStatus
    job = get_job_manager().get_job(job_id)
    if not job:
        return web.json_response({"success": False, "error": "Job not found"}, status=404)

    # In a real implementation, we would re-trigger the provider logic here.
    # For R20 scope, we just verify state transition is possible.
    if job.status.value not in ("failed", "cancelled", "pending"):
            return web.json_response({"success": False, "message": f"Cannot resume job in state {job.status}"}, status=400)
            
    # Mock resume for now
    get_job_manager().update_job(job_id, status=JobStatus.PENDING, meta_update={"resumed_at": time.time()})
    return web.json_response({"success": True, "message": "Job resumed"})


async def api_cancel_job(request):
    """
    Cancel a running/pending job.
    """
    job_id = request.match_info.get("job_id", "")
    from services.job_manager import get_job_manager, JobStatus
    if get_job_manager().update_job(job_id, status=JobStatus.CANCELLED):
            return web.json_response({"success": True, "message": "Job cancelled"})
    return web.json_response({"success": False, "error": "Job not found"}, status=404)


async def api_provider_status(request):
    """
    Get specific provider status/capability.
    """
    provider_id = request.match_info.get("provider_id", "")
    from services.providers.registry import ProviderRegistry
    
    cap = ProviderRegistry.get_capability(provider_id)
    if not cap:
            return web.json_response({"success": False, "error": "Provider not found"}, status=404)
            
    # Check active status via adapter if needed, for now return capability
    return web.json_response({
        "success": True,
        "provider_id": provider_id,
        "capabilities": {
                "supports_submit": cap.supports_submit,
                "requires_auth": cap.requires_auth,
                "concurrency_limit": cap.concurrency_limit
        }
    })
