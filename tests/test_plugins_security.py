import hashlib
import hmac
import json
import os
from pathlib import Path

import pytest

from config import CONFIG
from pipeline.plugins import discover_plugins, scan_plugins, TRUST_BLOCKED, TRUST_TRUSTED, TRUST_UNTRUSTED, TRUST_UNSIGNED


def _write_plugin(tmp_path: Path, plugin_id: str, content: str, signature: str = "") -> Path:
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    py_file = plugin_dir / "example_plugin.py"
    py_file.write_text(content, encoding="utf-8")

    digest = hashlib.sha256(py_file.read_bytes()).hexdigest()
    manifest = {
        "id": plugin_id,
        "name": "Test Plugin",
        "version": "1.0.0",
        "author": "tests",
        "min_doctor_version": "0.0.0",
        "sha256": digest,
    }
    if signature:
        manifest["signature"] = signature
        manifest["signature_alg"] = "hmac-sha256"
    (plugin_dir / "example_plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    return plugin_dir


def _sign_plugin(py_file: Path, key: str) -> str:
    return hmac.new(key.encode("utf-8"), py_file.read_bytes(), hashlib.sha256).hexdigest()


def test_plugins_disabled_returns_empty(tmp_path: Path):
    plugin_dir = _write_plugin(
        tmp_path,
        "community.test",
        "def register_matchers(traceback):\n    return None\n",
    )

    original_enabled = CONFIG.enable_community_plugins
    original_allowlist = list(CONFIG.plugin_allowlist)
    try:
        CONFIG.enable_community_plugins = False
        CONFIG.plugin_allowlist = ["community.test"]
        assert discover_plugins(plugin_dir) == []
    finally:
        CONFIG.enable_community_plugins = original_enabled
        CONFIG.plugin_allowlist = original_allowlist


def test_allowlisted_plugin_loads_and_is_trusted(tmp_path: Path):
    plugin_dir = _write_plugin(
        tmp_path,
        "community.test",
        "def register_matchers(traceback):\n    return ('ok', {'matched_pattern_id': 'x'})\n",
    )

    original_enabled = CONFIG.enable_community_plugins
    original_allowlist = list(CONFIG.plugin_allowlist)
    try:
        CONFIG.enable_community_plugins = True
        CONFIG.plugin_allowlist = ["community.test"]
        plugins = discover_plugins(plugin_dir)
        assert len(plugins) == 1
        assert getattr(plugins[0], "__plugin_trust__", None) == "trusted"
    finally:
        CONFIG.enable_community_plugins = original_enabled
        CONFIG.plugin_allowlist = original_allowlist


def test_oversized_plugin_is_rejected(tmp_path: Path):
    plugin_dir = _write_plugin(
        tmp_path,
        "community.test",
        "x = 'a' * 100\n\ndef register_matchers(traceback):\n    return None\n",
    )

    big_file = next(plugin_dir.glob("*.py"))
    big_file.write_bytes(b"a" * 2000)

    manifest_path = big_file.with_suffix(".json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sha256"] = hashlib.sha256(big_file.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    original_enabled = CONFIG.enable_community_plugins
    original_allowlist = list(CONFIG.plugin_allowlist)
    original_max_size = CONFIG.plugin_max_file_size_bytes
    try:
        CONFIG.enable_community_plugins = True
        CONFIG.plugin_allowlist = ["community.test"]
        CONFIG.plugin_max_file_size_bytes = 1024
        assert discover_plugins(plugin_dir) == []
    finally:
        CONFIG.enable_community_plugins = original_enabled
        CONFIG.plugin_allowlist = original_allowlist
        CONFIG.plugin_max_file_size_bytes = original_max_size


def test_symlink_escape_is_rejected(tmp_path: Path):
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "evil.py"
    outside_file.write_text("def register_matchers(traceback):\n    return None\n", encoding="utf-8")

    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    symlink_file = plugin_dir / "evil.py"

    try:
        symlink_file.symlink_to(outside_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported in this environment")

    digest = hashlib.sha256(outside_file.read_bytes()).hexdigest()
    manifest = {
        "id": "community.evil",
        "name": "Evil Plugin",
        "version": "1.0.0",
        "author": "tests",
        "min_doctor_version": "0.0.0",
        "sha256": digest,
    }
    symlink_file.with_suffix(".json").write_text(json.dumps(manifest), encoding="utf-8")

    original_enabled = CONFIG.enable_community_plugins
    original_allowlist = list(CONFIG.plugin_allowlist)
    try:
        CONFIG.enable_community_plugins = True
        CONFIG.plugin_allowlist = ["community.evil"]
        assert discover_plugins(plugin_dir) == []
    finally:
        CONFIG.enable_community_plugins = original_enabled
        CONFIG.plugin_allowlist = original_allowlist


def test_scan_plugins_reports_unsigned_without_manifest(tmp_path: Path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "example_plugin.py").write_text(
        "def register_matchers(traceback):\n    return None\n", encoding="utf-8"
    )

    original_allowlist = list(CONFIG.plugin_allowlist)
    original_blocklist = list(CONFIG.plugin_blocklist)
    try:
        CONFIG.plugin_allowlist = ["community.test"]
        CONFIG.plugin_blocklist = []
        report = scan_plugins(plugin_dir)
        assert len(report) == 1
        assert report[0]["trust"] == TRUST_UNSIGNED
    finally:
        CONFIG.plugin_allowlist = original_allowlist
        CONFIG.plugin_blocklist = original_blocklist


def test_scan_plugins_reports_untrusted_when_not_allowlisted(tmp_path: Path):
    plugin_dir = _write_plugin(
        tmp_path,
        "community.test",
        "def register_matchers(traceback):\n    return None\n",
    )

    original_allowlist = list(CONFIG.plugin_allowlist)
    original_blocklist = list(CONFIG.plugin_blocklist)
    try:
        CONFIG.plugin_allowlist = []
        CONFIG.plugin_blocklist = []
        report = scan_plugins(plugin_dir)
        assert len(report) == 1
        assert report[0]["trust"] == TRUST_UNTRUSTED
    finally:
        CONFIG.plugin_allowlist = original_allowlist
        CONFIG.plugin_blocklist = original_blocklist


def test_scan_plugins_reports_blocked_when_blocklisted(tmp_path: Path):
    plugin_dir = _write_plugin(
        tmp_path,
        "community.bad",
        "def register_matchers(traceback):\n    return None\n",
    )

    original_allowlist = list(CONFIG.plugin_allowlist)
    original_blocklist = list(CONFIG.plugin_blocklist)
    try:
        CONFIG.plugin_allowlist = ["community.bad"]
        CONFIG.plugin_blocklist = ["community.bad"]
        report = scan_plugins(plugin_dir)
        assert len(report) == 1
        assert report[0]["trust"] == TRUST_BLOCKED
    finally:
        CONFIG.plugin_allowlist = original_allowlist
        CONFIG.plugin_blocklist = original_blocklist


def test_signature_required_missing_is_unsigned(tmp_path: Path):
    plugin_dir = _write_plugin(
        tmp_path,
        "community.sig",
        "def register_matchers(traceback):\n    return None\n",
    )

    original_allowlist = list(CONFIG.plugin_allowlist)
    original_required = CONFIG.plugin_signature_required
    original_key = CONFIG.plugin_signature_key
    try:
        CONFIG.plugin_allowlist = ["community.sig"]
        CONFIG.plugin_signature_required = True
        CONFIG.plugin_signature_key = "secret"
        report = scan_plugins(plugin_dir)
        assert report[0]["trust"] == TRUST_UNSIGNED
        assert report[0]["reason"] == "signature_missing"
    finally:
        CONFIG.plugin_allowlist = original_allowlist
        CONFIG.plugin_signature_required = original_required
        CONFIG.plugin_signature_key = original_key


def test_signature_required_invalid_is_untrusted(tmp_path: Path):
    plugin_dir = _write_plugin(
        tmp_path,
        "community.sig",
        "def register_matchers(traceback):\n    return None\n",
        signature="bad-signature",
    )

    original_allowlist = list(CONFIG.plugin_allowlist)
    original_required = CONFIG.plugin_signature_required
    original_key = CONFIG.plugin_signature_key
    try:
        CONFIG.plugin_allowlist = ["community.sig"]
        CONFIG.plugin_signature_required = True
        CONFIG.plugin_signature_key = "secret"
        report = scan_plugins(plugin_dir)
        assert report[0]["trust"] == TRUST_UNTRUSTED
        assert report[0]["reason"] == "signature_invalid"
    finally:
        CONFIG.plugin_allowlist = original_allowlist
        CONFIG.plugin_signature_required = original_required
        CONFIG.plugin_signature_key = original_key


def test_signature_required_valid_is_trusted(tmp_path: Path):
    plugin_dir = _write_plugin(
        tmp_path,
        "community.sig",
        "def register_matchers(traceback):\n    return None\n",
    )
    py_file = plugin_dir / "example_plugin.py"

    signature = _sign_plugin(py_file, "secret")
    manifest_path = plugin_dir / "example_plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["signature"] = signature
    manifest["signature_alg"] = "hmac-sha256"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    original_allowlist = list(CONFIG.plugin_allowlist)
    original_required = CONFIG.plugin_signature_required
    original_key = CONFIG.plugin_signature_key
    try:
        CONFIG.plugin_allowlist = ["community.sig"]
        CONFIG.plugin_signature_required = True
        CONFIG.plugin_signature_key = "secret"
        report = scan_plugins(plugin_dir)
        assert report[0]["trust"] == TRUST_TRUSTED
    finally:
        CONFIG.plugin_allowlist = original_allowlist
        CONFIG.plugin_signature_required = original_required
        CONFIG.plugin_signature_key = original_key
