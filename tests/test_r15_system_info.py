"""
R15 Unit Tests: System Info Canonicalization and Pipeline Logs.

Tests for:
1. canonicalize_system_info() - schema transformation
2. Smart package keyword extraction from error text
3. Package capping behavior
4. Pipeline execution_logs population from LogRingBuffer
"""

import pytest
from typing import Dict, Any


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def legacy_env_info() -> Dict[str, Any]:
    """Legacy format from get_system_environment()."""
    return {
        "os": "Windows 11",
        "os_version": "10.0.22631",
        "python_version": "3.10.11",
        "pytorch_info": {
            "pytorch_version": "2.1.0+cu121",
            "cuda_available": True,
            "cuda_version": "12.1",
            "gpu_count": 1,
        },
        "installed_packages": (
            "torch==2.1.0+cu121\n"
            "numpy==1.24.3\n"
            "pillow==10.0.0\n"
            "opencv-python==4.8.0\n"
            "transformers==4.35.0\n"
            "diffusers==0.21.0\n"
            "safetensors==0.4.0\n"
            "accelerate==0.24.0\n"
            "xformers==0.0.23\n"
            "triton==2.1.0\n"
            "insightface==0.7.3\n"
            "onnxruntime==1.16.0\n"
            "bitsandbytes==0.41.0\n"
            "mediapipe==0.10.0\n"
            "ultralytics==8.0.0\n"
            "requests==2.31.0\n"
            "aiohttp==3.8.0\n"
            "pyyaml==6.0.0\n"
            "tqdm==4.66.0\n"
            "colorama==0.4.6\n"
            "some-random-package==1.0.0\n"
            "another-package==2.0.0\n"
        ),
        "cache_age_seconds": 3600,
    }


@pytest.fixture
def canonical_env_info() -> Dict[str, Any]:
    """Already canonical format."""
    return {
        "os": "Windows 11 10.0.22631",
        "python_version": "3.10.11",
        "torch_version": "2.1.0+cu121",
        "cuda_available": True,
        "cuda_version": "12.1",
        "gpu_count": 1,
        "packages": ["torch==2.1.0+cu121", "numpy==1.24.3"],
        "packages_total": 22,
        "source": "get_system_environment",
    }


# ═══════════════════════════════════════════════════════════════════════════
# TEST: canonicalize_system_info from legacy shape
# ═══════════════════════════════════════════════════════════════════════════

