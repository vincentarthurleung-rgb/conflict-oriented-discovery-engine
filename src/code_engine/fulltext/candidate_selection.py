from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def _read_json(path: Path) -> Any:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return {}
def _read_jsonl(path: Path) -> list[dict]:
    try: return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, json.JSONDecodeError): return []
def select_conflict_related_papers(artifacts_dir: str|Path, *, include_near_conflicts: bool=False, max_papers: int=20) -> dict:
    root=Path(artifacts_dir); selected: dict[str,dict]={}; sources=[]
    discovery=_read_jsonl(root/"fulltext_discovery_escalation_candidates.jsonl") or _read_jsonl(root/"fulltext_escalation_candidates.jsonl")
    if discovery:sources.append("fulltext_discovery_escalation_candidates.jsonl")
    for paper in discovery:
        key=str(paper.get("paper_id") or paper.get("pmid") or paper.get("canonical_paper_id") or "")
        if not key:continue
        selected[key]={**paper,"paper_id":paper.get("paper_id") or key,"selection_reason":paper.get("selection_source") or "discovery_escalation",
            "conflict_candidate_ids":list(paper.get("linked_weak_candidate_ids") or []),"abstract_observation_ids":list(paper.get("linked_observation_ids") or [])}
    candidates=[]
    for name in ("graph_conflict_candidates.jsonl","conflict_graph_candidates.jsonl"):
        rows=_read_jsonl(root/name)
        if rows: candidates.extend(rows); sources.append(name)
    graph=_read_json(root/"graph_conflict_summary.json")
    if graph: candidates.extend(graph.get("candidates",graph.get("graph_conflict_candidates",[]))); sources.append("graph_conflict_summary.json")
    for candidate in candidates:
        is_true=bool(candidate.get("is_true_graph_conflict",candidate.get("true_graph_conflict",candidate.get("status") in {"true_graph_conflict","confirmed"})))
        near=not is_true and include_near_conflicts
        if not (is_true or near): continue
        reason="true_graph_conflict" if is_true else "near_conflict_optional"
        papers=candidate.get("papers") or [{"paper_id":x} for x in candidate.get("paper_ids",[])]
        for paper in papers:
            if not isinstance(paper,dict): paper={"paper_id":paper}
            key=str(paper.get("paper_id") or paper.get("pmid") or paper.get("pmcid") or "")
            if not key: continue
            selected.setdefault(key,{"paper_id":paper.get("paper_id",key),"pmid":paper.get("pmid"),"pmcid":paper.get("pmcid"),"doi":paper.get("doi"),"title":paper.get("title"),"selection_reason":reason,"conflict_relation":candidate.get("relation") or candidate.get("relation_family"),"conflict_candidate_ids":[],"abstract_observation_ids":[]})
            selected[key]["conflict_candidate_ids"].append(candidate.get("candidate_id"))
            selected[key]["abstract_observation_ids"] += candidate.get("observation_ids",[])
    hypotheses=_read_jsonl(root/"hypotheses.jsonl")
    if hypotheses: sources.append("hypotheses.jsonl")
    for h in hypotheses:
        if not h.get("is_graph_conflict_hypothesis", h.get("source_mode") in {"graph_conflict","fulltext_grounded"}): continue
        for paper in h.get("papers",[]):
            key=str(paper.get("paper_id") or paper.get("pmid") or "") if isinstance(paper,dict) else str(paper)
            if key and key not in selected: selected[key]={"paper_id":key,"pmid":paper.get("pmid") if isinstance(paper,dict) else None,"pmcid":paper.get("pmcid") if isinstance(paper,dict) else None,"doi":None,"title":None,"selection_reason":"graph_conflict_hypothesis","conflict_relation":h.get("relation"),"conflict_candidate_ids":h.get("conflict_candidate_ids",[]),"abstract_observation_ids":h.get("observation_ids",[])}
    papers=list(selected.values())[:max(0,max_papers)]
    return {"selection_policy":"conflict_related_only","include_near_conflicts":include_near_conflicts,"source_artifacts":sources,"candidate_paper_count":len(papers),"candidate_papers":papers,"status":"completed" if papers else "completed_no_candidates","message":None if papers else "No conflict-related papers selected for full-text retrieval."}
