"""
F14 Proactive Diagnostics - Environment & Dependencies Check

Analyzes system environment to detect:
1. Python version constraints (soft warning)
2. torch/cuda mismatch and "GPU expected but not available"
3. Missing optional accelerators (xformers/triton)
"""

import logging
import sys
import platform
from typing import Dict, Any, List, Optional

from ..models import (
    HealthIssue,
    HealthCheckRequest,
    IssueCategory,
    IssueSeverity,
    IssueTarget,
)
from . import register_check

logger = logging.getLogger("comfyui-doctor.diagnostics.checks.env_deps")


# ============================================================================
# Configuration
# ============================================================================

# Recommended Python versions
PYTHON_MIN_VERSION = (3, 10)
PYTHON_MAX_VERSION = (3, 12)

# GPU node types that require CUDA
GPU_REQUIRING_NODES = {
    "KSampler", "KSamplerAdvanced", "SamplerCustom",
    "VAEDecode", "VAEEncode", "VAEDecodeTiled", "VAEEncodeTiled",
    "CheckpointLoaderSimple", "CheckpointLoader",
    "ControlNetApply", "ControlNetApplyAdvanced",
    "IPAdapter", "IPAdapterApply",
}


# ============================================================================
# Cached Environment Info
# ============================================================================

_env_cache: Optional[Dict[str, Any]] = None


def _get_env_info() -> Dict[str, Any]:
    """Get cached environment information."""
    global _env_cache
    if _env_cache is not None:
        return _env_cache

    info: Dict[str, Any] = {
        "python_version": sys.version_info[:3],
        "platform": platform.system(),
        "torch_available": False,
        "torch_version": None,
        "cuda_available": False,
        "cuda_version": None,
        "cudnn_available": False,
        "cudnn_version": None,
        "mps_available": False,
        "xformers_available": False,
        "xformers_version": None,
        "triton_available": False,
        "triton_version": None,
        "gpu_name": None,
        "gpu_memory_gb": None,
    }

    # Check torch
    try:
        import torch
        info["torch_available"] = True
        info["torch_version"] = torch.__version__

        # Check CUDA
        info["cuda_available"] = torch.cuda.is_available()
        if info["cuda_available"]:
            info["cuda_version"] = torch.version.cuda
            info["cudnn_available"] = torch.backends.cudnn.is_available()
            if info["cudnn_available"]:
                info["cudnn_version"] = torch.backends.cudnn.version()

            # Get GPU info
            try:
                info["gpu_name"] = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                info["gpu_memory_gb"] = round(props.total_memory / (1024**3), 1)
            except Exception:
                pass

        # Check MPS (Apple Silicon)
        if hasattr(torch.backends, "mps"):
            info["mps_available"] = torch.backends.mps.is_available()

    except ImportError:
        pass

    # Check xformers
    try:
        import xformers
        info["xformers_available"] = True
        info["xformers_version"] = getattr(xformers, "__version__", "unknown")
    except ImportError:
        pass

    # Check triton
    try:
        import triton
        info["triton_available"] = True
        info["triton_version"] = getattr(triton, "__version__", "unknown")
    except ImportError:
        pass

    _env_cache = info
    return info


def _clear_env_cache():
    """Clear environment cache (for testing)."""
    global _env_cache
    _env_cache = None


# ============================================================================
# Check Implementation
# ============================================================================

@register_check("env_deps")
async def check_env_deps(
    workflow: Dict[str, Any],
    request: HealthCheckRequest,
) -> List[HealthIssue]:
    """
    Check environment and dependencies for issues.

    Returns list of HealthIssues for detected problems.
    """
    issues: List[HealthIssue] = []

    env = _get_env_info()

    # Check 1: Python version
    issues.extend(_check_python_version(env))

    # Check 2: PyTorch availability
    issues.extend(_check_torch_availability(env))

    # Check 3: CUDA/GPU availability (based on workflow needs)
    issues.extend(_check_gpu_availability(env, workflow))

    # Check 4: Optional accelerators
    issues.extend(_check_accelerators(env))

    return issues


def _check_python_version(env: Dict[str, Any]) -> List[HealthIssue]:
    """Check Python version compatibility."""
    issues: List[HealthIssue] = []

    py_version = env["python_version"]
    py_str = ".".join(map(str, py_version))

    if py_version < PYTHON_MIN_VERSION:
        target = IssueTarget(setting="python_version")
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("python_too_old", target, py_str),
            category=IssueCategory.ENV,
            severity=IssueSeverity.WARNING,
            title="Python Version Too Old",
            summary=f"Python {py_str} may not be fully compatible with ComfyUI",
            evidence=[
                f"Current Python version: {py_str}",
                f"Recommended minimum: {'.'.join(map(str, PYTHON_MIN_VERSION))}",
            ],
            recommendation=[
                f"Consider upgrading to Python {'.'.join(map(str, PYTHON_MIN_VERSION))} or newer",
                "Some features may not work correctly on older Python versions",
            ],
            target=target,
        ))

    if py_version > PYTHON_MAX_VERSION:
        target = IssueTarget(setting="python_version")
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("python_too_new", target, py_str),
            category=IssueCategory.ENV,
            severity=IssueSeverity.INFO,
            title="Python Version May Be Too New",
            summary=f"Python {py_str} may have compatibility issues with some dependencies",
            evidence=[
                f"Current Python version: {py_str}",
                f"Tested up to: {'.'.join(map(str, PYTHON_MAX_VERSION))}",
            ],
            recommendation=[
                "Some packages (especially compiled ones) may not have wheels for this Python version",
                "If you encounter import errors, consider using an older Python version",
            ],
            target=target,
        ))

    return issues


