"""
API Routes for ComfyUI-Doctor.
Refactored from __init__.py for testability.
"""

import logging
import time

import aiohttp.web as web

from .admin_guard import validate_admin_request
from . import job_manager
from .providers import registry as provider_registry

try:
    from ..config import CONFIG
except ImportError:
    from config import CONFIG


logger = logging.getLogger("ComfyUI-Doctor.routes")


def _admin_denied_response(code: str, message: str):
    status_code = 401 if code == "unauthorized" else 403
    return web.json_response({"success": False, "error": code, "message": message}, status=status_code)


async def _optional_json_payload(request):
    if not getattr(request, "can_read_body", False):
        return {}
    try:
        return await request.json()
    except Exception:
        return {}


async def api_plugins(request):
    """
    Plugin trust report (scan-only).
    Returns the trust classification for each discovered community plugin without importing code.
    """
    try:
        from pathlib import Path

        try:
            from ..pipeline.plugins import scan_plugins
        except ImportError:
            from pipeline.plugins import scan_plugins

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
    job = job_manager.get_job_manager().get_job(job_id)
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
    payload = await _optional_json_payload(request)
    allowed, code, message = validate_admin_request(request, payload=payload)
    if not allowed:
        return _admin_denied_response(code, message)

    job_id = request.match_info.get("job_id", "")
    job = job_manager.get_job_manager().get_job(job_id)
    if not job:
        return web.json_response({"success": False, "error": "Job not found"}, status=404)

    if job.status.value not in ("failed", "cancelled", "pending"):
        return web.json_response({"success": False, "message": f"Cannot resume job in state {job.status}"}, status=400)

    job_manager.get_job_manager().update_job(job_id, status=job_manager.JobStatus.PENDING, meta_update={"resumed_at": time.time()})
    return web.json_response({"success": True, "message": "Job resumed"})


async def api_cancel_job(request):
    """
    Cancel a running/pending job.
    """
    payload = await _optional_json_payload(request)
    allowed, code, message = validate_admin_request(request, payload=payload)
    if not allowed:
        return _admin_denied_response(code, message)

    job_id = request.match_info.get("job_id", "")
    if job_manager.get_job_manager().update_job(job_id, status=job_manager.JobStatus.CANCELLED):
        return web.json_response({"success": True, "message": "Job cancelled"})
    return web.json_response({"success": False, "error": "Job not found"}, status=404)


async def api_provider_status(request):
    """
    Get specific provider status/capability.
    """
    provider_id = request.match_info.get("provider_id", "")
    cap = provider_registry.ProviderRegistry.get_capability(provider_id)
    if not cap:
        return web.json_response({"success": False, "error": "Provider not found"}, status=404)

    return web.json_response({
        "success": True,
        "provider_id": provider_id,
        "capabilities": {
            "supports_submit": cap.supports_submit,
            "requires_auth": cap.requires_auth,
            "concurrency_limit": cap.concurrency_limit,
        }
    })
