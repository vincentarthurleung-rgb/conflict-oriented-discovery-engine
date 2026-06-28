"""Scientific Encoder client boundary."""

from __future__ import annotations

from typing import Any, Protocol


class ScientificEncoderClient(Protocol):
    def extract_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]: ...


def create_default_scientific_encoder_client() -> ScientificEncoderClient:
    # Construction is deferred until execute+api has been verified by semantic_intake.
    from code_engine.extraction.deepseek_client import DeepSeekClient
    return DeepSeekClient()
