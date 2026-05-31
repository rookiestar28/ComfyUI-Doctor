"""
Internationalization (i18n) loader for ComfyUI Runtime Diagnostics.

Translation data lives in i18n_data/<language>.json so translators can edit
localized UI text and suggestions without touching Python source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

# ============================================================================
# CRITICAL: Default Language Configuration
# ============================================================================
# WARNING: DO NOT change this default to any language other than "en".
# This is the fallback language used before user settings are applied and it
# matches frontend DEFAULTS.LANGUAGE in web/doctor.js.
_current_language = "en"

SUPPORTED_LANGUAGES = ['en', 'zh_TW', 'zh_CN', 'ja', 'de', 'fr', 'it', 'es', 'ko']

ERROR_KEYS = {'TYPE_MISMATCH': 'type_mismatch',
 'DIMENSION_MISMATCH': 'dimension_mismatch',
 'OOM': 'oom',
 'MATRIX_MULT': 'matrix_mult',
 'DEVICE_TYPE': 'device_type',
 'MISSING_MODULE': 'missing_module',
 'ASSERTION': 'assertion',
 'KEY_ERROR': 'key_error',
 'ATTRIBUTE_ERROR': 'attribute_error',
 'SHAPE_MISMATCH': 'shape_mismatch',
 'FILE_NOT_FOUND': 'file_not_found',
 'TORCH_OOM': 'torch_oom',
 'AUTOGRAD': 'autograd',
 'SAFETENSORS_ERROR': 'safetensors_error',
 'CUDNN_ERROR': 'cudnn_error',
 'MISSING_INSIGHTFACE': 'missing_insightface',
 'MODEL_VAE_MISMATCH': 'model_vae_mismatch',
 'MPS_OOM': 'mps_oom',
 'INVALID_PROMPT': 'invalid_prompt',
 'VALIDATION_ERROR': 'validation_error',
 'TENSOR_NAN_INF': 'tensor_nan_inf',
 'META_TENSOR': 'meta_tensor',
 'MISSING_INPUT': 'missing_input',
 'CONTROLNET_MODEL_NOT_FOUND': 'controlnet_model_not_found',
 'CONTROLNET_PREPROCESSOR_FAILED': 'controlnet_preprocessor_failed',
 'CONTROLNET_SIZE_MISMATCH': 'controlnet_size_mismatch',
 'CONTROLNET_UNSUPPORTED_MODEL': 'controlnet_unsupported_model',
 'CONTROLNET_INVALID_STRENGTH': 'controlnet_invalid_strength',
 'CONTROLNET_MISSING_PREPROCESSOR': 'controlnet_missing_preprocessor',
 'CONTROLNET_CHANNEL_MISMATCH': 'controlnet_channel_mismatch',
 'CONTROLNET_DEVICE_MISMATCH': 'controlnet_device_mismatch',
 'LORA_NOT_FOUND': 'lora_not_found',
 'LORA_INCOMPATIBLE': 'lora_incompatible',
 'LORA_CORRUPTED': 'lora_corrupted',
 'LORA_STRENGTH_INVALID': 'lora_strength_invalid',
 'LORA_OOM': 'lora_oom',
 'LORA_KEY_MISMATCH': 'lora_key_mismatch',
 'VAE_DECODE_FAILED': 'vae_decode_failed',
 'VAE_ENCODE_FAILED': 'vae_encode_failed',
 'VAE_TILING_ERROR': 'vae_tiling_error',
 'VAE_FP16_ISSUE': 'vae_fp16_issue',
 'VAE_BATCH_SIZE_ERROR': 'vae_batch_size_error',
 'ANIMATEDIFF_MODEL_NOT_FOUND': 'animatediff_model_not_found',
 'ANIMATEDIFF_FRAME_MISMATCH': 'animatediff_frame_mismatch',
 'ANIMATEDIFF_CONTEXT_ERROR': 'animatediff_context_error',
 'ANIMATEDIFF_OOM': 'animatediff_oom',
 'IPADAPTER_MODEL_NOT_FOUND': 'ipadapter_model_not_found',
 'IPADAPTER_IMAGE_ENCODING_FAILED': 'ipadapter_image_encoding_failed',
 'IPADAPTER_INCOMPATIBLE': 'ipadapter_incompatible',
 'IPADAPTER_WEIGHT_ERROR': 'ipadapter_weight_error',
 'FACERESTORE_MODEL_NOT_FOUND': 'facerestore_model_not_found',
 'FACERESTORE_DETECTION_FAILED': 'facerestore_detection_failed',
 'FACERESTORE_OOM': 'facerestore_oom',
 'CHECKPOINT_CORRUPTED': 'checkpoint_corrupted',
 'IMAGE_FORMAT_UNSUPPORTED': 'image_format_unsupported',
 'SAMPLER_NOT_FOUND': 'sampler_not_found',
 'SCHEDULER_ERROR': 'scheduler_error',
 'CLIP_ENCODING_ERROR': 'clip_encoding_error',
 'VALUE_NOT_IN_LIST': 'value_not_in_list'}

I18N_DATA_DIR = Path(__file__).resolve().with_name("i18n_data")
SUGGESTION_PREFIX = "\U0001f4a1 SUGGESTION: "


class I18nDataError(RuntimeError):
    """Raised when translation data is missing or malformed."""


def _require_string_mapping(value: Any, *, field: str, language: str) -> Dict[str, str]:
    if not isinstance(value, dict):
        raise I18nDataError(f"{language}: {field} must be an object")

    result: Dict[str, str] = {}
    for key, text in value.items():
        if not isinstance(key, str):
            raise I18nDataError(f"{language}: {field} contains a non-string key")
        if not isinstance(text, str):
            raise I18nDataError(f"{language}: {field}.{key} must be a string")
        result[key] = text
    return result


def _load_language_file(path: Path, expected_language: str) -> Dict[str, Dict[str, str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise I18nDataError(f"{expected_language}: invalid JSON in {path.name}: {exc}") from exc
    except OSError as exc:
        raise I18nDataError(f"{expected_language}: cannot read {path.name}: {exc}") from exc

    if not isinstance(raw, dict):
        raise I18nDataError(f"{expected_language}: language file root must be an object")
    if raw.get("language") != expected_language:
        raise I18nDataError(
            f"{expected_language}: language marker mismatch in {path.name} "
            f"(got {raw.get('language')!r})"
        )

    return {
        "ui_text": _require_string_mapping(raw.get("ui_text"), field="ui_text", language=expected_language),
        "suggestions": _require_string_mapping(raw.get("suggestions"), field="suggestions", language=expected_language),
    }


def _validate_loaded_data(ui_text: Dict[str, Dict[str, str]], suggestions: Dict[str, Dict[str, str]]) -> None:
    missing_ui_languages = [lang for lang in SUPPORTED_LANGUAGES if lang not in ui_text]
    missing_suggestion_languages = [lang for lang in SUPPORTED_LANGUAGES if lang not in suggestions]
    if missing_ui_languages or missing_suggestion_languages:
        raise I18nDataError(
            "Missing i18n languages: "
            f"ui_text={missing_ui_languages}, suggestions={missing_suggestion_languages}"
        )

    required_suggestion_keys = set(ERROR_KEYS.values())
    for lang in SUPPORTED_LANGUAGES:
        missing = sorted(required_suggestion_keys - set(suggestions[lang]))
        if missing:
            raise I18nDataError(f"{lang}: missing suggestion translations: {', '.join(missing)}")


def _load_translation_data(data_dir: Path = I18N_DATA_DIR) -> tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
    ui_text: Dict[str, Dict[str, str]] = {}
    suggestions: Dict[str, Dict[str, str]] = {}

    for lang in SUPPORTED_LANGUAGES:
        payload = _load_language_file(data_dir / f"{lang}.json", lang)
        ui_text[lang] = payload["ui_text"]
        suggestions[lang] = payload["suggestions"]

    _validate_loaded_data(ui_text, suggestions)
    return ui_text, suggestions


UI_TEXT, SUGGESTIONS = _load_translation_data()


def set_language(lang: str) -> bool:
    """
    Set the current language for suggestions.

    Args:
        lang: Language code (e.g., 'en', 'zh_TW', 'zh_CN', 'ja')

    Returns:
        True if language was set successfully, False otherwise.
    """
    global _current_language
    if lang in SUPPORTED_LANGUAGES:
        _current_language = lang
        return True
    return False


def get_language() -> str:
    """Get the current language setting."""
    return _current_language


def get_suggestion(key: str, *args) -> Optional[str]:
    """
    Get a localized suggestion by key.

    Args:
        key: The suggestion key (from ERROR_KEYS values)
        *args: Format arguments for the suggestion template

    Returns:
        Formatted localized suggestion, or None if key not found.
    """
    lang_dict = SUGGESTIONS.get(_current_language, SUGGESTIONS["en"])
    template = lang_dict.get(key)

    if template is None:
        template = SUGGESTIONS["en"].get(key)

    if template is None:
        return None

    try:
        if args:
            return SUGGESTION_PREFIX + template.format(*args)
        return SUGGESTION_PREFIX + template
    except (IndexError, KeyError):
        return SUGGESTION_PREFIX + template


def get_ui_text(key: str, lang: Optional[str] = None) -> str:
    """
    Get localized UI text by key.

    Args:
        key: The UI text key (from UI_TEXT values)
        lang: Optional language override (defaults to current language)

    Returns:
        Localized UI text, or English fallback if key not found.
    """
    target_lang = lang if lang else _current_language
    lang_dict = UI_TEXT.get(target_lang, UI_TEXT["en"])
    text = lang_dict.get(key)

    if text is None:
        text = UI_TEXT["en"].get(key, f"[Missing: {key}]")

    return text
