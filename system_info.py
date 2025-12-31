"""
System Environment Information Collector for ComfyUI-Doctor.
Captures Python version, installed packages, and OS info for AI analysis context.
"""

import sys
import platform
import subprocess
import time
from typing import Dict, Any, Optional
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
