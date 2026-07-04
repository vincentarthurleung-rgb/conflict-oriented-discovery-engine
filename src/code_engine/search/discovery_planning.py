"""Direction-neutral retrieval planning for conflict-enriched discovery cases."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from code_engine.query.search_planner import LiteratureSearchPlan, LiteratureSearchQuery
from code_engine.schemas.triples import build_seed_triple
from code_engine.temporal.paper_year_filter import paper_year_filter_from_dict, pubmed_date_clause

NEUTRAL_RELATIONS={"associated_with","involved_in","modulates","has_context_dependent_role_in","participates_in","affects"}
DIRECTIONAL_PATTERN=re.compile(r"\b(promot\w*|inhibit\w*|suppress\w*|induc\w*|exhibit\w*|caus\w*|protect\w*|worsen\w*|activat\w*|repress\w*)\b",re.I)
CONTRAST_PATTERN=re.compile(r"\b(but|however|whereas|while|although|on the other hand|context[- ]dependent|dual role|opposite effects)\b",re.I)


def _unique(values): return list(dict.fromkeys(str(x).strip() for x in values if str(x).strip()))
def _entity_name(seed,role):
    value=seed.get(role) or {}; return str(value.get("name") or "") if isinstance(value,dict) else str(value)


def _neutral_context_terms(semantic:dict[str,Any],query:str)->list[str]:
    intent=semantic.get("research_intent") or {}
    values=[]
    for key in ("disease_or_condition","comparison_entities","mechanism_entities","outcome_entities","context_terms"):
        values.extend(intent.get(key) or [])
    # Clause payloads preserve contrast context diagnostically, while acquisition queries filter directional words.
    clauses=[x.strip(" ,.;:") for x in CONTRAST_PATTERN.split(query) if x and not CONTRAST_PATTERN.fullmatch(x)]
    values.extend(clauses)
    if CONTRAST_PATTERN.search(query): values.append("context-dependent role")
    return _unique(values)


def _query_safe_terms(terms:list[str],subject:str,object_:str)->list[str]:
    result=[]
    for term in terms:
        clean=DIRECTIONAL_PATTERN.sub("",term)
        clean=re.sub(r"\b(?:has|role|roles|effects?)\b","",clean,flags=re.I)
        clean=" ".join(clean.split(" ,.;:-"))
        if clean and clean.casefold() not in {subject.casefold(),object_.casefold()} and len(clean)>2: result.append(clean)
    return _unique(result)


def assess_discovery_queries(queries:list[LiteratureSearchQuery], *, intended_context_terms:list[str]|None=None,
                             directional_terms_observed:list[str]|None=None)->dict[str,Any]:
    groups=_unique([q.query_group for q in queries]); directional_queries=sum(bool(DIRECTIONAL_PATTERN.search(q.query_string)) for q in queries)
    fraction=directional_queries/len(queries) if queries else 1.0
    risk="high" if len(queries)<=1 or (queries and directional_queries==len(queries)) else "medium" if fraction>0 else "low"
    return {"discovery_planning_mode":"neutral_discovery","discovery_query_balance_valid":len(queries)>=3 and len(groups)>=2 and risk!="high",
        "discovery_query_count":len(queries),"discovery_query_groups":groups,"directional_query_fraction":round(fraction,4),
        "one_sided_retrieval_risk":risk,"intended_context_terms":intended_context_terms or [],
        "directional_terms_observed_in_user_query":directional_terms_observed or [],
        "directional_terms_not_used_as_fixed_search_sides":directional_queries==0}


def build_neutral_discovery_plan(plan:LiteratureSearchPlan, *, query:str, semantic_intake:dict[str,Any],
                                 semantic_search_intent:dict[str,Any], max_results:int=60)->tuple[LiteratureSearchPlan,dict[str,Any],dict[str,Any]]:
    intent=semantic_intake.get("research_intent") or {}; original=plan.seed_triple or {}
    subject=(intent.get("primary_entities") or [_entity_name(original,"subject")])[0]
    diseases=list(intent.get("disease_or_condition") or [])
    broad_object=diseases[0] if diseases else _entity_name(original,"object") or "biological response"
    contexts=_neutral_context_terms(semantic_intake,query); safe_contexts=_query_safe_terms(contexts,subject,broad_object)
    relation="has_context_dependent_role_in" if CONTRAST_PATTERN.search(query) else "involved_in"
    original_subject=original.get("subject") if isinstance(original.get("subject"),dict) else {}
    original_object=original.get("object") if isinstance(original.get("object"),dict) else {}
    neutral_seed=build_seed_triple(query,domain=plan.domain_id,subject=subject,relation=relation,obj=broad_object,
        relation_family=relation,context_terms=contexts,source=str(original.get("source") or "semantic_intake"),
        confidence=max(float(original.get("confidence") or 0.0),float(plan.semantic_confidence or 0.0)),
        human_review_required=bool(original.get("human_review_required")),intake_mode=str(original.get("intake_mode") or "llm_semantic"),
        subject_type=str(original_subject.get("type") or "unknown"),object_type=str(original_object.get("type") or "unknown")).model_dump(mode="json")
    neutral_seed["relation"]["directional"]=False
    date_clause=pubmed_date_clause(paper_year_filter_from_dict(plan.paper_year_filter))
    coverage=" ".join([subject,*safe_contexts[:2]])
    if broad_object.casefold() not in coverage.casefold(): coverage=f"{coverage} {broad_object}"
    candidates=[("entity_pair_core",f"{subject} {broad_object} biology"),
                ("mechanism_context",f"{subject} molecular mechanism {broad_object}"),
                ("context_coverage",coverage),
                ("optional_conflict_hint",f"{subject} context dependent role {broad_object}")]
    queries=[]
    for group,text in candidates:
        text=" ".join(text.split())
        if DIRECTIONAL_PATTERN.search(text): continue
        final=f"({text}) AND {date_clause}" if date_clause else text
        queries.append(LiteratureSearchQuery(query_id=hashlib.sha256(f"pubmed|{final}".encode()).hexdigest()[:16],
            query_string=final,source="pubmed",purpose=group,query_group=group,priority=1,max_results=max_results,
            expected_domain=plan.domain_id,expected_prompt_profile=plan.prompt_profile_id,
            year_from=(plan.paper_year_filter or {}).get("paper_year_from"),year_to=(plan.paper_year_filter or {}).get("paper_year_to"),
            paper_year_filter_enabled=bool((plan.paper_year_filter or {}).get("enabled")),
            paper_year_from=(plan.paper_year_filter or {}).get("paper_year_from"),paper_year_to=(plan.paper_year_filter or {}).get("paper_year_to"),
            temporal_role=(plan.paper_year_filter or {}).get("temporal_role","discovery"),year_filter_applied_to_query=bool(date_clause),
            search_intent_mode="neutral_discovery",search_intent_confidence=plan.semantic_confidence,
            allowed_for_l1_acquisition=True,passed_query_guard=True,seed_subject_required=True,seed_object_required=False,
            passed_context_guard=True,context_guard_reason="neutral_discovery_context_coverage",query_scope="neutral_discovery"))
    plan.seed_triple=neutral_seed; plan.pubmed_queries=queries; plan.primary_queries=[]; plan.secondary_queries=[]
    plan.mechanism_queries=[]; plan.comparison_queries=[]; plan.clinical_queries=[]; plan.pmc_queries=[]
    plan.query_generation_mode="neutral_discovery"; plan.query_groups=[{"group":g,"stage":"abstract_retrieval","source":"pubmed",
        "queries":[q.model_dump(mode="json") for q in queries if q.query_group==g]} for g in _unique([q.query_group for q in queries])]
    directional=sorted(set(x.casefold() for x in DIRECTIONAL_PATTERN.findall(query)))
    groups=_unique([q.query_group for q in queries])
    quality=assess_discovery_queries(queries,intended_context_terms=contexts,directional_terms_observed=directional)
    search_intent={**semantic_search_intent,"seed_triple":neutral_seed,"neutral_seed_triple":neutral_seed,
        "directional_terms_observed":directional,"context_terms":contexts,"query_groups":{
            group:[{"query":q.query_string,"purpose":group,"allowed_for_l1_acquisition":True,
                    "must_include_subject":True,"must_include_object":False} for q in queries if q.query_group==group] for group in groups},
        **quality}
    return plan,search_intent,quality


__all__=["NEUTRAL_RELATIONS","DIRECTIONAL_PATTERN","assess_discovery_queries","build_neutral_discovery_plan"]
