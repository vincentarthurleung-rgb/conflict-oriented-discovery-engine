from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import urlopen
from code_engine.fulltext.jats_parser import parse_jats
from code_engine.fulltext.pmc_oa_client import ALLOWED_HOSTS

def download_oa_article(paper:dict, availability:dict, output_root:str|Path, *, network_enabled:bool=False, transport:Callable[[str],bytes]|None=None)->dict:
    resource=availability.get("selected_resource"); pmcid=paper.get("pmcid") or availability.get("pmcid"); base={"paper_id":paper.get("paper_id"),"pmid":paper.get("pmid"),"pmcid":pmcid,"copyright_safe":True}
    if availability.get("decision")!="download_allowed" or not resource: return {**base,"full_text_status":"unavailable","reason":availability.get("reason") or "no_oa_download_resource"}
    if resource.get("format") not in {"jats_xml","bioc_xml","bioc_json"}: return {**base,"full_text_status":"unavailable","reason":"no_supported_oa_download_resource"}
    host=urlparse(resource["url"]).hostname
    if host not in ALLOWED_HOSTS: return {**base,"full_text_status":"unavailable","reason":"non_official_resource_rejected"}
    if not network_enabled: return {**base,"full_text_status":"unavailable","reason":"network_disabled"}
    try:
        raw=transport(resource["url"]) if transport else urlopen(resource["url"],timeout=60).read()
        if resource["format"]!="jats_xml": return {**base,"full_text_status":"unavailable","reason":"supported_parser_not_implemented"}
        parsed=parse_jats(raw); parsed.update(pmcid=pmcid,pmid=paper.get("pmid"))
        dest=Path(output_root)/str(pmcid); dest.mkdir(parents=True,exist_ok=True)
        (dest/"article.xml").write_bytes(raw); (dest/"article_text.json").write_text(json.dumps(parsed,ensure_ascii=False,indent=2),encoding="utf-8")
        (dest/"article_sections.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in parsed["sections"]),encoding="utf-8")
        metadata={**base,"full_text_status":"available","access_source":"pmc_oa","license_status":"oa_reuse_allowed","retrieval_url_or_resource":resource["url"],"retrieved_at":datetime.now(timezone.utc).isoformat(),"sha256":hashlib.sha256(raw).hexdigest(),"copyright_safe":True}
        (dest/"retrieval_metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8"); return metadata
    except Exception as exc: return {**base,"full_text_status":"unavailable","reason":"retrieval_error","error":str(exc)}
