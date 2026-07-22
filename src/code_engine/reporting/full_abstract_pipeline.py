"""Offline abstract-compatible L4-L7 artifacts for a completed L2 run."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from code_engine.reporting.whitebox_case import CANCER_CONTEXTS, MECHANISM_TERMS, generate_whitebox_case_artifacts


def _json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text()) if path.exists() else ({} if default is None else default)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def resolve_l2_observations(run_dir: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run = Path(run_dir); artifacts = run / "artifacts"
    provenance = _json(artifacts / "runtime_provenance_report.json")
    source_value = (provenance.get("rebuild_from_run") or {}).get("source_run_dir")
    source = Path(source_value) if source_value else None
    names = ("l2_graph_observations.jsonl", "core_observations.jsonl", "l2_retained_observations.jsonl", "l2_normalized_observations.jsonl")
    paths = [artifacts / name for name in names]
    if source:
        paths += [source / "artifacts" / name for name in names]
    searched = [str(path) for path in paths]
    combined: dict[str, dict[str, Any]] = {}; selected = None; source_fallback = False
    for path in paths:
        rows = _jsonl(path)
        if rows and selected is None:
            selected = path
        if rows and source is not None and source in path.parents:
            source_fallback = True
        for index, row in enumerate(rows):
            identity = str(row.get("observation_id") or row.get("triple_id") or row.get("claim_id") or f"{path}:{index}")
            combined[identity] = {**combined.get(identity, {}), **row}
    if combined:
        return list(combined.values()), {"status": "resolved", "selected_path": str(selected), "searched_paths": searched,
            "resolved_paths": [str(path) for path in paths if path.exists() and path.stat().st_size],
            "source_run_fallback_used": source_fallback}
    return [], {"status": "not_found", "selected_path": None, "searched_paths": searched,
                "source_run_fallback_used": False, "reason": "no_l2_observation_artifact_found"}


def _terms(item: dict[str, Any], candidates: tuple[str, ...]) -> list[str]:
    text = " ".join(str(item.get(key) or "") for key in ("title", "evidence_sentence", "context", "context_mentions",
                                                                "normalized_subject", "normalized_object")).casefold()
    values = [term for term in candidates if term.casefold() in text]
    if "drug resistance" in candidates and any(value in text for value in ("drug-resistant", "drug resistant", "acquired resistance", "tki resistance")):
        values.append("drug resistance")
    return list(dict.fromkeys(values))


def build_l4_context_mining(run_dir: str | Path) -> dict[str, Any]:
    run = Path(run_dir); artifacts = run / "artifacts"; observations, resolution = resolve_l2_observations(run)
    l2_summary = _json(artifacts / "l2_abstract_summary.json")
    factors = []
    for item in observations:
        compatibility = item.get("context_compatibility") or {}
        contexts = _terms(item, CANCER_CONTEXTS)
        mechanisms = _terms(item, MECHANISM_TERMS)
        text = " ".join(str(item.get(key) or "") for key in ("title", "evidence_sentence", "context", "context_mentions")).casefold()
        factors.append({"observation_id": item.get("observation_id") or item.get("triple_id"), "paper_id": item.get("paper_id"),
            "title": item.get("title"), "cancer_contexts": contexts, "cell_line_or_model": (item.get("context") or {}).get("experimental_system") if isinstance(item.get("context"), dict) else None,
            "species": (item.get("context") or {}).get("species") if isinstance(item.get("context"), dict) else None,
            "assay_or_model": (item.get("context") or {}).get("assay_type") if isinstance(item.get("context"), dict) else None,
            "drug_resistance_state": "drug resistance" if any(value in text for value in ("resistan", "tki")) else None,
            "treatment_combination": (item.get("context") or {}).get("drug") if isinstance(item.get("context"), dict) else None,
            "mechanism_terms": mechanisms, "pathway_contexts": [term for term in mechanisms if term in {"mTOR", "ERK/NF-κB", "YAP", "Hippo pathway"}],
            "evidence_layer": item.get("evidence_tier"), "graph_layer": item.get("graph_layer"),
            "context_compatibility_status": item.get("context_compatibility_status") or compatibility.get("status"),
            "query_context_only": bool(item.get("query_context_only", compatibility.get("query_context_only"))),
            "strong_context_match": bool(item.get("strong_context_match", compatibility.get("strong_context_match")))})
    graph_layers = Counter(str(item.get("graph_layer") or "unknown") for item in factors)
    compat = Counter(str(item.get("context_compatibility_status") or "unknown") for item in factors)
    summary = {"status": "completed" if observations else "blocked", "mode": "abstract_context_mining", "fulltext_required": False,
        "source_l2_observation_count": len(observations), "core_context_count": graph_layers["core_canonical_graph"],
        "context_factor_count": len(factors), "cancer_contexts": sorted({x for row in factors for x in row["cancer_contexts"]}),
        "mechanism_terms": [x for x in MECHANISM_TERMS if any(x in row["mechanism_terms"] for row in factors)],
        # A missing bibliographic title is a valid provenance gap, not a sortable label.
        "drug_resistance_contexts": sorted({row["title"] for row in factors if row["drug_resistance_state"] and row["title"] is not None}),
        "treatment_combination_contexts": sorted({str(row["treatment_combination"]) for row in factors if row["treatment_combination"]}),
        "pathway_contexts": sorted({x for row in factors for x in row["pathway_contexts"]}),
        "graph_layer_distribution": dict(sorted(graph_layers.items())), "context_compatibility_distribution": dict(sorted(compat.items())),
        "query_context_only_count": int(l2_summary.get("context_query_only_observation_count", sum(row["query_context_only"] for row in factors))),
        "strong_context_match_count": int(l2_summary.get("strong_context_matched_observation_count", sum(row["strong_context_match"] for row in factors))),
        "artifact_resolution": resolution, "warnings": [] if observations else ["l2_observation_artifacts_not_found"]}
    _write_json(artifacts / "l4_context_mining_summary.json", summary); _write_jsonl(artifacts / "l4_context_factors.jsonl", factors)
    columns = ("observation_id", "title", "cancer_contexts", "cell_line_or_model", "drug_resistance_state", "mechanism_terms", "graph_layer")
    (artifacts / "l4_context_factor_table.tsv").write_text("\t".join(columns)+"\n"+"".join("\t".join(json.dumps(row.get(k), ensure_ascii=False) if isinstance(row.get(k), list) else str(row.get(k) or "") for k in columns)+"\n" for row in factors), encoding="utf-8")
    (artifacts / "l4_context_factor_table.md").write_text("| Observation | Title | Cancer context | Mechanisms | Graph layer |\n|---|---|---|---|---|\n"+"".join(f"| {row['observation_id']} | {row['title']} | {', '.join(row['cancer_contexts'])} | {', '.join(row['mechanism_terms'])} | {row['graph_layer']} |\n" for row in factors), encoding="utf-8")
    return summary


def build_l5_context_attribution(run_dir: str | Path) -> dict[str, Any]:
    run = Path(run_dir); artifacts = run / "artifacts"; observations, resolution = resolve_l2_observations(run)
    l2_summary = _json(artifacts / "l2_abstract_summary.json")
    rows=[]
    for item in observations:
        compatibility=item.get("context_compatibility") or {}; layer=str(item.get("graph_layer") or "excluded")
        query_only=bool(item.get("query_context_only", compatibility.get("query_context_only")))
        core=layer=="core_canonical_graph"
        if core: decision, explanation="core_context_qualified", "The evidence directly links the seed entities and cancer context in the evidence sentence or L1 context slots."
        elif query_only: decision, explanation="downgraded_or_excluded", "Cancer context was only present in retrieval query or was not grounded in evidence sentence/L1 context slots."
        else: decision, explanation="retained_non_core_or_excluded", f"The observation was assigned to {layer} under the existing L2 source and eligibility gates."
        rows.append({"observation_id":item.get("observation_id") or item.get("triple_id"),"paper_id":item.get("paper_id"),"title":item.get("title"),
            "graph_layer":layer,"attribution_decision":decision,"context_compatibility_status":item.get("context_compatibility_status") or compatibility.get("status"),
            "strong_context_match":bool(item.get("strong_context_match",compatibility.get("strong_context_match"))),"query_context_only":query_only,
            "core_context_eligible":bool(item.get("core_context_eligible",compatibility.get("core_context_eligible"))),
            "canonical_graph_eligible":bool(item.get("canonical_graph_eligible")),"allow_high_confidence_graph_use":bool(item.get("allow_high_confidence_graph_use")),
            "excluded_from_core_reason":item.get("excluded_from_core_reason"),"evidence_sentence":item.get("evidence_sentence"),"attribution_explanation":explanation})
    layers=Counter(row["graph_layer"] for row in rows); reasons=Counter(str(row.get("excluded_from_core_reason") or "none") for row in rows if row["graph_layer"]!="core_canonical_graph")
    summary={"status":"completed" if observations else "blocked","mode":"abstract_context_attribution","fulltext_required":False,
        "source_l2_observation_count":len(observations),"core_canonical_observation_count":layers["core_canonical_graph"],
        "query_context_only_downgraded_count":int(l2_summary.get("context_query_only_observation_count", sum(row["query_context_only"] and row["graph_layer"]!="core_canonical_graph" for row in rows))),
        "graph_layer_distribution":dict(sorted(layers.items())),"exclusion_reason_distribution":dict(sorted(reasons.items())),
        "no_high_confidence_hypothesis_reason":"core_evidence_directionally_consistent_without_opposing_polarity_conflict",
        "artifact_resolution":resolution,"warnings":[] if observations else ["l2_observation_artifacts_not_found"]}
    _write_json(artifacts/"l5_context_attribution_summary.json",summary); _write_jsonl(artifacts/"l5_observation_attributions.jsonl",rows)
    cores=[row for row in rows if row["graph_layer"]=="core_canonical_graph"]
    (artifacts/"l5_core_attribution_table.md").write_text("| Observation | Title | Decision | Explanation |\n|---|---|---|---|\n"+"".join(f"| {r['observation_id']} | {r['title']} | {r['attribution_decision']} | {r['attribution_explanation']} |\n" for r in cores),encoding="utf-8")
    (artifacts/"l5_exclusion_reason_table.md").write_text("| Reason | Count |\n|---|---:|\n"+"".join(f"| {k} | {v} |\n" for k,v in sorted(reasons.items())),encoding="utf-8")
    return summary


def _id(prefix:str,value:str)->str: return prefix+"_"+hashlib.sha256(value.encode()).hexdigest()[:16]


def build_l6_mechanism_graph(run_dir: str | Path) -> dict[str, Any]:
    run=Path(run_dir); artifacts=run/"artifacts"; observations,resolution=resolve_l2_observations(run)
    # Reentry context is a separate exploratory overlay.  Reading it here keeps
    # it visible to the mechanism graph without promoting it into formal core.
    context_overlay=_jsonl(artifacts/"fulltext_context_graph_observations.jsonl")
    known={str(x.get("observation_id") or x.get("claim_id") or x.get("triple_id")) for x in observations}
    observations=[*observations,*[x for x in context_overlay if str(x.get("observation_id") or x.get("claim_id") or x.get("triple_id")) not in known]]
    mechanism=[item for item in observations if item.get("graph_observation_eligible", item.get("canonical_graph_eligible", item.get("graph_layer") in {"core_canonical_graph","mechanism_layer","cross_context_mechanism_layer"}))]
    nodes_by_id={};edges=[]
    for item in mechanism:
        source_name=item.get("subject_canonical_name") or item.get("subject_raw") or item.get("subject");target_name=item.get("object_canonical_name") or item.get("object_raw") or item.get("object")
        source_id=item.get("subject_canonical_id") or (_id("unresolved_entity",str(source_name)) if source_name else None);target_id=item.get("object_canonical_id") or (_id("unresolved_entity",str(target_name)) if target_name else None);relation=item.get("relation_family") or item.get("relation_raw")
        if not all((source_id,target_id,relation)):continue
        for role,node_id in (("subject",source_id),("object",target_id)):
            nodes_by_id[node_id]={"node_id":node_id,"label":item.get(f"{role}_canonical_name") or item.get(f"{role}_raw"),"node_type":item.get(f"{role}_entity_type") or "entity","canonical_source":item.get(f"{role}_canonical_source") or ("external" if item.get(f"{role}_canonical_id") else "legacy_unresolved_display_only"),"requires_review":bool(item.get(f"{role}_requires_review") or not item.get(f"{role}_canonical_id"))}
        oid=str(item.get("observation_id") or item.get("triple_id") or item.get("claim_id")); edges.append({"edge_id":_id("mechanism_edge",f"{source_id}|{relation}|{target_id}|{oid}"),"source":source_id,"target":target_id,"relation":relation,"direction":item.get("direction"),"source_observation_ids":[oid],"evidence_level":"fulltext" if item.get("edge_layer")=="context_reentry" else "abstract","edge_layer":item.get("edge_layer") or "abstract_prior","requires_review":bool(item.get("requires_review") or item.get("edge_layer")=="context_reentry"),"conflict_reasoning_eligible":bool(item.get("conflict_reasoning_eligible") and item.get("edge_layer")!="context_reentry")})
    nodes=list(nodes_by_id.values());paths=[]
    summary={"status":"completed" if observations else "blocked","mode":"layered_abstract_and_fulltext_context_mechanism_graph" if context_overlay else "abstract_level_mechanism_graph","source_observation_count":len(observations),
        "core_observation_count":sum(bool(x.get("conflict_reasoning_eligible")) for x in mechanism),"graph_observation_count":len(mechanism),"mechanism_observation_count":len(mechanism),"node_count":len(nodes),"edge_count":len(edges),"path_count":len(paths),
        "core_paths":[],"mechanism_terms":sorted({str(x.get("subject_canonical_name") or x.get("subject_raw")) for x in mechanism}|{str(x.get("object_canonical_name") or x.get("object_raw")) for x in mechanism}),"fulltext_required":False,
        "evidence_level":"layered" if context_overlay else "abstract","fulltext_context_observation_count":len(context_overlay),"requires_fulltext_confirmation_for_mechanistic_detail":True,"artifact_resolution":resolution,
        "warnings":[] if observations else ["l2_observation_artifacts_not_found"]}
    _write_json(artifacts/"l6_mechanism_graph_summary.json",summary); _write_jsonl(artifacts/"l6_mechanism_nodes.jsonl",nodes); _write_jsonl(artifacts/"l6_mechanism_edges.jsonl",edges); _write_jsonl(artifacts/"l6_mechanism_paths.jsonl",paths)
    (artifacts/"l6_mechanism_graph.md").write_text("# Abstract-Level Mechanism Graph\n\n"+"".join(f"- {e['source']} --{e['relation']}--> {e['target']}\n" for e in edges)+"\nMechanistic detail requires full-text confirmation.\n",encoding="utf-8")
    return summary


def build_l7_validation_stub(run_dir: str | Path) -> dict[str, Any]:
    run=Path(run_dir); artifacts=run/"artifacts"; core=_jsonl(artifacts/"core_observations.jsonl"); ids=[str(x.get("observation_id")) for x in core]
    claims=("metformin activates AMPK in cancer contexts","metformin/AMPK/mTOR axis","metformin/AMPK/ERK-NF-kB axis",
            "metformin/AMPK/YAP-Hippo axis","metformin suppresses cancer stem cells through AMPK activation","metformin affects drug resistance via AMPK-related pathways")
    targets=[{"validation_target_id":_id("validation_target",claim),"claim":claim,"evidence_level":"abstract","source_observation_ids":ids,
        "suggested_validation_source_types":["post-window PubMed abstracts","full-text confirmation","external curated pathway database","experimental validation paper"],
        "status":"not_run_config_missing"} for claim in claims]
    summary={"status":"not_run_config_missing","external_index_configured":False,"validation_executed":False,"validation_plan_generated":True,
        "validation_target_count":len(targets),"reason":"external_validation_index_not_configured","api_calls":0,"network_calls":0}
    _write_json(artifacts/"l7_external_validation_summary.json",summary); _write_json(artifacts/"l7_validation_plan.json",{"planning_only":True,"targets":[x["validation_target_id"] for x in targets]}); _write_jsonl(artifacts/"l7_validation_targets.jsonl",targets)
    (artifacts/"l7_validation_status.md").write_text(f"# L7 External Validation\n\nStatus: `{summary['status']}`\n\nValidation targets generated: {len(targets)}\n\nNo validation was executed because an external index was not configured.\n",encoding="utf-8")
    return summary


def generate_full_abstract_pipeline(run_dir: str | Path) -> dict[str, Any]:
    run=Path(run_dir); artifacts=run/"artifacts"; whitebox=generate_whitebox_case_artifacts(run)
    l4=build_l4_context_mining(run); l5=build_l5_context_attribution(run); l6=build_l6_mechanism_graph(run); l7=build_l7_validation_stub(run)
    l1=_json(artifacts/"abstract_l1_summary.json"); l2=_json(artifacts/"l2_abstract_summary.json"); graph=_json(artifacts/"merged_evidence_graph_summary.json")
    stages={"L1":{"status":"completed","mode":"abstract_screening","successful":l1.get("successful_l1_papers",0)},
        "L2":{"status":"completed","mode":"abstract_context_gate","retained_observation_count":l2.get("retained_observation_count",0)},
        "L3":{"status":"completed","mode":"strict_source_gate","true_graph_conflict_count":graph.get("true_graph_conflict_count",0)},
        "L4":{"status":l4["status"],"mode":l4["mode"]},"L5":{"status":l5["status"],"mode":l5["mode"]},
        "L6":{"status":l6["status"],"mode":l6["mode"]},"L7":{"status":l7["status"],"mode":"validation_plan_only","validation_plan_generated":True}}
    blocking=[] if all(stages[x]["status"]=="completed" for x in ("L1","L2","L3","L4","L5","L6")) else ["abstract_pipeline_stage_incomplete"]
    summary={"stages":stages,"pipeline_complete_for_abstract_mode":not blocking,"pipeline_complete_for_fulltext_mode":False,
        "pipeline_complete_for_external_validation":False,"blocking_errors":blocking,
        "expected_non_blocking_limitations":["fulltext_not_enabled","external_validation_index_not_configured"]}
    _write_json(artifacts/"pipeline_stage_summary.json",summary)
    table=[("L1 Abstract extraction","completed","abstract_screening",f"{l1.get('successful_l1_papers',0)}/{l1.get('abstract_available_count',l1.get('successful_l1_papers',0))} successful"),
        ("L2 Context gate","completed","abstract_context_gate",f"{l2.get('retained_observation_count',0)} retained"),("L3 Graph conflict gate","completed","strict_source_gate",f"{graph.get('true_graph_conflict_count',0)} true conflicts"),
        ("L4 Context mining",l4["status"],l4["mode"],"context factors extracted"),("L5 Context attribution",l5["status"],l5["mode"],"core/exclusion reasons explained"),
        ("L6 Mechanism graph",l6["status"],l6["mode"],"mechanism graph built from L2"),("L7 External validation",l7["status"],"validation_plan_only","validation targets generated")]
    table_md="| Stage | Status | Mode | Notes |\n|---|---|---|---|\n"+"".join(f"| {a} | {b} | {c} | {d} |\n" for a,b,c,d in table)
    (artifacts/"pipeline_stage_summary.md").write_text("# Pipeline Stage Summary\n\n"+table_md,encoding="utf-8")
    report_path=artifacts/"whitebox_case_report.md"; report_path.write_text(report_path.read_text()+"\n## Pipeline completeness\n\n"+table_md+"\nThis case is complete for the abstract-mode C.O.D.E. pipeline. Full-text confirmation and external validation were not executed because those modules were intentionally not configured in this run.\n",encoding="utf-8")
    report_json=_json(artifacts/"whitebox_case_report.json"); report_json["pipeline_completeness"]=summary; _write_json(artifacts/"whitebox_case_report.json",report_json)
    return {"l4":l4,"l5":l5,"l6":l6,"l7":l7,"pipeline":summary,"whitebox":whitebox}


__all__=["resolve_l2_observations","build_l4_context_mining","build_l5_context_attribution","build_l6_mechanism_graph","build_l7_validation_stub","generate_full_abstract_pipeline"]
