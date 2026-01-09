# Plugin Migration Guide

This guide helps you migrate existing plugins to the new safe-by-default plugin system introduced in Phase 2.

## Overview

Phase 2 introduces a trust-based plugin system with:

- **Safe-by-default**: Plugins are OFF by default
- **Manifest requirement**: All plugins need a `.json` manifest
- **SHA256 verification**: File integrity checking
- **Allowlist gating**: Only explicitly allowed plugins load
- **Optional HMAC signatures**: Integrity verification with shared secrets

## Quick Start

### 1. Generate Manifest

```bash
# Dry-run (preview only)
python scripts/plugin_manifest.py pipeline/plugins/community/example.py

# Write manifest file
python scripts/plugin_manifest.py pipeline/plugins/community/example.py --write
```

**What it does**:
- Computes SHA256 hash of your plugin
- Prompts for metadata (ID, name, version, author, min Doctor version)
- Creates `example.json` next to `example.py`

**Example manifest**:
```json
{
  "id": "community.example",
  "name": "Example Plugin",
  "version": "1.0.0",
  "author": "Your Name",
  "min_doctor_version": "1.3.0",
  "sha256": "014e7c1426b7316d706a0e21799e39b4ae773cb403600895dcbb05d4e295ea5e"
}
```

### 2. Generate Allowlist

```bash
# Scan plugins and suggest allowlist
python scripts/plugin_allowlist.py --report
```

**Output**:
```
Found 3 plugins:
  ✅ community.example (TRUSTED)
  ⚠️ community.custom (UNSIGNED)
  ❌ community.risky (UNTRUSTED)

Suggested config.json snippet:
{
  "enable_community_plugins": true,
  "plugin_allowlist": [
    "community.example"
  ]
}
```

### 3. Update Config

Add the suggested snippet to your `config.json`:

```json
{
  "enable_community_plugins": true,
  "plugin_allowlist": [
    "community.example",
    "community.myawesomeplugin"
  ]
}
```

### 4. Validate

```bash
# Validate all plugins
python scripts/plugin_validator.py

# Validate specific plugin
python scripts/plugin_validator.py community.example

# Check config consistency
python scripts/plugin_validator.py --check-config
```

## Trust Levels

| Level | Description | Can Load? |
|-------|-------------|-----------|
| **TRUSTED** | Allowlisted + valid manifest + SHA256 match | ✅ Yes |
| **UNSIGNED** | Missing manifest or signature (when required) | ❌ No |
| **UNTRUSTED** | Not allowlisted, hash mismatch, or policy violation | ❌ No |
| **BLOCKED** | Explicitly blocked | ❌ No |

## Manifest Fields

### Required Fields

```json
{
  "id": "community.example",           // Unique plugin ID (used in allowlist)
  "name": "Example Plugin",            // Human-readable name
  "version": "1.0.0",                  // Semantic version
  "author": "Your Name",               // Plugin author
  "min_doctor_version": "1.3.0",       // Minimum Doctor version required
  "sha256": "014e7c14..."              // SHA256 hash of .py file
}
```

### Optional Fields

```json
{
  "signature": "a3f2b1c4...",          // HMAC-SHA256 signature (if enabled)
  "signature_alg": "hmac-sha256"       // Signature algorithm
}
```

## HMAC Signatures (Optional)

For additional integrity verification, you can add HMAC signatures to manifests.

### Enable Signature Verification

In `config.json`:
```json
{
  "plugin_signature_required": true,
  "plugin_signature_key": "your-secret-key-min-32-chars",
  "plugin_signature_alg": "hmac-sha256"
}
```

**⚠️ Important**: Never commit `plugin_signature_key` to Git. Use environment variables or secure storage.

### Sign a Plugin

```bash
# Interactive mode (prompts for key)
python scripts/plugin_hmac_sign.py pipeline/plugins/community/example.py

# Environment variable mode
DOCTOR_PLUGIN_HMAC_KEY="your-secret" python scripts/plugin_hmac_sign.py example.py
```

**What it does**:
- Computes HMAC-SHA256 of plugin file
- Updates manifest with `signature` and `signature_alg` fields

## Migration Checklist

For each plugin you want to enable:

- [ ] Run `plugin_manifest.py --write` to create manifest
- [ ] Verify manifest fields are correct
- [ ] Add plugin ID to `plugin_allowlist` in `config.json`
- [ ] Run `plugin_validator.py` to verify
- [ ] (Optional) Sign with `plugin_hmac_sign.py` if using signatures
- [ ] Set `enable_community_plugins: true` in `config.json`
- [ ] Restart ComfyUI and verify plugin loads

## Troubleshooting

### Plugin not loading

**Check trust level**:
```bash
python scripts/plugin_allowlist.py --report
```

**Common issues**:
1. `enable_community_plugins: false` - Set to `true` in `config.json`
2. Plugin ID not in allowlist - Add to `plugin_allowlist`
3. SHA256 mismatch - File changed after manifest creation, regenerate with `plugin_manifest.py`
4. Missing manifest - Run `plugin_manifest.py --write`

### SHA256 keeps changing

**Cause**: File is being modified (line endings, encoding, etc.)

**Fix**:
1. Don't edit plugin after generating manifest
2. Regenerate manifest after any changes: `plugin_manifest.py --write`

### Signature verification fails

**Cause**: Key mismatch or file changed

**Fix**:
1. Verify `plugin_signature_key` is correct
2. Regenerate signature: `plugin_hmac_sign.py`

## Security Best Practices

1. **Review before allowing**: Always inspect plugin code before adding to allowlist
2. **Keep manifests in Git**: Commit `.json` manifests alongside `.py` files
3. **Never commit keys**: Don't commit `plugin_signature_key` to version control
4. **Use signatures for distribution**: Sign plugins if distributing to others
5. **Validate regularly**: Run `plugin_validator.py` periodically

## Example Workflow

```bash
# 1. Create new plugin
cat > pipeline/plugins/community/myplugin.py << 'EOF'
def register_matchers(traceback: str):
    if "MyError" in traceback:
        return ("My fix suggestion", {"priority": 80})
    return None
EOF

# 2. Generate manifest
python scripts/plugin_manifest.py pipeline/plugins/community/myplugin.py --write

# 3. Add to allowlist
# Edit config.json and add "community.myplugin" to plugin_allowlist

# 4. Validate
python scripts/plugin_validator.py community.myplugin

# 5. (Optional) Sign
DOCTOR_PLUGIN_HMAC_KEY="secret" python scripts/plugin_hmac_sign.py myplugin.py

# 6. Restart ComfyUI
```

## Resources

- **Plugin Guide**: `docs/PLUGIN_GUIDE.md`
- **Manifest Generator**: `scripts/plugin_manifest.py`
- **Allowlist Suggester**: `scripts/plugin_allowlist.py`
- **Validator**: `scripts/plugin_validator.py`
- **HMAC Signer**: `scripts/plugin_hmac_sign.py`

## Questions?

If you encounter issues migrating plugins, please file an issue on GitHub.
