"""HTTP helpers for patient L2 entity provider clients."""

from __future__ import annotations

from typing import Any

import requests

from code_engine.normalization.providers.patient_execution import ProviderExecutionConfig, ProviderRetryableError


def provider_timeout() -> tuple[float, float]:
    cfg = ProviderExecutionConfig.from_env()
    return (cfg.connect_timeout_seconds, cfg.read_timeout_seconds)


def classify_response_status(status_code: int) -> str | None:
    if status_code == 429:
        return "http_429"
    if status_code in {500, 502, 503, 504}:
        return f"http_{status_code}"
    return None


def raise_for_retryable_status(response: requests.Response) -> None:
    category = classify_response_status(int(response.status_code))
    if category:
        raise ProviderRetryableError(category, f"provider returned HTTP {response.status_code}")


def get_json(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    try:
        response = requests.get(url, params=params, headers=headers, timeout=provider_timeout())
    except requests.exceptions.ConnectTimeout as exc:
        raise ProviderRetryableError("connection_timeout", str(exc)) from exc
    except requests.exceptions.ReadTimeout as exc:
        raise ProviderRetryableError("read_timeout", str(exc)) from exc
    except requests.exceptions.SSLError as exc:
        raise ProviderRetryableError("tls_error", str(exc)) from exc
    except requests.exceptions.ConnectionError as exc:
        raise ProviderRetryableError("connection_error", str(exc)) from exc
    except requests.exceptions.RequestException as exc:
        raise ProviderRetryableError("provider_unavailable", str(exc)) from exc
    raise_for_retryable_status(response)
    if 400 <= response.status_code < 500:
        return response.status_code, {}
    try:
        return response.status_code, response.json()
    except ValueError as exc:
        raise ProviderRetryableError("remote_closed", str(exc)) from exc

