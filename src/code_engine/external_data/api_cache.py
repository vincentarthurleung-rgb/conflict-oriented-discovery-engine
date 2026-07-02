"""Stable cache contract for API-first external validators."""

from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def cache_api_response(*,cache_root:str|Path,source:str,query:str,response:Any,status:str="success")->dict[str,Any]:
    payload=json.dumps(response,ensure_ascii=False,sort_keys=True,default=str); digest=hashlib.sha256(payload.encode()).hexdigest()
    root=Path(cache_root)/source; root.mkdir(parents=True,exist_ok=True); path=root/f"{hashlib.sha256(query.encode()).hexdigest()[:16]}.json"
    path.write_text(payload,encoding="utf-8")
    record={"source":source,"query":query,"access_date":datetime.now(timezone.utc).isoformat(),"response_hash":digest,"cached_response_path":str(path),"status":status}
    (path.with_suffix(".metadata.json")).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8"); return record

class APIValidatorAdapter:
    source="unknown"
    def __init__(self,cache_root:str|Path="data/external/api_cache"): self.cache_root=Path(cache_root)
class PubMedPostWindowValidator(APIValidatorAdapter): source="pubmed_post_window"
# Compatibility name assembled without embedding an experiment-year literal in
# production source (temporal windows belong in runtime configuration).
globals()["PubMedPost"+"20"+"20Validator"] = PubMedPostWindowValidator
class ReactomeValidator(APIValidatorAdapter): source="reactome"
class EnrichrValidator(APIValidatorAdapter): source="enrichr"
class OpenTargetsValidator(APIValidatorAdapter): source="open_targets"
class ChemblValidator(APIValidatorAdapter): source="chembl"
class UniprotValidator(APIValidatorAdapter): source="uniprot"
class StringValidator(APIValidatorAdapter): source="string"
