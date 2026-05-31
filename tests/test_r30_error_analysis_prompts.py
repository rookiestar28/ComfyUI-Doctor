"""
R30 regression tests for multilingual error-analysis prompt generation.

The helpers live outside the ComfyUI package entry point so route refactors can
keep prompt behavior covered without importing the host startup module.
"""

from services import prompt_helpers


def test_r30_prompt_languages_are_generated_from_shared_base_template():
    base_template = prompt_helpers.ERROR_ANALYSIS_BASE_TEMPLATE
    language_labels = prompt_helpers.ERROR_ANALYSIS_RESPONSE_LANGUAGES
    templates = prompt_helpers.ERROR_ANALYSIS_TEMPLATES

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
    get_error_analysis_prompt = prompt_helpers.get_error_analysis_prompt

    assert get_error_analysis_prompt("missing") == get_error_analysis_prompt("en")
    assert "**Response Language**: English" in get_error_analysis_prompt("")
