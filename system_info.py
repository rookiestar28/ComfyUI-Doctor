"""
System Environment Information Collector for ComfyUI-Doctor.
Captures Python version, installed packages, and OS info for AI analysis context.
"""

import sys
import platform
import subprocess
import time
from typing import Dict, Any, Optional, List
from functools import lru_cache


# Cache TTL in seconds (24 hours)
_CACHE_TTL = 24 * 60 * 60
_cache_timestamp: Optional[float] = None
_cached_env_info: Optional[Dict[str, Any]] = None


def _run_pip_list() -> str:
    """
    Run 'pip list' to get installed packages.
    Returns formatted string of packages, or error message if fails.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
            timeout=10,  # 10 second timeout
            check=False
        )

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"[Error running pip list: {result.stderr.strip()}]"

    except subprocess.TimeoutExpired:
        return "[pip list timed out after 10 seconds]"
    except Exception as e:
        return f"[pip list failed: {str(e)}]"


@lru_cache(maxsize=1)
def _get_torch_info() -> Dict[str, Any]:
    """Get PyTorch and CUDA information (cached)."""
    try:
        import torch
        return {
            "pytorch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        }
    except ImportError:
        return {
            "pytorch_version": None,
            "cuda_available": False,
            "cuda_version": None,
            "gpu_count": 0,
        }


def get_system_environment(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get comprehensive system environment information.

    Uses 24-hour cache to avoid performance impact from repeated pip list calls.

    Args:
        force_refresh: Force refresh cache even if not expired

    Returns:
        Dictionary containing:
        - os: OS name and version
        - python_version: Python version string
        - pytorch_info: PyTorch and CUDA details
        - installed_packages: pip list output (cached for 24h)
        - cache_age_seconds: How old the package cache is
    """
    global _cache_timestamp, _cached_env_info

    current_time = time.time()
    cache_valid = (
        _cache_timestamp is not None
        and _cached_env_info is not None
        and (current_time - _cache_timestamp) < _CACHE_TTL
    )

    # Return cached data if valid and not forcing refresh
    if cache_valid and not force_refresh:
        cache_age = current_time - _cache_timestamp
        _cached_env_info["cache_age_seconds"] = int(cache_age)
        return _cached_env_info

    # Collect fresh environment data
    env_info = {
        "os": f"{platform.system()} {platform.release()}",
        "os_version": platform.version(),
        "python_version": sys.version.split()[0],
        "pytorch_info": _get_torch_info(),
        "installed_packages": _run_pip_list(),
        "cache_age_seconds": 0,
    }

    # Update cache
    _cache_timestamp = current_time
    _cached_env_info = env_info

    return env_info


def format_env_for_llm(env_info: Dict[str, Any], max_packages: int = 50) -> str:
    """
    Format environment info as concise text for LLM context.

    Args:
        env_info: Environment dictionary from get_system_environment()
        max_packages: Maximum number of packages to include (top N most relevant)

    Returns:
        Formatted string suitable for LLM prompt
    """
    lines = []

    lines.append("=== System Environment ===")
    lines.append(f"OS: {env_info['os']}")
    lines.append(f"Python: {env_info['python_version']}")

    torch_info = env_info['pytorch_info']
    if torch_info['pytorch_version']:
        lines.append(f"PyTorch: {torch_info['pytorch_version']}")
        if torch_info['cuda_available']:
            lines.append(f"CUDA: {torch_info['cuda_version']} ({torch_info['gpu_count']} GPU(s))")
        else:
            lines.append("CUDA: Not available")

    # Package list - prioritize ComfyUI-related and common dependencies
    packages_raw = env_info['installed_packages']
    if packages_raw and not packages_raw.startswith("["):  # Not an error message
        lines.append("\n=== Key Installed Packages ===")

        # Filter and prioritize packages
        all_packages = packages_raw.split('\n')
        priority_keywords = [
            'torch', 'cuda', 'comfy', 'numpy', 'pillow', 'opencv',
            'transformers', 'diffusers', 'safetensors', 'accelerate',
            'xformers', 'triton', 'onnx', 'tensorrt', 'insightface'
        ]

        priority_packages = []
        other_packages = []

        for pkg in all_packages:
            if any(keyword in pkg.lower() for keyword in priority_keywords):
                priority_packages.append(pkg)
            else:
                other_packages.append(pkg)

        # Show priority packages first, then fill with others up to max_packages
        selected = priority_packages[:max_packages]
        remaining_slots = max_packages - len(selected)
        if remaining_slots > 0:
            selected.extend(other_packages[:remaining_slots])

        for pkg in selected:
            lines.append(pkg)

        total_packages = len(all_packages)
        if total_packages > max_packages:
            lines.append(f"... ({total_packages - max_packages} more packages)")

    cache_age = env_info.get('cache_age_seconds', 0)
    if cache_age > 0:
        hours = cache_age // 3600
        lines.append(f"\n(Package cache age: {hours}h)")

    return '\n'.join(lines)


