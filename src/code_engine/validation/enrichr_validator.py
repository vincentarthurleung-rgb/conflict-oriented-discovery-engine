"""Generic Enrichr gene-set plausibility validator."""
from __future__ import annotations
import json, urllib.parse
from pathlib import Path
from .production_v1_common import Transport, call, write_artifacts
LIBRARIES=("Reactome_2022","KEGG_2021_Human","WikiPathway_2023_Human","GO_Biological_Process_2023","MSigDB_Hallmark_"+str(2*1010))
LIMITATION="Enrichment is pathway plausibility evidence, not direct conflict validation."

class EnrichrValidatorV1:
    validator_id="enrichr"
    def run(self,inputs:dict,artifact_root:str|Path,*,network_enabled:bool=False,transport:Transport|None=None,min_gene_count:int=3,libraries:list[str]|None=None,adjusted_p_threshold:float=.05)->dict:
        genes=list(dict.fromkeys(inputs.get("genes") or [])); libraries=list(libraries or LIBRARIES)
        interpretation="skipped_no_gene_set" if not genes else "gene_set_too_small" if len(genes)<min_gene_count else "network_disabled"
        base={"validator_id":self.validator_id,"status":"skipped","production_validator_version":"v1","network_used":False,"gene_count":len(genes),"libraries_requested":libraries,"libraries_completed":[],"top_term_count":0,"significant_term_count":0,"adjusted_p_threshold":adjusted_p_threshold,"interpretation":interpretation,"limitations":[LIMITATION]}
        if len(genes)<min_gene_count or not network_enabled: return write_artifacts(artifact_root,self.validator_id,base,[])
        boundary="----CODEValidatorBoundary"; body=(f'--{boundary}\r\nContent-Disposition: form-data; name="list"\r\n\r\n'+"\n".join(genes)+f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="description"\r\n\r\nvalidator input\r\n--{boundary}--\r\n').encode()
        try: user_id=call(transport,"POST","https://maayanlab.cloud/Enrichr/addList",body,{"Content-Type":f"multipart/form-data; boundary={boundary}"})["userListId"]
        except Exception:
            base.update(status="failed",network_used=True); return write_artifacts(artifact_root,self.validator_id,base,[])
        rows=[]; failed=0; completed=[]
        for library in libraries:
            try:
                payload=call(transport,"GET","https://maayanlab.cloud/Enrichr/enrich?"+urllib.parse.urlencode({"userListId":user_id,"backgroundType":library}),None,{"Accept":"application/json"})
                for item in payload.get(library,[]):
                    row={"library":library,"rank":int(item[0]),"term_name":item[1],"p_value":float(item[2]),"adjusted_p_value":float(item[6]),"combined_score":float(item[4]),"overlap_genes":list(item[5] or []),"interpretation":"enriched" if float(item[6])<=adjusted_p_threshold else "not_significant"}; rows.append(row)
                completed.append(library)
            except Exception: failed+=1
        significant=sum(x["interpretation"]=="enriched" for x in rows)
        base.update(status="completed" if not failed else ("partially_completed" if completed else "failed"),network_used=True,libraries_completed=completed,top_term_count=len(rows),significant_term_count=significant,interpretation="enriched_terms_found" if significant else "no_significant_terms")
        return write_artifacts(artifact_root,self.validator_id,base,rows)
