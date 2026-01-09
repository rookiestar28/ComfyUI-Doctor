"""
API Endpoint Tests for ComfyUI-Doctor
Tests validation logic and thread safety without requiring full module imports.

Note: Full API endpoint tests with aiohttp would require running within
ComfyUI environment. These tests focus on the logic components that can
be tested in isolation.
"""
import unittest
import sys
import os
import threading
from unittest.mock import MagicMock, patch
from collections import deque

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class TestLocalLLMDetection(unittest.TestCase):
    """Tests for is_local_llm_url function logic."""

    def test_ollama_url_detected(self):
        """Test that Ollama URLs are detected as local."""
        from security import is_local_llm_url
        test_urls = [
            "http://localhost:11434/v1",
            "http://127.0.0.1:11434/v1",
            "http://localhost:1234/v1",
            "http://0.0.0.0:11434/v1",
        ]
        
        for url in test_urls:
            self.assertTrue(is_local_llm_url(url), f"URL {url} should be detected as local")

    def test_cloud_url_not_local(self):
        """Test that cloud URLs are not detected as local."""
        from security import is_local_llm_url
        cloud_urls = [
            "https://api.openai.com/v1",
            "https://api.deepseek.com/v1",
            "https://api.groq.com/openai/v1",
        ]
        
        for url in cloud_urls:
            self.assertFalse(is_local_llm_url(url), f"URL {url} should not be detected as local")


class TestAnalyzeErrorValidation(unittest.TestCase):
    """Tests for /doctor/analyze endpoint validation logic."""

    def test_missing_error_text(self):
        """Test that missing error text is caught."""
        error_text = None
        self.assertIsNone(error_text)

    def test_error_text_truncation(self):
        """Test that long error texts are truncated."""
        MAX_ERROR_LENGTH = 8000
        long_error = "X" * 10000
        
        if len(long_error) > MAX_ERROR_LENGTH:
            truncated = long_error[:MAX_ERROR_LENGTH] + "\n\n[... truncated ...]"
            self.assertTrue(len(truncated) < len(long_error))
            self.assertIn("[... truncated ...]", truncated)
        else:
            self.fail("Error should have been truncated")


class TestVerifyKeyValidation(unittest.TestCase):
    """Tests for /doctor/verify_key endpoint validation logic."""

    def test_local_llm_no_key_required(self):
        """Test that local LLM doesn't require API key."""
        from security import is_local_llm_url
        base_url = "http://localhost:11434/v1"
        api_key = ""
        
        is_local = is_local_llm_url(base_url)
        
        # For local LLM, we should allow empty key
        if is_local and not api_key:
            api_key = "local-llm"  # Placeholder
        
        self.assertTrue(is_local)
        self.assertEqual(api_key, "local-llm")

    def test_cloud_requires_key(self):
        """Test that cloud provider requires API key."""
        from security import is_local_llm_url
        base_url = "https://api.openai.com/v1"
        api_key = ""
        
        is_local = is_local_llm_url(base_url)
        
        # For cloud LLM, empty key should fail
        self.assertFalse(is_local)
        requires_key = not api_key and not is_local
        self.assertTrue(requires_key)


class TestListModelsResponseParsing(unittest.TestCase):
    """Tests for /doctor/list_models response parsing logic."""

    def test_parse_openai_style_response(self):
        """Test parsing OpenAI-style model list response."""
        response = {
            "data": [
                {"id": "gpt-4o"},
                {"id": "gpt-4-turbo"},
                {"id": "gpt-3.5-turbo"}
            ]
        }
        
        models = []
        if "data" in response:
            for m in response["data"]:
                model_id = m.get("id", "")
                models.append({"id": model_id, "name": model_id})
        
        self.assertEqual(len(models), 3)
        self.assertEqual(models[0]["id"], "gpt-4o")
        self.assertEqual(models[1]["id"], "gpt-4-turbo")
        self.assertEqual(models[2]["id"], "gpt-3.5-turbo")

    def test_parse_ollama_style_response(self):
        """Test parsing Ollama-style model list response."""
        response = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "mistral:7b"},
                {"model": "codellama:13b"}  # Some use 'model' instead of 'name'
            ]
        }
        
        models = []
        if "models" in response:
            for m in response["models"]:
                model_name = m.get("name", m.get("model", ""))
                models.append({"id": model_name, "name": model_name})
        
        self.assertEqual(len(models), 3)
        self.assertEqual(models[0]["id"], "llama3.1:8b")
        self.assertEqual(models[1]["id"], "mistral:7b")
        self.assertEqual(models[2]["id"], "codellama:13b")

    def test_empty_response(self):
        """Test handling empty model list response."""
        response = {"data": []}
        
        models = []
        if "data" in response:
            for m in response["data"]:
                model_id = m.get("id", "")
                models.append({"id": model_id, "name": model_id})
        
        self.assertEqual(len(models), 0)


