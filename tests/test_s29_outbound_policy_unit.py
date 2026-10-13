"""Unit contracts of the outbound destination policy (registry, canonicalizer, connect-time resolver)."""

from __future__ import annotations

import asyncio
import http.server
import importlib.util
import socket
import subprocess
import sys
import threading
import types
import warnings
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, Mock

import pytest

aiohttp = pytest.importorskip("aiohttp")

from services.outbound_policy import (  # noqa: E402
    DestinationPolicyError,
    DestinationPolicyResolver,
    address_allowed,
    build_destination_registry,
    canonicalize_base_url,
    is_destination_policy_error,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _FakeResolver(aiohttp.abc.AbstractResolver):
    def __init__(self, answers: List[str]):
        self.answers = answers
        self.calls: List[str] = []

    async def resolve(self, host, port=0, family=socket.AF_INET):
        self.calls.append(host)
        return [
            {"hostname": host, "host": ip, "port": port, "family": socket.AF_INET6 if ":" in ip else socket.AF_INET,
             "proto": 0, "flags": socket.AI_NUMERICHOST}
            for ip in self.answers
        ]

    async def close(self):
        return None


@pytest.mark.parametrize(
    "raw",
    [
        "https://user" + ":synthetic@api.openai.com/v1",  # userinfo vector, split for detect-secrets
        "https://api.openai.com/v1?x=1",
        "https://api.openai.com/v1#x",
        "https://api.openai.com\\@evil.test/v1",
        "https://api.openai.com%2f@evil.test/v1",
        "https://api.openai.com/v1/%2e%2e",
        "https://api.openai.com/v1/../v1",
        "https://api.openai.com/./v1",
        "https://api.openai.com//v1",
        "https://api.openai.com/v1\t",
        " https://api.openai.com/v1",
        "https://api.openai.com:0/v1",
        "https://api.openai.com:99999/v1",
        "https://api.openai.com:/v1",
        "https://xn--pple-43d.com/v1",
        "https://аpple.com/v1",
        "http://0x7f.1:11434",
        "http://2130706433:11434",
        "http://127.1:11434",
        "http://[fe80::1%25eth0]:11434",
        "file:///etc/passwd",
        "https:/api.openai.com/v1",
        "//api.openai.com/v1",
        None,
        123,
    ],
)
def test_canonicalizer_rejects_ambiguous_forms(raw):
    if raw == "https://xn--pple-43d.com/v1":
        # Punycode is ASCII and syntactically valid; it is accepted as a *different* host and can
        # never match an official entry.
        canonical = canonicalize_base_url(raw)
        assert canonical is not None and canonical.host == "xn--pple-43d.com"
        return
    assert canonicalize_base_url(raw) is None


def test_canonicalizer_normalizes_case_trailing_dot_default_port_and_slash():
    canonical = canonicalize_base_url("HTTPS://API.OpenAI.COM.:443/v1/")
    assert canonical is not None
    assert canonical.key == ("https", "api.openai.com", 443, "/v1")
    ipv6 = canonicalize_base_url("http://[0:0:0:0:0:0:0:1]:11434")
    assert ipv6 is not None and ipv6.host == "::1"


def test_registry_is_built_from_catalog_and_operator_environment_only():
    registry = build_destination_registry(
        {
            "DOCTOR_LLM_ALLOWED_BASE_URLS": "https://gw.example.test/v1, not a url, http://169.254.169.254/x,"
            " https://api.openai.com/v1/files, http://[fd00:ec2::254]/v1",
            "OLLAMA_BASE_URL": "http://ollama:11434",
        }
    )
    ids = {entry.destination_id for entry in registry.entries}
    assert {"openai", "anthropic", "deepseek", "groq", "gemini", "xai", "openrouter"} <= ids
    operator = [entry for entry in registry.entries if entry.kind == "operator"]
    assert sorted(entry.base_url for entry in operator) == ["http://ollama:11434", "https://gw.example.test/v1"]
    assert registry.match("https://api.openai.com/v1/files") is None
    assert registry.match("http://169.254.169.254/x") is None
    ollama = registry.match("http://ollama:11434")
    assert ollama is not None and ollama.provider == "ollama" and ollama.address_policy == "operator_network"
    assert registry.match("http://localhost:11434").address_policy == "loopback"
    assert registry.match("https://api.openai.com").address_policy == "public"
    with pytest.raises(Exception):
        registry.entries[0].host = "evil.test"  # frozen dataclass


@pytest.mark.parametrize(
    "policy, address, allowed",
    [
        ("public", "8.8.4.4", True),
        ("public", "2606:4700:4700::1111", True),
        ("public", "127.0.0.1", False),
        ("public", "10.1.2.3", False),
        ("public", "172.16.0.1", False),
        ("public", "192.168.1.1", False),
        ("public", "100.64.0.1", False),
        ("public", "100.100.100.200", False),
        ("public", "169.254.169.254", False),
        ("public", "0.0.0.0", False),
        ("public", "::1", False),
        ("public", "::ffff:127.0.0.1", False),
        ("public", "fd00:ec2::254", False),
        ("public", "64:ff9b::7f00:1", False),
        ("public", "2002:7f00:1::", False),
        ("public", "fe80::1", False),
        ("public", "not-an-ip", False),
        ("loopback", "127.0.0.1", True),
        ("loopback", "::1", True),
        ("loopback", "::ffff:127.0.0.1", True),
        ("loopback", "8.8.4.4", False),
        ("loopback", "10.0.0.1", False),
        ("operator_network", "192.168.1.5", True),
        ("operator_network", "172.17.0.2", True),
        ("operator_network", "100.101.1.1", True),
        ("operator_network", "8.8.4.4", True),
        ("operator_network", "127.0.0.1", False),
        ("operator_network", "::ffff:127.0.0.1", False),
        ("operator_network", "169.254.169.254", False),
        ("operator_network", "100.100.100.200", False),
        ("operator_network", "fd00:ec2::254", False),
        ("operator_network", "0.0.0.0", False),
        ("operator_network", "224.0.0.1", False),
        ("unknown-policy", "8.8.4.4", False),
    ],
)
def test_address_policy_matrix(policy, address, allowed):
    assert address_allowed(policy, address) is allowed


def _resolve(resolver, host, port):
    return asyncio.run(resolver.resolve(host, port))


@pytest.mark.parametrize("answer", ["127.0.0.1", "10.0.0.5", "100.64.3.3", "100.100.100.200", "169.254.169.254", "fd00:ec2::254"])
def test_resolver_refuses_official_host_resolving_to_restricted_address(answer):
    resolver = DestinationPolicyResolver(build_destination_registry({}), _FakeResolver([answer]))
    with pytest.raises(DestinationPolicyError):
        _resolve(resolver, "api.openai.com", 443)


def test_resolver_refuses_mixed_answers_and_unknown_hosts_and_accepts_public():
    registry = build_destination_registry({})
    mixed = DestinationPolicyResolver(registry, _FakeResolver(["8.8.4.4", "127.0.0.1"]))
    with pytest.raises(DestinationPolicyError):
        _resolve(mixed, "api.openai.com", 443)

    unknown = _FakeResolver(["8.8.4.4"])
    with pytest.raises(DestinationPolicyError):
        _resolve(DestinationPolicyResolver(registry, unknown), "public.probe.test", 443)
    assert unknown.calls == []  # refused before any lookup

    wrong_port = _FakeResolver(["8.8.4.4"])
    with pytest.raises(DestinationPolicyError):
        _resolve(DestinationPolicyResolver(registry, wrong_port), "api.openai.com", 8443)

    ok = _resolve(DestinationPolicyResolver(registry, _FakeResolver(["8.8.4.4"])), "api.openai.com.", 443)
    assert [item["host"] for item in ok] == ["8.8.4.4"]


def test_resolver_local_entries_accept_only_loopback_answers():
    registry = build_destination_registry({})
    with pytest.raises(DestinationPolicyError):
        _resolve(DestinationPolicyResolver(registry, _FakeResolver(["8.8.4.4"])), "localhost", 11434)
    ok = _resolve(DestinationPolicyResolver(registry, _FakeResolver(["127.0.0.1", "::1"])), "localhost", 11434)
    assert len(ok) == 2


def test_resolver_proxy_mode_passes_only_unregistered_hosts():
    registry = build_destination_registry({})
    proxied = DestinationPolicyResolver(registry, _FakeResolver(["10.9.9.9"]), allow_unregistered_hosts=True)
    assert _resolve(proxied, "proxy.corp.test", 3128)[0]["host"] == "10.9.9.9"
    with pytest.raises(DestinationPolicyError):
        _resolve(proxied, "api.openai.com", 443)  # registry hosts stay enforced (NO_PROXY path)


def test_resolver_proxy_mode_accepts_localhost_proxy_on_an_unregistered_port():
    registry = build_destination_registry({})
    proxied = DestinationPolicyResolver(registry, _FakeResolver(["127.0.0.1"]), allow_unregistered_hosts=True)
    assert _resolve(proxied, "localhost", 7890)[0]["host"] == "127.0.0.1"
    # The registered local destination on the same host keeps its loopback-only policy.
    rebound = DestinationPolicyResolver(registry, _FakeResolver(["8.8.8.8"]), allow_unregistered_hosts=True)
    with pytest.raises(DestinationPolicyError):
        _resolve(rebound, "localhost", 11434)
    strict = DestinationPolicyResolver(registry, _FakeResolver(["127.0.0.1"]))
    with pytest.raises(DestinationPolicyError):
        _resolve(strict, "localhost", 7890)


def test_docker_service_names_with_underscores_are_canonical_hosts():
    canonical = canonicalize_base_url("http://My_Ollama:11434")
    assert canonical is not None and canonical.key == ("http", "my_ollama", 11434, "")
    registry = build_destination_registry({"DOCTOR_LLM_ALLOWED_BASE_URLS": "http://llm_gateway.internal_net:8080/v1"})
    entry = registry.match("http://llm_gateway.internal_net:8080/v1")
    assert entry is not None and entry.base_url == "http://llm_gateway.internal_net:8080/v1"
    # aiohttp's URL parser keeps the same host, so the connector resolves exactly the approved name.
    from yarl import URL

    assert URL("http://my_ollama:11434/api/tags").host == "my_ollama"
    for raw in ("http://_:11434", "http://my ollama:11434", "http://-ollama:11434", "http://ollama-:11434"):
        assert canonicalize_base_url(raw) is None, raw


@pytest.mark.parametrize(
    ("policy", "address"),
    [
        ("public", "::127.0.0.1"),            # IPv4-compatible (deprecated) form of loopback
        ("public", "::8.8.8.8"),              # IPv4-compatible forms are never public destinations
        ("public", "fec0::1"),                # deprecated site-local
        ("operator_network", "64:ff9b::a9fe:a9fe"),   # NAT64 of 169.254.169.254
        ("operator_network", "2002:a9fe:a9fe::1"),    # 6to4 of 169.254.169.254
        ("operator_network", "::169.254.169.254"),    # IPv4-compatible metadata
        ("operator_network", "64:ff9b::7f00:1"),      # NAT64 of 127.0.0.1
        ("operator_network", "2002:7f00:1::1"),       # 6to4 of 127.0.0.1
    ],
)
def test_embedded_ipv4_and_deprecated_ipv6_forms_are_refused(policy, address):
    assert address_allowed(policy, address) is False


def test_operator_ip_literal_embedding_metadata_is_dropped_and_loopback_entries_stay():
    registry = build_destination_registry(
        {"DOCTOR_LLM_ALLOWED_BASE_URLS": "http://[64:ff9b::a9fe:a9fe]:8080/v1,http://[::1]:8081/v1"}
    )
    assert registry.match("http://[64:ff9b::a9fe:a9fe]:8080/v1") is None
    assert registry.match("http://[::1]:8081/v1") is not None
    assert address_allowed("loopback", "::1") is True
    assert address_allowed("operator_network", "192.168.1.20") is True
    assert address_allowed("public", "2606:4700::1111") is True


def test_real_connector_with_policy_resolver_never_connects_to_rebound_loopback():
    hits: List[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            return None

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    registry = build_destination_registry({"DOCTOR_LLM_ALLOWED_BASE_URLS": f"http://rebind.unit.test:{port}/v1"})

    async def scenario():
        resolver = DestinationPolicyResolver(registry, _FakeResolver(["127.0.0.1"]))
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(resolver=resolver)) as session:
            with pytest.raises(aiohttp.ClientError) as caught:
                async with session.get(f"http://rebind.unit.test:{port}/v1/models", allow_redirects=False):
                    pass
            return caught.value

    loop = asyncio.SelectorEventLoop()
    try:
        error = loop.run_until_complete(scenario())
    finally:
        loop.close()
        server.shutdown()
        server.server_close()

    assert hits == []
    assert is_destination_policy_error(error)


def test_policy_module_loads_on_aiohttp_without_resolve_result(monkeypatch):
    # aiohttp 3.9 has AbstractResolver but no aiohttp.abc.ResolveResult (added in 3.10); the node
    # uses the host's bundled aiohttp, so the policy module must still import there.
    legacy_abc = types.ModuleType("aiohttp.abc")
    legacy_abc.__dict__.update(
        {name: value for name, value in vars(aiohttp.abc).items() if name not in {"ResolveResult", "__name__"}}
    )
    assert not hasattr(legacy_abc, "ResolveResult")
    monkeypatch.setitem(sys.modules, "aiohttp.abc", legacy_abc)

    spec = importlib.util.spec_from_file_location(
        "s29_legacy_aiohttp_outbound_policy", PROJECT_ROOT / "services" / "outbound_policy.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)  # @dataclass resolves its module via sys.modules
    spec.loader.exec_module(module)

    registry = module.build_destination_registry({})
    resolver = module.DestinationPolicyResolver(registry, _FakeResolver(["127.0.0.1"]))
    assert isinstance(resolver, aiohttp.abc.AbstractResolver)
    assert _resolve(resolver, "localhost", 11434)[0]["host"] == "127.0.0.1"


def test_retry_client_treats_redirect_as_failure():
    from llm_client import RetryConfig, llm_request_with_retry

    response = Mock()
    response.status = 302
    response.headers = {"Location": "http://127.0.0.1/internal"}
    response.release = Mock()
    session = Mock()
    session.request = AsyncMock(return_value=response)

    result = asyncio.run(
        llm_request_with_retry(session, "POST", "https://api.openai.com/v1/chat/completions", config=RetryConfig(add_idempotency_key=False))
    )

    assert result.success is False
    assert "302" in (result.error or "")
    assert session.request.call_args.kwargs["allow_redirects"] is False


def test_static_outbound_check_enforces_redirect_and_session_rules(tmp_path):
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    try:
        from check_outbound_safety import OutboundSafetyChecker, check_file
    finally:
        sys.path.pop(0)
    assert OutboundSafetyChecker is not None
    bad = tmp_path / "bad_client.py"
    bad.write_text(
        "import aiohttp\n"
        "async def fetch(url):\n"
        "    async with aiohttp.ClientSession() as session:\n"
        "        async with session.get(url) as response:\n"
        "            return await response.text()\n",
        encoding="utf-8",
    )
    rules = {violation.rule for violation in check_file(bad)}
    assert {"CLIENT_SESSION_OUTSIDE_POLICY", "REDIRECT_NOT_DISABLED"} <= rules

    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "check_outbound_safety.py")],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _checker_module():
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    try:
        import check_outbound_safety
    finally:
        sys.path.pop(0)
    return check_outbound_safety


