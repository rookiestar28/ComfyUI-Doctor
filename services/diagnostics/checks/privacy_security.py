"""
F14 Proactive Diagnostics - Privacy & Security Check

Analyzes privacy and security configuration to detect:
1. privacy_mode=none with remote provider configured → warning/critical
2. API key missing for remote provider → warning
3. Local LLM without explicit privacy_mode → info
"""

import logging
import os
from typing import Dict, Any, List, Optional

from ..models import (
    HealthIssue,
    HealthCheckRequest,
    IssueCategory,
    IssueSeverity,
    IssueTarget,
)
from . import register_check

logger = logging.getLogger("comfyui-doctor.diagnostics.checks.privacy_security")


# ============================================================================
# Configuration
# ============================================================================

# Known remote provider patterns (non-local)
REMOTE_PROVIDER_PATTERNS = {
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.groq.com",
    "api.together.xyz",
    "api.mistral.ai",
    "api.deepseek.com",
    "openrouter.ai",
}

# Known local LLM hosts
LOCAL_LLM_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
LOCAL_LLM_PORTS = {11434, 1234}  # Ollama, LMStudio default ports

# Environment variable names for API keys
API_KEY_ENV_VARS = {
    "OPENAI_API_KEY": "OpenAI",
    "ANTHROPIC_API_KEY": "Anthropic",
    "GOOGLE_API_KEY": "Google",
    "GROQ_API_KEY": "Groq",
    "TOGETHER_API_KEY": "Together",
    "MISTRAL_API_KEY": "Mistral",
    "DEEPSEEK_API_KEY": "DeepSeek",
}


# ============================================================================
# Cached Settings Info
# ============================================================================

_settings_cache: Optional[Dict[str, Any]] = None


def _get_settings_info() -> Dict[str, Any]:
    """Get cached settings information from environment/config."""
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache

    info: Dict[str, Any] = {
        "privacy_mode": "basic",  # default
        "base_url": None,
        "is_local_provider": False,
        "is_remote_provider": False,
        "provider_name": None,
        "api_keys_present": {},
    }

    # Check for API keys in environment
    for env_var, provider_name in API_KEY_ENV_VARS.items():
        key_value = os.environ.get(env_var, "")
        info["api_keys_present"][provider_name] = bool(key_value and key_value.strip())

    _settings_cache = info
    return info


def _clear_settings_cache():
    """Clear settings cache (for testing)."""
    global _settings_cache
    _settings_cache = None


def _detect_provider_type(base_url: str) -> Dict[str, Any]:
    """Detect if the provider is local or remote based on URL."""
    result = {
        "is_local": False,
        "is_remote": False,
        "provider_name": None,
    }

    if not base_url:
        return result

    base_url_lower = base_url.lower()

    # Check for remote providers
    for pattern in REMOTE_PROVIDER_PATTERNS:
        if pattern in base_url_lower:
            result["is_remote"] = True
            result["provider_name"] = pattern.split(".")[1] if "." in pattern else pattern
            return result

    # Check for local LLM patterns
    try:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        hostname = (parsed.hostname or "").lower()
        port = parsed.port

        if hostname in LOCAL_LLM_HOSTS:
            result["is_local"] = True
            if port == 11434:
                result["provider_name"] = "Ollama"
            elif port == 1234:
                result["provider_name"] = "LMStudio"
            else:
                result["provider_name"] = "Local LLM"
            return result
    except Exception:
        pass

    # Unknown provider
    return result


# ============================================================================
# Check Implementation
# ============================================================================

@register_check("privacy_security")
async def check_privacy_security(
    workflow: Dict[str, Any],
    request: HealthCheckRequest,
) -> List[HealthIssue]:
    """
    Check privacy and security configuration for issues.

    Returns list of HealthIssues for detected problems.
    """
    issues: List[HealthIssue] = []

    # Extract settings from workflow metadata if available
    metadata = workflow.get("extra", {}).get("doctor_metadata", {})
    privacy_mode = metadata.get("privacy_mode", "basic")
    base_url = metadata.get("base_url", "")

    # Detect provider type
    provider_info = _detect_provider_type(base_url)

    # Check 1: privacy_mode=none with remote provider
    if privacy_mode == "none" and provider_info["is_remote"]:
        issues.append(_create_privacy_none_remote_issue(
            provider_info["provider_name"] or "remote provider",
            base_url
        ))

    # Check 2: privacy_mode=none with unknown provider (potential risk)
    if privacy_mode == "none" and not provider_info["is_local"] and not provider_info["is_remote"] and base_url:
        issues.append(_create_privacy_none_unknown_issue(base_url))

    # Check 3: Remote provider without API key configured
    environment_info = _get_settings_info()
    for provider_name, has_key in environment_info["api_keys_present"].items():
        # Only warn if the provider is actively being used
        if provider_info.get("provider_name", "").lower() == provider_name.lower():
            if not has_key:
                issues.append(_create_missing_api_key_issue(provider_name))

    # Check 4: Local provider with privacy_mode=none (info - this is OK but user should be aware)
    if privacy_mode == "none" and provider_info["is_local"]:
        issues.append(_create_local_privacy_none_info(
            provider_info["provider_name"] or "Local LLM"
        ))

    return issues


