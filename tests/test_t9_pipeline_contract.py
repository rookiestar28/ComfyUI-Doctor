from pipeline.metadata_contract import validate_metadata_contract


def test_metadata_contract_schema_validation():
    """T9: Verify metadata schema validation works without ComfyUI runtime."""
    
    # 1. Valid Contract
    valid_data = {
        # "version": "1.0", -> metadata_schema_version is auto-added or validated
        "matched_pattern_id": "test_pattern",
        "category": "execution",
        "priority": 10
    }
    
    # Validation should pass (no exception) and return dict
    result = validate_metadata_contract(valid_data)
    assert result["metadata_schema_version"] == "v1"
    
    # 2. Invalid Contract (Invalid field type)
    invalid_data = valid_data.copy()
    invalid_data["priority"] = "high"  # Should be int
    
    result = validate_metadata_contract(invalid_data)
    # The current impl quarantines invalid keys, does not raise ValueError
    assert "priority" not in result
    assert "_invalid" in result
    assert result["_invalid"]["priority"] == "high"
        
    # 3. Invalid schema version should be quarantined
    invalid_version = {
        "metadata_schema_version": "v999",
        "matched_pattern_id": "x",
        "category": "execution",
        "priority": 1,
    }
    result = validate_metadata_contract(invalid_version)
    assert result["metadata_schema_version"] == "v1"
    assert result["matched_pattern_id"] == "x"
