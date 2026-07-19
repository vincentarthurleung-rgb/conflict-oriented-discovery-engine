"""Offline transition audit for evidence-aware three-state adjudication."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from code_engine.normalization.adjudicator import adjudicate_entity_candidates
from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest


REPORT_DIR = Path("reports")
CASES = {
    "EMT": {
        "case_id": "emt_metastasis_drug_resistance_discovery_v1",
        "run_dir": Path("runs/20260719_000216_emt_metastasis_drug_resistance_discovery_v1_l2_replay_v5_with_llm"),
        "bundle_dir": Path("case_bundles/emt_metastasis_drug_resistance_discovery_v1___l2_cleaner_fulltext_replay"),
    },
    "Ferroptosis": {
        "case_id": "ferroptosis_cancer_therapy_response_discovery_v1",
        "run_dir": Path("runs/20260719_022954_ferroptosis_cancer_therapy_response_discovery_v1_l2_replay_v5_with_llm"),
        "bundle_dir": Path("case_bundles/ferroptosis_cancer_therapy_response_discovery_v1___l2_cleaner_fulltext_replay"),
    },
    "HIF1A": {
        "case_id": "hif1a_hypoxia_cancer_response_discovery_v1",
        "run_dir": Path("runs/20260719_040612_hif1a_hypoxia_cancer_response_discovery_v1_l2_replay_v5_with_llm"),
        "bundle_dir": Path("case_bundles/hif1a_hypoxia_cancer_response_discovery_v1___l2_cleaner_fulltext_replay"),
    },
}

ACCEPTED_OLD = {"resolved_external_grounded", "resolved_curated", "resolved_cache", "accepted_external_grounded"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _candidate_rows(items: list[dict[str, Any]]) -> list[EntityCandidate]:
    candidates = []
    for item in items:
        try:
            candidates.append(EntityCandidate.model_validate(item))
        except Exception:
            continue
    return candidates


def _decision_key(row: dict[str, Any]) -> str:
    request = row.get("request") or {}
    return "|".join(str(request.get(key) or "") for key in ("paper_id", "claim_id", "observation_id", "endpoint_role", "surface"))


def _transition_bucket(old_status: str, new_status: str, old_id: str | None, new_id: str | None, has_candidates: bool) -> str:
    if old_status in ACCEPTED_OLD and new_status == "accepted_external_grounded" and old_id == new_id:
        return "old accepted -> new accepted"
    if old_status in ACCEPTED_OLD and new_status == "ambiguous_external_candidate":
        return "A. old accepted -> new ambiguous"
    if old_status in ACCEPTED_OLD and new_status == "rejected_external_candidate":
        return "A. old accepted -> new rejected"
    if old_status not in ACCEPTED_OLD and new_status == "accepted_external_grounded":
        return "C. old unresolved/rejected -> new accepted"
    if old_status not in ACCEPTED_OLD and new_status == "ambiguous_external_candidate":
        return "D. old unresolved/rejected -> new ambiguous"
    if old_id and new_id and old_id == new_id and old_status != new_status:
        return "E. same canonical ID status changed"
    if not has_candidates:
        return "F. no useful external candidate"
    if old_status in ACCEPTED_OLD and new_status == "rejected_external_candidate":
        return "B. old accepted -> new rejected"
    return "unchanged_or_low_signal"


def _status_three_state(status: str) -> str:
    if status in ACCEPTED_OLD:
        return "accepted_external_grounded"
    if status in {"ambiguous", "ambiguous_external_candidate", "manual_review_required"}:
        return "ambiguous_external_candidate"
    if status in {"rejected_external_candidate"}:
        return "rejected_external_candidate"
    return status


def _case_counts(bundle_dir: Path) -> dict[str, int]:
    graph = _read_jsonl(bundle_dir / "l2_graph_observations.jsonl")
    review = _read_jsonl(bundle_dir / "l2_reviewable_graph_observations.jsonl")
    core = _read_jsonl(bundle_dir / "core_observations.jsonl")
    conflicts = _read_json(bundle_dir / "graph_conflict_summary.json")
    return {
        "formal_graph_endpoint_count": sum(1 for item in graph if item.get("allow_high_confidence_graph_use")),
        "reviewable_observation_count": len(review),
        "core_observation_count": len(core),
        "formal_conflict_count": int(conflicts.get("formal_conflict_count") or conflicts.get("conflict_count") or 0),
    }


def _audit_case(label: str, spec: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = spec["run_dir"] / "artifacts" / "entity_resolution_decisions.jsonl"
    rows = _read_jsonl(path)
    transitions = []
    old_counts: Counter[str] = Counter()
    new_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    accepted_ids: set[str] = set()
    ambiguous_ids: set[str] = set()
    network_calls = api_calls = 0
    llm_calls = 0

    for row in rows:
        request_payload = row.get("request") or {}
        candidates_payload = row.get("candidates") or []
        try:
            request = EntityResolutionRequest.model_validate(request_payload)
        except Exception:
            continue
        candidates = _candidate_rows(candidates_payload)
        if not candidates:
            old_status = str(row.get("normalization_status") or "unresolved")
            old_counts[old_status] += 1
            new_counts["unresolved"] += 1
            continue
        new_result = adjudicate_entity_candidates(request, candidates)
        old_status = str(row.get("normalization_status") or "unresolved")
        old_selected = row.get("selected_candidate") or {}
        new_selected = new_result.selected_candidate
        old_id = old_selected.get("canonical_id") if isinstance(old_selected, dict) else None
        new_id = new_selected.canonical_id if new_selected else None
        bucket = _transition_bucket(old_status, new_result.normalization_status, old_id, new_id, bool(candidates))
        old_counts[old_status] += 1
        new_counts[new_result.normalization_status] += 1
        reason_counts.update(new_result.decision_reasons)
        bucket_counts[bucket] += 1
        if new_result.decision == "accepted" and new_id:
            accepted_ids.add(new_id)
        if new_result.decision == "ambiguous":
            ambiguous_ids.update(str(item.canonical_id) for item in new_result.candidates[:5] if item.canonical_id)
        for trace in row.get("provider_trace", []):
            network_calls += int(trace.get("network_calls_made", 0) or 0)
            api_calls += int(trace.get("api_calls_made", 0) or 0)
        if row.get("cleaner_trace"):
            llm_calls += 1
        transitions.append({
            "case_id": spec["case_id"],
            "mention": request.surface,
            "cleaned_mention": (old_selected.get("supporting_context") or {}).get("llm_cleaned_surface") if isinstance(old_selected, dict) else None,
            "old_status": old_status,
            "new_status": new_result.normalization_status,
            "old_canonical_id": old_id,
            "new_canonical_id": new_id,
            "old_score": row.get("confidence"),
            "new_score": new_result.confidence,
            "provider_candidates": [
                {"canonical_id": item.canonical_id, "label": item.canonical_name, "provider": item.provider_name, "score": item.overall_score}
                for item in new_result.candidates[:5]
            ],
            "species_context": request.species_context,
            "granularity": request.mention_granularity,
            "relation": request.relation,
            "subject_or_object": request.endpoint_role,
            "rejection_reason": ";".join(new_result.hard_exclusions or new_result.decision_reasons),
            "transition_bucket": bucket,
            "reason_codes": new_result.decision_reasons,
            "score_margin": new_result.score_margin,
        })

    graph_counts = _case_counts(spec["bundle_dir"])
    summary = {
        "case_id": spec["case_id"],
        "label": label,
        "source_decisions": str(path),
        "mentions_with_candidates": sum(1 for row in rows if row.get("candidates")),
        "external_candidate_mentions": sum(1 for row in rows if row.get("candidates")),
        "old_status_counts": dict(old_counts),
        "new_status_counts": dict(new_counts),
        "old accepted": sum(old_counts[status] for status in ACCEPTED_OLD),
        "new accepted": new_counts.get("accepted_external_grounded", 0) + new_counts.get("resolved_curated", 0) + new_counts.get("resolved_cache", 0),
        "new ambiguous": new_counts.get("ambiguous_external_candidate", 0),
        "new rejected": new_counts.get("rejected_external_candidate", 0),
        "accepted_canonical_endpoint_count": len(accepted_ids),
        "ambiguous_candidate_endpoint_count": len(ambiguous_ids),
        **graph_counts,
        "transition_counts": dict(bucket_counts),
        "top_rejection_reasons": dict(Counter({k: v for k, v in reason_counts.items() if k.startswith("rejected_")}).most_common(10)),
        "top_ambiguous_reasons": dict(Counter({k: v for k, v in reason_counts.items() if k.startswith("ambiguous_")}).most_common(10)),
        "network/API calls": {"provider_network_calls_replayed": 0, "provider_api_calls_replayed": 0, "llm_cleaner_calls_replayed": 0, "abstract_l1_calls_replayed": 0, "retrieval_calls_replayed": 0, "source_artifact_network_calls": network_calls, "source_artifact_api_calls": api_calls, "source_artifact_llm_cleaner_records": llm_calls},
    }
    return summary, transitions


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_markdown(summaries: list[dict[str, Any]], transitions: list[dict[str, Any]]) -> None:
    lines = ["# Entity Adjudication Transition Audit", "", "Offline replay used existing resolver decision artifacts only. Provider, LLM cleaner, Abstract L1, and retrieval replay calls were all zero.", ""]
    for summary in summaries:
        lines.extend([
            f"## {summary['label']}",
            "",
            f"- case_id: `{summary['case_id']}`",
            f"- mentions_with_candidates: {summary['mentions_with_candidates']}",
            f"- old accepted: {summary['old accepted']}",
            f"- new accepted: {summary['new accepted']}",
            f"- new ambiguous: {summary['new ambiguous']}",
            f"- new rejected: {summary['new rejected']}",
            f"- accepted canonical endpoints: {summary['accepted_canonical_endpoint_count']}",
            f"- ambiguous candidate endpoints: {summary['ambiguous_candidate_endpoint_count']}",
            f"- formal graph endpoints: {summary['formal_graph_endpoint_count']}",
            f"- core observations: {summary['core_observation_count']}",
            f"- transition counts: `{summary['transition_counts']}`",
            f"- top ambiguous reasons: `{summary['top_ambiguous_reasons']}`",
            f"- top rejection reasons: `{summary['top_rejection_reasons']}`",
            "",
        ])
    lines.extend(["## Sample Transitions", ""])
    for row in transitions[:60]:
        lines.append(f"- {row['case_id']} `{row['mention']}`: {row['old_status']} -> {row['new_status']} ({row['transition_bucket']}); reasons={row['reason_codes']}")
    (REPORT_DIR / "entity_adjudication_transition_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_design() -> None:
    text = """# Evidence-Aware Three-State Entity Adjudication

