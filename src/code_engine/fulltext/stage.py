from __future__ import annotations
import json, os
from pathlib import Path
from typing import Callable
from code_engine.fulltext.candidate_selection import select_conflict_related_papers
from code_engine.fulltext.pmc_id_resolver import resolve_pmcid
from code_engine.fulltext.pmc_oa_client import check_oa_availability
from code_engine.fulltext.pmc_oa_downloader import download_oa_article
from code_engine.fulltext.l1_extraction import extract_fulltext_claims
from code_engine.fulltext.conflict_confirmation import confirm_fulltext_conflicts

def _write_json(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def _write_jsonl(path,rows): path.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")
def _expose_summary(artifacts:Path, summary:dict)->None:
    path=artifacts/"pipeline_stage_summary.json"
    try: payload=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): payload={}
    payload["l35_fulltext_confirmation"]=summary; _write_json(path,payload)
    block="\n## L3.5 OA Full-Text Retrieval and Confirmation\n\n"+"\n".join(f"- {k}: {v}" for k,v in summary.items())+"\n"
    for name in ("pipeline_stage_summary.md","whitebox_case_report.md"):
        target=artifacts/name
        if target.is_file(): target.write_text(target.read_text(encoding="utf-8")+block,encoding="utf-8")
    run_report=artifacts.parent/"run_report.md"
    if run_report.is_file(): run_report.write_text(run_report.read_text(encoding="utf-8")+block,encoding="utf-8")
    hypothesis=artifacts/"hypothesis_summary.json"
    if hypothesis.is_file():
        try: hp=json.loads(hypothesis.read_text(encoding="utf-8"))
        except json.JSONDecodeError: hp={}
        hp.update(full_text_confirmation_status=summary.get("status"),full_text_candidate_paper_count=summary.get("candidate_paper_count",0),full_text_available_count=summary.get("oa_available_count",0),full_text_l1_claim_count=summary.get("fulltext_l1_claim_count",0),full_text_confirmed_conflict_count=summary.get("fulltext_confirmed_conflict_count",0)); _write_json(hypothesis,hp)
def run_l35_pmc_oa_stage(run_dir:str|Path, *, enabled:bool, network_enabled:bool=False, max_papers:int=20, include_near_conflicts:bool=False, extractor:Callable|None=None, id_transport=None, oa_transport=None, download_transport=None)->dict:
    run=Path(run_dir); artifacts=run/"artifacts"; artifacts.mkdir(parents=True,exist_ok=True)
    selection=select_conflict_related_papers(artifacts,include_near_conflicts=include_near_conflicts,max_papers=max_papers) if enabled else {"selection_policy":"conflict_related_only","include_near_conflicts":include_near_conflicts,"source_artifacts":[],"candidate_paper_count":0,"candidate_papers":[],"status":"not_enabled","message":"Full-text confirmation is disabled by case policy."}
    _write_jsonl(artifacts/"l35_fulltext_candidate_papers.jsonl",selection["candidate_papers"])
    if not enabled or not selection["candidate_papers"]:
        status="not_enabled" if not enabled else "completed_no_candidates"; summary={"status":status,"candidate_paper_count":0,"pmcid_resolved_count":0,"oa_available_count":0,"fulltext_downloaded_count":0,"fulltext_l1_claim_count":0,"fulltext_confirmed_conflict_count":0,"copyright_safe":True,"non_oa_skipped_count":0,"message":selection["message"]}
        for name in ("l35_fulltext_retrieval_results.jsonl","l35_fulltext_l1_claims.jsonl","l35_fulltext_conflict_confirmations.jsonl"): _write_jsonl(artifacts/name,[])
        for name in ("l35_fulltext_retrieval_summary.json","l35_fulltext_l1_summary.json","l35_fulltext_conflict_confirmation_summary.json"): _write_json(artifacts/name,summary)
        _expose_summary(artifacts,summary)
        return summary
    results=[]; claims=[]; resolved=[]
    cache=artifacts/"cache/pmc_idconv"; fulltext_root=artifacts/"fulltext/pmc_oa"
    for paper in selection["candidate_papers"]:
        identity=resolve_pmcid(paper,network_enabled=network_enabled,cache_dir=cache,transport=id_transport); resolved.append(identity)
        if not identity.get("pmcid"): results.append({**identity,"full_text_status":"unavailable","reason":"no_pmcid" if identity.get("idconv_status")=="no_pmcid" else identity.get("idconv_status","retrieval_error"),"copyright_safe":True}); continue
        enriched={**paper,"pmcid":identity["pmcid"]}; oa=check_oa_availability(identity["pmcid"],network_enabled=network_enabled,transport=oa_transport)
        result=download_oa_article(enriched,oa,fulltext_root,network_enabled=network_enabled,transport=download_transport); results.append(result)
        if result.get("full_text_status")=="available":
            article=json.loads((fulltext_root/identity["pmcid"]/"article_text.json").read_text(encoding="utf-8")); claims += extract_fulltext_claims(enriched,article,extractor=extractor,provider=os.getenv("L1_PROVIDER"),model=os.getenv("MODEL_NAME"))
    conflict_map={}
    for paper in selection["candidate_papers"]:
        for cid in paper.get("conflict_candidate_ids",[]):
            if cid is not None: conflict_map.setdefault(str(cid),{"candidate_id":str(cid),"paper_ids":[]})["paper_ids"].append(str(paper.get("paper_id")))
    confirmation=confirm_fulltext_conflicts(list(conflict_map.values()),claims,results)
    all_available=all(x.get("full_text_status")=="available" for x in results)
    summary={"status":"completed" if all_available and extractor is not None else "partially_completed","candidate_paper_count":len(selection["candidate_papers"]),"pmcid_resolved_count":sum(bool(x.get("pmcid")) for x in resolved),"oa_available_count":sum(x.get("full_text_status")=="available" for x in results),"fulltext_downloaded_count":sum(x.get("full_text_status")=="available" for x in results),"fulltext_l1_claim_count":len(claims),"fulltext_confirmed_conflict_count":confirmation["summary"]["fulltext_confirmed_conflict_count"],"copyright_safe":True,"non_oa_skipped_count":sum(x.get("reason") in {"not_in_pmc_oa_subset","no_oa_download_resource"} for x in results),"warnings":[] if extractor is not None else ["fulltext_l1_extractor_not_connected_in_run_case"]}
    _write_jsonl(artifacts/"l35_fulltext_retrieval_results.jsonl",results); _write_jsonl(artifacts/"l35_fulltext_l1_claims.jsonl",claims); _write_jsonl(artifacts/"l35_fulltext_conflict_confirmations.jsonl",confirmation["confirmations"])
    _write_json(artifacts/"l35_fulltext_retrieval_summary.json",summary); _write_json(artifacts/"l35_fulltext_l1_summary.json",summary); _write_json(artifacts/"l35_fulltext_conflict_confirmation_summary.json",{**summary,**confirmation["summary"]})
    _expose_summary(artifacts,summary)
    return summary
