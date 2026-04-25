"""
R30 regression tests for multilingual error-analysis prompt generation.

These tests execute only the prompt helper block from the root module so they
stay independent of ComfyUI's package-loading context.
"""

from pathlib import Path


def _load_prompt_namespace() -> dict:
    root = Path(__file__).resolve().parent.parent
    for filename in ("__init__.py", "__init__.py.bak"):
        candidate = root / filename
        if candidate.exists():
            source = candidate.read_text(encoding="utf-8")
            break
    else:
        raise FileNotFoundError("Cannot find project root __init__.py or __init__.py.bak")

    start = source.index("# Multi-language error analysis prompt templates")
    end = source.index("# --- Option B Phase 2: Error Categorization ---")
    namespace: dict = {}
    exec(source[start:end], namespace)
    return namespace


def test_r30_prompt_languages_are_generated_from_shared_base_template():
    namespace = _load_prompt_namespace()
    base_template = namespace["ERROR_ANALYSIS_BASE_TEMPLATE"]
    language_labels = namespace["ERROR_ANALYSIS_RESPONSE_LANGUAGES"]
    templates = namespace["ERROR_ANALYSIS_TEMPLATES"]

    assert set(templates) == {
        "en",
        "zh_TW",
        "zh_CN",
        "ja",
        "de",
        "fr",
        "it",
        "es",
        "ko",
    }

    for language_code, response_language in language_labels.items():
        prompt = templates[language_code]["system_instruction"]
        assert prompt == base_template.replace("{response_language}", response_language)
        assert f"**Response Language**: {response_language}" in prompt
        assert "Focus on CRASH PREVENTION" in prompt


def test_r30_prompt_helper_falls_back_to_english():
    namespace = _load_prompt_namespace()
    get_error_analysis_prompt = namespace["get_error_analysis_prompt"]

    assert get_error_analysis_prompt("missing") == get_error_analysis_prompt("en")
    assert "**Response Language**: English" in get_error_analysis_prompt("")
