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
from collections.abc import Mapping
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


SENSITIVE_HEADER_NAMES = frozenset({"authorization", "x-api-key"})
SENSITIVE_HEADER_REDACTION = "***"

_QUOTED_SENSITIVE_HEADER_PATTERN = re.compile(
    r"""(?P<prefix>(?P<key_quote>["'])(?:authorization|x-api-key)(?P=key_quote)\s*:\s*)"""
    r"""(?P<value_quote>["'])(?P<value>(?:\\.|[^\\\r\n])*?)(?P=value_quote)""",
    re.IGNORECASE,
)
_UNQUOTED_SENSITIVE_HEADER_PATTERN = re.compile(
    r"""(?P<prefix>(?<![\w"'])\b(?:authorization|x-api-key)\b\s*[:=]\s*)"""
    r"""(?P<value>[^\r\n|,}\]]+)""",
    re.IGNORECASE | re.MULTILINE,
)


def is_sensitive_header_name(name: Any) -> bool:
    """Return whether a mapping key is an unconditional sensitive header."""
    return (
        isinstance(name, str)
        and name.strip().casefold() in SENSITIVE_HEADER_NAMES
    )


def _redact_sensitive_header_text(text: str) -> tuple[str, int]:
    """Redact serialized/header-line values and return replacement count."""
    if not text:
        return text, 0

    replacement_count = 0

    def replace_quoted(match: re.Match) -> str:
        nonlocal replacement_count
        replacement_count += 1
        quote = match.group("value_quote")
        return (
            f"{match.group('prefix')}{quote}"
            f"{SENSITIVE_HEADER_REDACTION}{quote}"
        )

    def replace_unquoted(match: re.Match) -> str:
        nonlocal replacement_count
        replacement_count += 1
        raw_value = match.group("value").strip()
        if (
            len(raw_value) >= 2
            and raw_value[0] in {'"', "'"}
            and raw_value[-1] == raw_value[0]
        ):
            redacted = (
                f"{raw_value[0]}{SENSITIVE_HEADER_REDACTION}"
                f"{raw_value[0]}"
            )
        else:
            redacted = SENSITIVE_HEADER_REDACTION
        return f"{match.group('prefix')}{redacted}"

    redacted = _QUOTED_SENSITIVE_HEADER_PATTERN.sub(
        replace_quoted,
        text,
    )
    redacted = _UNQUOTED_SENSITIVE_HEADER_PATTERN.sub(
        replace_unquoted,
        redacted,
    )
    return redacted, replacement_count


def redact_sensitive_headers(value: Any) -> Any:
    """Recursively apply only the unconditional sensitive-header boundary."""
    if isinstance(value, str):
        return _redact_sensitive_header_text(value)[0]

    if isinstance(value, Mapping):
        return {
            key: (
                SENSITIVE_HEADER_REDACTION
                if is_sensitive_header_name(key)
                else redact_sensitive_headers(item)
            )
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [redact_sensitive_headers(item) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_sensitive_headers(item) for item in value)

    return value


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

    Generic PII patterns are skipped when level=NONE. Sensitive header-name
    redaction remains mandatory at every level.
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
            r'\b(?:sk-[a-zA-Z0-9_-]{20,}|key_[a-zA-Z0-9]{20,}|token_[a-zA-Z0-9]{20,})\b',
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

        # Long hex tokens (privacy-first; avoid false positives in BASIC)
        "api_key_hex": (
            r'\b(?<!SHA256:)[a-f0-9]{32,64}\b',
            r'<API_KEY>'
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
        if not text:
            return SanitizationResult(
                sanitized_text=text,
                pii_found=False,
                replacements={},
                original_length=len(text) if text else 0,
                sanitized_length=len(text) if text else 0
            )

        # CRITICAL: sensitive header-name redaction is unconditional and must
        # stay ahead of token-shape patterns and privacy-level early returns.
        sanitized, header_replacements = _redact_sensitive_header_text(text)
        replacements = {}
        if header_replacements:
            replacements["sensitive_header"] = header_replacements

        if self.level == SanitizationLevel.NONE:
            return SanitizationResult(
                sanitized_text=sanitized,
                pii_found=bool(replacements),
                replacements=replacements,
                original_length=len(text),
                sanitized_length=len(sanitized),
            )

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
        if keys_to_sanitize is None:
            keys_to_sanitize = []

        sanitized_data = {}
        for key, value in data.items():
            if is_sensitive_header_name(key):
                sanitized_data[key] = SENSITIVE_HEADER_REDACTION
            elif isinstance(value, str):
                if not keys_to_sanitize or key in keys_to_sanitize:
                    sanitized_data[key] = self.sanitize(value).sanitized_text
                else:
                    sanitized_data[key] = redact_sensitive_headers(value)
            elif isinstance(value, dict):
                sanitized_data[key] = self.sanitize_dict(value, keys_to_sanitize)
            elif isinstance(value, list):
                sanitized_data[key] = self._sanitize_list(
                    value,
                    keys_to_sanitize,
                )
            else:
                sanitized_data[key] = value

        return sanitized_data

    def _sanitize_list(
        self,
        values: list,
        keys_to_sanitize: list,
    ) -> list:
        """Recursively sanitize list content while preserving its shape."""
        sanitized_values = []
        for item in values:
            if isinstance(item, dict):
                sanitized_values.append(
                    self.sanitize_dict(item, keys_to_sanitize)
                )
            elif isinstance(item, list):
                sanitized_values.append(
                    self._sanitize_list(item, keys_to_sanitize)
                )
            elif isinstance(item, str):
                sanitized_values.append(self.sanitize(item).sanitized_text)
            else:
                sanitized_values.append(item)
        return sanitized_values

    def preview_diff(self, text: str, max_examples: int = 5) -> list:
        """
        Generate a preview of what will be sanitized (for frontend display).

        Args:
            text: Input text to analyze
            max_examples: Maximum number of examples per type

        Returns:
            List of dicts with {type, original, replacement, count}
        """
        if not text:
            return []

        preview = []
        header_safe_text, header_count = _redact_sensitive_header_text(text)
        if header_count:
            preview.append({
                "type": "sensitive_header",
                "replacement": SENSITIVE_HEADER_REDACTION,
                "examples": [],
                "total_count": header_count,
            })

        if self.level == SanitizationLevel.NONE:
            return preview

        all_patterns = dict(self.PATTERNS)
        if self.level == SanitizationLevel.STRICT:
            all_patterns.update(self.STRICT_PATTERNS)

        for name, (pattern, replacement) in all_patterns.items():
            compiled = self._compiled_patterns.get(name)
            if compiled:
                matches = compiled.findall(header_safe_text)
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
