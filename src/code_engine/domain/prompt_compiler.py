"""Strict, deterministic compiler for L1 prompt profiles."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from code_engine.domain.models import PromptProfile


def compile_prompt(template: str, variables: dict[str, str]) -> str:
    return template.format_map(variables)


@dataclass(frozen=True)
class CompiledPrompt:
    text: str
    domain_id: str
    prompt_profile_id: str
    prompt_version: str
    compiled_prompt_hash: str
    output_schema_version: str
    extraction_policy_version: str
    compiled_prompt_char_count: int
    compiled_prompt_word_count: int


def compile_l1_prompt(
    profile: PromptProfile,
    chunk_text: str,
    *,
    prompt_version: str | None = None,
    output_schema_version: str | None = None,
) -> CompiledPrompt:
    """Compile a profile and return stable metadata without calling an LLM."""

    version = prompt_version or profile.version
    schema_version = output_schema_version or profile.output_schema_version
    variables = {
        "domain_id": profile.domain_id,
        "prompt_profile_id": profile.profile_id,
        "prompt_version": version,
        "output_schema_version": schema_version,
        "extraction_policy_version": profile.extraction_policy_version,
        "context_slots": ", ".join(profile.context_slots),
        "chunk_text": str(chunk_text),
    }
    text = compile_prompt(profile.template, variables)
    return CompiledPrompt(
        text=text,
        domain_id=profile.domain_id,
        prompt_profile_id=profile.profile_id,
        prompt_version=version,
        compiled_prompt_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        output_schema_version=schema_version,
        extraction_policy_version=profile.extraction_policy_version,
        compiled_prompt_char_count=len(text),
        compiled_prompt_word_count=len(text.split()),
    )
