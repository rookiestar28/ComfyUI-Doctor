"""R12 budget service: per-call estimator settings.

``BudgetConfig.estimator_config`` must change the estimate the budget works with, without tiktoken,
while an explicitly injected estimator stays authoritative and per-call settings never change the
service's default estimator.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from services.token_budget import BudgetConfig, TokenBudgetService  # noqa: E402
from services.token_estimator import EstimatorConfig, TokenEstimate  # noqa: E402

OVERHEAD = 1000
PAYLOAD = {
    "messages": [],
    "error_context": {"error": "RuntimeError: probe", "traceback": "frame line\n" * 400},
}


def _estimator(chars_per_token: float) -> EstimatorConfig:
    return EstimatorConfig(mode="fallback_only", fallback_chars_per_token=chars_per_token, safety_multiplier=1.0)


def _initial_tokens(service: TokenBudgetService, estimator_config: EstimatorConfig) -> int:
    config = BudgetConfig(
        soft_max_tokens=1_000_000,
        hard_max_tokens=2_000_000,
        overhead_fixed=OVERHEAD,
        estimator_config=estimator_config,
    )
    _, meta = service.apply_token_budget(PAYLOAD, True, config)
    return meta["token_budget"]["estimated_tokens_initial"]


def test_estimator_config_changes_the_estimate_without_tiktoken():
    service = TokenBudgetService()

    coarse = _initial_tokens(service, _estimator(4.0)) - OVERHEAD
    fine = _initial_tokens(service, _estimator(2.0)) - OVERHEAD

    assert coarse > 0
    # Half the characters per token -> about twice the tokens (per-section ceil rounding aside).
    assert abs(fine - 2 * coarse) <= 8


def test_per_call_settings_do_not_change_the_service_default():
    service = TokenBudgetService()
    default_tokens = _initial_tokens(service, EstimatorConfig())

    _initial_tokens(service, _estimator(1.0))

    assert _initial_tokens(service, EstimatorConfig()) == default_tokens
    assert service.estimator.config == EstimatorConfig()


def test_injected_estimator_stays_authoritative():
    injected = MagicMock()
    injected.estimate.return_value = TokenEstimate(
        estimated_tokens=7, method="fallback", multiplier_applied=1.0, chars=28, tokens_per_char=4.0
    )
    service = TokenBudgetService(estimator=injected)

    tokens = _initial_tokens(service, _estimator(1.0))

    assert injected.estimate.called
    # traceback section (7) + "other" clamped at max(0, whole context 7 - sections 7) = 0
    assert tokens == OVERHEAD + 7
