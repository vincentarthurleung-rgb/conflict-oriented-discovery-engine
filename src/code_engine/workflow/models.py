"""JSON-serializable workflow state models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class WorkflowStepStatus(str, Enum):
    PENDING = "pending"
    PLANNED = "planned"
    SKIPPED = "skipped"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class WorkflowStepName(str, Enum):
    INTAKE = "intake"
    SEARCH = "search"
    ACQUISITION = "acquisition"
    PAYLOAD = "payload"
    ABSTRACT_L1 = "abstract_l1"
    L2_ABSTRACT = "l2_abstract"
    ABSTRACT_CONFLICT_SCREENING = "abstract_conflict_screening"
    FULLTEXT_ESCALATION = "fulltext_escalation"
    FULLTEXT_L1 = "fulltext_l1"
    L2_FULLTEXT = "l2_fulltext"
    FULLTEXT_CONFLICT_CONFIRMATION = "fulltext_conflict_confirmation"
    L1 = "l1"
    L1_5 = "l1_5"
    L2 = "l2"
    MECHANISM = "mechanism"
    CONFLICT = "conflict"
    HYPOTHESIS = "hypothesis"
    VALIDATION = "validation"
    REPORT = "report"


STEP_ORDER = [item.value for item in WorkflowStepName]


@dataclass
class WorkflowStepRecord:
    step_name: str
    status: str = WorkflowStepStatus.PENDING.value
    started_at: str | None = None
    completed_at: str | None = None
    input_refs: list[str] = field(default_factory=list)
    output_refs: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    api_calls_made: int = 0
    network_calls_made: int = 0
    skipped_reason: str | None = None


@dataclass
class RunState:
    run_id: str
    created_at: str
    updated_at: str
    query: str
    mode: str
    api_enabled: bool
    network_enabled: bool
    until: str
    max_papers: int | None = None
    domain_id: str | None = None
    subdomain_id: str | None = None
    domain_profile_id: str | None = None
    prompt_profile_id: str | None = None
    entity_registry_profile: str | None = None
    validator_profile_id: str | None = None
    semantic_mode: str | None = None
    semantic_confidence: float | None = None
    requires_manual_review: bool = False
    entity_network_lookup_enabled: bool = False
    entity_llm_proposer_enabled: bool = False
    entity_resolution_policy: str | None = None
    l1_mode: str = "legacy"
    fulltext_escalation_enabled: bool = False
    l1_estimated_cost_usd: float = 0.0
    l1_actual_cost_usd: float | None = None
    validation_anchor_count: int = 0
    validation_question_count: int = 0
    validation_route_count: int = 0
    validation_query_plan_count: int = 0
    validation_allowed_query_count: int = 0
    validation_blocked_query_count: int = 0
    validation_estimated_records: int = 0
    validation_actual_evidence_count: int = 0
    validation_signal_count: int = 0
    validation_cache_hit_count: int = 0
    validation_cache_miss_count: int = 0
    validation_estimated_memory_mb: float = 0.0
    validation_result_count: int = 0
    validation_aggregate_status: str = "not_run"
    steps: dict[str, WorkflowStepRecord] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    api_calls_made: int = 0
    network_calls_made: int = 0
    current_step: str | None = None
    failed_step: str | None = None
    final_status: str = "planned"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        payload = dict(data)
        existing_steps = {
            name: record if isinstance(record, WorkflowStepRecord) else WorkflowStepRecord(**record)
            for name, record in payload.get("steps", {}).items()
        }
        payload["steps"] = {
            name: existing_steps.get(name, WorkflowStepRecord(step_name=name))
            for name in STEP_ORDER
        }
        return cls(**payload)
