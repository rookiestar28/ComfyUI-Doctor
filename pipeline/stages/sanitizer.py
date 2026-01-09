import logging
from ..base import PipelineStage
from ..context import AnalysisContext
try:
    from sanitizer import PIISanitizer, SanitizationLevel, get_sanitizer
except ImportError:
    # Fallback for relative import if needed (mostly for tests)
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from sanitizer import PIISanitizer, SanitizationLevel, get_sanitizer

logger = logging.getLogger(__name__)

class SanitizerStage(PipelineStage):
    """
    Stage 1: PII Sanitization.
    Removes sensitive information from the traceback before further processing.
    """
    
    def __init__(self, use_cached_instance=True):
        self._name = "SanitizerStage"
        self.stage_id = "sanitizer"
        self.requires = ["traceback"]
        self.provides = ["sanitized_traceback", "metadata.sanitization"]
        self.version = "1.0"
        self.use_cached_instance = use_cached_instance

    @property
    def name(self) -> str:
        return self._name

    def process(self, context: AnalysisContext) -> None:
        """
        Sanitizes the traceback in the context.
        """
        if not context.traceback:
            context.sanitized_traceback = context.traceback
            return

        # Determine sanitization level from settings, default to "basic"
        level_name = context.settings.get("privacy_mode", "basic")
        try:
            level = SanitizationLevel(level_name)
        except ValueError:
            level = SanitizationLevel.BASIC

        sanitizer = get_sanitizer(level) if self.use_cached_instance else PIISanitizer(level)
        result = sanitizer.sanitize(context.traceback)
        context.sanitized_traceback = result.sanitized_text
        context.metadata["sanitization"] = result.to_dict()
