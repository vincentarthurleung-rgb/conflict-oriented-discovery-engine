"""Offline v2.4-dev alpha1 event binding and default-deny search eligibility.

This is a new development contract. Frozen planner proposals, V1 receipts,
coverage, compiler and historical artifacts are never rewritten.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import re
from typing import Any

from code_engine.search.planner_authority_contract_split_v1 import validate_validated_plan
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from code_engine.search.query_compiler_v24_dev import DEFAULT_DEVELOPMENT_BUDGETS, QueryBudgetConfigDev
from code_engine.search.retrieval_intent_v1 import DIMENSION_ORDER, INTENT_ORDER

RECEIPT_VERSION = "SearchTermValidationReceiptV1_1"
EVENT_VERSION = "RelationEventFrameV1"
BINDING_VERSION = "RelationBindingAssessmentV1"
COVERAGE_VERSION = "RetrievalPlanCoverageV1_1"
ELIGIBILITY_VERSION = "SearchOnlyEligibilityV1"
VALIDATOR_VERSION = "SearchTermValidatorAlpha1"
COMPILER_VERSION = "DeterministicQueryCompilerV24DevAlpha1"
STATES = ("STRUCTURALLY_BOUND", "PARTIALLY_BOUND", "UNDERREPRESENTED", "NOT_APPLICABLE")
CLASSIFICATIONS = ("AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED")
USABLE = frozenset(CLASSIFICATIONS[:2])

RELATION_LEXICON = {
    "artifact_schema_version": "GenericRelationSearchLexiconV1",
    "rule_scope": "generic scientific relation families; never case IDs",
    "families": {
        "increase_activation": ["increase", "enhance", "promote", "induce", "activate", "upregulat", "elevat"],
        "decrease_suppression": ["decrease", "suppress", "inhibit", "reduc", "attenuat"],
        "sensitization_response": ["sensitiv", "sensitiz", "response", "resistan", "ic50"],
        "necessity_loss": ["necess", "required", "loss", "deplet", "knockdown", "delet", "deficien"],
        "rescue": ["rescu", "restor", "re-express", "reconstitut", "add-back", "revers"],
        "gain_activation": ["gain", "activat", "overexpress", "increase"],
        "secretion_release": ["secret", "releas", "extracellular"],
        "phosphorylation_activation": ["phospho", "phosphorylat", "activat"],
    },
    "full_phrase_required_for_relation_role": True,
}
ENDPOINT_LEXICON = {
    "artifact_schema_version": "GenericEndpointSearchLexiconV1",
    "families": {
        "secretion_release": ["secretion", "secreted", "release", "extracellular release"],
        "phosphorylation": ["phosphorylation", "phosphorylated", "phospho"],
        "drug_response": ["sensitivity", "sensitization", "response", "resistance", "ic50"],
        "dynamic_autophagic_flux": ["autophagic flux", "autophagy flux", "autophagic turnover", "dynamic autophagic degradation"],
        "nuclear_localization": ["nuclear accumulation", "nuclear localization", "nuclear translocation"],
    },
    "static_autophagy_marker_alone_is_flux": False,
    "polarity_required_for_therapy_response_relation": True,
}


class Alpha1BoundaryError(ValueError):
    """Raised for an alpha1 authority, relation or compilation violation."""


def normalize(value: str) -> str:
    value = str(value).casefold()
    for old, new in (("α", "alpha"), ("β", "beta"), ("γ", "gamma"), ("κ", "kappa")):
        value = value.replace(old, new)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def singular_tokens(value: str) -> str:
    tokens = normalize(value).split()
    return " ".join(x[:-1] if len(x)>4 and x.endswith("s") and not x.endswith("ss") else x for x in tokens)


def alternatives(value: Any) -> list[str]:
    if value is None: return []
    if isinstance(value, list):
        return [part for item in value for part in alternatives(item)]
    return [piece.strip() for piece in str(value).split(" / ") if piece.strip()]


def _anchors(target: dict[str, Any], dimension: str) -> list[str]:
    context=target.get("context_qualifier_dimensions") or {}
    fields={
        "subject": [target.get("subject"),target.get("canonical_subject"),target.get("subject_intervention")],
        "object_measurement_target": [target.get("object"),target.get("measurement_target")],
        "endpoint_property": [target.get("measurement_property_endpoint"),target.get("acceptable_endpoint_evidence")],
        "biological_unit": [context.get("biological_unit")],
        "therapy": [target.get("therapy"),context.get("therapy")],
        "disease": [context.get("disease_context"),context.get("disease")],
        "genotype": [context.get("genotype_context"),context.get("genotype")],
        "nested_treatment": [context.get("treatment"),context.get("treatment_context")],
    }
    return list(dict.fromkeys(part for value in fields.get(dimension,[]) for part in alternatives(value)))


def _has_therapy(target: dict[str, Any]) -> bool:
    return bool(_anchors(target, "therapy"))


def _has_anchor(text: str, anchors: list[str]) -> bool:
    phrase=" "+normalize(text)+" "
    for anchor in anchors:
        normalized=normalize(anchor)
        if normalized and " "+normalized+" " in phrase:
            return True
    return False


def _relation_semantics(text: str) -> bool:
    folded=normalize(text)
    return any(stem in folded for terms in RELATION_LEXICON["families"].values() for stem in terms)


def _relation_phrase_bound(term: str, target: dict[str, Any]) -> bool:
    if not (_has_anchor(term, _anchors(target, "subject")) and _relation_semantics(term)):
        return False
    value = normalize(term)
    if _has_therapy(target):
        response_words = ENDPOINT_LEXICON["families"]["drug_response"]
        action_words = ("inhib", "deplet", "knockdown", "loss", "re express", "rescu",
                        "restor", "overexpress", "function", "activity", "deficien")
        return (_has_anchor(term, _anchors(target, "therapy")) and
                any(word in value for word in response_words) and
                any(word in value for word in action_words))
    return _has_anchor(term, _anchors(target, "object_measurement_target"))


def _lexical_direction(phrase: str) -> str:
    if not phrase:
        return "UNRESOLVED"
    families = (
        (r"\b(?:increas\w*|enhanc\w*|promot\w*|elevat\w*|induc\w*)\b", "INCREASE"),
        (r"\b(?:decreas\w*|reduc\w*|suppress\w*|attenuat\w*)\b", "DECREASE"),
        (r"\b(?:rescu\w*|revers\w*|restor\w*)\b", "RESCUE_OR_RESTORATION"),
        (r"\b(?:sensitiz\w*|sensitiv\w*)\b", "SENSITIZATION"),
        (r"\b(?:resistan\w*|resistanc\w*)\b", "RESISTANCE"),
    )
    hits = [(match.start(), name) for pattern, name in families for match in re.finditer(pattern, normalize(phrase))]
    return max(hits)[1] if hits else "UNRESOLVED"


def _unsafe(term: str) -> bool:
    folded=term.casefold()
    return (not term.strip() or len(term)>240 or any(ord(c)<32 for c in term)
            or any(x in folded for x in ("http://","https://","<script","drop table"))
            or bool(re.search(r"\b(?:AND|OR|NOT)\b|\[[^]]+\]",term)))


def semantic_eligibility(term: str, dimension: str, target: dict[str, Any]) -> tuple[str,str]:
    """Return (state, generic rule ID); no negative evidence never grants use."""
    value=normalize(term)
    anchors=_anchors(target,dimension)
    if not value: return "DENIED","NO_LEXICAL_IDENTITY"
    # Component/subunit substitutions are not target aliases or generic
    # relation paraphrases. A separate explicit mechanistic authority is needed.
    if dimension in {"subject", "relation", "direction"} and any(
        re.search(r"\b" + stem + r"\w*\b", value)
        for stem in ("component", "subunit", "downstream", "upstream")
    ) and not any(stem in normalize(target.get("subject") or "") for stem in ("component", "subunit")):
        return "DENIED", "MECHANISTIC_PROXY_REQUIRES_EXPLICIT_AUTHORITY"
    if dimension in {"relation","direction"}:
        if _relation_phrase_bound(term,target):
            return "ELIGIBLE","RELATION_PARAPHRASE_FROM_FROZEN_LEXICON"
        return "DENIED","RELATION_EVENT_ROLES_NOT_EXPLICITLY_LINKED"
    if dimension in {"subject","object_measurement_target","therapy","disease","genotype","biological_unit"}:
        if any(singular_tokens(term)==singular_tokens(anchor) for anchor in anchors):
            return "ELIGIBLE",("BIOLOGICAL_UNIT_LEXICAL_VARIANT_WITH_GENERIC_AUTHORITY" if dimension=="biological_unit"
                               else "CONTEXT_LEXICAL_VARIANT_WITH_GENERIC_AUTHORITY" if dimension in {"disease","genotype"}
                               else "ORTHOGRAPHIC_OR_MORPHOLOGICAL_VARIANT")
        if dimension=="biological_unit":
            meaning=singular_tokens(target.get("primary_proposition_meaning") or "")
            if len(value.split())>=2 and " "+singular_tokens(term)+" " in " "+meaning+" ":
                return "ELIGIBLE","BIOLOGICAL_UNIT_LEXICAL_VARIANT_WITH_GENERIC_AUTHORITY"
        if dimension=="object_measurement_target" and _has_therapy(target):
            if _has_anchor(term,_anchors(target,"therapy")) and any(x in value for x in ENDPOINT_LEXICON["families"]["drug_response"]):
                return "ELIGIBLE","THERAPY_RESPONSE_PARAPHRASE_FROM_FROZEN_LEXICON"
        return "DENIED","NO_GENERIC_ENTITY_OR_CONTEXT_AUTHORITY"
    if dimension=="endpoint_property":
        if any(singular_tokens(term)==singular_tokens(anchor) for anchor in anchors):
            return "ELIGIBLE","ORTHOGRAPHIC_OR_MORPHOLOGICAL_VARIANT"
        prop=normalize(target.get("measurement_property_endpoint") or "")
        if "flux" in prop:
            if any(x in value for x in ENDPOINT_LEXICON["families"]["dynamic_autophagic_flux"]):
                return "ELIGIBLE","ENDPOINT_PARAPHRASE_FROM_FROZEN_LEXICON_DYNAMIC_FLUX"
            return "DENIED","STATIC_MARKER_NOT_DYNAMIC_FLUX"
        if "phosphorylat" in prop and any(x in value for x in ENDPOINT_LEXICON["families"]["phosphorylation"]):
            return "ELIGIBLE","ENDPOINT_PARAPHRASE_FROM_FROZEN_LEXICON"
        if "secret" in prop and any(x in value for x in ENDPOINT_LEXICON["families"]["secretion_release"]):
            return "ELIGIBLE","ENDPOINT_PARAPHRASE_FROM_FROZEN_LEXICON"
        if _has_therapy(target) and _has_anchor(term,_anchors(target,"therapy")) and any(x in value for x in ENDPOINT_LEXICON["families"]["drug_response"]):
            return "ELIGIBLE","THERAPY_RESPONSE_PARAPHRASE_FROM_FROZEN_LEXICON"
        if "nuclear" in prop and any(x in value for x in ENDPOINT_LEXICON["families"]["nuclear_localization"]):
            return "ELIGIBLE","ENDPOINT_PARAPHRASE_FROM_FROZEN_LEXICON"
        return "DENIED","NO_GENERIC_ENDPOINT_PARAPHRASE_AUTHORITY"
    if dimension=="nested_treatment":
        if any(singular_tokens(term)==singular_tokens(anchor) for anchor in anchors):
            return "ELIGIBLE","CONTEXT_LEXICAL_VARIANT_WITH_GENERIC_AUTHORITY"
        if _has_anchor(term,_anchors(target,"subject")) and _has_anchor(term,_anchors(target,"therapy")) and _relation_semantics(term):
            return "ELIGIBLE","THERAPY_COMBINATION_EVENT_CONTEXT"
        return "DENIED","NO_NESTED_TREATMENT_AUTHORITY"
    if dimension=="evidence_mode":
        return "DENIED","EVIDENCE_MODE_PHRASE_REQUIRES_EXPLICIT_AUTHORITY"
    return "DENIED","NO_GENERIC_SEMANTIC_ELIGIBILITY_RULE"


def alpha1_receipts(plan: dict[str,Any]) -> list[dict[str,Any]]:
    validate_validated_plan(plan)
    target=plan["canonical_proposition"]["target_payload"]
    results=[]
    for old in plan["term_validation_receipts"]:
        term=old["term"]; cls=old["deterministic_classification"]
        lexical="REJECTED" if _unsafe(term) else "PASS"
        if lexical=="REJECTED": new="REJECTED";eligibility="DENIED";rule="LEXICAL_SAFETY_REJECTION";ref=None
        elif cls=="AUTHORIZED_EQUIVALENT" and old["authority_reference"]:
            new="AUTHORIZED_EQUIVALENT";eligibility="AUTHORIZED";rule="IMMUTABLE_TARGET_EXACT_AUTHORITY";ref=old["authority_reference"]
        else:
            eligibility,rule=semantic_eligibility(term,old["concept_type"],target)
            new="SEARCH_ONLY_EXPANSION" if eligibility=="ELIGIBLE" else "UNRESOLVED"
            ref=None
        material={
            "artifact_schema_version":RECEIPT_VERSION,"term_id":old["term_id"],"term":term,
            "concept_id":old["concept_id"],"concept_type":old["concept_type"],
            "input_term_hash":old["input_term_hash"],"old_receipt_sha256":old["receipt_sha256"],
            "lexical_safety_state":lexical,"semantic_search_eligibility_state":eligibility,
            "final_authority_classification":new,"eligibility_rule_id":rule,
            "authority_reference":ref,"reason":rule.replace("_"," ").lower(),
            "validator_version":VALIDATOR_VERSION,"authority_state_hash":old["authority_state_hash"],
        }
        material["receipt_sha256"]=sha256_value(material)
        results.append(material)
    return results


def _selected_terms(concept:dict[str,Any],receipts:dict[str,dict[str,Any]],budget:QueryBudgetConfigDev):
    usable=[{**term,"receipt":receipts[term["term_id"]]} for term in concept["proposed_terms"]
            if receipts[term["term_id"]]["final_authority_classification"] in USABLE]
    search_only=sorted((t for t in usable if t["receipt"]["final_authority_classification"]=="SEARCH_ONLY_EXPANSION"),
                       key=lambda t:(normalize(t["term"]),t["term"].encode(),t["term_id"]))
    allowed={t["term_id"] for t in search_only[:budget.max_search_only_terms_per_concept]}
    chosen=[t for t in usable if t["receipt"]["final_authority_classification"]=="AUTHORIZED_EQUIVALENT" or t["term_id"] in allowed]
    by_norm={}
    for t in chosen:
        key=normalize(t["term"])
        old=by_norm.get(key)
        if old is None or (old["receipt"]["final_authority_classification"]=="SEARCH_ONLY_EXPANSION" and
                           t["receipt"]["final_authority_classification"]=="AUTHORIZED_EQUIVALENT"):
            by_norm[key]=t
    return [by_norm[k] for k in sorted(by_norm)]


def relation_event_and_binding(plan:dict[str,Any],receipts:list[dict[str,Any]],budget:QueryBudgetConfigDev=DEFAULT_DEVELOPMENT_BUDGETS):
    target=plan["canonical_proposition"]["target_payload"]
    byid={r["term_id"]:r for r in receipts}
    events=[];assessments=[];coverages=[]
    for intent in plan["planner_proposal_payload"]["retrieval_intents"]:
        concepts={c["concept_id"]:c for c in intent["search_concepts"]}
        applicable=set(intent["required_dimensions"]+intent["optional_dimensions"])
        for blueprint in intent["candidate_query_blueprints"]:
            chosen=[concepts[i] for i in blueprint["concept_ids"]]
            bydim={d:[c for c in chosen if c["concept_type"]==d] for d in DIMENSION_ORDER}
            executable={d:[t for c in bydim[d] for t in _selected_terms(c,byid,budget)] for d in DIMENSION_ORDER}
            def cid(d): return bydim[d][0]["concept_id"] if bydim[d] else None
            relation_terms=[t for d in ("relation","direction") for t in executable[d]]
            phrases=[t["term"] for t in relation_terms]
            event={
                "artifact_schema_version":EVENT_VERSION,"intent_id":intent["intent_id"],"blueprint_id":blueprint["blueprint_id"],
                "subject_concept_id":cid("subject"),"subject_role":"ACTOR_OR_INTERVENTION",
                "perturbation_or_action":target.get("subject_intervention") or target.get("subject"),
                "relation_family":target.get("relation_family"),"polarity_or_direction":phrases[0] if phrases else "UNRESOLVED_NONEXECUTABLE",
                "polarity_basis":"FIRST_EXECUTABLE_RELATION_OR_DIRECTION_PHRASE",
                "lexical_direction_operator":_lexical_direction(phrases[0]) if phrases else "UNRESOLVED",
                "canonical_target_direction":target.get("canonical_relation_family") or target.get("relation_family"),
                "relation_phrase_term_ids":[t["term_id"] for t in relation_terms],
                "measurement_target_concept_id":cid("object_measurement_target"),
                "endpoint_property":target.get("measurement_property_endpoint"),
                "response_role":"THERAPY_RESPONSE" if _has_therapy(target) else "RESPONSE_TARGET",
                "nested_treatment_context":cid("nested_treatment"),"therapy_context":cid("therapy"),
                "biological_unit_context":cid("biological_unit"),
                "evidence_mode_requirement":target.get("required_evidence_mode"),
                "semantic_roles":{
                    "ACTOR_OR_INTERVENTION":cid("subject"),"PERTURBATION_ACTION":cid("nested_treatment") or cid("subject"),
                    "RELATION_DIRECTION":cid("relation") or cid("direction"),
                    "RESPONSE_TARGET":cid("object_measurement_target"),"RESPONSE_PROPERTY":cid("endpoint_property"),
                    "THERAPY_RESPONSE":cid("therapy") if _has_therapy(target) else None,
                    "CONDITIONING_CONTEXT":cid("nested_treatment"),"BIOLOGICAL_UNIT_CONTEXT":cid("biological_unit"),
                },
            }
            subject=bool(executable["subject"])
            response=bool(executable["object_measurement_target"] or executable["endpoint_property"])
            direction=bool(executable["relation"] or executable["direction"])
            linked=any(_relation_phrase_bound(p,target) for p in phrases)
            therapy_ok=(not _has_therapy(target) or bool(executable["therapy"]) and
                        any(_has_anchor(p,_anchors(target,"therapy")) for p in phrases))
            nested_anchor=_anchors(target,"nested_treatment")
            nested_ok=(not nested_anchor or bool(executable["nested_treatment"]))
            dynamic_ok=("flux" not in normalize(target.get("measurement_property_endpoint") or "") or
                        any("flux" in normalize(t["term"]) or "autophagic turnover" in normalize(t["term"])
                            for t in executable["object_measurement_target"]+executable["endpoint_property"]))
            if not target.get("relation_family"):
                state="NOT_APPLICABLE"
            elif subject and response and direction and linked and therapy_ok and nested_ok and dynamic_ok:
                state="STRUCTURALLY_BOUND"
            elif subject and response and direction:
                state="PARTIALLY_BOUND"
            else: state="UNDERREPRESENTED"
            assessment={
                "artifact_schema_version":BINDING_VERSION,"intent_id":intent["intent_id"],"blueprint_id":blueprint["blueprint_id"],
                "state":state,"subject_side_searchable":subject,"response_side_searchable":response,
                "direction_searchable":direction,"explicit_cross_role_phrase":linked,
                "therapy_response_bound":therapy_ok,"nested_treatment_bound":nested_ok,"dynamic_endpoint_bound":dynamic_ok,
                "binding_phrase_candidates":phrases,
                "compiler_action":"COMPILE" if state in {"STRUCTURALLY_BOUND","NOT_APPLICABLE"} else "NON_EXECUTABLE_RELATION_UNDERREPRESENTED",
            }
            rows=[]
            for d in DIMENSION_ORDER:
                relevant=d in applicable or (d=="relation" and bool(target.get("relation_family")))
                terms=executable[d]
                if not relevant: coverage="NOT_APPLICABLE";source=[];ids=[]
                elif terms: coverage="REPRESENTED";source=[c["concept_id"] for c in bydim[d]];ids=[t["term_id"] for t in terms]
                elif bydim[d]: coverage="UNDERREPRESENTED";source=[c["concept_id"] for c in bydim[d]];ids=[]
                else: coverage="OMITTED";source=[];ids=[]
                if d=="relation" and relevant:
                    if state=="STRUCTURALLY_BOUND":
                        coverage="REPRESENTED"
                        source=list(dict.fromkeys(source+[c["concept_id"] for c in bydim["direction"]]))
                        ids=list(dict.fromkeys(ids+[t["term_id"] for t in executable["direction"]]))
                    else:
                        coverage="UNDERREPRESENTED"
                rows.append({"dimension":d,"coverage_state":coverage,"source_concept_ids":source,"query_term_ids":ids,
                             "rationale":"alpha1 deterministic eligible terms and event binding"})
            coverages.append({"artifact_schema_version":COVERAGE_VERSION,"intent_id":intent["intent_id"],
                              "blueprint_id":blueprint["blueprint_id"],"dimension_coverage":rows,
                              "relation_binding_state":state})
            events.append(event);assessments.append(assessment)
    return events,assessments,coverages


def _qualified(term:str)->str:
    escaped=term.replace("\\","\\\\").replace('"','\\"')
    return f'"{escaped}"[Title/Abstract]'


def compile_alpha1(plan:dict[str,Any],receipts:list[dict[str,Any]],assessments:list[dict[str,Any]],coverages:list[dict[str,Any]],
                   budget:QueryBudgetConfigDev=DEFAULT_DEVELOPMENT_BUDGETS)->list[dict[str,Any]]:
    validate_validated_plan(plan)
    if [r["term_id"] for r in receipts]!=[r["term_id"] for r in alpha1_receipts(plan)]:
        raise Alpha1BoundaryError("alpha1 receipt identity mismatch")
    if sha256_value(receipts)!=sha256_value(alpha1_receipts(plan)):
        raise Alpha1BoundaryError("alpha1 receipts not reproducible")
    ev,expected,expected_cov=relation_event_and_binding(plan,receipts,budget)
    if sha256_value(expected)!=sha256_value(assessments) or sha256_value(expected_cov)!=sha256_value(coverages):
        raise Alpha1BoundaryError("event binding/coverage not reproducible")
    byid={r["term_id"]:r for r in receipts}
    bind={r["blueprint_id"]:r for r in assessments}; cov={r["blueprint_id"]:r for r in coverages}
    pos={name:i for i,name in enumerate(INTENT_ORDER)}; dpos={name:i for i,name in enumerate(DIMENSION_ORDER)}
    applicable=[i for i in plan["planner_proposal_payload"]["retrieval_intents"] if i["applicability"]=="APPLICABLE"]
    if len(applicable)>budget.max_intents_per_target: raise Alpha1BoundaryError("intent budget exceeded")
    rows=[]
    for intent in sorted(applicable,key=lambda i:(pos[i["intent_type"]],i["intent_id"])):
        if len(intent["candidate_query_blueprints"])>budget.max_blueprints_per_intent: raise Alpha1BoundaryError("blueprint budget exceeded")
        concepts={c["concept_id"]:c for c in intent["search_concepts"]}
        for blueprint in sorted(intent["candidate_query_blueprints"],key=lambda b:b["blueprint_id"]):
            bid=blueprint["blueprint_id"]
            if bind[bid]["compiler_action"]!="COMPILE": continue
            groups=[]
            for cid in sorted(blueprint["concept_ids"],key=lambda c:(dpos[concepts[c]["concept_type"]],c)):
                concept=concepts[cid];terms=_selected_terms(concept,byid,budget)
                if not terms: continue
                fragments=[_qualified(t["term"]) for t in terms]
                groups.append({"concept_id":cid,"concept_type":concept["concept_type"],
                               "terms":[{"term_id":t["term_id"],"term":t["term"],
                                         "classification":t["receipt"]["final_authority_classification"],
                                         "eligibility_rule_id":t["receipt"]["eligibility_rule_id"],
                                         "receipt_sha256":t["receipt"]["receipt_sha256"]} for t in terms],
                               "query_fragment":fragments[0] if len(fragments)==1 else "("+" OR ".join(fragments)+")"})
            if not groups: raise Alpha1BoundaryError("bound blueprint has no executable terms")
            text=" AND ".join(g["query_fragment"] for g in groups)
            material={"target_sha256":plan["canonical_proposition"]["target_sha256"],"query_string":text,
                      "groups":groups,"intent_id":intent["intent_id"],"blueprint_id":bid,
                      "receipt_corpus_sha256":sha256_value(receipts),"compiler_version":COMPILER_VERSION,
                      "budget":budget.to_dict()}
            qhash=sha256_value(material)
            rows.append({"artifact_schema_version":"CompiledPropositionAwareQueryV24DevAlpha1",
                         "query_id":"v24a1q:"+qhash,"query_sha256":qhash,"query_text_sha256":hashlib.sha256(text.encode()).hexdigest(),
                         "query_string":text,"target_id":plan["target_id"],"intent_id":intent["intent_id"],
                         "intent_type":intent["intent_type"],"blueprint_id":bid,"ordered_term_groups":groups,
                         "relation_binding_state":bind[bid]["state"],"dimension_coverage":cov[bid]["dimension_coverage"],
                         "execution_status":"NOT_EXECUTED_DEVELOPMENT_ALPHA1"})
    if len(rows)>budget.max_queries_per_target: raise Alpha1BoundaryError("query budget exceeded")
    return rows


__all__=["Alpha1BoundaryError","BINDING_VERSION","CLASSIFICATIONS","COMPILER_VERSION","COVERAGE_VERSION",
         "ELIGIBILITY_VERSION","ENDPOINT_LEXICON","EVENT_VERSION","RECEIPT_VERSION","RELATION_LEXICON",
         "STATES","alpha1_receipts","compile_alpha1","normalize","relation_event_and_binding","semantic_eligibility"]
