"""Deterministic Mechanism Evidence Dossier projection for Atlas."""
from __future__ import annotations
import hashlib
import json
from collections import Counter

MISSING="未报告"

def _one(params,key,default=""):return (params.get(key) or [default])[0]
def _bool(params,key):return str(_one(params,key)).lower() in {"1","true","yes"}
def _int(params,key,default,lo,hi):
    try:return max(lo,min(hi,int(_one(params,key,str(default)))))
    except ValueError:return default

RELATION_LABELS={
    "activates":"激活","promotes":"促进","increases":"增加","upregulates":"上调",
    "inhibits":"抑制","suppresses":"抑制","decreases":"降低","downregulates":"下调",
    "regulates":"调节","modulates":"调节","affects":"影响",
    "associated_with":"相关","correlates_with":"相关",
}
CONTEXT_FIELDS=("species","cell_type","tissue","disease_or_cancer_type","treatment","dose","time","genotype","localization")

def _norm(value):
    return str(value or "").strip().casefold()

def _semantic_payload(triple):
    payload={
        "subject_id":str(triple.get("subject_id","")),
        "relation_normalized":_norm(triple.get("relation_normalized")),
        "object_id":str(triple.get("object_id","")),
    }
    for key in ("direction","relation_direction","negated","negation","is_negated"):
        value=triple.get(key)
        if value not in (None,"",[]):
            payload[key]=value
    return payload

def legacy_dossier_id_for(triple):
    raw="|".join(str(triple.get(k,"")) for k in ("subject_id","relation_normalized","object_id"))
    return "dos_"+hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

def dossier_id_for(triple):
    raw=json.dumps(_semantic_payload(triple),sort_keys=True,separators=(",",":"),ensure_ascii=True)
    return "dos_"+hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]

def relation_label(rel):return RELATION_LABELS.get(str(rel or "").lower().replace("-","_"),"影响")

def _label(ent):return ent.get("display_label") or ent.get("label") or ent.get("entity_id") or ""

