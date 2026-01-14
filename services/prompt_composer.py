"""
R14 Service: Prompt Composer.
Unified context-to-prompt logic for /doctor/analyze and /doctor/chat endpoints.

Features:
- compose(): Build LLM-ready prompt from structured llm_context
- Summary-first ordering
- Token budget integration with R12
- Legacy fallback support via feature flag
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PromptComposerConfig:
    """Configuration for prompt composition."""
    max_traceback_chars: int = 4000
    max_logs_lines: int = 50
    max_workflow_chars: int = 2000
    max_env_chars: int = 1000
    include_summary: bool = True
    include_node_info: bool = True
    include_execution_logs: bool = True
    include_workflow: bool = True
    include_system_info: bool = True
    use_legacy_format: bool = False  # Feature flag for rollback

# ═══════════════════════════════════════════════════════════════════════════
# PROMPT COMPOSER
# ═══════════════════════════════════════════════════════════════════════════

class PromptComposer:
    """
    Composes LLM-ready prompts from structured context.
    
    Used by:
    - /doctor/analyze (single-shot analysis)
    - /doctor/chat (system prompt enrichment)
    """
    
    def __init__(self, token_budget_service=None):
        """
        Initialize composer.
        
        Args:
            token_budget_service: Optional R12 TokenBudgetService for budget enforcement
        """
        self.budget_service = token_budget_service
    
    def compose(
        self,
        llm_context: Dict[str, Any],
        config: Optional[PromptComposerConfig] = None
    ) -> str:
        """
        Compose an LLM-ready prompt from structured context.
        
        Section order (summary-first):
        1. Error Summary (R14: most important signal first)
        2. Failed Node Info
        3. Traceback (collapsed if long)
        4. Execution Logs
        5. Workflow Subset
        6. System Info
        
        Args:
            llm_context: Structured context dict from LLMContextBuilderStage
            config: Composition configuration
            
        Returns:
            Formatted prompt string
        """
        config = config or PromptComposerConfig()
        
        if config.use_legacy_format:
            return self._compose_legacy(llm_context, config)
        
        sections = []
        
        # 1. Error Summary (R14: Summary-first)
        if config.include_summary and llm_context.get("error_summary"):
            sections.append(self._format_section(
                "Error Summary",
                llm_context["error_summary"]
            ))
        
        # 2. Failed Node Info
        if config.include_node_info and llm_context.get("node_info"):
            node_info = llm_context["node_info"]
            if any(node_info.values()):
                node_text = self._format_node_info(node_info)
                sections.append(self._format_section("Failed Node", node_text))
        
        # 3. Traceback
        traceback = llm_context.get("traceback", "")
        if traceback:
            # Truncate if needed
            if len(traceback) > config.max_traceback_chars:
                traceback = traceback[:config.max_traceback_chars] + "\n... (truncated)"
            sections.append(self._format_section("Traceback", traceback))
        
        # 4. Execution Logs
        if config.include_execution_logs and llm_context.get("execution_logs"):
            logs = llm_context["execution_logs"][:config.max_logs_lines]
            if logs:
                logs_text = "\n".join(str(log) for log in logs)
                sections.append(self._format_section("Recent Logs", logs_text))
        
        # 5. Workflow Subset
        if config.include_workflow and llm_context.get("workflow_subset"):
            workflow = llm_context["workflow_subset"]
            workflow_text = self._format_workflow(workflow, config.max_workflow_chars)
            if workflow_text:
                sections.append(self._format_section("Workflow Context", workflow_text))
        
        # 6. System Info
        if config.include_system_info and llm_context.get("system_info"):
            sys_info = llm_context["system_info"]
            sys_text = self._format_system_info(sys_info, config.max_env_chars)
            if sys_text:
                sections.append(self._format_section("System Environment", sys_text))
        
        return "\n\n".join(sections)
    
    def _format_section(self, title: str, content: str) -> str:
        """Format a section with title and content."""
        return f"## {title}\n{content}"
    
    def _format_node_info(self, node_info: Dict[str, Any]) -> str:
        """Format node information."""
        parts = []
        if node_info.get("node_id"):
            parts.append(f"- Node ID: #{node_info['node_id']}")
        if node_info.get("node_name"):
            parts.append(f"- Node Name: {node_info['node_name']}")
        if node_info.get("node_class"):
            parts.append(f"- Node Class: {node_info['node_class']}")
        if node_info.get("custom_node_path"):
            parts.append(f"- Source: {node_info['custom_node_path']}")
        return "\n".join(parts) if parts else ""
    
    def _format_workflow(self, workflow: Dict[str, Any], max_chars: int) -> str:
        """Format workflow subset with truncation."""
        import json
        try:
            workflow_str = json.dumps(workflow, indent=2)
            if len(workflow_str) > max_chars:
                workflow_str = workflow_str[:max_chars] + "\n... (truncated)"
            return f"```json\n{workflow_str}\n```"
        except Exception:
            return ""
    
    def _format_system_info(self, sys_info: Dict[str, Any], max_chars: int) -> str:
        """Format system info with selective inclusion."""
        parts = []
        
        # Include key info
        if sys_info.get("os"):
            parts.append(f"- OS: {sys_info['os']}")
        if sys_info.get("python_version"):
            parts.append(f"- Python: {sys_info['python_version']}")
        if sys_info.get("cuda_available") is not None:
            parts.append(f"- CUDA: {'Available' if sys_info['cuda_available'] else 'Not Available'}")
        if sys_info.get("torch_version"):
            parts.append(f"- PyTorch: {sys_info['torch_version']}")
        
        # Include error-referenced packages only
        if sys_info.get("packages"):
            packages = sys_info.get("packages", [])
            if isinstance(packages, list) and packages:
                pkg_list = packages[:10]  # Limit to 10 most relevant
                pkg_str = ", ".join(str(p) for p in pkg_list)
                if len(packages) > 10:
                    pkg_str += f" (+{len(packages) - 10} more)"
                parts.append(f"- Key Packages: {pkg_str}")
        
        text = "\n".join(parts)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... (truncated)"
        return text
    
    def _compose_legacy(
        self,
        llm_context: Dict[str, Any],
        config: PromptComposerConfig
    ) -> str:
        """
        Legacy format for rollback compatibility.
        Order: traceback → node → workflow → env (original order)
        """
        sections = []
        
        # Traceback first (legacy order)
        if llm_context.get("traceback"):
            sections.append(f"Error:\n{llm_context['traceback'][:config.max_traceback_chars]}")
        
        # Node context
        if llm_context.get("node_info"):
            import json
            sections.append(f"Node Context:\n{json.dumps(llm_context['node_info'], indent=2)}")
        
        # Workflow
        if llm_context.get("workflow_subset"):
            import json
            sections.append(f"Workflow:\n{json.dumps(llm_context['workflow_subset'], indent=2)[:config.max_workflow_chars]}")
        
        # System info
        if llm_context.get("system_info"):
            import json
            sections.append(f"System Environment:\n{json.dumps(llm_context['system_info'], indent=2)[:config.max_env_chars]}")
        
        return "\n\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

_prompt_composer: Optional[PromptComposer] = None


def get_prompt_composer(token_budget_service=None) -> PromptComposer:
    """
    Get or create the global prompt composer instance.
    
    Args:
        token_budget_service: Optional TokenBudgetService for R12 integration
        
    Returns:
        The global PromptComposer instance
    """
    global _prompt_composer
    
    if _prompt_composer is None:
        _prompt_composer = PromptComposer(token_budget_service)
    
    return _prompt_composer
