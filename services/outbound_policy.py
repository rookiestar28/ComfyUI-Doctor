"""Operator-controlled outbound destination policy for LLM requests.

Every server-side LLM request goes to an entry of an immutable destination registry that is built
once at startup from a built-in catalog (official providers and default local LLM services) plus
operator configuration read from the process environment. Request bodies, routes, ComfyUI settings
and workflows can only *select* an entry by sending its base URL; they can never add, widen or
alter one. Outbound URLs are built from the matched entry, never from caller text.

Address checks happen at connect time inside the shared aiohttp connector
(:class:`DestinationPolicyResolver`), on the exact addresses the connector will use.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import urlsplit

from aiohttp.abc import AbstractResolver
from aiohttp.resolver import ThreadedResolver

if TYPE_CHECKING:
    # CRITICAL: annotation-only import. aiohttp<3.10 (still bundled by some ComfyUI hosts) has no
    # ResolveResult; a runtime import raises ImportError and the whole node fails to load.
    from aiohttp.abc import ResolveResult

logger = logging.getLogger(__name__)

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

DESTINATION_NOT_ALLOWED = "destination_not_allowed"
DESTINATION_NOT_ALLOWED_MESSAGE = (
    "This LLM endpoint is not approved on this server. The server operator can approve it with "
    "DOCTOR_LLM_ALLOWED_BASE_URLS."
)

ENV_ALLOWED_BASE_URLS = "DOCTOR_LLM_ALLOWED_BASE_URLS"
ENV_DOCTOR_LLM_BASE_URL = "DOCTOR_LLM_BASE_URL"
ENV_OLLAMA_BASE_URL = "OLLAMA_BASE_URL"
ENV_LMSTUDIO_BASE_URL = "LMSTUDIO_BASE_URL"

KIND_OFFICIAL = "official"
KIND_LOCAL = "local"
KIND_OPERATOR = "operator"

POLICY_PUBLIC = "public"      # official hosts: every resolved address must be globally routable
POLICY_LOOPBACK = "loopback"  # local services: every resolved address must be loopback
# Operator-approved non-loopback hosts (LAN/Docker/VPN gateways): any routable unicast address
# except loopback; metadata, link-local, unspecified, multicast and reserved stay refused.
POLICY_OPERATOR_NETWORK = "operator_network"

_MAX_URL_LENGTH = 2048
_DEFAULT_PORTS = {"http": 80, "https": 443}
_PATH_PATTERN = re.compile(r"^(?:/[A-Za-z0-9_~-][A-Za-z0-9._~-]*)*$")
# Underscores are allowed inside labels because Docker/Compose service names (e.g. `my_ollama`)
# contain them; labels still start and end with a letter or digit.
_HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?$")
_LOOPBACK_NAMES = frozenset({"localhost"})

# Never reachable, even when resolved for an approved name or listed as an operator IP literal.
_ALWAYS_DENIED_NETWORKS: Tuple[Union[ipaddress.IPv4Network, ipaddress.IPv6Network], ...] = tuple(
    ipaddress.ip_network(net)
    for net in (
        "0.0.0.0/8",            # "this network" / unspecified
        "169.254.0.0/16",       # link-local incl. cloud metadata 169.254.169.254
        "100.100.100.200/32",   # Alibaba Cloud instance metadata (inside 100.64.0.0/10)
        "224.0.0.0/4",          # multicast
        "240.0.0.0/4",          # reserved
        "255.255.255.255/32",
        "::/128",
        "fe80::/10",            # IPv6 link-local
        "fd00:ec2::254/128",    # AWS IPv6 instance metadata
        "ff00::/8",             # IPv6 multicast
    )
)
# Additionally refused for public (official and operator hostname) destinations.
_NON_PUBLIC_NETWORKS: Tuple[Union[ipaddress.IPv4Network, ipaddress.IPv6Network], ...] = tuple(
    ipaddress.ip_network(net)
    for net in (
        "100.64.0.0/10",        # shared address space / CGNAT (not covered by is_private)
        "::/96",                # IPv4-compatible IPv6 (deprecated)
        "64:ff9b::/96",         # NAT64
        "64:ff9b:1::/48",
        "2002::/16",            # 6to4
        "fec0::/10",            # IPv6 site-local (deprecated)
    )
)
_NAT64_WELL_KNOWN = ipaddress.IPv6Network("64:ff9b::/96")
_IPV4_COMPATIBLE = ipaddress.IPv6Network("::/96")


class DestinationPolicyError(OSError):
    """Raised when a connection would leave the approved destination policy (fails closed)."""


@dataclass(frozen=True)
class Destination:
    """One approved outbound LLM destination (immutable)."""

    destination_id: str
    provider: str
    kind: str
    scheme: str
    host: str
    port: int
    base_path: str

    @property
    def is_loopback(self) -> bool:
        return self.address_policy == POLICY_LOOPBACK

    @property
    def address_policy(self) -> str:
        if self.host in _LOOPBACK_NAMES:
            return POLICY_LOOPBACK
        literal = _parse_ip(self.host)
        if literal is not None and literal.is_loopback:
            return POLICY_LOOPBACK
        if self.kind == KIND_OPERATOR:
            return POLICY_OPERATOR_NETWORK
        return POLICY_PUBLIC

    @property
    def base_url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        default_port = _DEFAULT_PORTS.get(self.scheme)
        netloc = host if self.port == default_port else f"{host}:{self.port}"
        return f"{self.scheme}://{netloc}{self.base_path}"


@dataclass(frozen=True)
class CanonicalBaseUrl:
    scheme: str
    host: str
    port: int
    path: str

    @property
    def key(self) -> Tuple[str, str, int, str]:
        return (self.scheme, self.host, self.port, self.path)


def _parse_ip(host: str) -> Optional[IPAddress]:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _unmapped(ip: IPAddress) -> IPAddress:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _in_any(ip: IPAddress, networks: Sequence[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]) -> bool:
    return any(ip.version == net.version and ip in net for net in networks)


def _embedded_ipv4(ip: IPAddress) -> Optional[ipaddress.IPv4Address]:
    """IPv4 address carried inside an IPv6 transition form (mapped, compatible, NAT64, 6to4)."""
    if not isinstance(ip, ipaddress.IPv6Address):
        return None
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip in _NAT64_WELL_KNOWN or (ip in _IPV4_COMPATIBLE and int(ip) > 1):  # not :: or ::1
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def _is_denied_itself(ip: IPAddress) -> bool:
    return ip.is_unspecified or ip.is_multicast or ip.is_link_local or _in_any(ip, _ALWAYS_DENIED_NETWORKS)


def is_always_denied_address(ip: IPAddress) -> bool:
    """Metadata, link-local, unspecified, multicast and reserved addresses are never reachable.

    IPv6 transition forms are judged by the IPv4 address they carry as well, so a NAT64/6to4/
    compatible spelling of a metadata address is refused like the address itself.
    """
    embedded = _embedded_ipv4(ip)
    return _is_denied_itself(ip) or (embedded is not None and _is_denied_itself(embedded))


def _is_loopback_like(ip: IPAddress) -> bool:
    embedded = _embedded_ipv4(ip)
    return ip.is_loopback or (embedded is not None and embedded.is_loopback)


def is_public_address(ip: IPAddress) -> bool:
    """Deny-unless-global check used for official provider destinations."""
    ip = _unmapped(ip)
    if is_always_denied_address(ip) or _in_any(ip, _NON_PUBLIC_NETWORKS):
        return False
    return bool(ip.is_global)


def address_allowed(policy: str, address: str) -> bool:
    """Return whether one resolved address satisfies a destination address policy."""
    ip = _parse_ip(address.split("%", 1)[0])
    if ip is None:
        return False
    if policy == POLICY_LOOPBACK:
        return _unmapped(ip).is_loopback
    if policy == POLICY_PUBLIC:
        return is_public_address(ip)
    if policy == POLICY_OPERATOR_NETWORK:
        return not _is_loopback_like(ip) and not is_always_denied_address(ip)
    return False


def _canonical_host(raw_host: str) -> Optional[str]:
    host = raw_host.lower()
    if host.endswith("."):
        host = host[:-1]
    if not host or not host.isascii():
        return None
    if host.startswith("[") and host.endswith("]"):
        literal = _parse_ip(host[1:-1])
        if not isinstance(literal, ipaddress.IPv6Address) or literal.scope_id:
            return None
        return literal.compressed
    literal = _parse_ip(host)
    if literal is not None:
        return literal.compressed if isinstance(literal, ipaddress.IPv4Address) else None
    if len(host) > 253:
        return None
    labels = host.split(".")
    if not all(_HOST_LABEL_PATTERN.match(label) for label in labels):
        return None
    # Purely numeric dotted names (e.g. "2130706433", "0x7f.1") are not hostnames.
    if all(label.isdigit() for label in labels) or labels[-1].isdigit() or labels[-1].startswith("0x"):
        return None
    return host


def canonicalize_base_url(raw: object) -> Optional[CanonicalBaseUrl]:
    """Strictly parse a base URL; return None for anything that is not an exact, plain form.

    CRITICAL: reject before any DNS/socket activity. Userinfo, query, fragment, backslash,
    whitespace/control characters, percent-encoding, non-ASCII hosts and dot segments are refused
    instead of normalized, because parser differentials on those forms are how a caller string
    escapes an exact-match allowlist.
    """
    if not isinstance(raw, str) or not raw or len(raw) > _MAX_URL_LENGTH:
        return None
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in raw):
        return None
    if any(ch in raw for ch in ("\\", "@", "?", "#", "%")):
        return None
    scheme_sep = raw.find("://")
    if scheme_sep <= 0:
        return None
    scheme = raw[:scheme_sep].lower()
    if scheme not in _DEFAULT_PORTS:
        return None
    try:
        parts = urlsplit(raw)
        port = parts.port
    except ValueError:
        return None
    if parts.username is not None or parts.password is not None or parts.query or parts.fragment:
        return None
    netloc = parts.netloc
    if not netloc:
        return None
    if netloc.startswith("["):
        closing = netloc.find("]")
        if closing < 0:
            return None
        raw_host = netloc[: closing + 1]
        rest = netloc[closing + 1:]
    else:
        raw_host, separator, port_text = netloc.partition(":")
        rest = f"{separator}{port_text}"
    if rest and not re.fullmatch(r":[0-9]{1,5}", rest):
        return None
    host = _canonical_host(raw_host)
    if host is None:
        return None
    effective_port = port if port is not None else _DEFAULT_PORTS[scheme]
    if not 0 < effective_port < 65536:
        return None
    path = parts.path
    if path.endswith("/"):
        path = path[:-1]
    if not _PATH_PATTERN.match(path) or any(seg in {".", ".."} for seg in path.split("/")):
        return None
    return CanonicalBaseUrl(scheme=scheme, host=host, port=effective_port, path=path)


# (provider id, scheme, host, port, canonical base path, accepted input paths)
_OFFICIAL_CATALOG: Tuple[Tuple[str, str, str, int, str, Tuple[str, ...]], ...] = (
    ("openai", "https", "api.openai.com", 443, "/v1", ("/v1", "")),
    ("anthropic", "https", "api.anthropic.com", 443, "", ("", "/v1")),
    ("deepseek", "https", "api.deepseek.com", 443, "/v1", ("/v1", "")),
    ("groq", "https", "api.groq.com", 443, "/openai/v1", ("/openai/v1",)),
    ("gemini", "https", "generativelanguage.googleapis.com", 443, "/v1beta/openai", ("/v1beta/openai",)),
    ("xai", "https", "api.x.ai", 443, "/v1", ("/v1",)),
    ("openrouter", "https", "openrouter.ai", 443, "/api/v1", ("/api/v1",)),
)
_LOCAL_CATALOG: Tuple[Tuple[str, int, str, Tuple[str, ...]], ...] = (
    ("ollama", 11434, "", ("", "/v1")),
    ("lmstudio", 1234, "/v1", ("/v1", "")),
)
_LOCAL_HOSTS: Tuple[str, ...] = ("127.0.0.1", "localhost", "::1")


class DestinationRegistry:
    """Immutable lookup of approved destinations, keyed by canonical (scheme, host, port, path)."""

    def __init__(self, routes: Mapping[Tuple[str, str, int, str], Destination]):
        self._routes: Dict[Tuple[str, str, int, str], Destination] = dict(routes)
        self._entries: Tuple[Destination, ...] = tuple(
            sorted(set(self._routes.values()), key=lambda d: d.destination_id)
        )
        strictness = {POLICY_LOOPBACK: 0, POLICY_PUBLIC: 1, POLICY_OPERATOR_NETWORK: 2}
        policies: Dict[Tuple[str, int], str] = {}
        for entry in self._entries:
            key = (entry.host, entry.port)
            existing = policies.get(key)
            # One host:port listed under two policies keeps the stricter one (official beats operator).
            if existing is None or strictness[entry.address_policy] < strictness[existing]:
                policies[key] = entry.address_policy
        self._host_policies: Dict[Tuple[str, int], str] = policies

    @property
    def entries(self) -> Tuple[Destination, ...]:
        return self._entries

    def match(self, base_url: object) -> Optional[Destination]:
        """Return the approved destination for a requested base URL, or None (no DNS, no I/O)."""
        canonical = canonicalize_base_url(base_url)
        if canonical is None:
            return None
        return self._routes.get(canonical.key)

    def address_policy_for(self, host: str, port: int) -> Optional[str]:
        normalized = host.lower().rstrip(".")
        if normalized.startswith("[") and normalized.endswith("]"):
            normalized = normalized[1:-1]
        return self._host_policies.get((normalized, port))

    def snapshot(self) -> Tuple[Tuple[str, str, str, str, str, int, str], ...]:
        return tuple(
            (d.destination_id, d.provider, d.kind, d.scheme, d.host, d.port, d.base_path)
            for d in self._entries
        )


def _operator_provider(env_name: str, canonical: CanonicalBaseUrl) -> str:
    if env_name == ENV_OLLAMA_BASE_URL:
        return "ollama"
    if env_name == ENV_LMSTUDIO_BASE_URL:
        return "lmstudio"
    if canonical.port == 11434:
        return "ollama"
    return "openai_compatible"


def _operator_entry_rejection(canonical: CanonicalBaseUrl) -> Optional[str]:
    literal = _parse_ip(canonical.host)
    if literal is not None and is_always_denied_address(literal):
        return "address is never reachable (metadata, link-local, unspecified, multicast or reserved)"
    if canonical.host in {official[2] for official in _OFFICIAL_CATALOG}:
        return "official provider hosts only accept their built-in base paths"
    return None


def build_destination_registry(environ: Mapping[str, str]) -> DestinationRegistry:
    """Build the registry from the built-in catalog plus operator environment configuration.

    Malformed or forbidden operator values are dropped with one warning each and never widen the
    registry. Values are not logged (they may carry credentials in a malformed userinfo part).
    """
    routes: Dict[Tuple[str, str, int, str], Destination] = {}

    for provider, scheme, host, port, base_path, input_paths in _OFFICIAL_CATALOG:
        entry = Destination(provider, provider, KIND_OFFICIAL, scheme, host, port, base_path)
        for path in input_paths:
            routes[(scheme, host, port, path)] = entry

    for provider, port, base_path, input_paths in _LOCAL_CATALOG:
        for host in _LOCAL_HOSTS:
            entry = Destination(f"{provider}@{host}", provider, KIND_LOCAL, "http", host, port, base_path)
            for path in input_paths:
                routes[("http", host, port, path)] = entry

    operator_values: List[Tuple[str, int, str]] = []
    for env_name in (ENV_DOCTOR_LLM_BASE_URL, ENV_OLLAMA_BASE_URL, ENV_LMSTUDIO_BASE_URL):
        value = (environ.get(env_name) or "").strip()
        if value:
            operator_values.append((env_name, 1, value))
    allowed_items = [item.strip() for item in (environ.get(ENV_ALLOWED_BASE_URLS) or "").split(",")]
    for position, item in enumerate(allowed_items, start=1):
        if item:
            operator_values.append((ENV_ALLOWED_BASE_URLS, position, item))

    for serial, (env_name, position, value) in enumerate(operator_values, start=1):
        canonical = canonicalize_base_url(value)
        if canonical is None:
            logger.warning("Ignoring malformed LLM destination in %s (item %d)", env_name, position)
            continue
        if canonical.key in routes:
            continue
        rejection = _operator_entry_rejection(canonical)
        if rejection:
            logger.warning("Ignoring LLM destination in %s (item %d): %s", env_name, position, rejection)
            continue
        entry = Destination(
            f"operator-{serial}",
            _operator_provider(env_name, canonical),
            KIND_OPERATOR,
            canonical.scheme,
            canonical.host,
            canonical.port,
            canonical.path,
        )
        routes[canonical.key] = entry

    return DestinationRegistry(routes)


class DestinationPolicyResolver(AbstractResolver):
    """aiohttp resolver that enforces the destination address policy at connect time.

    CRITICAL: validation must run on the addresses the connector actually connects to. A separate
    pre-flight lookup is a DNS-rebinding TOCTOU bypass (the name can resolve to a public address
    for the check and to loopback/private/metadata for the connection).
    """

    def __init__(
        self,
        registry: DestinationRegistry,
        inner: Optional[AbstractResolver] = None,
        *,
        allow_unregistered_hosts: bool = False,
    ):
        self._registry = registry
        self._inner = inner if inner is not None else ThreadedResolver()
        self._allow_unregistered_hosts = allow_unregistered_hosts

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> List[ResolveResult]:
        policy = self._registry.address_policy_for(host, port)
        if policy is None:
            # IMPORTANT: decide by host *and* port. Request URLs are always built from registry
            # entries, so with proxy inheritance an unregistered host:port can only be the proxy
            # itself (e.g. a local proxy on localhost:7890); checking the host alone refuses it.
            if self._allow_unregistered_hosts:
                return await self._inner.resolve(host, port, family)
            raise DestinationPolicyError("destination host is not approved")
        results = await self._inner.resolve(host, port, family)
        if not results:
            raise DestinationPolicyError("destination host resolved to no address")
        for result in results:
            if not address_allowed(policy, str(result.get("host", ""))):
                raise DestinationPolicyError("destination host resolved to a forbidden address")
        return results

    async def close(self) -> None:
        await self._inner.close()


def is_destination_policy_error(exc: BaseException) -> bool:
    """Return whether an aiohttp client error was caused by a destination policy refusal."""
    seen = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, DestinationPolicyError):
            return True
        seen.add(id(current))
        os_error = getattr(current, "os_error", None)
        if isinstance(os_error, DestinationPolicyError):
            return True
        current = current.__cause__ or current.__context__
    return False


_REGISTRY: Optional[DestinationRegistry] = None


def get_destination_registry() -> DestinationRegistry:
    """Return the process registry, built once from the environment.

    ``register_api_routes`` calls this while ComfyUI loads the node, so approvals are fixed at
    startup; later environment changes in the same process do not alter them.
    """
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = build_destination_registry(os.environ)
    return _REGISTRY


__all__ = [
    "DESTINATION_NOT_ALLOWED",
    "DESTINATION_NOT_ALLOWED_MESSAGE",
    "Destination",
    "DestinationPolicyError",
    "DestinationPolicyResolver",
    "DestinationRegistry",
    "address_allowed",
    "build_destination_registry",
    "canonicalize_base_url",
    "get_destination_registry",
    "is_always_denied_address",
    "is_destination_policy_error",
    "is_public_address",
]
