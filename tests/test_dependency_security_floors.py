"""Offline regressions for dependency versions with security minimums."""

import json
import copy
from pathlib import Path
import re

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
POSTCSS_PATCHED_FLOOR = (8, 5, 18)


def _release_tuple(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    assert len(parts) == 3
    return tuple(int(part) for part in parts)


def test_postcss_override_and_lock_resolve_a_patched_release():
    package = json.loads((REPO_ROOT / "package.json").read_text("utf-8"))
    lock = json.loads((REPO_ROOT / "package-lock.json").read_text("utf-8"))

    override = package.get("overrides", {}).get("postcss")
    assert isinstance(override, str), "PostCSS security override is required"
    assert _release_tuple(override) >= POSTCSS_PATCHED_FLOOR

    postcss_entries = {
        path: entry
        for path, entry in lock.get("packages", {}).items()
        if path == "node_modules/postcss"
        or path.endswith("/node_modules/postcss")
    }
    assert set(postcss_entries) == {"node_modules/postcss"}

    locked = postcss_entries["node_modules/postcss"]
    assert locked.get("version") == override
    assert _release_tuple(locked["version"]) >= POSTCSS_PATCHED_FLOOR
    assert locked.get("resolved", "").startswith(
        "https://registry.npmjs.org/postcss/-/postcss-"
    )
    assert locked.get("integrity", "").startswith("sha512-")


def _assert_vite_security_floor(package: dict, lock: dict) -> None:
    override = package.get("overrides", {}).get("vite")
    assert isinstance(override, str), "Vite security override is required"
    release = re.fullmatch(r"6\.4\.(0|[1-9][0-9]*)", override)
    # IMPORTANT: Vite bundles launch-editor; a standalone override cannot patch it.
    # Floors differ by major branch, so do not accept an arbitrary newer major.
    assert release and int(release[1]) >= 4, "Vite needs a patched stable 6.4.x release"
    entries = {
        path: entry
        for path, entry in lock.get("packages", {}).items()
        if path == "node_modules/vite" or path.endswith("/node_modules/vite")
    }
    assert "node_modules/vite" in entries, "Canonical Vite package is required"
    for path, entry in entries.items():
        assert entry.get("version") == override, f"Vite version drift: {path}"
        assert entry.get("resolved") == (
            f"https://registry.npmjs.org/vite/-/vite-{override}.tgz"
        ), f"Untrusted Vite resolution: {path}"
        assert isinstance(entry.get("integrity"), str) and entry["integrity"].startswith(
            "sha512-"
        ), f"Missing Vite integrity: {path}"


def test_vite_override_and_every_locked_copy_resolve_a_patched_release():
    package = json.loads((REPO_ROOT / "package.json").read_text("utf-8"))
    lock = json.loads((REPO_ROOT / "package-lock.json").read_text("utf-8"))
    _assert_vite_security_floor(package, lock)


def _patched_vite_fixture():
    return {"overrides": {"vite": "6.4.4"}}, {"packages": {"node_modules/vite": {
        "version": "6.4.4",
        "resolved": "https://registry.npmjs.org/vite/-/vite-6.4.4.tgz",
        "integrity": "sha512-synthetic-fixture",
    }}}


def test_patched_vite_fixture_and_matching_nested_copy_pass():
    package, lock = _patched_vite_fixture()
    lock["packages"]["node_modules/tool/node_modules/vite"] = copy.deepcopy(
        lock["packages"]["node_modules/vite"]
    )
    _assert_vite_security_floor(package, lock)


@pytest.mark.parametrize("version", [
    None, "", "6.4.3", "6.4.bad", "6.4.04", "6.4.4-beta.1", "^6.4.4",
    "7.0.0", "8.0.0", "6.4.4 ", "6.4.-4",
])
def test_vite_rejects_missing_malformed_vulnerable_or_unreviewed_override(version):
    package, lock = _patched_vite_fixture()
    package["overrides"]["vite"] = version
    with pytest.raises(AssertionError):
        _assert_vite_security_floor(package, lock)


@pytest.mark.parametrize("mutation", [
    "missing_canonical", "nested_vulnerable", "missing_version", "malformed_version",
    "override_mismatch", "non_registry", "missing_integrity",
])
def test_vite_rejects_lock_graph_drift(mutation):
    package, lock = _patched_vite_fixture()
    entry = lock["packages"]["node_modules/vite"]
    if mutation == "missing_canonical":
        lock["packages"].clear()
    elif mutation == "nested_vulnerable":
        lock["packages"]["node_modules/tool/node_modules/vite"] = {
            **entry, "version": "6.4.3"
        }
    elif mutation == "missing_version":
        entry.pop("version")
    elif mutation == "malformed_version":
        entry["version"] = "invalid"
    elif mutation == "override_mismatch":
        entry["version"] = "6.4.5"
    elif mutation == "non_registry":
        entry["resolved"] = "file:untrusted-vite.tgz"
    else:
        entry.pop("integrity")
    with pytest.raises(AssertionError):
        _assert_vite_security_floor(package, lock)
