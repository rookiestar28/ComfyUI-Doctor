"""
Security utilities for ComfyUI-Doctor.
Includes SSRF protection helpers that can be imported without ComfyUI context.
"""

from typing import Tuple, Optional, Dict, List
import ipaddress
import os
import socket
import threading
import time
from urllib.parse import urlparse


LOCAL_LLM_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
LOCAL_LLM_PORTS = {11434, 1234}
DEFAULT_DNS_TIMEOUT_SECONDS = 1.5

_SSRF_METRICS = {
    "ssrf_block_count": 0,
    "last_block_timestamp": None,
    "last_block_reason": None,
}


def _record_ssrf_block(reason: str) -> None:
    _SSRF_METRICS["ssrf_block_count"] += 1
    _SSRF_METRICS["last_block_timestamp"] = time.time()
    _SSRF_METRICS["last_block_reason"] = reason


def _dns_timeout_seconds() -> float:
    raw = (os.getenv("DOCTOR_SSRF_DNS_TIMEOUT_SECONDS", "") or "").strip()
    if not raw:
        return DEFAULT_DNS_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except Exception:
        return DEFAULT_DNS_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_DNS_TIMEOUT_SECONDS
    return min(value, 10.0)


def _resolve_hostname_ips(hostname: str, timeout_seconds: Optional[float] = None) -> List[str]:
    """
    Resolve hostname to IP addresses with bounded timeout.
    Raises RuntimeError when DNS resolution fails/times out/returns empty.
    """
    result: Dict[str, List[str]] = {}
    error: Dict[str, Exception] = {}

    def _worker() -> None:
        try:
            infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
            ips: List[str] = []
            for info in infos:
                sockaddr = info[4]
                if not isinstance(sockaddr, tuple) or not sockaddr:
                    continue
                ip_text = str(sockaddr[0]).strip()
                if ip_text:
                    ips.append(ip_text)
            # Keep deterministic order and unique values.
            deduped = list(dict.fromkeys(ips))
            result["ips"] = deduped
        except Exception as exc:
            error["exc"] = exc

    timeout = timeout_seconds if timeout_seconds is not None else _dns_timeout_seconds()
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        raise RuntimeError(f"DNS resolution timeout ({timeout:.1f}s)")
    if "exc" in error:
        raise RuntimeError(f"DNS resolution failed: {error['exc']}")

    ips = result.get("ips") or []
    if not ips:
        raise RuntimeError("DNS resolution returned no addresses")
    return ips


def _classify_restricted_ip(ip) -> Optional[str]:
    # Keep metadata endpoint reason explicit for audits.
    if str(ip) == "169.254.169.254":
        return "metadata endpoint"
    if ip.is_private:
        return "private IP"
    if ip.is_loopback:
        return "loopback IP"
    if ip.is_link_local:
        return "link-local IP"
    if ip.is_multicast:
        return "multicast IP"
    if ip.is_unspecified:
        return "unspecified IP"
    if ip.is_reserved:
        return "reserved IP"
    return None


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
    - DNS-rebinding patterns (domain names resolving to restricted/local addresses)

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
        restricted_reason = _classify_restricted_ip(ip)
        if restricted_reason:
            return _block(f"Blocked: {restricted_reason} ({hostname})")
    except ValueError:
        # Not an IP address (domain name)
        blocked_domains = [".local", ".internal", ".corp", ".lan"]
        if any(hostname_lower.endswith(d) for d in blocked_domains):
            return _block(f"Blocked: internal domain ({hostname})")

        # CRITICAL: DNS check must fail-closed to prevent DNS rebinding SSRF bypasses.
        try:
            resolved_ips = _resolve_hostname_ips(hostname)
        except RuntimeError as exc:
            return _block(f"Blocked: DNS resolution error ({exc})")

        for resolved_ip in resolved_ips:
            try:
                ip = ipaddress.ip_address(resolved_ip)
            except ValueError:
                return _block(f"Blocked: DNS returned invalid IP ({resolved_ip})")

            restricted_reason = _classify_restricted_ip(ip)
            if restricted_reason:
                return _block(f"Blocked: DNS resolved to {restricted_reason} ({resolved_ip})")

    return True, ""


def get_ssrf_metrics() -> Dict[str, Optional[str]]:
    return dict(_SSRF_METRICS)
