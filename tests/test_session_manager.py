"""
Tests for SessionManager - aiohttp session reuse.
"""
import unittest
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from session_manager import SessionManager


class TestSessionManagerLifecycle(unittest.TestCase):
    """Tests for SessionManager lifecycle management."""
    
    def setUp(self):
        """Reset SessionManager state before each test."""
        SessionManager.reset()
    
    def tearDown(self):
        """Clean up after each test."""
        async def cleanup():
            await SessionManager.close()
        try:
            asyncio.run(cleanup())
        except Exception:
            pass
        SessionManager.reset()
    
    def test_get_session_creates_session(self):
        """Test that get_session creates a session on first call."""
        async def run_test():
            session = await SessionManager.get_session()
            self.assertIsNotNone(session)
            self.assertFalse(session.closed)
        
        asyncio.run(run_test())
    
    def test_get_session_returns_same_instance(self):
        """Test that multiple calls return the same session."""
        async def run_test():
            session1 = await SessionManager.get_session()
            session2 = await SessionManager.get_session()
            self.assertIs(session1, session2)
        
        asyncio.run(run_test())
    
    def test_close_closes_session(self):
        """Test that close properly closes the session."""
        async def run_test():
            session = await SessionManager.get_session()
            self.assertFalse(session.closed)
            await SessionManager.close()
            self.assertTrue(SessionManager.is_closed())
        
        asyncio.run(run_test())
    
    def test_get_session_after_close_creates_new(self):
        """Test that getting session after close creates a new one."""
        async def run_test():
            session1 = await SessionManager.get_session()
            session1_id = id(session1)
            await SessionManager.close()
            session2 = await SessionManager.get_session()
            # After close and re-get, should be a new session
            self.assertNotEqual(session1_id, id(session2))
            self.assertFalse(session2.closed)
        
        asyncio.run(run_test())
    
    def test_multiple_close_is_safe(self):
        """Test that calling close multiple times is safe."""
        async def run_test():
            await SessionManager.get_session()
            await SessionManager.close()
            await SessionManager.close()  # Should not raise
            await SessionManager.close()  # Should not raise
        
        asyncio.run(run_test())
    
    def test_reset_clears_state(self):
        """Test that reset clears all state."""
        async def run_test():
            await SessionManager.get_session()
            await SessionManager.close()
            SessionManager.reset()
            self.assertIsNone(SessionManager._session)
            self.assertIsNone(SessionManager._lock)
            self.assertFalse(SessionManager._closed)
        
        asyncio.run(run_test())


class TestSessionManagerTimeout(unittest.TestCase):
    """Tests for SessionManager timeout configuration."""
    
    def test_default_timeout_is_60_seconds(self):
        """Test that default timeout is 60 seconds."""
        self.assertEqual(SessionManager.DEFAULT_TIMEOUT.total, 60)


class TestSessionManagerProxyPolicy(unittest.TestCase):
    """Tests for S13 outbound proxy trust boundary policy."""

    def setUp(self):
        SessionManager.reset()

    def tearDown(self):
        async def cleanup():
            await SessionManager.close()
        try:
            asyncio.run(cleanup())
        except Exception:
            pass
        SessionManager.reset()

    def test_default_policy_is_strict_off(self):
        diagnostics = SessionManager.get_proxy_diagnostics()
        self.assertEqual(diagnostics["policy"], "strict_off")
        self.assertFalse(diagnostics["trust_env"])

    def test_config_policy_can_opt_in_inherit_env(self):
        SessionManager.configure_proxy_policy(config_policy="inherit_env")
        diagnostics = SessionManager.get_proxy_diagnostics()
        self.assertEqual(diagnostics["policy"], "inherit_env")
        self.assertTrue(diagnostics["trust_env"])
        self.assertEqual(diagnostics["source"], "config")

    def test_env_policy_overrides_config(self):
        SessionManager.configure_proxy_policy(
            config_policy="strict_off",
            env_policy="inherit_env",
        )
        diagnostics = SessionManager.get_proxy_diagnostics()
        self.assertEqual(diagnostics["policy"], "inherit_env")
        self.assertTrue(diagnostics["trust_env"])
        self.assertEqual(diagnostics["source"], "env")

    def test_invalid_policy_falls_back_to_strict_off(self):
        SessionManager.configure_proxy_policy(config_policy="invalid-policy")
        diagnostics = SessionManager.get_proxy_diagnostics()
        self.assertEqual(diagnostics["policy"], "strict_off")
        self.assertFalse(diagnostics["trust_env"])
        self.assertEqual(diagnostics["source"], "config_invalid_fallback")

    def test_client_session_uses_effective_trust_env_flag(self):
        async def run_test():
            fake_session = MagicMock()
            fake_session.closed = False
            fake_session.close = AsyncMock()
            with patch("session_manager.aiohttp.ClientSession", return_value=fake_session) as mock_cs:
                SessionManager.configure_proxy_policy(config_policy="strict_off")
                await SessionManager.get_session()
                self.assertFalse(mock_cs.call_args.kwargs["trust_env"])

                await SessionManager.close()
                SessionManager.configure_proxy_policy(config_policy="inherit_env")
                await SessionManager.get_session()
                self.assertTrue(mock_cs.call_args.kwargs["trust_env"])

        asyncio.run(run_test())


class TestSessionManagerLimits(unittest.TestCase):
    """Tests for SessionManager limiter wiring."""

    def setUp(self):
        SessionManager.reset()

    def tearDown(self):
        SessionManager.reset()

    def test_configure_limits_applies_rate_window(self):
        SessionManager.configure_limits(
            core_rate_limit=30,
            light_rate_limit=10,
            max_concurrent=3,
            rate_window_seconds=120,
        )
        core = SessionManager.get_core_limiter()
        light = SessionManager.get_light_limiter()
        self.assertEqual(core.window_seconds, 120)
        self.assertEqual(light.window_seconds, 120)


class TestSessionManagerThreadSafety(unittest.TestCase):
    """Tests for SessionManager thread safety."""
    
    def setUp(self):
        SessionManager.reset()
    
    def tearDown(self):
        async def cleanup():
            await SessionManager.close()
        try:
            asyncio.run(cleanup())
        except Exception:
            pass
        SessionManager.reset()
    
    def test_concurrent_get_session(self):
        """Test that concurrent get_session calls are safe."""
        async def run_test():
            # Create multiple concurrent get_session calls
            tasks = [SessionManager.get_session() for _ in range(10)]
            sessions = await asyncio.gather(*tasks)
            
            # All should return the same session
            first_session = sessions[0]
            for session in sessions:
                self.assertIs(session, first_session)
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main(verbosity=2)
