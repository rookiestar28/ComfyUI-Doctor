import json
from pathlib import Path

import pytest

import i18n


def _write_language_files(base: Path, overrides: dict | None = None) -> None:
    overrides = overrides or {}
    for lang in i18n.SUPPORTED_LANGUAGES:
        payload = {
            "language": lang,
            "ui_text": dict(i18n.UI_TEXT[lang]),
            "suggestions": dict(i18n.SUGGESTIONS[lang]),
        }
        if lang in overrides:
            payload.update(overrides[lang])
        (base / f"{lang}.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )


def test_i18n_loader_reads_all_supported_language_files():
    assert set(i18n.UI_TEXT) == set(i18n.SUPPORTED_LANGUAGES)
    assert set(i18n.SUGGESTIONS) == set(i18n.SUPPORTED_LANGUAGES)

    for lang in i18n.SUPPORTED_LANGUAGES:
        assert (i18n.I18N_DATA_DIR / f"{lang}.json").exists()
        assert "tab_chat" in i18n.UI_TEXT[lang]
        assert i18n.ERROR_KEYS["OOM"] in i18n.SUGGESTIONS[lang]


def test_i18n_fallbacks_still_match_existing_behavior():
    i18n.set_language("zh_TW")

    assert i18n.get_ui_text("tab_chat", lang="missing-lang") == i18n.UI_TEXT["en"]["tab_chat"]
    assert i18n.get_ui_text("missing_key") == "[Missing: missing_key]"
    assert i18n.get_suggestion("missing_key") is None

    assert i18n.set_language("invalid_lang") is False
    assert i18n.get_language() == "zh_TW"
    i18n.set_language("en")


def test_i18n_loader_rejects_malformed_json(tmp_path):
    _write_language_files(tmp_path)
    (tmp_path / "en.json").write_text("{", encoding="utf-8")

    with pytest.raises(i18n.I18nDataError, match="invalid JSON"):
        i18n._load_translation_data(tmp_path)


def test_i18n_loader_rejects_missing_suggestion_keys(tmp_path):
    en_suggestions = dict(i18n.SUGGESTIONS["en"])
    en_suggestions.pop(i18n.ERROR_KEYS["OOM"])
    _write_language_files(tmp_path, {"en": {"suggestions": en_suggestions}})

    with pytest.raises(i18n.I18nDataError, match="missing suggestion translations"):
        i18n._load_translation_data(tmp_path)


def test_i18n_loader_rejects_non_string_values(tmp_path):
    en_ui_text = dict(i18n.UI_TEXT["en"])
    en_ui_text["tab_chat"] = ["Chat"]
    _write_language_files(tmp_path, {"en": {"ui_text": en_ui_text}})

    with pytest.raises(i18n.I18nDataError, match="ui_text.tab_chat must be a string"):
        i18n._load_translation_data(tmp_path)
