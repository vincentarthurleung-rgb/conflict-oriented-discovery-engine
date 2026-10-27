"""Bounded source-evidence routing hints, independent of scientific authority.

Reuse the six domain profiles and their instructions. Legacy claims templates
cannot be sent to V3: their JSON contract differs. Source windows may contain
multiple designs; no paper-wide label is imposed on individual observations.
"""
import hashlib
import json
import re
from pathlib import Path

from code_engine.domain.models import default_domain_profiles
from code_engine.domain.prompt_registry import DOMAIN_INSTRUCTIONS, default_prompt_registry
from code_engine.domain.router import default_domain_router
from code_engine.fulltext.evidence_anchors import generate_evidence_anchors

VERSION = "source_evidence_prompt_routing_v1"
V3_PROFILE = "domain_design_experimental_v3_v1"
LINKAGE_PROFILE = "domain_design_linkage_candidate_v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def implementation_identity():
    files = [Path(__file__), Path(__file__).with_name("models.py"),
             Path(__file__).with_name("prompt_registry.py")]
    return digest({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


# Narrow lexical design cues, never biological identity equivalence. Every hit
# retains the entire original source anchor and its exact coordinates/hash.
DESIGN_RULES = {
    "in_vitro": r"\bin[ -]vitro\b|\bcell culture conditions\b|\bcells?\b[^.!?]{0,110}\b(?:incubated|cultured|transfected|maintained|grown|exposed)\b",
    "in_vivo": r"\bin[ -]vivo\b|\b(?:mice|mouse|rats?|animals?)\b[^.!?]{0,160}\b(?:conditional|deletion|treated|injected|injection|subjected|ablation|xenograft)\b|\b(?:injected|treated|generated)\b[^.!?]{0,100}\b(?:mice|rats?)\b",
    "observational_clinical": r"\b(?:retrospective|observational)\b[^.!?]{0,100}\b(?:cohort|patients?|study)\b|\barchival\b[^.!?]{0,160}\bpatients?\b|\bpositive\b[^.!?]{0,90}\bnegative\b[^.!?]{0,80}\bpatients?\b|\bpatients?\b[^.!?]{0,80}\bpositive\b[^.!?]{0,90}\bnegative\b",
    "interventional_clinical": r"\bpatients?\b[^.!?]{0,90}\b(?:randomly assigned|randomized|randomised)\b|\b(?:randomized|randomised)\b[^.!?]{0,100}\b(?:patients?|clinical trial)\b|\binterventional clinical trial\b",
    "omics": r"\b(?:RNA[ -]seq|RNA sequencing|single[ -]cell RNA|whole[ -]genome sequencing|proteomics|transcriptomics|multiomics|multiomic|metabolomics)\b",
    "computational": r"\b(?:in silico|computational (?:analysis|model|simulation)|bioinformatics analys(?:is|es)|molecular dynamics|molecular docking|mathematical model)\b",
}
GUIDANCE = {
    "in_vitro": "Keep cultured-cell exposures, controls and readouts within their own experiment; do not import animal or patient context.",
    "in_vivo": "Keep animal genotype, allocation, shared injury context, tissue and sampling time explicit; deletion effects do not prove intracellular mediation.",
    "observational_clinical": "Preserve biomarker strata and survival/event endpoints. No assigned treatment is implied; associations and nonsignificant differences are not causal effects or equivalence.",
    "interventional_clinical": "Retain only source-reported treatment assignment, comparator and outcome; do not infer randomization, blinding or mediation beyond the evidence.",
    "omics": "Keep assay, sampled biological unit and molecular endpoint explicit; transcript, protein, accessibility and pathway inference are distinct.",
    "computational": "Keep predictions, simulations and computational endpoints distinct from experimentally observed outcomes.",
    "unknown": "Design is unresolved. Preserve source wording and missing information; do not force an experiment type.",
}


def design_from_spans(spans, *, scope):
    hits = []; uncertain = []
    for s in spans:
        text = s["text"]
        if hashlib.sha256(text.encode()).hexdigest() != s["text_hash"]:
            raise ValueError("routing_anchor_hash_mismatch")
        if s.get("source_role") not in {"current", "methods", "setup"}:
            continue
        for kind, pattern in DESIGN_RULES.items():
            match = re.search(pattern, text, re.I)
            if not match:
                continue
            if re.search(r"\b(?:did not|not performed|planned|proposed|previously|future|would|might)\b|\bno\s+(?:in[ -]vivo|in[ -]vitro|clinical trial)|\b(?:were|was)\s+not\b[^.!?]{0,35}\b(?:randomized|randomised|cultured|injected|performed|assigned)\b", text, re.I):
                uncertain.append({"design": kind, "anchor_id": s.get("anchor_id"), "reason": "negated_hypothetical_or_prior_work_context"})
                continue
            hits.append({"design": kind, "rule_id": VERSION + ":" + kind,
                         "matched_text": match.group(), "match_start_in_anchor": match.start(),
                         "match_end_in_anchor": match.end(), "evidence": dict(s)})
    designs = sorted({h["design"] for h in hits}) or ["unknown"]
    return {"scope": scope, "designs": designs, "mixed_design": len(designs) > 1,
            "status": "source_cue_candidates" if hits else "unknown",
            "evidence_hits": hits, "uncertain_cues": uncertain,
            "limitations": ["Bounded deterministic cues, not a comprehensive semantic classifier",
                            "Co-located cues do not bind methods or prove a shared experiment",
                            "Modalities (omics/computational) may coexist with biological systems"],
            "scientific_authorization": False}


def block_design(block, *, scope="source_window"):
    title = str((block.get("section") or {}).get("section_title", ""))
    spans = []
    if not any(x in title.casefold() for x in ("introduction", "discussion", "abstract")):
        spans = [x.as_dict() for x in generate_evidence_anchors(
            block_id=block["block_id"], source_document_id=str((block.get("paper_metadata") or {}).get("pmcid", "source")),
            block_text=block["text"], section=title)]
    result = design_from_spans(spans, scope=scope)
    result["block_sha256"] = hashlib.sha256(block["text"].encode()).hexdigest()
    return result


def paper_design(article):
    from code_engine.fulltext.source_windows import extraction_block
    spans = []
    for i, sec in enumerate(article.get("sections", [])):
        title = sec.get("section_title", "")
        if any(x in title.casefold() for x in ("introduction", "discussion", "abstract")):
            continue
        window = {"window_id": sec.get("section_id", str(i)), "text": sec["text"], "section_title": title}
        block = extraction_block(window, article.get("pmcid", "source"), article.get("pmid", ""))
        spans.extend(x.as_dict() for x in generate_evidence_anchors(block_id=block["block_id"],
                     source_document_id=article.get("pmcid", "source"), block_text=block["text"], section=title))
    result = design_from_spans(spans, scope="paper_design_inventory_not_experiment_assignment")
    result.update(article_sha256=digest(article), article_type_raw=article.get("article_type_raw"),
                  paper_domain_semantic_classification="not_established_by_design_inventory")
    return result


def routing_decision(design, *, question_domain=None, input_hashes=None):
    router = default_domain_router()
    question = router.resolve(question_domain) if question_domain else None
    known = question is not None
    question = question or router.get_or_default("general_biomedical")
    selected = question
    biological = set(design["designs"]) - {"omics", "computational", "unknown"}
    basis = "question_domain_context_only" if known else "general_fallback_no_semantic_intake"
    # Clinical stratification/assignment are explicit source design cues; no gene
    # or disease name can trigger this specialization. Mixed systems stay mixed.
    if biological and biological <= {"observational_clinical", "interventional_clinical"}:
        selected = router.get_or_default("clinical_outcome")
        basis = "source_supported_clinical_design_candidate"
    legacy = default_prompt_registry().get_profile(selected.prompt_profile_id)
    return {"routing_version": VERSION, "question_domain": question.domain_id,
            "question_domain_state": "provided_intake_profile" if known else "general_fallback",
            "selected_domain": selected.domain_id, "selection_basis": basis,
            "legacy_instruction_profile": legacy.profile_id, "legacy_instruction_version": legacy.version,
            "legacy_schema_compatible_with_V3": False, "study_design": design,
            "input_hashes": input_hashes or {}, "routing_implementation_sha256": implementation_identity(),
            "scientific_authorization": False,
            "semantics_normalization_profile": "generic_experimental"}


def guidance(decision):
    kinds = decision["study_design"]["designs"]
    return ("\nNON_AUTHORITATIVE_ROUTING_GUIDANCE " + VERSION + "\nDomain context: " +
            decision["selected_domain"] + "; source design hints: " + ", ".join(kinds) + ".\n" +
            DOMAIN_INSTRUCTIONS[decision["selected_domain"]] + "\n" +
            " ".join(GUIDANCE[k] for k in kinds) +
            "\nThese are routing hints, not evidence, method linkage or causal authority. "
            "Split distinct experiments and retain unknowns; the original source-anchor and output-schema rules prevail.")


def prepare_v3_prompt(article, block, *, question_domain=None):
    from code_engine.fulltext.fulltext_l1_v2 import build_prompt, PROMPT_VERSION, SCHEMA_VERSION, schema_hash
    from code_engine.schemas.fulltext_observation_draft import DRAFT_SCHEMA_VERSION
    decision = routing_decision(block_design(block), question_domain=question_domain,
                               input_hashes={"article": digest(article), "block": digest(block)})
    text = build_prompt({"pmcid": article.get("pmcid"), "pmid": article.get("pmid")}, block) + guidance(decision)
    decision.update(prompt_profile=V3_PROFILE, prompt_version="1", base_prompt_version=PROMPT_VERSION,
                    schema_version=DRAFT_SCHEMA_VERSION, formal_schema_version=SCHEMA_VERSION,
                    schema_sha256=schema_hash(), compiled_prompt_sha256=hashlib.sha256(text.encode()).hexdigest())
    return text, decision


def routed_v3_preflight(article, block, *, question_domain=None, budget=None):
    from code_engine.fulltext.fulltext_l1_v2 import token_budget_preflight, FulltextTokenBudget, estimate_tokens
    budget = budget or FulltextTokenBudget()
    check = token_budget_preflight(article, block, budget)
    _, decision = prepare_v3_prompt(article, block, question_domain=question_domain)
    overhead = estimate_tokens(guidance(decision))
    check.update(routing_profile=V3_PROFILE, routing_overhead_token_estimate=overhead,
                 input_token_estimate=check["input_token_estimate"] + overhead,
                 total_context_budget=check["total_context_budget"] + overhead)
    if check["input_token_estimate"] > budget.safe_input_tokens:
        check["preflight_reasons"] = sorted(set([*check["preflight_reasons"], "routed_safe_input_budget_exceeded"]))
        check["preflight_decision"] = "split_before_provider_call"
    if check["total_context_budget"] > budget.model_context_limit:
        check["preflight_reasons"].append("routed_context_budget_exceeded")
        check["preflight_decision"] = "reject_invalid_configuration"
    return check


def prepare_linkage_prompt(packet, base_prompt, *, question_domain=None):
    design = design_from_spans(packet["evidence_spans"], scope="source_bound_native_observation")
    decision = routing_decision(design, question_domain=question_domain, input_hashes={"packet": digest(packet)})
    text = base_prompt + guidance(decision)
    from code_engine.extraction_assets.experimental_core.linkage_candidates import LinkProposalResponse, PROMPT_VERSION
    decision.update(prompt_profile=LINKAGE_PROFILE, prompt_version="1", base_prompt_version=PROMPT_VERSION,
                    schema_version="source_grounded_linkage_proposals_v1",
                    schema_sha256=digest(LinkProposalResponse.model_json_schema()),
                    compiled_prompt_sha256=hashlib.sha256(text.encode()).hexdigest())
    return text, decision