def _check_torch_availability(env: Dict[str, Any]) -> List[HealthIssue]:
    """Check PyTorch availability and configuration."""
    issues: List[HealthIssue] = []

    if not env["torch_available"]:
        target = IssueTarget(setting="torch")
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("torch_missing", target, ""),
            category=IssueCategory.DEPS,
            severity=IssueSeverity.CRITICAL,
            title="PyTorch Not Available",
            summary="PyTorch is not installed or cannot be imported",
            evidence=[
                "PyTorch import failed",
                "ComfyUI requires PyTorch for all image generation operations",
            ],
            recommendation=[
                "Install PyTorch: pip install torch torchvision",
                "For GPU support, install the CUDA version: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121",
            ],
            target=target,
        ))

    return issues


def _check_gpu_availability(
    env: Dict[str, Any],
    workflow: Dict[str, Any],
) -> List[HealthIssue]:
    """Check GPU availability based on workflow requirements."""
    issues: List[HealthIssue] = []

    # Determine if workflow likely needs GPU
    nodes = workflow.get("nodes", [])
    needs_gpu = False
    gpu_nodes = []

    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict):
                node_type = node.get("type", "")
                if any(gpu_type in node_type for gpu_type in GPU_REQUIRING_NODES):
                    needs_gpu = True
                    gpu_nodes.append(node_type)

    if not needs_gpu:
        return issues

    # Check if GPU is available
    has_gpu = env["cuda_available"] or env["mps_available"]

    if not has_gpu and env["torch_available"]:
        target = IssueTarget(setting="gpu")
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("no_gpu", target, ""),
            category=IssueCategory.ENV,
            severity=IssueSeverity.WARNING,
            title="No GPU Acceleration Available",
            summary="Workflow contains GPU-intensive nodes but no GPU is available",
            evidence=[
                f"CUDA available: {env['cuda_available']}",
                f"MPS available (Apple Silicon): {env['mps_available']}",
                f"GPU-requiring nodes: {', '.join(sorted(list(set(gpu_nodes)))[:5])}{'...' if len(set(gpu_nodes)) > 5 else ''}",
            ],
            recommendation=[
                "Generation will be very slow on CPU",
                "Install CUDA-enabled PyTorch for NVIDIA GPUs",
                "For Apple Silicon, ensure MPS backend is enabled",
            ],
            target=target,
        ))

    # Check for CUDA but no cuDNN (suboptimal)
    if env["cuda_available"] and not env["cudnn_available"]:
        target = IssueTarget(setting="cudnn")
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("no_cudnn", target, ""),
            category=IssueCategory.DEPS,
            severity=IssueSeverity.INFO,
            title="cuDNN Not Available",
            summary="CUDA is available but cuDNN is not, which may reduce performance",
            evidence=[
                f"CUDA version: {env['cuda_version']}",
                "cuDNN provides optimized deep learning primitives",
            ],
            recommendation=[
                "cuDNN usually comes with PyTorch CUDA packages",
                "If missing, reinstall PyTorch with CUDA support",
            ],
            target=target,
        ))

    return issues


def _check_accelerators(env: Dict[str, Any]) -> List[HealthIssue]:
    """Check for optional accelerators (xformers, triton)."""
    issues: List[HealthIssue] = []

    # Only suggest accelerators if CUDA is available
    if not env["cuda_available"]:
        return issues

    # Check xformers
    if not env["xformers_available"]:
        target = IssueTarget(setting="xformers")
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("no_xformers", target, ""),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.INFO,
            title="xformers Not Installed",
            summary="xformers can significantly improve memory efficiency and speed",
            evidence=[
                "xformers provides memory-efficient attention implementations",
                f"GPU: {env['gpu_name'] or 'Unknown'}",
                f"GPU VRAM: {env['gpu_memory_gb'] or 'Unknown'} GB",
            ],
            recommendation=[
                "Install xformers: pip install xformers",
                "Enables memory-efficient attention, reducing VRAM usage by 20-50%",
                "Particularly helpful for high-resolution generation",
            ],
            target=target,
        ))

    # Check triton (Windows support is limited)
    if not env["triton_available"] and env["platform"] != "Windows":
        target = IssueTarget(setting="triton")
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("no_triton", target, ""),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.INFO,
            title="Triton Not Installed",
            summary="Triton can enable additional optimizations for some operations",
            evidence=[
                "Triton provides JIT-compiled GPU kernels",
                f"Platform: {env['platform']}",
            ],
            recommendation=[
                "Install triton: pip install triton",
                "Note: Triton has limited Windows support",
                "Primarily benefits Linux users",
            ],
            target=target,
        ))

    return issues
