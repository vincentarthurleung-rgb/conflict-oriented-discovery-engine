"""Backward-compatible streaming validator plugin interface."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator

from code_engine.schemas.validation import (
    ExternalEvidenceRecord, ValidationAnchor, ValidationExecutionContext,
    ValidationQueryPlan, ValidationQuestion, ValidationResult, ValidationSignal,
    ValidatorCapability,
)


class AbstractValidator:
    name = "AbstractValidator"
    supported_domains: tuple[str, ...] = ()
    supported_relation_types: tuple[str, ...] = ()
    supported_entity_types: tuple[str, ...] = ()
    required_resources: tuple[str, ...] = ()
    supported_anchor_types: tuple[str, ...] = ()
    supported_validation_intents: tuple[str, ...] = ()
    supported_polarity_types: tuple[str, ...] = ()
    supports_local_index = False
    supports_remote_api = False
    supports_cache_only = True
    requires_auth = False
    index_name: str | None = None
    schema_name: str | None = None
    schema_version: str | None = None
    source_database = "unknown"
    default_max_records = 100
    default_max_signals = 30

    def can_validate(self, question_or_anchor, context=None) -> bool:
        if isinstance(question_or_anchor, ValidationAnchor):
            anchor_ok = not self.supported_anchor_types or question_or_anchor.anchor_type in self.supported_anchor_types
            intent_ok = not self.supported_validation_intents or question_or_anchor.validation_intent in self.supported_validation_intents
            return anchor_ok and intent_ok
        if not isinstance(question_or_anchor, ValidationQuestion):
            return False
        question = question_or_anchor
        domain_ok = not self.supported_domains or question.domain_id in self.supported_domains
        relation = question.relation_family or question.relation_type
        relation_ok = not self.supported_relation_types or relation in self.supported_relation_types
        intent_ok = (
            not self.supported_validation_intents
            or question.validator_intent in {"", "unknown"}
            or question.validator_intent in self.supported_validation_intents
        )
        observed_types = {
            str(question.context.get("subject_entity_type") or ""),
            str(question.context.get("object_entity_type") or ""),
        } - {""}
        entity_ok = (
            not self.supported_entity_types
            or not observed_types
            or bool(observed_types.intersection(self.supported_entity_types))
        )
        return domain_ok and relation_ok and entity_ok and intent_ok

    @classmethod
    def capability(cls) -> ValidatorCapability:
        return ValidatorCapability(
            validator_name=cls.name,
            supported_anchor_types=list(cls.supported_anchor_types),
            supported_validation_intents=list(cls.supported_validation_intents),
            supported_domains=list(cls.supported_domains),
            supported_relation_families=list(cls.supported_relation_types),
            supported_polarity_types=list(cls.supported_polarity_types),
            supported_entity_types=list(cls.supported_entity_types),
            supports_local_index=bool(cls.supports_local_index),
            supports_remote_api=bool(cls.supports_remote_api),
            supports_cache_only=bool(cls.supports_cache_only),
            requires_auth=bool(cls.requires_auth),
            default_max_records=int(cls.default_max_records),
            default_max_signals=int(cls.default_max_signals),
            index_name=cls.index_name,
        )

    def plan_queries(
        self, anchors: list[ValidationAnchor], context: ValidationExecutionContext,
    ) -> list[ValidationQueryPlan]:
        plans = []
        for anchor in anchors:
            if not self.can_validate(anchor, context):
                continue
            stable = f"{self.name}|{anchor.anchor_id}|{anchor.validation_intent}"
            plans.append(ValidationQueryPlan(
                query_plan_id=hashlib.sha256(stable.encode()).hexdigest()[:16],
                anchor_id=anchor.anchor_id,
                validator_name=self.name,
                query_type=anchor.validation_intent,
                query_entities=anchor.entities,
                query_context=anchor.contexts,
                execution_mode="planned",
                index_name=self.index_name,
                max_records=self.default_max_records,
                max_signals=self.default_max_signals,
                status="planned",
                reason="validator_default_plan_requires_query_planner",
            ))
        return plans

    def stream_evidence(
        self, query_plan: ValidationQueryPlan, context: ValidationExecutionContext,
    ) -> Iterator[ExternalEvidenceRecord]:
        if False:
            yield ExternalEvidenceRecord(
                evidence_id="", validator_name=self.name, source_database=self.source_database,
                query_plan_id=query_plan.query_plan_id, anchor_id=query_plan.anchor_id,
                evidence_type="unconfigured",
            )

    def build_signals(
        self, evidence_stream: Iterable[ExternalEvidenceRecord],
        context: ValidationExecutionContext,
    ) -> Iterator[ValidationSignal]:
        if False:
            yield ValidationSignal(
                signal_id="", validator_name=self.name, source_database=self.source_database,
                query_plan_id="", anchor_id="", signal_type="no_coverage_signal",
            )

    def validate(self, question_or_anchor, context=None) -> ValidationResult:
        hypothesis_id = getattr(question_or_anchor, "hypothesis_id", "UNKNOWN")
        domain_id = getattr(question_or_anchor, "domain_id", None) or "general_biomedical"
        return ValidationResult(
            hypothesis_id=hypothesis_id,
            validator_name=self.name,
            domain_id=domain_id,
            validation_status="external_index_not_configured",
            summary="Validator has no configured execution provider.",
            limitations=["External evidence is not proof."],
        )
