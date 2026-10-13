"""Executable route-handler harness for ComfyUI-Doctor tests.

This helper (not collected by pytest: no ``test_`` prefix) executes the real package
``__init__.py`` host-style inside a synthetic package, registers the real PromptServer routes on an
``aiohttp`` ``RouteTableDef`` and serves them through ``aiohttp.test_utils.TestServer`` on loopback.

Isolation guarantees for the harness lifetime:

- credential/admin/proxy environment variables are scrubbed before import and restored afterwards;
- Doctor data is redirected to a temporary directory through a stub ``folder_paths`` module;
- outbound provider traffic is replaced by in-process capture fakes (``captured`` records the
  method, URL, headers and JSON of every attempted provider request);
- an egress guard refuses every non-loopback socket connect and every DNS lookup that is not in the
  explicit fake DNS table, and refuses the default local-LLM ports so a real Ollama/LM Studio
  instance is never contacted.

Typical use::

    with DoctorRouteHarness() as harness:
        response = harness.request("POST", "/doctor/list_models", json={...})
        assert response.status == 200
        assert harness.captured == []
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import importlib.util
import io
import ipaddress
import json as jsonlib
import os
import shutil
import socket
import sys
import tempfile
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple, TypeVar

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_host_load.py"

#: Public answer returned by the fake DNS table. Nothing ever connects to it: provider traffic is
#: faked and the egress guard refuses non-loopback connects.
PUBLIC_TEST_ANSWER = "8.8.4.4"

#: Official provider hosts resolvable inside the harness (deterministic SSRF-validator DNS step).
DEFAULT_DNS_TABLE: Mapping[str, Tuple[str, ...]] = {
    host: (PUBLIC_TEST_ANSWER,)
    for host in (
        "api.openai.com",
        "api.anthropic.com",
        "api.deepseek.com",
        "api.groq.com",
        "generativelanguage.googleapis.com",
        "api.x.ai",
        "openrouter.ai",
    )
}

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
_BLOCKED_LOOPBACK_PORTS = frozenset({11434, 1234})
_SCRUBBED_ENV_TOKENS = ("API_KEY", "DOCTOR", "TOKEN", "SECRET", "PROXY")
_HOST_STUB_NAMES = ("folder_paths", "server", "torch")

T = TypeVar("T")


class EgressBlocked(OSError):
    """Raised by the harness egress guard for any forbidden connect or DNS lookup."""


def _is_ip_literal(name: str) -> bool:
    try:
        ipaddress.ip_address(name.strip("[]"))
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class CapturedRequest:
    """One provider request attempted by a handler (never sent anywhere)."""

    via: str
    method: str
    url: str
    headers: Mapping[str, str]
    json: Optional[Mapping[str, Any]]

    def header_names(self) -> frozenset:
        return frozenset(name.lower() for name in self.headers)

    def header(self, name: str) -> Optional[str]:
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return None


def _default_stream_chunks() -> Tuple[bytes, ...]:
    return (
        b'data: {"choices":[{"delta":{"content":"harness-ok"}}]}\n\n',
        b"data: [DONE]\n\n",
    )


def _default_json_body() -> Dict[str, Any]:
    return {
        "choices": [{"message": {"content": "harness-ok"}}],
        "message": {"content": "harness-ok"},
        "data": [{"id": "harness-model"}],
        "models": [{"name": "harness-model"}],
    }


@dataclass
class ProviderReply:
    """Deterministic reply returned by the provider fakes."""

    status: int = 200
    json_body: Any = field(default_factory=_default_json_body)
    stream_chunks: Tuple[bytes, ...] = field(default_factory=_default_stream_chunks)


@dataclass(frozen=True)
class HarnessResponse:
    """Status and body of one harness route call."""

    status: int
    text: str

    def json(self) -> Any:
        return jsonlib.loads(self.text)


class _FakeContent:
    def __init__(self, chunks: Sequence[bytes]):
        self._chunks = tuple(chunks)

    async def iter_chunked(self, _size: int):
        for chunk in self._chunks:
            yield chunk

    async def iter_any(self):
        for chunk in self._chunks:
            yield chunk


class _FakeProviderResponse:
    def __init__(self, reply: ProviderReply):
        self.status = reply.status
        self.headers: Dict[str, str] = {}
        self._reply = reply
        self.content = _FakeContent(reply.stream_chunks)

    async def __aenter__(self) -> "_FakeProviderResponse":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def json(self, **_kwargs: Any) -> Any:
        return self._reply.json_body

    async def text(self) -> str:
        return jsonlib.dumps(self._reply.json_body)

    def close(self) -> None:
        return None

    def release(self) -> None:
        return None


class _FakeSession:
    def __init__(self, harness: "DoctorRouteHarness"):
        self._harness = harness

    def _record(self, method: str, url: Any, headers: Optional[Mapping[str, str]], json_body: Any) -> _FakeProviderResponse:
        self._harness.captured.append(
            CapturedRequest(
                via="session",
                method=method.upper(),
                url=str(url),
                headers=dict(headers or {}),
                json=json_body if isinstance(json_body, Mapping) else None,
            )
        )
        return _FakeProviderResponse(self._harness.provider_reply)

    def get(self, url: Any, *, headers: Optional[Mapping[str, str]] = None, **_kwargs: Any) -> _FakeProviderResponse:
        return self._record("GET", url, headers, None)

    def post(self, url: Any, *, headers: Optional[Mapping[str, str]] = None, json: Any = None, **_kwargs: Any) -> _FakeProviderResponse:
        return self._record("POST", url, headers, json)

    def request(self, method: str, url: Any, *, headers: Optional[Mapping[str, str]] = None, json: Any = None, **_kwargs: Any) -> _FakeProviderResponse:
        return self._record(method, url, headers, json)


class _EgressGuard:
    """Loopback-only socket/DNS guard with an explicit fake DNS table."""

    def __init__(self, dns_table: Mapping[str, Sequence[str]]):
        self._dns_table = {name.lower(): tuple(ips) for name, ips in dns_table.items()}
        self.blocked: List[str] = []
        self._saved: Optional[Tuple[Any, Any, Any]] = None

    def _check_target(self, address: Any) -> None:
        host = str(address[0]) if isinstance(address, tuple) and address else str(address)
        port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
        if host not in _LOOPBACK_HOSTS or port in _BLOCKED_LOOPBACK_PORTS:
            self.blocked.append(f"connect:{host}:{port}")
            raise EgressBlocked(f"harness egress guard refused connect to {host!r}:{port}")

    def install(self) -> None:
        real_connect = socket.socket.connect
        real_connect_ex = socket.socket.connect_ex
        real_getaddrinfo = socket.getaddrinfo
        self._saved = (real_connect, real_connect_ex, real_getaddrinfo)
        guard = self

        def connect(sock: socket.socket, address: Any) -> Any:
            guard._check_target(address)
            return real_connect(sock, address)

        def connect_ex(sock: socket.socket, address: Any) -> Any:
            guard._check_target(address)
            return real_connect_ex(sock, address)

        def getaddrinfo(host: Any, port: Any = None, *args: Any, **kwargs: Any) -> Any:
            name = "" if host is None else str(host)
            if name in _LOOPBACK_HOSTS or _is_ip_literal(name):
                # Numeric hosts resolve locally without a DNS query; connect() is still guarded.
                return real_getaddrinfo(host, port, *args, **kwargs)
            answers = guard._dns_table.get(name.lower().rstrip("."))
            if answers is None:
                guard.blocked.append(f"dns:{name}")
                raise socket.gaierror(f"harness egress guard refused DNS lookup for {name!r}")
            numeric_port = port if isinstance(port, int) else 0
            return [
                (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, numeric_port))
                for ip in answers
            ]

        socket.socket.connect = connect  # type: ignore[method-assign]
        socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
        socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]

    def uninstall(self) -> None:
        if self._saved is None:
            return
        real_connect, real_connect_ex, real_getaddrinfo = self._saved
        socket.socket.connect = real_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = real_connect_ex  # type: ignore[method-assign]
        socket.getaddrinfo = real_getaddrinfo  # type: ignore[assignment]
        self._saved = None


def _load_validator() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("doctor_route_harness_host_load", _VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DoctorRouteHarness:
    """Context manager that executes the real Doctor package and serves its routes on loopback."""

    def __init__(
        self,
        *,
        env: Optional[Mapping[str, str]] = None,
        dns_table: Optional[Mapping[str, Sequence[str]]] = None,
    ) -> None:
        self._env_overrides = dict(env or {})
        self.guard = _EgressGuard(DEFAULT_DNS_TABLE if dns_table is None else dns_table)
        self.captured: List[CapturedRequest] = []
        self.provider_reply = ProviderReply()
        self.startup_output = ""
        self.package_name = ""
        self.data_root: Optional[Path] = None
        self._route_table: Optional[web.RouteTableDef] = None
        self._stack: Optional[contextlib.ExitStack] = None

    # ------------------------------------------------------------------ lifecycle
    def __enter__(self) -> "DoctorRouteHarness":
        stack = contextlib.ExitStack()
        try:
            stack.callback(self._restore_env, dict(os.environ))
            for key in list(os.environ):
                if any(token in key.upper() for token in _SCRUBBED_ENV_TOKENS):
                    del os.environ[key]
            os.environ.update(self._env_overrides)

            self.data_root = Path(tempfile.mkdtemp(prefix="doctor-route-harness-"))
            stack.callback(shutil.rmtree, self.data_root, True)

            saved_stubs = {name: sys.modules.get(name) for name in _HOST_STUB_NAMES}
            stack.callback(self._restore_host_stubs, saved_stubs)
            self._route_table = self._install_host_stubs(self.data_root)

            self.guard.install()
            stack.callback(self.guard.uninstall)

            validator = _load_validator()
            self.package_name = stack.enter_context(validator.synthetic_package_import_context(PROJECT_ROOT))
            self._execute_package_init()
            self._install_outbound_fakes()
        except BaseException:
            stack.close()
            raise
        self._stack = stack
        return self

    def __exit__(self, *_exc: object) -> None:
        stack, self._stack = self._stack, None
        if stack is not None:
            stack.close()

    @staticmethod
    def _restore_env(saved: Dict[str, str]) -> None:
        os.environ.clear()
        os.environ.update(saved)

    @staticmethod
    def _restore_host_stubs(saved: Mapping[str, Optional[types.ModuleType]]) -> None:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    @staticmethod
    def _install_host_stubs(data_root: Path) -> web.RouteTableDef:
        routes = web.RouteTableDef()

        folder_paths = types.ModuleType("folder_paths")
        folder_paths.get_system_user_directory = (  # type: ignore[attr-defined]
            lambda name="comfyui_doctor": str(data_root / "system_user" / name)
        )
        folder_paths.get_user_directory = lambda: str(data_root / "user")  # type: ignore[attr-defined]
        folder_paths.folder_names_and_paths = {}  # type: ignore[attr-defined]
        sys.modules["folder_paths"] = folder_paths

        server = types.ModuleType("server")
        prompt_server = type("PromptServer", (), {"instance": types.SimpleNamespace(routes=routes)})
        server.PromptServer = prompt_server  # type: ignore[attr-defined]
        sys.modules["server"] = server

        if importlib.util.find_spec("torch") is None:
            torch = types.ModuleType("torch")
            torch.__version__ = "0.0-harness-stub"  # type: ignore[attr-defined]
            torch.Tensor = type("Tensor", (), {})  # type: ignore[attr-defined]
            torch.cuda = types.SimpleNamespace(is_available=lambda: False)  # type: ignore[attr-defined]
            sys.modules["torch"] = torch
        return routes

    def _execute_package_init(self) -> None:
        package = sys.modules[self.package_name]
        init_path = PROJECT_ROOT / "__init__.py"
        sink = io.StringIO()
        original_stdout, original_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout = sink
            sys.stderr = sink
            # IMPORTANT: execute the canonical entrypoint unchanged (T31 invariant: never rename or
            # rewrite the production __init__.py to make tests import it).
            exec(compile(init_path.read_text(encoding="utf-8"), str(init_path), "exec"), package.__dict__)
        finally:
            # CRITICAL: the Doctor logger wraps sys.stdout/sys.stderr and starts a daemon thread.
            # Uninstall it before restoring the streams; skipping this leaves SafeStreamWrapper around
            # pytest's capture and corrupts every later test in the session.
            logger_module = sys.modules.get(f"{self.package_name}.logger")
            if logger_module is not None and hasattr(logger_module, "uninstall"):
                logger_module.uninstall()
            sys.stdout, sys.stderr = original_stdout, original_stderr
        self.startup_output = sink.getvalue()

    def _install_outbound_fakes(self) -> None:
        api_routes = self.module("api_routes")
        llm_client = self.module("llm_client")
        system_info = self.module("system_info")
        harness = self

        async def fake_llm_request_with_retry(
            _session: Any,
            method: str,
            url: str,
            *,
            json: Any = None,
            headers: Optional[Mapping[str, str]] = None,
            **_kwargs: Any,
        ) -> Any:
            harness.captured.append(
                CapturedRequest(
                    via="llm_request_with_retry",
                    method=method.upper(),
                    url=str(url),
                    headers=dict(headers or {}),
                    json=json if isinstance(json, Mapping) else None,
                )
            )
            reply = harness.provider_reply
            success = reply.status < 400
            return llm_client.RetryResult(
                response=_FakeProviderResponse(reply),
                success=success,
                attempts=1,
                total_time=0.0,
                error=None if success else f"HTTP {reply.status}",
                idempotency_key="harness",
            )

        async def fake_get_session(*_args: Any, **_kwargs: Any) -> _FakeSession:
            return _FakeSession(harness)

        def fake_system_environment(force_refresh: bool = False) -> Dict[str, Any]:
            # Same keys as system_info.get_system_environment, without the pip subprocess.
            return {
                "os": "HarnessOS 1.0",
                "os_version": "harness",
                "python_version": "3.11.0",
                "environment_type": "harness",
                "runtime_layout_source": "harness",
                "pytorch_info": {"pytorch_version": "0.0-harness", "cuda_available": False},
                "installed_packages": "",
                "cache_age_seconds": 0,
            }

        api_routes.llm_request_with_retry = fake_llm_request_with_retry
        api_routes.SessionManager.get_session = staticmethod(fake_get_session)
        api_routes.get_system_environment = fake_system_environment
        system_info.get_system_environment = fake_system_environment

    # ------------------------------------------------------------------ accessors
    def module(self, dotted_name: str) -> types.ModuleType:
        """Return a module of the synthetic Doctor package (imported on demand)."""
        full_name = f"{self.package_name}.{dotted_name}"
        loaded = sys.modules.get(full_name)
        if loaded is not None:
            return loaded
        return importlib.import_module(full_name)

    @property
    def registered_operations(self) -> List[Tuple[str, str]]:
        if self._route_table is None:
            return []
        operations = []
        for route in self._route_table:
            method = getattr(route, "method", "")
            path = getattr(route, "path", "")
            if method and path:
                operations.append((method.upper(), path))
        return sorted(operations)

    @contextlib.contextmanager
    def patched_env(self, **values: str) -> Iterator[None]:
        """Temporarily set environment variables (restored on exit)."""
        saved = {key: os.environ.get(key) for key in values}
        os.environ.update(values)
        try:
            yield
        finally:
            for key, previous in saved.items():
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous

    # ------------------------------------------------------------------ execution
    def run(self, scenario: Callable[[TestClient], Awaitable[T]]) -> T:
        """Run ``scenario(client)`` against the registered routes on a fresh selector loop."""
        if self._route_table is None:
            raise RuntimeError("DoctorRouteHarness is not active")
        # IMPORTANT: an explicit selector loop routes connects through socket.connect so the egress
        # guard applies on Windows (the default proactor loop bypasses it) without mutating the
        # process-wide event-loop policy.
        loop = asyncio.SelectorEventLoop()
        try:
            return loop.run_until_complete(self._serve(scenario))
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    async def _serve(self, scenario: Callable[[TestClient], Awaitable[T]]) -> T:
        app = web.Application()
        app.add_routes(self._route_table or [])
        client = TestClient(TestServer(app, host="127.0.0.1"))
        await client.start_server()
        try:
            return await scenario(client)
        finally:
            await client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> HarnessResponse:
        """Perform one HTTP call against the real handler and return its status and body."""

        async def scenario(client: TestClient) -> HarnessResponse:
            response = await client.request(method, path, json=json, headers=dict(headers or {}))
            return HarnessResponse(status=response.status, text=await response.text())

        return self.run(scenario)