class TestCanonicalizeSystemInfo:
    """Tests for system_info.canonicalize_system_info()."""

    def test_canonicalize_from_legacy_shape(self, legacy_env_info: Dict[str, Any]):
        """Test transformation from legacy env_info to canonical schema."""
        from system_info import canonicalize_system_info
        
        result = canonicalize_system_info(legacy_env_info)
        
        # Core fields should be present
        assert "torch_version" in result
        assert result["torch_version"] == "2.1.0+cu121"
        assert result["cuda_available"] is True
        assert result["cuda_version"] == "12.1"
        assert result["gpu_count"] == 1
        assert result["python_version"] == "3.10.11"
        
        # OS should be combined
        assert "Windows 11" in result["os"]
        
        # Packages should be a list
        assert isinstance(result["packages"], list)
        assert len(result["packages"]) <= 20  # Default max
        
        # packages_total should reflect total parsed
        assert result["packages_total"] >= 10
        
        # Source marker
        assert result["source"] == "get_system_environment"

    def test_canonicalize_already_canonical_passthrough(self, canonical_env_info: Dict[str, Any]):
        """Test that already canonical info is passed through unchanged."""
        from system_info import canonicalize_system_info
        
        result = canonicalize_system_info(canonical_env_info)
        
        # Should be mostly the same
        assert result["torch_version"] == canonical_env_info["torch_version"]
        assert result["packages"] == canonical_env_info["packages"]
        assert result["packages_total"] == canonical_env_info["packages_total"]

    def test_canonicalize_keyword_selection_from_error(self, legacy_env_info: Dict[str, Any]):
        """Test that error-referenced packages are prioritized."""
        from system_info import canonicalize_system_info
        
        # Error mentions insightface
        error_text = "ModuleNotFoundError: No module named 'insightface'"
        
        result = canonicalize_system_info(legacy_env_info, error_text=error_text)
        
        # insightface should be in packages (error-referenced)
        package_names = [p.lower() for p in result["packages"]]
        assert any("insightface" in p for p in package_names)

    def test_canonicalize_keyword_extraction_import_error(self, legacy_env_info: Dict[str, Any]):
        """Test keyword extraction from ImportError."""
        from system_info import canonicalize_system_info
        
        error_text = "ImportError: cannot import name 'something' from 'ultralytics'"
        
        result = canonicalize_system_info(legacy_env_info, error_text=error_text)
        
        package_names = [p.lower() for p in result["packages"]]
        assert any("ultralytics" in p for p in package_names)

    def test_canonicalize_caps_packages(self, legacy_env_info: Dict[str, Any]):
        """Test that packages are capped at max_packages."""
        from system_info import canonicalize_system_info
        
        # Set very low cap
        result = canonicalize_system_info(legacy_env_info, max_packages=5)
        
        assert len(result["packages"]) <= 5
        assert result["packages_total"] > 5  # Total should still reflect full count

    def test_canonicalize_empty_packages(self):
        """Test handling of empty or error package strings."""
        from system_info import canonicalize_system_info
        
        env_info = {
            "os": "Windows 11",
            "python_version": "3.10.11",
            "pytorch_info": {"pytorch_version": "2.1.0"},
            "installed_packages": "[Error running pip list: timeout]",
        }
        
        result = canonicalize_system_info(env_info)
        
        # Should not crash, should have empty packages
        assert result["packages"] == []
        assert result["packages_total"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Package keyword extraction
# ═══════════════════════════════════════════════════════════════════════════

class TestPackageKeywordExtraction:
    """Tests for _extract_package_keywords_from_error()."""

    def test_extract_module_not_found(self):
        """Test extraction from ModuleNotFoundError."""
        from system_info import _extract_package_keywords_from_error
        
        error = "ModuleNotFoundError: No module named 'xformers'"
        keywords = _extract_package_keywords_from_error(error)
        
        assert "xformers" in keywords

    def test_extract_module_not_found_submodule(self):
        """Test extraction from ModuleNotFoundError with submodule."""
        from system_info import _extract_package_keywords_from_error
        
        error = "ModuleNotFoundError: No module named 'segment_anything.build_sam'"
        keywords = _extract_package_keywords_from_error(error)
        
        assert "segment_anything" in keywords

    def test_extract_import_error(self):
        """Test extraction from ImportError."""
        from system_info import _extract_package_keywords_from_error
        
        error = "ImportError: cannot import name 'AutoModel' from 'transformers'"
        keywords = _extract_package_keywords_from_error(error)
        
        assert "transformers" in keywords

    def test_extract_runtime_keyword_mention(self):
        """Test extraction of runtime keywords mentioned in error."""
        from system_info import _extract_package_keywords_from_error
        
        error = "RuntimeError: CUDA error in xformers attention: out of memory"
        keywords = _extract_package_keywords_from_error(error)
        
        assert "xformers" in keywords
        assert "cuda" in keywords

    def test_extract_empty_error(self):
        """Test handling of empty/None error text."""
        from system_info import _extract_package_keywords_from_error
        
        assert _extract_package_keywords_from_error("") == set()
        assert _extract_package_keywords_from_error(None) == set()


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Pipeline execution_logs population
# ═══════════════════════════════════════════════════════════════════════════

class TestPipelineLogPopulation:
    """Tests for LLMContextBuilderStage execution_logs population."""

    def test_populate_execution_logs_from_ring_buffer(self):
        """Test that empty execution_logs are populated from ring buffer."""
        from services.log_ring_buffer import get_ring_buffer, reset_ring_buffer
        from pipeline.context import AnalysisContext
        from services.workflow_pruner import WorkflowPruner
        from pipeline.stages.llm_builder import LLMContextBuilderStage
        
        # Reset and populate ring buffer
        reset_ring_buffer()
        ring = get_ring_buffer()
        ring.add_line("Processing node KSampler...")
        ring.add_line("Loading model checkpoint...")
        ring.add_line("Error in node 42")
        
        # Create context with empty logs - note: stage requires sanitized_traceback
        traceback_text = "Traceback (most recent call last):\n  File \"test.py\", line 10\nValueError: test error"
        context = AnalysisContext(
            traceback=traceback_text,
            execution_logs=[],  # Empty, should be populated
            settings={"privacy_mode": "basic"}
        )
        # Pipeline stages work on sanitized_traceback, not traceback
        context.sanitized_traceback = traceback_text
        
        # Process
        stage = LLMContextBuilderStage(WorkflowPruner())
        stage.process(context)
        
        # Verify logs were populated
        assert len(context.execution_logs) > 0
        assert context.llm_context is not None
        assert len(context.llm_context["execution_logs"]) > 0
        
        # Cleanup
        reset_ring_buffer()

    def test_preserve_existing_execution_logs(self):
        """Test that existing execution_logs are preserved."""
        from pipeline.context import AnalysisContext
        from services.workflow_pruner import WorkflowPruner
        from pipeline.stages.llm_builder import LLMContextBuilderStage
        
        existing_logs = ["Existing log 1", "Existing log 2"]
        traceback_text = "Traceback (most recent call last):\n  File \"test.py\"\nValueError: test"
        
        context = AnalysisContext(
            traceback=traceback_text,
            execution_logs=existing_logs.copy(),
            settings={}
        )
        context.sanitized_traceback = traceback_text
        
        stage = LLMContextBuilderStage(WorkflowPruner())
        stage.process(context)
        
        # Original logs should be preserved
        assert context.execution_logs == existing_logs
        assert context.llm_context is not None
        assert context.llm_context["execution_logs"] == existing_logs

    def test_populate_execution_logs_respects_privacy_mode_strict(self):
        """Strict mode should sanitize patterns not covered by basic."""
        from services.log_ring_buffer import get_ring_buffer, reset_ring_buffer
        from pipeline.context import AnalysisContext
        from services.workflow_pruner import WorkflowPruner
        from pipeline.stages.llm_builder import LLMContextBuilderStage

        reset_ring_buffer()
        ring = get_ring_buffer()
        ring.add_line("IPv6: fe80:abcd:ef12:3456")
        ring.add_line("SSH: SHA256:ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ")

        traceback_text = "Traceback (most recent call last):\n  File \"test.py\"\nValueError: test"
        context = AnalysisContext(
            traceback=traceback_text,
            execution_logs=[],
            settings={"privacy_mode": "strict"},
        )
        context.sanitized_traceback = traceback_text

        stage = LLMContextBuilderStage(WorkflowPruner())
        stage.process(context)

        logs = context.llm_context["execution_logs"]
        assert any("<PRIVATE_IPV6>" in line for line in logs)
        assert any("<SSH_FINGERPRINT>" in line for line in logs)

        reset_ring_buffer()


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Pipeline system_info population
# ═══════════════════════════════════════════════════════════════════════════

class TestPipelineSystemInfoPopulation:
    """Tests for LLMContextBuilderStage system_info population."""

    def test_populate_system_info_when_missing(self):
        """Test that missing system_info is populated with canonical schema."""
        from pipeline.context import AnalysisContext
        from services.workflow_pruner import WorkflowPruner
        from pipeline.stages.llm_builder import LLMContextBuilderStage
        
        traceback_text = "Traceback (most recent call last):\n  File \"test.py\"\nModuleNotFoundError: No module named 'xformers'"
        context = AnalysisContext(
            traceback=traceback_text,
            system_info={},  # Empty, should be populated
            settings={"include_system_info": True, "privacy_mode": "basic"}
        )
        context.sanitized_traceback = traceback_text
        
        stage = LLMContextBuilderStage(WorkflowPruner())
        stage.process(context)
        
        # system_info should be populated
        assert context.llm_context is not None
        sys_info = context.llm_context["system_info"]
        assert sys_info  # Not empty
        # Should be canonical schema
        if sys_info:  # Guard for CI environments
            assert "packages" in sys_info or "source" in sys_info

    def test_preserve_existing_system_info(self):
        """Test that existing system_info is preserved."""
        from pipeline.context import AnalysisContext
        from services.workflow_pruner import WorkflowPruner
        from pipeline.stages.llm_builder import LLMContextBuilderStage
        
        existing_info = {"os": "TestOS", "python_version": "3.10.0"}
        traceback_text = "Traceback (most recent call last):\n  File \"test.py\"\nValueError: test"
        
        context = AnalysisContext(
            traceback=traceback_text,
            system_info=existing_info.copy(),
            settings={}
        )
        context.sanitized_traceback = traceback_text
        
        stage = LLMContextBuilderStage(WorkflowPruner())
        stage.process(context)
        
        # Original info should be preserved
        assert context.system_info == existing_info
        assert context.llm_context is not None
        assert context.llm_context["system_info"] == existing_info

    def test_respect_include_system_info_setting(self):
        """Test that include_system_info=False prevents auto-population."""
        from pipeline.context import AnalysisContext
        from services.workflow_pruner import WorkflowPruner
        from pipeline.stages.llm_builder import LLMContextBuilderStage
        
        traceback_text = "Traceback (most recent call last):\n  File \"test.py\"\nValueError: test"
        context = AnalysisContext(
            traceback=traceback_text,
            system_info={},
            settings={"include_system_info": False}
        )
        context.sanitized_traceback = traceback_text
        
        stage = LLMContextBuilderStage(WorkflowPruner())
        stage.process(context)
        
        # Should remain empty due to setting
        assert context.llm_context is not None
        assert context.llm_context["system_info"] == {}
