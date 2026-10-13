"""Process-state restoration contract of the executable route-handler harness.

Kept in its own module so no other harness instance (for example a module-scoped fixture) is
active while restoration is measured.
"""

from __future__ import annotations

import os
import socket
import sys
import threading

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import PROJECT_ROOT, DoctorRouteHarness  # noqa: E402

_REAL_CONNECT = socket.socket.connect
_REAL_GETADDRINFO = socket.getaddrinfo
_SCRUBBED_VAR = "DOCTOR_LLM_" + "API_KEY"
_SCRUBBED_VALUE = "SYNTHETIC-SHOULD-BE-SCRUBBED"


def _user_dir_snapshot():
    user_dir = PROJECT_ROOT / "user"
    if not user_dir.exists():
        return None
    return sorted(
        (str(path.relative_to(user_dir)), path.stat().st_size, path.stat().st_mtime_ns)
        for path in user_dir.rglob("*")
    )


def test_harness_teardown_restores_process_state():
    original_stdout, original_stderr = sys.stdout, sys.stderr
    env_before = dict(os.environ)
    user_before = _user_dir_snapshot()
    os.environ[_SCRUBBED_VAR] = _SCRUBBED_VALUE
    try:
        with DoctorRouteHarness() as active:
            assert _SCRUBBED_VAR not in os.environ
            assert socket.socket.connect is not _REAL_CONNECT
            data_root = active.data_root
            assert active.request("GET", "/doctor/provider_defaults").status == 200
    finally:
        scrubbed_value = os.environ.pop(_SCRUBBED_VAR, None)

    assert scrubbed_value == _SCRUBBED_VALUE
    assert dict(os.environ) == env_before
    assert sys.stdout is original_stdout
    assert sys.stderr is original_stderr
    assert not [t for t in threading.enumerate() if t.name == "DoctorLogProcessor" and t.is_alive()]
    assert not [name for name in sys.modules if name.startswith("doctor_hostload_")]
    assert socket.socket.connect is _REAL_CONNECT
    assert socket.getaddrinfo is _REAL_GETADDRINFO
    assert data_root is not None and not data_root.exists()
    assert _user_dir_snapshot() == user_before


def test_harness_restores_state_when_entry_fails(monkeypatch):
    env_before = dict(os.environ)
    import tests.doctor_route_harness as harness_module

    def failing_init(self):
        raise RuntimeError("synthetic entry failure")

    monkeypatch.setattr(harness_module.DoctorRouteHarness, "_execute_package_init", failing_init)
    with pytest.raises(RuntimeError, match="synthetic entry failure"):
        with DoctorRouteHarness():
            pass

    assert dict(os.environ) == env_before
    assert socket.socket.connect is _REAL_CONNECT
    assert not [name for name in sys.modules if name.startswith("doctor_hostload_")]
