"""Resource-aware base for local-index/cache/optional-provider validators."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.schemas.validation import (
    ExternalEvidenceRecord, ValidationExecutionContext, ValidationQueryPlan,
    ValidationQuestion, ValidationResult, ValidationSignal,
)
from code_engine.validation.base import AbstractValidator


class ExternalIndexValidator(AbstractValidator):
    evidence_type = "external_record"
    default_signal_type = "no_coverage_signal"
    interpretation_limits: tuple[str, ...] = ("External evidence is not proof.",)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "index_name", None):
            cls.schema_name = getattr(cls, "schema_name", None) or getattr(cls, "index_name", None)
            cls.schema_version = getattr(cls, "schema_version", None) or "1.0.0"

    def __init__(
        self, configured_resources: set[str] | None = None,
        resource_paths: dict[str, str] | None = None, provider_client: Any | None = None,
    ):
        self.configured_resources = configured_resources or set()
        self.resource_paths = resource_paths or {}
        self.provider_client = provider_client

    @property
    def configured(self) -> bool:
        return all(
            resource in self.configured_resources
            or (resource in self.resource_paths and Path(self.resource_paths[resource]).exists())
            for resource in self.required_resources
        )

    def stream_evidence(
        self, query_plan: ValidationQueryPlan, context: ValidationExecutionContext,
    ) -> Iterator[ExternalEvidenceRecord]:
        if query_plan.execution_mode == "local_index":
            from code_engine.validation.storage import ValidationLocalIndex
            path = query_plan.query_context.get("index_path")
            index_type = query_plan.query_context.get("index_type")
            if not path or not index_type:
                return
            index = ValidationLocalIndex(
                query_plan.index_name or self.index_name or self.name, self.name, index_type, path,
                schema_path=query_plan.query_context.get("schema_path"),
                manifest_path=query_plan.query_context.get("manifest_path"),
            )
            for sequence, raw in enumerate(index.stream_query(query_plan)):
                yield self._evidence_from_raw(raw, query_plan, sequence)
        elif query_plan.execution_mode == "remote_api" and self.provider_client is not None:
            stream = self.provider_client.stream(query_plan) if hasattr(self.provider_client, "stream") else self.provider_client.query(query_plan)
            for sequence, raw in enumerate(stream):
                yield self._evidence_from_raw(raw, query_plan, sequence)

    def _evidence_from_raw(self, raw: dict[str, Any], plan: ValidationQueryPlan, sequence: int) -> ExternalEvidenceRecord:
        stable = f"{self.name}|{plan.query_plan_id}|{raw.get('record_id', sequence)}"
        score = raw.get("score", raw.get("pchembl_value", raw.get("dependency_score")))
        return ExternalEvidenceRecord(
            evidence_id=hashlib.sha256(stable.encode()).hexdigest()[:16],
            validator_name=self.name, source_database=self.source_database,
            query_plan_id=plan.query_plan_id, anchor_id=plan.anchor_id,
            evidence_type=self.evidence_type,
            source_entity=plan.query_entities[0] if plan.query_entities else None,
            target_entity=plan.query_entities[1] if len(plan.query_entities) > 1 else None,
            context={
                **plan.query_context.get("anchor_context", {}),
                **dict(raw.get("context") or {}),
                "expected_direction": plan.query_context.get("expected_direction"),
            },
            record_id=str(raw.get("record_id")) if raw.get("record_id") is not None else None,
            external_ids=dict(raw.get("external_ids") or {}),
            direction=raw.get("direction"), score=float(score) if score is not None else None,
            strength=float(raw["strength"]) if raw.get("strength") is not None else None,
            p_value=float(raw["p_value"]) if raw.get("p_value") is not None else None,
            effect_size=float(raw["effect_size"]) if raw.get("effect_size") is not None else None,
            raw_payload_ref=raw.get("raw_payload_ref"),
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            interpretation_limits=list(self.interpretation_limits),
            warnings=list(raw.get("warnings") or []),
        )

    def build_signals(
        self, evidence_stream: Iterable[ExternalEvidenceRecord],
        context: ValidationExecutionContext,
    ) -> Iterator[ValidationSignal]:
        for evidence in evidence_stream:
            signal_type = self.default_signal_type
            supports: bool | None = None
            contradicts: bool | None = None
            expected = evidence.context.get("expected_direction")
            if signal_type == "expression_support" and expected and evidence.direction:
                supports = str(expected) == str(evidence.direction)
                contradicts = not supports
                signal_type = "expression_support" if supports else "expression_contradiction"
            elif signal_type == "protein_interaction_support":
                supports = True
                contradicts = False
            confidence = min(0.95, max(0.3, abs(float(evidence.score or evidence.strength or 0.6))))
            yield ValidationSignal(
                signal_id=hashlib.sha256(f"{evidence.evidence_id}|{signal_type}".encode()).hexdigest()[:16],
                validator_name=self.name, source_database=self.source_database,
                query_plan_id=evidence.query_plan_id, anchor_id=evidence.anchor_id,
                signal_type=signal_type, linked_external_evidence_ids=[evidence.evidence_id],
                supports_hypothesis=supports, contradicts_hypothesis=contradicts,
                direction=evidence.direction, confidence=confidence, quality=confidence,
                interpretation_limits=list(self.interpretation_limits),
                warnings=["validation_signal_is_not_proof"],
            )

    def validate(self, question: ValidationQuestion) -> ValidationResult:
        if not self.can_validate(question):
            status = "not_applicable"
            limitation = "Validator does not cover this domain/relation."
        elif not self.configured:
            status = "external_index_not_configured"
            limitation = "Required local external index is not configured."
        else:
            status = "no_coverage"
            limitation = "Configured index returned no local coverage."
        return ValidationResult(
            hypothesis_id=question.hypothesis_id,
            validator_name=self.name,
            domain_id=question.domain_id or "general_biomedical",
            validator_profile_id=question.validator_profile_id,
            evidence_modality=question.evidence_modality,
            validation_status=status,
            coverage_status="none",
            limitations=[limitation],
            summary=limitation,
            interpretation_limits=list(self.interpretation_limits),
        )