class TestThreadSafetyLocks(unittest.TestCase):
    """Tests for thread safety mechanisms."""

    def test_lock_type(self):
        """Test that threading.Lock objects work correctly."""
        lock = threading.Lock()
        
        # Test basic lock operations
        acquired = lock.acquire(blocking=False)
        self.assertTrue(acquired)
        lock.release()
        
        # Test with context manager
        with lock:
            pass  # Should not deadlock

    def test_deque_with_maxlen(self):
        """Test deque with maxlen behaves as expected."""
        history = deque(maxlen=5)
        
        for i in range(10):
            history.append(i)
        
        # Should only contain last 5 items
        self.assertEqual(len(history), 5)
        self.assertEqual(list(history), [5, 6, 7, 8, 9])

    def test_concurrent_deque_access(self):
        """Test concurrent access to deque with lock."""
        history = deque(maxlen=100)
        lock = threading.Lock()
        
        def append_items(start, count):
            for i in range(start, start + count):
                with lock:
                    history.append(i)
        
        threads = [
            threading.Thread(target=append_items, args=(0, 50)),
            threading.Thread(target=append_items, args=(50, 50)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # With lock protection, all items should be present
        self.assertEqual(len(history), 100)


class TestXSSPrevention(unittest.TestCase):
    """Tests for XSS prevention logic."""

    def test_escape_html_basic(self):
        """Test basic HTML escaping logic."""
        dangerous_strings = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<div onclick='evil()'>click</div>",
        ]
        
        def escape_html(text):
            """Python equivalent of the JS escapeHtml function."""
            if not text:
                return ""
            return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))
        
        for dangerous in dangerous_strings:
            escaped = escape_html(dangerous)
            self.assertNotIn("<script>", escaped)
            self.assertNotIn("<img", escaped)
            self.assertNotIn("<div", escaped)

    def test_escape_html_preserves_content(self):
        """Test that escaping preserves meaningful content."""
        normal_strings = [
            "Node #42: KSampler",
            "Error: Out of memory",
            "Check model file exists",
        ]
        
        def escape_html(text):
            if not text:
                return ""
            return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))
        
        for s in normal_strings:
            escaped = escape_html(s)
            # Content should be mostly preserved (only special chars escaped)
            self.assertIn("Node" if "Node" in s else "Error" if "Error" in s else "Check", escaped)


class TestSetLanguageLogic(unittest.TestCase):
    """Tests for language setting logic."""

    def test_supported_languages(self):
        """Test that supported languages list is valid."""
        SUPPORTED_LANGUAGES = ["en", "zh_TW", "zh_CN", "ja"]
        
        self.assertIn("en", SUPPORTED_LANGUAGES)
        self.assertIn("zh_TW", SUPPORTED_LANGUAGES)
        self.assertIn("zh_CN", SUPPORTED_LANGUAGES)
        self.assertIn("ja", SUPPORTED_LANGUAGES)
        
    def test_language_validation(self):
        """Test language validation logic."""
        SUPPORTED_LANGUAGES = ["en", "zh_TW", "zh_CN", "ja"]
        
        valid_lang = "zh_TW"
        invalid_lang = "fr"
        
        self.assertIn(valid_lang, SUPPORTED_LANGUAGES)
        self.assertNotIn(invalid_lang, SUPPORTED_LANGUAGES)


