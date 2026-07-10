"""Deterministic Display KG projections for the Atlas global graph workspace."""
from __future__ import annotations
from collections import Counter,defaultdict,deque

GENERIC_TYPES={"unknown","unknown_biomedical_entity","biomedical_entity"}

def _one(params,key,default=""):return (params.get(key) or [default])[0]
def _bool(params,key):return str(_one(params,key)).lower() in {"1","true","yes"}
def _int(params,key,default,lo,hi):
    try:return max(lo,min(hi,int(_one(params,key,str(default)))))
    except ValueError:return default

def _relation_label(rel):
    r=str(rel or "").lower().replace("-","_")
    if r in {"activates"}:return "激活"
    if r in {"promotes"}:return "促进"
    if r in {"increases"}:return "增加"
    if r in {"upregulates"}:return "上调"
    if r in {"inhibits","suppresses"}:return "抑制"
    if r in {"decreases"}:return "降低"
    if r in {"downregulates"}:return "下调"
    if r in {"regulates","modulates"}:return "调节"
    if r in {"associated_with","correlates_with"}:return "相关"
    return "影响"

class GraphProjection:
    def __init__(self,api):
        self.api=api
        self.entity_by_label={x.get("display_label") or x.get("label"):x for x in api.entities}
        self.outgoing=defaultdict(list);self.incoming=defaultdict(list)
        for t in api.triples:
            self.outgoing[t.get("subject_id")].append(t);self.incoming[t.get("object_id")].append(t)

    def filters(self):
        return {
            "cases":self.api.cases,
            "entity_types":sorted({x.get("entity_type","unknown") for x in self.api.entities}),
            "evidence_scope":["any","fulltext","abstract"],
            "conflict_status":sorted({x.get("conflict_status","none") for x in self.api.triples}),
            "fulltext_support":[False,True],
        }

    def overview(self,params):
        limit_nodes=_int(params,"limit_nodes",150,1,300);limit_edges=_int(params,"limit_edges",240,1,500)
        triples=self._filtered_triples(params)
        scores=Counter()
        for t in triples:
            for eid in (t.get("subject_id"),t.get("object_id")):
                ent=self.api.entity_by_id.get(eid)
                if not ent:continue
                scores[eid]+=self._entity_score(ent,t)
        selected={eid for eid,_ in scores.most_common(limit_nodes)}
        edges=[self.edge(t) for t in triples if t.get("subject_id") in selected and t.get("object_id") in selected]
        edges=sorted(edges,key=lambda e:-e.get("weight",0))[:limit_edges]
        node_ids={e["source"] for e in edges}|{e["target"] for e in edges}
        if not node_ids:node_ids=selected
        nodes=[self.node(self.api.entity_by_id[eid],scores[eid]) for eid in node_ids if eid in self.api.entity_by_id]
        clusters=[{"cluster_id":case,"label":case,"node_ids":[n["id"] for n in nodes if case in n.get("case_ids",[])],"ui_only":True} for case in self.api.cases]
        return {"nodes":nodes,"edges":edges,"clusters":clusters,"summary":{"visible_nodes":len(nodes),"visible_edges":len(edges),"total_nodes":len(self.api.entities),"total_edges":len(self.api.triples)},"filters":{k:_one(params,k) for k in ("case_id","entity_type","has_fulltext","has_conflict")}}

    def neighborhood(self,entity_id,params):
        depth=_int(params,"depth",1,1,2);limit=_int(params,"limit",100,1,200);direction=_one(params,"direction","both");case=_one(params,"case_id")
        seen_nodes={entity_id};seen_edges=[];q=deque([(entity_id,0)])
        while q and len(seen_nodes)<limit:
            eid,d=q.popleft()
            if d>=depth:continue
            triples=[]
            if direction in {"both","downstream"}:triples+=self.outgoing.get(eid,[])
            if direction in {"both","upstream"}:triples+=self.incoming.get(eid,[])
            if case:triples=[t for t in triples if case in t.get("case_ids",[])]
            for t in sorted(triples,key=lambda x:-x.get("display_priority_score_v2",0)):
                other=t.get("object_id") if t.get("subject_id")==eid else t.get("subject_id")
                if other not in self.api.entity_by_id:continue
                seen_edges.append(t);seen_nodes.add(other)
                if len(seen_nodes)>=limit:break
                q.append((other,d+1))
        edges=[self.edge(t) for t in seen_edges if t.get("subject_id") in seen_nodes and t.get("object_id") in seen_nodes][:limit*2]
        nodes=[self.node(self.api.entity_by_id[eid],0) for eid in seen_nodes if eid in self.api.entity_by_id]
        return {"center":entity_id,"nodes":nodes,"edges":edges,"summary":{"visible_nodes":len(nodes),"visible_edges":len(edges),"depth":depth,"limit":limit}}

    def path(self,params):
        source=_one(params,"source").casefold();target=_one(params,"target").casefold();case=_one(params,"case_id");max_depth=_int(params,"max_depth",4,1,6)
        chains=self.api.chains
        if case:chains=[x for x in chains if case in x.get("case_ids",[])]
        rows=[]
        for c in chains:
            labels=[str(x).casefold() for x in c.get("entity_path",[])]
            if len(labels)-1>max_depth:continue
            if source and source not in labels[0]:continue
            if target and target not in labels[-1]:continue
            rows.append(c)
        rows=sorted(rows,key=lambda x:-x.get("chain_quality_score",0))[:20]
        return {"items":[self._chain_projection(c) for c in rows],"total":len(rows),"source":source,"target":target}

    def _filtered_triples(self,params):
        rows=self.api.triples;case=_one(params,"case_id");etype=_one(params,"entity_type");conflict=_one(params,"conflict_status")
        if case:rows=[x for x in rows if case in x.get("case_ids",[])]
        if etype:rows=[x for x in rows if self.api.entity_by_id.get(x.get("subject_id"),{}).get("entity_type")==etype or self.api.entity_by_id.get(x.get("object_id"),{}).get("entity_type")==etype]
        if _bool(params,"has_fulltext"):rows=[x for x in rows if x.get("fulltext_evidence_count",0)>0]
        if _bool(params,"has_conflict"):rows=[x for x in rows if x.get("conflict_status") and x.get("conflict_status")!="none"]
        if conflict:rows=[x for x in rows if x.get("conflict_status")==conflict]
        return sorted(rows,key=lambda x:-x.get("display_priority_score_v2",0))

    def _entity_score(self,ent,triple):
        score=float(ent.get("display_priority_score") or 0)*2+float(triple.get("display_priority_score_v2") or 0)*3
        score+=min(10,float(ent.get("evidence_count") or 0))/5+len(ent.get("source_case_ids",[]))
        if ent.get("entity_type") in GENERIC_TYPES:score*=.25
        if ent.get("genericity_penalty") or ent.get("generic_subject_penalty") or ent.get("generic_object_penalty"):score*=.5
        return score

    def node(self,ent,score):
        return {"id":ent.get("entity_id"),"label":ent.get("display_label") or ent.get("label"),"entity_type":ent.get("entity_type","unknown"),"degree":ent.get("degree",0),"evidence_count":ent.get("evidence_count",0),"case_ids":ent.get("source_case_ids",[]),"score":round(score,4),"node_kind":"display_entity"}

    def edge(self,t):
        return {"id":t.get("triple_id"),"source":t.get("subject_id"),"target":t.get("object_id"),"source_label":t.get("subject_display_label"),"target_label":t.get("object_display_label"),"relation":t.get("relation_normalized"),"relation_label":_relation_label(t.get("relation_normalized")),"evidence_count":t.get("evidence_count",0),"fulltext_evidence_count":t.get("fulltext_evidence_count",0),"case_ids":t.get("case_ids",[]),"conflict_status":t.get("conflict_status","none"),"review_status":"unknown","weight":float(t.get("display_priority_score_v2") or 0)}

    def _chain_projection(self,c):
        return {"chain_id":c.get("chain_id"),"entity_path":c.get("entity_path",[]),"relation_path":c.get("relation_path",[]),"triple_ids":c.get("triple_ids",[]),"case_ids":c.get("case_ids",[]),"depth":c.get("depth"),"fulltext_evidence_count_sum":c.get("fulltext_evidence_count_sum",0)}
