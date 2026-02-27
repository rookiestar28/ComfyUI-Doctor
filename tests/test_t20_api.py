"""
T20: API Endpoint Unit Tests.
Verifies logic for job management and provider status endpoints.
"""
import pytest
from unittest.mock import MagicMock, patch, ANY
from services.job_manager import JobStatus, JobCheckpoint

# Import handlers to test
# We use patch to mock dependencies before importing if they have side effects
# But services.routes is designed to be side-effect free on import
from services.routes import (
    api_get_job,
    api_resume_job,
    api_cancel_job,
    api_provider_status
)

@pytest.fixture
def mock_request():
    request = MagicMock()
    request.match_info = {}
    request.remote = "127.0.0.1"
    request.headers = {}
    request.can_read_body = False
    return request

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_get_job_found(mock_request):
    mock_request.match_info["job_id"] = "job_123"
    
    mock_job = JobCheckpoint(
        job_id="job_123",
        provider_id="prov_1",
        status=JobStatus.COMPLETED,
        cursor="",
        created_at=100.0,
        updated_at=200.0,
        meta={}
    )
    
    with patch("services.job_manager.get_job_manager") as mock_get_jm:
        mock_manager = MagicMock()
        mock_manager.get_job.return_value = mock_job
        mock_get_jm.return_value = mock_manager
        
        response = await api_get_job(mock_request)
        assert response.status == 200
        import json
        data = json.loads(response.body)
        assert data["success"] is True
        assert data["job"]["job_id"] == "job_123"
        assert data["job"]["status"] == "completed"

@pytest.mark.anyio
async def test_get_job_not_found(mock_request):
    mock_request.match_info["job_id"] = "job_404"
    
    with patch("services.job_manager.get_job_manager") as mock_get_jm:
        mock_manager = MagicMock()
        mock_manager.get_job.return_value = None
        mock_get_jm.return_value = mock_manager
        
        response = await api_get_job(mock_request)
        assert response.status == 404
        import json
        data = json.loads(response.body)
        assert data["success"] is False

@pytest.mark.anyio
async def test_resume_job_success(mock_request):
    mock_request.match_info["job_id"] = "job_failed"
    
    mock_job = JobCheckpoint(
        job_id="job_failed",
        provider_id="prov_1",
        status=JobStatus.FAILED,
        cursor="cursor_1",
        created_at=100.0,
        updated_at=200.0
    )
    
    with patch.dict("os.environ", {}, clear=False), patch("services.job_manager.get_job_manager") as mock_get_jm:
        import os
        os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
        os.environ.pop("DOCTOR_ALLOW_REMOTE_ADMIN", None)
        mock_manager = MagicMock()
        mock_manager.get_job.return_value = mock_job
        mock_get_jm.return_value = mock_manager
        
        response = await api_resume_job(mock_request)
        assert response.status == 200
        mock_manager.update_job.assert_called_with(
            "job_failed", 
            status=JobStatus.PENDING, 
            meta_update={"resumed_at": ANY}
        )

@pytest.mark.anyio
async def test_resume_job_invalid_state(mock_request):
    mock_request.match_info["job_id"] = "job_running"
    
    mock_job = JobCheckpoint(
        job_id="job_running",
        provider_id="prov_1",
        status=JobStatus.RUNNING, # Cannot resume running job
        cursor="",
        created_at=100.0,
        updated_at=200.0
    )
    
    with patch.dict("os.environ", {}, clear=False), patch("services.job_manager.get_job_manager") as mock_get_jm:
        import os
        os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
        os.environ.pop("DOCTOR_ALLOW_REMOTE_ADMIN", None)
        mock_manager = MagicMock()
        mock_manager.get_job.return_value = mock_job
        mock_get_jm.return_value = mock_manager
        
        response = await api_resume_job(mock_request)
        assert response.status == 400

@pytest.mark.anyio
async def test_cancel_job(mock_request):
    mock_request.match_info["job_id"] = "job_pending"
    
    with patch.dict("os.environ", {}, clear=False), patch("services.job_manager.get_job_manager") as mock_get_jm:
        import os
        os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
        os.environ.pop("DOCTOR_ALLOW_REMOTE_ADMIN", None)
        mock_manager = MagicMock()
        mock_manager.update_job.return_value = True
        mock_get_jm.return_value = mock_manager
        
        response = await api_cancel_job(mock_request)
        assert response.status == 200
        mock_manager.update_job.assert_called_with("job_pending", status=JobStatus.CANCELLED)


@pytest.mark.anyio
async def test_resume_job_remote_denied_without_token(mock_request):
    mock_request.match_info["job_id"] = "job_failed"
    mock_request.remote = "192.168.1.8"

    with patch.dict("os.environ", {}, clear=False), patch("services.job_manager.get_job_manager") as mock_get_jm:
        import os
        os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
        os.environ.pop("DOCTOR_ALLOW_REMOTE_ADMIN", None)
        mock_manager = MagicMock()
        mock_manager.get_job.return_value = None
        mock_get_jm.return_value = mock_manager

        response = await api_resume_job(mock_request)
        assert response.status == 403


@pytest.mark.anyio
async def test_cancel_job_requires_token_when_configured(mock_request):
    mock_request.match_info["job_id"] = "job_pending"
    mock_request.remote = "127.0.0.1"
    mock_request.headers = {}

    with patch.dict("os.environ", {"DOCTOR_ADMIN_TOKEN": "secret-token"}, clear=False), patch("services.job_manager.get_job_manager") as mock_get_jm:
        mock_manager = MagicMock()
        mock_manager.update_job.return_value = True
        mock_get_jm.return_value = mock_manager

        response = await api_cancel_job(mock_request)
        assert response.status == 401


@pytest.mark.anyio
async def test_cancel_job_accepts_header_token_when_configured(mock_request):
    mock_request.match_info["job_id"] = "job_pending"
    mock_request.remote = "127.0.0.1"
    mock_request.headers = {"X-Doctor-Admin-Token": "secret-token"}

    with patch.dict("os.environ", {"DOCTOR_ADMIN_TOKEN": "secret-token"}, clear=False), patch("services.job_manager.get_job_manager") as mock_get_jm:
        mock_manager = MagicMock()
        mock_manager.update_job.return_value = True
        mock_get_jm.return_value = mock_manager

        response = await api_cancel_job(mock_request)
        assert response.status == 200

@pytest.mark.anyio
async def test_provider_status(mock_request):
    mock_request.match_info["provider_id"] = "mock_prov"
    
    with patch("services.providers.registry.ProviderRegistry") as mock_registry:
        mock_cap = MagicMock()
        mock_cap.supports_submit = True
        mock_cap.requires_auth = False
        mock_cap.concurrency_limit = 5
        
        mock_registry.get_capability.return_value = mock_cap
        
        response = await api_provider_status(mock_request)
        assert response.status == 200
        import json
        data = json.loads(response.body)
        assert data["success"] is True
        assert data["capabilities"]["concurrency_limit"] == 5

