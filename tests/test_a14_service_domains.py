def test_llm_domain_exports_legacy_service_objects():
    from services import llm
    from services.llm_keys import resolve_api_key
    from services.llm_provider_adapters import get_llm_provider_adapter
    from services.prompt_composer import PromptComposer
    from services.token_budget import TokenBudgetService
    from services.token_estimator import TokenEstimator
    from services.workflow_pruner import WorkflowPruner

    assert llm.resolve_api_key is resolve_api_key
    assert llm.get_llm_provider_adapter is get_llm_provider_adapter
    assert llm.PromptComposer is PromptComposer
    assert llm.TokenBudgetService is TokenBudgetService
    assert llm.TokenEstimator is TokenEstimator
    assert llm.WorkflowPruner is WorkflowPruner


def test_security_domain_exports_legacy_service_objects():
    from services import security
    from services.admin_guard import validate_admin_request
    from services.audit import ActionAudit
    from services.confirmation import ConfirmationTokenService
    from services.policy import PolicyEngine
    from services.secret_store import SecretStore, get_secret_store

    assert security.validate_admin_request is validate_admin_request
    assert security.ActionAudit is ActionAudit
    assert security.ConfirmationTokenService is ConfirmationTokenService
    assert security.PolicyEngine is PolicyEngine
    assert security.SecretStore is SecretStore
    assert security.get_secret_store is get_secret_store


def test_infra_domain_exports_legacy_service_objects():
    from services import infra
    from services.config_guardrails import GuardrailConfig
    from services.doctor_paths import get_doctor_data_dir
    from services.job_manager import JobManager
    from services.log_ring_buffer import get_ring_buffer
    from services.time_utils import utc_now

    assert infra.GuardrailConfig is GuardrailConfig
    assert infra.get_doctor_data_dir is get_doctor_data_dir
    assert infra.JobManager is JobManager
    assert infra.get_ring_buffer is get_ring_buffer
    assert infra.utc_now is utc_now


def test_community_domain_exports_legacy_service_objects():
    from services import community
    from services.community_feedback import (
        FeedbackValidationError,
        GitHubFeedbackConfig,
        build_feedback_preview,
        submit_feedback,
    )

    assert community.FeedbackValidationError is FeedbackValidationError
    assert community.GitHubFeedbackConfig is GitHubFeedbackConfig
    assert community.build_feedback_preview is build_feedback_preview
    assert community.submit_feedback is submit_feedback
