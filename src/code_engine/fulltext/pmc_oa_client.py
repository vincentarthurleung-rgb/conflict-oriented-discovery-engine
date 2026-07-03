from __future__ import annotations
import xml.etree.ElementTree as ET
from typing import Callable
from urllib.request import urlopen

OA_URL="https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id="
ALLOWED_HOSTS=("www.ncbi.nlm.nih.gov","ftp.ncbi.nlm.nih.gov","pmc.ncbi.nlm.nih.gov")
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
            if fmt in {"tgz","xml","bioc_xml","bioc_json"} and href.startswith(("https://","ftp://")): resources.append({"format":"jats_xml" if fmt=="xml" else fmt,"url":href,"preferred":fmt=="xml"})
        selected=next((x for x in resources if x["preferred"]),resources[0] if resources else None)
        return {**base,"oa_status":"available" if selected else "unavailable","license":license_name,"download_resources":resources,"selected_resource":selected,"decision":"download_allowed" if selected else "skip_no_resource"}
    except Exception as exc: return {**base,"oa_status":"unknown_error","decision":"skip_no_resource","reason":"retrieval_error","error":str(exc)}
