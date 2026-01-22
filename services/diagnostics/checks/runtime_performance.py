"""
F14 Proactive Diagnostics - Runtime Performance Check

Analyzes workflow for potential runtime performance issues:
1. VRAM risk estimation (resolution * batch size vs available VRAM)
2. Excessive batch sizes
3. Extreme resolutions
4. Optimization suggestions (tiled VAE, etc.)
"""

import logging
import math
from typing import Dict, Any, List, Optional, Tuple

from ..models import (
    HealthIssue,
    HealthCheckRequest,
    IssueCategory,
    IssueSeverity,
    IssueTarget,
)
from . import register_check
from .env_deps import _get_env_info

logger = logging.getLogger("comfyui-doctor.diagnostics.checks.runtime_performance")


# ============================================================================
# Configuration & Heuristics
# ============================================================================

# Resolution thresholds (width * height)
RES_SD15_OPTIMAL = 512 * 512
RES_SDXL_OPTIMAL = 1024 * 1024
RES_WARNING_THRESHOLD = 2048 * 2048  # 4MP
RES_CRITICAL_THRESHOLD = 4096 * 4096  # 16MP

# Batch size thresholds
BATCH_WARNING_THRESHOLD = 8
BATCH_CRITICAL_THRESHOLD = 32

# VRAM Heuristics (Estimates)
VRAM_SYSTEM_OVERHEAD_GB = 1.5  # OS + Display + ComfyUI base
VRAM_MODEL_SD15_GB = 3.0       # UNet + VAE + CLIP
VRAM_MODEL_SDXL_GB = 8.0       # Base + Refiner approx
VRAM_MODEL_FLUX_GB = 16.0      # Large model

# Node types of interest
LATENT_NODES = {"EmptyLatentImage", "EmptyLatentAudio"}
IMAGE_NODES = {"LoadImage", "ImageScale", "ImageResize"}
BATCH_NODES = {"RepeatImage", "ImageBatch"}


# ============================================================================
# Check Implementation
# ============================================================================

@register_check("runtime_performance")
async def check_runtime_performance(
    workflow: Dict[str, Any],
    request: HealthCheckRequest,
) -> List[HealthIssue]:
    """
    Check workflow for runtime performance risks.

    Returns list of HealthIssues for detected problems.
    """
    issues: List[HealthIssue] = []
    
    # Get environment info (VRAM, etc.)
    env = _get_env_info()
    total_vram_gb = env.get("gpu_memory_gb", 0) or 0
    has_gpu = env.get("cuda_available", False) or env.get("mps_available", False)

    # 1. Analyze Latent/Image Dimensions & Batch Sizes
    max_dims, max_batch = _analyze_dimensions(workflow)
    
    # Check resolution risks
    issues.extend(_check_resolution(max_dims, has_gpu))
    
    # Check batch size risks
    issues.extend(_check_batch_size(max_batch))

    # 2. VRAM Estimates (Rough heuristic)
    # Only run if we have GPU info
    if has_gpu and total_vram_gb > 0:
        issues.extend(_check_vram_risk(max_dims, max_batch, total_vram_gb))

    return issues


def _analyze_dimensions(workflow: Dict[str, Any]) -> Tuple[Tuple[int, int], int]:
    """
    Find maximum dimensions and batch sizes in the workflow.
    Returns ((width, height), batch_size)
    """
    max_width = 0
    max_height = 0
    max_batch = 1
    
    nodes = workflow.get("nodes", [])
    if not isinstance(nodes, list):
        return (0, 0), 1
        
    for node in nodes:
        if not isinstance(node, dict):
            continue
            
        node_type = node.get("type", "")
        widgets_values = node.get("widgets_values", [])
        
        # EmptyLatentImage: [width, height, batch_size]
        if node_type == "EmptyLatentImage" and len(widgets_values) >= 3:
            try:
                w = int(widgets_values[0])
                h = int(widgets_values[1])
                b = int(widgets_values[2])
                
                if w * h > max_width * max_height:
                    max_width, max_height = w, h
                if b > max_batch:
                    max_batch = b
            except (ValueError, TypeError):
                pass
                
        # LoadImage: Usually just one image, check if we can get dims? 
        # (Dimensions are not in widget values usually, so skip for now)
        
        # Primitive nodes handling is complex, skipping for v1
        
    return (max_width, max_height), max_batch


