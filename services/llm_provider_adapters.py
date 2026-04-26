"""Dedicated LLM provider adapters for chat/analyze/list-model dispatch."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

try:
    from ..security import parse_base_url
except ImportError as import_error:
    from import_compat import ensure_absolute_import_fallback_allowed

    ensure_absolute_import_fallback_allowed(import_error)
    from security import parse_base_url


@dataclass(frozen=True)
class LLMProviderRequest:
    """Prepared HTTP request data for an LLM provider call."""

    url: str
    headers: Dict[str, str]
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMStreamParseResult:
    """Normalized result for one provider stream line."""

    delta: str = ""
    done: bool = False
    skip: bool = False


class LLMProviderAdapter(Protocol):
    """Contract for LLM chat/analyze/list-model provider behavior."""

    provider_id: str

    def build_chat_request(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        *,
        stream: bool,
        temperature: float,
    ) -> LLMProviderRequest:
        ...

    def parse_chat_response(self, data: Dict[str, Any]) -> str:
        ...

    def parse_stream_line(self, line: str) -> LLMStreamParseResult:
        ...

    def build_models_request(self, base_url: str, api_key: str) -> LLMProviderRequest:
        ...

    def parse_models_response(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        ...


class OpenAICompatibleLLMProviderAdapter:
    """Adapter for OpenAI-compatible chat completion providers."""

    provider_id = "openai_compatible"

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        base_url = base_url.rstrip("/")
        base_info = parse_base_url(base_url)
        hostname = (base_info.get("hostname") if base_info else "") or ""
        if not base_url.endswith("/v1") and hostname.lower().endswith(("openai.com", "deepseek.com")):
            return f"{base_url}/v1"
        return base_url

    def build_chat_request(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        *,
        stream: bool,
        temperature: float,
    ) -> LLMProviderRequest:
        normalized_base = self._normalize_base_url(base_url)
        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages.extend(messages)
        return LLMProviderRequest(
            url=f"{normalized_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            payload={
                "model": model,
                "messages": api_messages,
                "temperature": temperature,
                "stream": stream,
            },
        )

    def parse_chat_response(self, data: Dict[str, Any]) -> str:
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def parse_stream_line(self, line: str) -> LLMStreamParseResult:
        if not line.startswith("data:"):
            return LLMStreamParseResult(skip=True)
        payload_str = line[5:].strip()
        if payload_str == "[DONE]":
            return LLMStreamParseResult(done=True)
        if not payload_str:
            return LLMStreamParseResult(skip=True)
        chunk_json = json.loads(payload_str)
        delta = chunk_json.get("choices", [{}])[0].get("delta", {}).get("content", "")
        return LLMStreamParseResult(delta=delta, skip=not bool(delta))

    def build_models_request(self, base_url: str, api_key: str) -> LLMProviderRequest:
        return LLMProviderRequest(
            url=f"{self._normalize_base_url(base_url)}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def parse_models_response(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        models = []
        for model in data.get("data", []):
            model_id = model.get("id", "")
            if model_id:
                models.append({"id": model_id, "name": model_id})
        return models


class AnthropicLLMProviderAdapter:
    """Adapter for Anthropic Messages API."""

    provider_id = "anthropic"

    def build_chat_request(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        *,
        stream: bool,
        temperature: float,
    ) -> LLMProviderRequest:
        base_url = base_url.rstrip("/")
        return LLMProviderRequest(
            url=f"{base_url}/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload={
                "model": model,
                "system": system_prompt,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": temperature,
                "stream": stream,
            },
        )

    def parse_chat_response(self, data: Dict[str, Any]) -> str:
        return data.get("content", [{}])[0].get("text", "")

    def parse_stream_line(self, line: str) -> LLMStreamParseResult:
        if not line.startswith("data:"):
            return LLMStreamParseResult(skip=True)
        payload_str = line[5:].strip()
        if not payload_str:
            return LLMStreamParseResult(skip=True)
        chunk_json = json.loads(payload_str)
        event_type = chunk_json.get("type", "")
        if event_type == "message_stop":
            return LLMStreamParseResult(done=True)
        if event_type == "content_block_delta":
            delta = chunk_json.get("delta", {}).get("text", "")
            return LLMStreamParseResult(delta=delta, skip=not bool(delta))
        return LLMStreamParseResult(skip=True)

    def build_models_request(self, base_url: str, api_key: str) -> LLMProviderRequest:
        base_url = base_url.rstrip("/")
        return LLMProviderRequest(
            url=f"{base_url}/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )

    def parse_models_response(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        models = []
        for model in data.get("data", []):
            model_id = model.get("id", "")
            if model_id:
                models.append({"id": model_id, "name": model_id})
        return models


class OllamaLLMProviderAdapter:
    """Adapter for Ollama chat and tag APIs."""

    provider_id = "ollama"

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        base_url = base_url.rstrip("/")
        if base_url.endswith("/v1"):
            return base_url[:-3]
        return base_url

    def build_chat_request(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        *,
        stream: bool,
        temperature: float,
    ) -> LLMProviderRequest:
        normalized_base = self._normalize_base_url(base_url)
        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages.extend(messages)
        return LLMProviderRequest(
            url=f"{normalized_base}/api/chat",
            headers={"Content-Type": "application/json"},
            payload={
                "model": model,
                "messages": api_messages,
                "temperature": temperature,
                "stream": stream,
            },
        )

    def parse_chat_response(self, data: Dict[str, Any]) -> str:
        return data.get("message", {}).get("content", "")

    def parse_stream_line(self, line: str) -> LLMStreamParseResult:
        chunk_json = json.loads(line)
        if chunk_json.get("done", False):
            return LLMStreamParseResult(done=True)
        delta = chunk_json.get("message", {}).get("content", "")
        return LLMStreamParseResult(delta=delta, skip=not bool(delta))

    def build_models_request(self, base_url: str, api_key: str) -> LLMProviderRequest:
        normalized_base = self._normalize_base_url(base_url)
        return LLMProviderRequest(
            url=f"{normalized_base}/api/tags",
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def parse_models_response(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        models = []
        for model in data.get("models", []):
            model_name = model.get("name", model.get("model", ""))
            if model_name:
                models.append({"id": model_name, "name": model_name})
        return models


def is_anthropic_base_url(base_url: str) -> bool:
    """Return whether a validated base URL targets Anthropic."""
    info = parse_base_url(base_url)
    hostname = (info.get("hostname") if info else "") or ""
    return "anthropic.com" in hostname.lower()


def get_llm_provider_adapter(base_url: str, *, is_local: bool) -> LLMProviderAdapter:
    """Select an LLM provider adapter for a validated base URL."""
    base_info = parse_base_url(base_url.rstrip("/"))
    if is_local and base_info and base_info.get("port") == 11434:
        return OllamaLLMProviderAdapter()
    if is_anthropic_base_url(base_url):
        return AnthropicLLMProviderAdapter()
    return OpenAICompatibleLLMProviderAdapter()


__all__ = [
    "AnthropicLLMProviderAdapter",
    "LLMProviderAdapter",
    "LLMProviderRequest",
    "LLMStreamParseResult",
    "OllamaLLMProviderAdapter",
    "OpenAICompatibleLLMProviderAdapter",
    "get_llm_provider_adapter",
    "is_anthropic_base_url",
]
