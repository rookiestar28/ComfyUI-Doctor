"""Offline regressions for dependency versions with security minimums."""

import json
from pathlib import Path


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
