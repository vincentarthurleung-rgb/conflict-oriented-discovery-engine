"""Stable freezing and replay of final executable literature search plans."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.query.search_planner import LiteratureSearchPlan

HASH_FIELDS = ("query_string", "source", "query_group", "query_scope", "year_from", "year_to",
               "max_results", "allowed_for_l1_acquisition", "context_strict",
               "allowed_for_context_specific_core", "context_terms_required")


def executable_query_hash(plan: LiteratureSearchPlan | dict[str, Any]) -> str:
    payload = plan.model_dump(mode="json") if isinstance(plan, LiteratureSearchPlan) else plan
    rows = [{key: query.get(key) for key in HASH_FIELDS} for query in payload.get("pubmed_queries", [])]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def freeze_search_plan(plan: LiteratureSearchPlan, path: str | Path, *, run_id: str, query_text: str,
                       semantic_search_intent: dict[str, Any], query_guard_summary: dict[str, Any]) -> dict[str, Any]:
    plan_payload = json.loads(plan.model_dump_json())
    payload = {"artifact_schema_version": "frozen_search_plan.v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by_run_id": run_id, "query_text": query_text, "seed_triple": plan_payload["seed_triple"],
        "semantic_search_intent": semantic_search_intent,
        "planner_model": semantic_search_intent.get("planner_model"),
        "planner_prompt_hash": semantic_search_intent.get("planner_prompt_hash"),
        "query_guard_summary": query_guard_summary, "paper_year_filter": plan_payload["paper_year_filter"],
        "pubmed_queries": plan_payload["pubmed_queries"],
        "search_plan": plan_payload, "executable_query_hash": executable_query_hash(plan), "frozen": True}
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                 default=lambda value: value.model_dump(mode="json") if hasattr(value, "model_dump") else str(value)), encoding="utf-8")
    return payload


def load_frozen_search_plan(path: str | Path, *, fail_if_drift: bool = False) -> tuple[LiteratureSearchPlan, dict[str, Any]]:
    source = Path(path); payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("artifact_schema_version") != "frozen_search_plan.v1" or not payload.get("frozen"):
        raise ValueError("search_plan_file_is_not_frozen_search_plan_v1")
    plan = LiteratureSearchPlan.model_validate(payload.get("search_plan") or {**payload, "intent_id": payload.get("created_by_run_id", "frozen")})
    actual = executable_query_hash(plan); expected = str(payload.get("executable_query_hash") or "")
    drift = bool(expected and actual != expected)
    if drift and fail_if_drift:
        raise ValueError("frozen_search_plan_drift_detected")
    provenance = {"enabled": True, "search_plan_file": str(source.resolve()), "frozen_plan_hash": expected or actual,
        "planner_called": False, "llm_search_intent_called": False, "deterministic_fallback_called": False,
        "query_guard_reapplied": False, "query_guard_changed_plan": False, "search_plan_drift_detected": drift}
    return plan, provenance


__all__ = ["HASH_FIELDS", "executable_query_hash", "freeze_search_plan", "load_frozen_search_plan"]