def _rules(checker, root: Path, relative: str, source: str) -> set:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return {violation.rule for violation in checker.check_file(path, project_root=root)}


def test_static_outbound_check_resolves_aliases_and_policy_files(tmp_path):
    checker = _checker_module()

    aliased = (
        "from aiohttp import ClientSession as CS, TCPConnector as TC, request as fetch\n"
        "import aiohttp as ah\n"
        "async def run(url):\n"
        "    CS()\n"
        "    TC()\n"
        "    ah.client.ClientSession()\n"
        "    await fetch('GET', url)\n"
        "    await ah.request('GET', url)\n"
    )
    rules = _rules(checker, tmp_path, "services/aliased.py", aliased)
    assert {"CLIENT_SESSION_OUTSIDE_POLICY", "REDIRECT_NOT_DISABLED"} <= rules

    # Only the exact repository paths are session factories, not any file with the same name.
    lookalike = "import aiohttp\ndef make():\n    return aiohttp.ClientSession(connector=aiohttp.TCPConnector(resolver=None))\n"
    assert "CLIENT_SESSION_OUTSIDE_POLICY" in _rules(checker, tmp_path, "plugins/session_manager.py", lookalike)

    # The policy session factory must install a resolver on every connector and pass the connector.
    factory = (
        "import aiohttp\n"
        "def make(resolver):\n"
        "    aiohttp.ClientSession(connector=aiohttp.TCPConnector())\n"
        "    aiohttp.ClientSession()\n"
        "    return aiohttp.ClientSession(connector=aiohttp.TCPConnector(resolver=resolver))\n"
    )
    factory_violations = [
        v.rule for v in checker.check_file(_write(tmp_path / "session_manager.py", factory), project_root=tmp_path)
    ]
    assert factory_violations.count("CONNECTOR_WITHOUT_POLICY_RESOLVER") == 1
    assert factory_violations.count("SESSION_WITHOUT_POLICY_CONNECTOR") == 1

    # Policy rules cannot be silenced with the sanitization-funnel nosec marker.
    suppressed = (
        "import aiohttp\n"
        "async def run(url):\n"
        "    async with aiohttp.ClientSession() as session:  # nosec: outbound-bypass-allowed\n"
        "        await session.get(url)  # nosec: outbound-bypass-allowed\n"
    )
    assert {"CLIENT_SESSION_OUTSIDE_POLICY", "REDIRECT_NOT_DISABLED"} <= _rules(
        checker, tmp_path, "services/suppressed.py", suppressed
    )

    # Raw HTTP clients outside aiohttp are not allowed in shipped code.
    raw_clients = "import requests\nimport urllib.request\nfrom httpx import AsyncClient\nimport http.client\n"
    assert "RAW_HTTP_CLIENT_IMPORT" in _rules(checker, tmp_path, "services/raw_clients.py", raw_clients)

    # Unparseable files fail closed.
    assert "PARSE_ERROR" in _rules(checker, tmp_path, "services/broken.py", "def broken(:\n")


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def test_static_outbound_check_skips_only_whole_path_segments(tmp_path):
    checker = _checker_module()
    checked = [
        "latests/client.py",
        "evil_outbound.py",
        "services/my_sanitizer.py",
        "web_reference/client.py",
    ]
    skipped = [
        "tests/test_x.py",
        "services/tests/test_y.py",
        "reference/repo/client.py",
        ".planning/x.py",
        "outbound.py",
        "sanitizer.py",
        "pipeline/stages/sanitizer.py",
    ]
    for relative in checked:
        assert checker.should_check_file(tmp_path / relative, tmp_path) is True, relative
    for relative in skipped:
        assert checker.should_check_file(tmp_path / relative, tmp_path) is False, relative