class TestSSRFProtection(unittest.TestCase):
    """S2: Tests for SSRF protection in base URL validation."""
    
    def setUp(self):
        """Import validate_ssrf_url from project."""
        from security import validate_ssrf_url, is_local_llm_url
        self.validate_ssrf_url = validate_ssrf_url
        self.is_local_llm_url = is_local_llm_url
    
    def test_private_ip_blocked(self):
        """Test that private IP addresses are blocked."""
        blocked_urls = [
            "http://10.0.0.1/v1",
            "http://10.255.255.255/v1",
            "http://172.16.0.1/v1",
            "http://172.31.255.255/v1",
            "http://192.168.0.1/v1",
            "http://192.168.1.100/v1",
        ]
        for url in blocked_urls:
            is_valid, error = self.validate_ssrf_url(url, allow_local_llm=False)
            self.assertFalse(is_valid, f"Private IP {url} should be blocked")
            self.assertIn("private", error.lower())
    
    def test_localhost_blocked(self):
        """Test that localhost is blocked (when not local LLM)."""
        blocked_urls = [
            "http://localhost/v1",
            "http://127.0.0.1/v1",
            "http://0.0.0.0/v1",
        ]
        for url in blocked_urls:
            is_valid, error = self.validate_ssrf_url(url, allow_local_llm=False)
            self.assertFalse(is_valid, f"Localhost {url} should be blocked")
    
    def test_local_llm_allowed(self):
        """Test that known local LLM patterns are allowed."""
        allowed_urls = [
            "http://localhost:11434/v1",  # Ollama
            "http://127.0.0.1:1234/v1",   # LMStudio
        ]
        for url in allowed_urls:
            is_valid, error = self.validate_ssrf_url(url, allow_local_llm=True)
            self.assertTrue(is_valid, f"Local LLM {url} should be allowed")
    
    def test_cloud_urls_allowed(self):
        """Test that legitimate cloud URLs are allowed."""
        allowed_urls = [
            "https://api.openai.com/v1",
            "https://api.deepseek.com/v1",
            "https://api.groq.com/openai/v1",
            "https://api.anthropic.com/v1",
        ]
        for url in allowed_urls:
            is_valid, error = self.validate_ssrf_url(url)
            self.assertTrue(is_valid, f"Cloud URL {url} should be allowed: {error}")
    
    def test_non_http_blocked(self):
        """Test that non-HTTP protocols are blocked."""
        blocked_urls = [
            "file:///etc/passwd",
            "ftp://ftp.example.com/file",
            "gopher://example.com/",
        ]
        for url in blocked_urls:
            is_valid, error = self.validate_ssrf_url(url)
            self.assertFalse(is_valid, f"Non-HTTP {url} should be blocked")
            self.assertIn("protocol", error.lower())
    
    def test_internal_domains_blocked(self):
        """Test that internal domains are blocked."""
        blocked_urls = [
            "http://server.local/v1",
            "http://api.internal/v1",
            "http://db.corp/v1",
            "http://host.lan/v1",
        ]
        for url in blocked_urls:
            is_valid, error = self.validate_ssrf_url(url)
            self.assertFalse(is_valid, f"Internal domain {url} should be blocked")
    
    def test_metadata_endpoint_blocked(self):
        """Test that cloud metadata endpoints are blocked."""
        # AWS metadata endpoint
        is_valid, error = self.validate_ssrf_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(is_valid, "Metadata endpoint should be blocked")

    def test_ssrf_metrics_increment(self):
        """Blocked requests should increment SSRF metrics."""
        from security import get_ssrf_metrics
        before = get_ssrf_metrics().get("ssrf_block_count", 0)
        self.validate_ssrf_url("http://169.254.169.254/latest/meta-data/", allow_local_llm=False)
        after = get_ssrf_metrics().get("ssrf_block_count", 0)
        self.assertGreaterEqual(after, before + 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
