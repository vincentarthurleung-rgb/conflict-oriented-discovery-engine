from __future__ import annotations
import xml.etree.ElementTree as ET
from typing import Callable
from urllib.request import urlopen

OA_URL="https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id="
ALLOWED_HOSTS=("www.ncbi.nlm.nih.gov","ftp.ncbi.nlm.nih.gov","pmc.ncbi.nlm.nih.gov")

def _resource(format_name:str,href:str,label:str="")->dict:
    original_href=href
    if href.startswith("ftp://ftp.ncbi.nlm.nih.gov/"): href="https://ftp.ncbi.nlm.nih.gov/"+href.split("/",3)[3]
    fmt=format_name.casefold();lower=href.casefold()
    if fmt in {"xml","nxml"} or lower.endswith((".xml",".nxml")): kind="nxml" if fmt=="nxml" or lower.endswith(".nxml") else "jats_xml"
    elif fmt in {"tgz","tar.gz","gz"} or lower.endswith((".tar.gz",".tgz",".gz")): kind="pmc_oa_archive"
    elif fmt in {"bioc_xml","bioc"}: kind="bioc_xml"
    elif fmt=="pdf" or lower.endswith(".pdf"): kind="pdf"
    else: kind="unsupported"
    supported=kind in {"jats_xml","nxml","pmc_oa_archive","bioc_xml"}
    reason="supported_direct_xml" if kind in {"jats_xml","nxml"} else "supported_pmc_oa_archive" if kind=="pmc_oa_archive" else "supported_bioc_xml" if kind=="bioc_xml" else "unsupported_pdf_only" if kind=="pdf" else "unsupported_resource_type"
    return {"format":fmt,"resource_type":kind,"url":href,"original_url":original_href,"label":label or fmt,"content_type":None,"supported":supported,"support_reason":reason,
        "preferred":kind in {"jats_xml","nxml"}}

def check_oa_availability(pmcid:str, *, network_enabled:bool=False, transport:Callable[[str],bytes]|None=None)->dict:
    base={"pmcid":pmcid,"oa_status":"unavailable","license":"unknown","download_resources":[],"selected_resource":None,"decision":"skip_no_resource"}
    if not network_enabled: return {**base,"decision":"network_disabled"}
    try:
        raw=transport(OA_URL+pmcid) if transport else urlopen(OA_URL+pmcid,timeout=30).read()
        root=ET.fromstring(raw); error=root.find("error")
        if error is not None: return {**base,"decision":"skip_non_oa","reason":"not_in_pmc_oa_subset"}
        record=root.find("records/record"); license_name=record.get("license","unknown") if record is not None else "unknown"; resources=[]
        for link in ([] if record is None else record.findall("link")):
            fmt=link.get("format",""); href=link.get("href","")
            if href.startswith(("https://","ftp://")): resources.append(_resource(fmt,href,link.get("label",fmt)))
        if record is not None and any(x["resource_type"] in {"jats_xml","nxml","bioc_xml","pmc_oa_archive"} for x in resources):
            resources.append(_resource("bioc_xml",f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmcid}/unicode","NCBI PMC BioC XML"))
        supported=[x for x in resources if x["supported"]]
        rank={"jats_xml":0,"nxml":0,"bioc_xml":1,"pmc_oa_archive":2}
        selected=min(supported,key=lambda x:rank.get(x["resource_type"],9)) if supported else None
        reason=None if selected else "oa_metadata_no_links" if not resources else "only_pdf_resources_available" if all(x["resource_type"]=="pdf" for x in resources) else "oa_links_present_but_unsupported_types"
        return {**base,"oa_status":"available" if record is not None else "unavailable","license":license_name,"download_resources":resources,"selected_resource":selected,
            "decision":"download_allowed" if selected else "skip_no_resource","reason":reason}
    except Exception as exc: return {**base,"oa_status":"unknown_error","decision":"skip_no_resource","reason":"retrieval_error","error":str(exc)}
