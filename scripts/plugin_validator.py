#!/usr/bin/env python3
"""
Plugin Validator

Validates plugin manifests and configuration for ComfyUI-Doctor.

Usage:
  python scripts/plugin_validator.py
  python scripts/plugin_validator.py community.example
  python scripts/plugin_validator.py --check-config

Exit codes:
  0 = All valid
  1 = Validation failed
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

# Constants
PLUGIN_DIR = Path(__file__).parent.parent / 'pipeline' / 'plugins' / 'community'
CONFIG_PATH = Path(__file__).parent.parent / 'config.json'
VALID_FILENAME_PATTERN = re.compile(r'^[A-Za-z0-9_]+\.py$')


@dataclass
class ValidationResult:
    """Result of plugin validation."""
    plugin_id: str
    plugin_name: str
    passed: bool
    checks: List[tuple[str, bool, str]]  # (check_name, passed, message)


def parse_version(version_str: str) -> tuple:
    """Parse version string to tuple for comparison."""
    parts = re.split(r'[.-]', version_str)
    return tuple(int(p) for p in parts if p.isdigit())


def validate_plugin(plugin_path: Path, manifest_path: Path) -> ValidationResult:
    """Validate a single plugin and its manifest."""
    plugin_name = plugin_path.stem
    checks = []

    # Check 1: Manifest exists
    if not manifest_path.exists():
        return ValidationResult(
            plugin_id="",
            plugin_name=plugin_name,
            passed=False,
            checks=[("Manifest found", False, f"No manifest at {manifest_path}")]
        )

    checks.append(("Manifest found", True, "OK"))

    # Load manifest
    try:
        with manifest_path.open('r', encoding='utf-8') as f:
            manifest = json.load(f)
    except Exception as e:
        checks.append(("Manifest parse", False, str(e)))
        return ValidationResult("", plugin_name, False, checks)

    checks.append(("Manifest parse", True, "OK"))

    # Check 2: Required fields
    required_fields = ['id', 'name', 'version', 'author', 'min_doctor_version', 'sha256']
    missing = [f for f in required_fields if f not in manifest]

    if missing:
        checks.append(("Required fields", False, f"Missing: {', '.join(missing)}"))
    else:
        checks.append(("Required fields", True, "All present"))

    plugin_id = manifest.get('id', '')

    # Check 3: SHA256 match
    actual_sha256 = hashlib.sha256(plugin_path.read_bytes()).hexdigest()
    manifest_sha256 = manifest.get('sha256', '')

    if actual_sha256 == manifest_sha256:
        checks.append(("SHA256 match", True, "OK"))
    else:
        checks.append(("SHA256 match", False, f"Mismatch: file changed after manifest creation"))

    # Check 4: Version valid
    version = manifest.get('version', '')
    try:
        parsed_version = parse_version(version)
        checks.append(("Version valid", True, f"{version}"))
    except Exception as e:
        checks.append(("Version valid", False, str(e)))

    # Check 5: Min Doctor version compatible
    min_version = manifest.get('min_doctor_version', '')
    try:
        parsed_min = parse_version(min_version)
        # Assume current version is 1.4.0 (from ROADMAP context)
        current = (1, 4, 0)
        compatible = parsed_min <= current
        checks.append(("Min Doctor version", compatible, f"{min_version} ({'compatible' if compatible else 'incompatible'})"))
    except Exception as e:
        checks.append(("Min Doctor version", False, str(e)))

    # Check 6: Signature (optional)
    if 'signature' in manifest:
        sig = manifest['signature']
        sig_alg = manifest.get('signature_alg', 'hmac-sha256')
        checks.append(("Signature", True, f"Present ({sig_alg})"))
    else:
        checks.append(("Signature", None, "Not present (optional)"))

    # Determine overall pass/fail
    passed = all(c[1] for c in checks if c[1] is not None)

    return ValidationResult(
        plugin_id=plugin_id,
        plugin_name=plugin_name,
        passed=passed,
        checks=checks
    )


def validate_config() -> dict:
    """Validate config.json consistency."""
    if not CONFIG_PATH.exists():
        return {"exists": False, "valid": False, "message": "config.json not found"}

    try:
        with CONFIG_PATH.open('r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        return {"exists": True, "valid": False, "message": f"Parse error: {e}"}

    checks = {}

    # Check enable flag
    enabled = config.get('enable_community_plugins', False)
    checks['enable_community_plugins'] = enabled

    # Check allowlist
    allowlist = config.get('plugin_allowlist', [])
    checks['plugin_allowlist'] = f"{len(allowlist)} entry" + ("" if len(allowlist) == 1 else "ies")

    # Check signature settings
    sig_required = config.get('plugin_signature_required', False)
    checks['plugin_signature_required'] = sig_required

    return {"exists": True, "valid": True, "checks": checks}


def print_validation_result(result: ValidationResult):
    """Print validation result for a plugin."""
    icon = "✅" if result.passed else "❌"
    print(f"{icon} {result.plugin_name}:")

    for check_name, passed, message in result.checks:
        if passed is None:
            icon = "ℹ️"
        elif passed:
            icon = "✓"
        else:
            icon = "✗"

        print(f"  {icon} {check_name}: {message}")

    if not result.passed:
        print(f"  → Run: python scripts/plugin_manifest.py {PLUGIN_DIR}/{result.plugin_name}.py --write")

    print()


def main():
    parser = argparse.ArgumentParser(description="Plugin Validator")
    parser.add_argument("plugin_id", nargs='?', help="Specific plugin ID to validate")
    parser.add_argument("--check-config", action="store_true", help="Check config.json consistency")
    args = parser.parse_args()

    print("✅ Plugin Validation Report\n")

    if args.check_config:
        # Validate config
        config_result = validate_config()
        print("Config check:")

        if not config_result['exists']:
            print(f"  ✗ {config_result['message']}")
            return 1

        if not config_result['valid']:
            print(f"  ✗ {config_result['message']}")
            return 1

        for key, value in config_result['checks'].items():
            print(f"  ✓ {key}: {value}")

        print()

    # Validate plugins
    if args.plugin_id:
        # Validate specific plugin
        plugin_path = PLUGIN_DIR / f"{args.plugin_id.replace('community.', '')}.py"
        manifest_path = plugin_path.with_suffix('.json')

        if not plugin_path.exists():
            print(f"❌ Plugin not found: {plugin_path}")
            return 1

        result = validate_plugin(plugin_path, manifest_path)
        print_validation_result(result)

        return 0 if result.passed else 1

    else:
        # Validate all plugins
        if not PLUGIN_DIR.exists():
            print(f"❌ Plugin directory not found: {PLUGIN_DIR}")
            return 1

        plugins = list(PLUGIN_DIR.glob('*.py'))
        if not plugins:
            print(f"⚠️ No plugins found in {PLUGIN_DIR}")
            return 0

        results = []
        for plugin_path in plugins:
            if not VALID_FILENAME_PATTERN.match(plugin_path.name):
                continue

            manifest_path = plugin_path.with_suffix('.json')
            result = validate_plugin(plugin_path, manifest_path)
            results.append(result)
            print_validation_result(result)

        # Summary
        passed_count = sum(1 for r in results if r.passed)
        print(f"Summary: {passed_count}/{len(results)} plugin(s) passed validation")

        return 0 if passed_count == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
