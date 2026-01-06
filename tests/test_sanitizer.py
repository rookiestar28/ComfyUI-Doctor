"""
Unit tests for PII Sanitizer module.

Tests all sanitization patterns across different security levels to ensure
sensitive information is properly removed before sending to LLMs.
"""

import pytest
from sanitizer import PIISanitizer, SanitizationLevel, sanitize_for_llm


class TestPIISanitizerBasic:
    """Tests for basic sanitization level."""

    def test_windows_user_path_sanitization(self):
        """Test Windows user path removal."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        test_cases = [
            (
                "Error in C:\\Users\\john_doe\\AppData\\Local\\temp.py",
                "Error in <USER_PATH>\\AppData\\Local\\temp.py"
            ),
            (
                "File not found: C:\\Users\\Alice123\\Documents\\workflow.json",
                "File not found: <USER_PATH>\\Documents\\workflow.json"
            ),
            (
                "Multiple paths: C:\\Users\\Bob\\test.py and C:\\Users\\Alice\\data.txt",
                "Multiple paths: <USER_PATH>\\test.py and <USER_PATH>\\data.txt"
            ),
        ]

        for input_text, expected in test_cases:
            result = sanitizer.sanitize(input_text)
            assert result.sanitized_text == expected
            assert result.pii_found is True
            assert "windows_user_path" in result.replacements

    def test_unix_home_path_sanitization(self):
        """Test Linux/macOS home directory removal."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        test_cases = [
            (
                "Error in /home/john/comfyui/custom_nodes/test.py",
                "Error in <USER_HOME>/comfyui/custom_nodes/test.py"
            ),
            (
                "File: /Users/alice/Documents/workflow.json",
                "File: <USER_HOME>/Documents/workflow.json"
            ),
            (
                "Traceback: /home/bob/.config/app.conf",
                "Traceback: <USER_HOME>/.config/app.conf"
            ),
        ]

        for input_text, expected in test_cases:
            result = sanitizer.sanitize(input_text)
            assert result.sanitized_text == expected
            assert result.pii_found is True
            assert "unix_home_path" in result.replacements

    def test_api_key_sanitization(self):
        """Test API key removal."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        test_cases = [
            (
                "Using key: sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz",
                "Using key: <API_KEY>"
            ),
            (
                "Token: key_1234567890abcdef1234567890abcdef",
                "Token: <API_KEY>"
            ),
            (
                "Auth with token_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "Auth with <API_KEY>"
            ),
            (
                "Hash: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
                "Hash: <API_KEY>"
            ),
        ]

        for input_text, expected in test_cases:
            result = sanitizer.sanitize(input_text)
            assert result.sanitized_text == expected
            assert result.pii_found is True
            assert "api_key" in result.replacements

    def test_email_sanitization(self):
        """Test email address removal."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        test_cases = [
            (
                "Contact: user@example.com for support",
                "Contact: <EMAIL> for support"
            ),
            (
                "Error from john.doe@company.org",
                "Error from <EMAIL>"
            ),
            (
                "Multiple emails: alice@test.com and bob@example.net",
                "Multiple emails: <EMAIL> and <EMAIL>"
            ),
        ]

        for input_text, expected in test_cases:
            result = sanitizer.sanitize(input_text)
            assert result.sanitized_text == expected
            assert result.pii_found is True
            assert "email" in result.replacements

    def test_private_ipv4_sanitization(self):
        """Test private IPv4 address removal."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        test_cases = [
            (
                "Connection to 192.168.1.100 failed",
                "Connection to <PRIVATE_IP> failed"
            ),
            (
                "Server: 10.0.0.5:8080",
                "Server: <PRIVATE_IP>:8080"
            ),
            (
                "Internal IP: 172.16.0.10",
                "Internal IP: <PRIVATE_IP>"
            ),
            (
                "Multiple IPs: 192.168.0.1 and 10.1.1.1",
                "Multiple IPs: <PRIVATE_IP> and <PRIVATE_IP>"
            ),
        ]

        for input_text, expected in test_cases:
            result = sanitizer.sanitize(input_text)
            assert result.sanitized_text == expected
            assert result.pii_found is True
            assert "private_ipv4" in result.replacements

    def test_localhost_sanitization(self):
        """Test localhost variants removal."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        test_cases = [
            (
                "Connecting to 127.0.0.1:8000",
                "Connecting to <LOCALHOST>:8000"
            ),
            (
                "Server at localhost:3000",
                "Server at <LOCALHOST>:3000"
            ),
            (
                "IPv6: ::1 failed",
                "IPv6: <LOCALHOST> failed"
            ),
        ]

        for input_text, expected in test_cases:
            result = sanitizer.sanitize(input_text)
            assert result.sanitized_text == expected
            assert result.pii_found is True
            assert "localhost" in result.replacements

    def test_url_credentials_sanitization(self):
        """Test URL username/password removal."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        test_cases = [
            (
                "Git remote: https://john:secret123@github.com/repo.git",
                "Git remote: https<USER>@github.com/repo.git"
            ),
            (
                "SSH: ssh://alice@server.com/path",
                "SSH: ssh<USER>@server.com/path"
            ),
            (
                "FTP: ftp://user:pass@ftp.example.com/file",
                "FTP: ftp<USER>@ftp.example.com/file"
            ),
        ]

        for input_text, expected in test_cases:
            result = sanitizer.sanitize(input_text)
            assert result.sanitized_text == expected
            assert result.pii_found is True
            assert "url_credentials" in result.replacements

    def test_no_pii_found(self):
        """Test that clean text is not modified."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        clean_texts = [
            "RuntimeError: CUDA out of memory",
            "File not found: model.safetensors",
            "Dimension mismatch at layer 5",
            "Module 'torch' has no attribute 'foo'",
        ]

        for text in clean_texts:
            result = sanitizer.sanitize(text)
            assert result.sanitized_text == text
            assert result.pii_found is False
            assert len(result.replacements) == 0

    def test_sanitization_level_none(self):
        """Test that NONE level does not sanitize anything."""
        sanitizer = PIISanitizer(SanitizationLevel.NONE)

        text_with_pii = "Error in C:\\Users\\john\\test.py with key sk-abc123def456abc123def456abc123def456"
        result = sanitizer.sanitize(text_with_pii)

        assert result.sanitized_text == text_with_pii
        assert result.pii_found is False
        assert len(result.replacements) == 0


