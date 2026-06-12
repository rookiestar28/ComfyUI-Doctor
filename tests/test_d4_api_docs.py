import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
API_REFERENCE_PATH = ROOT / "docs" / "API_REFERENCE.md"
OPENAPI_PATH = ROOT / "docs" / "openapi.json"

FORBIDDEN_PUBLIC_FRAGMENTS = [
    ".planning",
    "reference/",
    "REFERENCE/",
    "ROADMAP",
    "IMPLEMENTATION_RECORD",
    "command log",
    "validation evidence",
]


def _api_reference_text() -> str:
    return API_REFERENCE_PATH.read_text(encoding="utf-8")


def _openapi() -> dict:
    return json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))


def test_d4_api_reference_documents_host_route_alias_policy():
    text = _api_reference_text()

    assert "`/doctor/...`" in text
    assert "`/api/doctor/...`" in text
    assert "canonical" in text.lower()
    assert "host-provided alias" in text.lower()
    assert "ComfyUI route duplication" in text


def test_d4_api_reference_documents_prompt_usage_source_policy():
    text = _api_reference_text()

    assert "`comfyui-doctor`" in text
    assert "does not currently queue host prompts directly" in text
    for forbidden_data_class in [
        "secrets",
        "raw prompts",
        "private paths",
        "cookies",
        "credentials",
    ]:
        assert forbidden_data_class in text.lower()


def test_d4_openapi_description_records_alias_without_duplicate_paths():
    spec = _openapi()
    description = spec["info"]["description"]

    assert "/api/doctor/..." in description
    assert "host-provided alias" in description.lower()
    assert "comfyui-doctor" in description
    assert all(not path.startswith("/api/doctor/") for path in spec["paths"])


def test_d4_public_docs_do_not_expose_internal_records():
    public_texts = [
        _api_reference_text(),
        OPENAPI_PATH.read_text(encoding="utf-8"),
    ]

    for text in public_texts:
        for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
            assert fragment not in text
