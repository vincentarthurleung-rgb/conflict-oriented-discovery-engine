"""Cached read-only API over display KG v2 and manual-review artifacts."""
from __future__ import annotations
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote
from .annotation_store import AnnotationStore

BOUNDARY = "C.O.D.E. Atlas supports evidence navigation and triage. Outputs require human review and are not biological validation."
REQUIRED = ("display_entities_v2.jsonl", "display_triples_v2.jsonl", "display_chains_v2.jsonl", "case_focused_triples.jsonl", "case_focused_chains.jsonl", "triple_evidence_links.jsonl")

def _json(path):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return {}

def _jsonl(path):
    if not path.is_file(): return []
    rows=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        try: value=json.loads(line)
        except json.JSONDecodeError: continue
        if isinstance(value,dict): rows.append(value)
    return rows

def _bool(params,key): return str((params.get(key) or [""])[0]).lower() in {"1","true","yes"}
def _one(params,key,default=""): return (params.get(key) or [default])[0]
def _page(rows,params):
    try: limit=max(1,min(500,int(_one(params,"limit","100")))); offset=max(0,int(_one(params,"offset","0")))
    except ValueError: raise ValueError("limit and offset must be integers")
    return {"items":rows[offset:offset+limit],"total":len(rows),"limit":limit,"offset":offset}

