"""Build a detailed audit for entity normalization decisions."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def build_audit(run_dir: Path, *, top_n: int = 25) -> dict[str, Any]:
    artifacts = run_dir / "artifacts"
    decisions = _rows(artifacts / "entity_resolution_decisions.jsonl")
    by_type: dict[str, Counter] = defaultdict(Counter)
    provider_attempts = Counter()
    provider_candidate_hits = Counter()
    provider_accepts = Counter()
    provider_network_calls = Counter()
    rejection_reasons = Counter()
    unresolved = Counter()
    repeated_network_queries = Counter()
    seen_network_queries: set[tuple[str, str]] = set()
    accepted: list[dict[str, Any]] = []
    boundary_suspects = Counter()
    route_mismatch = Counter()

    for item in decisions:
        req = item.get("request") or {}
        surface = str(req.get("surface") or "")
        etype = str(req.get("l1_entity_type_hint") or "unknown")
        status = str(item.get("normalization_status") or "unknown")
        by_type[etype][status] += 1
        if status in {"unresolved", "manual_review_required", "ambiguous"}:
            unresolved[surface] += 1
        if status == "manual_review_required":
            rejection_reasons[str(item.get("decision_reason") or "manual_review_required")] += 1
        if status in {"resolved_external_grounded", "resolved_curated", "resolved_cache"}:
            selected = item.get("selected_candidate") or {}
            accepted.append({
                "surface": surface,
                "type": etype,
                "canonical_id": selected.get("canonical_id"),
                "canonical_name": selected.get("canonical_name"),
                "provider": selected.get("provider_name"),
                "confidence": item.get("confidence"),
            })
            if selected.get("provider_name"):
                provider_accepts[str(selected["provider_name"])] += 1
        if any(token in surface.casefold() for token in (" expression", " levels", "activation of ", "inhibition of ", "silenced ", "after ", " mg/kg", " nm")):
            boundary_suspects[surface] += 1
        for trace in item.get("provider_trace") or []:
            status_trace = trace.get("status")
            pname = str(trace.get("provider_name") or "unknown")
            if status_trace in {"not_applicable", "not_needed"}:
                if pname not in {"NullProvider", "LocalCuratedProvider", "LocalCacheProvider"}:
                    route_mismatch[f"{etype}->{pname}"] += 1
                continue
            provider_attempts[pname] += 1
            provider_network_calls[pname] += int(trace.get("network_calls_made") or 0)
            if int(trace.get("candidate_count") or 0) > 0:
                provider_candidate_hits[pname] += 1
            key = (pname, surface.casefold())
            if int(trace.get("network_calls_made") or 0) > 0 and key in seen_network_queries:
                repeated_network_queries[f"{pname}:{surface}"] += 1
            if int(trace.get("network_calls_made") or 0) > 0:
                seen_network_queries.add(key)

    provider_stats = {}
    for provider, attempts in provider_attempts.items():
        provider_stats[provider] = {
            "query_count": attempts,
            "candidate_hit_count": provider_candidate_hits[provider],
            "candidate_hit_rate": round(provider_candidate_hits[provider] / attempts, 4) if attempts else 0.0,
            "final_accept_count": provider_accepts[provider],
            "final_accept_rate": round(provider_accepts[provider] / attempts, 4) if attempts else 0.0,
            "network_calls": provider_network_calls[provider],
        }

    summary_path = artifacts / "l2_canonicalization_audit_summary.json"
    l2_summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    return {
        "run_dir": str(run_dir),
        "eligible_entity_mention_count": len(decisions),
        "status_counts": dict(Counter(str(item.get("normalization_status") or "unknown") for item in decisions)),
        "type_status_counts": {key: dict(value) for key, value in sorted(by_type.items())},
        "provider_stats": provider_stats,
        "rejected_candidate_reason_counts": dict(rejection_reasons.most_common(top_n)),
        "top_unresolved_mentions": [{"surface": key, "count": value} for key, value in unresolved.most_common(top_n)],
        "mention_boundary_suspect_count": sum(boundary_suspects.values()),
        "top_mention_boundary_suspects": [{"surface": key, "count": value} for key, value in boundary_suspects.most_common(top_n)],
        "route_mismatch_counts": dict(route_mismatch.most_common(top_n)),
        "repeated_network_query_counts": dict(repeated_network_queries.most_common(top_n)),
        "accepted_result_count": len(accepted),
        "accepted_results_sample": accepted[:top_n],
        "l2_canonicalization_summary": l2_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output")
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args()
    audit = build_audit(Path(args.run_dir), top_n=args.top_n)
    text = json.dumps(audit, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