class DossierProjection:
    def __init__(self,api):
        self.api=api
        self.triples=api.dossier_triples or api.triples
        self.by_id={}
        self.alias_to_dossier={}
        self.triple_to_dossier={}
        for triple in self.triples:
            did=dossier_id_for(triple)
            self.by_id[did]=triple
            legacy=legacy_dossier_id_for(triple)
            if legacy!=did:self.alias_to_dossier[legacy]=did
            self.triple_to_dossier[triple.get("triple_id")]=did

    def resolve(self,value):
        return value if value in self.by_id else self.alias_to_dossier.get(value) or self.triple_to_dossier.get(value)

    def list(self,params):
        rows=[self._summary_for(t) for t in self.triples]
        q=_one(params,"q").casefold();case=_one(params,"case_id");etype=_one(params,"entity_type");status=_one(params,"review_status")
        if q:
            rows=[x for x in rows if q in " ".join(str(x.get(k,"")) for k in ("humanized_statement","dossier_id","backing_triple_id")).casefold()]
        if case:rows=[x for x in rows if case in x.get("related_cases",[])]
        if etype:rows=[x for x in rows if x.get("subject",{}).get("entity_type")==etype or x.get("object",{}).get("entity_type")==etype]
        if _bool(params,"has_fulltext"):rows=[x for x in rows if x.get("evidence_summary",{}).get("fulltext_count",0)>0]
        if _bool(params,"has_conflict"):rows=[x for x in rows if x.get("conflict_summary",{}).get("status")!="evidence_consistent"]
        if status:rows=[x for x in rows if x.get("review_summary",{}).get("status")==status]
        sort=_one(params,"sort","priority")
        if sort=="evidence":rows=sorted(rows,key=lambda x:-x["evidence_summary"]["total"])
        elif sort=="fulltext":rows=sorted(rows,key=lambda x:-x["evidence_summary"]["fulltext_count"])
        else:rows=sorted(rows,key=lambda x:-x.get("priority_score",0))
        limit=_int(params,"limit",50,1,200);offset=_int(params,"offset",0,0,100000)
        return {"items":rows[offset:offset+limit],"total":len(rows),"limit":limit,"offset":offset,"filters":{k:_one(params,k) for k in ("q","case_id","entity_type","has_fulltext","has_conflict","review_status","sort")}}

    def detail(self,dossier_id):
        triple=self.by_id.get(self.resolve(dossier_id) or "")
        if not triple:return None
        did=dossier_id_for(triple)
        evidence=self.evidence(did)["groups"]
        context=self.context_matrix(did)
        conflicts=self._conflicts_for(triple)
        review=self.review_target(did)
        paths=self.paths(did,{"limit":["8"]})["items"]
        return {**self._summary_for(triple),"dossier_id":did,"summary":self._coverage_summary(triple,context,conflicts,review),"evidence_groups":evidence,"context_summary":context["summary"],"conflict_summary":self._conflict_summary(conflicts),"review_summary":self._review_summary(review),"related_paths":paths,"badges":self._badges(triple,conflicts,review)}

    def evidence(self,dossier_id):
        triple=self.by_id.get(self.resolve(dossier_id) or "")
        if not triple:return None
        groups={"supporting":[],"opposing_or_differing":[],"uncertain":[]}
        conflicts=self._conflicts_for(triple)
        conflict_text=" ".join(str(x) for x in conflicts).casefold()
        for e in self.api.evidence_by_triple.get(triple.get("triple_id"),[]):
            row=self._evidence_row(e,triple)
            bucket=row["evidence_class"]
            if bucket=="supporting" and conflict_text and any(str(e.get(k,"")).casefold() in conflict_text for k in ("evidence_sentence","pmid","pmcid") if e.get(k)):
                bucket="opposing_or_differing";row["evidence_class"]=bucket;row["classification_reason"]="linked_conflict_record_mentions_this_evidence"
            groups[bucket].append(row)
        return {"dossier_id":dossier_id_for(triple),"groups":groups,"total":sum(len(v) for v in groups.values())}

    def context_matrix(self,dossier_id):
        triple=self.by_id.get(self.resolve(dossier_id) or "")
        if not triple:return None
        rows=[];contexts=self.api.context_by_triple.get(triple.get("triple_id"),[])
        by_key={}
        for c in contexts:
            key=(c.get("pmid"),c.get("pmcid"),c.get("evidence_sentence") or c.get("context_text"))
            by_key[key]=c
        for e in self.api.evidence_by_triple.get(triple.get("triple_id"),[]):
            c=by_key.get((e.get("pmid"),e.get("pmcid"),e.get("evidence_sentence"))) or {}
            context=e.get("context") if isinstance(e.get("context"),dict) else {}
            merged={**c,**context}
            row={"paper_title":e.get("paper_title") or c.get("paper_title") or MISSING,"pmid":e.get("pmid") or c.get("pmid") or MISSING,"pmcid":e.get("pmcid") or c.get("pmcid") or MISSING,"case_id":e.get("case_id") or c.get("case_id") or MISSING,"direction":e.get("direction") or c.get("direction") or triple.get("direction") or MISSING,"source_scope":e.get("source_scope") or MISSING,"section_title":e.get("section_title") or c.get("section_title") or MISSING}
            for field in CONTEXT_FIELDS:row[field]=merged.get(field) or MISSING
            erow=self._evidence_row(e,triple)
            row["evidence_class"]=erow["evidence_class"]
            row["classification_reason"]=erow["classification_reason"]
            rows.append(row)
        differences={field:sorted({r[field] for r in rows}) for field in (*CONTEXT_FIELDS,"direction","source_scope","section_title","evidence_class") if len({r[field] for r in rows})>1}
        return {"dossier_id":dossier_id_for(triple),"columns":["paper_title","pmid","pmcid","case_id","source_scope","section_title",*CONTEXT_FIELDS,"direction","evidence_class","classification_reason"],"items":rows,"total":len(rows),"summary":{"missing_value_label":MISSING,"differing_fields":differences,"row_count":len(rows)}}

    def audit(self):
        by_semantic={}
        unresolved=[];mixed_direction=[];mixed_negation=[];mixed_raw_relation=[]
        for triple in self.triples:
            did=dossier_id_for(triple)
            by_semantic.setdefault(did,[]).append(triple)
            if triple.get("subject_id") not in self.api.entity_by_id or triple.get("object_id") not in self.api.entity_by_id:
                unresolved.append(did)
        for did,triples in by_semantic.items():
            directions={str(t.get("direction") or t.get("relation_direction") or "") for t in triples if t.get("direction") or t.get("relation_direction")}
            negations={str(t.get(k)) for t in triples for k in ("negated","negation","is_negated") if t.get(k) not in (None,"")}
            rawrels={str(t.get("relation") or t.get("relation_raw") or t.get("predicate") or "") for t in triples if t.get("relation") or t.get("relation_raw") or t.get("predicate")}
            if len(directions)>1:mixed_direction.append(did)
            if len(negations)>1:mixed_negation.append(did)
            if len(rawrels)>1:mixed_raw_relation.append(did)
        relation_pairs=Counter((str(t.get("subject_id")),str(t.get("object_id"))) for t in self.api.triples)
        issues=[]
        if mixed_direction:issues.append({"issue":"mixed_direction_within_dossier","count":len(mixed_direction),"examples":mixed_direction[:10]})
        if mixed_negation:issues.append({"issue":"mixed_negation_within_dossier","count":len(mixed_negation),"examples":mixed_negation[:10]})
        if unresolved:issues.append({"issue":"unresolved_entity_reference","count":len(set(unresolved)),"examples":sorted(set(unresolved))[:10]})
        return {
            "dossier_count":len(by_semantic),
            "triple_count":len(self.triples),
            "legacy_alias_count":len(self.alias_to_dossier),
            "multi_case_dossier_count":sum(1 for t in self.triples if len(t.get("case_ids",[]))>1),
            "multi_direction_dossier_count":len(mixed_direction),
            "mixed_negation_dossier_count":len(mixed_negation),
            "mixed_relation_raw_count":len(mixed_raw_relation),
            "unresolved_entity_dossier_count":len(set(unresolved)),
            "possible_overmerge_count":len(mixed_direction)+len(mixed_negation),
            "possible_fragmentation_count":sum(1 for _,n in relation_pairs.items() if n>1),
            "issues":issues,
        }

    def paths(self,dossier_id,params):
        triple=self.by_id.get(self.resolve(dossier_id) or "")
        if not triple:return None
        tid=triple.get("triple_id");labels={triple.get("subject_display_label"),triple.get("object_display_label")}
        rows=[]
        for chain in self.api.chains:
            if tid in chain.get("triple_ids",[]) or any(x in labels for x in chain.get("entity_path",[])):
                rows.append({"chain_id":chain.get("chain_id"),"entity_path":chain.get("entity_path",[]),"relation_path":chain.get("relation_path",[]),"triple_ids":chain.get("triple_ids",[]),"dossier_ids":[self.triple_to_dossier.get(x) for x in chain.get("triple_ids",[]) if self.triple_to_dossier.get(x)],"case_ids":chain.get("case_ids",[]),"fulltext_evidence_count_sum":chain.get("fulltext_evidence_count_sum",0)})
        rows=sorted(rows,key=lambda x:-x.get("fulltext_evidence_count_sum",0))
        limit=_int(params,"limit",20,1,100)
        return {"dossier_id":dossier_id_for(triple),"items":rows[:limit],"total":len(rows)}

    def review_target(self,dossier_id):
        triple=self.by_id.get(self.resolve(dossier_id) or "")
        if not triple:return None
        for item in self.api.review:
            if item.get("triple_id")==triple.get("triple_id") or item.get("backing_triple_id")==triple.get("triple_id"):
                return self._review_target_row(item,"triple_backing_id")
        subj=str(triple.get("subject_display_label","")).casefold();obj=str(triple.get("object_display_label","")).casefold();rel=str(triple.get("relation_normalized","")).casefold()
        for item in self.api.review:
            text=" ".join(str(item.get(k,"")) for k in ("subject","relation","object")).casefold()
            if subj in text and obj in text and rel in text:return self._review_target_row(item,"case_subject_relation_object")
        return {"reviewable":False,"reason":"no_matching_review_item","dossier_id":dossier_id_for(triple)}

    def _review_target_row(self,item,method):
        ann=self.api.annotations.get(item.get("review_item_id"))
        return {"reviewable":True,"match_method":method,"review_item_id":item.get("review_item_id"),"case_id":item.get("case_id"),"item_type":item.get("item_type"),"review_status":"reviewed" if ann else "unreviewed","annotation":ann}

    def _summary_for(self,triple):
        did=dossier_id_for(triple);subject=self.api.entity_by_id.get(triple.get("subject_id"),{});obj=self.api.entity_by_id.get(triple.get("object_id"),{})
        rel=triple.get("relation_normalized")
        return {"dossier_id":did,"public_id":did,"backing_triple_id":triple.get("triple_id"),"subject":{"entity_id":triple.get("subject_id"),"label":triple.get("subject_display_label") or _label(subject),"entity_type":subject.get("entity_type") or triple.get("subject_entity_type")},"relation":{"normalized":rel,"label":relation_label(rel)},"object":{"entity_id":triple.get("object_id"),"label":triple.get("object_display_label") or _label(obj),"entity_type":obj.get("entity_type") or triple.get("object_entity_type")},"humanized_statement":f"{triple.get('subject_display_label')} {relation_label(rel)} {triple.get('object_display_label')}","evidence_summary":{"total":triple.get("evidence_count",0),"fulltext_count":triple.get("fulltext_evidence_count",0),"abstract_count":max(0,triple.get("evidence_count",0)-triple.get("fulltext_evidence_count",0))},"related_cases":triple.get("case_ids",[]),"priority_score":triple.get("display_priority_score_v2",0)}

    def _coverage_summary(self,triple,context,conflicts,review):
        papers={(e.get("pmid"),e.get("pmcid")) for e in self.api.evidence_by_triple.get(triple.get("triple_id"),[]) if e.get("pmid") or e.get("pmcid")}
        return {"evidence_count":triple.get("evidence_count",0),"fulltext_coverage":triple.get("fulltext_evidence_count",0),"abstract_coverage":max(0,triple.get("evidence_count",0)-triple.get("fulltext_evidence_count",0)),"paper_count":len(papers),"case_count":len(triple.get("case_ids",[])),"context_completeness":self._context_completeness(context["items"]),"evidence_consistency":self._conflict_summary(conflicts)["label"],"review_status":self._review_summary(review)["status"]}

    def _context_completeness(self,rows):
        if not rows:return "no_context_rows"
        total=len(rows)*len(CONTEXT_FIELDS);filled=sum(1 for r in rows for f in CONTEXT_FIELDS if r.get(f) and r.get(f)!=MISSING)
        return {"filled":filled,"total":total,"fraction":round(filled/total,4) if total else 0}

    def _conflicts_for(self,triple):
        return self.api.conflict_by_triple.get(triple.get("triple_id"),[])

    def _conflict_summary(self,conflicts):
        if not conflicts:return {"status":"evidence_consistent","label":"证据一致","count":0}
        kinds=Counter(x.get("record_type","unknown") for x in conflicts)
        if kinds.get("non_comparable_direction_pair"):label="条件不同，不能直接比较";status="conditions_differ"
        elif kinds.get("weak_candidate"):label="可能存在真正分歧";status="possible_conflict"
        else:label="证据不足";status="insufficient_evidence"
        return {"status":status,"label":label,"count":len(conflicts),"types":dict(kinds)}

    def _review_summary(self,review):
        if not review or not review.get("reviewable"):return {"status":"not_in_review_queue","label":"暂无匹配审核任务"}
        return {"status":review.get("review_status","unreviewed"),"label":"已审核" if review.get("review_status")=="reviewed" else "待审核","review_item_id":review.get("review_item_id")}

    def _badges(self,triple,conflicts,review):
        badges=[]
        if triple.get("fulltext_evidence_count",0)>0:badges.append("全文证据")
        badges.append(self._conflict_summary(conflicts)["label"])
        badges.append(self._review_summary(review)["label"])
        return badges

    def _evidence_row(self,e,triple):
        sentence=e.get("evidence_sentence") or e.get("claim_text")
        direction=e.get("direction") or triple.get("direction")
        evidence_class="supporting";reason="linked_to_this_display_relation"
        if not sentence:
            evidence_class="uncertain";reason="missing_evidence_sentence"
        elif not direction and not e.get("source_scope"):
            evidence_class="uncertain";reason="missing_direction_and_source_scope"
        for conflict in self._conflicts_for(triple):
            if conflict.get("record_type")=="non_comparable_direction_pair":
                evidence_class="opposing_or_differing";reason="conditions_differ_non_comparable_direction_pair";break
        return {"direction":direction,"source_scope":e.get("source_scope"),"section":e.get("section_title"),"context":e.get("context") if isinstance(e.get("context"),dict) else {},"paper_title":e.get("paper_title"),"pmid":e.get("pmid"),"pmcid":e.get("pmcid"),"evidence_sentence":sentence,"evidence_class":evidence_class,"classification_reason":reason,"extracted":{"subject":triple.get("subject_display_label"),"relation":triple.get("relation_normalized"),"object":triple.get("object_display_label")},"case_id":e.get("case_id"),"source_file":e.get("source_file"),"source_line":e.get("source_line")}
