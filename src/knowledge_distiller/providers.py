"""AI provider abstraction layer for summarization."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx


@runtime_checkable
class AIProvider(Protocol):
    async def complete(self, system: str, user: str) -> str: ...
    @property
    def model(self) -> str: ...


class GoogleProvider:
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self.api_key = api_key
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, system: str, user: str) -> str:
        url = f"{self.BASE_URL}/models/{self._model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.3},
        }
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Empty response from Google AI: {data}")
        return candidates[0]["content"]["parts"][0]["text"]


class OpenAIProvider:
    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str | None = None) -> None:
        self.api_key = api_key
        self._model = model
        self.base_url = base_url or self.BASE_URL

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, system: str, user: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]


class AnthropicProvider:
    BASE_URL = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
        self.api_key = api_key
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, system: str, user: str) -> str:
        url = f"{self.BASE_URL}/messages"
        payload = {
            "model": self._model,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["content"][0]["text"]


def build_provider(
    provider_name: str,
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
) -> AIProvider:
    """Factory: build an AIProvider from config values."""
    defaults = {
        "google": "gemini-2.5-flash",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-haiku-4-5-20251001",
    }
    match provider_name:
        case "google":
            return GoogleProvider(api_key, model or defaults["google"])
        case "openai":
            return OpenAIProvider(api_key, model or defaults["openai"], base_url)
        case "anthropic":
            return AnthropicProvider(api_key, model or defaults["anthropic"])
        case _:
            raise ValueError(f"Unknown provider: {provider_name}. Choose: google, openai, anthropic")
