from pipeline import AnalysisPipeline, AnalysisContext


class MissingRequirementStage:
    def __init__(self):
        self._name = "MissingRequirementStage"
        self.stage_id = "missing_requirement"
        self.requires = ["node_context"]
        self.provides = ["metadata.example"]
        self.version = "1.0"

    @property
    def name(self):
        return self._name

    def process(self, context: AnalysisContext) -> None:
        context.add_metadata("example", "value")


class ExplodingStage:
    def __init__(self):
        self._name = "ExplodingStage"
        self.stage_id = "exploding"
        self.requires = ["traceback"]
        self.provides = []
        self.version = "1.0"

    @property
    def name(self):
        return self._name

    def process(self, context: AnalysisContext) -> None:
        raise RuntimeError("boom")


def test_pipeline_skips_missing_requirements():
    pipeline = AnalysisPipeline([MissingRequirementStage()])
    ctx = AnalysisContext(traceback="Traceback (most recent call last): ...")
    pipeline.run(ctx)

    assert ctx.metadata["pipeline_status"] == "degraded"
    assert ctx.metadata["stage_errors"][0]["error"] == "missing_requirements"
    assert ctx.metadata["stage_errors"][0]["missing"] == ["node_context"]


def test_pipeline_marks_failed_on_exception():
    pipeline = AnalysisPipeline([ExplodingStage()])
    ctx = AnalysisContext(traceback="Traceback (most recent call last): ...")
    pipeline.run(ctx)

    assert ctx.metadata["pipeline_status"] == "failed"
    assert ctx.metadata["stage_errors"][0]["error"] == "boom"

