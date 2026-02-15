"""
T20: Resume & Persistence Tests.
"""
import pytest
import time
from services.job_manager import JobManager, JobStatus

@pytest.fixture
def job_manager(tmp_path):
    return JobManager(tmp_path)

def test_job_lifecycle(job_manager):
    job_id = job_manager.create_job("prov1", {"meta": 1})
    assert job_id
    
    job = job_manager.get_job(job_id)
    assert job.status == JobStatus.PENDING
    assert job.meta["meta"] == 1
    
    job_manager.update_job(job_id, status=JobStatus.RUNNING, cursor="abc")
    job = job_manager.get_job(job_id)
    assert job.status == JobStatus.RUNNING
    assert job.cursor == "abc"

def test_persistence(tmp_path):
    jm1 = JobManager(tmp_path)
    jid = jm1.create_job("prov1")
    jm1.update_job(jid, status=JobStatus.COMPLETED)
    
    # Reload from disk
    jm2 = JobManager(tmp_path)
    job = jm2.get_job(jid)
    assert job is not None
    assert job.status == JobStatus.COMPLETED
    assert job.provider_id == "prov1"

def test_stale_cleanup(job_manager):
    jid1 = job_manager.create_job("prov1")
    job_manager.update_job(jid1, status=JobStatus.COMPLETED)
    
    # Force old time
    job = job_manager._jobs[jid1]
    # Manually set updated_at to the past
    job.updated_at = time.time() - 1000
    # Save manually to persist the backdated time (update_job would reset it to now)
    job_manager._save_checkpoint(job)
    
    # Fresh job
    jid2 = job_manager.create_job("prov2")
    job_manager.update_job(jid2, status=JobStatus.COMPLETED)
    
    # Clean up jobs older than 10s
    count = job_manager.cleanup_stale_jobs(max_age_seconds=10)
    assert count >= 1
    assert job_manager.get_job(jid1) is None
    assert job_manager.get_job(jid2) is not None
