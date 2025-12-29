"""
Session Manager for ComfyUI-Doctor.

Manages a reusable aiohttp ClientSession for LLM API calls to reduce
resource overhead and prevent "Unclosed client session" warnings.
"""

import asyncio
import aiohttp
import atexit
from typing import Optional


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
    
    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """Get or create the async lock (must be created in event loop)."""
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock
    
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
