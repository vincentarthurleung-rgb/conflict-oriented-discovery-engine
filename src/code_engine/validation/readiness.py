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
                         external_data_root: str | Path = "data/external", *, network_allowed: bool = False,
                         smoke_report_file: str | Path = "external_api_smoke_reports/external_api_smoke_summary.json") -> dict[str, Any]:
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
        elif plan.get("plan_status") == "placeholder" or plan.get("executable") is False:
            plan_error = "search plan is a non-executable placeholder"
    except (OSError, json.JSONDecodeError) as exc: plan_error = str(exc)
    search_status = "placeholder" if isinstance(plan, dict) and plan.get("plan_status") == "placeholder" else ("ready" if plan_error is None else "missing_or_invalid")
    search = {"ready": plan_error is None, "status": search_status, "path": str(plan_path), "frozen_metadata_present": bool(isinstance(plan, dict) and any("frozen" in str(k).lower() for k in plan)), "reason": plan_error}
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
    smoke_data = {}
    try:
        smoke_data = json.loads(Path(smoke_report_file).read_text(encoding="utf-8")).get("results", {})
    except (OSError, json.JSONDecodeError, AttributeError):
        smoke_data = {}
    if profile:
        routed = route_case_validators(profile, external_data_root=external_data_root)
        routing.update(routed); routing["executed_if_run"] = list(routed["selected_validators"])
        required = set(profile.expected_validators)
        validator_policy = dict(getattr(profile, "validator_policy", {}) or {})
        require_production = bool(validator_policy.get("require_production_validators", True))
        routing["blocked_required_validators"] = [v for v in routed["recommended_but_unavailable"] if v in required] if require_production else []
        routing["required_validator_policy"] = "blocking" if require_production else "warning_only"
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
            smoke = smoke_data.get(validator_id, {})
            production_ready = bool(smoke.get("production_validator_ready", spec.get("runnable_now", False)))
            decision_label = "selected_for_execution" if selected else "recommended_but_unavailable"
            if validator_id == "pmc_oa" and production_ready:
                resource_ready = True
                decision_label = "fulltext_service_configured"
                reason = "PMC OA client configured; smoke test does not download full text"
            resources.append({"validator_id": validator_id, "status": spec.get("status", "not_registered"), "resource_ready": resource_ready,
                "execution_mode": spec.get("execution_mode"), "network_required": spec.get("network_required", False),
                "blocking": validator_id in routing["blocked_required_validators"], "decision": decision_label,
                "reason": reason, "api_smoke_status": smoke.get("status", "not_checked"),
                "api_reachable": smoke.get("status") == "reachable", "production_validator_ready": production_ready,
                "index_summary": {k: detail.get(k) for k in ("selected_signature_count","selected_gene_count","compact_matrix_orientation")} if detail else None})
        blocking.extend(f"required validator unavailable: {v}" for v in routing["blocked_required_validators"])
    policy=dict(getattr(profile,"fulltext_policy",{}) or {}); fulltext_enabled=bool(policy.get("enabled") or (profile and ("full_text_conflict_confirmation" in profile.validation_needs or profile.case_type=="conflict_enriched")))
    cache_ready=Path("data/cache/pmc_idconv").is_dir()
    ft_blocking=[] if (not fulltext_enabled or network_allowed or cache_ready) else ["pmc_oa_fulltext_requires_network_or_cache"]
    fulltext={"enabled":fulltext_enabled,"source":policy.get("source","pmc_oa"),"selection_policy":"conflict_related_only","copyright_policy":"oa_only_skip_non_oa","pmc_client_configured":True,"pmc_network_required":fulltext_enabled,"l1_required_if_oa_available":fulltext_enabled,"l1_ready":llm["ready"] if fulltext_enabled else None,"network_allowed":network_allowed,"max_papers":policy.get("max_papers",20),"publisher_scraping_enabled":False,"ready":not ft_blocking,"blocking_reasons":ft_blocking,"reason":policy.get("reason") if not fulltext_enabled else None}
    blocking.extend(ft_blocking)
    production_by_id = {item["validator_id"]: item["production_validator_ready"] for item in resources}
    warnings = [f"validator production-unavailable: {v}" for v in routing.get("recommended_but_unavailable", []) if v not in routing.get("blocked_required_validators", []) and not production_by_id.get(v, False)]
    return {"schema_version":"case_readiness_report_v1", "created_at":datetime.now(timezone.utc).isoformat(), "case_id":getattr(profile,"case_id",None),
            "ready": not blocking, "blocking_reasons":blocking, "llm":llm, "search_plan":search, "case_profile":profile_status,
            "routing":routing, "resources":resources,"fulltext":fulltext, "warnings": warnings,
            "api_reachability_is_production_readiness": False, "smoke_report_path": str(smoke_report_file)}

def write_readiness_report(report: dict[str, Any], output_root: str | Path = "readiness_reports") -> tuple[Path, Path]:
    root=Path(output_root); root.mkdir(parents=True, exist_ok=True); case_id=report.get("case_id") or "unknown_case"
    jp=root/f"{case_id}_readiness_report.json"; mp=root/f"{case_id}_readiness_report.md"
    jp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=[f"# {case_id} Readiness Report","",f"Overall ready: **{str(report['ready']).lower()}**","","## Validator routing",""]
    lines += [f"- `{r['validator_id']}`: {r['decision']}; API smoke `{r.get('api_smoke_status', 'not_checked')}`; production ready `{str(r.get('production_validator_ready', False)).lower()}` ({r['reason']})" for r in report["resources"]]
    if report["blocking_reasons"]: lines += ["","## Blocking reasons",""]+[f"- {x}" for x in report["blocking_reasons"]]
    mp.write_text("\n".join(lines)+"\n",encoding="utf-8"); return jp,mp