def _check_resolution(dims: Tuple[int, int], has_gpu: bool) -> List[HealthIssue]:
    """Check for extreme resolutions."""
    issues = []
    width, height = dims
    pixels = width * height
    
    target = IssueTarget(setting="resolution")
    
    if pixels >= RES_CRITICAL_THRESHOLD:
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("extreme_resolution", target, f"{width}x{height}"),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.WARNING,
            title="Extreme Resolution Detected",
            summary=f"Workflow uses very high resolution: {width}x{height} ({pixels/1e6:.1f} MP)",
            evidence=[
                f"Max Dimensions: {width}x{height}",
                f"Pixel Count: {pixels}",
                "Significantly exceeds standard generation sizes"
            ],
            recommendation=[
                "Ensure you have sufficient VRAM (typically >24GB for this size)",
                "Consider using Tiled VAE Decoding to prevent OOM",
                "Consider generating at lower res and upscaling"
            ],
            target=target
        ))
    elif pixels >= RES_WARNING_THRESHOLD:
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("high_resolution", target, f"{width}x{height}"),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.INFO,
            title="High Resolution",
            summary=f"Workflow uses high resolution: {width}x{height}",
            evidence=[
                f"Dimensions: {width}x{height}",
                "Exceeds typical SDXL native resolution"
            ],
            recommendation=[
                "Verify VAE Decode capability",
                "Use Tiled VAE if you encounter Out of Memory errors"
            ],
            target=target
        ))
        
    return issues


def _check_batch_size(batch_size: int) -> List[HealthIssue]:
    """Check for large batch sizes."""
    issues = []
    target = IssueTarget(setting="batch_size")
    
    if batch_size >= BATCH_CRITICAL_THRESHOLD:
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("critical_batch_size", target, str(batch_size)),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.WARNING,
            title="Review Batch Size",
            summary=f"Large batch size detected: {batch_size}",
            evidence=[
                f"Batch Size: {batch_size}",
                "Can cause significant VRAM spikes"
            ],
            recommendation=[
                "Reduce batch size if OOM occurs",
                "Ensure total VRAM usage stays within limits"
            ],
            target=target
        ))
    
    return issues


def _check_vram_risk(dims: Tuple[int, int], batch_size: int, available_vram: float) -> List[HealthIssue]:
    """Estimate VRAM usage and warn if risky."""
    issues = []
    width, height = dims
    
    if width == 0 or height == 0:
        return issues
        
    # Heuristic: 
    # VRAM ~= Baseline + Model(avg) + (Pixels * Batch * BytesPerPixel * ProcessMultiplier)
    # BytesPerPixel: float32=4, float16=2. Multipliers depend on attention, etc.
    # We'll use a conservative multiplier for latent processing.
    # 1 Latent Pixel = 8x8 Image Pixels. But attention maps are huge.
    
    # Simplified estimation for "Working Memory" peak
    # Assuming float16 (2 bytes)
    # Resolution-dependent buffer size (Attention, VAE, etc.)
    # Empirically: 1024x1024 batch=1 takes ~2GB over model size on SDXL
    
    base_model_gb = VRAM_MODEL_SDXL_GB # Assume worst case (SDXL) for safety
    
    # Pixels in millions
    mp = (width * height) / 1e6
    
    # Rough formula: 
    # Extra VRAM = (MP * Batch * 1.5) GB
    # Example: 1MP * 1 * 1.5 = 1.5GB working
    # Example: 1MP * 4 * 1.5 = 6.0GB working
    estimated_working_gb = (mp * batch_size * 1.5)
    
    estimated_total_gb = VRAM_SYSTEM_OVERHEAD_GB + base_model_gb + estimated_working_gb
    
    risk_ratio = estimated_total_gb / available_vram
    
    if risk_ratio > 1.1: # >110% of VRAM
        target = IssueTarget(setting="vram_estimate")
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("vram_oom_risk", target, str(risk_ratio)),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.WARNING,
            title="High Risk of Out-of-Memory (OOM)",
            summary=f"Estimated VRAM usage ({estimated_total_gb:.1f}GB) exceeds available ({available_vram:.1f}GB)",
            evidence=[
                f"Available VRAM: {available_vram:.1f} GB",
                f"Estimated Usage: ~{estimated_total_gb:.1f} GB",
                f"Resolution: {width}x{height}",
                f"Batch Size: {batch_size}",
                "Based on SDXL checks (worst-case heuristic)"
            ],
            recommendation=[
                "Reduce resolution or batch size",
                "Use --lowvram command line argument if not enabled",
                "Close other GPU applications"
            ],
            target=target
        ))
    elif risk_ratio > 0.9: # >90% of VRAM
         target = IssueTarget(setting="vram_estimate")
         issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("vram_tight_risk", target, str(risk_ratio)),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.INFO,
            title="High VRAM Usage Expected",
            summary=f"Estimated VRAM usage is close to limit ({estimated_total_gb:.1f}/{available_vram:.1f} GB)",
            evidence=[
                f"Available VRAM: {available_vram:.1f} GB",
                f"Estimated Usage: ~{estimated_total_gb:.1f} GB"
            ],
            recommendation=[
                "Monitor VRAM usage during generation",
                "Close browser tabs/apps to free up shared GPU memory"
            ],
            target=target
        ))

    return issues
