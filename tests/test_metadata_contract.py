from pipeline.metadata_contract import (
    METADATA_SCHEMA_VERSION,
    MAX_STRING_LENGTH,
    validate_metadata_contract,
)


def test_metadata_contract_quarantines_invalid_fields():
    metadata = {
        "pipeline_status": "unknown",
        "matched_pattern_id": "pattern.bad",
        "category": "a" * (MAX_STRING_LENGTH + 1),
        "priority": "high",
        "match_source": "json_loader",
        "stage_errors": ["not-a-dict"],
        "extra": "value",
    }

    validated = validate_metadata_contract(metadata)

    assert validated["metadata_schema_version"] == METADATA_SCHEMA_VERSION
    assert validated["pipeline_status"] == "ok"
    assert validated["matched_pattern_id"] == "pattern.bad"
    assert validated["match_source"] == "json_loader"

    invalid = validated.get("_invalid", {})
    assert "category" in invalid
    assert "priority" in invalid
    assert "stage_errors" in invalid
    assert "extra" in invalid

