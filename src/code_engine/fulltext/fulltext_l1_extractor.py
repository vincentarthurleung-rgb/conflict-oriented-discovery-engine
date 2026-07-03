"""Conflict-focused, cached PMC OA section extraction using the existing L1 client."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from code_engine.extraction.l1_response import normalize_l1_json_response

PROMPT_VERSION = "fulltext_conflict_l1_v1"
PREFERRED = {"results", "discussion", "conclusion", "introduction", "abstract", "figure_caption", "table_caption"}
EXCLUDED = {"references", "bibliography", "acknowledgments", "acknowledgements", "funding", "author contributions"}

def _jsonl(path: Path) -> list[dict[str, Any]]:
    try: return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError): return []

def classify_section(title: str) -> str:
    value=title.casefold().strip()
    for kind, words in (("results",("result",)),("discussion",("discussion",)),("conclusion",("conclusion",)),("introduction",("introduction","background")),("abstract",("abstract",)),("figure_caption",("figure",)),("table_caption",("table",))):
        if any(word in value for word in words): return kind
    return "other"

def select_sections(article: dict[str, Any], *, max_sections: int=12, policy: str="results_discussion_intro_only") -> list[dict[str, Any]]:
    selected=[]
    for index, section in enumerate(article.get("sections", [])):
        title=str(section.get("section_title") or ""); lowered=title.casefold().strip(); kind=classify_section(title)
        if lowered in EXCLUDED or kind=="other" or not str(section.get("text") or "").strip(): continue
        selected.append({**section,"section_type":kind,"section_index":index,"selected_for_l1":True,"selection_reason":"matches policy and linked conflict entities"})
        if len(selected)>=max_sections: break
    return selected

def chunk_text(text: str, max_chars: int=6000) -> list[str]:
    text=re.sub(r"\s+"," ",text).strip()
    if not text: return []
    chunks=[]
    while text:
        if len(text)<=max_chars: chunks.append(text); break
        cut=text.rfind(". ",0,max_chars)
        if cut < max_chars//2: cut=max_chars
        else: cut+=1
        chunks.append(text[:cut].strip()); text=text[cut:].strip()
    return chunks

def build_prompt(candidate: dict[str, Any], section: dict[str, Any], chunk: str) -> str:
    focus={"case_id":candidate.get("case_id"),"relation_family":candidate.get("conflict_relation") or candidate.get("relation_family"),"subject":candidate.get("subject"),"object":candidate.get("object"),"competing_polarities":candidate.get("competing_polarities",["positive","negative"]),"abstract_observation_ids":candidate.get("abstract_observation_ids",[]),"abstract_evidence_snippets":candidate.get("abstract_evidence_snippets",[]),"context_terms":candidate.get("context_terms",[])}
    return """You are performing conflict-focused extraction from a PMC Open Access article section.
