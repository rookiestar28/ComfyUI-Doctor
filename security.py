"""
Security utilities for ComfyUI-Doctor.
Includes SSRF protection helpers that can be imported without ComfyUI context.
"""

from typing import Tuple
import ipaddress
from urllib.parse import urlparse


def is_local_llm_url(base_url: str) -> bool:
    """
    Check if the base URL is a local LLM service (LMStudio, Ollama, etc.).
    These typically don't require an API key.
    """
    if not base_url:
        return False

    base_url_lower = base_url.lower()
    local_patterns = [
        # LMStudio patterns
        "localhost:1234", "127.0.0.1:1234", "0.0.0.0:1234",
        # Ollama patterns
        "localhost:11434", "127.0.0.1:11434", "0.0.0.0:11434",
        # Generic local patterns
        "localhost/v1", "127.0.0.1/v1",
    ]
    return any(pattern in base_url_lower for pattern in local_patterns)


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
    if not base_url:
        return False, "Empty URL"

    # Allow known local LLM patterns if enabled
    if allow_local_llm and is_local_llm_url(base_url):
        return True, ""

    try:
        parsed = urlparse(base_url)
    except Exception as e:
        return False, f"Invalid URL format: {e}"

    # Check protocol
    if parsed.scheme not in ("http", "https"):
        return False, f"Invalid protocol: {parsed.scheme}. Only HTTP/HTTPS allowed."

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname"

    hostname_lower = hostname.lower()

    # Block localhost patterns
    localhost_patterns = ["localhost", "127.0.0.1", "::1", "0.0.0.0"]
    if hostname_lower in localhost_patterns:
        return False, f"Blocked: localhost access ({hostname})"

    # Check if hostname is an IP address
    try:
        ip = ipaddress.ip_address(hostname)

        # Block private IPs
        if ip.is_private:
            return False, f"Blocked: private IP ({hostname})"

        # Block loopback, link-local, multicast, etc.
        if ip.is_loopback or ip.is_link_local or ip.is_multicast:
            return False, f"Blocked: restricted IP ({hostname})"

        # Block cloud metadata IP
        if str(ip) == "169.254.169.254":
            return False, "Blocked: metadata endpoint"

    except ValueError:
        # Not an IP address (domain name)
        blocked_domains = [".local", ".internal", ".corp", ".lan"]
        if any(hostname_lower.endswith(d) for d in blocked_domains):
            return False, f"Blocked: internal domain ({hostname})"

    return True, ""
