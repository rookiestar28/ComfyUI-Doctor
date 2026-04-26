from pathlib import Path


def _package_entrypoint_text() -> str:
    project_root = Path(__file__).resolve().parent.parent
    entrypoint = project_root / "__init__.py"
    if not entrypoint.exists():
        entrypoint = project_root / "__init__.py.bak"
    return entrypoint.read_text(encoding="utf-8")


def test_llm_provider_factory_selects_supported_provider_shapes():
    from services.llm_provider_adapters import (
        AnthropicLLMProviderAdapter,
        OllamaLLMProviderAdapter,
        OpenAICompatibleLLMProviderAdapter,
        get_llm_provider_adapter,
    )

    assert isinstance(
        get_llm_provider_adapter("https://api.openai.com/v1", is_local=False),
        OpenAICompatibleLLMProviderAdapter,
    )
    assert isinstance(
        get_llm_provider_adapter("https://api.anthropic.com", is_local=False),
        AnthropicLLMProviderAdapter,
    )
    assert isinstance(
        get_llm_provider_adapter("http://localhost:11434", is_local=True),
        OllamaLLMProviderAdapter,
    )


def test_llm_provider_adapters_build_requests_and_parse_non_stream_responses():
    from services.llm_provider_adapters import get_llm_provider_adapter

    openai = get_llm_provider_adapter("https://api.openai.com", is_local=False)
    openai_request = openai.build_chat_request(
        "https://api.openai.com",
        "sk-test",
        "gpt-4o",
        "system",
        [{"role": "user", "content": "hello"}],
        stream=False,
        temperature=0.5,
    )
    assert openai_request.url == "https://api.openai.com/v1/chat/completions"
    assert openai_request.headers["Authorization"] == "Bearer sk-test"
    assert openai_request.payload["messages"][0] == {"role": "system", "content": "system"}
    assert openai.parse_chat_response({"choices": [{"message": {"content": "ok"}}]}) == "ok"

    anthropic = get_llm_provider_adapter("https://api.anthropic.com", is_local=False)
    anthropic_request = anthropic.build_chat_request(
        "https://api.anthropic.com",
        "anthropic-key",
        "claude",
        "system",
        [{"role": "user", "content": "hello"}],
        stream=False,
        temperature=0.7,
    )
    assert anthropic_request.url == "https://api.anthropic.com/v1/messages"
    assert anthropic_request.headers["x-api-key"] == "anthropic-key"
    assert anthropic_request.payload["system"] == "system"
    assert anthropic.parse_chat_response({"content": [{"text": "ok"}]}) == "ok"

    ollama = get_llm_provider_adapter("http://localhost:11434/v1", is_local=True)
    ollama_request = ollama.build_chat_request(
        "http://localhost:11434/v1",
        "local-llm",
        "llama3",
        "system",
        [{"role": "user", "content": "hello"}],
        stream=False,
        temperature=0.7,
    )
    assert ollama_request.url == "http://localhost:11434/api/chat"
    assert ollama_request.payload["messages"][0] == {"role": "system", "content": "system"}
    assert ollama.parse_chat_response({"message": {"content": "ok"}}) == "ok"


def test_llm_provider_adapters_parse_stream_and_models():
    from services.llm_provider_adapters import get_llm_provider_adapter

    openai = get_llm_provider_adapter("https://api.openai.com/v1", is_local=False)
    openai_chunk = openai.parse_stream_line('data: {"choices":[{"delta":{"content":"hi"}}]}')
    assert openai_chunk.delta == "hi"
    assert not openai_chunk.done
    assert openai.parse_stream_line("data: [DONE]").done
    assert openai.parse_models_response({"data": [{"id": "gpt-4o"}]}) == [
        {"id": "gpt-4o", "name": "gpt-4o"}
    ]

    anthropic = get_llm_provider_adapter("https://api.anthropic.com", is_local=False)
    anthropic_chunk = anthropic.parse_stream_line(
        'data: {"type":"content_block_delta","delta":{"text":"hi"}}'
    )
    assert anthropic_chunk.delta == "hi"
    assert anthropic.parse_stream_line('data: {"type":"message_stop"}').done

    ollama = get_llm_provider_adapter("http://localhost:11434", is_local=True)
    ollama_chunk = ollama.parse_stream_line('{"message":{"content":"hi"},"done":false}')
    assert ollama_chunk.delta == "hi"
    assert ollama.parse_stream_line('{"done":true}').done
    assert ollama.parse_models_response({"models": [{"name": "llama3"}]}) == [
        {"id": "llama3", "name": "llama3"}
    ]


def test_routes_delegate_provider_specific_logic_to_llm_adapters():
    source = _package_entrypoint_text()

    assert "get_llm_provider_adapter" in source
    assert "is_ollama =" not in source
    assert "is_anthropic_api" not in source
    assert "resp_data.get('choices'" not in source
    assert "chunk_json.get('choices'" not in source
    assert "/api/tags" not in source