def test_comfyignore_excludes_non_runtime_files_from_the_published_archive():
    pathspec = pytest.importorskip("pathspec")
    ignore_file = PROJECT_ROOT / ".comfyignore"
    patterns = [
        line.strip()
        for line in ignore_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    with warnings.catch_warnings():
        # comfy-cli builds the spec with the "gitwildmatch" factory; mirror it exactly even though
        # newer pathspec releases deprecate that name.
        warnings.simplefilter("ignore", DeprecationWarning)
        spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    tracked = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "ls-files"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    shipped = [path for path in tracked if not spec.match_file(path)]

    assert shipped, "archive would be empty"
    for prefix in ("tests/", "scripts/", ".github/", ".githooks/"):
        assert not [path for path in shipped if path.startswith(prefix)], prefix
    for name in ("package-lock.json", "package.json", "playwright.config.js", "vitest.config.js",
                 "requirements-dev.txt", ".pre-commit-config.yaml", ".secrets.baseline"):
        assert name not in shipped
    for runtime in ("__init__.py", "api_routes.py", "pyproject.toml", "services/outbound_policy.py",
                    "web/doctor.js", "i18n_data/en.json", "LICENSE", "README.md"):
        assert runtime in shipped, runtime


def test_destination_guidance_is_localized_in_all_supported_languages():
    import json

    texts = {}
    for lang in ("en", "zh_TW", "zh_CN", "ja", "de", "fr", "it", "es", "ko"):
        data = json.loads((PROJECT_ROOT / "i18n_data" / f"{lang}.json").read_text(encoding="utf-8-sig"))
        text = data["ui_text"].get("llm_destination_not_allowed", "")
        assert "DOCTOR_LLM_ALLOWED_BASE_URLS" in text, lang
        texts[lang] = text
    assert len(set(texts.values())) == len(texts)  # every language has its own translation
