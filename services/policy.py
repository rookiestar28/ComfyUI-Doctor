"""
S9: Submission Safety Policy Engine.

Evaluates whether an action (read/query vs submit/upload) is allowed based on
provider capabilities, configuration, and confirmation tokens.
Enforces "fail-closed" defaults for all data submission actions.
"""

import logging
from typing import Any, Dict, Optional

from services.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Evaluates whether an action is allowed.
    Enforces strict gates for 'submit' and 'upload' actions.
    """

    @staticmethod
    def evaluate_action(
        provider_id: str,
        action: str,
        has_valid_token: bool = False,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Returns True if action is allowed.
        
        Rules:
        1. Read/Query/Status -> Always Allowed (if provider exists)
        2. Submit/Upload -> Blocked unless:
           - Provider supports it
           - Config explicitly enables it (allow_{provider}_submit=True)
           - Valid confirmation token is present
        """
        capability = ProviderRegistry.get_capability(provider_id)
        if not capability:
            logger.warning(f"Policy check failed: Unknown provider '{provider_id}'")
            return False

        # Safe actions
        if action in ("read", "query", "status", "fetch"):
            return True
            
        # Hazardous actions
        if action in ("submit", "upload"):
            # 1. Capability check
            if not capability.supports_submit:
                logger.warning(f"Policy denied: Provider '{provider_id}' does not support submit/upload")
                return False
                
            # 2. Config allow-list check
            # Default to False (Closed) if config is missing or key not present
            if not config or not config.get(f"allow_{provider_id}_submit", False):
                logger.warning(f"Policy denied: '{provider_id}' submission not enabled in configuration")
                return False

            # 3. Confirmation token check
            if not has_valid_token:
                logger.warning(f"Policy denied: '{provider_id}' submission requires valid confirmation token")
                return False
                
            return True
            
        # Default deny for unknown actions
        logger.warning(f"Policy denied: Unknown action type '{action}'")
        return False
