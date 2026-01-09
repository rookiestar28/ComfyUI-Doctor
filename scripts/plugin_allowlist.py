#!/usr/bin/env python3
"""
Plugin Allowlist Suggester

Scans plugins and generates allowlist config snippet for ComfyUI-Doctor.

Usage:
  python scripts/plugin_allowlist.py
  python scripts/plugin_allowlist.py --report

Exit codes:
  0 = Success
  1 = Error
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List

# Constants
PLUGIN_DIR_DEFAULT = Path(__file__).parent.parent / 'pipeline' / 'plugins' / 'community'
VALID_FILENAME_PATTERN = re.compile(r'^[A-Za-z0-9_]+\.py$')
MAX_FILE_SIZE = 262144  # 256 KiB


@dataclass
class PluginInfo:
    """Information about a discovered plugin."""
    path: Path
    name: str
    manifest_path: Path
    trust_level: str
    trust_reason: str
    plugin_id: str = ""
    sha256_file: str = ""
    sha256_manifest: str = ""
    size_bytes: int = 0


def scan_plugins(plugin_dir: Path) -> List[PluginInfo]:
    """Scan directory for plugin files."""
    plugins = []

    for py_file in plugin_dir.glob('*.py'):
        if not VALID_FILENAME_PATTERN.match(py_file.name):
            continue

        # Primary manifest: {plugin_name}.json
        manifest_path = py_file.with_suffix('.json')

        # Fallback: plugin.json (only if single plugin in directory)
        if not manifest_path.exists():
            fallback = plugin_dir / 'plugin.json'
            py_count = len(list(plugin_dir.glob('*.py')))
            if fallback.exists() and py_count == 1:
                manifest_path = fallback

        plugin = PluginInfo(
            path=py_file,
            name=py_file.stem,
            manifest_path=manifest_path,
            trust_level="UNKNOWN",
            trust_reason="",
            size_bytes=py_file.stat().st_size
        )

        plugins.append(plugin)

    return plugins


def classify_plugin_trust(plugin: PluginInfo) -> PluginInfo:
    """Classify plugin trust level."""
    # Check symlink
    if plugin.path.is_symlink():
        plugin.trust_level = "UNTRUSTED"
        plugin.trust_reason = "Symlink detected"
        return plugin

    # Check file size
    if plugin.size_bytes > MAX_FILE_SIZE:
        plugin.trust_level = "UNTRUSTED"
        plugin.trust_reason = f"File too large: {plugin.size_bytes} bytes (max: {MAX_FILE_SIZE})"
        return plugin

    # Check manifest exists
    if not plugin.manifest_path.exists():
        plugin.trust_level = "UNSIGNED"
        plugin.trust_reason = "No manifest file found"
        return plugin

    # Load manifest
    try:
        with plugin.manifest_path.open('r', encoding='utf-8') as f:
            manifest = json.load(f)
    except Exception as e:
        plugin.trust_level = "UNTRUSTED"
        plugin.trust_reason = f"Manifest parse error: {e}"
        return plugin

    # Check required fields
    required_fields = ['id', 'name', 'version', 'author', 'min_doctor_version', 'sha256']
    missing = [f for f in required_fields if f not in manifest]
    if missing:
        plugin.trust_level = "UNTRUSTED"
        plugin.trust_reason = f"Manifest missing fields: {', '.join(missing)}"
        return plugin

    plugin.plugin_id = manifest['id']
    plugin.sha256_manifest = manifest['sha256']

    # Compute actual SHA256
    plugin.sha256_file = hashlib.sha256(plugin.path.read_bytes()).hexdigest()

    # Check SHA256 match
    if plugin.sha256_file != plugin.sha256_manifest:
        plugin.trust_level = "UNTRUSTED"
        plugin.trust_reason = "SHA256 mismatch - file modified after manifest creation"
        return plugin

    # All checks passed
    plugin.trust_level = "TRUSTED"
    plugin.trust_reason = "All checks passed"
    return plugin


def generate_allowlist_config(plugins: List[PluginInfo]) -> dict:
    """Generate config.json snippet with allowlist."""
    trusted_ids = [p.plugin_id for p in plugins if p.trust_level == "TRUSTED"]

    config = {
        "enable_community_plugins": True,
        "plugin_allowlist": trusted_ids
    }

    return config


def print_report(plugins: List[PluginInfo]):
    """Print human-readable trust report."""
    print("\n🔍 Plugin Allowlist Suggester\n")
    print(f"Scanning: {PLUGIN_DIR_DEFAULT}\n")
    print(f"Found {len(plugins)} plugin(s):\n")

    for plugin in plugins:
        # Icon based on trust level
        if plugin.trust_level == "TRUSTED":
            icon = "✅"
        elif plugin.trust_level == "UNSIGNED":
            icon = "⚠️"
        else:
            icon = "❌"

        print(f"  {icon} {plugin.name} ({plugin.trust_level})")

        if plugin.manifest_path.exists():
            print(f"     - Manifest: ✓ Valid" if plugin.trust_level == "TRUSTED" else f"     - Manifest: ✗ Invalid")
        else:
            print(f"     - Manifest: ✗ Missing")

        if plugin.sha256_file and plugin.sha256_manifest:
            match = "✓" if plugin.sha256_file == plugin.sha256_manifest else "✗"
            print(f"     - SHA256: {match} {'Match' if match == '✓' else 'Mismatch'}")

        print(f"     - Size: {plugin.size_bytes / 1024:.1f} KiB")
        print(f"     - Symlink: {'Yes' if plugin.path.is_symlink() else 'No'}")

        if plugin.trust_reason:
            print(f"     - Reason: {plugin.trust_reason}")

        print()


def print_recommendations(plugins: List[PluginInfo]):
    """Print recommendations for untrusted plugins."""
    unsigned = [p for p in plugins if p.trust_level == "UNSIGNED"]
    untrusted = [p for p in plugins if p.trust_level == "UNTRUSTED"]

    if unsigned or untrusted:
        print("⚠️ Review recommendations:")

        for plugin in unsigned:
            print(f"  - {plugin.name}: Create manifest with plugin_manifest.py")

        for plugin in untrusted:
            print(f"  - {plugin.name}: {plugin.trust_reason} - verify integrity before allowing")

        print()


def main():
    parser = argparse.ArgumentParser(description="Plugin Allowlist Suggester")
    parser.add_argument("--report", action="store_true", help="Include detailed trust report")
    args = parser.parse_args()

    plugin_dir = PLUGIN_DIR_DEFAULT

    if not plugin_dir.exists():
        print(f"❌ Plugin directory not found: {plugin_dir}")
        return 1

    # Scan plugins
    plugins = scan_plugins(plugin_dir)

    if not plugins:
        print(f"⚠️ No plugins found in {plugin_dir}")
        return 0

    # Classify trust
    plugins = [classify_plugin_trust(p) for p in plugins]

    # Print report if requested
    if args.report:
        print_report(plugins)

    # Generate config
    config = generate_allowlist_config(plugins)

    print("Suggested config.json snippet:")
    print(json.dumps(config, indent=2))
    print()

    # Print recommendations
    print_recommendations(plugins)

    trusted_count = sum(1 for p in plugins if p.trust_level == "TRUSTED")
    print(f"Summary: {trusted_count}/{len(plugins)} plugins are TRUSTED and allowlisted")

    return 0


if __name__ == '__main__':
    sys.exit(main())
