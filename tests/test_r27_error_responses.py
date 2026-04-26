import json
from unittest.mock import MagicMock, patch

import pytest

from services.job_manager import JobCheckpoint, JobStatus
from services.routes import api_get_job, api_provider_status, api_resume_job


def _json_body(response):
    return json.loads(response.body.decode("utf-8"))


def _assert_error_envelope(response, *, status):
    payload = _json_body(response)
    assert response.status == status
    assert payload["success"] is False
    assert isinstance(payload["error"], str)
    assert payload["error"]
    assert isinstance(payload["message"], str)
    assert payload["message"]
    return payload


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
    return "asyncio"


@pytest.mark.anyio
async def test_r27_job_not_found_uses_error_envelope(mock_request):
    mock_request.match_info["job_id"] = "missing"

    with patch("services.job_manager.get_job_manager") as mock_get_jm:
        manager = MagicMock()
        manager.get_job.return_value = None
        mock_get_jm.return_value = manager

        response = await api_get_job(mock_request)

    payload = _assert_error_envelope(response, status=404)
    assert payload["message"] == "Job not found"


@pytest.mark.anyio
async def test_r27_resume_invalid_state_uses_error_envelope(mock_request):
    mock_request.match_info["job_id"] = "running"
    mock_job = JobCheckpoint(
        job_id="running",
        provider_id="provider",
        status=JobStatus.RUNNING,
        cursor="",
        created_at=100.0,
        updated_at=200.0,
    )

    with patch.dict("os.environ", {}, clear=False), patch("services.job_manager.get_job_manager") as mock_get_jm:
        import os

        os.environ.pop("DOCTOR_ADMIN_TOKEN", None)
        os.environ.pop("DOCTOR_ALLOW_REMOTE_ADMIN", None)
        manager = MagicMock()
        manager.get_job.return_value = mock_job
        mock_get_jm.return_value = manager

        response = await api_resume_job(mock_request)

    payload = _assert_error_envelope(response, status=400)
    assert "Cannot resume job" in payload["message"]


@pytest.mark.anyio
async def test_r27_provider_not_found_uses_error_envelope(mock_request):
    mock_request.match_info["provider_id"] = "missing"

    with patch("services.providers.registry.ProviderRegistry") as mock_registry:
        mock_registry.get_capability.return_value = None

        response = await api_provider_status(mock_request)

    payload = _assert_error_envelope(response, status=404)
    assert payload["message"] == "Provider not found"
