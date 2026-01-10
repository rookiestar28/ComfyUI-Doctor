"""
Tests for llm_client module.

R6 Implementation: Network retry logic with exponential backoff.
"""

import unittest
import asyncio
import time
import sys
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from llm_client import (
    RetryConfig,
    RetryResult,
    llm_request_with_retry,
    llm_post_with_retry,
    _calculate_backoff,
    _safe_release,
)


class MockResponse:
    """Mock aiohttp.ClientResponse."""
    
    def __init__(self, status: int, headers: dict = None, text: str = ""):
        self.status = status
        self.headers = headers or {}
        self._text = text
        self._closed = False
    
    async def text(self):
        return self._text
    
    async def json(self):
        import json
        return json.loads(self._text)
    
    def close(self):
        self._closed = True
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        self.close()


class TestRetryConfig(unittest.TestCase):
    """Tests for RetryConfig dataclass."""
    
    def test_default_values(self):
        """Should have sensible defaults."""
        config = RetryConfig()
        
        self.assertEqual(config.max_retries, 2)
        self.assertEqual(config.base_delay, 1.0)
        self.assertEqual(config.max_delay, 30.0)
        self.assertEqual(config.request_timeout_seconds, 60.0)
        self.assertEqual(config.total_timeout_seconds, 180.0)
        self.assertTrue(config.add_idempotency_key)
        self.assertEqual(config.idempotency_header, "Idempotency-Key")
    
    def test_custom_values(self):
        """Should accept custom values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            retry_on_5xx=True,
        )
        
        self.assertEqual(config.max_retries, 5)
        self.assertEqual(config.base_delay, 0.5)
        self.assertTrue(config.retry_on_5xx)


class TestCalculateBackoff(unittest.TestCase):
    """Tests for exponential backoff calculation."""
    
    def test_exponential_increase(self):
        """Should increase exponentially."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0)
        
        delay1 = _calculate_backoff(1, config)
        delay2 = _calculate_backoff(2, config)
        delay3 = _calculate_backoff(3, config)
        
        # Account for jitter (±10%)
        self.assertGreater(delay1, 0.9)
        self.assertLess(delay1, 1.2)
        
        self.assertGreater(delay2, 1.8)
        self.assertLess(delay2, 2.4)
        
        self.assertGreater(delay3, 3.6)
        self.assertLess(delay3, 4.8)
    
    def test_respects_max_delay(self):
        """Should not exceed max_delay."""
        config = RetryConfig(base_delay=10.0, max_delay=15.0, exponential_base=2.0)
        
        delay = _calculate_backoff(5, config)  # Would be 10 * 2^4 = 160
        
        self.assertLessEqual(delay, 15.0)


class TestSafeRelease(unittest.TestCase):
    """Tests for response resource cleanup."""
    
    def test_closes_response(self):
        """Should close response."""
        response = MockResponse(200)
        _safe_release(response)
        
        self.assertTrue(response._closed)
    
    def test_handles_exception(self):
        """Should not raise on error."""
        response = Mock()
        response.close.side_effect = Exception("close error")
        
        # Should not raise
        _safe_release(response)


