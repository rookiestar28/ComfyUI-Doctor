"""
PII Sanitization Module for ComfyUI-Doctor.

Removes sensitive information (file paths, API keys, emails, IP addresses) from
error messages before sending to LLM services. Critical for enterprise adoption
and GDPR compliance.

Security Level:
- none: No sanitization (default for local LLMs)
- basic: Remove user paths and obvious API keys
- strict: Remove all PII including emails, IPs, and usernames
"""

import re
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class SanitizationLevel(Enum):
    """Sanitization security levels."""
    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"


@dataclass
class SanitizationResult:
    """Result of sanitization operation with metadata."""
    sanitized_text: str
    pii_found: bool
    replacements: Dict[str, int]  # Type -> count
    original_length: int
    sanitized_length: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/preview."""
        return {
            "pii_found": self.pii_found,
            "replacements": self.replacements,
            "original_length": self.original_length,
            "sanitized_length": self.sanitized_length,
            "reduction_bytes": self.original_length - self.sanitized_length
        }


class PIISanitizer:
    """
    Sanitizes personally identifiable information from error tracebacks.

    Removes:
    - Windows user paths: C:\\Users\\username\\... → <USER_PATH>\\...
    - Linux/macOS home dirs: /home/username/ → <USER_HOME>/...
    - API keys: sk-abc123... → <API_KEY>
    - Email addresses: user@example.com → <EMAIL>
    - Private IP addresses: 192.168.1.1 → <PRIVATE_IP>
    - Usernames in paths and URLs

    Zero runtime overhead when level=NONE, GDPR-friendly.
    """

    # Regex patterns for different PII types
    PATTERNS = {
        # Windows user paths (C:\Users\username\...)
        "windows_user_path": (
            r'[A-Z]:\\Users\\[^\\\/\s]+',
            r'<USER_PATH>'
        ),

        # Linux/macOS home directories (/home/username/ or /Users/username/)
        "unix_home_path": (
            r'/(?:home|Users)/[^/\s]+',
            r'<USER_HOME>'
        ),

        # API keys (common patterns: sk-..., key_..., token_...)
        "api_key": (
            r'\b(?:sk-[a-zA-Z0-9_-]{20,}|key_[a-zA-Z0-9]{20,}|token_[a-zA-Z0-9]{20,}|[a-f0-9]{32,64})\b',
            r'<API_KEY>'
        ),

        # Username in URLs (http://username:password@host or ssh://username@host)
        # IMPORTANT: Must come BEFORE email pattern to avoid email sanitizer matching password@domain
        "url_credentials": (
            r'://[^:@\s]+(?::[^@\s]+)?@',
            r'<USER>@'
        ),

        # Email addresses
        "email": (
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'<EMAIL>'
        ),

        # Private IPv4 addresses (10.x.x.x, 172.16-31.x.x, 192.168.x.x)
        "private_ipv4": (
            r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b',
            r'<PRIVATE_IP>'
        ),

        # Localhost variants
        "localhost": (
            r'\b(?:127\.0\.0\.1|localhost)\b|(?<![0-9a-f])::1(?![0-9a-f:])',
            r'<LOCALHOST>'
        ),
    }

    # Strict mode additional patterns
    STRICT_PATTERNS = {
        # Generic username patterns in file paths (conservative)
        "generic_username": (
            r'\\(?:Users|home)\\([A-Za-z][A-Za-z0-9_-]{2,20})\\',
            r'\\Users\\<USER>\\'
        ),

        # IPv6 private addresses (fc00::/7, fe80::/10)
        "private_ipv6": (
            r'(?:fc00|fe80):[0-9a-f:]+(?:/\d{1,3})?',
            r'<PRIVATE_IPV6>'
        ),

        # SSH keys fingerprints
        "ssh_fingerprint": (
            r'SHA256:[A-Za-z0-9+/=]{32,}|:(?:[0-9a-f]{2}:){15}[0-9a-f]{2}',
            r'<SSH_FINGERPRINT>'
        ),
    }

    def __init__(self, level: SanitizationLevel = SanitizationLevel.BASIC):
        """
        Initialize sanitizer with specified security level.

        Args:
            level: Sanitization level (NONE, BASIC, STRICT)
        """
        self.level = level
        self._compiled_patterns = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile all regex patterns for performance."""
        if self.level == SanitizationLevel.NONE:
            return

        # Compile basic patterns
        for name, (pattern, _) in self.PATTERNS.items():
            self._compiled_patterns[name] = re.compile(pattern, re.IGNORECASE)

        # Compile strict patterns if needed
        if self.level == SanitizationLevel.STRICT:
            for name, (pattern, _) in self.STRICT_PATTERNS.items():
                self._compiled_patterns[name] = re.compile(pattern, re.IGNORECASE)

    def sanitize(self, text: str) -> SanitizationResult:
        """
        Sanitize text by removing PII.

        Args:
            text: Input text (error message, traceback, etc.)

        Returns:
            SanitizationResult with sanitized text and metadata
        """
        if self.level == SanitizationLevel.NONE or not text:
            return SanitizationResult(
                sanitized_text=text,
                pii_found=False,
                replacements={},
                original_length=len(text) if text else 0,
                sanitized_length=len(text) if text else 0
            )

        sanitized = text
        replacements = {}

        # Apply basic patterns
        for name, (pattern, replacement) in self.PATTERNS.items():
            compiled = self._compiled_patterns.get(name)
            if compiled:
                matches = compiled.findall(sanitized)
                if matches:
                    replacements[name] = len(matches)
                    sanitized = compiled.sub(replacement, sanitized)

        # Apply strict patterns
        if self.level == SanitizationLevel.STRICT:
            for name, (pattern, replacement) in self.STRICT_PATTERNS.items():
                compiled = self._compiled_patterns.get(name)
                if compiled:
                    matches = compiled.findall(sanitized)
                    if matches:
                        replacements[name] = len(matches)
                        sanitized = compiled.sub(replacement, sanitized)

        return SanitizationResult(
            sanitized_text=sanitized,
            pii_found=bool(replacements),
            replacements=replacements,
            original_length=len(text),
            sanitized_length=len(sanitized)
        )

    def sanitize_dict(self, data: Dict[str, Any], keys_to_sanitize: list = None) -> Dict[str, Any]:
        """
        Recursively sanitize string values in a dictionary.

        Args:
            data: Dictionary to sanitize
            keys_to_sanitize: List of keys to sanitize (None = all string values)

        Returns:
            New dictionary with sanitized values
        """
        if self.level == SanitizationLevel.NONE:
            return data

        if keys_to_sanitize is None:
            keys_to_sanitize = ["error", "traceback", "message", "path", "custom_node_path"]

        sanitized_data = {}
        for key, value in data.items():
            if isinstance(value, str) and (not keys_to_sanitize or key in keys_to_sanitize):
                result = self.sanitize(value)
                sanitized_data[key] = result.sanitized_text
            elif isinstance(value, dict):
                sanitized_data[key] = self.sanitize_dict(value, keys_to_sanitize)
            elif isinstance(value, list):
                sanitized_data[key] = [
                    self.sanitize_dict(item, keys_to_sanitize) if isinstance(item, dict)
                    else self.sanitize(item).sanitized_text if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                sanitized_data[key] = value

        return sanitized_data

    def preview_diff(self, text: str, max_examples: int = 5) -> list:
        """
        Generate a preview of what will be sanitized (for frontend display).

        Args:
            text: Input text to analyze
            max_examples: Maximum number of examples per type

        Returns:
            List of dicts with {type, original, replacement, count}
        """
        if self.level == SanitizationLevel.NONE or not text:
            return []

        preview = []
        all_patterns = dict(self.PATTERNS)
        if self.level == SanitizationLevel.STRICT:
            all_patterns.update(self.STRICT_PATTERNS)

        for name, (pattern, replacement) in all_patterns.items():
            compiled = self._compiled_patterns.get(name)
            if compiled:
                matches = compiled.findall(text)
                if matches:
                    # Get unique matches
                    unique_matches = list(set(matches))[:max_examples]
                    preview.append({
                        "type": name,
                        "replacement": replacement,
                        "examples": unique_matches,
                        "total_count": len(matches)
                    })

        return preview


# Global sanitizer instance (initialized on first use)
_global_sanitizer: Optional[PIISanitizer] = None


def get_sanitizer(level: SanitizationLevel = SanitizationLevel.BASIC) -> PIISanitizer:
    """
    Get or create the global sanitizer instance.

    Args:
        level: Desired sanitization level

    Returns:
        PIISanitizer instance
    """
    global _global_sanitizer
    if _global_sanitizer is None or _global_sanitizer.level != level:
        _global_sanitizer = PIISanitizer(level)
    return _global_sanitizer


def sanitize_for_llm(text: str, level: str = "basic") -> str:
    """
    Convenience function to sanitize text for LLM transmission.

    Args:
        text: Text to sanitize
        level: Sanitization level ("none", "basic", "strict")

    Returns:
        Sanitized text
    """
    try:
        sanitization_level = SanitizationLevel(level)
    except ValueError:
        sanitization_level = SanitizationLevel.BASIC

    sanitizer = get_sanitizer(sanitization_level)
    result = sanitizer.sanitize(text)
    return result.sanitized_text
