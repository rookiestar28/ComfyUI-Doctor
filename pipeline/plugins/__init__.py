import importlib
import importlib.util
import json
import logging
import re
import hashlib
import hmac
import os
from pathlib import Path
from typing import List, Callable, Any, Dict, Optional

try:
    from config import CONFIG
except ImportError:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from config import CONFIG

logger = logging.getLogger(__name__)

TRUST_TRUSTED = "trusted"
TRUST_UNSIGNED = "unsigned"
TRUST_UNTRUSTED = "untrusted"
TRUST_BLOCKED = "blocked"

_last_allowlist_snapshot: Optional[set] = None

def _parse_version(value: str) -> Optional[tuple]:
    if not isinstance(value, str):
        return None
    parts = []
    for token in re.split(r"[.-]", value.strip()):
        if token.isdigit():
            parts.append(int(token))
        else:
            break
    if not parts:
        return None
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _get_doctor_version() -> str:
    root_dir = Path(__file__).resolve().parents[2]
    package_json = root_dir / "package.json"
    if not package_json.exists():
        return "0.0.0"
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
        return data.get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def _read_manifest(py_file: Path, plugin_dir: Path, plugin_count: int) -> Optional[Dict[str, Any]]:
    manifest_candidates = [py_file.with_suffix(".json")]
    fallback_manifest = plugin_dir / "plugin.json"
    if fallback_manifest.exists() and plugin_count == 1:
        manifest_candidates.append(fallback_manifest)

    for candidate in manifest_candidates:
        if candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to parse manifest {candidate.name}: {e}")
                return None
    return None


