"""Small DeepSeek JSON client with retries and structured failures."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


class DeepSeekExtractionError(RuntimeError):
    def __init__(self, code: str, message: str, attempts: int):
        super().__init__(message)
        self.details = {"code": code, "message": message, "attempts": attempts}


class DeepSeekClient:
    endpoint = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self, api_key: str | None = None, *, max_retries: int = 2, sleep_fn=time.sleep):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for --execute --api")
        self.max_retries = max_retries
        self.sleep_fn = sleep_fn

    def extract_json(self, prompt: str, model: str = "deepseek-v4-pro", temperature: float = 0.0, top_p: float = 1.0, timeout: int = 60, **_: Any) -> dict[str, Any]:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "system", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "top_p": top_p,
        }).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        last_error = "unknown_error"
        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                content = payload["choices"][0]["message"]["content"]
                parsed = json.loads(content) if isinstance(content, str) else content
                if not isinstance(parsed, dict):
                    raise ValueError("DeepSeek response JSON must be an object")
                return parsed
            except urllib.error.HTTPError as exc:
                last_error = f"http_{exc.code}"
                if exc.code == 429 and attempt < self.max_retries:
                    self.sleep_fn(2 ** attempt)
                    continue
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
                last_error = str(exc)
            if attempt < self.max_retries:
                self.sleep_fn(2 ** attempt)
        raise DeepSeekExtractionError("deepseek_extraction_failed", last_error, self.max_retries)
