"""
Security utilities for ComfyUI-Doctor.
Includes SSRF protection helpers that can be imported without ComfyUI context.
"""

from typing import Tuple, Optional, Dict
import ipaddress
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


def validate_ssrf_url(base_url: str, allow_local_llm: bool = True) -> Tuple[bool, str]:
    """
    Validate base URL to prevent SSRF attacks.

    Blocks:
    - Private IP ranges (10.x, 172.16-31.x, 192.168.x)
    - Localhost (127.x.x.x, localhost, ::1)
    - Link-local addresses (169.254.x.x)
    - Non-HTTP protocols (file://, ftp://, etc.)
    - Metadata endpoints (169.254.169.254)

    Args:
        base_url: The URL to validate
        allow_local_llm: If True, allows known local LLM patterns (LMStudio, Ollama)

    Returns:
        (is_valid, error_message) tuple
    """
    def _block(reason: str):
        _record_ssrf_block(reason)
        return False, reason

    if not base_url:
        return _block("Empty URL")

    try:
        parsed = urlparse(base_url)
    except Exception as e:
        return _block(f"Invalid URL format: {e}")

    # Check protocol
    if parsed.scheme not in ("http", "https"):
        return _block(f"Invalid protocol: {parsed.scheme}. Only HTTP/HTTPS allowed.")

    # Allow known local LLM patterns if enabled
    if allow_local_llm and is_local_llm_url(base_url):
        return True, ""

    hostname = parsed.hostname
    if not hostname:
        return _block("Missing hostname")

    hostname_lower = hostname.lower()

    # Block localhost patterns
    if hostname_lower in LOCAL_LLM_HOSTS:
        return _block(f"Blocked: localhost access ({hostname})")

    # Check if hostname is an IP address
    try:
        ip = ipaddress.ip_address(hostname)

        # Block private IPs
        if ip.is_private:
            return _block(f"Blocked: private IP ({hostname})")

        # Block loopback, link-local, multicast, etc.
        if ip.is_loopback or ip.is_link_local or ip.is_multicast:
            return _block(f"Blocked: restricted IP ({hostname})")

        # Block cloud metadata IP
        if str(ip) == "169.254.169.254":
            return _block("Blocked: metadata endpoint")

    except ValueError:
        # Not an IP address (domain name)
        blocked_domains = [".local", ".internal", ".corp", ".lan"]
        if any(hostname_lower.endswith(d) for d in blocked_domains):
            return _block(f"Blocked: internal domain ({hostname})")

    return True, ""


def get_ssrf_metrics() -> Dict[str, Optional[str]]:
    return dict(_SSRF_METRICS)
