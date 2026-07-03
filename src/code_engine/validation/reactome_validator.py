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
        base={"validator_id":self.validator_id,"status":"skipped","production_validator_version":"v1","network_used":False,"api_reachable":False,"entity_count":len(terms),"mapped_entity_count":0,"pathway_hit_count":0,"mapping_status":"no_mapping" if not terms else "not_attempted","failure_type":None,"interpretation":"skipped_no_pathway_terms" if not terms else "pathway_membership_not_found","limitations":[LIMITATION]}
        if not terms or not network_enabled:
            if terms: base["interpretation"]="network_disabled"
            return write_artifacts(artifact_root,self.validator_id,base,[])
        rows=[]; failed=0; succeeded=0; failure_types=[]
        for term in terms:
            try:
                payload=call(transport,"GET","https://reactome.org/ContentService/search/query?"+urllib.parse.urlencode({"query":term,"species":"Homo sapiens","types":"Pathway"}),None,{"Accept":"application/json"})
                succeeded+=1; hits=payload.get("results",payload if isinstance(payload,list) else [])
                if isinstance(hits,dict): hits=hits.get("entries",[])
                for hit in hits or []:
                    rid=hit.get("stId") or hit.get("dbId") or hit.get("id")
                    rows.append({"entity":term,"query":term,"reactome_id":str(rid) if rid else None,"pathway_name":hit.get("name") or hit.get("displayName"),"species":hit.get("speciesName") or hit.get("species") or "Homo sapiens","url":f"https://reactome.org/content/detail/{rid}" if rid else None,"mapping_status":"mapped"})
                if not hits: rows.append({"entity":term,"query":term,"reactome_id":None,"pathway_name":None,"species":"Homo sapiens","url":None,"mapping_status":"not_mapped"})
            except Exception as error: failed+=1; failure_types.append(type(error).__name__)
        mapped={x["entity"] for x in rows if x["mapping_status"]=="mapped"}
        status="completed" if mapped and not failed else "completed_no_mapping" if succeeded and not mapped and not failed else "completed_with_warnings" if succeeded else "failed"
        mapping="mapped" if mapped else "ambiguous" if succeeded and failed else "no_mapping" if succeeded else "failed"
        base.update(status=status,network_used=True,api_reachable=bool(succeeded),mapped_entity_count=len(mapped),pathway_hit_count=sum(x["mapping_status"]=="mapped" for x in rows),mapping_status=mapping,failure_type=",".join(sorted(set(failure_types))) or None,interpretation="pathway_membership_found" if mapped else ("pathway_membership_not_found" if succeeded and not failed else "pathway_mapping_ambiguous"))
        return write_artifacts(artifact_root,self.validator_id,base,rows)