def _create_privacy_none_remote_issue(provider_name: str, base_url: str) -> HealthIssue:
    """Create issue for privacy_mode=none with remote provider."""
    target = IssueTarget(setting="privacy_mode")
    return HealthIssue(
        issue_id=HealthIssue.generate_issue_id("privacy_none_remote", target, provider_name),
        category=IssueCategory.PRIVACY,
        severity=IssueSeverity.CRITICAL,
        title="Privacy Mode Disabled with Remote Provider",
        summary=f"privacy_mode=none is configured but using remote provider ({provider_name})",
        evidence=[
            f"Current privacy_mode: none",
            f"Provider: {provider_name}",
            "Data will be sent to remote servers without sanitization",
        ],
        recommendation=[
            "Change privacy_mode to 'basic' or 'strict' for remote providers",
            "privacy_mode=none should only be used with local LLMs",
            "Review what data is being sent to the AI provider",
        ],
        target=target,
    )


def _create_privacy_none_unknown_issue(base_url: str) -> HealthIssue:
    """Create issue for privacy_mode=none with unknown provider."""
    # Redact most of the URL for privacy
    display_url = base_url[:30] + "..." if len(base_url) > 30 else base_url
    target = IssueTarget(setting="privacy_mode")
    return HealthIssue(
        issue_id=HealthIssue.generate_issue_id("privacy_none_unknown", target, ""),
        category=IssueCategory.PRIVACY,
        severity=IssueSeverity.WARNING,
        title="Privacy Mode Disabled with Unknown Provider",
        summary="privacy_mode=none is configured with an unrecognized provider",
        evidence=[
            f"Current privacy_mode: none",
            f"Provider URL: {display_url}",
            "Cannot verify if this is a trusted local provider",
        ],
        recommendation=[
            "Verify the provider is a trusted local LLM service",
            "Consider using privacy_mode='basic' if unsure",
            "Only use privacy_mode=none with verified local providers",
        ],
        target=target,
    )


def _create_missing_api_key_issue(provider_name: str) -> HealthIssue:
    """Create issue for missing API key."""
    env_var = next(
        (k for k, v in API_KEY_ENV_VARS.items() if v == provider_name),
        f"{provider_name.upper()}_API_KEY"
    )
    target = IssueTarget(setting="api_key")
    return HealthIssue(
        issue_id=HealthIssue.generate_issue_id("missing_api_key", target, provider_name),
        category=IssueCategory.SECURITY,
        severity=IssueSeverity.WARNING,
        title=f"API Key Not Configured for {provider_name}",
        summary=f"No API key found for {provider_name} provider",
        evidence=[
            f"Environment variable {env_var} is not set or empty",
            f"Provider: {provider_name}",
        ],
        recommendation=[
            f"Set the {env_var} environment variable",
            "API requests may fail without a valid API key",
            "Check your provider dashboard for API key generation",
        ],
        target=target,
    )


def _create_local_privacy_none_info(provider_name: str) -> HealthIssue:
    """Create info issue for local provider with privacy_mode=none."""
    target = IssueTarget(setting="privacy_mode")
    return HealthIssue(
        issue_id=HealthIssue.generate_issue_id("local_privacy_none", target, provider_name),
        category=IssueCategory.PRIVACY,
        severity=IssueSeverity.INFO,
        title="Privacy Mode Disabled (Local Provider)",
        summary=f"privacy_mode=none is configured with local provider ({provider_name})",
        evidence=[
            f"Current privacy_mode: none",
            f"Provider: {provider_name} (verified local)",
            "Data stays on your local machine",
        ],
        recommendation=[
            "This configuration is acceptable for local LLMs",
            "Data is not sent to external servers",
            "Consider 'basic' mode if you later switch to remote providers",
        ],
        target=target,
    )
