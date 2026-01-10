"""
R12 Service: Token Estimator.
Provides token estimation using tiktoken (if available) or character-based fallback.
Supports provider-specific payload analysis.
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal, Union

# Try to import tiktoken, but don't fail if missing
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None
    TIKTOKEN_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class TokenEstimate:
    """Result of a token estimation."""
    estimated_tokens: int
    method: Literal["tiktoken", "fallback"]
    multiplier_applied: float
    chars: int
    tokens_per_char: float

@dataclass
class EstimatorConfig:
    """Configuration for the token estimator."""
    mode: str = "tiktoken_preferred"  #tiktoken_preferred, fallback_only
    fallback_chars_per_token: float = 4.0
    safety_multiplier: float = 1.15
    default_model: str = "gpt-4"

class TokenEstimator:
    """
    Estimates tokens for text strings and LLM payloads.
    """

    def __init__(self, config: Optional[EstimatorConfig] = None):
        self.config = config or EstimatorConfig()
        self._encoding_cache = {}

    def _get_encoding(self, model_name: str):
        """Get or cache tiktoken encoding for a model."""
        if not TIKTOKEN_AVAILABLE or self.config.mode == "fallback_only":
            return None
        
        # Normalize model name for common aliases
        model_name = model_name.lower()
        if model_name.startswith("gpt-4"):
            encoding_name = "cl100k_base"
        elif model_name.startswith("gpt-3.5"):
            encoding_name = "cl100k_base" 
        else:
            # Default to cl100k_base for modern models if unknown
            # or try to get by model name
            try:
                return tiktoken.encoding_for_model(model_name)
            except (KeyError, ValueError):
                encoding_name = "cl100k_base"

        if encoding_name not in self._encoding_cache:
            try:
                self._encoding_cache[encoding_name] = tiktoken.get_encoding(encoding_name)
            except Exception as e:
                logger.warning(f"Failed to get tiktoken encoding {encoding_name}: {e}")
                return None
        
        return self._encoding_cache.get(encoding_name)

    def estimate(self, text: str, model_name: Optional[str] = None) -> TokenEstimate:
        """
        Estimate tokens for a single string.
        """
        if not text:
            return TokenEstimate(0, "fallback", 1.0, 0, 0.0)

        model = model_name or self.config.default_model
        encoding = self._get_encoding(model)
        
        if encoding:
            # Tiktoken exact count
            try:
                # We still apply a small safety multiplier even for tiktoken 
                # because simple text encoding ignores message structure overhead
                tokens = len(encoding.encode(text))
                # Base structural overhead is handled in section estimation, 
                # but we add a tiny buffer for safety if using raw text
                params = TokenEstimate(
                    estimated_tokens=tokens,
                    method="tiktoken",
                    multiplier_applied=1.0, # Exact count doesn't strictly need multiplier, but budget logic might add one. 
                                          # Here we return raw count.
                    chars=len(text),
                    tokens_per_char=len(text)/tokens if tokens > 0 else 0
                )
                return params
            except Exception as e:
                logger.warning(f"Tiktoken encoding failed: {e}, using fallback")

        # Fallback estimation
        chars = len(text)
        raw_estimate = chars / self.config.fallback_chars_per_token
        safe_estimate = math.ceil(raw_estimate * self.config.safety_multiplier)
        
        return TokenEstimate(
            estimated_tokens=safe_estimate,
            method="fallback",
            multiplier_applied=self.config.safety_multiplier,
            chars=chars,
            tokens_per_char=self.config.fallback_chars_per_token
        )

    def estimate_section_map(self, sections: Dict[str, str], model_name: Optional[str] = None) -> Dict[str, TokenEstimate]:
        """
        Estimate tokens for a map of sections (e.g., {'traceback': '...', 'workflow': '...'}).
        """
        results = {}
        for key, text in sections.items():
            results[key] = self.estimate(text, model_name)
        return results
