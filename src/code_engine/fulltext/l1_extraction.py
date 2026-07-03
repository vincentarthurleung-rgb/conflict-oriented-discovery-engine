from __future__ import annotations
import hashlib
from typing import Callable

def extract_fulltext_claims(paper:dict, article:dict, *, extractor:Callable[[str,dict],list[dict]]|None, provider:str|None=None, model:str|None=None, max_sections:int=12)->list[dict]:
    """Run an injected L1 extractor per section; never manufactures claims."""
    if extractor is None: return []
    claims=[]
    for index,section in enumerate(article.get("sections",[])[:max_sections]):
        text=section.get("text",""); chunk_hash=hashlib.sha256(text.encode()).hexdigest()
        context={"paper":paper,"section_title":section.get("section_title"),"section_index":index,"conflict_relation":paper.get("conflict_relation")}
        for raw in extractor(text,context) or []:
            claims.append({**raw,"claim_id":raw.get("claim_id") or f"ft_{paper.get('pmcid')}_{chunk_hash[:12]}_{len(claims)}","source_scope":"full_text","pmid":paper.get("pmid"),"pmcid":paper.get("pmcid"),"section_title":section.get("section_title"),"section_index":index,"chunk_hash":chunk_hash,"linked_abstract_observation_ids":paper.get("abstract_observation_ids",[]),"linked_conflict_candidate_ids":paper.get("conflict_candidate_ids",[]),"l1_provider":provider,"l1_model":model,"extraction_status":"success"})
    return claims
