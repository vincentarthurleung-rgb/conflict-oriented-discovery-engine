"""Execute selected production-v1 validators and conservatively aggregate L7."""
from __future__ import annotations
import json
from pathlib import Path
from .validator_input_builder import build_validator_input
from .pubmed_post_cutoff_validator import PubMedPostCutoffValidator
from .reactome_validator import ReactomeValidatorV1
from .enrichr_validator import EnrichrValidatorV1

VALIDATORS={"pubmed_post_cutoff":PubMedPostCutoffValidator,"reactome":ReactomeValidatorV1,"enrichr":EnrichrValidatorV1}
CATEGORIES={"pubmed_post_cutoff":"literature_presence","reactome":"pathway_plausibility","enrichr":"gene_set_plausibility"}

def aggregate_l7(artifact_root:str|Path, results:dict[str,dict], unavailable:list[str]|None=None)->dict:
    completed_statuses={"completed","partially_completed","completed_no_mapping","completed_with_warnings"}
    executed=[key for key,value in results.items() if value.get("status") in completed_statuses]
    skipped=[key for key,value in results.items() if value.get("status")=="skipped"]
    accounting={group:[key for key,value in results.items() if (group=="completed" and value.get("status") in {"completed","completed_no_mapping"}) or (group=="completed_with_warnings" and value.get("status") in {"partially_completed","completed_with_warnings"}) or value.get("status")==group] for group in ("completed","completed_with_warnings","skipped","failed")}
    summary={"schema_version":"l7_external_validation_summary_v2","status":"completed" if executed else "not_attempted","executed_validators":executed,"skipped_validators":skipped,"validator_status_accounting":accounting,"validator_results":results,"evidence_categories":{key:CATEGORIES[key] for key in executed},"recommended_but_unavailable":list(unavailable or []),"overall_interpretation":"preliminary" if executed else "not_attempted","semantic_support_refutation_attempted":False,"limitations":["Heterogeneous validator outputs are not interchangeable and are not automatic support or refutation."]}
    path=Path(artifact_root)/"l7_external_validation_summary.json"; path.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); return summary

def run_production_v1_validators(run_dir:str|Path,case_profile:str|Path,search_plan:str|Path,selected:list[str],*,network_enabled:bool,unavailable:list[str]|None=None,transports:dict|None=None)->dict:
    artifacts=Path(run_dir)/"artifacts"; transports=transports or {}
    inputs=build_validator_input(case_profile,search_plan=search_plan,core_observations=artifacts/"core_observations.jsonl",hypothesis_summary=artifacts/"hypothesis_summary.json",mechanism_graph=artifacts/"l6_mechanism_graph_summary.json")
    results={}
    for validator_id in selected:
        factory=VALIDATORS.get(validator_id)
        if factory: results[validator_id]=factory().run(inputs,artifacts,network_enabled=network_enabled,transport=transports.get(validator_id))
    summary=aggregate_l7(artifacts,results,unavailable)
    selection_path=artifacts/"validator_selection_report.json"
    if selection_path.is_file():
        payload=json.loads(selection_path.read_text(encoding="utf-8")); selection=payload.setdefault("validator_selection",{})
        selection["executed_validators"]=summary["executed_validators"]; selection["skipped_validators"]=summary["skipped_validators"]
        selection["recommended_but_unavailable"]=[item for item in summary["recommended_but_unavailable"] if item not in summary["executed_validators"]]
        selection_path.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return summary

__all__=["aggregate_l7","run_production_v1_validators"]
