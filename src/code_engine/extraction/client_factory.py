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


def _chat_messages(prompt: Any) -> list[dict[str, Any]]:
    return prompt if isinstance(prompt, list) else [{"role": "system", "content": prompt}]


class OpenAIJSONClient:
    endpoint = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model_name: str = "gpt-4.1-mini"):
        self.api_key, self.model_name = api_key, model_name

    def extract_json_result(self, prompt: Any, **kwargs: Any) -> Any:
        from code_engine.extraction.l1_response import parse_json_object_response
        from code_engine.extraction.deepseek_client import JSONExtractionResult
        request_payload = {
            "model": kwargs.get("model") or self.model_name,
            "messages": _chat_messages(prompt),
            "response_format": {"type": "json_object"}, "temperature": 0,
        }
        if kwargs.get("max_tokens") is not None:
            request_payload["max_tokens"] = int(kwargs["max_tokens"])
        body = json.dumps(request_payload).encode("utf-8")
        request = urllib.request.Request(self.endpoint, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
        })
        with urllib.request.urlopen(request, timeout=int(kwargs.get("timeout", 60))) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        parsed, warnings = parse_json_object_response(content)
        return JSONExtractionResult(payload=parsed, raw_response=content, warnings=list(warnings),
            finish_reason=payload["choices"][0].get("finish_reason"), usage=dict(payload.get("usage") or {}),
            provider_metadata={"provider": "openai", "model": request_payload["model"],
                "response_format": {"type": "json_object"}, "json_output_enabled": True,
                "max_tokens": kwargs.get("max_tokens"), "http_status": getattr(response, "status", 200)})

    def extract_json(self, prompt: Any, **kwargs: Any) -> dict[str, Any]:
        return self.extract_json_result(prompt, **kwargs).payload


class ConfiguredJSONClient:
    def __init__(self, client: Any, model_name: str | None = None):
        self.client, self.model_name = client, model_name

    def extract_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if self.model_name:
            kwargs["model"] = self.model_name
        return self.client.extract_json(prompt, **kwargs)

    def extract_json_result(self, prompt: str, **kwargs: Any) -> Any:
        if self.model_name:
            kwargs["model"] = self.model_name
        method = getattr(self.client, "extract_json_result", None)
        if method is None:
            payload = self.client.extract_json(prompt, **kwargs)
            from code_engine.extraction.deepseek_client import JSONExtractionResult
            return JSONExtractionResult(payload=payload, raw_response=json.dumps(payload, ensure_ascii=False))
        return method(prompt, **kwargs)


def _select_json_provider(provider: str | None = None) -> str:
    selected = (provider or "").casefold()
    deepseek_key, openai_key = os.getenv("DEEPSEEK_API_KEY"), os.getenv("OPENAI_API_KEY")
    if not selected:
        selected = "deepseek" if deepseek_key else "openai" if openai_key else ""
    return selected


def build_json_client_from_config(provider: str | None = None, model_name: str | None = None,
                                  *, connect_timeout_seconds: float | None = None,
                                  read_timeout_seconds: float | None = None,
                                  max_retries: int | None = None) -> Any | None:
    """Return a configured JSON client without making a network request."""
    selected = _select_json_provider(provider)
    deepseek_key, openai_key = os.getenv("DEEPSEEK_API_KEY"), os.getenv("OPENAI_API_KEY")
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


def build_l1_client_from_env_or_config(provider: str | None = None, model_name: str | None = None,
                                       *, connect_timeout_seconds: float | None = None,
                                       read_timeout_seconds: float | None = None,
                                       max_retries: int | None = None) -> Any | None:
    """Return a configured L1 client without making a network request."""
    return build_json_client_from_config(
        provider or os.getenv("L1_PROVIDER"),
        model_name or os.getenv("MODEL_NAME"),
        connect_timeout_seconds=connect_timeout_seconds,
        read_timeout_seconds=read_timeout_seconds,
        max_retries=max_retries,
    )


