"""Unit contracts of the outbound destination policy (registry, canonicalizer, connect-time resolver)."""

from __future__ import annotations

import asyncio
import http.server
import socket
import subprocess
import sys
import threading
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
