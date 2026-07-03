"""Trace a case run without mutating runs or fabricating scientific output."""
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path

def _json(path,default=None):
 try:return json.loads(Path(path).read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError):return {} if default is None else default
def _rows(path):
 try:return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
 except (OSError,json.JSONDecodeError):return []
def _count(path):
 try:return sum(bool(x.strip()) for x in Path(path).read_text(encoding="utf-8").splitlines())
 except OSError:return 0

def audit_case_run(case_bundle,source_run,final_run):
 bundle,source,final=map(Path,(case_bundle,source_run,final_run)); sa,fa=source/"artifacts",final/"artifacts"
 manifest=_json(bundle/"case_bundle_manifest.json"); l1=_rows(sa/"abstract_l1_claims.jsonl"); retained=_rows(fa/"l2_retained_observations.jsonl"); core=_rows(fa/"l2_core_graph_observations.jsonl")
 exclusion=_rows(fa/"l2_exclusion_audit.jsonl"); reasons=Counter(str(x.get("excluded_from_core_reason") or x.get("excluded_from_retention_reason") or "unspecified") for x in exclusion)
 missing_subject=sum(not (x.get("subject_canonical_id") or (x.get("normalization",{}).get("subject",{}).get("canonical_id"))) for x in retained)
 missing_object=sum(not (x.get("object_canonical_id") or (x.get("normalization",{}).get("object",{}).get("canonical_id"))) for x in retained)
 missing_direction=sum(str(x.get("direction") or "unknown") in {"","unknown","none"} for x in retained)
 validators={}
 for p in sorted(bundle.glob("l7_*_summary.json")):
  if p.name=="l7_external_validation_summary.json":continue
  value=_json(p); validators[value.get("validator_id") or p.stem.removeprefix("l7_").removesuffix("_summary")]={k:value.get(k) for k in ("status","interpretation","mapping_status","failure_type")}
 counts={"search_acquisition_count":_count(sa/"acquired_paper_provenance.jsonl"),"l1_input_paper_count":_json(sa/"abstract_l1_summary.json").get("paper_count",0),"l1_success_count":max(0,_json(sa/"abstract_l1_summary.json").get("paper_count",0)-_count(sa/"abstract_l1_errors.jsonl")),"l1_failure_count":_count(sa/"abstract_l1_errors.jsonl"),"raw_extracted_claim_count":len(l1),"l2_retained_count":len(retained),"l2_filtered_count":_count(fa/"l2_excluded_observations.jsonl"),"core_observation_count":len(core),"canonicalization_failure_count":sum(not x.get("canonical_graph_eligible",False) for x in retained),"missing_subject_canonical_id_count":missing_subject,"missing_object_canonical_id_count":missing_object,"missing_direction_count":missing_direction,"l3_conflict_count":_count(fa/"graph_conflict_candidates.jsonl"),"hypothesis_input_count":_count(fa/"hypothesis_candidates.jsonl"),"fulltext_candidate_count":_count(bundle/"l35_fulltext_candidate_papers.jsonl")}
 if not counts["l1_input_paper_count"]: diagnosis="NO_L1_INPUT"; stage="L1_INPUT"
 elif not counts["raw_extracted_claim_count"]: diagnosis="L1_EXTRACTION_EMPTY"; stage="L1_EXTRACTION"
 elif not counts["core_observation_count"] and counts["canonicalization_failure_count"]>=counts["l2_retained_count"]>0: diagnosis="CANONICALIZATION_FAILED"; stage="L2_CANONICALIZATION_GATE"
 elif not counts["core_observation_count"]: diagnosis="L2_FILTERED_ALL"; stage="L2_CORE_GATE"
 elif not counts["l3_conflict_count"]: diagnosis="NO_CONFLICT_CANDIDATES"; stage="L3_CONFLICT"
 elif not counts["hypothesis_input_count"]: diagnosis="NO_HYPOTHESIS_INPUTS"; stage="HYPOTHESIS"
 elif not counts["fulltext_candidate_count"]: diagnosis="FULLTEXT_NO_CANDIDATES"; stage="FULLTEXT_SELECTION"
 else: diagnosis="UNKNOWN"; stage="UNKNOWN"
 required=("pipeline_stage_summary.json","validator_selection_report.json","l7_external_validation_summary.json")
 empty=[name for name in required if not _json(bundle/name)]
 consistency={"required_summary_empty":empty,"manifest_core_count":manifest.get("core_observation_count"),"observed_core_count":len(core),"consistent":not empty and manifest.get("core_observation_count")==len(core)}
 if manifest.get("core_observation_count")!=len(core): diagnosis="BUNDLE_EXPORT_INCONSISTENCY";stage="BUNDLE_EXPORT"
 zero={"is_zero_claim_case":not core,"diagnosis":diagnosis,"stage_where_data_was_lost":stage,"primary_filter_reasons":dict(reasons.most_common(12)),"explanation":"Execution passed, but no core observations survived." if not core else None}
 return {"schema_version":"case_run_forensic_audit_v1","case_id":manifest.get("case_id") or bundle.name,"counts":counts,"l2_filter_reasons":dict(reasons),"validator_statuses":validators,"bundle_export_consistency":consistency,"zero_claim_diagnosis":zero}

def write(report,output_root):
 root=Path(output_root);root.mkdir(parents=True,exist_ok=True)
 (root/"forensic_audit_summary.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
 (root/"stage_count_trace.json").write_text(json.dumps(report["counts"],indent=2,ensure_ascii=False)+"\n")
 (root/"zero_claim_diagnosis.json").write_text(json.dumps(report["zero_claim_diagnosis"],indent=2,ensure_ascii=False)+"\n")
 z=report["zero_claim_diagnosis"]; lines=["# Case Run Forensic Audit","",f"Case: `{report['case_id']}`",f"Diagnosis: **{z['diagnosis']}**",f"Stage: `{z['stage_where_data_was_lost']}`","","## Stage counts",""]+[f"- {k}: {v}" for k,v in report["counts"].items()]+["","## Filter reasons",""]+[f"- {k}: {v}" for k,v in z["primary_filter_reasons"].items()]+["","No observations, conflicts, hypotheses, or biological edges were fabricated."]
 (root/"forensic_audit_report.md").write_text("\n".join(lines)+"\n")
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--case-bundle",required=True);p.add_argument("--source-run",required=True);p.add_argument("--final-run",required=True);p.add_argument("--output-root",required=True);a=p.parse_args(argv);r=audit_case_run(a.case_bundle,a.source_run,a.final_run);write(r,a.output_root);print(json.dumps(r,indent=2,ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
