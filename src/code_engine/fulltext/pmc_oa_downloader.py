from __future__ import annotations
import gzip,hashlib,io,json,tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import urlopen
from code_engine.fulltext.jats_parser import parse_bioc_xml,parse_jats
from code_engine.fulltext.pmc_oa_client import ALLOWED_HOSTS

MAX_ARCHIVE_FILES=2000
MAX_ARCHIVE_BYTES=250*1024*1024
MAX_XML_BYTES=50*1024*1024

def _looks_xml(raw:bytes)->bool:
    return raw.lstrip().startswith(b"<")

def _xml_score(name:str,raw:bytes)->tuple[int,int]:
    lower=name.casefold();sample=raw[:20000].lower()
    return (4 if lower.endswith(".nxml") else 3 if b"<article" in sample else 2 if lower.endswith(".xml") else 1, len(raw))

def _archive_xml(raw:bytes,resource_url:str)->tuple[bytes,str,int]:
    files=[]
    if tarfile.is_tarfile(io.BytesIO(raw)):
        with tarfile.open(fileobj=io.BytesIO(raw),mode="r:*") as archive:
            members=archive.getmembers()
            if len(members)>MAX_ARCHIVE_FILES: raise ValueError("archive_file_count_limit_exceeded")
            total=0
            for member in members:
                name=member.name.replace("\\","/")
                if member.issym() or member.islnk() or name.startswith("/") or ".." in name.split("/"): raise ValueError("archive_unsafe_path")
                if not member.isfile(): continue
                total+=member.size
                if total>MAX_ARCHIVE_BYTES or member.size>MAX_XML_BYTES: raise ValueError("archive_size_limit_exceeded")
                if name.casefold().endswith((".nxml",".xml")):
                    handle=archive.extractfile(member);data=handle.read() if handle else b""
                    if _looks_xml(data): files.append((name,data))
            count=len([x for x in members if x.isfile()])
    else:
        try:data=gzip.decompress(raw)
        except Exception as exc: raise ValueError("archive_extraction_failed") from exc
        if len(data)>MAX_XML_BYTES: raise ValueError("archive_size_limit_exceeded")
        if not _looks_xml(data): raise ValueError("archive_contains_no_xml")
        name=Path(resource_url).name.removesuffix(".gz") or "article.xml";files=[(name,data)];count=1
    if not files: raise ValueError("archive_contains_no_xml")
    name,data=max(files,key=lambda x:_xml_score(x[0],x[1]));return data,name,count

def download_oa_article(paper:dict, availability:dict, output_root:str|Path, *, network_enabled:bool=False, transport:Callable[[str],bytes]|None=None)->dict:
    resource=availability.get("selected_resource"); pmcid=paper.get("pmcid") or availability.get("pmcid"); base={"paper_id":paper.get("paper_id"),"pmid":paper.get("pmid"),"pmcid":pmcid,"copyright_safe":True,
        "resource_type":(resource or {}).get("resource_type","unsupported"),"resource_url":(resource or {}).get("url"),"resource_selected":bool(resource),
        "resource_selection_reason":(resource or {}).get("support_reason"),"archive_downloaded":False,"archive_extracted":False,"archive_file_count":0,
        "selected_xml_file":None,"selected_xml_kind":None}
    if availability.get("decision")!="download_allowed" or not resource: return {**base,"full_text_status":"unavailable","reason":availability.get("reason") or "no_supported_oa_download_resource"}
    host=urlparse(resource["url"]).hostname
    if host not in ALLOWED_HOSTS: return {**base,"full_text_status":"unavailable","reason":"non_official_resource_rejected"}
    if not network_enabled: return {**base,"full_text_status":"unavailable","reason":"network_disabled"}
    try:
        raw=transport(resource["url"]) if transport else urlopen(resource["url"],timeout=60).read()
    except Exception as exc:
        return {**base,"full_text_status":"unavailable","download_status":"failed","reason":"jats_download_http_error","error":str(exc)}
    if not raw:
        return {**base,"full_text_status":"unavailable","download_status":"failed","reason":"jats_download_empty"}
    archive=resource.get("resource_type")=="pmc_oa_archive"
    selected_name=Path(resource["url"]).name
    archive_count=0
    if archive:
        try:raw,selected_name,archive_count=_archive_xml(raw,resource["url"])
        except ValueError as exc:
            reason=str(exc);return {**base,"full_text_status":"unavailable","download_status":"success","archive_downloaded":True,
                "archive_extracted":reason not in {"archive_extraction_failed","archive_unsafe_path","archive_file_count_limit_exceeded","archive_size_limit_exceeded"},"reason":reason}
    elif not _looks_xml(raw):
        return {**base,"full_text_status":"unavailable","download_status":"success","reason":"xml_download_failed"}
    try:
        parsed=(parse_bioc_xml(raw) if resource.get("resource_type")=="bioc_xml" else parse_jats(raw)); parsed.update(pmcid=pmcid,pmid=paper.get("pmid"))
        dest=Path(output_root)/str(pmcid); dest.mkdir(parents=True,exist_ok=True)
        if archive:
            extracted=dest/"archive_extracted";extracted.mkdir(exist_ok=True);(extracted/Path(selected_name).name).write_bytes(raw)
        (dest/"article.xml").write_bytes(raw); (dest/"article_text.json").write_text(json.dumps(parsed,ensure_ascii=False,indent=2),encoding="utf-8")
        (dest/"article_sections.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in parsed["sections"]),encoding="utf-8")
        kind="bioc" if resource.get("resource_type")=="bioc_xml" else "nxml" if selected_name.casefold().endswith(".nxml") else "jats"
        metadata={**base,"full_text_status":"available","download_status":"success","parse_status":"success","access_source":"pmc_oa","license_status":"oa_reuse_allowed","retrieval_url_or_resource":resource["url"],"retrieved_at":datetime.now(timezone.utc).isoformat(),"sha256":hashlib.sha256(raw).hexdigest(),"copyright_safe":True,
            "archive_downloaded":archive,"archive_extracted":archive,"archive_file_count":archive_count,"selected_xml_file":selected_name,"selected_xml_kind":kind,"parsed_section_count":len(parsed.get("sections",[]))}
        (dest/"retrieval_metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8"); return metadata
    except Exception as exc: return {**base,"full_text_status":"unavailable","download_status":"success","reason":"jats_parse_failed","error":str(exc)}
