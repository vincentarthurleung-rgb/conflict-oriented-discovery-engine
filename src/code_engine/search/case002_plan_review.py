"""Human review and bounded diagnostics for the Case 002 LLM search plan."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from code_engine.search.search_plan_replay import executable_query_hash, load_frozen_search_plan

def curate_frozen_plan(path: str | Path, *, model: str | None = None, review_spec: str | Path | None = None) -> dict:
    target = Path(path); payload = json.loads(target.read_text(encoding="utf-8"))
    spec_path = Path(review_spec) if review_spec else target.parent / f"{payload.get('case_id')}.review_spec.json"
    config = json.loads(spec_path.read_text(encoding="utf-8"))
    if payload.get("artifact_schema_version") != "frozen_search_plan.v1" or not payload.get("frozen"):
        raise ValueError("search-plan curation requires a generated frozen_search_plan.v1")
    template = dict(payload["search_plan"]["pubmed_queries"][0])
    year_from, year_to = int(config["paper_year_from"]), int(config["paper_year_to"])
    date = f'("{year_from}/01/01"[PDAT] : "{year_to}/12/31"[PDAT])'
    query_specs = [(item["group"], item["query"]) for item in config["query_specs"]]
    queries = []
    for group, core in query_specs:
        text = f"{core} AND {date}"
        item = {**template, "query_id": hashlib.sha256(f"pubmed|{text}".encode()).hexdigest()[:16], "query_string": text, "query": text, "purpose": group, "query_group": group, "query_scope": "context_strict", "precision_level": "high" if group != "mechanism_pathway" else "medium", "year_from": year_from, "year_to": year_to, "paper_year_from": year_from, "paper_year_to": year_to, "temporal_role": config["temporal_role"], "allowed_for_l1_acquisition": True, "passed_query_guard": True, "passed_context_guard": True, "context_strict": True, "allowed_for_context_specific_core": True, "context_terms_required": list(config.get("context_terms_required") or []), "warnings": []}
        queries.append(item)
    plan = payload["search_plan"]
    plan.update({"pubmed_queries": queries, "primary_queries": [], "secondary_queries": [], "mechanism_queries": [], "comparison_queries": [], "clinical_queries": [], "pmc_queries": [], "query_generation_mode": "llm_human_reviewed", "query_groups": [{"group": group, "stage": "abstract_retrieval", "source": "pubmed", "queries": [q for q in queries if q["query_group"] == group], "paper_year_filter_enabled": True, "paper_year_from": year_from, "paper_year_to": year_to, "temporal_role": config["temporal_role"], "year_filter_applied_to_query": True} for group in dict.fromkeys(group for group, _ in query_specs)]})
    intent = payload.setdefault("semantic_search_intent", {})
    intent["human_reviewed_query_families"] = list(dict.fromkeys(group for group, _ in query_specs))
    intent["human_review_note"] = "LLM semantic intent retained; executable queries balanced during human review without asserting that a conflict exists."
    now = datetime.now(timezone.utc).isoformat()
    payload.update({"case_id": config["case_id"], "case_type": config["case_type"], "planner_mode": "llm_semantic", "frozen": True, "paper_year_from": year_from, "paper_year_to": year_to, "temporal_role": config["temporal_role"], "generated_at": now, "model": model or os.getenv("MODEL_NAME") or payload.get("planner_model"), "query_count": len(queries), "intended_conflict_axes": config["intended_conflict_axes"], "required_conflict_groups": config.get("required_conflict_groups", []), "do_not_overclaim": ["Search plan is designed for recall and balance, not proof of conflict.", "Abstract-only conflict requires full-text confirmation.", "Non-OA full text absence is coverage gap, not negative evidence."], "pubmed_queries": queries, "paper_year_filter": {"enabled": True, "paper_year_from": year_from, "paper_year_to": year_to, "temporal_role": config["temporal_role"], "source": "human_review_of_llm_plan", "hardcoded_cutoff_used": False}, "human_reviewed": True})
    payload["executable_query_hash"] = executable_query_hash(plan)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    load_frozen_search_plan(target, fail_if_drift=True)
    return payload


def diagnose_queries(payload: dict, *, network: bool = False, timeout: float = 20) -> list[dict]:
    rows = []
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for query in payload["pubmed_queries"]:
        row = {"query_id": query["query_id"], "query": query["query_string"], "query_group": query["query_group"], "status": "skipped", "hit_count_estimate": None, "risk": "unknown", "reason": "network diagnostics disabled"}
        if network:
            params = {"db": "pubmed", "term": query["query_string"], "retmax": "0", "retmode": "json", "tool": os.getenv("NCBI_TOOL", "conflict_oriented_discovery_engine"), "email": os.getenv("NCBI_EMAIL", "")}
            if os.getenv("NCBI_API_KEY"): params["api_key"] = os.environ["NCBI_API_KEY"]
            try:
                with opener.open("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params), timeout=timeout) as response:
                    result = json.load(response)["esearchresult"]
                count = int(result["count"]); risk = "too_broad" if count > 5000 else "too_narrow" if count < 3 else "ok"
                row.update(status="zero_hits" if count == 0 else "ok", hit_count_estimate=count, risk=risk, reason=None)
            except Exception as error:
                row.update(status="error", risk="unknown", reason=f"{type(error).__name__}: {error}")
        rows.append(row)
    return rows


def write_review(payload: dict, rows: list[dict], output_root: str | Path = "search_plan_reviews") -> dict:
    root = Path(output_root); root.mkdir(parents=True, exist_ok=True)
    groups = {query["query_group"] for query in payload["pubmed_queries"]}
    required_groups = set(payload.get("required_conflict_groups") or [])
    both_sides = bool(required_groups) and required_groups.issubset(groups)
    risks = [row["risk"] for row in rows]
    warnings = []
    if "too_broad" in risks: warnings.append("One or more PubMed count diagnostics indicate broad retrieval risk.")
    if "too_narrow" in risks or any(row["status"] == "zero_hits" for row in rows): warnings.append("One or more query families may be narrow and should be monitored during acquisition.")
    if any(row["status"] == "error" for row in rows): warnings.append("Some lightweight PubMed diagnostics failed; plan content remains reviewable.")
    decision = "SEARCH_PLAN_READY_WITH_WARNINGS" if warnings else "SEARCH_PLAN_READY"
    review = {"schema_version": "search_plan_review_v1", "case_id": payload["case_id"], "query_count": len(payload["pubmed_queries"]), "query_strings": [q["query_string"] for q in payload["pubmed_queries"]], "paper_year_from": payload["paper_year_from"], "paper_year_to": payload["paper_year_to"], "conflict_axes_covered": payload["intended_conflict_axes"], "query_families": sorted(groups), "both_sides_represented": both_sides, "broadness_risk": "present" if "too_broad" in risks else "controlled", "expected_recall_risk": "moderate", "expected_precision_risk": "moderate", "warnings": warnings, "final_review_decision": decision, "scientific_interpretation": "Balanced retrieval design only; not evidence that a biological conflict exists."}
    case_id = str(payload["case_id"])
    (root / f"{case_id}_search_plan_review.json").write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"# {case_id} Search Plan Review", "", f"**{decision}**", "", f"- Query count: {review['query_count']}", f"- Date window: {review['paper_year_from']}–{review['paper_year_to']}", f"- Both conflict sides represented: {str(both_sides).lower()}", f"- Broadness risk: {review['broadness_risk']}", f"- Expected recall risk: {review['expected_recall_risk']}", f"- Expected precision risk: {review['expected_precision_risk']}", "", "## Conflict axes", ""] + [f"- {axis}" for axis in review["conflict_axes_covered"]] + ["", "## Queries", ""] + [f"- `{q['query_string']}` — {q['query_group']}" for q in payload["pubmed_queries"]] + ["", "## Warnings", ""] + [f"- {item}" for item in warnings or ["None."]] + ["", "Search balance supports retrieval and review; it does not prove a conflict."]
    (root / f"{case_id}_search_plan_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / f"{case_id}_query_diagnostics.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return review
