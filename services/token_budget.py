"""
R12 Service: Token Budget.
Manages LLM context size by progressively trimming payload sections 
until they fit within the defined provider budget.
"""

import logging
import copy
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Literal

from .token_estimator import TokenEstimator, EstimatorConfig, TokenEstimate
from .workflow_pruner import WorkflowPruner, PruneConfig

logger = logging.getLogger(__name__)

@dataclass
class BudgetConfig:
    """Configuration for token budget."""
    enabled_remote: bool = True
    enabled_local: bool = False
    
    soft_max_tokens: int = 4000
    hard_max_tokens: int = 6000
    
    trimming_policy: Literal["remote_strict", "local_soft"] = "remote_strict"
    
    # Estimator settings
    estimator_config: EstimatorConfig = field(default_factory=EstimatorConfig)
    
    # Pruning defaults
    prune_default_depth: int = 3
    prune_default_nodes: int = 40
    
    # Fixed overhead reserved for system prompt, message structure, etc.
    overhead_fixed: int = 1000

@dataclass
class BudgetResult:
    """Result of budget application."""
    final_payload: Dict[str, Any]
    metadata: Dict[str, Any] # R12 metadata (token_budget, pruning, trim)
    budget_satisfied: bool
    trim_steps: List[str]

class TokenBudgetService:
    """
    Service to apply token budget constraints to LLM payloads.
    """
    
    def __init__(self, estimator: Optional[TokenEstimator] = None, pruner: Optional[WorkflowPruner] = None):
        self.estimator = estimator or TokenEstimator()
        self.pruner = pruner or WorkflowPruner()

    def apply_token_budget(
        self,
        payload: Dict[str, Any],
        is_remote_provider: bool,
        config: BudgetConfig
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Apply token budget to the payload.
        Returns (pruned_payload, r12_metadata).
        """
        # 0. Check if enabled
        is_enabled = config.enabled_remote if is_remote_provider else config.enabled_local
        if not is_enabled:
            return payload, {}

        # Working copy to avoid mutating original
        # Note: If deepcopy is too slow for massive workflows, we might need optimization.
        # But payload usually contains dicts/lists, so shallow copy isn't enough.
        current_payload = copy.deepcopy(payload)
        
        # 1. Identify Sections
        # Map payload fields to logical sections
        # Standard Doctor payload (defined in api_chat):
        # - system_prompt (or in messages)
        # - messages (user/assistant)
        # - error_context (traceback, workflow, etc - often embedded in system prompt or user msg)
        
        # NOTE: In api_chat, the payload structure provided to apply_token_budget 
        # depends on WHERE we call it. The plan says "build_llm_payload" -> R12 matches provider format (OpenAI/Anthropic).
        # OR we call it on the internal data structure BEFORE mapping to provider format.
        # Calling on internal structure (messages, error_context dict) is safer/easier than parsing "messages" list.
        # BUT api_chat builds the prompt string inside the handler.
        # To effectively trim, R12 needs access to the raw components: 
        # error_text, workflow_json, node_context, system_info.
        
        # Since we integrate in __init__.py `api_chat`, we likely pass the *internal* context dicts 
        # OR we operate on the final payload.
        # Modifying the final prompt string is hard (regex parsing).
        # Ideally we operate on the data used to BUILD the prompt.
        
        # REVISION to plan during implementation:
        # To make this robust, `apply_token_budget` should probably take the *components* 
        # and return the *trimmed components*, which `api_chat` then uses to build the prompt.
        # OR `apply_token_budget` operates on the specific `error_context` dict which contains the big data.
        
        # Let's assume we pass the `error_context` and updates it.
        # But wait, `api_chat` constructs the prompt string itself.
        # If we return a trimmed `error_context`, `api_chat` will use that to build the prompt.
        # This seems like the best injection point:
        # Before prompt construction, create trimmed context.
        
        # However, the interface in Plan said `apply_token_budget(payload, ...)`
        # If "payload" means the strict LLM JSON payload (messages list), we have to parse text.
        # That's messy.
        
        # Let's look at `api_chat` in __init__.py again.
        # It takes `data = await request.json()`.
        # Then `error_context = data.get("error_context", {})`.
        # Then it builds `system_prompt`.
        
        # Best approach: R12 Service takes `error_context` (and maybe messages) 
        # and returns a `trimmed_error_context`.
        # We can simulate this by having `payload` argument actually accept the `error_context` dict 
        # (or a dict containing error_context, messages, etc).
        
        # Let's support a flexible input: dictionary containing 'error_context' key.
        # For the integration in __init__.py, we will pass `{'error_context': error_context, ...}`
        
        trim_steps = []
        
        # Extract components
        error_context = current_payload.get("error_context", {})
        # If error_context is inside "data" or similar, handle it. 
        # But let's assume caller passes the dict that holds "error_context".
        
        if not error_context:
            # Nothing to trim
            return payload, {}
            
        target_node_id = None
        if "node_context" in error_context:
            target_node_id = error_context["node_context"].get("node_id")

        # Initial Estimate - by section for observability
        def estimate_section(key: str, ctx: dict) -> int:
            """Estimate tokens for a specific section."""
            if key not in ctx:
                return 0
            return self.estimator.estimate(json.dumps(ctx[key])).estimated_tokens
        
        def estimate_by_section(ctx: dict) -> dict:
            """Get token breakdown by section."""
            sections = {
                "workflow": estimate_section("workflow", ctx),
                "traceback": estimate_section("traceback", ctx),
                "node_context": estimate_section("node_context", ctx),
                "system_info": sum(estimate_section(k, ctx) for k in ["pip_list", "system_env", "env_info"] if k in ctx),
            }
            sections["other"] = self.estimator.estimate(json.dumps(ctx)).estimated_tokens - sum(sections.values())
            sections["other"] = max(0, sections["other"])  # Clamp to 0
            return sections
        
        def estimate_total(ctx: dict) -> int:
            return self.estimator.estimate(json.dumps(ctx)).estimated_tokens
        
        # Initial by-section breakdown
        initial_by_section = estimate_by_section(error_context)
        current_tokens = sum(initial_by_section.values())
        
        # 2. Fixed overhead (system instructions, user query)
        overhead_tokens = config.overhead_fixed
        
        total_estimated = current_tokens + overhead_tokens
        
        # Step-by-step token tracking for observability
        step_history = [{
            "step": "initial",
            "tokens": total_estimated,
            "by_section": initial_by_section.copy()
        }]
        
        # Metadata tracking - enhanced for observability
        r12_meta = {
            "version": "1.0",
            "token_budget": {
                "enabled": True,
                "provider_type": "remote" if is_remote_provider else "local",
                "soft_max_tokens": config.soft_max_tokens,
                "hard_max_tokens": config.hard_max_tokens,
                "overhead_fixed": config.overhead_fixed,
                "estimated_tokens_initial": total_estimated,
                "by_section_initial": initial_by_section,
                "estimator_method": "tiktoken" if self.estimator._get_encoding("gpt-4") else "fallback"
            },
            "pruning": {
                "applied": False,
                "mode": None,
                "kept_nodes": [],
                "dropped_count": 0,
                "depth_used": None,
                "nodes_limit_used": None,
                "reason": None
            },
            "trim": {
                "steps": [],
                "step_history": step_history,
                "degraded": False,
                "final_policy": config.trimming_policy
            }
        }
        
        if total_estimated <= config.soft_max_tokens:
            r12_meta["token_budget"]["estimated_tokens_final"] = total_estimated
            r12_meta["token_budget"]["by_section_final"] = initial_by_section
            r12_meta["token_budget"]["budget_used_ratio"] = total_estimated / config.hard_max_tokens
            return current_payload, r12_meta
            
        # 3. Progressive Trimming Loop
        # Strategy: Reduce components in order until budget met 
        # OR until hard limit met (for remote)
        
        max_budget = config.hard_max_tokens if config.trimming_policy == "remote_strict" else config.soft_max_tokens
        
        # Valid trimming actions
        actions = [
            ("prune_workflow_std", {"depth": config.prune_default_depth, "nodes": config.prune_default_nodes}),
            ("prune_workflow_agg", {"depth": max(1, config.prune_default_depth - 1), "nodes": max(10, config.prune_default_nodes // 2)}),
            ("prune_workflow_min", {"depth": 1, "nodes": 10}),
            ("drop_system_info", {}),
            ("truncate_traceback", {"lines": 10})
        ]
        
        current_step_index = 0
        
        while total_estimated > max_budget and current_step_index < len(actions):
            action_name, params = actions[current_step_index]
            current_step_index += 1
            trim_steps.append(f"{action_name}({params})")
            r12_meta["trim"]["degraded"] = True
            
            # Execute Action
            if action_name.startswith("prune_workflow"):
                if "workflow" in error_context:
                    wf = error_context["workflow"]
                    # If wf is string, parse it
                    if isinstance(wf, str):
                        try:
                            wf = json.loads(wf)
                        except:
                            wf = None
                            
                    if wf and isinstance(wf, dict):
                         # Prune
                         prune_conf = PruneConfig(
                             max_depth=params["depth"],
                             max_nodes=params["nodes"]
                         )
                         res = self.pruner.prune(wf, target_node_id, prune_conf)
                         
                         # Update context
                         error_context["workflow"] = res.pruned_workflow_json
                         
                         # Update metadata - enhanced pruning details
                         r12_meta["pruning"] = {
                             "applied": True,
                             "mode": res.mode,
                             "kept_nodes": res.kept_node_ids,
                             "dropped_count": res.dropped_nodes_count,
                             "depth_used": params["depth"],
                             "nodes_limit_used": params["nodes"],
                             "reason": f"Budget exceeded: {total_estimated} > {max_budget}"
                         }
            
            elif action_name == "drop_system_info":
                # Remove system/env info if present
                # Assuming it might be merged into error_context or separate
                keys_to_drop = ["pip_list", "system_env", "env_info"]
                for k in keys_to_drop:
                    if k in error_context:
                        del error_context[k]
                        
            elif action_name == "truncate_traceback":
                if "traceback" in error_context:
                    tb = error_context["traceback"]
                    if isinstance(tb, str):
                        lines = tb.splitlines()
                        if len(lines) > params["lines"] + 5: # +5 for exception msg
                            # Keep start and end
                            new_tb = lines[:2] + ["...[truncated]..."] + lines[-params["lines"]:]
                            error_context["traceback"] = "\n".join(new_tb)
                            
            # Re-estimate with by_section
            current_by_section = estimate_by_section(error_context)
            current_tokens = sum(current_by_section.values())
            total_estimated = current_tokens + overhead_tokens
            
            # Track step history
            step_history.append({
                "step": action_name,
                "tokens": total_estimated,
                "by_section": current_by_section.copy()
            })
            
            # Check hard cap for strict mode
            if config.trimming_policy == "remote_strict" and total_estimated <= config.hard_max_tokens:
                break
                
            # Check soft cap for local mode (stop early logic?)
            # Plan says: local_soft mostly uses soft budget. 
            # If we are here, we are trying to reduce.
        
        # Final update - enhanced
        final_by_section = estimate_by_section(error_context)
        r12_meta["token_budget"]["estimated_tokens_final"] = total_estimated
        r12_meta["token_budget"]["by_section_final"] = final_by_section
        r12_meta["token_budget"]["budget_used_ratio"] = total_estimated / config.hard_max_tokens
        r12_meta["trim"]["steps"] = trim_steps
        r12_meta["trim"]["step_history"] = step_history
        
        # IMPORTANT: Updated error_context back into payload
        current_payload["error_context"] = error_context
        
        return current_payload, r12_meta