def clear_cache() -> None:
    """Clear the environment info cache (force fresh collection on next call)."""
    global _cache_timestamp, _cached_env_info
    _cache_timestamp = None
    _cached_env_info = None
    _get_torch_info.cache_clear()


# ═══════════════════════════════════════════════════════════════════════════
# R15: SYSTEM INFO CANONICALIZATION
# ═══════════════════════════════════════════════════════════════════════════

# Baseline packages always included (if present in pip freeze)
_BASELINE_PACKAGES = frozenset([
    'torch', 'pytorch', 'comfy', 'comfyui', 'numpy', 'pillow', 'pil',
    'opencv', 'cv2', 'diffusers', 'transformers', 'safetensors',
    'accelerate', 'xformers', 'triton'
])

# Runtime-related packages to prioritize when seen in error text
_RUNTIME_KEYWORDS = frozenset([
    'xformers', 'triton', 'onnx', 'onnxruntime', 'insightface',
    'torch', 'cuda', 'tensorrt', 'bitsandbytes', 'flash_attn',
    'segment_anything', 'groundingdino', 'mediapipe', 'ultralytics'
])


def _extract_package_keywords_from_error(error_text: str) -> set:
    """
    Extract package names referenced in error messages.
    
    Handles:
    - ModuleNotFoundError: No module named 'pkg.sub'
    - ImportError: cannot import name ... from 'pkg'
    - Generic mentions of package names in traceback
    
    Returns:
        Set of package name keywords (lowercase)
    """
    if not error_text:
        return set()
    
    import re
    keywords = set()
    
    # Pattern 1: ModuleNotFoundError: No module named 'pkg' or 'pkg.sub'
    for match in re.finditer(r"No module named ['\"]([^'\"\.]+)", error_text, re.IGNORECASE):
        keywords.add(match.group(1).lower())
    
    # Pattern 2: ImportError: cannot import name ... from 'pkg'
    for match in re.finditer(r"cannot import name .+ from ['\"]([^'\"\.]+)", error_text, re.IGNORECASE):
        keywords.add(match.group(1).lower())
    
    # Pattern 3: ModuleNotFoundError with full path like 'pkg.submodule'
    for match in re.finditer(r"No module named ['\"]([^'\"]+)['\"]", error_text, re.IGNORECASE):
        full_path = match.group(1)
        if '.' in full_path:
            keywords.add(full_path.split('.')[0].lower())
    
    # Pattern 4: Runtime keywords mentioned anywhere in error
    error_lower = error_text.lower()
    for kw in _RUNTIME_KEYWORDS:
        if kw in error_lower:
            keywords.add(kw)
    
    return keywords


def _parse_packages_from_freeze(freeze_str: str) -> Dict[str, str]:
    """
    Parse pip freeze output into dict of {package_name_lower: 'pkg==version'}.
    
    Returns:
        Dict mapping lowercase package name to original freeze line
    """
    packages = {}
    if not freeze_str or freeze_str.startswith('['):
        return packages
    
    for line in freeze_str.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Handle both '==' and other separators like '@' for editable installs
        if '==' in line:
            pkg_name = line.split('==')[0].lower().replace('-', '_').replace('.', '_')
            packages[pkg_name] = line
        elif '@' in line:
            pkg_name = line.split('@')[0].strip().lower().replace('-', '_').replace('.', '_')
            packages[pkg_name] = line
    
    return packages


