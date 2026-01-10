"""
Session Manager for ComfyUI-Doctor.

Manages a reusable aiohttp ClientSession for LLM API calls to reduce
resource overhead and prevent "Unclosed client session" warnings.

R7 Enhancement: Adds rate limiting and concurrency control for LLM requests.
"""

import asyncio
import aiohttp
import atexit
from typing import Optional

from rate_limiter import RateLimiter, ConcurrencyLimiter


class SessionManager:
    """
    Manages a shared aiohttp ClientSession for LLM API calls.
    
    Benefits:
    - Connection reuse (HTTP keep-alive)
    - Reduced resource overhead
    - Proper cleanup on shutdown
    
    Usage:
        session = await SessionManager.get_session()
        async with session.get(url) as response:
            ...
    """
    _session: Optional[aiohttp.ClientSession] = None
    _lock: Optional[asyncio.Lock] = None
    _closed: bool = False
    
    # Default timeout for LLM API calls
    DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=60)
    
    # R7: Rate limiters (shared across all requests)
    _core_limiter: Optional[RateLimiter] = None       # analyze, chat
    _light_limiter: Optional[RateLimiter] = None      # verify_key, list_models
    _concurrency: Optional[ConcurrencyLimiter] = None # max concurrent LLM calls
    
    # R7: Default limits (configurable via CONFIG)
    DEFAULT_CORE_RATE = 30    # req/min for heavy endpoints
    DEFAULT_LIGHT_RATE = 10   # req/min for light endpoints
    DEFAULT_CONCURRENCY = 3   # simultaneous LLM requests

    @classmethod
    def configure_limits(
        cls,
        *,
        core_rate_limit: Optional[int] = None,
        light_rate_limit: Optional[int] = None,
        max_concurrent: Optional[int] = None,
    ) -> None:
        """
        Configure rate/concurrency limits (typically from config).

        This resets cached limiter instances so new values take effect.
        """
        def _coerce_positive_int(value: Optional[int], default: int) -> int:
            if value is None:
                return default
            try:
                coerced = int(value)
            except (TypeError, ValueError):
                return default
            return coerced if coerced > 0 else default

        cls.DEFAULT_CORE_RATE = _coerce_positive_int(core_rate_limit, cls.DEFAULT_CORE_RATE)
        cls.DEFAULT_LIGHT_RATE = _coerce_positive_int(light_rate_limit, cls.DEFAULT_LIGHT_RATE)
        cls.DEFAULT_CONCURRENCY = _coerce_positive_int(max_concurrent, cls.DEFAULT_CONCURRENCY)

        cls._core_limiter = None
        cls._light_limiter = None
        cls._concurrency = None
    
    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """Get or create the async lock (must be created in event loop)."""
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock
    
    @classmethod
    def get_core_limiter(cls) -> RateLimiter:
        """
        Get rate limiter for heavy LLM endpoints (analyze, chat).
        
        Returns:
            RateLimiter: Shared rate limiter instance (30 req/min default).
        """
        if cls._core_limiter is None:
            cls._core_limiter = RateLimiter(max_per_minute=cls.DEFAULT_CORE_RATE)
        return cls._core_limiter
    
    @classmethod
    def get_light_limiter(cls) -> RateLimiter:
        """
        Get rate limiter for light endpoints (verify_key, list_models).
        
        Returns:
            RateLimiter: Shared rate limiter instance (10 req/min default).
        """
        if cls._light_limiter is None:
            cls._light_limiter = RateLimiter(max_per_minute=cls.DEFAULT_LIGHT_RATE)
        return cls._light_limiter
    
    @classmethod
    def get_concurrency_limiter(cls) -> ConcurrencyLimiter:
        """
        Get concurrency limiter for LLM requests.
        
        Returns:
            ConcurrencyLimiter: Shared semaphore (3 concurrent default).
        """
        if cls._concurrency is None:
            cls._concurrency = ConcurrencyLimiter(max_concurrent=cls.DEFAULT_CONCURRENCY)
        return cls._concurrency
    
    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """
        Get or create a shared aiohttp ClientSession.
        
        Returns:
            aiohttp.ClientSession: The shared session instance.
            
        Note:
            This method is thread-safe and will create the session
            on first call. The session uses a default 60-second timeout.
        """
        async with cls._get_lock():
            if cls._session is None or cls._session.closed:
                cls._closed = False
                cls._session = aiohttp.ClientSession(
                    timeout=cls.DEFAULT_TIMEOUT,
                    # Trust environment for proxy settings
                    trust_env=True
                )
            return cls._session
    
    @classmethod
    async def close(cls) -> None:
        """
        Close the shared session.
        
        This should be called during application shutdown to ensure
        proper cleanup. Safe to call multiple times.
        """
        async with cls._get_lock():
            if cls._session is not None and not cls._session.closed:
                await cls._session.close()
                cls._session = None
                cls._closed = True
    
    @classmethod
    def is_closed(cls) -> bool:
        """Check if the session has been explicitly closed."""
        return cls._closed
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset the manager state (for testing purposes).
        
        Warning: This does not close the session - call close() first.
        """
        cls._session = None
        cls._lock = None
        cls._closed = False
        cls._core_limiter = None
        cls._light_limiter = None
        cls._concurrency = None


def _sync_close_session():
    """
    Synchronous wrapper for session cleanup at interpreter shutdown.
    
    Called by atexit to ensure session is closed when Python exits.
    """
    if SessionManager._session is not None and not SessionManager._session.closed:
        try:
            # Try to get or create an event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run the close coroutine
            if loop.is_running():
                # If loop is running, schedule the close
                loop.create_task(SessionManager.close())
            else:
                loop.run_until_complete(SessionManager.close())
        except Exception:
            # At shutdown, errors are expected - just try to close directly
            try:
                if SessionManager._session is not None:
                    # Force close the connector
                    if SessionManager._session.connector is not None:
                        SessionManager._session.connector.close()
            except Exception:
                pass


# Register cleanup at interpreter exit
atexit.register(_sync_close_session)
