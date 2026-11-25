"""
Security utilities for ComfyUI-Doctor.
Holds the SSRF block counter reported by /doctor/health and the base URL helpers. It can be imported
without ComfyUI context.

Outbound LLM destinations are approved only by services/outbound_policy.py (an exact-match registry
plus a connect-time address check). There is deliberately no function here that validates a
caller-supplied URL: see test_legacy_deny_list_validator_stays_removed.
"""

from typing import Optional, Dict
import time
from urllib.parse import urlparse


LOCAL_LLM_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
LOCAL_LLM_PORTS = {11434, 1234}

_SSRF_METRICS = {
    "ssrf_block_count": 0,
    "last_block_timestamp": None,
    "last_block_reason": None,
}


def _record_ssrf_block(reason: str) -> None:
    _SSRF_METRICS["ssrf_block_count"] += 1
    _SSRF_METRICS["last_block_timestamp"] = time.time()
    _SSRF_METRICS["last_block_reason"] = reason


def record_ssrf_block(reason: str) -> None:
    """Count an outbound-destination refusal in the /doctor/health SSRF metrics."""
    _record_ssrf_block(reason)


def parse_base_url(base_url: str) -> Optional[Dict[str, str]]:
    """
    Parse base URL into normalized components.

    Returns:
        dict with scheme, hostname, port, path, netloc or None if invalid.
    """
    if not base_url:
        return None

    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.hostname:
        return None

    scheme = parsed.scheme.lower()
    port = parsed.port
    if port is None:
        if scheme == "https":
            port = 443
        elif scheme == "http":
            port = 80

    return {
        "scheme": scheme,
        "hostname": parsed.hostname,
        "port": port,
        "path": parsed.path or "",
        "netloc": parsed.netloc,
    }


def is_local_llm_url(base_url: str) -> bool:
    """
    Check if the base URL is a local LLM service (LMStudio, Ollama, etc.).
    These typically don't require an API key.
    """
    if not base_url:
        return False

    info = parse_base_url(base_url)
    if not info:
        return False

    hostname = (info.get("hostname") or "").lower()
    port = info.get("port")
    if hostname in LOCAL_LLM_HOSTS and port in LOCAL_LLM_PORTS:
        return True

    return False


def get_ssrf_metrics() -> Dict[str, Optional[str]]:
    return dict(_SSRF_METRICS)
