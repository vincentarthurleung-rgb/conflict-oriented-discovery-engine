"""Conflict-focused, cached PMC OA section extraction using the existing L1 client."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from code_engine.extraction.l1_response import normalize_l1_json_response
from code_engine.extraction.client_factory import diagnose_l1_provider

PROMPT_VERSION = "fulltext_conflict_l1_v1"
PREFERRED = {"results", "discussion", "conclusion", "introduction", "abstract", "figure_caption", "table_caption"}
EXCLUDED = {"references", "bibliography", "acknowledgments", "acknowledgements", "funding", "author contributions"}
SECTION_WEIGHTS={"results":1.0,"discussion":.85,"abstract":.70,"introduction":.55,"methods":.40,"other":.25}

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
    return """You are performing conservative biomedical claim extraction from one PMC Open Access full-text chunk.
Extract only explicit mechanistic claims stated in this chunk. Do not summarize the paper and do not infer beyond the text. Preserve entities, direction, context, and a verbatim evidence sentence. If there is no relevant evidence return {\"claims\": []}.
Return JSON object {\"claims\":[{\"relation_family\":\"...\",\"subject\":\"...\",\"predicate\":\"...\",\"object\":\"...\",\"polarity\":\"positive|negative|neutral|unclear\",\"direction\":\"...\",\"context\":{},\"context_terms\":[],\"evidence_sentence\":\"...\",\"confidence\":0.0,\"extraction_warnings\":[]}]}.
SOURCE_SCOPE: full_text
TARGET_CONFLICT: %s
SECTION_TITLE: %s
SECTION_TYPE: %s
SECTION_TEXT:
%s""" % (json.dumps(focus,ensure_ascii=False), section.get("section_title"),section.get("section_type"), chunk)

def run_fulltext_l1_extraction(*, run_dir: Path, fulltext_candidates_path: Path, parsed_articles_dir: Path,
    l1_provider: str, l1_model: str, api_enabled: bool, network_enabled: bool, max_papers: int=20,
    max_sections_per_paper: int=12, max_chunks_per_paper: int=24, max_chars_per_chunk: int=6000,
    max_total_chunks: int=200, section_policy: str="results_discussion_intro_only", dry_run: bool=False,
    client: Any|None=None, read_timeout_seconds: float=240, max_retries: int=1, reuse_selected_chunks: bool=True) -> dict[str, Any]:
    artifacts=Path(run_dir)/"artifacts"; cache_dir=artifacts/"cache/fulltext_l1"; cache_dir.mkdir(parents=True,exist_ok=True)
    candidates=_jsonl(Path(fulltext_candidates_path))[:max_papers];claims=[];chunk_records=[];execution_records=[];planned=[];sections_selected=0;skipped=0;limit_hit=False
    selected_path=artifacts/"l35_fulltext_discovery_selected_chunks.jsonl";cached_chunks=_jsonl(selected_path) if reuse_selected_chunks else []
    if cached_chunks:
        by_pmcid={str(x.get("pmcid")):x for x in candidates}
        for row in cached_chunks[:max_total_chunks]:
            paper=by_pmcid.get(str(row.get("pmcid")),row);section={"section_title":row.get("section_title"),"section_type":row.get("section_type"),"section_index":row.get("section_index",0)}
            text=str(row.get("text") or "");planned.append((paper,section,text,row.get("chunk_hash") or hashlib.sha256(text.encode()).hexdigest(),row.get("chunk_id")))
        sections_selected=len({(x.get("pmcid"),x.get("section_index")) for x in cached_chunks})
    else:
        selected=[]
        for paper in candidates:
            article_path=Path(parsed_articles_dir)/str(paper.get("pmcid"))/"article_text.json"
            if not article_path.is_file(): continue
            article=json.loads(article_path.read_text(encoding="utf-8")); sections=select_sections(article,max_sections=max_sections_per_paper,policy=section_policy); sections_selected+=len(sections); paper_chunks=0
            for section in sections:
                for chunk_index,text in enumerate(chunk_text(section["text"],max_chars_per_chunk)):
                    if paper_chunks>=max_chunks_per_paper or len(planned)>=max_total_chunks: skipped+=1;limit_hit=True;continue
                    paper_chunks+=1;digest=hashlib.sha256(text.encode()).hexdigest();cid=f"{paper.get('pmcid')}_{section['section_index']}_{chunk_index}"
                    tier=section.get("section_type") or "other";planned.append((paper,section,text,digest,cid));selected.append({"chunk_id":cid,"chunk_hash":digest,"pmid":paper.get("pmid"),"pmcid":paper.get("pmcid"),"title":paper.get("title"),"section_title":section.get("section_title"),"section_type":tier,"section_evidence_tier":tier,"section_evidence_weight":SECTION_WEIGHTS.get(tier,.25),"section_index":section.get("section_index"),"chunk_index":chunk_index,"text":text,"source_scope":"full_text","selection_score":paper.get("selection_score",0.0),"selection_reasons":paper.get("selection_reasons",[]),"linked_observation_ids":paper.get("abstract_observation_ids",[]),"linked_weak_candidate_ids":paper.get("conflict_candidate_ids",[])})
        selected_path.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in selected),encoding="utf-8")
    provider_errors=parse_errors=api_calls=cache_hits=0
    blocked=not (api_enabled and network_enabled and client is not None)
    provider_diag=diagnose_l1_provider(l1_provider,l1_model,api_enabled=api_enabled,network_enabled=network_enabled)
    if client is not None:provider_diag.update(provider_available=True,provider_error=None)
    for paper,section,text,digest,cid in planned:
        key_payload="\x1f".join((str(paper.get("pmcid")),str(section["section_index"]),digest,"|".join(map(str,paper.get("conflict_candidate_ids",[]))),l1_provider,l1_model,PROMPT_VERSION))
        key=hashlib.sha256(key_payload.encode()).hexdigest(); cache_path=cache_dir/f"{key}.json"
        if cache_path.is_file():
            raw_claims=json.loads(cache_path.read_text(encoding="utf-8")).get("claims",[]); cache_status="hit"; cache_hits+=1
        elif dry_run or blocked:
            status="planned" if dry_run else "blocked";chunk_records.append({"chunk_id":cid,"chunk_hash":digest,"cache_status":"miss","api_call_made":False,"extraction_status":status})
            execution_records.append({"chunk_id":cid,"pmid":paper.get("pmid"),"pmcid":paper.get("pmcid"),"title":paper.get("title"),"provider":l1_provider,"model":l1_model,"fulltext_l1_attempted":False,"fulltext_l1_status":"skipped","fulltext_l1_error_type":"provider_unavailable" if blocked else None,"fulltext_l1_error_message":provider_diag.get("provider_error"),"claim_count":0,"schema_valid":True,"retry_count":0,"source_scope":"full_text"});continue
        else:
            try:
                response=client.extract_json(build_prompt(paper,section,text),model=l1_model,temperature=0,top_p=1,timeout=read_timeout_seconds,max_retries=max_retries); api_calls+=1
                normalized,_=normalize_l1_json_response(response); raw_claims=normalized["claims"]; cache_path.write_text(json.dumps({"claims":raw_claims,"prompt_version":PROMPT_VERSION},ensure_ascii=False,indent=2),encoding="utf-8"); cache_status="miss"
            except Exception as exc:
                error_type="parse_error" if "json" in str(exc).casefold() or "claims" in str(exc).casefold() else "provider_error"
                parse_errors += error_type=="parse_error"; provider_errors += error_type=="provider_error"
                message=str(exc)[:500];chunk_records.append({"chunk_id":cid,"chunk_hash":digest,"cache_status":"miss","api_call_made":True,"extraction_status":error_type,"error":message})
                execution_records.append({"chunk_id":cid,"pmid":paper.get("pmid"),"pmcid":paper.get("pmcid"),"title":paper.get("title"),"provider":l1_provider,"model":l1_model,"fulltext_l1_attempted":True,"fulltext_l1_status":"failed","fulltext_l1_error_type":error_type,"fulltext_l1_error_message":message,"claim_count":0,"schema_valid":error_type!="parse_error","retry_count":max_retries,"source_scope":"full_text"});continue
        for index,raw in enumerate(raw_claims):
            tier=section.get("section_type") or "other";claims.append({"claim_id":raw.get("claim_id") or f"ft_{digest[:12]}_{index}","source_scope":"full_text","paper_id":paper.get("paper_id"),"pmid":paper.get("pmid"),"pmcid":paper.get("pmcid"),"section_title":section.get("section_title"),"section_type":tier,"section_evidence_tier":tier,"section_evidence_weight":SECTION_WEIGHTS.get(tier,.25),"chunk_id":cid,"chunk_hash":digest,"linked_abstract_observation_ids":paper.get("abstract_observation_ids",[]),"linked_conflict_candidate_ids":paper.get("conflict_candidate_ids",[]),"relation_family":raw.get("relation_family") or paper.get("conflict_relation"),"subject":raw.get("subject"),"predicate":raw.get("predicate"),"object":raw.get("object"),"polarity":raw.get("polarity","unclear"),"direction":raw.get("direction") or raw.get("polarity","unclear"),"context":raw.get("context",{}),"context_terms":raw.get("context_terms",[]),"confidence":raw.get("confidence"),"extraction_warnings":raw.get("extraction_warnings",[]),"evidence_sentence":raw.get("evidence_sentence",""),"evidence_char_start":raw.get("evidence_char_start"),"evidence_char_end":raw.get("evidence_char_end"),"l1_provider":l1_provider,"l1_model":l1_model,"extraction_status":"success"})
        chunk_records.append({"chunk_id":cid,"chunk_hash":digest,"cache_status":cache_status,"api_call_made":cache_status=="miss","extraction_status":"success" if raw_claims else "no_relevant_claim"})
        execution_records.append({"chunk_id":cid,"pmid":paper.get("pmid"),"pmcid":paper.get("pmcid"),"title":paper.get("title"),"provider":l1_provider,"model":l1_model,"fulltext_l1_attempted":True,"fulltext_l1_status":"success","fulltext_l1_error_type":None,"fulltext_l1_error_message":None,"claim_count":len(raw_claims),"schema_valid":True,"retry_count":0,"source_scope":"full_text"})
    attempted=sum(x["fulltext_l1_attempted"] for x in execution_records);success=sum(x["fulltext_l1_status"]=="success" for x in execution_records);failed=sum(x["fulltext_l1_status"]=="failed" for x in execution_records);skipped_count=sum(x["fulltext_l1_status"]=="skipped" for x in execution_records)
    status="skipped_provider_unavailable" if planned and blocked and not dry_run else "skipped" if not planned else "failed" if attempted and failed==attempted else "partially_completed" if failed else "completed_with_claims" if claims else "completed_no_claims"
    summary={"fulltext_l1_status":status,"candidate_paper_count":len(candidates),"oa_available_count":len({p.get('pmcid') for p,_,_,_,_ in planned}),"papers_processed":len({p.get('paper_id') for p,_,_,_,_ in planned}),"sections_selected":sections_selected,"selected_chunk_count":len(planned),"chunks_planned":len(planned),"chunks_processed":sum(x["extraction_status"] not in {"blocked","planned"} for x in chunk_records),"chunks_skipped":skipped,"api_calls_made":api_calls,"cache_hits":cache_hits,"provider_errors":provider_errors,"parse_errors":parse_errors,"fulltext_claim_count":len(claims),"fulltext_l1_claim_count":len(claims),"fulltext_l1_attempted_count":attempted,"fulltext_l1_success_count":success,"fulltext_l1_failed_count":failed,"fulltext_l1_skipped_count":skipped_count,"fulltext_l1_provider":l1_provider,"fulltext_l1_model":l1_model,**{k:v for k,v in provider_diag.items() if k not in {"scope","provider","model"}},"cost_estimate":None,"limit_hit":limit_hit,"limit_type":"max_total_or_per_paper_chunks" if limit_hit else None,"skipped_remaining_chunks":skipped,"prompt_version":PROMPT_VERSION}
    (artifacts/"l35_fulltext_l1_claims.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in claims),encoding="utf-8"); (artifacts/"l35_fulltext_l1_chunks.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in chunk_records),encoding="utf-8");(artifacts/"l35_fulltext_l1_execution_records.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in execution_records),encoding="utf-8"); (artifacts/"l35_fulltext_l1_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"summary":summary,"claims":claims,"chunks":chunk_records}
