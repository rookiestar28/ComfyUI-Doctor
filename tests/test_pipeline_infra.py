import pytest
from pipeline.context import AnalysisContext
from pipeline.orchestrator import AnalysisPipeline
from pipeline.base import PipelineStage
from pipeline.stages.sanitizer import SanitizerStage
from dataclasses import dataclass

class MockStage:
    def __init__(self, name="MockStage", should_fail=False):
        self._name = name
        self.stage_id = name
        self.requires = ["traceback"]
        self.provides = []
        self.version = "1.0"
        self.should_fail = should_fail
        self.processed = False

    @property
    def name(self):
        return self._name

    def process(self, context: AnalysisContext):
        if self.should_fail:
            raise ValueError(f"Simulated failure in {self.name}")
        
        context.add_metadata(f"{self.name}_ran", True)
        self.processed = True

def test_context_metadata():
    ctx = AnalysisContext(traceback="error")
    ctx.add_metadata("test_key", "test_value")
    assert ctx.metadata["test_key"] == "test_value"

def test_orchestrator_runs_stages():
    stage1 = MockStage("stage1")
    stage2 = MockStage("stage2")
    pipeline = AnalysisPipeline([stage1, stage2])
    ctx = AnalysisContext(traceback="error")
    
    pipeline.run(ctx)
    
    assert stage1.processed
    assert stage2.processed
    invalid = ctx.metadata.get("_invalid", {})
    assert invalid["stage1_ran"] is True
    assert invalid["stage2_ran"] is True

def test_orchestrator_fail_safe():
    stage1 = MockStage("stage1")
    stage2 = MockStage("stage2", should_fail=True)
    stage3 = MockStage("stage3")
    
    pipeline = AnalysisPipeline([stage1, stage2, stage3])
    ctx = AnalysisContext(traceback="error")
    
    pipeline.run(ctx)
    
    # Stage 1 ran
    assert stage1.processed
    
    # Stage 2 failed but didn't crash pipeline
    assert not stage2.processed # processed flag set after failure point if it was process logic, but here it raises before setting flag? No in MockStage it raises first.
    assert "stage_error_stage2" in ctx.metadata
    
    # Stage 3 still ran
    assert stage3.processed
    invalid = ctx.metadata.get("_invalid", {})
    assert invalid["stage3_ran"] is True

def test_sanitizer_stage_basic():
    ctx = AnalysisContext(
        traceback='File "C:\\Users\\john\\project\\main.py"\\nAPI key: sk-01234567890123456789'
    )
    ctx.settings["privacy_mode"] = "basic"
    stage = SanitizerStage(use_cached_instance=False)

    stage.process(ctx)

    assert ctx.sanitized_traceback is not None
    assert "<USER_PATH>" in ctx.sanitized_traceback
    assert "C:\\Users\\john" not in ctx.sanitized_traceback
    assert "<API_KEY>" in ctx.sanitized_traceback
    assert "sk-01234567890123456789" not in ctx.sanitized_traceback
    assert ctx.metadata.get("sanitization") is not None
    assert ctx.metadata["sanitization"]["pii_found"] is True
    assert ctx.metadata["sanitization"]["sanitized_length"] < ctx.metadata["sanitization"]["original_length"]

def test_sanitizer_stage_none():
    raw = "Traceback with no sanitization"
    ctx = AnalysisContext(traceback=raw)
    ctx.settings["privacy_mode"] = "none"
    stage = SanitizerStage(use_cached_instance=False)

    stage.process(ctx)

    assert ctx.sanitized_traceback == raw

def test_sanitizer_stage_strict():
    ctx = AnalysisContext(
        traceback="IPv6: fe80:abcd:ef12:3456\\nSSH: SHA256:ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"
    )
    ctx.settings["privacy_mode"] = "strict"
    stage = SanitizerStage(use_cached_instance=False)

    stage.process(ctx)

    assert "<PRIVATE_IPV6>" in ctx.sanitized_traceback
    assert "fe80:abcd:ef12:3456" not in ctx.sanitized_traceback
    assert "<SSH_FINGERPRINT>" in ctx.sanitized_traceback
    assert "SHA256:ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ" not in ctx.sanitized_traceback
    assert ctx.metadata.get("sanitization") is not None
    assert ctx.metadata["sanitization"]["pii_found"] is True
