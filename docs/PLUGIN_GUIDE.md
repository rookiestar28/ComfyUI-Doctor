# ComfyUI-Doctor Plugin Guide

ComfyUI-Doctor supports community plugins to extend error analysis capabilities beyond regex patterns. Plugins are Python scripts that can implement complex logic (e.g., checking file headers, parsing specific log formats).

## Important: Safe-by-Default Loading

Plugins are **disabled by default** and will only be imported when all of the following are true:

1. `config.json` sets `"enable_community_plugins": true`
2. The plugin `id` is present in `"plugin_allowlist"`
3. The plugin has a valid manifest with a matching `sha256`
4. The plugin passes filesystem hardening checks (containment, symlink policy, size/scan limits)
5. (Optional) If `plugin_signature_required=true`, the manifest includes a valid HMAC signature

## How to Create a Plugin

1. Create a Python file in `pipeline/plugins/community/` (e.g., `my_check.py`).
2. Define a function `register_matchers(traceback: str)`.
3. Implement your logic.
4. Return `(suggestion, metadata)` tuple on match, or `None`.

### Example

```python
from typing import Optional, Tuple, Dict, Any

def register_matchers(traceback: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    if "My Specific Error" in traceback:
        return (
            "Try adjusting the X parameter.",
            {
                "matched_pattern_id": "MY_SPECIFIC_ERROR",
                "category": "custom",
                "priority": 90
            }
        )
    return None
```

## Manifest (Required)

Next to each plugin file, create a manifest JSON:

- `my_check.py` → `my_check.json`

Fields:

```json
{
  "id": "example.plugin",
  "name": "Example Plugin",
  "version": "1.0.0",
  "author": "you",
  "min_doctor_version": "1.3.0",
  "sha256": "<sha256 of the .py file>",
  "signature": "<optional hmac-sha256 of the .py file>",
  "signature_alg": "hmac-sha256"
}
```

If there is only one plugin file in the directory, `plugin.json` is also accepted as a fallback manifest name.

## Optional: HMAC Signature Policy

If you set `plugin_signature_required=true`, ComfyUI-Doctor will require `signature` in the manifest and verify it using `plugin_signature_key`.

Security note:

- HMAC is **shared-secret integrity verification**, not a public signing scheme.
- It helps detect accidental tampering or untrusted changes when the key is kept secret.
- It does not protect against a malicious publisher who has (or can guess/leak) the shared key.

## Security Warning

> [!WARNING]
> Plugins are executed as arbitrary Python code.
> Only install plugins from trusted sources.
> Malicious plugins can access your file system and network.

## Testing

You can test your plugin by triggering the error in ComfyUI or adding a unit test in `tests/`.

---

## Migration Tooling

ComfyUI-Doctor provides automated tools to simplify plugin management:

### Generate Manifest

```bash
# Create manifest with SHA256 hash
python scripts/plugin_manifest.py pipeline/plugins/community/myplugin.py --write
```

**What it does**:
- Computes SHA256 hash automatically
- Prompts for metadata (ID, name, version, etc.)
- Creates `myplugin.json` next to your plugin

### Generate Allowlist

```bash
# Scan all plugins and suggest allowlist
python scripts/plugin_allowlist.py --report
```

**What it does**:
- Scans `pipeline/plugins/community/` directory
- Classifies plugins by trust level (TRUSTED/UNSIGNED/UNTRUSTED)
- Generates `config.json` snippet with allowlist

### Validate Plugins

```bash
# Validate all plugins
python scripts/plugin_validator.py

# Validate specific plugin
python scripts/plugin_validator.py community.example

# Check config consistency
python scripts/plugin_validator.py --check-config
```

**What it checks**:
- Manifest exists and parses correctly
- All required fields present
- SHA256 matches actual file
- Version compatibility
- (Optional) HMAC signature validity

### Sign Plugins (Optional)

```bash
# Add HMAC signature to manifest
DOCTOR_PLUGIN_HMAC_KEY="your-secret" python scripts/plugin_hmac_sign.py myplugin.py
```

**What it does**:
- Computes HMAC-SHA256 of plugin file
- Updates manifest with `signature` field

---

## Complete Workflow

```bash
# 1. Create your plugin
cat > pipeline/plugins/community/myplugin.py << 'EOF'
def register_matchers(traceback: str):
    if "MyError" in traceback:
        return ("My fix suggestion", {"priority": 80})
    return None
EOF

# 2. Generate manifest
python scripts/plugin_manifest.py pipeline/plugins/community/myplugin.py --write

# 3. Generate allowlist
python scripts/plugin_allowlist.py --report

# 4. Update config.json (add plugin ID to allowlist)
# Set enable_community_plugins: true

# 5. Validate
python scripts/plugin_validator.py community.myplugin

# 6. (Optional) Sign
DOCTOR_PLUGIN_HMAC_KEY="secret" python scripts/plugin_hmac_sign.py myplugin.py

# 7. Restart ComfyUI
```

---

## Resources

- **Migration Guide**: `docs/PLUGIN_MIGRATION.md` - Step-by-step migration instructions
- **Manifest Generator**: `scripts/plugin_manifest.py` - Automate manifest creation
- **Allowlist Suggester**: `scripts/plugin_allowlist.py` - Scan and suggest allowlist
- **Validator**: `scripts/plugin_validator.py` - Verify plugin integrity
- **HMAC Signer**: `scripts/plugin_hmac_sign.py` - Add signatures to manifests