def _select_packages(
    all_packages: Dict[str, str],
    error_keywords: set,
    max_packages: int
) -> List[str]:
    """
    Select most relevant packages based on priority:
    1. Error-referenced packages (from error text)
    2. Baseline packages (core ML/ComfyUI dependencies)
    3. Other runtime keywords
    
    Returns:
        List of package strings (e.g., ['torch==2.1.0', 'numpy==1.24.0'])
    """
    selected = []
    used_keys = set()
    
    # Priority 1: Error-referenced packages
    for kw in error_keywords:
        if kw in all_packages and kw not in used_keys:
            selected.append(all_packages[kw])
            used_keys.add(kw)
            if len(selected) >= max_packages:
                return selected
    
    # Priority 2: Baseline packages
    for kw in _BASELINE_PACKAGES:
        if kw in all_packages and kw not in used_keys:
            selected.append(all_packages[kw])
            used_keys.add(kw)
            if len(selected) >= max_packages:
                return selected
    
    # Priority 3: Runtime keywords
    for kw in _RUNTIME_KEYWORDS:
        if kw in all_packages and kw not in used_keys:
            selected.append(all_packages[kw])
            used_keys.add(kw)
            if len(selected) >= max_packages:
                return selected
    
    return selected


def canonicalize_system_info(
    env_info: Dict[str, Any],
    *,
    error_text: Optional[str] = None,
    privacy_mode: str = "basic",
    max_packages: int = 20
) -> Dict[str, Any]:
    """
    R15: Transform raw system_info from get_system_environment() into canonical schema.
    
    Canonical schema:
    {
        "os": "Windows 11",
        "python_version": "3.10.11",
        "torch_version": "2.1.0+cu121",
        "cuda_available": true,
        "cuda_version": "12.1",
        "gpu_count": 1,
        "packages": ["torch==2.1.0", "xformers==0.0.23", ...],
        "packages_total": 412,
        "cache_age_seconds": 3600,
        "source": "get_system_environment"
    }
    
    Args:
        env_info: Raw environment dict from get_system_environment() or already canonical
        error_text: Optional error text for smart package keyword extraction
        privacy_mode: 'none' | 'basic' | 'strict' - affects future sanitization passes
        max_packages: Maximum number of packages to include (default 20)
        
    Returns:
        Canonical system_info dict
    """
    # Check if already canonical (has flattened torch_version and packages list)
    if isinstance(env_info.get("packages"), list) and "torch_version" in env_info:
        # Already canonical, just ensure caps
        result = dict(env_info)
        if len(result.get("packages", [])) > max_packages:
            result["packages"] = result["packages"][:max_packages]
        return result
    
    # Build canonical schema
    result: Dict[str, Any] = {
        "source": "get_system_environment"
    }
    
    # OS info (pass through)
    if env_info.get("os"):
        os_str = env_info["os"]
        if env_info.get("os_version"):
            os_str = f"{os_str} {env_info['os_version']}"
        result["os"] = os_str
    
    # Python version (pass through)
    if env_info.get("python_version"):
        result["python_version"] = env_info["python_version"]
    
    # Flatten torch info from nested dict
    pytorch_info = env_info.get("pytorch_info", {})
    if isinstance(pytorch_info, dict):
        if pytorch_info.get("pytorch_version"):
            result["torch_version"] = pytorch_info["pytorch_version"]
        result["cuda_available"] = pytorch_info.get("cuda_available", False)
        if pytorch_info.get("cuda_version"):
            result["cuda_version"] = pytorch_info["cuda_version"]
        if pytorch_info.get("gpu_count"):
            result["gpu_count"] = pytorch_info["gpu_count"]
    
    # Parse and select packages
    freeze_str = env_info.get("installed_packages", "")
    all_packages = _parse_packages_from_freeze(freeze_str)
    
    # Extract keywords from error text
    error_keywords = _extract_package_keywords_from_error(error_text) if error_text else set()
    
    # Select packages with priority
    selected_packages = _select_packages(all_packages, error_keywords, max_packages)
    
    result["packages"] = selected_packages
    result["packages_total"] = len(all_packages)
    
    # Cache age (pass through)
    if env_info.get("cache_age_seconds") is not None:
        result["cache_age_seconds"] = env_info["cache_age_seconds"]
    
    return result
