from __future__ import annotations
import re, xml.etree.ElementTree as ET
def _text(node): return re.sub(r"\s+"," "," ".join(node.itertext())).strip()
def parse_jats(xml:bytes|str, *, exclude_references:bool=True)->dict:
    root=ET.fromstring(xml); title=_text(root.find(".//article-title")) if root.find(".//article-title") is not None else ""; abstract=_text(root.find(".//abstract")) if root.find(".//abstract") is not None else ""
    sections=[]
    for i,sec in enumerate(root.findall(".//body/sec"),1):
        heading=_text(sec.find("title")) if sec.find("title") is not None else f"Section {i}"
        if exclude_references and heading.lower() in {"references","bibliography"}: continue
        text=_text(sec); sections.append({"section_id":f"sec_{i}","section_title":heading,"text":text,"token_count_estimate":max(1,len(text)//4)})
    return {"title":title,"abstract":abstract,"sections":sections,"references_removed":exclude_references,"tables_captions_included":True,"figures_captions_included":True}

def parse_bioc_xml(xml:bytes|str)->dict:
    root=ET.fromstring(xml);sections=[];title="";abstract=""
    for index,passage in enumerate(root.findall(".//passage"),1):
        infons={str(x.get("key") or ""):str(x.text or "") for x in passage.findall("infon")}
        kind=(infons.get("section_type") or infons.get("type") or "").casefold()
        heading=infons.get("section") or infons.get("section_title") or kind or f"Section {index}"
        text=" ".join(str(x.text or "").strip() for x in passage.findall("text") if str(x.text or "").strip())
        if not text:continue
        if kind=="title" and not title:title=text
        if kind=="abstract" and not abstract:abstract=text
        if kind in {"ref","references","bibliography"}:continue
        sections.append({"section_id":f"bioc_{index}","section_title":heading,"text":text,"token_count_estimate":max(1,len(text)//4)})
    return {"title":title,"abstract":abstract,"sections":sections,"references_removed":True,"tables_captions_included":True,"figures_captions_included":True,"source_format":"bioc_xml"}
