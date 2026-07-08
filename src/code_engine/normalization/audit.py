"""Run-scoped append-only entity resolution audit."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from code_engine.normalization.candidates import EntityResolutionResult


class EntityResolutionAuditWriter:
    def __init__(self, run_dir: str | Path):
        self.artifacts = Path(run_dir) / "artifacts"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.candidates_path = self.artifacts / "entity_resolution_candidates.jsonl"
        self.decisions_path = self.artifacts / "entity_resolution_decisions.jsonl"
        self.summary_path = self.artifacts / "entity_resolution_audit.json"

    def write(self, result: EntityResolutionResult, provider_trace: list[dict] | None = None) -> str:
        result.audit_ref = str(self.decisions_path)
        with self.candidates_path.open("a", encoding="utf-8") as handle:
            for candidate in result.candidates:
                handle.write(candidate.model_dump_json() + "\n")
        payload = {**result.model_dump(), "provider_trace": provider_trace or []}
        with self.decisions_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        decisions = self._read_lines(self.decisions_path)
        statuses, providers = {}, {}
        network_calls = api_calls = 0

        # Failure taxonomy accumulators
        provider_eligible_count = 0
        provider_ineligible_by_type: dict[str, int] = {}
        provider_attempt_by_provider: dict[str, int] = {}
        provider_no_result_count = 0
        provider_ambiguous_count = 0
        provider_resolved_count = 0
        adjudicator_rejected_count = 0
        top_unresolved_eligible: list[str] = []
        top_unresolved_ineligible: list[str] = []
        top_llm_cleaned_unverified: list[str] = []

        for item in decisions:
            status = item.get("normalization_status", "unknown")
            statuses[status] = statuses.get(status, 0) + 1

            request = item.get("request", {})
            surface = request.get("surface", "")

            for trace in item.get("provider_trace", []):
                if trace.get("status") in {"not_applicable", "not_needed"}:
                    continue
                name = trace.get("provider_name", "unknown")
                providers[name] = providers.get(name, 0) + 1
                network_calls += int(trace.get("network_calls_made", 0))
                api_calls += int(trace.get("api_calls_made", 0))

            # Failure taxonomy
            has_external_provider = any(
                t.get("provider_name") in {"PubChemCandidateProvider", "ChEMBLCandidateProvider",
                                             "MyGeneCandidateProvider", "UniProtCandidateProvider"}
                for t in item.get("provider_trace", [])
            )
            entity_type = request.get("l1_entity_type_hint", "unknown")

            if has_external_provider:
                provider_eligible_count += 1
            else:
                provider_ineligible_by_type[entity_type] = provider_ineligible_by_type.get(entity_type, 0) + 1

            for trace in item.get("provider_trace", []):
                pname = trace.get("provider_name", "")
                if trace.get("status") not in {"not_applicable", "not_needed"}:
                    provider_attempt_by_provider[pname] = provider_attempt_by_provider.get(pname, 0) + 1

            if status == "unresolved":
                provider_no_result_count += 1
                if has_external_provider and len(top_unresolved_eligible) < 20:
                    top_unresolved_eligible.append(surface)
                elif not has_external_provider and len(top_unresolved_ineligible) < 20:
                    top_unresolved_ineligible.append(surface)
            elif status == "ambiguous":
                provider_ambiguous_count += 1
            elif status in {"resolved_external_grounded", "resolved_curated", "resolved_cache"}:
                provider_resolved_count += 1
            elif status == "manual_review_required":
                adjudicator_rejected_count += 1

            # Track LLM cleaned but unverified
            if status == "llm_suggestion_ungrounded" and len(top_llm_cleaned_unverified) < 20:
                top_llm_cleaned_unverified.append(surface)

        failure_taxonomy = {
            "entity_provider_eligible_count": provider_eligible_count,
            "provider_ineligible_count_by_type": provider_ineligible_by_type,
            "provider_attempt_count_by_provider": provider_attempt_by_provider,
            "provider_no_result_count": provider_no_result_count,
            "provider_ambiguous_count": provider_ambiguous_count,
            "provider_resolved_count": provider_resolved_count,
            "adjudicator_rejected_count": adjudicator_rejected_count,
            "top_unresolved_provider_eligible_mentions": top_unresolved_eligible,
            "top_unresolved_provider_ineligible_mentions": top_unresolved_ineligible,
            "top_llm_cleaned_but_unverified_mentions": top_llm_cleaned_unverified,
        }

        self.summary_path.write_text(json.dumps({
            "total_mentions": len(decisions),
            "status_counts": statuses,
            "provider_usage_counts": providers,
            "network_calls_made": network_calls,
            "api_calls_made": api_calls,
            "failure_taxonomy": failure_taxonomy,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(self.decisions_path)

    @staticmethod
    def _read_lines(path: Path) -> list[dict]:
        records = []
        for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
            try: records.append(json.loads(line))
            except json.JSONDecodeError: pass
        return records
