"""Small DeepSeek JSON client with retries and structured failures."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True)
class JSONExtractionResult:
    """A provider response whose transport data is kept outside scientific JSON."""

    payload: dict[str, Any]
    raw_response: str
    warnings: list[str] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    attempt_count: int = 1
    provider_metadata: dict[str, Any] = field(default_factory=dict)


class DeepSeekExtractionError(RuntimeError):
    def __init__(self, code: str, message: str, attempts: int, *,
                 error_kind: str = "unknown", retryable: bool = False,
                 raw_response: Any = None, status_code: int | None = None,
                 finish_reason: str | None = None, usage: dict[str, Any] | None = None,
                 provider_metadata: dict[str, Any] | None = None,
                 cause: Exception | None = None):
        super().__init__(message)
        self.error_kind = error_kind
        self.retryable = retryable
        self.raw_response = raw_response
        self.status_code = status_code
        self.finish_reason = finish_reason
        self.usage = dict(usage or {})
        self.provider_metadata = dict(provider_metadata or {})
        self.cause = cause
        self.attempts = attempts
        self.details = {
            "code": code, "message": message, "attempts": attempts,
            "error_kind": error_kind, "retryable": retryable,
            "status_code": status_code, "finish_reason": finish_reason,
            "usage": self.usage, "provider_metadata": self.provider_metadata,
        }


def _error_metadata(exc: Exception) -> tuple[str, bool, int | None]:
    """Classify failures without relying on provider error-message wording."""
    from code_engine.extraction.l1_response import GenericJSONResponseError

    if isinstance(exc, GenericJSONResponseError):
        kind = "malformed_json" if exc.error_type == "json_parse_failed" else "schema_parse_failure"
        return kind, True, None
    if isinstance(exc, json.JSONDecodeError):
        return "malformed_json", True, None
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 401:
            return "authentication", False, status
        if status == 403:
            return "authorization", False, status
        if status == 429:
            return "rate_limit", True, status
        if status >= 500:
            return "provider_server_error", True, status
        if status in {400, 404, 409, 422}:
            return "configuration", False, status
        return "unknown", False, status
    if isinstance(exc, httpx.TimeoutException) or isinstance(exc, TimeoutError):
        return "timeout", True, None
    if isinstance(exc, httpx.TransportError):
        return "transport", True, None
    if isinstance(exc, KeyError):
        return "schema_parse_failure", True, None
    return "unknown", False, None


class DeepSeekClient:
    endpoint = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self, api_key: str | None = None, *, connect_timeout_seconds: float = 20.0,
                 read_timeout_seconds: float = 120.0, max_retries: int = 2, sleep_fn=time.sleep):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for --execute --api")
        self.max_retries = max_retries
        self.connect_timeout_seconds = float(connect_timeout_seconds)
        self.read_timeout_seconds = float(read_timeout_seconds)
        self.sleep_fn = sleep_fn

    def extract_json_result(self, prompt: Any, model: str = "deepseek-v4-pro",
                            temperature: float = 0.0, top_p: float = 1.0,
                            max_tokens: int | None = None, retry_on_length: bool = False,
                            **_: Any) -> JSONExtractionResult:
        from code_engine.extraction.l1_response import GenericJSONResponseError, parse_json_object_response
        messages = prompt if isinstance(prompt, list) else [{"role": "system", "content": prompt}]
        request_payload = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "top_p": top_p,
        }
        if max_tokens is not None:
            request_payload["max_tokens"] = int(max_tokens)
        body = json.dumps(request_payload).encode("utf-8")
        last_error = "unknown_error"
        last_exception: Exception | None = None
        last_raw_response: Any = None
        last_finish_reason: str | None = None
        last_usage: dict[str, Any] = {}
        last_provider_metadata: dict[str, Any] = {}
        attempts = self.max_retries + 1
        timeout = httpx.Timeout(connect=self.connect_timeout_seconds, read=self.read_timeout_seconds,
                                write=self.connect_timeout_seconds, pool=self.connect_timeout_seconds)
        for attempt in range(1, attempts + 1):
            last_raw_response = None
            last_finish_reason = None
            started = time.monotonic()
            try:
                response = httpx.post(self.endpoint, content=body, headers={
                    "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                }, timeout=timeout)
                response.raise_for_status()
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                last_raw_response = content
                last_finish_reason = payload["choices"][0].get("finish_reason")
                last_usage = dict(payload.get("usage") or {})
                last_provider_metadata = {
                    "provider": "deepseek", "model": model,
                    "response_format": {"type": "json_object"},
                    "json_output_enabled": True, "max_tokens": max_tokens,
                    "http_status": getattr(response, "status_code", 200),
                    "latency_seconds": time.monotonic() - started,
                }
                if content is None or not str(content).strip():
                    empty = ValueError("empty_json_content")
                    empty.error_type = "empty_json_content"  # type: ignore[attr-defined]
                    raise empty
                try:
                    parsed, warnings = parse_json_object_response(content)
                except GenericJSONResponseError as exc:
                    exc.raw_response = content
                    raise
                return JSONExtractionResult(
                    payload=parsed, raw_response=content, warnings=list(warnings),
                    finish_reason=last_finish_reason, usage=last_usage,
                    attempt_count=attempt, provider_metadata=last_provider_metadata,
                )
            except (httpx.HTTPError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
                last_error = str(exc)
                last_exception = exc
                if isinstance(exc, json.JSONDecodeError) and "response" in locals():
                    last_raw_response = response.text
                _, retryable, _ = _error_metadata(exc)
                if getattr(exc, "error_type", None) == "empty_json_content":
                    retryable = True
                # Retrying an identical request cannot repair an exhausted output
                # budget. The caller must reduce the scientific unit instead.
                if last_finish_reason == "length" and not retry_on_length:
                    retryable = False
                if not retryable:
                    attempts = attempt
                    break
            if attempt < attempts:
                self.sleep_fn(2 ** attempt)
        assert last_exception is not None
        error_kind, retryable, status_code = _error_metadata(last_exception)
        if getattr(last_exception, "error_type", None) == "empty_json_content":
            error_kind, retryable = "empty_json_content", True
        if last_finish_reason == "length":
            error_kind, retryable = ("malformed_json", True) if retry_on_length else ("output_truncated", False)
        error = DeepSeekExtractionError(
            "deepseek_extraction_failed", last_error, attempts,
            error_kind=error_kind, retryable=retryable,
            raw_response=getattr(last_exception, "raw_response", last_raw_response),
            status_code=status_code, finish_reason=last_finish_reason,
            usage=last_usage, provider_metadata=last_provider_metadata,
            cause=last_exception,
        )
        is_timeout = isinstance(last_exception, httpx.TimeoutException) or "timed out" in last_error.casefold() or "timeout" in last_error.casefold()
        error.error_type = "timeout" if is_timeout else getattr(last_exception, "error_type", "api_error")
        error.parsed_json_type = getattr(last_exception, "parsed_json_type", "unknown")
        error.provider = "deepseek"; error.model = model
        error.timeout_type = "read_timeout" if isinstance(last_exception, httpx.ReadTimeout) else "connect_timeout" if isinstance(last_exception, httpx.ConnectTimeout) else "unknown_timeout" if is_timeout else None
        error.timeout_seconds = self.read_timeout_seconds if error.timeout_type == "read_timeout" else self.connect_timeout_seconds if error.timeout_type == "connect_timeout" else None
        error.max_retries = self.max_retries; error.attempts = attempts
        raise error from last_exception

    def extract_json(self, prompt: Any, **kwargs: Any) -> dict[str, Any]:
        """Compatibility API returning scientific JSON only."""
        kwargs.setdefault("retry_on_length", True)
        return self.extract_json_result(prompt, **kwargs).payload


__all__ = ["DeepSeekClient", "DeepSeekExtractionError", "JSONExtractionResult"]
