"""Minimal environment-backed JSON extraction client factory."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


class OpenAIJSONClient:
    endpoint = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model_name: str = "gpt-4.1-mini"):
        self.api_key, self.model_name = api_key, model_name

    def extract_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        body = json.dumps({
            "model": kwargs.get("model") or self.model_name,
            "messages": [{"role": "system", "content": prompt}],
            "response_format": {"type": "json_object"}, "temperature": 0,
        }).encode("utf-8")
        request = urllib.request.Request(self.endpoint, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
        })
        with urllib.request.urlopen(request, timeout=int(kwargs.get("timeout", 60))) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content) if isinstance(content, str) else content
        if not isinstance(parsed, dict):
            raise ValueError("OpenAI response JSON must be an object")
        return parsed


class ConfiguredJSONClient:
    def __init__(self, client: Any, model_name: str | None = None):
        self.client, self.model_name = client, model_name

    def extract_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if self.model_name:
            kwargs["model"] = self.model_name
        return self.client.extract_json(prompt, **kwargs)


def build_l1_client_from_env_or_config(provider: str | None = None, model_name: str | None = None) -> Any | None:
    """Return a configured client without making a network request."""
    selected = (provider or os.getenv("L1_PROVIDER") or "").casefold()
    deepseek_key, openai_key = os.getenv("DEEPSEEK_API_KEY"), os.getenv("OPENAI_API_KEY")
    if not selected:
        selected = "deepseek" if deepseek_key else "openai" if openai_key else ""
    configured_model = model_name or os.getenv("MODEL_NAME")
    if selected == "deepseek" and deepseek_key:
        from code_engine.extraction.deepseek_client import DeepSeekClient
        return ConfiguredJSONClient(DeepSeekClient(deepseek_key), configured_model)
    if selected == "openai" and openai_key:
        return OpenAIJSONClient(openai_key, configured_model or "gpt-4.1-mini")
    return None


__all__ = ["OpenAIJSONClient", "build_l1_client_from_env_or_config"]
