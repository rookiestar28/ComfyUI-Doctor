def test_harness_payload_shape_is_accepted():
    """T9: backend accepts harness-like minimal payload shape."""
    from services.prompt_composer import PromptComposer

    harness_payload = {
        "error_summary": "Sampler failed",
        "system_info": {"os": "Windows"},
        "node_context": {"node_id": 1, "node_class": "KSampler"},
    }

    composer = PromptComposer()
    prompt = composer.compose(
        llm_context={
            "error_summary": harness_payload["error_summary"],
            "system_info": harness_payload["system_info"],
            "node_context": harness_payload["node_context"],
        }
    )

    assert "Sampler failed" in prompt
    assert "Windows" in prompt

def test_pipeline_harness_integration():
    """T9: Verify we can construct a valid analysis payload for the harness."""
    from services.prompt_composer import PromptComposer
    
    # Simulate data that the harness would send
    harness_data = {
        "error_summary": "Test Error",
        "system_info": {"os": "Windows"},
        "node_context": {"node_id": 1}
    }
    
    composer = PromptComposer()
    context = {
        "error_summary": harness_data["error_summary"],
        "system_info": harness_data["system_info"],
        "node_context": harness_data["node_context"],
    }
    
    prompt = composer.compose(llm_context=context)
    
    assert "Test Error" in prompt
    assert "Windows" in prompt
