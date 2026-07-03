from __future__ import annotations
import json
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.request import urlopen

IDCONV_URL="https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
def resolve_pmcid(paper:dict, *, network_enabled:bool=False, cache_dir:str|Path|None=None, transport:Callable[[str],dict]|None=None)->dict:
    base={"paper_id":paper.get("paper_id"),"pmid":paper.get("pmid"),"doi":paper.get("doi"),"pmcid":paper.get("pmcid"),"idconv_error":None}
    if paper.get("pmcid"): return {**base,"idconv_status":"resolved","idconv_source":"metadata"}
    identifier=str(paper.get("pmid") or paper.get("doi") or ""); cache=Path(cache_dir) if cache_dir else None; cached=cache/f"{identifier.replace('/','_')}.json" if cache and identifier else None
    if cached and cached.is_file():
        data=json.loads(cached.read_text(encoding="utf-8")); return {**base,**data,"idconv_source":"cache"}
    if not identifier: return {**base,"idconv_status":"no_pmcid","idconv_source":"metadata"}
    if not network_enabled: return {**base,"idconv_status":"network_disabled","idconv_source":None}
    try:
        url=IDCONV_URL+"?"+urlencode({"ids":identifier,"format":"json","tool":"code_engine"})
        if transport: payload=transport(url)
        else:
            with urlopen(url,timeout=30) as response: payload=json.load(response)
        record=(payload.get("records") or [{}])[0]; pmcid=record.get("pmcid"); result={**base,"pmcid":pmcid,"idconv_status":"resolved" if pmcid else "no_pmcid","idconv_source":"pmc_id_converter_api"}
    except Exception as exc: result={**base,"idconv_status":"error","idconv_source":"pmc_id_converter_api","idconv_error":str(exc)}
    if cached: cached.parent.mkdir(parents=True,exist_ok=True); cached.write_text(json.dumps({k:v for k,v in result.items() if k not in base or v!=base[k]},ensure_ascii=False,indent=2),encoding="utf-8")
    return result
