"""Recall-oriented, explicitly non-strict evidence lanes for discovery runs."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl

POSITIVE={"positive","increase","increased","promote","promotes","activate","activated","induce","induced","upregulate","upregulated"}
NEGATIVE={"negative","decrease","decreased","inhibit","inhibited","suppress","suppressed","reduce","reduced","downregulate","downregulated"}
CONTEXTUAL=("context dependent","context-dependent","dual role","opposite effect","whereas","however","but ")

@dataclass(frozen=True)
class DiscoveryRecallPolicy:
    seed_neighborhood_min_score:float=.45
    reviewable_graph_min_score:float=.55
    weak_conflict_min_observation_score:float=.60
    fulltext_escalation_min_observation_score:float=.65
    context_only_max_score:float=.35
    context_only_allowed_in_review:bool=True
    context_only_allowed_in_weak_conflict:bool=False
    context_only_allowed_in_fulltext_escalation:bool=False
    require_anchor_for_reviewable_graph:bool=True
    require_anchor_for_weak_conflict:bool=True
    require_anchor_for_fulltext_escalation:bool=True
    weak_conflict_min_comparability_score:float=.70
    context_split_min_comparability_score:float=.65
    mechanism_split_max_conflict_score:float=.60
    require_object_family_match_for_direction_mismatch:bool=True
    require_relation_family_match_for_direction_mismatch:bool=True
    allow_intervention_effect_pair_as_weak_conflict:bool=False
    broad_context_terms:tuple[str,...]=("cancer","disease","response","progression","context","cellular context","immune context","tumor")

def load_policy(path:str|Path="configs/discovery/anchored_recall_policy.json")->DiscoveryRecallPolicy:
    data=_json(Path(path),{})
    allowed={k:v for k,v in data.items() if k in DiscoveryRecallPolicy.__dataclass_fields__}
    if "broad_context_terms" in allowed:allowed["broad_context_terms"]=tuple(allowed["broad_context_terms"])
    return DiscoveryRecallPolicy(**allowed)


def _rows(path:Path)->list[dict]:
    if not path.is_file(): return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
def _json(path:Path,default=None):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):return default if default is not None else {}
def _norm(value:Any)->str:
    text=str(value or "").casefold()
    for symbol,name in (("α","alpha"),("β","beta"),("γ","gamma"),("δ","delta"),("κ","kappa")):
        text=text.replace(symbol,name)
    return " ".join(re.findall(r"[a-z0-9]+",text))
def _name(value:Any)->str:return str(value.get("name") or "") if isinstance(value,dict) else str(value or "")
def _direction(item:dict)->str:
    current=_norm(item.get("direction"))
    if current in {"positive","negative"}:return current
    text=_norm(" ".join(str(item.get(k) or "") for k in ("direction","relation_raw","relation_family")))
    if any(x in text.split() for x in POSITIVE):return "positive"
    if any(x in text.split() for x in NEGATIVE):return "negative"
    return "unknown"


def active_seed(artifacts:Path)->tuple[dict,str]:
    replay=_json(artifacts/"search_plan_replay.json",{})
    intent=_json(artifacts/"semantic_search_intent.json",{})
    plan=_json(artifacts/"search_plan.json",{})
    if replay.get("enabled") and intent.get("seed_triple"):return intent["seed_triple"],"frozen_search_plan"
    if plan.get("seed_triple"):return plan["seed_triple"],"search_plan"
    intake=_json(artifacts/"intake.json",{})
    return intake.get("unified_seed_triple") or {},"semantic_intake"


def _contains(text:str,term:str)->bool:
    needle=_norm(term);return bool(needle and re.search(r"(?<![a-z0-9])"+re.escape(needle)+r"(?![a-z0-9])",text))

def _preview(item:dict)->dict:
    return {k:item.get(k) for k in ("observation_id","subject_raw","relation_raw","direction","object_raw","evidence_sentence","paper_id","pmid","title","anchor_type","anchor_strength","seed_neighborhood_score")}

def _score(item:dict,seed:dict,seed_papers:set[str],anchor_terms:dict[str,list[str]],policy:DiscoveryRecallPolicy)->dict:
    subject=_name(seed.get("subject")); obj=_name(seed.get("object")); context=seed.get("context") or {}
    terms=[obj,*list(context.get("terms") or context.get("context_terms") or [])]
    stext=_norm(" ".join(str(item.get(k) or "") for k in ("subject_raw","subject_canonical_name","subject")))
    otext=_norm(" ".join(str(item.get(k) or "") for k in ("object_raw","object_canonical_name","object","evidence_sentence","relation_raw")))
    structural=_norm(" ".join(str(item.get(k) or "") for k in ("subject_raw","subject_canonical_name","subject","object_raw","object_canonical_name","object","relation_raw")))
    evidence=_norm(item.get("evidence_sentence"));alltext=f"{structural} {evidence}"
    structural_subject=any(_contains(structural,x) for x in anchor_terms["subject"])
    evidence_subject=any(_contains(evidence,x) for x in anchor_terms["subject"])
    seed_subject=structural_subject or evidence_subject
    direct_subject=_contains(structural,subject)
    broad={_norm(x) for x in policy.broad_context_terms}
    direct_seed_pathway=bool(obj and _norm(obj) not in broad and _contains(structural,obj))
    matched=[term for term in terms if _norm(term) and _norm(term) in otext]
    non_broad=[x for x in matched if _norm(x) not in broad]
    context_match=bool(matched);mechanism_anchor=any(_contains(alltext,x) for x in anchor_terms["mechanism"]);structural_mechanism_anchor=any(_contains(structural,x) for x in anchor_terms["mechanism"])
    query=(item.get("query_record") or {}).get("query_group") or item.get("query_group") or item.get("purpose")
    discovery_query=query in {"entity_pair_core","mechanism_context","context_coverage","optional_conflict_hint"}
    direction=_direction(item); paper=str(item.get("canonical_paper_id") or item.get("paper_id") or "")
    same_paper=paper in seed_papers
    mechanism=mechanism_anchor or bool(non_broad) or str(item.get("graph_layer")) in {"mechanism_layer","cross_context_mechanism_layer"}
    contrast=any(x in evidence for x in CONTEXTUAL)
    if direct_subject:anchor_type,anchor_strength="seed_subject_direct","strong"
    elif structural_subject:anchor_type,anchor_strength="seed_subject_alias","strong"
    elif evidence_subject:anchor_type,anchor_strength="seed_subject_evidence","strong"
    elif direct_seed_pathway:anchor_type,anchor_strength="seed_pathway_direct","strong"
    elif mechanism_anchor:anchor_type,anchor_strength="seed_pathway_family","medium"
    elif same_paper:anchor_type,anchor_strength="same_paper_seed_anchor","medium"
    elif mechanism and direction!="unknown":anchor_type,anchor_strength="seed_pathway_family","medium"
    elif discovery_query and mechanism:anchor_type,anchor_strength="query_provenance_anchor","medium"
    elif context_match:anchor_type,anchor_strength="context_only","weak"
    else:anchor_type,anchor_strength="none","none"
    context_only=anchor_type=="context_only"
    specific_context=bool(mechanism_anchor or non_broad) and not seed_subject and not direct_seed_pathway
    broad_context_only=bool(context_match and not non_broad and not seed_subject and not direct_seed_pathway and not mechanism_anchor)
    before="strong" if mechanism_anchor and not seed_subject and not direct_seed_pathway else anchor_strength
    downgrade_reasons=[]
    if before=="strong" and anchor_strength=="medium":downgrade_reasons.append("specific_context_without_direct_seed_subject_or_pathway")
    score={"strong":.8,"medium":.62,"weak":policy.context_only_max_score,"none":0.0}[anchor_strength]
    score=min(1.0,score+.08*(direction!="unknown")+.05*contrast+.04*bool(item.get("pmid") or item.get("paper_id")))
    if context_only:score=min(score,policy.context_only_max_score)
    reasons=[]
    if seed_subject:reasons.append("seed_subject_match")
    if context_match:reasons.append("seed_object_or_context_match")
    reasons.append(f"anchor:{anchor_type}")
    if mechanism:reasons.append("mechanism_or_discovery_context_match")
    if direction!="unknown":reasons.append("direction_available")
    if same_paper:reasons.append("same_paper_as_seed_subject_claim")
    if contrast:reasons.append("contrastive_language")
    local=any(str(item.get(f"{r}_canonical_id") or "").startswith("LOCAL:") for r in ("subject","object")) or bool(item.get("local_canonicalization_used"))
    anchored=anchor_strength in {"strong","medium"};structural_anchor=structural_subject or structural_mechanism_anchor;visible=score>=policy.seed_neighborhood_min_score and bool(item.get("evidence_sentence") or item.get("relation_raw"))
    reviewable=visible and score>=policy.reviewable_graph_min_score and (anchored or not policy.require_anchor_for_reviewable_graph) and bool(item.get("subject_raw") or item.get("subject_canonical_name")) and bool(item.get("object_raw") or item.get("object_canonical_name"))
    evidence_only=bool(evidence_subject and not structural_subject);generic_subject=_norm(item.get("subject_raw")) in broad
    review_priority=min(1.0,.65*score+.15*(anchor_strength=="strong")+.12*structural_subject+.04*(direction!="unknown")+.02*mechanism+.02*bool(item.get("pmid") or item.get("paper_id"))-.1*generic_subject-.08*evidence_only-.2*context_only)
    priority_reasons=[f"anchor_strength:{anchor_strength}"]+(["structural_seed_anchor"] if structural_subject else [])+(["evidence_only_anchor_downgraded"] if evidence_only else [])+(["direction_available"] if direction!="unknown" else [])+(["mechanism_relevant"] if mechanism else [])+(["context_only_ranked_last"] if context_only else [])
    return {**item,"seed_neighborhood_score":round(score,4),"seed_neighborhood_reasons":reasons,
        "seed_subject_match":seed_subject,"seed_object_or_context_match":context_match,"mechanism_context_match":mechanism,
        "direction":direction,"direction_available":direction!="unknown","local_canonical_id_used":local,
        "anchor_type":anchor_type,"anchor_strength":anchor_strength,"anchor_reasons":reasons,"context_only_match":context_only,
        "anchor_calibration_version":"v2","anchor_strength_before_calibration":before,"anchor_strength_after_calibration":anchor_strength,
        "anchor_downgrade_reasons":downgrade_reasons,"specific_context_anchor":specific_context,
        "direct_seed_subject_mention":seed_subject,"direct_seed_pathway_mention":direct_seed_pathway,"broad_context_only":broad_context_only,
        "pathway_or_mechanism_anchor":mechanism_anchor,"seed_subject_anchor":seed_subject,"structural_seed_or_pathway_anchor":structural_anchor,"same_paper_seed_anchor":same_paper,
        "review_priority_score":round(review_priority,4),"review_priority_reasons":priority_reasons,
        "requires_review":True,"graph_visibility_eligible":reviewable,"strict_core_eligible":bool(item.get("conflict_reasoning_eligible")),
        "conflict_reasoning_eligible":bool(item.get("conflict_reasoning_eligible")),
        "eligible_for_weak_conflict":bool(reviewable and score>=policy.weak_conflict_min_observation_score and anchored and structural_anchor and not context_only),
        "fulltext_escalation_eligible":bool(reviewable and paper and score>=policy.fulltext_escalation_min_observation_score and anchored and not context_only),
        "eligible_for_fulltext_escalation":bool(reviewable and paper and score>=policy.fulltext_escalation_min_observation_score and anchored and not context_only),
        "discovery_tier":"strict_core" if item.get("conflict_reasoning_eligible") else "reviewable_graph" if reviewable else "low_priority_context" if context_only else "seed_neighborhood"}


INTERVENTIONS={"knockdown":("knockdown","knock down","kd"),"depletion":("depletion","depleted"),"silencing":("silencing","silenced","rnai","sirna"),"inhibition":("inhibition","inhibitor","inhibited"),"overexpression":("overexpression","overexpressed"),"activation":("activation","activated"),"stabilization":("stabilization","stabilized"),"treatment":("treatment","treated"),"mutation":("mutation","mutant"),"loss":("loss","deficiency","deficient"),"gain":("gain","gain of function")}
PROCESS_TERMS={"expression":("expression","expressed","protein level","abundance","accumulation"),"activity":("activity","activation","activated"),"localization":("localization","translocation","nuclear","cytoplasmic"),"stability":("stability","stabilization","degradation"),"translation":("translation","translated"),"transcription":("transcription","transcriptional"),"secretion":("secretion","secreted"),"signaling":("signaling","signal transduction"),"metabolism":("metabolism","metabolic","glycolysis","glycolytic","warburg","glucose uptake"),"survival":("survival","viability"),"apoptosis":("apoptosis","apoptotic"),"migration":("migration","migratory"),"invasion":("invasion","invasive")}
COMPARTMENTS={"nucleus":("nucleus","nuclear"),"cytoplasm":("cytoplasm","cytoplasmic","cytosol"),"membrane":("membrane","membranous"),"extracellular":("extracellular","secreted"),"intracellular":("intracellular",),"mitochondria":("mitochondria","mitochondrial")}

def _subject_state(item:dict)->dict:
    raw=_norm(item.get("subject_raw") or item.get("subject_canonical_name"));state="baseline";terms=[]
    for name,variants in INTERVENTIONS.items():
        found=[x for x in variants if _contains(raw,x)]
        if found:state=name;terms=found;break
    base=raw
    for variants in INTERVENTIONS.values():
        for term in variants:base=re.sub(r"(?<![a-z0-9])"+re.escape(_norm(term))+r"(?![a-z0-9])"," ",base)
    base=" ".join(x for x in base.split() if x not in {"of","the","by"})
    return {"base_subject":base or raw,"intervention_state":state,"intervention_terms":terms}

def _process_type(text:str)->str:
    norm=_norm(text)
    return next((name for name,terms in PROCESS_TERMS.items() if any(_contains(norm,x) for x in terms)),"unknown")

def _object_info(item:dict)->dict:
    raw=_norm(item.get("object_raw") or item.get("object_canonical_name"));process=_process_type(raw);base=raw
    compartments=sorted(name for name,terms in COMPARTMENTS.items() if any(_contains(raw,x) for x in terms))
    for terms in PROCESS_TERMS.values():
        for term in terms:base=re.sub(r"(?<![a-z0-9])"+re.escape(_norm(term))+r"(?![a-z0-9])"," ",base)
    base=" ".join(x for x in base.split() if x not in {"of","the","level","levels"})
    return {"base_object":base or raw,"object_family":base or raw,"object_process_type":process,"object_compartments":compartments}

def _family_match(a:str,b:str)->str:
    a=_norm(a);b=_norm(b)
    if not a or not b:return "unknown"
    if a==b:return "exact"
    if _contains(a,b) or _contains(b,a):return "alias"
    aa=set(a.split());bb=set(b.split());overlap=len(aa&bb)/max(1,min(len(aa),len(bb)))
    return "family" if overlap>=.75 else "related" if overlap>=.4 else "mismatch"

def _relation_family(item:dict)->str:
    text=_norm(" ".join(str(item.get(k) or "") for k in ("relation_raw","relation_family","predicate")))
    if any(_contains(text,x) for x in ("bind","associate","interact")):return "physical_or_functional_interaction"
    if any(_contains(text,x) for x in ("require","depend on","necessary for")):return "requirement"
    if any(_contains(text,x) for x in ("translocate","localize","localization","translocation")):return "localization"
    if any(_contains(text,x) for x in ("express","protein level","translation","transcription")):return "expression_or_abundance"
    if _direction(item) in {"positive","negative"}:return "regulation"
    return "unknown"

def _context_terms(item:dict)->list[str]:
    values=item.get("context_terms") or []
    context=item.get("context") or {}
    if isinstance(context,dict):values=[*values,*[str(v) for v in context.values() if isinstance(v,(str,int,float))]]
    return sorted({_norm(x) for x in values if _norm(x)})

def evaluate_claim_comparability(left:dict,right:dict,policy:DiscoveryRecallPolicy|None=None)->dict:
    policy=policy or load_policy();ls=_subject_state(left);rs=_subject_state(right);lo=_object_info(left);ro=_object_info(right)
    subject_match=_family_match(ls["base_subject"],rs["base_subject"]);object_match=_family_match(lo["base_object"],ro["base_object"])
    lf,rf=_relation_family(left),_relation_family(right);relation_match="same" if lf==rf and lf!="unknown" else "compatible" if {lf,rf}<={"regulation","expression_or_abundance"} else "unknown" if "unknown" in {lf,rf} else "mismatch"
    intervention_match="same" if ls["intervention_state"]==rs["intervention_state"] else "compatible" if {ls["intervention_state"],rs["intervention_state"]}=={"baseline"} else "opposite_intervention" if "baseline" in {ls["intervention_state"],rs["intervention_state"]} else "different"
    lc,rc=_context_terms(left),_context_terms(right);context_match="same" if lc and lc==rc else "context_split" if lc and rc and lc!=rc else "compatible"
    subject_points={"exact":1,"alias":.9,"family":.75,"related":.45,"mismatch":0,"unknown":.2}[subject_match]
    object_points={"exact":1,"alias":.9,"family":.8,"related":.45,"mismatch":0,"unknown":.2}[object_match]
    relation_points={"same":1,"compatible":.85,"related":.5,"mismatch":0,"unknown":.25}[relation_match]
    intervention_points={"same":1,"compatible":.9,"opposite_intervention":0,"different":.2,"unknown":.3}.get(intervention_match,.3)
    context_points={"same":1,"compatible":.8,"context_split":.7,"different":.2,"unknown":.3}.get(context_match,.3)
    score=round(.25*subject_points+.35*object_points+.20*relation_points+.15*intervention_points+.05*context_points,4)
    reasons=[];non=[]
    if subject_match in {"exact","alias","family"}:reasons.append("subject_family_comparable")
    else:non.append("subject_family_mismatch")
    if object_match in {"exact","alias","family"}:reasons.append("object_family_comparable")
    else:non.append("object_family_mismatch")
    if lo["object_process_type"]!=ro["object_process_type"] and "unknown" not in {lo["object_process_type"],ro["object_process_type"]}:non.append("object_process_type_mismatch")
    if lo["object_compartments"] and ro["object_compartments"] and lo["object_compartments"]!=ro["object_compartments"]:non.append("object_compartment_mismatch")
    if relation_match in {"same","compatible"}:reasons.append("relation_family_comparable")
    else:non.append("relation_family_mismatch")
    if intervention_match not in {"same","compatible"}:non.append("intervention_state_mismatch")
    if context_match=="context_split":reasons.append("context_split_detected")
    direction_opposed={_direction(left),_direction(right)}=={"positive","negative"}
    process_compatible=(lo["object_process_type"]==ro["object_process_type"] or "unknown" in {lo["object_process_type"],ro["object_process_type"]}) and "object_compartment_mismatch" not in non
    object_ok=object_match in {"exact","alias","family"} and process_compatible;relation_ok=relation_match in {"same","compatible"};intervention_ok=intervention_match in {"same","compatible"} or policy.allow_intervention_effect_pair_as_weak_conflict
    threshold=policy.context_split_min_comparability_score if context_match=="context_split" else policy.weak_conflict_min_comparability_score
    eligible=direction_opposed and score>=threshold and (object_ok or not policy.require_object_family_match_for_direction_mismatch) and (relation_ok or not policy.require_relation_family_match_for_direction_mismatch) and intervention_ok
    label="comparable" if eligible else "partially_comparable" if score>=policy.mechanism_split_max_conflict_score else "not_comparable"
    candidate_type="context_split" if eligible and context_match=="context_split" else "direction_mismatch" if eligible else "intervention_effect_pair" if not intervention_ok else "mechanism_split" if (not object_ok or "object_process_type_mismatch" in non or "object_compartment_mismatch" in non) else "non_comparable_direction_pair"
    return {**ls,"right_base_subject":rs["base_subject"],"right_intervention_state":rs["intervention_state"],**lo,"right_base_object":ro["base_object"],"right_object_process_type":ro["object_process_type"],
        "comparability_score":score,"comparability_label":label,"comparability_reasons":reasons,"non_comparability_reasons":non,
        "subject_family_match":subject_match,"object_family_match":object_match,"relation_family_match":relation_match,"intervention_state_match":intervention_match,
        "context_match":context_match,"context_terms_left":lc,"context_terms_right":rc,"context_split_axes":["unspecified_context"] if context_match=="context_split" else [],"object_compartments_left":lo["object_compartments"],"object_compartments_right":ro["object_compartments"],
        "direction_opposed":direction_opposed,"eligible_for_weak_conflict":eligible,"candidate_type":candidate_type}

def evaluate_weak_candidate_pairs(rows:list[dict],policy:DiscoveryRecallPolicy|None=None)->tuple[list[dict],list[dict]]:
    policy=policy or load_policy()
    groups=defaultdict(list)
    for item in rows:
        key=_norm(item.get("subject_canonical_name") or item.get("subject_raw") or ("seed_subject" if item.get("seed_subject_match") else ""))
        if key:groups[key].append(item)
    output=[];rejected=[]
    for key,items in groups.items():
        eligible=[x for x in items if x.get("eligible_for_weak_conflict")]
        pos=[x for x in eligible if x.get("direction")=="positive"];neg=[x for x in eligible if x.get("direction")=="negative"]
        if not(pos and neg):continue
        for left in sorted(pos,key=lambda x:x.get("seed_neighborhood_score",0),reverse=True)[:25]:
         for right in sorted(neg,key=lambda x:x.get("seed_neighborhood_score",0),reverse=True)[:25]:
          ids=[str(x.get("observation_id") or x.get("claim_id") or "") for x in (left,right)];stable=hashlib.sha256((key+"|"+"|".join(ids)).encode()).hexdigest()[:20]
          strength="strong" if "strong" in {left.get("anchor_strength"),right.get("anchor_strength")} else "medium";comparison=evaluate_claim_comparability(left,right,policy)
          score=round(.55*comparison["comparability_score"]+.45*((left.get("seed_neighborhood_score",0)+right.get("seed_neighborhood_score",0))/2),4)
          candidate={"candidate_id":f"weak-{stable}" if comparison["eligible_for_weak_conflict"] else f"rejected-{stable}","candidate_type":comparison["candidate_type"],"strict_conflict":False,"is_weak_conflict":comparison["eligible_for_weak_conflict"],
            "requires_review":True,"confidence":round(min(.75,score),4),"anchor_strength":strength,"candidate_score":score,
            **comparison,"reasons":["comparable_opposite_direction_pair"] if comparison["eligible_for_weak_conflict"] else ["opposite_direction_but_not_comparable"],"supporting_observation_ids":[ids[0]],
            "opposing_or_contextual_observation_ids":[ids[1]],"supporting_observations_preview":[_preview(left)],"opposing_observations_preview":[_preview(right)],
            "paper_ids":list(dict.fromkeys(str(x.get("canonical_paper_id") or x.get("paper_id") or "") for x in (left,right))),
            "pmids":list(dict.fromkeys(str(x.get("pmid") or x.get("paper_id") or "") for x in (left,right) if x.get("pmid") or x.get("paper_id"))),
            "titles":list(dict.fromkeys(str(x.get("title") or "") for x in (left,right) if x.get("title"))),"evidence_sentences":[x.get("evidence_sentence") for x in (left,right)],
            "blocking_reasons_for_strict_conflict":["reviewable_discovery_lane_not_strict_core",*comparison["non_comparability_reasons"]],"recommended_next_step":"fulltext_escalation" if comparison["eligible_for_weak_conflict"] else "no_conflict_action",
            "discovery_tier":"weak_conflict" if comparison["eligible_for_weak_conflict"] else "non_comparable_direction_pair"}
          (output if comparison["eligible_for_weak_conflict"] else rejected).append(candidate)
    return output,rejected

def build_weak_candidates(rows:list[dict],policy:DiscoveryRecallPolicy|None=None)->list[dict]:
    return evaluate_weak_candidate_pairs(rows,policy)[0]


def score_discovery_records(run_dir:str|Path,records:list[dict],policy:DiscoveryRecallPolicy|None=None)->list[dict]:
    policy=policy or load_policy();artifacts=Path(run_dir)/"artifacts";seed,_=active_seed(artifacts)
    intake=_json(artifacts/"intake.json",{});research=intake.get("research_intent") or {};semantic=intake.get("semantic_intake") or {};semantic_research=semantic.get("research_intent") or {}
    subject_name=_name(seed.get("subject"));subject_terms=[subject_name]
    subject_terms += re.split(r"\s*(?:/|\+|\band\b)\s*",subject_name,flags=re.I)
    subject_terms += list(research.get("primary_entities") or [])+list(semantic_research.get("primary_entities") or [])
    mechanism_terms=list(research.get("mechanism_entities") or [])+list(semantic_research.get("mechanism_entities") or [])
    context=seed.get("context") or {};context_terms=list(context.get("terms") or context.get("context_terms") or [])
    broad={_norm(x) for x in policy.broad_context_terms}
    mechanism_terms += [x for x in context_terms if _norm(x) not in broad and len(_norm(x))>3]
    anchor_terms={"subject":list(dict.fromkeys(x for x in subject_terms if len(_norm(x))>1)),"mechanism":list(dict.fromkeys(x for x in mechanism_terms if len(_norm(x))>3))}
    reference=[*_rows(artifacts/"l2_retained_observations.jsonl"),*records];seed_papers=set()
    for x in reference:
        text=_norm(" ".join(str(x.get(k) or "") for k in ("subject_raw","object_raw","evidence_sentence")))
        if any(_contains(text,t) for t in anchor_terms["subject"]):seed_papers.add(str(x.get("canonical_paper_id") or x.get("paper_id") or ""))
    return [_score(x,seed,seed_papers,anchor_terms,policy) for x in records]

def build_discovery_lanes(run_dir:str|Path,max_fulltext_papers:int=20,policy:DiscoveryRecallPolicy|None=None)->dict[str,Any]:
    policy=policy or load_policy();artifacts=Path(run_dir)/"artifacts";retained=_rows(artifacts/"l2_retained_observations.jsonl");seed,seed_source=active_seed(artifacts)
    scored=score_discovery_records(run_dir,retained,policy)
    neighborhood=[x for x in scored if x["seed_neighborhood_score"]>=policy.seed_neighborhood_min_score and not x["context_only_match"]]
    low_priority=sorted([x for x in scored if x["context_only_match"]],key=lambda x:x["review_priority_score"],reverse=True)
    reviewable=sorted([x for x in neighborhood if x["graph_visibility_eligible"]],key=lambda x:x["review_priority_score"],reverse=True)
    weak,rejected=evaluate_weak_candidate_pairs(reviewable,policy)
    weak_papers={p for x in weak for p in x.get("paper_ids",[]) if p};ranked={}
    for item in reviewable:
        paper=str(item.get("canonical_paper_id") or item.get("paper_id") or "")
        if not paper or not item.get("fulltext_escalation_eligible"):continue
        priority=item["review_priority_score"]+(1 if paper in weak_papers else 0)
        if paper not in ranked or priority>ranked[paper][0]:ranked[paper]=(priority,item)
    selected=[]
    for paper,(priority,item) in sorted(ranked.items(),key=lambda x:x[1][0],reverse=True)[:max_fulltext_papers]:
        weak_ids=[x["candidate_id"] for x in weak if paper in x.get("paper_ids",[])]
        selected.append({"paper_id":item.get("paper_id") or paper,"canonical_paper_id":paper,"pmid":item.get("pmid") or item.get("paper_id"),"pmcid":item.get("pmcid"),"title":item.get("title"),
            "selected_for_fulltext":True,"selection_mode":"discovery_escalation","selection_source":"weak_conflict" if weak_ids else "anchored_reviewable",
            "selection_score":round(priority,4),"selection_reasons":["weak_conflict_member" if weak_ids else "anchored_reviewable_graph"],
            "linked_weak_candidate_ids":weak_ids,"linked_observation_ids":[item.get("observation_id")],"requires_oa_check":True,"fulltext_discovery_mode":True,
            "anchor_strength":item.get("anchor_strength")})
    audit=[]
    for item in scored:audit.append({k:item.get(k) for k in ("observation_id","paper_id","seed_neighborhood_score","seed_neighborhood_reasons","graph_visibility_eligible","strict_core_eligible","conflict_reasoning_eligible","fulltext_escalation_eligible","discovery_tier","requires_review")})
    loss=Counter(reason for x in retained for reason in x.get("conflict_ineligibility_reasons",[]) or [])
    strict_core=len(_rows(artifacts/"l2_core_graph_observations.jsonl"));strict_conflicts=len(_rows(artifacts/"graph_conflict_candidates.jsonl"));hyp=_json(artifacts/"hypothesis_summary.json",{})
    l35_count=len(selected);handoff_warnings=[]
    top=reviewable[:20];context_fraction=sum(x.get("context_only_match",False) for x in reviewable)/len(reviewable) if reviewable else 0.0
    strong_top=sum(x.get("anchor_strength")=="strong" for x in top)/len(top) if top else 0.0
    weak_anchor=sum(x.get("anchor_strength") in {"strong","medium"} for x in weak)/len(weak) if weak else 1.0
    ft_anchor=sum(x.get("anchor_strength") in {"strong","medium"} for x in selected)/len(selected) if selected else 1.0
    summary={"schema_version":"discovery_filter_summary_v1","raw_l1_claim_count":len(_rows(artifacts/"abstract_l1_claims.jsonl")),
        "l2_retained_observation_count":len(retained),"seed_neighborhood_observation_count":len(neighborhood),
        "reviewable_graph_observation_count":len(reviewable),"low_priority_context_observation_count":len(low_priority),"strict_core_observation_count":strict_core,
        "weak_conflict_candidate_count":len(weak),"non_comparable_direction_pair_count":len(rejected),"strict_graph_conflict_count":strict_conflicts,
        "formal_hypothesis_count":int(hyp.get("formal_hypothesis_count",0)),"fulltext_escalation_candidate_count":len(selected),
        "fulltext_l1_claim_count":len(_rows(artifacts/"fulltext_l1_claims.jsonl")),"top_filter_loss_reasons":[{"reason":k,"count":v} for k,v in loss.most_common(10)],
        "fulltext_escalation_mode":"discovery_escalation" if selected else "skipped","fulltext_escalation_paper_count":len(selected),
        "fulltext_escalation_reason":"strict conflicts absent; reviewable discovery signals selected" if selected else "no eligible reviewable papers",
        "selected_from_weak_conflicts":sum(x["canonical_paper_id"] in weak_papers for x in selected),
        "selected_from_seed_neighborhood":sum(x["canonical_paper_id"] not in weak_papers for x in selected),
        "selected_from_reviewable_graph":len(selected),"l35_candidate_paper_count":l35_count,"fulltext_handoff_consistent":not handoff_warnings,"fulltext_handoff_warnings":handoff_warnings,
        "context_only_fraction_in_reviewable":round(context_fraction,4),"strong_anchor_fraction_in_top_20_reviewable":round(strong_top,4),
        "medium_or_strong_anchor_fraction_in_weak_candidates":round(weak_anchor,4),"fulltext_candidates_with_anchor_fraction":round(ft_anchor,4),
        "active_seed_source":seed_source,"active_seed_triple_id":seed.get("triple_id"),"anchored_recall_policy":asdict(policy),
        "weak_conflict_comparability_policy":{k:v for k,v in asdict(policy).items() if "comparability" in k or k.startswith("require_object_family") or k.startswith("require_relation_family") or k.startswith("allow_intervention")}}
    atomic_write_jsonl(artifacts/"l2_seed_neighborhood_observations.jsonl",iter(neighborhood));atomic_write_json(artifacts/"l2_seed_neighborhood_summary.json",{"count":len(neighborhood),**summary})
    atomic_write_jsonl(artifacts/"l2_reviewable_graph_observations.jsonl",iter(reviewable));atomic_write_json(artifacts/"l2_reviewable_graph_summary.json",{"count":len(reviewable),**summary})
    atomic_write_jsonl(artifacts/"l2_low_priority_context_observations.jsonl",iter(low_priority));atomic_write_json(artifacts/"l2_low_priority_context_summary.json",{"count":len(low_priority),"discovery_tier":"low_priority_context","eligible_for_weak_conflict":False,"eligible_for_fulltext_escalation":False})
    atomic_write_jsonl(artifacts/"weak_conflict_candidates.jsonl",iter(weak));atomic_write_json(artifacts/"weak_conflict_summary.json",{"count":len(weak),"strict_conflict":False,"requires_review":True})
    atomic_write_jsonl(artifacts/"non_comparable_direction_pairs.jsonl",iter(rejected));atomic_write_json(artifacts/"non_comparable_direction_pair_summary.json",{"count":len(rejected),"mechanism_split_count":sum(x.get("candidate_type")=="mechanism_split" for x in rejected),"intervention_effect_pair_count":sum(x.get("candidate_type")=="intervention_effect_pair" for x in rejected)})
    atomic_write_jsonl(artifacts/"discovery_filter_audit.jsonl",iter(audit));atomic_write_json(artifacts/"discovery_filter_summary.json",summary)
    atomic_write_jsonl(artifacts/"fulltext_escalation_candidates.jsonl",iter(selected));atomic_write_jsonl(artifacts/"l35_fulltext_candidate_papers.jsonl",iter(selected))
    atomic_write_jsonl(artifacts/"fulltext_discovery_escalation_candidates.jsonl",iter(selected))
    handoff=validate_fulltext_handoff(artifacts);summary.update(handoff)
    atomic_write_json(artifacts/"discovery_filter_summary.json",summary)
    atomic_write_json(artifacts/"l2_seed_neighborhood_summary.json",{"count":len(neighborhood),**summary})
    atomic_write_json(artifacts/"l2_reviewable_graph_summary.json",{"count":len(reviewable),**summary})
    atomic_write_json(artifacts/"fulltext_escalation_plan.json",{"summary":{k:summary[k] for k in ("fulltext_escalation_mode","fulltext_escalation_candidate_count","fulltext_escalation_paper_count","fulltext_escalation_reason","selected_from_weak_conflicts","selected_from_seed_neighborhood","selected_from_reviewable_graph")},"selected":selected})
    calibration={"schema_version":"discovery_precision_recall_calibration_v1",**{k:summary[k] for k in ("raw_l1_claim_count","l2_retained_observation_count","seed_neighborhood_observation_count","reviewable_graph_observation_count","low_priority_context_observation_count","weak_conflict_candidate_count","fulltext_escalation_candidate_count","context_only_fraction_in_reviewable","strong_anchor_fraction_in_top_20_reviewable","medium_or_strong_anchor_fraction_in_weak_candidates","fulltext_candidates_with_anchor_fraction")},
        "estimated_recall_mode":"balanced" if neighborhood else "conservative","estimated_precision_mode":"balanced" if context_fraction<=.35 and weak_anchor>=.8 and ft_anchor>=.8 else "low",
        "recommended_threshold_action":"keep" if context_fraction<=.35 and strong_top>=.4 and weak_anchor>=.8 and ft_anchor>=.8 else "tighten"}
    atomic_write_json(artifacts/"discovery_precision_recall_calibration.json",calibration)
    calibration_md=["# Discovery Precision/Recall Calibration (Proxy)","","These are proxy metrics without a labeled gold standard."]+[f"- {k}: {v}" for k,v in calibration.items() if k!="schema_version"]
    (artifacts/"discovery_precision_recall_calibration.md").write_text("\n".join(calibration_md)+"\n",encoding="utf-8")
    md=["# Discovery Filter Summary","",f"- Raw L1 claims: {summary['raw_l1_claim_count']}",f"- L2 retained: {len(retained)}",f"- Seed neighborhood: {len(neighborhood)}",f"- Reviewable graph: {len(reviewable)}",f"- Low-priority context: {len(low_priority)}",f"- Weak conflicts: {len(weak)}",f"- Strict core: {strict_core}",f"- Fulltext escalation candidates: {len(selected)}"]
    (artifacts/"discovery_filter_summary.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    return {"summary":summary,"calibration":calibration,"seed_neighborhood":neighborhood,"reviewable_graph":reviewable,"low_priority_context":low_priority,"weak_conflicts":weak,"non_comparable_direction_pairs":rejected,"fulltext_candidates":selected,"active_seed":seed}


def synchronize_seed_metadata(run_dir:str|Path)->dict[str,Any]:
    artifacts=Path(run_dir)/"artifacts";seed,source=active_seed(artifacts);canonical=json.dumps(seed,sort_keys=True,ensure_ascii=False)
    seed_hash=hashlib.sha256(canonical.encode()).hexdigest();warnings=[]
    if not (artifacts/"hypothesis_summary.json").is_file():
        return {"active_seed_source":source,"active_seed_triple_id":seed.get("triple_id"),"active_seed_triple_hash":seed_hash,
            "seed_metadata_consistent":True,"seed_metadata_consistency_warnings":["hypothesis_summary_missing_seed_sync_skipped"]}
    summary=_json(artifacts/"hypothesis_summary.json",{})
    previous=summary.get("active_seed_triple") or summary.get("seed_triple")
    if previous and json.dumps(previous,sort_keys=True,ensure_ascii=False)!=canonical:warnings.append("stale_seed_metadata_replaced_with_active_seed")
    summary.update({"active_seed_source":source,"active_seed_triple":seed,"seed_triple":seed,"active_seed_triple_id":seed.get("triple_id"),
        "active_seed_triple_hash":seed_hash,"seed_metadata_consistent":True,"seed_metadata_consistency_warnings":warnings})
    atomic_write_json(artifacts/"hypothesis_summary.json",summary)
    return {"active_seed_source":source,"active_seed_triple_id":seed.get("triple_id"),"active_seed_triple_hash":seed_hash,
        "seed_metadata_consistent":True,"seed_metadata_consistency_warnings":warnings}


def validate_seed_metadata(run_dir:str|Path)->dict[str,Any]:
    artifacts=Path(run_dir)/"artifacts";seed,source=active_seed(artifacts);summary=_json(artifacts/"hypothesis_summary.json",{})
    candidate=summary.get("active_seed_triple") or summary.get("seed_triple")
    consistent=not candidate or json.dumps(candidate,sort_keys=True,ensure_ascii=False)==json.dumps(seed,sort_keys=True,ensure_ascii=False)
    return {"active_seed_source":source,"seed_metadata_consistent":consistent,
        "seed_metadata_consistency_warnings":[] if consistent else ["hypothesis_seed_does_not_match_active_replayed_seed"]}

def validate_fulltext_handoff(artifacts_or_run:str|Path)->dict[str,Any]:
    path=Path(artifacts_or_run);artifacts=path if path.name=="artifacts" else path/"artifacts"
    expected=len(_rows(artifacts/"fulltext_escalation_candidates.jsonl"));actual=len(_rows(artifacts/"l35_fulltext_candidate_papers.jsonl"))
    consistent=expected==actual
    return {"fulltext_escalation_candidate_count":expected,"l35_candidate_paper_count":actual,"fulltext_handoff_consistent":consistent,
        "fulltext_handoff_warnings":[] if consistent else [f"fulltext_handoff_count_mismatch:{expected}!={actual}"]}


__all__=["DiscoveryRecallPolicy","active_seed","build_discovery_lanes","build_weak_candidates","evaluate_claim_comparability","evaluate_weak_candidate_pairs","load_policy","score_discovery_records","synchronize_seed_metadata","validate_fulltext_handoff","validate_seed_metadata"]