class TestPIISanitizerStrict:
    """Tests for strict sanitization level."""

    def test_private_ipv6_sanitization(self):
        """Test private IPv6 address removal (strict mode only)."""
        sanitizer = PIISanitizer(SanitizationLevel.STRICT)

        test_cases = [
            (
                "IPv6: fc00::1 connection failed",
                "IPv6: <PRIVATE_IPV6> connection failed"
            ),
            (
                "Link-local: fe80::a1b2:c3d4:e5f6",
                "Link-local: <PRIVATE_IPV6>"
            ),
        ]

        for input_text, expected in test_cases:
            result = sanitizer.sanitize(input_text)
            assert result.sanitized_text == expected
            assert result.pii_found is True
            assert "private_ipv6" in result.replacements

    def test_ssh_fingerprint_sanitization(self):
        """Test SSH fingerprint removal (strict mode only)."""
        sanitizer = PIISanitizer(SanitizationLevel.STRICT)

        test_cases = [
            (
                "SSH fingerprint: SHA256:aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890ABCD",
                "SSH fingerprint: <SSH_FINGERPRINT>"
            ),
            (
                "SSH fingerprint: SHA256:abcdef0123456789abcdef0123456789",
                "SSH fingerprint: <SSH_FINGERPRINT>"
            ),
            (
                "MD5:a1:b2:c3:d4:e5:f6:a7:b8:c9:d0:e1:f2:a3:b4:c5:d6",
                "MD5<SSH_FINGERPRINT>"
            ),
        ]

        for input_text, expected in test_cases:
            result = sanitizer.sanitize(input_text)
            assert result.sanitized_text == expected
            assert result.pii_found is True
            assert "ssh_fingerprint" in result.replacements


class TestPIISanitizerDict:
    """Tests for dictionary sanitization."""

    def test_sanitize_dict_simple(self):
        """Test sanitizing a simple dictionary."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        data = {
            "error": "File not found at C:\\Users\\john\\test.py",
            "custom_node_path": "/home/alice/comfyui/nodes",
            "node_id": "42",
            "safe_field": "No PII here"
        }

        result = sanitizer.sanitize_dict(data)

        assert result["error"] == "File not found at <USER_PATH>\\test.py"
        assert result["custom_node_path"] == "<USER_HOME>/comfyui/nodes"
        assert result["node_id"] == "42"  # Not sanitized (not in default keys)
        assert result["safe_field"] == "No PII here"

    def test_sanitize_dict_nested(self):
        """Test sanitizing nested dictionaries."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        data = {
            "error": "Error in C:\\Users\\bob\\file.py",
            "context": {
                "path": "/home/charlie/test",
                "message": "Connection to 192.168.1.1 failed"
            }
        }

        result = sanitizer.sanitize_dict(data)

        assert result["error"] == "Error in <USER_PATH>\\file.py"
        assert result["context"]["path"] == "<USER_HOME>/test"
        assert result["context"]["message"] == "Connection to <PRIVATE_IP> failed"

    def test_sanitize_dict_with_list(self):
        """Test sanitizing dictionaries containing lists."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        data = {
            "traceback": [
                "Line 1: C:\\Users\\test\\app.py",
                "Line 2: /home/user/script.py",
                "Line 3: No PII"
            ]
        }

        result = sanitizer.sanitize_dict(data)

        assert result["traceback"][0] == "Line 1: <USER_PATH>\\app.py"
        assert result["traceback"][1] == "Line 2: <USER_HOME>/script.py"
        assert result["traceback"][2] == "Line 3: No PII"


class TestPIISanitizerMetadata:
    """Tests for sanitization metadata and preview."""

    def test_sanitization_result_metadata(self):
        """Test that sanitization result includes correct metadata."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        text = "Error in C:\\Users\\john\\test.py with API key sk-abc123def456abc123def456abc123def456"
        result = sanitizer.sanitize(text)

        assert result.pii_found is True
        assert result.original_length == len(text)
        assert result.sanitized_length < result.original_length
        assert "windows_user_path" in result.replacements
        assert "api_key" in result.replacements
        assert result.replacements["windows_user_path"] == 1
        assert result.replacements["api_key"] == 1

    def test_preview_diff(self):
        """Test preview diff generation."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        text = "Errors: C:\\Users\\alice\\test.py and user@example.com"
        preview = sanitizer.preview_diff(text)

        assert len(preview) == 2

        # Check windows path preview
        path_preview = next(p for p in preview if p["type"] == "windows_user_path")
        assert path_preview["replacement"] == "<USER_PATH>"
        assert len(path_preview["examples"]) > 0
        assert path_preview["total_count"] == 1

        # Check email preview
        email_preview = next(p for p in preview if p["type"] == "email")
        assert email_preview["replacement"] == "<EMAIL>"
        assert "user@example.com" in email_preview["examples"]
        assert email_preview["total_count"] == 1

    def test_to_dict_serialization(self):
        """Test SanitizationResult to_dict conversion."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        text = "Error in C:\\Users\\test\\file.py"
        result = sanitizer.sanitize(text)
        result_dict = result.to_dict()

        assert "pii_found" in result_dict
        assert "replacements" in result_dict
        assert "original_length" in result_dict
        assert "sanitized_length" in result_dict
        assert "reduction_bytes" in result_dict
        assert result_dict["reduction_bytes"] == result.original_length - result.sanitized_length


