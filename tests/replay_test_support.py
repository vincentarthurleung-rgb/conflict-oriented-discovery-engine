import json
from pathlib import Path

def fixture(root:Path):
 profile=root/"profile.json";plan=root/"plan.json";source=root/"source";a=source/"artifacts";a.mkdir(parents=True)
 profile.write_text(json.dumps({"case_id":"synthetic_replay","query":"specific process response","case_type":"conflict_enriched","profile_version":"1.0"}))
 plan.write_text(json.dumps({"case_id":"synthetic_replay","queries":[]}))
 claim={"claim_id":"C1","evidence_id":"C1","paper_id":"P1","subject_raw":"Specific biological process","subject_type":"biological_process","object_raw":"Specific cellular response","object_type":"phenotype","relation_raw":"increased","relation_family":"activation","direction":"unknown","evidence_sentence":"Specific biological process increased Specific cellular response."}
 (a/"abstract_l1_claims.jsonl").write_text(json.dumps(claim)+"\n");(a/"abstract_l1_summary.json").write_text('{"paper_count":1,"successful_l1_papers":1}')
 for name,value in (("case_domain_profile.json",json.loads(profile.read_text())),("domain_profile.json",{}),("intake.json",{}),("semantic_search_intent.json",{}),("acquisition_report.json",{}),("validator_selection_report.json",{"validator_selection":{}}),("l7_external_validation_summary.json",{"status":"skipped","executed_validators":[]}),("pipeline_stage_summary.json",{"status":"completed"}),("graph_conflict_summary.json",{"true_graph_conflict_count":0}),("hypothesis_summary.json",{"formal_hypothesis_count":0})):(a/name).write_text(json.dumps(value))
 (a/"whitebox_case_report.md").write_text("# Replay fixture\n")
 return profile,plan,source