class TestLLMRequestWithRetry(unittest.TestCase):
    """Tests for llm_request_with_retry function."""
    
    def test_success_no_retry(self):
        """Should return immediately on success."""
        async def run_test():
            session = Mock()
            response = MockResponse(200, text='{"result": "ok"}')
            session.request = AsyncMock(return_value=response)
            
            result = await llm_request_with_retry(
                session, "POST", "http://example.com/api",
                config=RetryConfig(add_idempotency_key=False)
            )
            
            self.assertTrue(result.success)
            self.assertEqual(result.attempts, 1)
            self.assertEqual(result.response.status, 200)
        
        asyncio.run(run_test())
    
    def test_retry_on_timeout(self):
        """Should retry on timeout."""
        async def run_test():
            session = Mock()
            
            # First call times out, second succeeds
            call_count = 0
            async def mock_request(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise asyncio.TimeoutError()
                return MockResponse(200)
            
            session.request = mock_request
            
            config = RetryConfig(
                max_retries=2,
                base_delay=0.01,
                add_idempotency_key=False
            )
            result = await llm_request_with_retry(
                session, "POST", "http://example.com/api",
                config=config
            )
            
            self.assertTrue(result.success)
            self.assertEqual(result.attempts, 2)
        
        asyncio.run(run_test())
    
    def test_no_retry_on_4xx(self):
        """Should not retry on 4xx errors (except 429)."""
        async def run_test():
            session = Mock()
            response = MockResponse(400, text='{"error": "bad request"}')
            session.request = AsyncMock(return_value=response)
            
            config = RetryConfig(max_retries=3, add_idempotency_key=False)
            result = await llm_request_with_retry(
                session, "POST", "http://example.com/api",
                config=config
            )
            
            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 1)  # No retries
        
        asyncio.run(run_test())
    
    def test_retry_on_429(self):
        """Should retry on 429 with Retry-After."""
        async def run_test():
            session = Mock()
            
            call_count = 0
            async def mock_request(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return MockResponse(429, headers={"Retry-After": "0.01"})
                return MockResponse(200)
            
            session.request = mock_request
            
            config = RetryConfig(
                max_retries=2,
                base_delay=0.01,
                retry_on_429=True,
                add_idempotency_key=False
            )
            result = await llm_request_with_retry(
                session, "POST", "http://example.com/api",
                config=config
            )
            
            self.assertTrue(result.success)
            self.assertEqual(result.attempts, 2)
        
        asyncio.run(run_test())
    
    def test_limited_5xx_retry(self):
        """Should retry 5xx only once when enabled."""
        async def run_test():
            session = Mock()
            
            call_count = 0
            async def mock_request(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:  # Fail twice
                    return MockResponse(503)
                return MockResponse(200)
            
            session.request = mock_request
            
            config = RetryConfig(
                max_retries=3,
                max_5xx_retries=1,  # Only 1 retry for 5xx
                retry_on_5xx=True,
                base_delay=0.01,
                add_idempotency_key=False
            )
            result = await llm_request_with_retry(
                session, "POST", "http://example.com/api",
                config=config
            )
            
            # Should fail because max_5xx_retries=1
            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 2)  # Initial + 1 retry
        
        asyncio.run(run_test())
    
    def test_idempotency_key_added(self):
        """Should add Idempotency-Key header on POST."""
        async def run_test():
            session = Mock()
            response = MockResponse(200)
            session.request = AsyncMock(return_value=response)
            
            config = RetryConfig(add_idempotency_key=True)
            result = await llm_request_with_retry(
                session, "POST", "http://example.com/api",
                config=config
            )
            
            # Check that Idempotency-Key was passed in headers
            call_args = session.request.call_args
            headers = call_args.kwargs.get("headers", {})
            self.assertIn("Idempotency-Key", headers)
            self.assertIsNotNone(result.idempotency_key)
        
        asyncio.run(run_test())
    
    def test_total_timeout_respected(self):
        """Should stop after total timeout budget."""
        async def run_test():
            session = Mock()
            
            async def slow_request(*args, **kwargs):
                await asyncio.sleep(0.5)
                raise asyncio.TimeoutError()
            
            session.request = slow_request
            
            config = RetryConfig(
                max_retries=10,
                base_delay=0.01,
                total_timeout_seconds=0.3,
                add_idempotency_key=False
            )
            
            start = time.monotonic()
            result = await llm_request_with_retry(
                session, "POST", "http://example.com/api",
                config=config
            )
            elapsed = time.monotonic() - start
            
            self.assertFalse(result.success)
            self.assertIn("timeout", result.error.lower())
            self.assertLess(elapsed, 1.0)  # Should not take long
        
        asyncio.run(run_test())
    
    def test_allows_redirects_false(self):
        """Should always use allow_redirects=False (SSRF protection)."""
        async def run_test():
            session = Mock()
            response = MockResponse(200)
            session.request = AsyncMock(return_value=response)
            
            await llm_request_with_retry(
                session, "POST", "http://example.com/api",
                config=RetryConfig(add_idempotency_key=False)
            )
            
            call_args = session.request.call_args
            self.assertFalse(call_args.kwargs.get("allow_redirects", True))
        
        asyncio.run(run_test())


class TestLLMPostWithRetry(unittest.TestCase):
    """Tests for convenience llm_post_with_retry function."""
    
    def test_uses_post_method(self):
        """Should use POST method."""
        async def run_test():
            session = Mock()
            response = MockResponse(200)
            session.request = AsyncMock(return_value=response)
            
            await llm_post_with_retry(
                session, "http://example.com/api",
                config=RetryConfig(add_idempotency_key=False)
            )
            
            call_args = session.request.call_args
            self.assertEqual(call_args.args[0], "POST")
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main(verbosity=2)
