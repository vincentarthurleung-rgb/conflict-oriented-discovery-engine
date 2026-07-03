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
