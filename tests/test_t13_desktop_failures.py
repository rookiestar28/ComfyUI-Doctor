import pytest
from unittest.mock import patch
from services.job_manager import JobManager, JobStatus

@pytest.fixture
def desktop_env(tmp_path):
    """Setup a temporary desktop-like environment."""
    data_dir = tmp_path / "comfy_doctor_data"
    data_dir.mkdir()
    return data_dir

def test_store_corruption_recovery(desktop_env):
    """
    T13: Verify JobManager handles corrupt checkpoint files by rotating them
    and ignoring the bad data without crashing.
    """
    # 1. Create a corrupt checkpoint file
    checkpoint_dir = desktop_env / "checkpoints"
    checkpoint_dir.mkdir()
    
    corrupt_file = checkpoint_dir / "job_bad_beef.json"
    corrupt_file.write_text("{ this is not valid json }", encoding="utf-8")
    
    # 2. Initialize JobManager
    manager = JobManager(desktop_env)
    
    # 3. Verify it didn't crash and loaded 0 jobs
    assert len(manager.list_jobs()) == 0
    
    # 4. Verify the corrupt file was rotated
    # Expectation: job_bad_beef.json renamed to job_bad_beef.json.corrupt.<timestamp>
    files = list(checkpoint_dir.glob("job_bad_beef.json.corrupt.*"))
    assert len(files) == 1
    assert not corrupt_file.exists()  # Original should be gone/renamed

def test_flush_storm_suppression(desktop_env):
    """
    T13: Verify that failing to save (e.g., locked file or disk full)
    does not cause a crash or infinite recursion loop.
    """
    manager = JobManager(desktop_env)
    job_id = manager.create_job("test_provider")
    
    # Mock open() to raise OSError (simulating locked file)
    with patch("builtins.open", side_effect=OSError("The process cannot access the file")):
        # Attempt update - should log error but not crash
        success = manager.update_job(job_id, status=JobStatus.RUNNING)
        
        # In our implementation, update_job returns True if in-memory update worked,
        # even if save failed (it logs error). We verify it didn't raise.
        assert success is True 
        
    # Verify in-memory state is still updated
    job = manager.get_job(job_id)
    assert job.status == JobStatus.RUNNING
