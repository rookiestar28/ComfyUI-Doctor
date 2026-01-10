"""
Shared rate limiter and concurrency control.

Used by:
- telemetry.py (event tracking)
- session_manager.py (LLM API calls)

R7 Implementation: Rate limiting + concurrency control for LLM API calls.
"""

import asyncio
import threading
import time
from typing import Optional


class RateLimiter:
    """
    Token bucket rate limiter (thread-safe).
    
    Uses time.monotonic() to avoid issues with system clock changes.
    """
    
    def __init__(self, max_per_minute: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_per_minute: Maximum requests allowed per minute.
        """
        self.max_tokens = max_per_minute
        self.tokens = float(max_per_minute)
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()
    
    def allow(self) -> bool:
        """
        Check if request is allowed (consumes one token if yes).
        
        Returns:
            True if request is allowed, False if rate limited.
        """
        with self._lock:
            self._refill()
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        # Refill at rate of max_tokens per 60 seconds
        refill_amount = elapsed * (self.max_tokens / 60.0)
        self.tokens = min(self.max_tokens, self.tokens + refill_amount)
        self.last_refill = now
    
    def get_tokens(self) -> float:
        """Get current token count (for testing/monitoring)."""
        with self._lock:
            self._refill()
            return self.tokens
    
    def reset(self) -> None:
        """Reset to full capacity (for testing)."""
        with self._lock:
            self.tokens = float(self.max_tokens)
            self.last_refill = time.monotonic()


class ConcurrencyLimiter:
    """
    Async semaphore wrapper for concurrent request limiting.
    
    Limits the number of simultaneous LLM requests to prevent
    connection pool exhaustion and provider overload.
    """
    
    def __init__(self, max_concurrent: int = 3):
        """
        Initialize concurrency limiter.
        
        Args:
            max_concurrent: Maximum simultaneous requests allowed.
        """
        self.max_concurrent = max_concurrent
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._lock = threading.Lock()
    
    def _get_semaphore(self) -> asyncio.Semaphore:
        """
        Lazy initialization of semaphore.
        
        Must be called from within an async context/event loop.
        """
        if self._semaphore is None:
            with self._lock:
                if self._semaphore is None:
                    self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore
    
    async def acquire(self) -> bool:
        """
        Acquire semaphore (blocks if at limit).
        
        Returns:
            True when semaphore is acquired.
        """
        await self._get_semaphore().acquire()
        return True
    
    def release(self) -> None:
        """Release semaphore."""
        self._get_semaphore().release()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.release()
        return False
    
    def reset(self) -> None:
        """Reset semaphore (for testing)."""
        with self._lock:
            self._semaphore = None
