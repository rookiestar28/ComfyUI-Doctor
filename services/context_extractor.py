"""
R14 Service: Context Extractor.
Extracts structured error context from tracebacks and logs.

Features:
- extract_error_summary(): Extract exception type + message from traceback
- collapse_stack_frames(): Keep first N + last M frames for token efficiency
- detect_fatal_pattern(): Identify non-traceback fatal errors
"""

import re
import logging
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

# Pattern to extract the final exception line from a traceback
EXCEPTION_LINE_PATTERN = re.compile(
    r'^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning|Interrupt)?)\s*:\s*(.+)$',
    re.MULTILINE
)

# Pattern to identify stack frame lines
FRAME_PATTERN = re.compile(r'^\s+File\s+"[^"]+",\s+line\s+\d+', re.MULTILINE)

# Non-traceback fatal error markers (Phase 3)
FATAL_MARKERS = [
    re.compile(r'^ERROR:\s*Exception\s+in\s+', re.IGNORECASE),
    re.compile(r'^CRITICAL:\s*', re.IGNORECASE),
    re.compile(r'^RuntimeError:\s*', re.IGNORECASE),
    re.compile(r'^\[ComfyUI\]\s+ERROR:\s*', re.IGNORECASE),
    re.compile(r'^OOM\s*:', re.IGNORECASE),  # Out of memory
    re.compile(r'^CUDA\s+out\s+of\s+memory', re.IGNORECASE),
]

# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ErrorSummary:
    """Structured error summary."""
    exception_type: str
    message: str
    category: Optional[str] = None  # From PatternMatcher if available
    
    def to_string(self) -> str:
        """Format as single-line summary."""
        if self.category:
            return f"[{self.category}] {self.exception_type}: {self.message}"
        return f"{self.exception_type}: {self.message}"

@dataclass
class ContextManifest:
    """Manifest of what context was included (for observability)."""
    traceback_chars: int = 0
    traceback_frames: int = 0
    logs_lines: int = 0
    workflow_nodes: int = 0
    env_packages_included: int = 0
    summary_present: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "traceback_chars": self.traceback_chars,
            "traceback_frames": self.traceback_frames,
            "logs_lines": self.logs_lines,
            "workflow_nodes": self.workflow_nodes,
            "env_packages_included": self.env_packages_included,
            "summary_present": self.summary_present,
        }

# ═══════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def extract_error_summary(
    traceback_text: str,
    pattern_category: Optional[str] = None
) -> Optional[ErrorSummary]:
    """
    Extract a short error summary from traceback text.
    
    Args:
        traceback_text: Full traceback string
        pattern_category: Optional category from PatternMatcher
        
    Returns:
        ErrorSummary or None if extraction fails
    """
    if not traceback_text:
        return None
    
    # Find the last exception line in the traceback
    lines = traceback_text.strip().split('\n')
    
    # Search from the end for the exception line
    for line in reversed(lines):
        line = line.strip()
        match = EXCEPTION_LINE_PATTERN.match(line)
        if match:
            exc_type = match.group(1)
            exc_message = match.group(2).strip()
            # Truncate message if too long
            if len(exc_message) > 200:
                exc_message = exc_message[:197] + "..."
            return ErrorSummary(
                exception_type=exc_type,
                message=exc_message,
                category=pattern_category
            )
    
    # Fallback: Try to find any line that looks like an exception
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith(('File ', 'Traceback ', '  ', 'During handling')):
            # This might be the exception line
            if ':' in line:
                parts = line.split(':', 1)
                return ErrorSummary(
                    exception_type=parts[0].strip(),
                    message=parts[1].strip()[:200] if len(parts) > 1 else "",
                    category=pattern_category
                )
    
    return None


def collapse_stack_frames(
    traceback_text: str,
    head_frames: int = 3,
    tail_frames: int = 5,
    preserve_exception: bool = True
) -> str:
    """
    Collapse stack frames to reduce token usage while preserving context.
    
    Keeps:
    - First N frames (head_frames) - shows entry point
    - Last M frames (tail_frames) - shows where error occurred
    - Exception line (always preserved)
    
    Args:
        traceback_text: Full traceback string
        head_frames: Number of frames to keep from the start
        tail_frames: Number of frames to keep from the end
        preserve_exception: Always keep the final exception line
        
    Returns:
        Collapsed traceback string
    """
    if not traceback_text:
        return ""
    
    lines = traceback_text.split('\n')
    result = []
    frame_indices = []
    
    # Find all frame start indices (lines starting with "  File ")
    for i, line in enumerate(lines):
        if FRAME_PATTERN.match(line):
            frame_indices.append(i)
    
    if len(frame_indices) <= head_frames + tail_frames:
        # No need to collapse
        return traceback_text
    
    # Determine which frames to keep
    keep_frames = set(frame_indices[:head_frames] + frame_indices[-tail_frames:])
    omitted_count = len(frame_indices) - len(keep_frames)
    
    # Build result
    i = 0
    omit_section_added = False
    
    while i < len(lines):
        line = lines[i]
        
        if FRAME_PATTERN.match(line):
            frame_idx = frame_indices.index(i) if i in frame_indices else -1
            
            if i in keep_frames:
                result.append(line)
                # Include the next line (code snippet) if it exists
                if i + 1 < len(lines) and lines[i + 1].strip().startswith('^') is False:
                    if not FRAME_PATTERN.match(lines[i + 1]) and not lines[i + 1].strip().startswith('Traceback'):
                        i += 1
                        result.append(lines[i])
                omit_section_added = False
            else:
                if not omit_section_added:
                    result.append(f"    ... ({omitted_count} frames omitted) ...")
                    omit_section_added = True
        else:
            result.append(line)
            omit_section_added = False
        
        i += 1
    
    return '\n'.join(result)


def detect_fatal_pattern(line: str) -> Optional[str]:
    """
    Detect if a log line matches a non-traceback fatal error pattern.
    
    Args:
        line: Single log line
        
    Returns:
        Pattern name if matched, None otherwise
    """
    if not line:
        return None
    
    line = line.strip()
    
    for i, pattern in enumerate(FATAL_MARKERS):
        if pattern.match(line):
            return f"fatal_marker_{i}"
    
    return None


def build_context_manifest(
    traceback_text: Optional[str] = None,
    execution_logs: Optional[List[str]] = None,
    workflow_json: Optional[Dict[str, Any]] = None,
    system_info: Optional[Dict[str, Any]] = None,
    error_summary: Optional[ErrorSummary] = None
) -> ContextManifest:
    """
    Build a manifest of included context for observability.
    
    Args:
        traceback_text: The traceback string
        execution_logs: List of log lines
        workflow_json: Workflow dict
        system_info: System info dict (may contain packages)
        error_summary: Extracted error summary
        
    Returns:
        ContextManifest with counts
    """
    manifest = ContextManifest()
    
    if traceback_text:
        manifest.traceback_chars = len(traceback_text)
        manifest.traceback_frames = len(FRAME_PATTERN.findall(traceback_text))
    
    if execution_logs:
        manifest.logs_lines = len(execution_logs)
    
    if workflow_json:
        manifest.workflow_nodes = len(workflow_json)
    
    if system_info and "packages" in system_info:
        packages = system_info.get("packages", [])
        if isinstance(packages, list):
            manifest.env_packages_included = len(packages)
    
    manifest.summary_present = error_summary is not None
    
    return manifest