def diagnose_json_provider(provider: str | None = None, model_name: str | None = None, *, api_enabled: bool = True,
                           network_enabled: bool = True, config_source: str = "env", scope: str = "json") -> dict[str, Any]:
    selected = _select_json_provider(provider)
    credential = {"deepseek": "DEEPSEEK_API_KEY", "openai": "OPENAI_API_KEY"}.get(selected)
    present = bool(credential and os.getenv(credential))
    configured_model = model_name or os.getenv("MODEL_NAME")
    if not api_enabled:
        error = "api_disabled"
    elif not network_enabled:
        error = "network_disabled"
    elif not selected:
        error = "provider_not_configured"
    elif selected not in {"deepseek", "openai"}:
        error = "provider_unsupported"
    elif not configured_model:
        error = "model_not_configured"
    elif not present:
        error = "credential_missing"
    else:
        error = None
    return {
        "scope": scope,
        "provider": selected or None,
        "model": configured_model,
        "provider_config_source": config_source,
        "provider_available": error is None,
        "credential_checked": bool(credential),
        "credential_name_checked": credential,
        "credential_name": credential,
        "credential_present": present,
        "provider_error": error,
    }


def build_entity_cleaner_client_from_config(provider: str | None = None, model_name: str | None = None,
                                            *, connect_timeout_seconds: float | None = None,
                                            read_timeout_seconds: float | None = None,
                                            max_retries: int | None = None) -> Any | None:
    """Return the L2 entity cleaner JSON client using L2 config with L1-compatible fallback."""
    selected = provider or os.getenv("L2_ENTITY_CLEANER_PROVIDER") or os.getenv("L1_PROVIDER")
    configured_model = model_name or os.getenv("L2_ENTITY_CLEANER_MODEL") or os.getenv("MODEL_NAME")
    if not diagnose_entity_cleaner_provider(selected, configured_model)["provider_available"]:
        return None
    return build_json_client_from_config(
        selected,
        configured_model,
        connect_timeout_seconds=connect_timeout_seconds,
        read_timeout_seconds=read_timeout_seconds,
        max_retries=max_retries,
    )


def diagnose_entity_cleaner_provider(provider: str | None = None, model_name: str | None = None, *,
                                     api_enabled: bool = True, network_enabled: bool = True) -> dict[str, Any]:
    selected = provider or os.getenv("L2_ENTITY_CLEANER_PROVIDER") or os.getenv("L1_PROVIDER")
    configured_model = model_name or os.getenv("L2_ENTITY_CLEANER_MODEL") or os.getenv("MODEL_NAME")
    return diagnose_json_provider(
        selected,
        configured_model,
        api_enabled=api_enabled,
        network_enabled=network_enabled,
        config_source="L2_ENTITY_CLEANER_* with L1 fallback",
        scope="l2_entity_cleaner",
    )


def diagnose_l1_provider(provider: str | None = None, model_name: str | None = None, *, api_enabled: bool=True,
                         network_enabled: bool=True, config_source: str="env") -> dict[str, Any]:
    selected=(provider or os.getenv("L1_PROVIDER") or "").casefold()
    if not selected:selected="deepseek" if os.getenv("DEEPSEEK_API_KEY") else "openai" if os.getenv("OPENAI_API_KEY") else ""
    credential={"deepseek":"DEEPSEEK_API_KEY","openai":"OPENAI_API_KEY"}.get(selected)
    present=bool(credential and os.getenv(credential))
    available=bool(api_enabled and network_enabled and selected in {"deepseek","openai"} and present)
    return {"scope":"fulltext","provider":selected or None,"model":model_name or os.getenv("MODEL_NAME"),
        "provider_config_source":config_source,"provider_available":available,"credential_checked":bool(credential),
        "credential_name_checked":credential,"credential_name":credential,"credential_present":present,
        "provider_error":None if available else "api_disabled" if not api_enabled else "network_disabled" if not network_enabled else "provider_not_configured" if not selected else "credential_missing"}


__all__ = [
    "OpenAIJSONClient",
    "build_json_client_from_config",
    "build_l1_client_from_env_or_config",
    "build_entity_cleaner_client_from_config",
    "diagnose_json_provider",
    "diagnose_entity_cleaner_provider",
    "diagnose_l1_provider",
    "resolve_l1_timeout_config",
]