def _manifest_valid(manifest: Dict[str, Any], py_file: Path) -> bool:
    required = ["id", "name", "version", "author", "min_doctor_version", "sha256"]
    for key in required:
        if not manifest.get(key):
            logger.warning(f"Manifest missing required field '{key}' for {py_file.name}")
            return False

    digest = hashlib.sha256(py_file.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        logger.warning(f"Manifest sha256 mismatch for {py_file.name}")
        return False

    current_version = _parse_version(_get_doctor_version())
    min_version = _parse_version(manifest["min_doctor_version"])
    if not current_version or not min_version:
        logger.warning(f"Unable to parse version for {py_file.name}")
        return False
    if current_version < min_version:
        logger.warning(f"Plugin {manifest['id']} requires Doctor >= {manifest['min_doctor_version']}")
        return False

    return True


def _compute_signature(py_file: Path, key: str) -> str:
    return hmac.new(key.encode("utf-8"), py_file.read_bytes(), hashlib.sha256).hexdigest()


def _is_path_within(child: Path, parent: Path) -> bool:
    try:
        child_resolved = child.resolve()
        parent_resolved = parent.resolve()
        return os.path.commonpath([str(child_resolved), str(parent_resolved)]) == str(parent_resolved)
    except Exception:
        return False


def _snapshot_allowlist_changes(allowlist: set) -> None:
    global _last_allowlist_snapshot
    if _last_allowlist_snapshot is None:
        _last_allowlist_snapshot = set(allowlist)
        return

    added = sorted(allowlist - _last_allowlist_snapshot)
    removed = sorted(_last_allowlist_snapshot - allowlist)
    if added or removed:
        logger.info(f"plugin_allowlist changed: +{added} -{removed}")
        _last_allowlist_snapshot = set(allowlist)


def scan_plugins(plugin_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan plugin directory and classify each plugin candidate without importing code.

    Returns a list of dictionaries:
      {file, plugin_id, trust, reason, manifest}
    """
    results: List[Dict[str, Any]] = []
    if not plugin_dir.exists():
        return results

    plugin_dir_resolved = plugin_dir.resolve()
    py_files = [f for f in plugin_dir.glob("*.py") if not f.name.startswith("_")]
    py_files = sorted(py_files, key=lambda p: p.name)

    max_scan = int(getattr(CONFIG, "plugin_max_scan_files", 50) or 50)
    if len(py_files) > max_scan:
        logger.warning(f"Plugin scan limit reached ({max_scan}); extra plugin files will be ignored")
        py_files = py_files[:max_scan]

    allowlist = set(getattr(CONFIG, "plugin_allowlist", []) or [])
    blocklist = set(getattr(CONFIG, "plugin_blocklist", []) or [])
    _snapshot_allowlist_changes(allowlist)

    signature_required = bool(getattr(CONFIG, "plugin_signature_required", False))
    signature_key = getattr(CONFIG, "plugin_signature_key", "") or ""
    signature_alg = (getattr(CONFIG, "plugin_signature_alg", "") or "hmac-sha256").lower()

    max_size = int(getattr(CONFIG, "plugin_max_file_size_bytes", 262144) or 262144)
    reject_symlinks = bool(getattr(CONFIG, "plugin_reject_symlinks", True))

    for py_file in py_files:
        trust = TRUST_UNTRUSTED
        reason = "unknown"
        manifest: Optional[Dict[str, Any]] = None
        plugin_id: Optional[str] = None

        if reject_symlinks and py_file.is_symlink():
            trust, reason = TRUST_UNTRUSTED, "symlink_not_allowed"
        elif not _is_path_within(py_file, plugin_dir_resolved):
            trust, reason = TRUST_UNTRUSTED, "path_escapes_plugin_dir"
        elif not re.fullmatch(r"[A-Za-z0-9_]+\.py", py_file.name):
            trust, reason = TRUST_UNTRUSTED, "invalid_filename"
        else:
            try:
                if py_file.stat().st_size > max_size:
                    trust, reason = TRUST_UNTRUSTED, "exceeds_max_size"
                else:
                    manifest = _read_manifest(py_file, plugin_dir, len(py_files))
                    if not manifest:
                        trust, reason = TRUST_UNSIGNED, "manifest_missing_or_invalid"
                    else:
                        plugin_id = manifest.get("id")
                        if not plugin_id:
                            trust, reason = TRUST_UNSIGNED, "manifest_missing_id"
                        elif plugin_id in blocklist:
                            trust, reason = TRUST_BLOCKED, "blocked_by_policy"
                        elif plugin_id not in allowlist:
                            trust, reason = TRUST_UNTRUSTED, "not_allowlisted"
                        elif not _manifest_valid(manifest, py_file):
                            trust, reason = TRUST_UNTRUSTED, "manifest_invalid"
                        else:
                            if signature_required:
                                if not signature_key:
                                    trust, reason = TRUST_UNTRUSTED, "signature_key_missing"
                                elif signature_alg != "hmac-sha256":
                                    trust, reason = TRUST_UNTRUSTED, "signature_alg_unsupported"
                                else:
                                    signature = manifest.get("signature")
                                    if not signature:
                                        trust, reason = TRUST_UNSIGNED, "signature_missing"
                                    elif signature != _compute_signature(py_file, signature_key):
                                        trust, reason = TRUST_UNTRUSTED, "signature_invalid"
                                    else:
                                        trust, reason = TRUST_TRUSTED, "allowlisted_and_valid"
                            else:
                                signature = manifest.get("signature")
                                if signature and signature_key and signature_alg == "hmac-sha256":
                                    if signature != _compute_signature(py_file, signature_key):
                                        trust, reason = TRUST_UNTRUSTED, "signature_invalid"
                                    else:
                                        trust, reason = TRUST_TRUSTED, "allowlisted_and_valid"
                                else:
                                    trust, reason = TRUST_TRUSTED, "allowlisted_and_valid"
            except Exception:
                trust, reason = TRUST_UNTRUSTED, "stat_failed"

        results.append(
            {
                "file": py_file,
                "plugin_id": plugin_id,
                "trust": trust,
                "reason": reason,
                "manifest": manifest,
            }
        )

    return results


def discover_plugins(plugin_dir: Path) -> List[Callable]:
    """
    Scan a directory for Python plugins and extract their matcher registration functions.
    
    Args:
        plugin_dir: Directory to scan for .py files.
        
    Returns:
        List of register_matchers functions from valid plugins.
    """
    plugins = []
    if not getattr(CONFIG, "enable_community_plugins", False):
        logger.info("Community plugins are disabled by default (enable_community_plugins=false)")
        return plugins
    
    if not plugin_dir.exists():
        logger.debug(f"Plugin directory {plugin_dir} does not exist, skipping.")
        return plugins
        
    allowlist = set(getattr(CONFIG, "plugin_allowlist", []) or [])
    if not allowlist:
        logger.info("Community plugins blocked: plugin_allowlist is empty")
        return plugins

    scan_results = scan_plugins(plugin_dir)
    for entry in scan_results:
        py_file = entry["file"]
        plugin_id = entry["plugin_id"]
        trust = entry["trust"]
        reason = entry["reason"]
        manifest = entry["manifest"]

        if trust != TRUST_TRUSTED:
            logger.info(f"Skipping {py_file.name}: trust={trust} reason={reason}")
            continue
            
        try:
            # Dynamic import using importlib
            module_name = f"comfyui_doctor_plugin_{py_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Check for standard entry point function 'register_matchers'
                if hasattr(module, "register_matchers") and callable(module.register_matchers):
                    matcher = module.register_matchers
                    setattr(matcher, "__plugin_id__", plugin_id or "community.plugin")
                    setattr(matcher, "__plugin_manifest__", manifest)
                    setattr(matcher, "__plugin_trust__", trust)
                    plugins.append(matcher)
                    logger.info(f"Loaded plugin: {py_file.name}")
                else:
                    logger.debug(f"Skipping {py_file.name}: No 'register_matchers' function found.")
        except Exception as e:
            logger.warning(f"Failed to load plugin {py_file}: {e}")
            logger.debug("Plugin load traceback", exc_info=True)
            
    return plugins
