"""Generic post-cutoff literature-presence validator using NCBI E-utilities."""
from __future__ import annotations
import hashlib, os, urllib.parse
from pathlib import Path
from .production_v1_common import Transport, call, write_artifacts

LIMITATION="Retrieval presence is not support/refutation without semantic interpretation."

def build_queries(inputs: dict, maximum: int = 8) -> list[dict]:
    terms=[]
    for value in [*(inputs.get("search_terms") or []), *(inputs.get("hypotheses") or []), *(inputs.get("entities") or [])]:
        value=" ".join(str(value).split())
        if value and value.casefold() not in {x.casefold() for x in terms}: terms.append(value)
    start=(inputs.get("time_window") or {}).get("post_cutoff_from")
    rows=[]
    for term in terms[:maximum]:
        bounded=f'"{term.replace(chr(34), "")}"'
        query=f"{bounded} AND ({start}:3000[dp])" if start else bounded
        rows.append({"query_id":hashlib.sha256(query.encode()).hexdigest()[:16],"query":query})
    return rows

class PubMedPostCutoffValidator:
    validator_id="pubmed_post_cutoff"
    def run(self, inputs:dict, artifact_root:str|Path, *, network_enabled:bool=False, transport:Transport|None=None, retmax:int=20)->dict:
        queries=build_queries(inputs); start=(inputs.get("time_window") or {}).get("post_cutoff_from")
        base={"validator_id":self.validator_id,"status":"skipped","production_validator_version":"v1","network_used":False,"post_cutoff_from_year":start,"query_count":len(queries),"total_hits_estimate":0,"retrieved_record_count":0,"interpretation":"skipped_no_search_terms" if not queries else "post_cutoff_interpretation_not_attempted","limitations":[LIMITATION]}
        if not queries: return write_artifacts(artifact_root,self.validator_id,base,[])
        if not network_enabled:
            base["interpretation"]="network_disabled"; return write_artifacts(artifact_root,self.validator_id,base,[])
        rows=[]; total=0; failed=0
        endpoint="https://eutils.ncbi.nlm.nih.gov/entrez/eutils"; common={"db":"pubmed","retmode":"json","tool":os.getenv("NCBI_TOOL","conflict_oriented_discovery_engine"),"email":os.getenv("NCBI_EMAIL","")}
        if os.getenv("NCBI_API_KEY"): common["api_key"]=os.environ["NCBI_API_KEY"]
        for query in queries:
            try:
                search=call(transport,"GET",endpoint+"/esearch.fcgi?"+urllib.parse.urlencode({**common,"term":query["query"],"retmax":retmax}),None,{"Accept":"application/json"})["esearchresult"]
                ids=list(search.get("idlist") or []); total+=int(search.get("count") or 0)
                summaries={}
                if ids:
                    payload=call(transport,"GET",endpoint+"/esummary.fcgi?"+urllib.parse.urlencode({**common,"id":",".join(ids)}),None,{"Accept":"application/json"})
                    summaries=payload.get("result",{})
                for pmid in ids:
                    item=summaries.get(str(pmid),{}); article_ids={x.get("idtype"):x.get("value") for x in item.get("articleids",[]) if isinstance(x,dict)}
                    year=next((int(x[:4]) for x in [str(item.get("pubdate") or "")] if x[:4].isdigit()),None)
                    rows.append({**query,"pmid":str(pmid),"title":item.get("title"),"year":year,"journal":item.get("fulljournalname") or item.get("source"),"doi":article_ids.get("doi"),"abstract_available":False,"matched_terms":[],"source":"ncbi_eutilities"})
            except Exception: failed+=1
        base.update(status="completed" if not failed else ("partially_completed" if rows else "failed"),network_used=True,total_hits_estimate=total,retrieved_record_count=len(rows),interpretation="post_cutoff_literature_found" if rows else ("post_cutoff_literature_absent" if not failed else "post_cutoff_interpretation_not_attempted"))
        return write_artifacts(artifact_root,self.validator_id,base,rows)
