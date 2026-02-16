import json
import os
from unittest.mock import patch
from services.config_guardrails import GuardrailConfig
from config import CONFIG, DiagnosticsConfig, load_config

def test_guardrail_defaults():
    """Verify default values are loaded when no ENV vars are set."""
    with patch.dict(os.environ, {}, clear=True):
        config = GuardrailConfig.load()
        assert config.MAX_HISTORY_ENTRIES == 1000
        assert config.MAX_JOB_RETENTION_SECONDS == 86400
        assert config.RATE_LIMIT_WINDOW_SECONDS == 60
        assert config.PROVIDER_TIMEOUT_SECONDS == 30

def test_guardrail_env_overrides():
    """Verify ENV variables override defaults."""
    env_vars = {
        "DOCTOR_GUARDRAIL_MAX_HISTORY": "500",
        "DOCTOR_GUARDRAIL_JOB_RETENTION": "3600",
        "DOCTOR_GUARDRAIL_RATE_LIMIT_WINDOW": "120",
        "DOCTOR_GUARDRAIL_PROVIDER_TIMEOUT": "45"
    }
    with patch.dict(os.environ, env_vars, clear=True):
        config = GuardrailConfig.load()
        assert config.MAX_HISTORY_ENTRIES == 500
        assert config.MAX_JOB_RETENTION_SECONDS == 3600
        assert config.RATE_LIMIT_WINDOW_SECONDS == 120
        assert config.PROVIDER_TIMEOUT_SECONDS == 45

def test_integration_with_main_config():
    """Verify GuardrailConfig is correctly integrated into DiagnosticsConfig."""
    # Ensure guardrails field exists and is populated
    assert isinstance(CONFIG.guardrails, GuardrailConfig)
    # Check a default value accessible via main config
    assert CONFIG.guardrails.MAX_HISTORY_ENTRIES > 0


def test_guardrails_runtime_only_not_persisted():
    """Verify runtime guardrails are excluded from persisted config payload."""
    payload = DiagnosticsConfig().to_dict()
    assert "guardrails" not in payload


def test_load_config_ignores_persisted_guardrails(tmp_path):
    """Verify legacy persisted guardrails do not override runtime guardrails."""
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "history_size": 42,
                "guardrails": {
                    "MAX_HISTORY_ENTRIES": 1,
                    "MAX_JOB_RETENTION_SECONDS": 1
                }
            }
        ),
        encoding="utf-8",
    )

    with patch("config._get_config_path_candidates", return_value=[str(config_path)]):
        loaded = load_config()

    assert loaded.history_size == 42
    assert isinstance(loaded.guardrails, GuardrailConfig)
    assert loaded.guardrails.MAX_HISTORY_ENTRIES != 1
