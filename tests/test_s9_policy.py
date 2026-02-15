"""
T15: S9 Policy & Confirmation Tests.
"""
import time
import json
import pytest
from unittest.mock import patch, MagicMock
from services.policy import PolicyEngine
from services.confirmation import ConfirmationTokenService
from services.audit import ActionAudit
from services.providers.registry import ProviderRegistry, ProviderCapability

# -----------------------------------------------------------------------------
# Policy Engine Tests
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_registry():
    # Setup registry with known capabilities
    ProviderRegistry.register(
        "safe-provider", 
        MagicMock(), 
        ProviderCapability(supports_submit=False)
    )
    ProviderRegistry.register(
        "unsafe-provider", 
        MagicMock(), 
        ProviderCapability(supports_submit=True)
    )
    yield
    ProviderRegistry.clear()

def test_policy_allow_safe_actions(mock_registry):
    assert PolicyEngine.evaluate_action("safe-provider", "read") is True
    assert PolicyEngine.evaluate_action("unsafe-provider", "query") is True

def test_policy_block_submit_if_not_supported(mock_registry):
    # Provider doesn't support submit
    assert PolicyEngine.evaluate_action("safe-provider", "submit") is False

def test_policy_block_submit_by_default(mock_registry):
    # Provider supports it, but config is missing
    assert PolicyEngine.evaluate_action("unsafe-provider", "submit") is False
    
    # Config present but False
    config = {"allow_unsafe-provider_submit": False}
    assert PolicyEngine.evaluate_action("unsafe-provider", "submit", config=config) is False

def test_policy_block_submit_without_token(mock_registry):
    config = {"allow_unsafe-provider_submit": True}
    # No token
    assert PolicyEngine.evaluate_action(
        "unsafe-provider", "submit", has_valid_token=False, config=config
    ) is False

def test_policy_allow_submit_with_token_and_config(mock_registry):
    config = {"allow_unsafe-provider_submit": True}
    assert PolicyEngine.evaluate_action(
        "unsafe-provider", "submit", has_valid_token=True, config=config
    ) is True


# -----------------------------------------------------------------------------
# Confirmation Token Tests
# -----------------------------------------------------------------------------

def test_token_lifecycle():
    token = ConfirmationTokenService.issue_token("meta")
    assert token
    
    # Validate and consume
    assert ConfirmationTokenService.validate_and_consume(token) is True
    
    # Replay should fail
    assert ConfirmationTokenService.validate_and_consume(token) is False

def test_token_expiry():
    with patch("services.confirmation.ConfirmationTokenService.TTL_SECONDS", 0.1):
        token = ConfirmationTokenService.issue_token()
        time.sleep(0.2)
        assert ConfirmationTokenService.validate_and_consume(token) is False

def test_token_cleanup():
    with patch("services.confirmation.ConfirmationTokenService.TTL_SECONDS", 0.1):
        ConfirmationTokenService.issue_token() # Expired
        time.sleep(0.2)
        active = ConfirmationTokenService.issue_token() # Active w/ normal TTL override? 
        # Wait, patch applies to class attribute. 
        # We need to insure the 2nd token relies on a different TTL or just test single cleanup.
    
    # Reset
    ConfirmationTokenService._tokens.clear()
    
    # Create expired
    with patch("services.confirmation.ConfirmationTokenService.TTL_SECONDS", -1):
         ConfirmationTokenService.issue_token()
         
    assert len(ConfirmationTokenService._tokens) == 1
    cleaned = ConfirmationTokenService.cleanup()
    assert cleaned == 1
    assert len(ConfirmationTokenService._tokens) == 0


# -----------------------------------------------------------------------------
# Action Audit Tests
# -----------------------------------------------------------------------------

def test_audit_redaction(tmp_path):
    audit = ActionAudit(tmp_path)
    audit.log_action("prov", "action", "allow", meta={"api_key": "secret", "other": "ok"})
    
    log_file = tmp_path / "doctor_audit.jsonl"
    assert log_file.exists()
    
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    last = json.loads(lines[-1])
    
    assert last["meta"]["api_key"] == "***"
    assert last["meta"]["other"] == "ok"