## Code Audit Conclusion

Provider candidates are generated by `EntityResolutionHub.resolve()` through `CandidateProvider.propose()` implementations under `src/code_engine/normalization/providers/`. Candidates use the provider-neutral `EntityCandidate` model and already carried provider name, canonical id/name, entity type, species, granularity, scores, aliases, warnings, and grounding flags. Acceptance was previously decided only by `adjudicate_entity_candidates()` using score, species/granularity penalties, a high confidence threshold, and top margin. That produced an operational two-layer outcome: accepted `resolved_*` versus `ambiguous/manual_review_required/unresolved`.

The previous score mixed provider score, label containment, type hint, species, granularity, and source reliability. Species conflict and too-specific/conflicting granularity were effectively hard manual-review exits, while type and relation compatibility were incomplete. Relation and endpoint role were not part of the request contract, and multi-provider agreement was not scored. Resolver decisions were written by `EntityResolutionAuditWriter`; high-confidence graph eligibility was controlled by `allow_high_confidence_graph_use`. Downstream graph/conflict paths mostly fail-closed on `allow_high_confidence_graph_use=false`, but their bad-status sets needed the new state names.

## Three States

- `accepted_external_grounded`: credible external/curated/cache grounding passes hard checks, threshold, and uncertainty gates. It may enter formal/reviewable/conflict/hypothesis layers subject to existing graph gates.
- `ambiguous_external_candidate`: credible candidates exist, but evidence is insufficient for formal identity commitment because of score, species unspecified, broader/narrower granularity, weak relation compatibility, small margin, or provider disagreement. It is reviewable only.
- `rejected_external_candidate`: no credible candidate floor or a hard exclusion applies. It is audit-only.

