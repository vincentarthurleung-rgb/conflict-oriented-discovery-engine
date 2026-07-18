"""Provider orchestration, deterministic adjudication, and audit boundary."""

from __future__ import annotations

from code_engine.normalization.adjudicator import adjudicate_entity_candidates
from code_engine.normalization.audit import EntityResolutionAuditWriter
from code_engine.normalization.cache import EntityCache
from code_engine.normalization.candidates import EntityResolutionRequest, EntityResolutionResult
from code_engine.normalization.providers.base import CandidateProvider


class EntityResolutionHub:
    def __init__(self, providers: list[CandidateProvider], adjudicator_policy: dict | None = None, audit_writer: EntityResolutionAuditWriter | None = None, *, entity_cache: EntityCache | None = None):
        self.providers = providers
        self.adjudicator_policy = adjudicator_policy
        self.audit_writer = audit_writer
        self.entity_cache = entity_cache

    def resolve(self, request: EntityResolutionRequest) -> EntityResolutionResult:
        candidates, warnings, trace = [], [], []
        for provider in self.providers:
            if provider.name == "NullProvider" and candidates:
                trace.append({"provider_name": provider.name, "status": "not_needed", "candidate_count": 0})
                continue
            if not provider.can_handle(request):
                trace.append({"provider_name": provider.name, "status": "not_applicable", "candidate_count": 0})
                continue
            try:
                proposed = provider.propose(request)
                candidates.extend(proposed)
                warnings.extend(provider.last_warnings)
                trace.append({"provider_name": provider.name, "status": provider.last_status, "candidate_count": len(proposed), "warnings": list(provider.last_warnings), "network_calls_made": provider.last_network_calls, "api_calls_made": provider.last_api_calls})
            except Exception as exc:
                warning = f"provider_failure:{provider.name}:{type(exc).__name__}"
                warnings.append(warning)
                trace.append({"provider_name": provider.name, "status": "error", "candidate_count": 0, "warnings": [warning]})
        result = adjudicate_entity_candidates(request, candidates, self.adjudicator_policy)
        external_pending = any(
            item.get("status") in {"retry_pending", "retryable_failed"}
            for item in trace
        )
        if result.normalization_status == "unresolved" and external_pending:
            result.normalization_status = "external_resolution_pending"
            result.decision_reason = "external_provider_resolution_pending"
            result.warnings = list(dict.fromkeys(
                result.warnings + ["external_provider_resolution_pending"]
            ))
        result.warnings = list(dict.fromkeys(result.warnings + warnings))
        if self.audit_writer:
            result.audit_ref = self.audit_writer.write(result, trace)
        if self.entity_cache:
            self.entity_cache.record_candidates(candidates)
            self.entity_cache.record_accepted(result)
        return result

    def resolve_many(self, requests: list[EntityResolutionRequest]) -> list[EntityResolutionResult]:
        return [self.resolve(request) for request in requests]
