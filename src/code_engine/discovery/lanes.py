"""Recall-oriented, explicitly non-strict evidence lanes for discovery runs."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl

POSITIVE={"positive","increase","increased","promote","promotes","activate","activated","induce","induced","upregulate","upregulated"}
NEGATIVE={"negative","decrease","decreased","inhibit","inhibited","suppress","suppressed","reduce","reduced","downregulate","downregulated"}
CONTEXTUAL=("context dependent","context-dependent","dual role","opposite effect","whereas","however","but ")


def _rows(path:Path)->list[dict]:
    if not path.is_file(): return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
def _json(path:Path,default=None):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):return default if default is not None else {}
def _norm(value:Any)->str:
    text=str(value or "").casefold().replace("β","beta"); return " ".join(re.findall(r"[a-z0-9]+",text))
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


def _score(item:dict,seed:dict,seed_papers:set[str])->dict:
    subject=_name(seed.get("subject")); obj=_name(seed.get("object")); context=seed.get("context") or {}
    terms=[obj,*list(context.get("terms") or context.get("context_terms") or [])]
    stext=_norm(" ".join(str(item.get(k) or "") for k in ("subject_raw","subject_canonical_name","subject")))
    otext=_norm(" ".join(str(item.get(k) or "") for k in ("object_raw","object_canonical_name","object","evidence_sentence","relation_raw")))
    seed_subject=bool(_norm(subject) and _norm(subject) in stext)
    matched=[term for term in terms if _norm(term) and _norm(term) in otext]
    context_match=bool(matched)
    query=(item.get("query_record") or {}).get("query_group") or item.get("query_group") or item.get("purpose")
    discovery_query=query in {"entity_pair_core","mechanism_context","context_coverage","optional_conflict_hint"}
    direction=_direction(item); paper=str(item.get("canonical_paper_id") or item.get("paper_id") or "")
    same_paper=paper in seed_papers
    mechanism=context_match or discovery_query or str(item.get("graph_layer")) in {"mechanism_layer","cross_context_mechanism_layer"}
    evidence=_norm(item.get("evidence_sentence")); contrast=any(x in evidence for x in CONTEXTUAL)
    score=min(1.0,.45*seed_subject+.25*context_match+.1*discovery_query+.1*(direction!="unknown")+.1*same_paper+.1*contrast)
    reasons=[]
    if seed_subject:reasons.append("seed_subject_match")
    if context_match:reasons.append("seed_object_or_context_match")
    if mechanism:reasons.append("mechanism_or_discovery_context_match")
    if direction!="unknown":reasons.append("direction_available")
    if same_paper:reasons.append("same_paper_as_seed_subject_claim")
    if contrast:reasons.append("contrastive_language")
    local=any(str(item.get(f"{r}_canonical_id") or "").startswith("LOCAL:") for r in ("subject","object")) or bool(item.get("local_canonicalization_used"))
    visible=score>=.25 and bool(item.get("evidence_sentence") or item.get("relation_raw"))
    reviewable=visible and bool(item.get("subject_raw") or item.get("subject_canonical_name")) and bool(item.get("object_raw") or item.get("object_canonical_name"))
    return {**item,"seed_neighborhood_score":round(score,4),"seed_neighborhood_reasons":reasons,
        "seed_subject_match":seed_subject,"seed_object_or_context_match":context_match,"mechanism_context_match":mechanism,
        "direction":direction,"direction_available":direction!="unknown","local_canonical_id_used":local,
        "requires_review":True,"graph_visibility_eligible":reviewable,"strict_core_eligible":bool(item.get("conflict_reasoning_eligible")),
        "conflict_reasoning_eligible":bool(item.get("conflict_reasoning_eligible")),
        "fulltext_escalation_eligible":bool(reviewable and paper and (score>=.35 or direction!="unknown")),
        "discovery_tier":"strict_core" if item.get("conflict_reasoning_eligible") else "reviewable_graph" if reviewable else "seed_neighborhood"}


def _weak_candidates(rows:list[dict])->list[dict]:
    groups=defaultdict(list)
    for item in rows:
        key=_norm(item.get("subject_canonical_name") or item.get("subject_raw") or ("seed_subject" if item.get("seed_subject_match") else ""))
        if key:groups[key].append(item)
    output=[]
    for key,items in groups.items():
        pos=[x for x in items if x.get("direction")=="positive"];neg=[x for x in items if x.get("direction")=="negative"]
        if not(pos and neg):continue
        left=max(pos,key=lambda x:x.get("seed_neighborhood_score",0));right=max(neg,key=lambda x:x.get("seed_neighborhood_score",0))
        ids=[str(x.get("observation_id") or x.get("claim_id") or "") for x in (left,right)]
        stable=hashlib.sha256((key+"|"+"|".join(ids)).encode()).hexdigest()[:20]
        output.append({"candidate_id":f"weak-{stable}","candidate_type":"direction_mismatch","strict_conflict":False,
            "requires_review":True,"confidence":round(min(.75,(left.get("seed_neighborhood_score",0)+right.get("seed_neighborhood_score",0))/2),4),
            "reasons":["positive_and_negative_directions_in_seed_neighborhood"],"supporting_observation_ids":[ids[0]],
            "opposing_or_contextual_observation_ids":[ids[1]],"paper_ids":list(dict.fromkeys(str(x.get("canonical_paper_id") or x.get("paper_id") or "") for x in (left,right))),
            "blocking_reasons_for_strict_conflict":["reviewable_discovery_lane_not_strict_core"],"recommended_next_step":"fulltext_escalation",
            "discovery_tier":"weak_conflict"})
    return output


def build_discovery_lanes(run_dir:str|Path,max_fulltext_papers:int=20)->dict[str,Any]:
    artifacts=Path(run_dir)/"artifacts";retained=_rows(artifacts/"l2_retained_observations.jsonl");seed,seed_source=active_seed(artifacts)
    subject=_norm(_name(seed.get("subject")));seed_papers={str(x.get("canonical_paper_id") or x.get("paper_id") or "") for x in retained if subject and subject in _norm(x.get("subject_raw") or x.get("subject_canonical_name"))}
    scored=[_score(x,seed,seed_papers) for x in retained];neighborhood=[x for x in scored if x["seed_neighborhood_score"]>=.25]
    reviewable=[x for x in neighborhood if x["graph_visibility_eligible"]];weak=_weak_candidates(reviewable)
    weak_papers={p for x in weak for p in x.get("paper_ids",[]) if p};ranked={}
    for item in reviewable:
        paper=str(item.get("canonical_paper_id") or item.get("paper_id") or "")
        if not paper or not item.get("fulltext_escalation_eligible"):continue
        priority=item["seed_neighborhood_score"]+(1 if paper in weak_papers else 0)
        if paper not in ranked or priority>ranked[paper][0]:ranked[paper]=(priority,item)
    selected=[]
    for paper,(priority,item) in sorted(ranked.items(),key=lambda x:x[1][0],reverse=True)[:max_fulltext_papers]:
        selected.append({"paper_id":item.get("paper_id") or paper,"canonical_paper_id":paper,"selected_for_fulltext":True,
            "selection_mode":"discovery_escalation","selection_score":round(priority,4),"source_observation_id":item.get("observation_id"),
            "selection_reasons":["weak_conflict_member" if paper in weak_papers else "seed_neighborhood_reviewable_graph"]})
    audit=[]
    for item in scored:audit.append({k:item.get(k) for k in ("observation_id","paper_id","seed_neighborhood_score","seed_neighborhood_reasons","graph_visibility_eligible","strict_core_eligible","conflict_reasoning_eligible","fulltext_escalation_eligible","discovery_tier","requires_review")})
    loss=Counter(reason for x in retained for reason in x.get("conflict_ineligibility_reasons",[]) or [])
    strict_core=len(_rows(artifacts/"l2_core_graph_observations.jsonl"));strict_conflicts=len(_rows(artifacts/"graph_conflict_candidates.jsonl"));hyp=_json(artifacts/"hypothesis_summary.json",{})
    summary={"schema_version":"discovery_filter_summary_v1","raw_l1_claim_count":len(_rows(artifacts/"abstract_l1_claims.jsonl")),
        "l2_retained_observation_count":len(retained),"seed_neighborhood_observation_count":len(neighborhood),
        "reviewable_graph_observation_count":len(reviewable),"strict_core_observation_count":strict_core,
        "weak_conflict_candidate_count":len(weak),"strict_graph_conflict_count":strict_conflicts,
        "formal_hypothesis_count":int(hyp.get("formal_hypothesis_count",0)),"fulltext_escalation_candidate_count":len(selected),
        "fulltext_l1_claim_count":len(_rows(artifacts/"fulltext_l1_claims.jsonl")),"top_filter_loss_reasons":[{"reason":k,"count":v} for k,v in loss.most_common(10)],
        "fulltext_escalation_mode":"discovery_escalation" if selected else "skipped","fulltext_escalation_paper_count":len(selected),
        "fulltext_escalation_reason":"strict conflicts absent; reviewable discovery signals selected" if selected else "no eligible reviewable papers",
        "selected_from_weak_conflicts":sum(x["canonical_paper_id"] in weak_papers for x in selected),
        "selected_from_seed_neighborhood":sum(x["canonical_paper_id"] not in weak_papers for x in selected),
        "selected_from_reviewable_graph":len(selected),"active_seed_source":seed_source,"active_seed_triple_id":seed.get("triple_id")}
    atomic_write_jsonl(artifacts/"l2_seed_neighborhood_observations.jsonl",iter(neighborhood));atomic_write_json(artifacts/"l2_seed_neighborhood_summary.json",{"count":len(neighborhood),**summary})
    atomic_write_jsonl(artifacts/"l2_reviewable_graph_observations.jsonl",iter(reviewable));atomic_write_json(artifacts/"l2_reviewable_graph_summary.json",{"count":len(reviewable),**summary})
    atomic_write_jsonl(artifacts/"weak_conflict_candidates.jsonl",iter(weak));atomic_write_json(artifacts/"weak_conflict_summary.json",{"count":len(weak),"strict_conflict":False,"requires_review":True})
    atomic_write_jsonl(artifacts/"discovery_filter_audit.jsonl",iter(audit));atomic_write_json(artifacts/"discovery_filter_summary.json",summary)
    atomic_write_jsonl(artifacts/"fulltext_escalation_candidates.jsonl",iter(selected));atomic_write_jsonl(artifacts/"l35_fulltext_candidate_papers.jsonl",iter(selected))
    atomic_write_json(artifacts/"fulltext_escalation_plan.json",{"summary":{k:summary[k] for k in ("fulltext_escalation_mode","fulltext_escalation_candidate_count","fulltext_escalation_paper_count","fulltext_escalation_reason","selected_from_weak_conflicts","selected_from_seed_neighborhood","selected_from_reviewable_graph")},"selected":selected})
    md=["# Discovery Filter Summary","",f"- Raw L1 claims: {summary['raw_l1_claim_count']}",f"- L2 retained: {len(retained)}",f"- Seed neighborhood: {len(neighborhood)}",f"- Reviewable graph: {len(reviewable)}",f"- Weak conflicts: {len(weak)}",f"- Strict core: {strict_core}",f"- Fulltext escalation candidates: {len(selected)}"]
    (artifacts/"discovery_filter_summary.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    return {"summary":summary,"seed_neighborhood":neighborhood,"reviewable_graph":reviewable,"weak_conflicts":weak,"fulltext_candidates":selected,"active_seed":seed}


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


__all__=["active_seed","build_discovery_lanes","synchronize_seed_metadata","validate_seed_metadata"]