## Evidence Integration

The adjudicator now evaluates hard exclusions before acceptance, then structured score components, provider agreement, top-margin uncertainty, and eligibility projection. Hard exclusions include chemical/gene mismatch, known species incompatibility, measurement-only tokens, incompatible granularity, incompatible relation type, invalid candidate IDs, and ungrounded LLM suggestions.

Species compatibility is `exact`, `ortholog_supported`, `unspecified`, or `incompatible`. Cross-species acceptance requires ortholog provenance in candidate supporting context. Granularity is `exact`, `projectable`, `broader`, `narrower`, or `incompatible`; broader/narrower defaults to ambiguous. Measurement dimensions such as phosphorylation and expression are separated from measured entity identity. Relation compatibility is registry-based and outputs compatible, weak, or incompatible.

## Downstream Safety

Ambiguous and rejected decisions set `allow_high_confidence_graph_use=false`, `conflict_reasoning_eligible=false`, `formal_hypothesis_eligible=false`, and `accepted_for_formal_graph=false`. Legacy resolver projection keeps old graph consumers compatible: accepted becomes legacy `resolved`, ambiguous becomes legacy `ambiguous`, rejected becomes `unresolved_fallback`. Graph, mechanism, and conflict consumers now include the new non-accepted status names in fail-closed status sets.
"""
    (REPORT_DIR / "entity_adjudication_three_state_design.md").write_text(text, encoding="utf-8")


def _gold_sample(transitions: list[dict[str, Any]]) -> None:
    priority = [row for row in transitions if row["transition_bucket"].startswith(("A.", "D.")) or row["new_status"] == "ambiguous_external_candidate" or "species" in row["rejection_reason"] or "granularity" in row["rejection_reason"]]
    sample = priority[:150]
    rows = []
    for row in sample:
        rows.append({
            "mention": row["mention"],
            "evidence_sentence": None,
            "species_context": row["species_context"],
            "relation": row["relation"],
            "endpoint_role": row["subject_or_object"],
            "old_decision": row["old_status"],
            "new_decision": row["new_status"],
            "top_k_candidates": row["provider_candidates"],
            "reason_codes": row["reason_codes"],
            "human_label": "",
            "human_canonical_id": "",
            "human_notes": "",
        })
    _write_jsonl(REPORT_DIR / "entity_adjudication_gold_sample.jsonl", rows)
    lines = ["# Entity Adjudication Gold Sample", "", "Human labels are intentionally blank.", ""]
    for row in rows[:80]:
        lines.append(f"- `{row['mention']}` {row['old_decision']} -> {row['new_decision']}; reasons={row['reason_codes']}; human_label=")
    (REPORT_DIR / "entity_adjudication_gold_sample.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    for label, spec in CASES.items():
        summary, case_transitions = _audit_case(label, spec)
        summaries.append(summary)
        transitions.extend(case_transitions)

    _write_json(REPORT_DIR / "entity_adjudication_transition_audit.json", {"cases": summaries, "transitions": transitions})
    _write_json(REPORT_DIR / "entity_adjudication_cross_case_results.json", {"cases": summaries})
    reason_counts = Counter(reason for row in transitions for reason in row["reason_codes"])
    _write_json(REPORT_DIR / "entity_adjudication_reason_distribution.json", dict(reason_counts))
    _write_markdown(summaries, transitions)
    _write_design()
    _gold_sample(transitions)


if __name__ == "__main__":
    main()
