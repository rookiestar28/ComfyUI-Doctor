"""
T15: A10 Adapter Regression Tests.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from services.providers.base import BaseProviderAdapter, ProviderResponse
from services.providers.registry import ProviderRegistry, ProviderCapability

class MockAdapter(BaseProviderAdapter):
    async def health_check(self):
        return True
    
    async def _submit_enrichment_impl(self, payload):
        return await self.execute_with_retry(self._do_work, payload)

    async def _do_work(self, payload):
        if payload.get("fail"):
            raise ValueError("Intentional failure")
        return {"result": "ok"}

def run_async(coro):
    """Helper to run async tests without pytest-asyncio dependency."""
    return asyncio.run(coro)

def test_base_adapter_success():
    adapter = MockAdapter("test", timeout=1.0, max_retries=1)
    
    async def _test():
        mock_func = AsyncMock(return_value={"data": "ok"})
        # The adapter.execute_with_retry wraps result in ProviderResponse if not already
        res = await adapter.execute_with_retry(mock_func)
        assert res.success is True
        assert res.data == {"data": "ok"}
        
    run_async(_test())

def test_base_adapter_timeout():
    adapter = MockAdapter("test", timeout=0.1, max_retries=1)
    
    async def slow():
        await asyncio.sleep(0.5)
        return "too slow"
    
    async def _test():
        res = await adapter.execute_with_retry(slow)
        assert res.success is False
        assert "Timeout" in str(res.error)

    run_async(_test())

def test_base_adapter_retry_logic():
    adapter = MockAdapter("test", timeout=1.0, max_retries=2)
    
    async def _test():
        mock_func = AsyncMock()
        mock_func.side_effect = [ValueError("fail1"), ValueError("fail2"), "success"]
        
        res = await adapter.execute_with_retry(mock_func)
        assert res.success is True
        assert res.data == "success"
        assert mock_func.call_count == 3
        
    run_async(_test())

def test_registry_registration():
    ProviderRegistry.clear()
    adapter = MockAdapter("reg_test")
    cap = ProviderCapability(supports_submit=True)
    
    ProviderRegistry.register("reg_test", adapter, cap)
    
    assert ProviderRegistry.get_adapter("reg_test") is adapter
    assert ProviderRegistry.get_capability("reg_test") is cap
    assert "reg_test" in ProviderRegistry.list_providers()