class TestConvenienceFunction:
    """Tests for the convenience sanitize_for_llm function."""

    def test_sanitize_for_llm_default(self):
        """Test default (basic) sanitization."""
        text = "Error in C:\\Users\\john\\test.py"
        result = sanitize_for_llm(text)

        assert result == "Error in <USER_PATH>\\test.py"

    def test_sanitize_for_llm_levels(self):
        """Test different sanitization levels."""
        text = "Error at C:\\Users\\test\\file.py with key sk-abc123abc123abc123abc123abc123abc123"

        # None level
        result_none = sanitize_for_llm(text, "none")
        assert result_none == text

        # Basic level
        result_basic = sanitize_for_llm(text, "basic")
        assert "<USER_PATH>" in result_basic
        assert "<API_KEY>" in result_basic

        # Strict level
        result_strict = sanitize_for_llm(text, "strict")
        assert "<USER_PATH>" in result_strict
        assert "<API_KEY>" in result_strict

    def test_sanitize_for_llm_invalid_level(self):
        """Test that invalid level defaults to BASIC."""
        text = "Error in C:\\Users\\john\\test.py"
        result = sanitize_for_llm(text, "invalid_level")

        # Should default to BASIC
        assert result == "Error in <USER_PATH>\\test.py"


class TestRealWorldScenarios:
    """Tests with real-world error messages."""

    def test_comfyui_traceback(self):
        """Test sanitizing a typical ComfyUI traceback."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        traceback = """Traceback (most recent call last):
  File "C:\\Users\\john_doe\\ComfyUI\\execution.py", line 152, in recursive_execute
    output_data, output_ui = get_output_data(obj, input_data_all)
  File "/home/alice/ComfyUI/custom_nodes/my_node/loader.py", line 45, in load_model
    raise FileNotFoundError(f"Model not found at {model_path}")
FileNotFoundError: Model not found at C:\\Users\\john_doe\\models\\checkpoint.safetensors
Contact support@example.com for help. Server IP: 192.168.1.100"""

        result = sanitizer.sanitize(traceback)

        # Check all PII is removed
        assert "john_doe" not in result.sanitized_text
        assert "alice" not in result.sanitized_text
        assert "support@example.com" not in result.sanitized_text
        assert "192.168.1.100" not in result.sanitized_text

        # Check placeholders are present
        assert "<USER_PATH>" in result.sanitized_text
        assert "<USER_HOME>" in result.sanitized_text
        assert "<EMAIL>" in result.sanitized_text
        assert "<PRIVATE_IP>" in result.sanitized_text

        # Check structure is preserved
        assert "Traceback (most recent call last):" in result.sanitized_text
        assert "FileNotFoundError" in result.sanitized_text

    def test_api_error_with_credentials(self):
        """Test sanitizing API error with embedded credentials."""
        sanitizer = PIISanitizer(SanitizationLevel.BASIC)

        error = """Failed to connect to API
URL: https://john:password123@api.example.com/v1/generate
API Key: sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
Response: 401 Unauthorized
Please check your credentials or contact admin@company.com"""

        result = sanitizer.sanitize(error)

        assert "john" not in result.sanitized_text
        assert "password123" not in result.sanitized_text
        assert "sk-proj-" not in result.sanitized_text
        assert "admin@company.com" not in result.sanitized_text

        assert "<USER>" in result.sanitized_text
        assert "<API_KEY>" in result.sanitized_text
        assert "<EMAIL>" in result.sanitized_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
