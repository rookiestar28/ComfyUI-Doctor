"""
S9+A10: Base Provider Adapter Contract.

Defines the abstract base class and normalized response schema for all external
enrichment providers. Enforces consistent error handling, timeouts, and retries.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProviderResponse:
    """Normalized response envelope for all provider interactions."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)  # usage, latency, etc.


class BaseProviderAdapter(ABC):
    """
    Abstract base class for all external service providers.
    Enforces consistent timeout, retry, and response structure.
    """

    def __init__(
        self,
        provider_id: str,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        self.provider_id = provider_id
        default_timeout = 30.0
        default_retries = 2
        try:
            # CRITICAL: keep this import local to avoid module import coupling at startup.
            from config import CONFIG  # pylint: disable=import-outside-toplevel
            default_timeout = float(getattr(CONFIG.guardrails, "PROVIDER_TIMEOUT_SECONDS", 30))
            default_retries = int(getattr(CONFIG.guardrails, "PROVIDER_MAX_RETRIES", 2))
        except Exception:
            pass

        resolved_timeout = default_timeout if timeout is None else float(timeout)
        resolved_retries = default_retries if max_retries is None else int(max_retries)
        self.timeout = resolved_timeout if resolved_timeout > 0 else default_timeout
        self.max_retries = resolved_retries if resolved_retries >= 0 else default_retries

    async def execute_with_retry(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Executes an async function with centralized retry/timeout logic.
        Captures exceptions and returns a standardized ProviderResponse.
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                should_retry = False
                # Simple exponential backoff
                if attempt > 0:
                    delay = 0.5 * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

                # Execute with timeout
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.timeout
                )
                
                # If result is already a ProviderResponse, return it directly
                if isinstance(result, ProviderResponse):
                    return result
                
                # Otherwise wrap it
                return ProviderResponse(success=True, data=result)

            except asyncio.TimeoutError:
                last_error = f"Timeout after {self.timeout}s"
                logger.warning(f"[{self.provider_id}] Attempt {attempt+1}/{self.max_retries+1} timed out")
                should_retry = True
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[{self.provider_id}] Attempt {attempt+1}/{self.max_retries+1} failed: {e}")
                should_retry = True
            
            if not should_retry:
                break

        return ProviderResponse(
            success=False,
            error=last_error or "Operation failed after retries"
        )

    @abstractmethod
    async def health_check(self) -> bool:
        """Quick connectivity check."""
        pass

    @abstractmethod
    async def _submit_enrichment_impl(self, payload: Dict[str, Any]) -> ProviderResponse:
        """
        Internal implementation of submission logic.
        Subclasses must implement this.
        """
        pass

    async def submit_enrichment(self, payload: Dict[str, Any]) -> ProviderResponse:
        """
        Public facade for enrichment submission.
        Enforces outbound PII sanitization before delegating to implementation.
        """
        try:
            # Import here to avoid circular dependencies if any (though outbound depends on sanitizer/security)
            from config import CONFIG
            from outbound import get_outbound_sanitizer, sanitize_outbound_payload
            
            # S6/S9: Enforce outbound sanitization
            # We assume provider base_url is known or check per-provider? 
            # For now, we use a generic placeholder URL or check registry if needed.
            # Privacy mode comes from CONFIG.
            sanitizer, _ = get_outbound_sanitizer("https://generic-provider", CONFIG.privacy_mode)
            clean_payload = sanitize_outbound_payload(payload, sanitizer)
            
            return await self._submit_enrichment_impl(clean_payload)
        except Exception as e:
            logger.error(f"Submission sanitization failed: {e}")
            return ProviderResponse(success=False, error=f"Pre-submission check failed: {e}")

    @staticmethod
    def clean_llm_output(text: str) -> str:
        """
        R19: Strip hidden reasoning (<think>...</think>) and normalize output.
        """
        import re
        # Remove <think>...</think> (dotall to match newlines)
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # Remove standalone markers if any remain
        cleaned = cleaned.replace('<think>', '').replace('</think>', '')
        return cleaned.strip()

