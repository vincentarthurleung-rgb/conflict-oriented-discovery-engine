import json
from pathlib import Path
from code_engine.workflow.steps import run_l2_abstract_step

INTENT={"seed_triple":{"subject":{"name":"metformin","aliases":["metformin"],"type":"drug_or_compound"},"relation":{"name":"activates"},"object":{"name":"AMPK","aliases":["AMPK","AMP-activated protein kinase"],"type":"protein_or_complex"},"context":{"terms":["cancer","cancer cells"]}}}

def claim(cid, subject, obj, sentence):
    return {"claim_id":cid,"paper_id":"P"+cid,"subject_raw":subject,"object_raw":obj,"relation_raw":"activates","direction":"increase","direction_confidence":0.9,"evidence_sentence":sentence,"context_mentions":{"clinical_condition":"cancer"}}

CLAIMS=[
    claim("1","metformin","AMPK","metformin activates AMPK in cancer cells"),
    claim("2","metformin","sorafenib sensitivity","metformin increases sorafenib sensitivity through AMPK activation"),
    claim("3","HCC patients","mortality risk","Cancer patients receiving sorafenib had higher mortality risk"),
    claim("4","EGFR expression","sorafenib resistance","EGFR expression correlates with sorafenib resistance"),
]

def run_case(root: Path):
    a=root/"artifacts"; a.mkdir(parents=True,exist_ok=True)
    (a/"semantic_search_intent.json").write_text(json.dumps(INTENT))
    (a/"domain_profile.json").write_text(json.dumps({"domain_id":"general_biomedical"}))
    (a/"abstract_l1_claims.jsonl").write_text("".join(json.dumps(x)+"\n" for x in CLAIMS))
    return run_l2_abstract_step(run_dir=root,l1_mode="abstract_screening",execute=False,api=False,network=False)
