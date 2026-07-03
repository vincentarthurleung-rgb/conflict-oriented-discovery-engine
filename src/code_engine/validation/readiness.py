"""Read-only readiness checks for domain-aware case execution."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.validation.case_routing import load_case_domain_profile, route_case_validators

REGISTRY_PATH = Path("configs/external_apis/external_api_registry.json")

def load_external_registry(path: str | Path = REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {v["validator_id"]: v for v in data["validators"]}

def check_case_readiness(case_profile: str | Path, search_plan_file: str | Path,
                         external_data_root: str | Path = "data/external") -> dict[str, Any]:
    blocking: list[str] = []
    provider, model = os.getenv("L1_PROVIDER", "").strip().lower(), os.getenv("MODEL_NAME", "").strip()
    key_name = "DEEPSEEK_API_KEY" if provider == "deepseek" else "OPENAI_API_KEY" if provider == "openai" else None
    missing = []
    if not provider: missing.append("L1_PROVIDER")
    if not model: missing.append("MODEL_NAME")
    key_present = bool(key_name and os.getenv(key_name))
    if not key_present: missing.append(key_name or "DEEPSEEK_API_KEY or OPENAI_API_KEY")
    blocking.extend(f"missing {x}" for x in missing)
    llm = {"ready": not missing, "provider": provider or None, "model": model or None,
           "api_key_present": key_present, "missing_env": missing, "blocking_reasons": [f"missing {x}" for x in missing]}

    plan_path = Path(search_plan_file)
    plan_error = None; plan = None
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if not plan: plan_error = "search plan is empty"
    except (OSError, json.JSONDecodeError) as exc: plan_error = str(exc)
    search = {"ready": plan_error is None, "path": str(plan_path), "frozen_metadata_present": bool(isinstance(plan, dict) and any("frozen" in str(k).lower() for k in plan)), "reason": plan_error}
    if plan_error: blocking.append(f"search plan not ready: {plan_error}")

    profile_error = None; profile = None
    try:
        profile = load_case_domain_profile(case_profile)
        if not all((profile.case_id, profile.query, profile.case_type, profile.profile_version)):
            profile_error = "required profile fields are empty"
    except Exception as exc: profile_error = str(exc)
    profile_status = {"ready": profile_error is None, "path": str(case_profile), "case_id": getattr(profile, "case_id", None), "reason": profile_error}
    if profile_error: blocking.append(f"case profile not ready: {profile_error}")

    routing: dict[str, Any] = {"selected_validators": [], "executed_if_run": [], "recommended_but_unavailable": [], "blocked_required_validators": [], "selection_mode": "domain_aware_router"}
    resources = []
    if profile:
        routed = route_case_validators(profile, external_data_root=external_data_root)
        routing.update(routed); routing["executed_if_run"] = list(routed["selected_validators"])
        required = set(profile.expected_validators)
        routing["blocked_required_validators"] = [v for v in routed["recommended_but_unavailable"] if v in required]
        registry = load_external_registry()
        decisions = {d["validator_id"]: d for d in routed["decisions"]}
        for validator_id in dict.fromkeys(routed["selected_validators"] + routed["recommended_but_unavailable"]):
            spec = registry.get(validator_id, {})
            selected = validator_id in routed["selected_validators"]
            summary = Path(external_data_root) / "lincs_l1000/index/GSE70138" / f"{profile.query.split()[0]}_index_summary.json"
            resource_ready = selected
            detail = None
            if validator_id == "lincs_l1000" and summary.is_file():
                detail = json.loads(summary.read_text(encoding="utf-8"))
                resource_ready = True
            reason = "local compact index exists" if resource_ready and validator_id == "lincs_l1000" else spec.get("reason_if_unavailable") or decisions.get(validator_id, {}).get("reason")
            resources.append({"validator_id": validator_id, "status": spec.get("status", "not_registered"), "resource_ready": resource_ready,
                "execution_mode": spec.get("execution_mode"), "network_required": spec.get("network_required", False),
                "blocking": validator_id in routing["blocked_required_validators"], "decision": "selected_for_execution" if selected else "recommended_but_unavailable",
                "reason": reason, "index_summary": {k: detail.get(k) for k in ("selected_signature_count","selected_gene_count","compact_matrix_orientation")} if detail else None})
        blocking.extend(f"required validator unavailable: {v}" for v in routing["blocked_required_validators"])
    return {"schema_version":"case_readiness_report_v1", "created_at":datetime.now(timezone.utc).isoformat(), "case_id":getattr(profile,"case_id",None),
            "ready": not blocking, "blocking_reasons":blocking, "llm":llm, "search_plan":search, "case_profile":profile_status,
            "routing":routing, "resources":resources}

def write_readiness_report(report: dict[str, Any], output_root: str | Path = "readiness_reports") -> tuple[Path, Path]:
    root=Path(output_root); root.mkdir(parents=True, exist_ok=True); case_id=report.get("case_id") or "unknown_case"
    jp=root/f"{case_id}_readiness_report.json"; mp=root/f"{case_id}_readiness_report.md"
    jp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=[f"# {case_id} Readiness Report","",f"Overall ready: **{str(report['ready']).lower()}**","","## Validator routing",""]
    lines += [f"- `{r['validator_id']}`: {r['decision']} ({r['reason']})" for r in report["resources"]]
    if report["blocking_reasons"]: lines += ["","## Blocking reasons",""]+[f"- {x}" for x in report["blocking_reasons"]]
    mp.write_text("\n".join(lines)+"\n",encoding="utf-8"); return jp,mp