class ExplorerAPI:
    def __init__(self, display_kg_root, review_root=None):
        self.root=Path(display_kg_root); self.review_root=Path(review_root) if review_root else None
        missing=[x for x in REQUIRED if not (self.root/x).is_file()]
        if missing: raise FileNotFoundError("Missing display KG v2 files: "+", ".join(missing)+". Run system_b_build_clean_kg first.")
        self.entities=_jsonl(self.root/"display_entities_v2.jsonl"); self.triples=_jsonl(self.root/"display_triples_v2.jsonl"); self.chains=_jsonl(self.root/"display_chains_v2.jsonl")
        self.case_triples=_jsonl(self.root/"case_focused_triples.jsonl"); self.case_chains=_jsonl(self.root/"case_focused_chains.jsonl"); self.evidence=_jsonl(self.root/"triple_evidence_links.jsonl")
        self.contexts=_jsonl(self.root/"triple_contexts.jsonl"); self.validators=_jsonl(self.root/"validator_annotations.jsonl"); self.conflicts=_jsonl(self.root/"conflict_lens_records.jsonl")
        self.entity_by_id={x["entity_id"]:x for x in self.entities}; self.triple_by_id={x["triple_id"]:x for x in self.triples}; self.chain_by_id={x["chain_id"]:x for x in self.chains}
        self.evidence_by_triple=defaultdict(list); self.context_by_triple=defaultdict(list); self.conflict_by_triple=defaultdict(list)
        for x in self.evidence:self.evidence_by_triple[x["triple_id"]].append(x)
        for x in self.contexts:self.context_by_triple[x["triple_id"]].append(x)
        for x in self.conflicts:
            for tid in x.get("linked_triple_ids",[]):self.conflict_by_triple[tid].append(x)
        self.review=_jsonl(self.review_root/"manual_review_queue.jsonl") if self.review_root else []
        self.review_by_id={x["review_item_id"]:x for x in self.review};self.annotations=AnnotationStore(self.review_root,self.review)
        self.paper_metrics=_json(self.review_root/"paper_metrics_starter.json") if self.review_root else {}
        self.annotation_status=self._annotation_status()
        self.cases=sorted({case for x in self.case_triples for case in [x["case_id"]]}|{case for x in self.triples for case in x.get("case_ids",[])})

    def _annotation_status(self):
        path=self.review_root/"manual_review_annotations_template.csv" if self.review_root else None
        if not path or not path.is_file(): return {"available":False,"reviewed":0,"total":len(self.review),"manual_metrics_available":False}
        with path.open(encoding="utf-8",newline="") as handle: rows=list(csv.DictReader(handle))
        reviewed=sum(bool((x.get("final_label") or "").strip()) for x in rows)
        return {"available":True,"reviewed":reviewed,"total":len(rows),"manual_metrics_available":reviewed>0}

    def summary(self):
        fulltext=sum(x.get("fulltext_evidence_count",0) for x in self.triples)
        warnings=[]
        if not self.review_root or not self.review_root.exists(): warnings.append("Review root unavailable; review panels are optional and empty.")
        return {"cases":len(self.cases),"display_entities":len(self.entities),"display_triples":len(self.triples),"display_chains":len(self.chains),"fulltext_evidence_count":fulltext,"conflict_lens_records":len(self.conflicts),"review_queue_count":len(self.review),"warnings":warnings,"scientific_boundary":BOUNDARY}

    def dispatch(self,path,params=None,method="GET",body=None):
        params=params or {}
        if path=="/api/summary":return 200,self.summary()
        if path=="/api/cases":return 200,{"items":[self._case_summary(x) for x in self.cases],"total":len(self.cases)}
        if path.startswith("/api/case/"):
            case=unquote(path.removeprefix("/api/case/")); return (200,self._case(case)) if case in self.cases else (404,{"error":"case_not_found"})
        if path=="/api/entities":return 200,_page(self._entities(params),params)
        if path.startswith("/api/entity/"):
            value=self._entity(unquote(path.removeprefix("/api/entity/"))); return (200,value) if value else (404,{"error":"entity_not_found"})
        if path=="/api/triples":return 200,_page(self._triples(params),params)
        if path.startswith("/api/triple/"):
            value=self._triple(unquote(path.removeprefix("/api/triple/")),params); return (200,value) if value else (404,{"error":"triple_not_found"})
        if path=="/api/chains":return 200,_page(self._chains(params),params)
        if path.startswith("/api/chain/"):
            value=self.chain_by_id.get(unquote(path.removeprefix("/api/chain/"))); return (200,value) if value else (404,{"error":"chain_not_found"})
        if path=="/api/conflicts":return 200,_page(self._conflicts(params),params)
        if path=="/api/review-summary":return 200,{"queue_count":len(self.review),"items_by_type":dict(Counter(x.get("item_type","unknown") for x in self.review)),"items_by_case":dict(Counter(x.get("case_id","unknown") for x in self.review)),"annotation_status":self.annotation_status,"paper_metrics":self.paper_metrics,"manual_metrics_notice":"Manual precision metrics require completed non-empty annotations."}
        if path=="/api/review-items":return 200,_page(self._review_items(params),params)
        if path.startswith("/api/review-item/"):
            item_id=unquote(path.removeprefix("/api/review-item/"));item=self.review_by_id.get(item_id)
            return (200,{**item,"annotation":self.annotations.get(item_id)}) if item else (404,{"error":"review_item_not_found"})
        if path=="/api/annotations":return 200,{"items":list(self.annotations.records.values()),"total":len(self.annotations.records)}
        if path.startswith("/api/annotation/"):
            item_id=unquote(path.removeprefix("/api/annotation/"))
            if method=="POST":
                try:return 200,self.annotations.save(item_id,body or {})
                except KeyError:return 404,{"error":"review_item_not_found"}
                except RuntimeError as error:return 503,{"error":str(error)}
            value=self.annotations.get(item_id);return (200,value) if value else (404,{"error":"annotation_not_found"})
        if path=="/api/review-metrics":return 200,self.annotations.metrics()
        if path=="/api/review-metrics/recompute" and method=="POST":
            if not self.annotations.available:return 503,{"error":"Review root is unavailable; metrics cannot be persisted."}
            self.annotations.write_all();return 200,self.annotations.metrics()
        if path=="/api/review-export.csv":return 200,{"_raw":self.annotations.csv_text(),"_content_type":"text/csv; charset=utf-8","_filename":"manual_review_annotations_live.csv"}
        if path=="/api/review-export.jsonl":return 200,{"_raw":self.annotations.jsonl_text(),"_content_type":"application/x-ndjson; charset=utf-8","_filename":"manual_review_annotations_live.jsonl"}
        if path=="/api/search":return 200,self._search(_one(params,"q").casefold(),params)
        return 404,{"error":"not_found"}

    def _entities(self,p):
        rows=self.entities; q=_one(p,"q").casefold(); et=_one(p,"entity_type"); case=_one(p,"case_id")
        if q:rows=[x for x in rows if q in (x.get("display_label") or x.get("label","")).casefold() or any(q in a.casefold() for a in x.get("aliases",[]))]
        if et:rows=[x for x in rows if x.get("entity_type")==et]
        if case:rows=[x for x in rows if case in x.get("source_case_ids",[])]
        sort=_one(p,"sort","display_priority"); key={"degree":"degree","evidence_count":"evidence_count"}.get(sort,"display_priority_score")
        return sorted(rows,key=lambda x:(-(x.get(key) or 0),x.get("display_label","")))

    def _triples(self,p):
        rows=self.triples; case=_one(p,"case_id"); q=_one(p,"q").casefold(); status=_one(p,"conflict_status")
        if case:rows=[x for x in rows if case in x.get("case_ids",[])]
        if q:rows=[x for x in rows if q in f"{x.get('subject_display_label','')} {x.get('relation_normalized','')} {x.get('object_display_label','')}".casefold()]
        if _bool(p,"has_fulltext"):rows=[x for x in rows if x.get("fulltext_evidence_count",0)>0]
        if _bool(p,"has_results"):rows=[x for x in rows if x.get("results_section_evidence_count",0)>0]
        if status:rows=[x for x in rows if x.get("conflict_status")==status]
        return sorted(rows,key=lambda x:-x.get("display_priority_score_v2",0))

    def _chains(self,p):
        rows=self.chains; case=_one(p,"case_id"); q=_one(p,"q").casefold(); start=_one(p,"start_entity").casefold(); end=_one(p,"end_entity").casefold(); etype=_one(p,"entity_type")
        if case:rows=[x for x in rows if case in x.get("case_ids",[])]
        if q:rows=[x for x in rows if q in " ".join(x.get("entity_path",[])).casefold()]
        if start:rows=[x for x in rows if x.get("entity_path") and start in x["entity_path"][0].casefold()]
        if end:rows=[x for x in rows if x.get("entity_path") and end in x["entity_path"][-1].casefold()]
        if etype:
            typed={x.get("display_label") for x in self.entities if x.get("entity_type")==etype};rows=[x for x in rows if any(label in typed for label in x.get("entity_path",[]))]
        if _bool(p,"has_fulltext"):rows=[x for x in rows if x.get("fulltext_evidence_count_sum",0)>0]
        if _bool(p,"has_results"):rows=[x for x in rows if x.get("results_section_evidence_count_sum",0)>0]
        if _bool(p,"has_conflict"):rows=[x for x in rows if x.get("conflict_statuses")]
        return sorted(rows,key=lambda x:-x.get("chain_quality_score",0))

    def _conflicts(self,p):
        rows=self.conflicts; case=_one(p,"case_id"); kind=_one(p,"record_type")
        if case:rows=[x for x in rows if x.get("case_id")==case]
        if kind:rows=[x for x in rows if x.get("record_type")==kind]
        return rows

    def _review_items(self,p):
        rows=[];case=_one(p,"case_id");kind=_one(p,"item_type");status=_one(p,"review_status");label=_one(p,"final_label").upper();q=_one(p,"q").casefold()
        for item in self.review:
            annotation=self.annotations.get(item["review_item_id"]);row={**item,"annotation":annotation,"review_status":"reviewed" if annotation else "unreviewed"}
            if case and item.get("case_id")!=case:continue
            if kind and item.get("item_type")!=kind:continue
            if status and status!="all" and row["review_status"]!=status:continue
            if label and (annotation or {}).get("final_label")!=label:continue
            if q and q not in " ".join(str(item.get(x,"")) for x in ("claim_text","evidence_sentence","subject","relation","object","pmid","paper_title")).casefold():continue
            rows.append(row)
        return rows

    def _case_summary(self,case):
        triples=[x for x in self.case_triples if x["case_id"]==case]; chains=[x for x in self.case_chains if x["case_id"]==case]
        return {"case_id":case,"display_triples_count":len(triples),"display_chains_count":len(chains),"fulltext_evidence_count":sum(x.get("case_fulltext_evidence_count",0) for x in triples),"non_comparable_records":sum(x.get("case_id")==case and x.get("record_type")=="non_comparable_direction_pair" for x in self.conflicts),"weak_candidates":sum(x.get("case_id")==case and x.get("record_type")=="weak_candidate" for x in self.conflicts),"review_queue_items":sum(x.get("case_id")==case for x in self.review)}

    def _case(self,case):
        triples=sorted((x for x in self.case_triples if x["case_id"]==case),key=lambda x:x.get("case_display_rank",999)); chains=sorted((x for x in self.case_chains if x["case_id"]==case),key=lambda x:x.get("case_display_rank",999))
        entity_ids={tid for x in triples[:50] for tid in (self.triple_by_id.get(x["triple_id"],{}).get("subject_id"),self.triple_by_id.get(x["triple_id"],{}).get("object_id")) if tid}
        return {**self._case_summary(case),"triples":triples[:150],"chains":chains[:300],"top_entities":sorted((self.entity_by_id[x] for x in entity_ids if x in self.entity_by_id),key=lambda x:-x.get("display_priority_score",0))[:20],"conflicts":[x for x in self.conflicts if x.get("case_id")==case],"review_progress":self.annotation_status}

    def _entity(self,eid):
        entity=self.entity_by_id.get(eid)
        if not entity:return None
        incoming=[x for x in self.triples if x.get("object_id")==eid]; outgoing=[x for x in self.triples if x.get("subject_id")==eid]; label=entity.get("display_label","")
        return {**entity,"incoming_triples":incoming,"outgoing_triples":outgoing,"chains":[x for x in self.chains if label in x.get("entity_path",[])][:100],"conflicts":[x for x in self.conflicts if label.casefold() in f"{x.get('subject','')} {x.get('object','')} {x.get('observation_a_preview','')} {x.get('observation_b_preview','')}".casefold()]}

    def _triple(self,tid,p):
        triple=self.triple_by_id.get(tid)
        if not triple:return None
        evidence=self.evidence_by_triple[tid]
        scope=_one(p,"scope")
        if scope=="fulltext":evidence=[x for x in evidence if "full" in str(x.get("source_scope",""))]
        elif scope=="abstract":evidence=[x for x in evidence if x.get("source_scope")=="abstract"]
        elif scope=="results":evidence=[x for x in evidence if "result" in str(x.get("section_title","")).casefold()]
        try: limit=max(1,min(200,int(_one(p,"evidence_limit","50"))))
        except ValueError:raise ValueError("evidence_limit must be an integer")
        cases=set(triple.get("case_ids",[]))
        enriched=[]
        for link in evidence[:limit]:
            item_id=f"{link.get('case_id')}::{link.get('item_type')}::{link.get('source_file')}::{link.get('source_line')}";item=self.review_by_id.get(item_id)
            enriched.append({**link,"review_item_id":item_id if item else None,"review_status":"reviewed" if item and self.annotations.get(item_id) else "unreviewed" if item else "not_in_review_queue","annotation":self.annotations.get(item_id) if item else None})
        return {**triple,"evidence_links":enriched,"evidence_total":len(evidence),"contexts":self.context_by_triple[tid],"validator_annotations":[x for x in self.validators if x.get("case_id") in cases],"conflict_lens_records":self.conflict_by_triple[tid],"manual_review_status":{"status":"evidence_level","note":"Manual labels assess extraction and triage quality, not biological validation."}}

    def _search(self,q,p):
        if not q:return {"entities":[],"triples":[],"chains":[]}
        return {"entities":self._entities({"q":[q]})[:20],"triples":self._triples({"q":[q]})[:20],"chains":self._chains({"q":[q]})[:20]}
