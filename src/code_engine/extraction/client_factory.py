"""Minimal environment-backed JSON extraction client factory."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


def _positive_number(value: Any, default: float) -> float:
    try:
        parsed = float(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _nonnegative_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError):
        return default


def resolve_l1_timeout_config(*, connect_timeout_seconds: float | None = None,
                              read_timeout_seconds: float | None = None,
                              max_retries: int | None = None) -> dict[str, Any]:
    """Resolve CLI values over environment values over conservative defaults."""
    connect = connect_timeout_seconds if connect_timeout_seconds is not None else os.getenv("L1_CONNECT_TIMEOUT_SECONDS")
    read = read_timeout_seconds if read_timeout_seconds is not None else (os.getenv("L1_READ_TIMEOUT_SECONDS") or os.getenv("L1_TIMEOUT_SECONDS"))
    retries = max_retries if max_retries is not None else os.getenv("L1_MAX_RETRIES")
    return {"connect_timeout_seconds": _positive_number(connect, 20.0),
            "read_timeout_seconds": _positive_number(read, 120.0),
            "max_retries": _nonnegative_int(retries, 2)}


class OpenAIJSONClient:
    endpoint = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model_name: str = "gpt-4.1-mini"):
        self.api_key, self.model_name = api_key, model_name

    def extract_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        from code_engine.extraction.l1_response import normalize_l1_json_response
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
        parsed, warnings = normalize_l1_json_response(content)
        parsed["__l1_warnings"] = warnings
        parsed["__l1_raw_response"] = content
        return parsed


class ConfiguredJSONClient:
    def __init__(self, client: Any, model_name: str | None = None):
        self.client, self.model_name = client, model_name

    def extract_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if self.model_name:
            kwargs["model"] = self.model_name
        return self.client.extract_json(prompt, **kwargs)


def build_l1_client_from_env_or_config(provider: str | None = None, model_name: str | None = None,
                                       *, connect_timeout_seconds: float | None = None,
                                       read_timeout_seconds: float | None = None,
                                       max_retries: int | None = None) -> Any | None:
    """Return a configured client without making a network request."""
    selected = (provider or os.getenv("L1_PROVIDER") or "").casefold()
    deepseek_key, openai_key = os.getenv("DEEPSEEK_API_KEY"), os.getenv("OPENAI_API_KEY")
    if not selected:
        selected = "deepseek" if deepseek_key else "openai" if openai_key else ""
    configured_model = model_name or os.getenv("MODEL_NAME")
    timeout_config = resolve_l1_timeout_config(connect_timeout_seconds=connect_timeout_seconds,
                                               read_timeout_seconds=read_timeout_seconds,
                                               max_retries=max_retries)
    if selected == "deepseek" and deepseek_key:
        from code_engine.extraction.deepseek_client import DeepSeekClient
        return ConfiguredJSONClient(DeepSeekClient(deepseek_key, **timeout_config), configured_model)
    if selected == "openai" and openai_key:
        return OpenAIJSONClient(openai_key, configured_model or "gpt-4.1-mini")
    return None


__all__ = ["OpenAIJSONClient", "build_l1_client_from_env_or_config", "resolve_l1_timeout_config"]
