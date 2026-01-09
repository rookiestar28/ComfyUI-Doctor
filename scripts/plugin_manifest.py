#!/usr/bin/env python3
"""
Plugin Manifest Generator

Generates manifest JSON files with computed SHA256 hashes for ComfyUI-Doctor plugins.

Usage:
  python scripts/plugin_manifest.py pipeline/plugins/community/example.py
  python scripts/plugin_manifest.py pipeline/plugins/community/example.py --write
  python scripts/plugin_manifest.py pipeline/plugins/community/*.py --write

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

# Valid plugin filename pattern
VALID_FILENAME_PATTERN = re.compile(r'^[A-Za-z0-9_]+\.py$')

# Max file size (256 KiB by default)
MAX_FILE_SIZE = 262144


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def validate_plugin_file(file_path: Path) -> tuple[bool, str]:
    """Validate plugin file meets requirements."""
    # Check exists
    if not file_path.exists():
        return False, "File does not exist"

    # Check is file
    if not file_path.is_file():
        return False, "Not a regular file"

    # Check filename pattern
    if not VALID_FILENAME_PATTERN.match(file_path.name):
        return False, f"Filename must match pattern: {VALID_FILENAME_PATTERN.pattern}"

    # Check file size
    size = file_path.stat().st_size
    if size > MAX_FILE_SIZE:
        return False, f"File too large: {size} bytes (max: {MAX_FILE_SIZE})"

    return True, "OK"


def get_manifest_path(plugin_path: Path) -> Path:
    """Get manifest path for plugin file."""
    return plugin_path.with_suffix('.json')


def prompt_manifest_fields(plugin_path: Path) -> dict:
    """Prompt user for manifest fields."""
    plugin_name = plugin_path.stem

    # Suggest defaults
    default_id = f"community.{plugin_name}"
    default_name = plugin_name.replace('_', ' ').title()
    default_version = "1.0.0"
    default_author = "Community"
    default_min_version = "1.3.0"

    print("\nEnter plugin details (press Enter to use defaults):")

    plugin_id = input(f"  ID [{default_id}]: ").strip() or default_id
    name = input(f"  Name [{default_name}]: ").strip() or default_name
    version = input(f"  Version [{default_version}]: ").strip() or default_version
    author = input(f"  Author [{default_author}]: ").strip() or default_author
    min_doctor_version = input(f"  Min Doctor Version [{default_min_version}]: ").strip() or default_min_version

    return {
        "id": plugin_id,
        "name": name,
        "version": version,
        "author": author,
        "min_doctor_version": min_doctor_version
    }


def generate_manifest(plugin_path: Path, sha256: str, fields: dict) -> dict:
    """Generate complete manifest."""
    manifest = {
        "id": fields["id"],
        "name": fields["name"],
        "version": fields["version"],
        "author": fields["author"],
        "min_doctor_version": fields["min_doctor_version"],
        "sha256": sha256
    }
    return manifest


def write_manifest(manifest_path: Path, manifest: dict):
    """Write manifest to file."""
    with manifest_path.open('w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write('\n')  # Trailing newline


def process_plugin(plugin_path: Path, write_mode: bool) -> bool:
    """Process a single plugin file."""
    print(f"\n🔧 Plugin Manifest Generator\n")
    print(f"Analyzing: {plugin_path}")

    # Validate
    valid, message = validate_plugin_file(plugin_path)
    if not valid:
        print(f"  ❌ Validation failed: {message}")
        return False

    # Compute hash
    sha256 = compute_sha256(plugin_path)
    size_kb = plugin_path.stat().st_size / 1024
    print(f"  SHA256: {sha256}")
    print(f"  Size: {size_kb:.1f} KiB (within limit)")

    # Get manifest fields
    fields = prompt_manifest_fields(plugin_path)

    # Generate manifest
    manifest = generate_manifest(plugin_path, sha256, fields)

    print("\nGenerated manifest:")
    print(json.dumps(manifest, indent=2))

    # Write or dry-run
    manifest_path = get_manifest_path(plugin_path)

    if write_mode:
        write_manifest(manifest_path, manifest)
        print(f"\n✅ Manifest written to: {manifest_path}")
    else:
        print(f"\n[--dry-run] Would write to: {manifest_path}")
        print("To write, run with --write flag")

    return True


def main():
    parser = argparse.ArgumentParser(description="Plugin Manifest Generator")
    parser.add_argument("plugins", nargs='+', type=Path, help="Plugin file(s) to process")
    parser.add_argument("--write", action="store_true", help="Write manifest files (default is dry-run)")
    args = parser.parse_args()

    if not args.write:
        print("🔍 Running in DRY-RUN mode (no files will be written)")
        print("Use --write to actually create manifest files\n")

    success_count = 0
    for plugin_path in args.plugins:
        try:
            if process_plugin(plugin_path, args.write):
                success_count += 1
        except Exception as e:
            print(f"❌ Error processing {plugin_path}: {e}")

    print(f"\n{'='*60}")
    print(f"Processed: {success_count}/{len(args.plugins)} plugins")

    if success_count == len(args.plugins):
        print("✅ All plugins processed successfully")
        return 0
    else:
        print("⚠️ Some plugins failed to process")
        return 1


if __name__ == '__main__':
    sys.exit(main())
