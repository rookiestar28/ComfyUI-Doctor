"""
S9+A10: Provider Registry & Capabilities.

Manages the registration and lookup of provider adapters and their specific capabilities.
Serves as the source of truth for what each provider supports.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from .base import BaseProviderAdapter


@dataclass
class ProviderCapability:
    """Capability contract for a specific provider."""
    supports_submit: bool = False
    requires_auth: bool = False
    max_page_size: int = 100
    concurrency_limit: int = 2  # R19/R20: Default conservative limit
    resume_cursor_type: str = "offset"  # offset | token | timestamp


class ProviderRegistry:
    """
    Singleton registry for all available provider adapters.
    """
    _adapters: Dict[str, BaseProviderAdapter] = {}
    _capabilities: Dict[str, ProviderCapability] = {}

    @classmethod
    def register(
        cls,
        provider_id: str,
        adapter: BaseProviderAdapter,
        capability: ProviderCapability
    ) -> None:
        """Register a provider adapter with its capabilities."""
        if not provider_id:
            raise ValueError("Provider ID cannot be empty")
        
        cls._adapters[provider_id] = adapter
        cls._capabilities[provider_id] = capability

    @classmethod
    def get_adapter(cls, provider_id: str) -> Optional[BaseProviderAdapter]:
        """Get an adapter instance by provider ID."""
        return cls._adapters.get(provider_id)

    @classmethod
    def get_capability(cls, provider_id: str) -> Optional[ProviderCapability]:
        """Get capability metadata by provider ID."""
        return cls._capabilities.get(provider_id)
        
    @classmethod
    def list_providers(cls) -> List[str]:
        """List all registered provider IDs."""
        return list(cls._adapters.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear the registry (useful for testing)."""
        cls._adapters.clear()
        cls._capabilities.clear()
