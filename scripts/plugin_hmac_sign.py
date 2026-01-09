#!/usr/bin/env python3
"""
Plugin HMAC Signer

Generates HMAC-SHA256 signatures for plugins and updates manifests.

Usage:
  python scripts/plugin_hmac_sign.py pipeline/plugins/community/example.py
  DOCTOR_PLUGIN_HMAC_KEY="secret" python scripts/plugin_hmac_sign.py example.py

Exit codes:
  0 = Success
  1 = Error
"""

import argparse
import getpass
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

# Minimum key length (32 chars = 256 bits)
MIN_KEY_LENGTH = 32


def get_hmac_key() -> str:
    """Get HMAC key from environment or prompt."""
    # Try environment variable first
    key = os.environ.get('DOCTOR_PLUGIN_HMAC_KEY', '')

    if key:
        print("Reading key from environment: DOCTOR_PLUGIN_HMAC_KEY")
    else:
        print("DOCTOR_PLUGIN_HMAC_KEY not set in environment")
        key = getpass.getpass("Enter HMAC key (will not echo): ")

    return key


def validate_key(key: str) -> tuple[bool, str]:
    """Validate HMAC key strength."""
    if len(key) < MIN_KEY_LENGTH:
        return False, f"Key too short: {len(key)} chars (min: {MIN_KEY_LENGTH})"

    return True, "OK"


def compute_hmac(file_path: Path, key: str) -> str:
    """Compute HMAC-SHA256 of file."""
    file_bytes = file_path.read_bytes()
    signature = hmac.new(key.encode('utf-8'), file_bytes, hashlib.sha256).hexdigest()
    return signature


def update_manifest(manifest_path: Path, signature: str, algorithm: str = "hmac-sha256"):
    """Update manifest with signature fields."""
    # Load existing manifest
    with manifest_path.open('r', encoding='utf-8') as f:
        manifest = json.load(f)

    # Add signature fields
    manifest['signature'] = signature
    manifest['signature_alg'] = algorithm

    # Write back
    with manifest_path.open('w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write('\n')


def process_plugin(plugin_path: Path, key: str) -> bool:
    """Process a single plugin file."""
    print(f"\n🔐 Plugin HMAC Signer\n")

    # Validate key
    valid, message = validate_key(key)
    if not valid:
        print(f"❌ {message}")
        return False

    print(f"Key length: {len(key)} chars ✓\n")

    # Check plugin exists
    if not plugin_path.exists():
        print(f"❌ Plugin not found: {plugin_path}")
        return False

    # Check manifest exists
    manifest_path = plugin_path.with_suffix('.json')
    if not manifest_path.exists():
        print(f"❌ Manifest not found: {manifest_path}")
        print("Run plugin_manifest.py first to create manifest")
        return False

    print(f"Processing: {plugin_path}")

    # Compute SHA256 (for verification)
    sha256 = hashlib.sha256(plugin_path.read_bytes()).hexdigest()
    print(f"  SHA256: {sha256}")

    # Compute HMAC
    signature = compute_hmac(plugin_path, key)
    print(f"  HMAC-SHA256: {signature}\n")

    # Update manifest
    print(f"Updating manifest: {manifest_path}")
    update_manifest(manifest_path, signature)
    print(f"  Added: signature")
    print(f"  Added: signature_alg\n")

    print("✅ Manifest updated successfully")

    return True


def main():
    parser = argparse.ArgumentParser(description="Plugin HMAC Signer")
    parser.add_argument("plugin", type=Path, help="Plugin file to sign")
    args = parser.parse_args()

    # Get HMAC key
    key = get_hmac_key()

    if not key:
        print("❌ No HMAC key provided")
        print("\nSet DOCTOR_PLUGIN_HMAC_KEY environment variable or enter interactively")
        return 1

    # Process plugin
    try:
        success = process_plugin(args.plugin, key)
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        # Clear key from memory
        key = None


if __name__ == '__main__':
    sys.exit(main())
