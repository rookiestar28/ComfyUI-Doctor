"""The settings panel's notices for a locked or just-rotated server key store exist in every language.

``GET /doctor/secrets/status`` reports ``store.state`` and writes to a locked store return HTTP 409
(``secret_store_locked``). The settings key-store section turns those states into one fixed, localized
notice per state, so a user whose key store is locked sees why saving fails and what to do. The copy
must stay accurate: it names the environment variable for the two locked states and never claims that a
key was sent anywhere.
"""
import json
from pathlib import Path
from typing import Dict

import pytest

ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = ROOT / "i18n_data"
LANGUAGES = ("en", "zh_TW", "zh_CN", "ja", "de", "fr", "it", "es", "ko")
STATE_KEYS = {
    "locked_key_required": "keystore_state_locked_key_required",
    "locked_key_mismatch": "keystore_state_locked_key_mismatch",
    "corrupt": "keystore_state_corrupt",
}
ENV_VARIABLE = "DOCTOR_SECRET_STORE_ENCRYPTION_KEY"


def ui_text(lang: str) -> Dict[str, str]:
    return json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))["ui_text"]


@pytest.mark.parametrize("lang", LANGUAGES)
@pytest.mark.parametrize("state", list(STATE_KEYS))
def test_every_state_has_a_translated_notice_in_every_language(lang, state):
    value = ui_text(lang).get(STATE_KEYS[state])

    assert isinstance(value, str) and len(value.strip()) >= 20, (lang, state)
    if lang != "en":
        assert value != ui_text("en")[STATE_KEYS[state]], f"{lang}.{STATE_KEYS[state]} is an untranslated copy"


@pytest.mark.parametrize("lang", LANGUAGES)
@pytest.mark.parametrize("state", ["locked_key_required", "locked_key_mismatch"])
def test_the_locked_notices_name_the_environment_variable(lang, state):
    assert ENV_VARIABLE in ui_text(lang)[STATE_KEYS[state]]


@pytest.mark.parametrize("lang", LANGUAGES)
def test_the_notices_are_plain_text_without_markup_or_placeholders(lang):
    for key in STATE_KEYS.values():
        value = ui_text(lang)[key]
        assert "<" not in value and ">" not in value and "{" not in value, (lang, key)


def test_the_three_notices_are_distinct_in_every_language():
    for lang in LANGUAGES:
        values = [ui_text(lang)[key] for key in STATE_KEYS.values()]
        assert len(set(values)) == 3, lang


def test_the_english_notices_say_what_happened_and_what_to_do():
    english = {state: ui_text("en")[key] for state, key in STATE_KEYS.items()}

    assert "not set" in english["locked_key_required"]
    assert "does not match" in english["locked_key_mismatch"]
    assert "restart" in english["locked_key_required"].lower() and "restart" in english["locked_key_mismatch"].lower()
    assert "moved" in english["corrupt"] and "again" in english["corrupt"]
    for text in english.values():
        assert "Nothing was changed or sent" in text or "Nothing was sent" in text


def test_the_end_to_end_ui_text_mock_carries_the_english_notices():
    mock = json.loads((ROOT / "tests" / "e2e" / "mocks" / "ui-text.json").read_text(encoding="utf-8"))

    for key in STATE_KEYS.values():
        assert mock["en"][key] == ui_text("en")[key], key