Extract only explicit claims relevant to the target relation. Do not infer beyond the text. Preserve entities, direction, polarity, context, and a verbatim evidence sentence. If there is no relevant evidence return {\"claims\": []}.
Return JSON object {\"claims\":[{\"relation_family\":\"...\",\"subject\":\"...\",\"predicate\":\"...\",\"object\":\"...\",\"polarity\":\"positive|negative|neutral|unclear\",\"context\":{},\"evidence_sentence\":\"...\"}]}.
TARGET_CONFLICT: %s
SECTION_TITLE: %s
SECTION_TEXT:
%s""" % (json.dumps(focus,ensure_ascii=False), section.get("section_title"), chunk)

def run_fulltext_l1_extraction(*, run_dir: Path, fulltext_candidates_path: Path, parsed_articles_dir: Path,
    l1_provider: str, l1_model: str, api_enabled: bool, network_enabled: bool, max_papers: int=20,
    max_sections_per_paper: int=12, max_chunks_per_paper: int=24, max_chars_per_chunk: int=6000,
    max_total_chunks: int=200, section_policy: str="results_discussion_intro_only", dry_run: bool=False,
    client: Any|None=None, read_timeout_seconds: float=240, max_retries: int=1) -> dict[str, Any]:
    artifacts=Path(run_dir)/"artifacts"; cache_dir=artifacts/"cache/fulltext_l1"; cache_dir.mkdir(parents=True,exist_ok=True)
    candidates=_jsonl(Path(fulltext_candidates_path))[:max_papers]; claims=[]; chunk_records=[]; planned=[]; sections_selected=0; skipped=0; limit_hit=False
    for paper in candidates:
        article_path=Path(parsed_articles_dir)/str(paper.get("pmcid"))/"article_text.json"
        if not article_path.is_file(): continue
        article=json.loads(article_path.read_text(encoding="utf-8")); sections=select_sections(article,max_sections=max_sections_per_paper,policy=section_policy); sections_selected+=len(sections); paper_chunks=0
        for section in sections:
            for chunk_index, text in enumerate(chunk_text(section["text"],max_chars_per_chunk)):
                if paper_chunks>=max_chunks_per_paper or len(planned)>=max_total_chunks: skipped+=1; limit_hit=True; continue
                paper_chunks+=1; digest=hashlib.sha256(text.encode()).hexdigest(); cid=f"{paper.get('pmcid')}_{section['section_index']}_{chunk_index}"
                planned.append((paper,section,text,digest,cid))
    provider_errors=parse_errors=api_calls=cache_hits=0
    blocked=not (api_enabled and network_enabled and client is not None)
    for paper,section,text,digest,cid in planned:
        key_payload="\x1f".join((str(paper.get("pmcid")),str(section["section_index"]),digest,"|".join(map(str,paper.get("conflict_candidate_ids",[]))),l1_provider,l1_model,PROMPT_VERSION))
        key=hashlib.sha256(key_payload.encode()).hexdigest(); cache_path=cache_dir/f"{key}.json"
        if cache_path.is_file():
            raw_claims=json.loads(cache_path.read_text(encoding="utf-8")).get("claims",[]); cache_status="hit"; cache_hits+=1
        elif dry_run or blocked:
            chunk_records.append({"chunk_id":cid,"chunk_hash":digest,"cache_status":"miss","api_call_made":False,"extraction_status":"planned" if dry_run else "blocked"}); continue
        else:
            try:
                response=client.extract_json(build_prompt(paper,section,text),model=l1_model,temperature=0,top_p=1,timeout=read_timeout_seconds,max_retries=max_retries); api_calls+=1
                normalized,_=normalize_l1_json_response(response); raw_claims=normalized["claims"]; cache_path.write_text(json.dumps({"claims":raw_claims,"prompt_version":PROMPT_VERSION},ensure_ascii=False,indent=2),encoding="utf-8"); cache_status="miss"
            except Exception as exc:
                error_type="parse_error" if "json" in str(exc).casefold() or "claims" in str(exc).casefold() else "provider_error"
                parse_errors += error_type=="parse_error"; provider_errors += error_type=="provider_error"
                chunk_records.append({"chunk_id":cid,"chunk_hash":digest,"cache_status":"miss","api_call_made":True,"extraction_status":error_type,"error":str(exc)[:500]}); continue
        for index,raw in enumerate(raw_claims):
            claims.append({"claim_id":raw.get("claim_id") or f"ft_{digest[:12]}_{index}","source_scope":"full_text","paper_id":paper.get("paper_id"),"pmid":paper.get("pmid"),"pmcid":paper.get("pmcid"),"section_title":section.get("section_title"),"section_type":section.get("section_type"),"chunk_id":cid,"chunk_hash":digest,"linked_abstract_observation_ids":paper.get("abstract_observation_ids",[]),"linked_conflict_candidate_ids":paper.get("conflict_candidate_ids",[]),"relation_family":raw.get("relation_family") or paper.get("conflict_relation"),"subject":raw.get("subject"),"predicate":raw.get("predicate"),"object":raw.get("object"),"polarity":raw.get("polarity","unclear"),"context":raw.get("context",{}),"evidence_sentence":raw.get("evidence_sentence",""),"evidence_char_start":raw.get("evidence_char_start"),"evidence_char_end":raw.get("evidence_char_end"),"l1_provider":l1_provider,"l1_model":l1_model,"extraction_status":"success"})
        chunk_records.append({"chunk_id":cid,"chunk_hash":digest,"cache_status":cache_status,"api_call_made":cache_status=="miss","extraction_status":"success" if raw_claims else "no_relevant_claim"})
    status="skipped" if not planned else "blocked" if blocked and not dry_run else "partially_completed" if provider_errors or parse_errors or limit_hit else "completed"
    summary={"fulltext_l1_status":status,"candidate_paper_count":len(candidates),"oa_available_count":len({p.get('pmcid') for p,_,_,_,_ in planned}),"papers_processed":len({p.get('paper_id') for p,_,_,_,_ in planned}),"sections_selected":sections_selected,"chunks_planned":len(planned),"chunks_processed":sum(x["extraction_status"] not in {"blocked","planned"} for x in chunk_records),"chunks_skipped":skipped,"api_calls_made":api_calls,"cache_hits":cache_hits,"provider_errors":provider_errors,"parse_errors":parse_errors,"fulltext_claim_count":len(claims),"cost_estimate":None,"limit_hit":limit_hit,"limit_type":"max_total_or_per_paper_chunks" if limit_hit else None,"skipped_remaining_chunks":skipped,"prompt_version":PROMPT_VERSION}
    (artifacts/"l35_fulltext_l1_claims.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in claims),encoding="utf-8"); (artifacts/"l35_fulltext_l1_chunks.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in chunk_records),encoding="utf-8"); (artifacts/"l35_fulltext_l1_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"summary":summary,"claims":claims,"chunks":chunk_records}
