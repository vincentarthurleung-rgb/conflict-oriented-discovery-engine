"""Generic Reactome pathway-membership validator."""
from __future__ import annotations
import urllib.parse
from pathlib import Path
from .production_v1_common import Transport, call, write_artifacts
LIMITATION="Reactome pathway membership does not establish causal direction or conflict truth."

class ReactomeValidatorV1:
    validator_id="reactome"
    def run(self,inputs:dict,artifact_root:str|Path,*,network_enabled:bool=False,transport:Transport|None=None)->dict:
        terms=list(dict.fromkeys([*(inputs.get("pathways") or []),*(inputs.get("genes") or []),*(inputs.get("entities") or [])]))
        base={"validator_id":self.validator_id,"status":"skipped","production_validator_version":"v1","network_used":False,"entity_count":len(terms),"mapped_entity_count":0,"pathway_hit_count":0,"interpretation":"skipped_no_pathway_terms" if not terms else "pathway_membership_not_found","limitations":[LIMITATION]}
        if not terms or not network_enabled:
            if terms: base["interpretation"]="network_disabled"
            return write_artifacts(artifact_root,self.validator_id,base,[])
        rows=[]; failed=0
        for term in terms:
            try:
                payload=call(transport,"GET","https://reactome.org/ContentService/search/query?"+urllib.parse.urlencode({"query":term,"species":"Homo sapiens","types":"Pathway"}),None,{"Accept":"application/json"})
                hits=payload.get("results",payload if isinstance(payload,list) else [])
                if isinstance(hits,dict): hits=hits.get("entries",[])
                for hit in hits or []:
                    rid=hit.get("stId") or hit.get("dbId") or hit.get("id")
                    rows.append({"entity":term,"query":term,"reactome_id":str(rid) if rid else None,"pathway_name":hit.get("name") or hit.get("displayName"),"species":hit.get("speciesName") or hit.get("species") or "Homo sapiens","url":f"https://reactome.org/content/detail/{rid}" if rid else None,"mapping_status":"mapped"})
                if not hits: rows.append({"entity":term,"query":term,"reactome_id":None,"pathway_name":None,"species":"Homo sapiens","url":None,"mapping_status":"not_mapped"})
            except Exception: failed+=1
        mapped={x["entity"] for x in rows if x["mapping_status"]=="mapped"}
        base.update(status="completed" if not failed else ("partially_completed" if rows else "failed"),network_used=True,mapped_entity_count=len(mapped),pathway_hit_count=sum(x["mapping_status"]=="mapped" for x in rows),interpretation="pathway_membership_found" if mapped else ("pathway_membership_not_found" if not failed else "pathway_mapping_ambiguous"))
        return write_artifacts(artifact_root,self.validator_id,base,rows)
