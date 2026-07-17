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
        # --- Redefined provider eligibility ---
        # provider_eligible = mention has at least one concrete external provider
        # that actually attempted lookup (not just registered but returning "not_applicable")
        CONCRETE_EXTERNAL_PROVIDERS = {
            "PubChemCandidateProvider", "ChEMBLCandidateProvider",
            "MyGeneCandidateProvider", "UniProtCandidateProvider",
            "OLSOntologyCandidateProvider", "ReactomeCandidateProvider",
            "CellosaurusCandidateProvider",
        }
        provider_eligible_count = 0
        provider_ineligible_count = 0
        provider_eligible_by_type: dict[str, int] = {}
        provider_ineligible_by_type: dict[str, int] = {}
        provider_ineligible_reason_counts: dict[str, int] = {}
        provider_attempt_by_provider: dict[str, int] = {}
        provider_candidate_hits_by_provider: dict[str, int] = {}
        provider_final_accept_by_provider: dict[str, int] = {}
        provider_network_calls_by_provider: dict[str, int] = {}
        duplicate_query_by_provider_surface: dict[str, int] = {}
        seen_provider_surface: set[str] = set()
        type_status_counts: dict[str, dict[str, int]] = {}
        provider_no_result_count = 0
        provider_ambiguous_count = 0
        provider_resolved_count = 0
        adjudicator_rejected_count = 0
        top_unresolved_eligible: list[dict[str, str]] = []
        top_unresolved_ineligible: list[dict[str, str]] = []
        top_llm_cleaned_unverified: list[str] = []

        # --- cleaner verified-but-rejected tracking ---
        cleaner_verified_but_rejected_count = 0
        top_cleaner_verified_but_rejected: list[dict[str, str]] = []

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

            # --- Redefined failure taxonomy: provider eligibility ---
            # A mention is provider_eligible ONLY if at least one concrete external
            # provider (PubChem/ChEMBL/MyGene/UniProt) was actually invoked
            # (status != "not_applicable" and status != "not_needed").
            # LocalCuratedProvider / LocalCacheProvider / NullProvider do NOT count.
            provider_trace = item.get("provider_trace", [])
            active_external_providers = [
                t for t in provider_trace
                if t.get("provider_name") in CONCRETE_EXTERNAL_PROVIDERS
                and t.get("status") not in {"not_applicable", "not_needed"}
            ]
            has_active_external_provider = len(active_external_providers) > 0

            entity_type = request.get("l1_entity_type_hint", "unknown")
            type_status_counts.setdefault(entity_type, {})
            type_status_counts[entity_type][status] = type_status_counts[entity_type].get(status, 0) + 1

            if has_active_external_provider:
                provider_eligible_count += 1
                provider_eligible_by_type[entity_type] = provider_eligible_by_type.get(entity_type, 0) + 1
            else:
                provider_ineligible_count += 1
                provider_ineligible_by_type[entity_type] = provider_ineligible_by_type.get(entity_type, 0) + 1
                # Determine ineligibility reason
                has_external_but_not_applicable = any(
                    t.get("provider_name") in CONCRETE_EXTERNAL_PROVIDERS
                    and t.get("status") in {"not_applicable"}
                    for t in provider_trace
                )
                if has_external_but_not_applicable:
                    reason = "no_matching_provider_for_entity_type"
                elif any(t.get("provider_name") in CONCRETE_EXTERNAL_PROVIDERS for t in provider_trace):
                    reason = "external_provider_registered_but_not_invoked"
                else:
                    reason = "no_external_provider_registered"
                provider_ineligible_reason_counts[reason] = provider_ineligible_reason_counts.get(reason, 0) + 1

            for trace in item.get("provider_trace", []):
                pname = trace.get("provider_name", "")
                if trace.get("status") not in {"not_applicable", "not_needed"}:
                    provider_attempt_by_provider[pname] = provider_attempt_by_provider.get(pname, 0) + 1
                    provider_network_calls_by_provider[pname] = provider_network_calls_by_provider.get(pname, 0) + int(trace.get("network_calls_made", 0))
                    if int(trace.get("candidate_count", 0)) > 0:
                        provider_candidate_hits_by_provider[pname] = provider_candidate_hits_by_provider.get(pname, 0) + 1
                    key = f"{pname}\t{surface.casefold()}"
                    if key in seen_provider_surface and int(trace.get("network_calls_made", 0)) > 0:
                        duplicate_query_by_provider_surface[key] = duplicate_query_by_provider_surface.get(key, 0) + 1
                    seen_provider_surface.add(key)

            if status == "unresolved":
                provider_no_result_count += 1
                if has_active_external_provider and len(top_unresolved_eligible) < 20:
                    top_unresolved_eligible.append({"surface": surface, "entity_type": entity_type})
                elif not has_active_external_provider and len(top_unresolved_ineligible) < 20:
                    top_unresolved_ineligible.append({"surface": surface, "entity_type": entity_type})
            elif status == "ambiguous":
                provider_ambiguous_count += 1
            elif status in {"resolved_external_grounded", "resolved_curated", "resolved_cache"}:
                provider_resolved_count += 1
                selected = item.get("selected_candidate") or {}
                pname = selected.get("provider_name")
                if pname:
                    provider_final_accept_by_provider[pname] = provider_final_accept_by_provider.get(pname, 0) + 1
            elif status == "manual_review_required":
                adjudicator_rejected_count += 1

            # Track LLM cleaned but unverified
            if status == "llm_suggestion_ungrounded" and len(top_llm_cleaned_unverified) < 20:
                top_llm_cleaned_unverified.append(surface)

            # Track cleaner verified-but-rejected decisions
            decision_reason = item.get("decision_reason", "")
            if "llm_cleaned" in decision_reason and status not in {
                "resolved_external_grounded", "resolved_curated", "resolved_cache",
            }:
                cleaner_verified_but_rejected_count += 1
                if len(top_cleaner_verified_but_rejected) < 20:
                    top_cleaner_verified_but_rejected.append({
                        "surface": surface,
                        "entity_type": entity_type,
                        "status": status,
                        "decision_reason": decision_reason,
                    })

        failure_taxonomy = {
            "entity_provider_eligible_count": provider_eligible_count,
            "entity_provider_ineligible_count": provider_ineligible_count,
            "provider_eligible_count_by_type": provider_eligible_by_type,
            "provider_ineligible_count_by_type": provider_ineligible_by_type,
            "provider_ineligible_reason_counts": provider_ineligible_reason_counts,
            "provider_attempt_count_by_provider": provider_attempt_by_provider,
            "provider_candidate_hit_count_by_provider": provider_candidate_hits_by_provider,
            "provider_final_accept_count_by_provider": provider_final_accept_by_provider,
            "provider_network_calls_by_provider": provider_network_calls_by_provider,
            "duplicate_network_query_count_by_provider_surface": duplicate_query_by_provider_surface,
            "type_status_counts": type_status_counts,
            "provider_no_result_count": provider_no_result_count,
            "provider_ambiguous_count": provider_ambiguous_count,
            "provider_resolved_count": provider_resolved_count,
            "adjudicator_rejected_count": adjudicator_rejected_count,
            "top_unresolved_provider_eligible_mentions": top_unresolved_eligible,
            "top_unresolved_provider_ineligible_mentions": top_unresolved_ineligible,
            "top_llm_cleaned_but_unverified_mentions": top_llm_cleaned_unverified,
            "cleaner_verified_but_rejected_count": cleaner_verified_but_rejected_count,
            "top_cleaner_verified_but_rejected_mentions": top_cleaner_verified_but_rejected,
            "top_provider_ineligible_mentions": top_unresolved_ineligible[:20],
            "top_provider_eligible_unresolved_mentions": top_unresolved_eligible[:20],
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
