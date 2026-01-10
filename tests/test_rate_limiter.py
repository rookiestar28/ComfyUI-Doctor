"""
Tests for rate_limiter module.

R7 Implementation: Rate limiting + concurrency control for LLM API calls.
"""

import unittest
import asyncio
import time
import threading
import sys
import os

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rate_limiter import RateLimiter, ConcurrencyLimiter


class TestRateLimiter(unittest.TestCase):
    """Tests for RateLimiter token bucket implementation."""
    
    def test_allow_within_limit(self):
        """Should allow requests within limit."""
        limiter = RateLimiter(max_per_minute=10)
        
        # Should allow 10 requests
        for i in range(10):
            self.assertTrue(limiter.allow(), f"Request {i+1} should be allowed")
    
    def test_block_over_limit(self):
        """Should block requests over limit."""
        limiter = RateLimiter(max_per_minute=5)
        
        # Use up all tokens
        for _ in range(5):
            self.assertTrue(limiter.allow())
        
        # Next request should be blocked
        self.assertFalse(limiter.allow())
    
    def test_refill_over_time(self):
        """Should refill tokens over time."""
        limiter = RateLimiter(max_per_minute=60)  # 1 token per second
        
        # Use up all tokens
        for _ in range(60):
            limiter.allow()
        
        # Should be blocked immediately
        self.assertFalse(limiter.allow())
        
        # Wait for refill (1 second = 1 token at 60/min)
        time.sleep(1.1)
        
        # Should be allowed now
        self.assertTrue(limiter.allow())
    
    def test_get_tokens(self):
        """Should return current token count."""
        limiter = RateLimiter(max_per_minute=10)
        
        self.assertAlmostEqual(limiter.get_tokens(), 10.0, delta=0.1)
        
        limiter.allow()
        self.assertAlmostEqual(limiter.get_tokens(), 9.0, delta=0.1)
    
    def test_reset(self):
        """Should reset to full capacity."""
        limiter = RateLimiter(max_per_minute=10)
        
        # Use some tokens
        for _ in range(5):
            limiter.allow()
        
        self.assertLess(limiter.get_tokens(), 10)
        
        # Reset
        limiter.reset()
        self.assertAlmostEqual(limiter.get_tokens(), 10.0, delta=0.1)
    
    def test_thread_safety(self):
        """Should be thread-safe."""
        limiter = RateLimiter(max_per_minute=100)
        results = []
        
        def try_request():
            results.append(limiter.allow())
        
        threads = [threading.Thread(target=try_request) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Exactly 100 should be allowed
        self.assertEqual(sum(results), 100)
    
    def test_monotonic_clock(self):
        """Should use monotonic clock (not wall clock)."""
        limiter = RateLimiter(max_per_minute=60)
        
        # This test just ensures the code runs without error
        # Actual monotonic clock behavior is internal
        initial_tokens = limiter.get_tokens()
        self.assertGreater(initial_tokens, 0)


class TestConcurrencyLimiter(unittest.TestCase):
    """Tests for ConcurrencyLimiter semaphore implementation."""
    
    def test_max_concurrent_enforced(self):
        """Should enforce max concurrent limit."""
        async def run_test():
            limiter = ConcurrencyLimiter(max_concurrent=2)
            active_count = 0
            max_observed = 0
            lock = asyncio.Lock()
            
            async def task():
                nonlocal active_count, max_observed
                async with limiter:
                    async with lock:
                        active_count += 1
                        max_observed = max(max_observed, active_count)
                    await asyncio.sleep(0.1)
                    async with lock:
                        active_count -= 1
            
            # Run 5 tasks concurrently
            await asyncio.gather(*[task() for _ in range(5)])
            
            # Max observed should never exceed 2
            self.assertLessEqual(max_observed, 2)
        
        asyncio.run(run_test())
    
    def test_acquire_release(self):
        """Should properly acquire and release."""
        async def run_test():
            limiter = ConcurrencyLimiter(max_concurrent=1)
            
            await limiter.acquire()
            # Now semaphore should be at 0
            
            limiter.release()
            # Should be back to 1
            
            # Should be able to acquire again
            result = await asyncio.wait_for(limiter.acquire(), timeout=1.0)
            self.assertTrue(result)
            limiter.release()
        
        asyncio.run(run_test())
    
    def test_context_manager(self):
        """Should work as async context manager."""
        async def run_test():
            limiter = ConcurrencyLimiter(max_concurrent=1)
            
            async with limiter:
                # Inside context
                pass
            
            # After context, should be released
            async with limiter:
                pass  # Should not block
        
        asyncio.run(run_test())
    
    def test_reset(self):
        """Should reset semaphore."""
        async def run_test():
            limiter = ConcurrencyLimiter(max_concurrent=1)
            
            # Use the semaphore
            async with limiter:
                pass
            
            # Reset
            limiter.reset()
            
            # Should work again
            async with limiter:
                pass
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main(verbosity=2)
