"""Secret routes with a locked encrypted store (executed through the real route handlers).

When the configured key is missing or wrong, ``GET /doctor/secrets/status`` reports the store state
without secret material, ``PUT /doctor/secrets`` and ``DELETE /doctor/secrets/{provider}`` return the
stable ``secret_store_locked`` envelope, and none of the calls renames or rewrites the store.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Iterator, Optional

import pytest

pytest.importorskip("aiohttp")

from tests.doctor_route_harness import DoctorRouteHarness  # noqa: E402

ADMIN_TOKEN = "S28-SYNTHETIC-ADMIN-TOKEN"  # pragma: allowlist secret
KEY_A = "s28-route-synthetic-key-a"  # pragma: allowlist secret
KEY_B = "s28-route-synthetic-key-b"  # pragma: allowlist secret
ORIGINAL = "S28-ROUTE-SYNTHETIC-ORIGINAL"  # pragma: allowlist secret
NEW_VALUE = "S28-ROUTE-SYNTHETIC-NEW"  # pragma: allowlist secret
ADMIN = {"X-Doctor-Admin-Token": ADMIN_TOKEN}
SECRET_MATERIAL = (KEY_A, KEY_B, ORIGINAL, NEW_VALUE)


@pytest.fixture(scope="module")
def harness() -> Iterator[DoctorRouteHarness]:
    with DoctorRouteHarness() as active:
        yield active


def _env(key: Optional[str]) -> Dict[str, str]:
    values = {"DOCTOR_ADMIN_TOKEN": ADMIN_TOKEN, "DOCTOR_SECRET_STORE_WINDOWS_ACL_HARDEN": "0"}
    if key:
        values["DOCTOR_SECRET_STORE_ENCRYPTION_KEY"] = key
    return values


@pytest.fixture
def store_path(harness) -> Iterator[Path]:
    module = harness.module("services.secret_store")
    module._secret_store = None
    with harness.patched_env(**_env(KEY_A)):
        store = module.get_secret_store()
        store.set_secret("openai", ORIGINAL)
    path = Path(store.filepath)
    module._secret_store = None
    try:
        yield path
    finally:
        module._secret_store = None
        for item in path.parent.glob(f"{path.name}*"):
            item.unlink()


def _snapshot(path: Path) -> Dict[str, str]:
    return {
        item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.parent.glob(f"{path.name}*"))
    }


@pytest.mark.parametrize(
    ("key", "state"),
    [(None, "locked_key_required"), (KEY_B, "locked_key_mismatch")],
    ids=["missing-key", "wrong-key"],
)
def test_locked_store_routes_fail_closed_without_touching_the_store(harness, store_path, key, state):
    before = _snapshot(store_path)
    module = harness.module("services.secret_store")

    with harness.patched_env(**_env(key)):
        module._secret_store = None
        status = harness.request("GET", "/doctor/secrets/status", headers=ADMIN)
        put = harness.request("PUT", "/doctor/secrets", json={"provider": "openai", "api_key": NEW_VALUE}, headers=ADMIN)
        delete = harness.request("DELETE", "/doctor/secrets/openai", headers=ADMIN)

    status_body = status.json()
    observed = {
        "status": status.status,
        "store_state": (status_body.get("store") or {}).get("state"),
        "openai_configured": status_body.get("providers", {}).get("openai", {}).get("configured"),
        "put": (put.status, put.json().get("error")),
        "delete": (delete.status, delete.json().get("error")),
        "files_unchanged": _snapshot(store_path) == before,
    }
    assert observed == {
        "status": 200,
        "store_state": state,
        "openai_configured": False,
        "put": (409, "secret_store_locked"),
        "delete": (409, "secret_store_locked"),
        "files_unchanged": True,
    }
    for response in (status, put, delete):
        assert not [value for value in SECRET_MATERIAL if value in response.text]
        assert str(store_path.parent) not in response.text

    with harness.patched_env(**_env(KEY_A)):
        module._secret_store = None
        assert module.get_secret_store().get_secret("openai") == ORIGINAL


def test_unlocked_store_reports_ok_and_saves(harness, store_path):
    module = harness.module("services.secret_store")
    with harness.patched_env(**_env(KEY_A)):
        module._secret_store = None
        status = harness.request("GET", "/doctor/secrets/status", headers=ADMIN)
        put = harness.request("PUT", "/doctor/secrets", json={"provider": "generic", "api_key": NEW_VALUE}, headers=ADMIN)
        reread = module.get_secret_store().get_secret("generic")

    assert status.status == 200
    assert status.json()["store"] == {"state": "ok"}
    assert status.json()["providers"]["openai"] == {"configured": True, "source": "server_store"}
    assert put.status == 200
    assert reread == NEW_VALUE
