"""Audit L2 canonicalization and preview generic graph-salvage candidates."""
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
from code_engine.normalization.graph_eligibility import apply_graph_eligibility

def _rows(path):
 try:return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
 except (OSError,json.JSONDecodeError):return []
def _write_jsonl(path,rows):Path(path).write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")
def audit(run_dir):
 root=Path(run_dir);a=root/"artifacts";retained=_rows(a/"l2_retained_observations.jsonl");core=_rows(a/"l2_core_graph_observations.jsonl")
 missing_s=[x for x in retained if not x.get("subject_canonical_id")];missing_o=[x for x in retained if not x.get("object_canonical_id")];missing_d=[x for x in retained if str(x.get("direction") or "unknown") in {"unknown",""}]
 salvaged=[apply_graph_eligibility(x,existing_conflict_eligible=bool(x.get("conflict_reasoning_eligible") or x.get("canonical_graph_eligible"))) for x in retained];salvaged=[x for x in salvaged if x.get("graph_observation_eligible")]
 subject=Counter(str(x.get("subject_raw") or x.get("subject") or "") for x in missing_s);obj=Counter(str(x.get("object_raw") or x.get("object") or "") for x in missing_o);rel=Counter(str(x.get("relation_raw") or x.get("relation_family") or "") for x in missing_d)
 entity_missing=len(missing_s)+len(missing_o); fix="mixed" if entity_missing and missing_d else "entity_type_coverage" if entity_missing else "direction_mapping" if missing_d else "seed_gate_too_strict"
 profile={}
 try:profile=json.loads((a/"case_domain_profile.json").read_text())
 except (OSError,json.JSONDecodeError):pass
 summary={"case_id":profile.get("case_id") or root.name,"retained_observation_count":len(retained),"core_graph_observation_count":len(core),"missing_subject_canonical_id_count":len(missing_s),"missing_object_canonical_id_count":len(missing_o),"missing_direction_count":len(missing_d),"salvage_candidate_count":len(salvaged),"top_unresolved_subject_strings":[{"text":k,"count":v} for k,v in subject.most_common(20)],"top_unresolved_object_strings":[{"text":k,"count":v} for k,v in obj.most_common(20)],"top_unresolved_relation_strings":[{"text":k,"count":v} for k,v in rel.most_common(20)],"recommended_fix_class":fix}
 return summary,missing_s,missing_o,missing_d,salvaged
def write(result,output_root):
 summary,ms,mo,md,salvaged=result;root=Path(output_root);root.mkdir(parents=True,exist_ok=True)
 (root/"l2_canonicalization_audit_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n")
 for name,rows in (("missing_subject_canonical_examples.jsonl",ms[:100]),("missing_object_canonical_examples.jsonl",mo[:100]),("missing_direction_examples.jsonl",md[:100]),("salvage_candidate_observations.jsonl",salvaged)):_write_jsonl(root/name,rows)
 lines=["# L2 Canonicalization Audit","",f"Case: `{summary['case_id']}`",f"Recommended fix: **{summary['recommended_fix_class']}**","",f"- Retained: {summary['retained_observation_count']}",f"- Core graph: {summary['core_graph_observation_count']}",f"- Missing subject IDs: {summary['missing_subject_canonical_id_count']}",f"- Missing object IDs: {summary['missing_object_canonical_id_count']}",f"- Missing direction: {summary['missing_direction_count']}",f"- Reviewable graph salvage candidates: {summary['salvage_candidate_count']}","","Local identifiers are reviewable run-local canonicalization, not external ontology validation."]
 (root/"l2_canonicalization_audit_report.md").write_text("\n".join(lines)+"\n")
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--run-dir",required=True);p.add_argument("--output-root",required=True);a=p.parse_args(argv);result=audit(a.run_dir);write(result,a.output_root);print(json.dumps(result[0],indent=2,ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
