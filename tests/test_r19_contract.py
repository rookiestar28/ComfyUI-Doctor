
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from services.providers.base import BaseProviderAdapter, ProviderResponse
from services.providers.registry import ProviderRegistry, ProviderCapability
print(f"DEBUG: BaseProviderAdapter abstract methods: {BaseProviderAdapter.__abstractmethods__}")


# 1. Mock adapter inheriting from BaseProviderAdapter
class MockR19Adapter(BaseProviderAdapter):
    async def execute(self, action: str, params: dict) -> ProviderResponse:
        # Simulate various responses
        if action == "query":
            raw_content = params.get("mock_content", "")
            # R19: Enforce cleaning in the adapter implementation
            cleaned_content = self.clean_llm_output(raw_content)
            
            return ProviderResponse(
                success=True,
                data={"content": cleaned_content},
                meta={"usage": 100}
            )
        elif action == "fallible":
             raise RuntimeError("Simulated failure")
        return ProviderResponse(success=False, error="Unknown action")

    async def health_check(self) -> bool:
        return True

    async def _submit_enrichment_impl(self, payload: dict) -> ProviderResponse:
        # Internal implementation receives already-sanitized payload
        return await self.execute("submit", payload)

# 2. Test Fixtures
@pytest.fixture
def adapter():
    return MockR19Adapter(provider_id="mock_r19")

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.fixture
def mock_registry():
    ProviderRegistry._adapters.clear()
    ProviderRegistry._capabilities.clear()
    yield ProviderRegistry
    ProviderRegistry._adapters.clear()
    ProviderRegistry._capabilities.clear()

# 3. R19 Regression Tests
@pytest.mark.anyio
async def test_r19_output_contract_normalization(adapter):
    """
    R19: Ensure output is normalized to ProviderResponse.
    """
    # Happy path
    response = await adapter.execute_with_retry(adapter.execute, "query", {"mock_content": "Valid output"})
    assert response.success is True
    assert response.data["content"] == "Valid output"
    assert "usage" in response.meta

@pytest.mark.anyio
async def test_r19_truncation_simulated(adapter):
    """
    R19: Verify large keys/values don't crash adapter (shim for truncation).
    Real truncation happens in outbound funnel, but adapter must handle large payloads.
    """
    large_input = "A" * 100000
    response = await adapter.execute_with_retry(adapter.execute, "query", {"mock_content": large_input})
    assert response.success is True
    assert len(response.data["content"]) == 100000
    # Note: Full truncation downstream is covered by outbound tests, 
    # here we ensure adapter doesn't choke on large data.

@pytest.mark.anyio
async def test_r19_error_fallback(adapter):
    """
    R19: Ensure exceptions are caught and wrapped in ProviderResponse(success=False).
    """
    response = await adapter.execute_with_retry(adapter.execute, "fallible", {})
    assert response.success is False
    assert "Simulated failure" in response.error

@pytest.mark.anyio
async def test_r19_hidden_marker_stripping(adapter):
    """
    R19: Check if markers/thinking tags are STRIPPED from output (not preserved).
    Roadmap R19 requires stripping hidden reasoning blocks before render/store.
    """
    thinking_content = "<think>Wait...</think>Result"
    response = await adapter.execute_with_retry(adapter.execute, "query", {"mock_content": thinking_content})
    assert response.success is True
    assert "<think>" not in response.data["content"]
    assert "</think>" not in response.data["content"]
    assert response.data["content"] == "Result"

@pytest.mark.anyio
async def test_r19_malformed_json_resilience(adapter):

    """
    R19: Ensure malformed JSON in provider response (simulated) is handled gracefully.
    """
    # For a base adapter, we handle the error string. 
    # Specific providers would parse JSON, but base catches the exception.
    with patch.object(MockR19Adapter, 'execute', side_effect=ValueError("Expecting value: line 1 column 1 (char 0)")):
        response = await adapter.execute_with_retry(adapter.execute, "query", {})
        assert response.success is False
        assert "Expecting value" in response.error
