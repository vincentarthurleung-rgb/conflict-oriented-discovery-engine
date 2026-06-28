"""Domain configuration models without scientific decision logic."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainProfile:
    name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    prompt_id: str = ""


@dataclass(frozen=True)
class PromptProfile:
    profile_id: str
    domain_id: str
    version: str
    template: str
    context_slots: tuple[str, ...] = field(default_factory=tuple)
    output_schema_version: str = "l1_v2_evidence_mechanism_schema"
    extraction_policy_version: str = "evidence_grounded_v2"
