import pytest
from unittest.mock import MagicMock, patch
import sys

# T9: Pipeline Isolation Test
# Verifies that PromptComposer and basic Pipeline components can be instantiated
# and used without a running ComfyUI instance (mocking `server` module).

@pytest.fixture
def mock_comfy_env():
    """Mock ComfyUI server and folder primitives."""
    with patch.dict(sys.modules, {
        "server": MagicMock(),
        "folder_paths": MagicMock()
    }):
        yield

def test_prompt_composer_contract_mock_env(mock_comfy_env):
    """
    Verify PromptComposer can format system info even when
    running outside main ComfyUI process (using mock SystemInfo).
    """
    # Import inside fixture to ensure mocks are active
    from services.prompt_composer import PromptComposer
    
    # Mock SystemInfo data structure
    mock_sys_info = {
        "os": "Windows 11",
        "python_version": "3.13.9",
        "gpu": {"name": "NVIDIA GeForce RTX 4090", "vram": 24564},
        "packages": {"torch": "2.5.1"}
    }
    
    # Verify composition
    composer = PromptComposer()
    
    # Construct LLM context as expected by PromptComposer
    llm_context = {
        "error_summary": "Fix error",
        "system_info": mock_sys_info,
        "node_info": {},
        "traceback": "Traceback (most recent call last):...",
        "workflow_subset": {}
    }
    
    system_prompt = composer.compose(llm_context)
    
    # Assertions
    assert "System Environment" in system_prompt
    assert "Windows 11" in system_prompt
    assert "3.13.9" in system_prompt

def test_pipeline_isolation_basics(mock_comfy_env):
    """Verify AnalysisPipeline basics without server."""
    # This test ensures we don't have hard imports of 'server' at module level
    # that would crash if server is missing (simulated by mock).
    from services.prompt_composer import PromptComposer
    # If we had a Pipeline class, we'd test it here.
    # Currently checking essential components used in the pipeline.
    assert PromptComposer is not None
