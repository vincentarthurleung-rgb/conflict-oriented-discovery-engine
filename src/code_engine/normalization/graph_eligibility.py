"""Generic, provenance-preserving graph salvage for retained observations."""
from __future__ import annotations
import hashlib,re,unicodedata

TYPE_ALIASES={"process":"biological_process","biological process":"biological_process","cellular_process":"biological_process","response":"cellular_response","treatment response":"treatment_response","resistance":"treatment_response","condition":"condition","cancer_type":"disease","disease_or_condition":"disease","model":"model_system","experimental system":"model_system","mechanism":"mechanism_state"}
LOCAL_TYPES={"biological_process","cellular_response","treatment_response","phenotype","disease","pathway","experimental_context","condition","mechanism_state","cell_type","model_system"}
MEANINGLESS={"effect","role","level","study","result","finding","cancer","cell","cells"}
POSITIVE=("increase","promot","induc","activat","enhanc","upregulat","stimulat","facilitat")
NEGATIVE=("decrease","inhibit","suppress","reduc","attenuat","block","downregulat","impair")
ASSOCIATIVE=("associate","correlat","linked to","related to","interact")
CONTEXT=("context dependent","context-dependent","dual role","both promote and inhibit","bidirectional")

def normalize_entity_type(value:str|None,text:str|None=None)->str:
    raw=str(value or "unknown").strip().casefold().replace("/"," ").replace("-","_")
    if raw in TYPE_ALIASES:return TYPE_ALIASES[raw]
    if raw in {"gene","protein","compound","drug","disease","pathway","biological_process","phenotype","treatment_response","experimental_context","cell_type","model_system","condition","mechanism_state","cellular_response"}:return raw
    folded=str(text or "").casefold()
    if any(token in folded for token in (" resistance","resistance to","sensitivity","response to")):return "treatment_response"
    if any(token in folded for token in (" survival","cell death","proliferation","migration","invasion")):return "phenotype"
    if raw in {"biological_process","cellular process"} or folded.endswith(("tion","sis")):return "biological_process"
    return "unknown"

def local_canonical_id(text:str|None,entity_type:str|None):
    label=unicodedata.normalize("NFKC",str(text or "")).strip(); kind=normalize_entity_type(entity_type,label)
    folded=re.sub(r"\s+"," ",label.casefold()).strip(" .,:;()[]")
    if kind not in LOCAL_TYPES or folded in MEANINGLESS or len(folded)<3 or not re.search(r"[a-zA-Z]",folded):return None
    slug=re.sub(r"[^a-z0-9]+","_",folded).strip("_")
    if not slug:return None
    if len(slug)>64:slug=slug[:48].rstrip("_")+"_"+hashlib.sha256(folded.encode()).hexdigest()[:12]
    return {"canonical_id":f"LOCAL:{kind}:{slug}","canonical_source":"local_case_canonicalization","canonical_confidence":"medium" if kind!="condition" else "low","external_mapping_status":"not_mapped","requires_review":True,"entity_type":kind}

def normalize_direction(relation:str|None,current:str|None=None)->dict:
    existing=str(current or "").casefold()
    if existing in {"positive","negative","associative","context_dependent"}:return {"direction":existing,"direction_source":"explicit_relation_phrase","direction_confidence":"high"}
    text=str(relation or "").casefold()
    if any(x in text for x in CONTEXT): value="context_dependent"
    elif any(x in text for x in POSITIVE): value="positive"
    elif any(x in text for x in NEGATIVE): value="negative"
    elif any(x in text for x in ASSOCIATIVE): value="associative"
    else:value="unknown"
    return {"direction":value,"direction_source":"inferred_from_predicate" if value!="unknown" else "not_inferred","direction_confidence":"medium" if value!="unknown" else "low"}

def apply_graph_eligibility(observation:dict,*,existing_conflict_eligible:bool=False)->dict:
    value=dict(observation); local_used=False
    for role in ("subject","object"):
        text=value.get(f"{role}_canonical_name") or value.get(f"{role}_raw") or value.get(role)
        kind=normalize_entity_type(value.get(f"{role}_entity_type") or value.get(f"{role}_type"),text)
        value[f"{role}_entity_type"]=kind
        if not value.get(f"{role}_canonical_id"):
            local=local_canonical_id(text,kind)
            if local:
                value[f"{role}_canonical_id"]=local["canonical_id"]; value[f"{role}_canonical_source"]=local["canonical_source"];value[f"{role}_canonical_confidence"]=local["canonical_confidence"];value[f"{role}_external_mapping_status"]=local["external_mapping_status"];value[f"{role}_requires_review"]=True;local_used=True
    direction=normalize_direction(value.get("relation_raw") or value.get("relation_family"),value.get("direction"));value.update(direction)
    predicate=str(value.get("relation_family") or value.get("relation_raw") or "").strip()
    provenance=bool(value.get("evidence_sentence") and (value.get("paper_id") or value.get("evidence_id") or value.get("claim_id")))
    graph_ok=bool(value.get("subject_canonical_id") and value.get("object_canonical_id") and predicate and provenance and direction["direction"]!="unknown")
    conflict_reasons=[]
    if not graph_ok: conflict_reasons.append("not_graph_observation_eligible")
    if local_used: conflict_reasons.append("local_canonical_id_requires_review")
    if direction["direction"] not in {"positive","negative"}: conflict_reasons.append("direction_not_conflict_eligible")
    conflict_ok=bool(graph_ok and existing_conflict_eligible and not conflict_reasons)
    value.update({"graph_observation_eligible":graph_ok,"conflict_reasoning_eligible":conflict_ok,"conflict_ineligibility_reasons":conflict_reasons,"requires_review":bool(local_used or not conflict_ok),"local_canonicalization_used":local_used})
    return value

__all__=["normalize_entity_type","local_canonical_id","normalize_direction","apply_graph_eligibility"]
