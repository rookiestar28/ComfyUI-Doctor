import asyncio
import os
from typing import Dict, Optional, Tuple
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from llm_client import RetryConfig, llm_request_with_retry
from services.policy import PolicyEngine


SKIP_REASON = "Online API tests are opt-in. Set RUN_ONLINE_API_TESTS=true to run."
RUN_ONLINE = os.environ.get("RUN_ONLINE_API_TESTS", "false").lower() == "true"


def _env_first(*keys: str) -> Optional[str]:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return None


def _run(coro):
    return asyncio.run(coro)


async def _smoke_get(url: str, headers: Dict[str, str]) -> Tuple[int, int]:
    async with aiohttp.ClientSession() as session:
        result = await llm_request_with_retry(
            session,
            "GET",
            url,
            headers=headers,
            config=RetryConfig(
                max_retries=1,
                base_delay=0.01,
                request_timeout_seconds=20,
                total_timeout_seconds=40,
                add_idempotency_key=False,
            ),
        )
        assert result.response is not None
        status = result.response.status
        attempts = result.attempts
        result.response.close()
        return status, attempts


@pytest.mark.skipif(not RUN_ONLINE, reason=SKIP_REASON)
def test_online_openai_models_smoke():
    api_key = _env_first("DOCTOR_OPENAI_API_KEY", "OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OpenAI API key not configured for opt-in online test.")

    base_url = os.environ.get("DOCTOR_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    status, attempts = _run(
        _smoke_get(
            f"{base_url}/models",
            {"Authorization": f"Bearer {api_key}"},
        )
    )
    assert status in (200, 401, 403, 404, 429)
    assert attempts >= 1


@pytest.mark.skipif(not RUN_ONLINE, reason=SKIP_REASON)
def test_online_deepseek_models_smoke():
    api_key = _env_first("DOCTOR_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DeepSeek API key not configured for opt-in online test.")

    base_url = os.environ.get("DOCTOR_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    status, attempts = _run(
        _smoke_get(
            f"{base_url}/models",
            {"Authorization": f"Bearer {api_key}"},
        )
    )
    assert status in (200, 401, 403, 404, 429)
    assert attempts >= 1


@pytest.mark.skipif(not RUN_ONLINE, reason=SKIP_REASON)
def test_online_anthropic_models_smoke():
    api_key = _env_first("DOCTOR_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("Anthropic API key not configured for opt-in online test.")

    base_url = os.environ.get("DOCTOR_ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
    status, attempts = _run(
        _smoke_get(
            f"{base_url}/models",
            {
                "x-api-key": api_key,
                "anthropic-version": os.environ.get("DOCTOR_ANTHROPIC_VERSION", "2023-06-01"),
            },
        )
    )
    assert status in (200, 401, 403, 404, 429)
    assert attempts >= 1


def test_online_policy_submit_guardrails():
    """
    T5/S9 integration guard: submit path must remain fail-closed unless both
    config and confirmation token are provided.
    """
    denied_unknown = PolicyEngine.evaluate_action("unknown_provider", "submit")
    assert denied_unknown is False

    with patch("services.providers.registry.ProviderRegistry.get_capability") as mock_cap:
        mock_cap.return_value = MagicMock(supports_submit=True)

        denied_no_config = PolicyEngine.evaluate_action("openai", "submit", config={})
        assert denied_no_config is False

        denied_no_token = PolicyEngine.evaluate_action(
            "openai",
            "submit",
            has_valid_token=False,
            config={"allow_openai_submit": True},
        )
        assert denied_no_token is False

        allowed = PolicyEngine.evaluate_action(
            "openai",
            "submit",
            has_valid_token=True,
            config={"allow_openai_submit": True},
        )
        assert allowed is True
