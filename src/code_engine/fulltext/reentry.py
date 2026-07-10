"""Replay existing fulltext L1 claims into downstream evidence artifacts."""
from __future__ import annotations

import json
import re
import hashlib
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl, iter_jsonl
from code_engine.fulltext.discovery_escalation import finalize_discovery_escalation, prepare_discovery_escalation
from code_engine.reporting.full_abstract_pipeline import build_l4_context_mining, build_l5_context_attribution, build_l6_mechanism_graph
from code_engine.workflow.steps import _normalize_progressive_records


POSITIVE_RELATION_TERMS = {
    "activate", "activates", "activation", "induce", "induced", "induces", "promote", "promotes",
    "enhance", "enhances", "increase", "increases", "increased", "sustain", "sustains",
    "empower", "empowers", "stabilize", "stabilizes", "upregulate", "upregulates", "up-regulate",
    "up-regulates", "lead", "leads", "drive", "drives", "rescue", "rescues", "restore", "restores",
}
NEGATIVE_RELATION_TERMS = {
    "inhibit", "inhibits", "inhibition", "suppress", "suppresses", "suppression", "repress",
    "represses", "reduce", "reduces", "decrease", "decreases", "decreased", "block", "blocks",
    "downregulate", "downregulates", "down-regulate", "down-regulates", "abolish", "abolishes",
    "abrogate", "abrogates", "abrogated", "degrade", "degrades",
}
EXPRESSION_TERMS = {
    "is upregulated", "is up regulated", "is downregulated", "is down regulated", "upregulated in",
    "up regulated in", "up-regulated", "down-regulated", "highly expressed", "overexpressed in",
    "reduced expression", "expression is increased", "expression is decreased", "protein level",
    "mRNA level", "levels in",
}
NEGATIVE_PERTURBATION_TERMS = {
    "knockdown", "knock-down", "silencing", "silenced", "depletion", "depleted", "loss of",
    "inhibition", "inhibition of", "inhibiting", "inhibited", "downregulation", "down-regulation",
    "deficiency", "deletion", "removal", "absence", "knockout", "ablation", "suppression of",
    "inhibitor",
}
POSITIVE_PERTURBATION_TERMS = {
    "overexpression", "overexpressed", "ectopic expression", "activation of", "activated",
    "agonist", "forced expression", "restoration", "supplementation",
}
NO_EFFECT_TERMS = ("does not", "did not", "no effect", "no difference", "failed to", "minimum impact", "minimal impact")
ASSOCIATION_TERMS = ("associated", "correlat", "linked", "marker")
COMPARISON_TERMS = ("survival", "prognosis", "overall survival", "reduced os", "higher than", "lower than", "compared with")
DEPENDENCY_TERMS = ("requires", "is required for", "required for", "depends on", "crucial for", "essential for")
TARGET_OF_TERMS = ("target of", "downstream target of", "transcriptional target of", "regulated target of")
RESCUE_TERMS = ("rescues", "rescue", "restores", "restoration", "reverses", "reversed")
ONE_HOP_STATE_TERMS = (
    "activation of", "inhibition of", "nuclear translocation of", "translocation of",
    "accumulation of", "degradation of", "phosphorylation of", "activity of",
    "target gene expression downstream of",
)
ACCEPTED_PREDICATE_ANCHOR_STATUSES = {
    "seed_predicate_found",
    "seed_predicate_anchor_found",
    "canonical_seed_predicate_found",
    "anchored",
    "accepted",
}


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        return list(iter_jsonl(path))
    except (OSError, json.JSONDecodeError, ValueError):
        return []


def _json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def _source_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("evidence_source") or row.get("source_scope") or "abstract"),
            str(row.get("observation_id") or row.get("triple_id") or row.get("claim_id") or ""))


def _entity_norm(observation: dict[str, Any] | None, side: str) -> dict[str, Any]:
    if not observation:
        return {}
    nested = observation.get("normalization") if isinstance(observation.get("normalization"), dict) else {}
    value = nested.get(side) if isinstance(nested.get(side), dict) else {}
    return value


def _side_normalization_status(observation: dict[str, Any] | None, side: str) -> str:
    return str((observation or {}).get(f"{side}_normalization_status") or _entity_norm(observation, side).get("normalization_status") or "")


def _side_requires_manual_review(observation: dict[str, Any] | None, side: str) -> bool | None:
    if not observation:
        return None
    key = f"{side}_requires_manual_review"
    if key in observation:
        return bool(observation.get(key))
    nested = _entity_norm(observation, side)
    if "requires_manual_review" in nested:
        return bool(nested.get("requires_manual_review"))
    return None


def _norm(value: Any) -> str:
    text = str(value or "").casefold()
    for symbol, name in (("α", "alpha"), ("β", "beta"), ("γ", "gamma"), ("δ", "delta"), ("κ", "kappa")):
        text = text.replace(symbol, name)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _contains(text: str, term: str) -> bool:
    needle = _norm(term)
    return bool(needle and re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", text))


def _name(value: Any) -> str:
    return str(value.get("name") or "") if isinstance(value, dict) else str(value or "")


def _active_seed(artifacts: Path) -> dict[str, Any]:
    replay = _json(artifacts / "search_plan_replay.json", {})
    intent = _json(artifacts / "semantic_search_intent.json", {})
    plan = _json(artifacts / "search_plan.json", {})
    if replay.get("enabled") and intent.get("seed_triple"):
        return intent["seed_triple"]
    if plan.get("seed_triple"):
        return plan["seed_triple"]
    intake = _json(artifacts / "intake.json", {})
    return intake.get("unified_seed_triple") or {}


def _seed_terms(seed: dict[str, Any]) -> dict[str, list[str]]:
    context = seed.get("context") or {}
    subject_terms = [x for x in [_name(seed.get("subject"))] if x]
    object_terms = [x for x in [_name(seed.get("object")), *list(context.get("terms") or context.get("context_terms") or [])] if x]
    return {
        "subject": subject_terms,
        "object": object_terms,
        "endpoints": [*subject_terms, *object_terms],
    }


def _relation_class_and_polarity(relation: str, evidence: str = "") -> tuple[str, str]:
    relation_norm = _norm(relation)
    evidence_norm = _norm(evidence)
    relation_words = set(relation_norm.split())
    text = f"{relation_norm} {evidence_norm}"
    if any(term in text for term in NO_EFFECT_TERMS):
        return "no_effect", "unknown"
    if any(_contains(relation_norm, term) for term in EXPRESSION_TERMS):
        return "expression_state", "not_applicable"
    if any(term in text for term in COMPARISON_TERMS):
        return "comparison", "unknown"
    if any(term in relation_norm for term in ASSOCIATION_TERMS):
        return "association", "unknown"
    if any(_contains(relation_norm, term) for term in TARGET_OF_TERMS):
        return "target_of", "unknown"
    if any(_contains(relation_norm, term) for term in DEPENDENCY_TERMS):
        return "dependency", "unknown"
    if any(_contains(relation_norm, term) for term in RESCUE_TERMS):
        return "rescue", "positive"
    if relation_words & NEGATIVE_RELATION_TERMS or any(_contains(relation_norm, term) for term in NEGATIVE_RELATION_TERMS):
        return "causal_regulation", "negative"
    if relation_words & POSITIVE_RELATION_TERMS or any(_contains(relation_norm, term) for term in POSITIVE_RELATION_TERMS):
        return "causal_regulation", "positive"
    if "mediate" in relation_norm:
        return "causal_regulation", "unknown"
    return "unknown", "unknown"


def _subject_perturbation_polarity(subject: str, relation: str, evidence: str) -> str:
    text = _norm(subject)
    if any(_contains(text, term) for term in NEGATIVE_PERTURBATION_TERMS):
        return "negative"
    if any(_contains(text, term) for term in POSITIVE_PERTURBATION_TERMS):
        return "positive"
    return "neutral"


def _effective_entity_polarity(relation_polarity: str, perturbation_polarity: str, raw_sign: str) -> tuple[str, str]:
    raw = str(raw_sign or "").casefold()
    if relation_polarity not in {"positive", "negative"}:
        return ("unknown", "not_applicable") if relation_polarity == "not_applicable" else ("unknown", "ambiguous")
    if perturbation_polarity == "negative":
        return ("negative" if relation_polarity == "positive" else "positive"), "resolved"
    if perturbation_polarity == "positive":
        return relation_polarity, "resolved"
    if perturbation_polarity == "neutral":
        if raw in {"positive", "negative"} and raw != relation_polarity:
            return relation_polarity, "mismatch"
        return relation_polarity, "resolved"
    return relation_polarity, "ambiguous"


def _endpoint_seed_match(text: str, seed_terms: list[str]) -> bool:
    return any(_contains(text, term) for term in seed_terms)


def _endpoint_one_hop_match(text: str, seed_terms: list[str]) -> bool:
    normalized = _norm(text)
    return any(_contains(normalized, term) and any(_norm(state) in normalized for state in ONE_HOP_STATE_TERMS) for term in seed_terms)


def _seed_distance(subject: str, obj: str, evidence: str, terms: dict[str, list[str]]) -> str:
    subject_text = _norm(subject)
    object_text = _norm(obj)
    endpoints = terms.get("endpoints", [])
    subject_match = _endpoint_seed_match(subject_text, endpoints)
    object_match = _endpoint_seed_match(object_text, endpoints)
    if subject_match or object_match:
        return "direct"
    if _endpoint_one_hop_match(subject_text, endpoints) or _endpoint_one_hop_match(object_text, endpoints):
        return "one_hop"
    if any(separator in object_text for separator in (" and ", " or ", " with ")) and any(_contains(object_text, term) for term in endpoints):
        return "ambiguous"
    return "none"


def _is_composite_endpoint(value: str) -> bool:
    text = _norm(value)
    if "," in str(value) or ";" in str(value) or " + " in str(value):
        return True
    if (" pathway" in text or " pathways" in text) and any(x in text for x in (" and ", " or ")):
        return True
    if len(re.findall(r"\b[A-Z0-9]{2,}\b", str(value or ""))) >= 3 and any(x in str(value) for x in (",", "/", "+", " and ")):
        return True
    return False


def _canonical_endpoint_eligible(observation: dict[str, Any] | None) -> bool:
    if not observation or not observation.get("retained"):
        return False
    reason = _rejection_reason(observation or {})
    if reason in {"low_confidence_entity_resolution", "canonical_endpoint_not_graph_eligible"}:
        return False
    return True


def _relation_pair_key(subject: Any, relation: Any, obj: Any) -> tuple[str, str, str]:
    return (_norm(subject), _norm(relation), _norm(obj))


def _section_value(claim: dict[str, Any], observation: dict[str, Any] | None, key: str) -> str:
    claim_section = claim.get("section_provenance") if isinstance(claim.get("section_provenance"), dict) else {}
    obs_section = (observation or {}).get("section_provenance") if isinstance((observation or {}).get("section_provenance"), dict) else {}
    return str(
        claim.get(key)
        or claim_section.get(key)
        or (observation or {}).get(key)
        or obs_section.get(key)
        or ""
    )


def _evidence_origin(claim: dict[str, Any], observation: dict[str, Any] | None) -> str:
    section_type = _section_value(claim, observation, "section_type").casefold()
    section_title = _section_value(claim, observation, "section_title").casefold()
    if section_type == "abstract" or section_title == "abstract":
        return "abstract_section"
    if section_type or section_title:
        return "body_section"
    return "unknown_section"


def _normalized_evidence_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" \t\r\n.。;；")
    return text


def _evidence_hash(value: Any) -> str:
    normalized = _normalized_evidence_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def _row_id(row: dict[str, Any]) -> str:
    return str(row.get("observation_id") or row.get("claim_id") or row.get("triple_id") or "")


def _pmid_value(row: dict[str, Any]) -> str:
    return str(row.get("pmid") or row.get("paper_id") or row.get("canonical_paper_id") or "")


def _canonical_or_strict_surface(row: dict[str, Any], side: str) -> str:
    canonical_id = str(row.get(f"{side}_canonical_id") or "")
    if canonical_id and not canonical_id.startswith("RUN:"):
        return f"id:{canonical_id}"
    nested = _entity_norm(row, side)
    nested_id = str(nested.get("canonical_id") or "")
    if nested_id and not nested_id.startswith("RUN:"):
        return f"id:{nested_id}"
    surface = (
        row.get(f"{side}_raw")
        or row.get(side)
        or row.get(f"{side}_canonical_name")
        or nested.get("canonical_name")
        or nested.get("normalized_surface")
        or nested.get("raw_text")
        or ""
    )
    return f"surface:{_norm(surface)}" if surface and not _is_composite_endpoint(str(surface)) else ""


def _relation_identity(row: dict[str, Any]) -> str:
    return _norm(row.get("relation_family") or row.get("relation_raw") or row.get("predicate") or row.get("relation") or "")


def _polarity_identity(row: dict[str, Any], fallback: str = "") -> str:
    value = str(row.get("effective_entity_polarity") or row.get("direction") or row.get("polarity") or row.get("sign") or fallback or "").casefold()
    return value if value in {"positive", "negative", "neutral", "unknown"} else fallback


def _abstract_duplicate_decision(claim: dict[str, Any], observation: dict[str, Any] | None, abstract_rows: list[dict[str, Any]]) -> dict[str, Any]:
    origin = _evidence_origin(claim, observation)
    linked = list(claim.get("linked_abstract_observation_ids") or (observation or {}).get("linked_abstract_observation_ids") or [])
    evidence = claim.get("evidence_sentence") or (observation or {}).get("evidence_sentence")
    evidence_digest = _evidence_hash(evidence)
    pmid = str(claim.get("pmid") or (observation or {}).get("pmid") or "")
    current = {
        **(observation or {}),
        "subject_raw": claim.get("subject") or claim.get("subject_raw") or (observation or {}).get("subject_raw"),
        "relation_raw": claim.get("predicate") or claim.get("relation_raw") or claim.get("relation_family") or (observation or {}).get("relation_raw"),
        "object_raw": claim.get("object") or claim.get("object_raw") or (observation or {}).get("object_raw"),
    }
    current_subject = _canonical_or_strict_surface(current, "subject")
    current_relation = _relation_identity(current)
    current_object = _canonical_or_strict_surface(current, "object")
    current_polarity = _polarity_identity(current)
    for row in abstract_rows:
        if not pmid or _pmid_value(row) != pmid:
            continue
        if evidence_digest and evidence_digest == _evidence_hash(row.get("evidence_sentence")):
            return {
                "evidence_origin": origin,
                "abstract_duplicate_status": "exact_evidence_duplicate",
                "duplicate_match_basis": ["same_pmid", "same_evidence_hash"],
                "matched_abstract_observation_id": _row_id(row),
                "dedup_action": "merge_provenance_into_abstract",
            }
        row_subject = _canonical_or_strict_surface(row, "subject")
        row_relation = _relation_identity(row)
        row_object = _canonical_or_strict_surface(row, "object")
        row_polarity = _polarity_identity(row, current_polarity)
        if (
            current_subject
            and current_relation
            and current_object
            and current_polarity
            and current_subject == row_subject
            and current_relation == row_relation
            and current_object == row_object
            and current_polarity == row_polarity
        ):
            return {
                "evidence_origin": origin,
                "abstract_duplicate_status": "deterministic_claim_duplicate",
                "duplicate_match_basis": ["same_pmid", "same_subject", "same_relation_family", "same_object", "same_polarity"],
                "matched_abstract_observation_id": _row_id(row),
                "dedup_action": "merge_provenance_into_abstract",
            }
    if linked:
        return {
            "evidence_origin": origin,
            "abstract_duplicate_status": "possible_linked_duplicate",
            "duplicate_match_basis": ["linked_abstract_observation_only"],
            "matched_abstract_observation_id": None,
            "dedup_action": "preserve_without_automatic_merge",
        }
    if origin == "body_section":
        action = "keep_as_fulltext_body_evidence"
    elif origin == "abstract_section":
        action = "keep_as_abstract_section_reextraction"
    else:
        action = "preserve_without_automatic_merge"
    return {
        "evidence_origin": origin,
        "abstract_duplicate_status": "not_duplicate",
        "duplicate_match_basis": [],
        "matched_abstract_observation_id": None,
        "dedup_action": action,
    }


def _evaluate_core_conflict_eligibility(
    observation: dict[str, Any] | None,
    *,
    relation_class: str,
    seed_distance: str,
    polarity_status: str,
    structural_graph_eligible: bool,
    canonical_status: bool,
    subject_is_composite: bool,
    object_is_composite: bool,
    abstract_duplicate_status: str,
) -> dict[str, Any]:
    failures: list[str] = []
    if not structural_graph_eligible:
        failures.append("structural_graph_ineligible")
    if relation_class != "causal_regulation":
        failures.append("relation_not_causal_regulation")
    if seed_distance != "direct":
        failures.append("seed_distance_not_direct")
    if polarity_status != "resolved":
        failures.append(f"polarity_{polarity_status}")
    if not canonical_status or (observation or {}).get("canonical_graph_eligible") is not True:
        failures.append("canonical_graph_ineligible")
    if (observation or {}).get("allow_high_confidence_graph_use") is not True:
        failures.append("high_confidence_graph_use_disallowed")
    if (observation or {}).get("conflict_reasoning_eligible") is not True:
        failures.append("conflict_reasoning_ineligible")
    if (observation or {}).get("exclude_from_high_confidence_conflict") is True:
        failures.append("excluded_from_high_confidence_conflict")
    if (observation or {}).get("excluded_from_core_reason"):
        failures.append("excluded_from_core_reason_present")
    if (observation or {}).get("predicate_direction_consistent") is not True:
        failures.append("predicate_direction_inconsistent")
    if str((observation or {}).get("predicate_anchor_status") or "") not in ACCEPTED_PREDICATE_ANCHOR_STATUSES:
        failures.append("predicate_anchor_not_accepted")
    for side in ("subject", "object"):
        status = _side_normalization_status(observation, side)
        if not status:
            failures.append(f"{side}_normalization_status_missing")
        elif status == "unresolved_fallback":
            failures.append(f"unresolved_{side}")
        review = _side_requires_manual_review(observation, side)
        if review is None:
            failures.append(f"{side}_manual_review_status_missing")
        elif review:
            failures.append(f"{side}_requires_manual_review")
    if subject_is_composite:
        failures.append("composite_subject")
    if object_is_composite:
        failures.append("composite_object")
    if abstract_duplicate_status != "not_duplicate":
        failures.append(abstract_duplicate_status)
    failures = sorted(dict.fromkeys(failures))
    passed = not failures
    if passed:
        lane = "core_seed_relation"
    elif abstract_duplicate_status != "not_duplicate" or any(x in failures for x in ("canonical_graph_ineligible", "predicate_anchor_not_accepted", "predicate_direction_inconsistent")):
        lane = "reviewable_context_relation"
    else:
        lane = "seed_neighborhood_mechanism" if seed_distance == "direct" and relation_class in {"causal_regulation", "dependency", "target_of", "rescue"} and polarity_status == "resolved" else "reviewable_context_relation"
    return {
        "core_gate_passed": passed,
        "core_gate_failures": failures,
        "conflict_eligible": passed,
        "recommended_lane": lane,
    }


def _core_gate_lane_reason(failures: list[str]) -> str:
    if "linked_abstract_duplicate" in failures:
        return "linked_abstract_duplicate_not_independent_fulltext_evidence"
    if "exact_evidence_duplicate" in failures or "possible_duplicate" in failures:
        return "abstract_duplicate_not_independent_fulltext_evidence"
    if "canonical_graph_ineligible" in failures:
        return "direct_seed_but_canonical_grounding_failed"
    if "predicate_anchor_not_accepted" in failures:
        return "direct_seed_but_predicate_anchor_failed"
    if "predicate_direction_inconsistent" in failures:
        return "direct_seed_but_predicate_direction_inconsistent"
    if "conflict_reasoning_ineligible" in failures:
        return "direct_seed_but_conflict_reasoning_ineligible"
    if "high_confidence_graph_use_disallowed" in failures:
        return "direct_seed_but_high_confidence_graph_use_disallowed"
    if "unresolved_subject" in failures or "unresolved_object" in failures:
        return "direct_seed_but_endpoint_unresolved"
    if "subject_requires_manual_review" in failures or "object_requires_manual_review" in failures:
        return "direct_seed_but_endpoint_requires_manual_review"
    return "direct_seed_but_core_gate_failed"


def _classify_lane(claim: dict[str, Any], observation: dict[str, Any] | None, *, seed_terms: dict[str, list[str]], abstract_rows: list[dict[str, Any]]) -> dict[str, Any]:
    subject = str(claim.get("subject") or claim.get("subject_raw") or (observation or {}).get("subject_raw") or "")
    relation = str(claim.get("predicate") or claim.get("relation_raw") or claim.get("relation_family") or (observation or {}).get("relation_raw") or "")
    obj = str(claim.get("object") or claim.get("object_raw") or (observation or {}).get("object_raw") or "")
    evidence = str(claim.get("evidence_sentence") or (observation or {}).get("evidence_sentence") or "")
    raw_claim_sign = str(claim.get("polarity") or claim.get("direction") or (observation or {}).get("direction") or "unknown").casefold()
    relation_class, relation_polarity = _relation_class_and_polarity(relation, evidence)
    subject_perturbation = _subject_perturbation_polarity(subject, relation, evidence)
    effective_polarity, polarity_status = _effective_entity_polarity(relation_polarity, subject_perturbation, raw_claim_sign)
    structural = bool(observation and observation.get("retained")) and relation_class in {"causal_regulation", "dependency", "target_of", "rescue"}
    canonical = bool((observation or {}).get("canonical_graph_eligible") is True)
    distance = _seed_distance(subject, obj, evidence, seed_terms)
    subject_is_composite = _is_composite_endpoint(subject)
    object_is_composite = _is_composite_endpoint(obj)
    composite_status = "composite" if subject_is_composite or object_is_composite else "atomic"
    subject_is_seed = _endpoint_seed_match(_norm(subject), seed_terms.get("endpoints", []))
    duplicate = _abstract_duplicate_decision(claim, observation, abstract_rows)
    core_gate = _evaluate_core_conflict_eligibility(
        observation,
        relation_class=relation_class,
        seed_distance=distance,
        polarity_status=polarity_status,
        structural_graph_eligible=structural,
        canonical_status=canonical,
        subject_is_composite=subject_is_composite,
        object_is_composite=object_is_composite,
        abstract_duplicate_status=duplicate["abstract_duplicate_status"],
    )
    if not subject_is_seed and core_gate["recommended_lane"] == "core_seed_relation":
        core_gate = {**core_gate, "core_gate_passed": False, "conflict_eligible": False, "recommended_lane": "seed_neighborhood_mechanism", "core_gate_failures": ["seed_subject_not_direct_seed_endpoint"]}
    conflict_eligible = bool(core_gate["conflict_eligible"])
    if distance == "direct" and relation_class == "causal_regulation" and polarity_status == "resolved" and structural:
        if core_gate["core_gate_passed"]:
            lane = "core_seed_relation"
            lane_reason = "direct_seed_relation_with_resolved_polarity"
        elif duplicate["abstract_duplicate_status"] != "not_duplicate" or subject_is_seed or composite_status == "composite":
            lane = "reviewable_context_relation"
            lane_reason = _core_gate_lane_reason(core_gate["core_gate_failures"])
        else:
            lane = "seed_neighborhood_mechanism"
            lane_reason = "direct_seed_mechanism_core_gate_failed_not_conflict_comparable"
    elif duplicate["abstract_duplicate_status"] != "not_duplicate":
        lane = "reviewable_context_relation"
        lane_reason = "linked_abstract_duplicate_not_independent_fulltext_evidence" if duplicate["abstract_duplicate_status"] == "linked_abstract_duplicate" else "abstract_duplicate_not_independent_fulltext_evidence"
    elif relation_class == "expression_state":
        lane = "reviewable_context_relation"
        lane_reason = "expression_state_claim_not_causal_graph_edge"
    elif polarity_status in {"mismatch", "ambiguous", "not_applicable"}:
        lane = "reviewable_context_relation"
        lane_reason = f"polarity_{polarity_status}"
    elif distance == "none":
        lane = "off_seed_relation"
        lane_reason = "no_claim_level_seed_endpoint"
    elif composite_status == "composite":
        lane = "reviewable_context_relation"
        lane_reason = "composite_entity_requires_atomic_decomposition"
    elif relation_class in {"association", "comparison", "no_effect", "unknown"}:
        lane = "reviewable_context_relation" if distance != "none" else "off_seed_relation"
        lane_reason = f"{relation_class}_not_conflict_comparable" if lane == "reviewable_context_relation" else "no_claim_level_seed_endpoint"
    elif not structural:
        lane = "reviewable_context_relation" if distance != "none" else "off_seed_relation"
        lane_reason = _rejection_reason(observation or {}) or "missing_structural_graph_eligibility"
    elif distance in {"direct", "one_hop"}:
        lane = "seed_neighborhood_mechanism"
        lane_reason = "direct_seed_mechanism_not_conflict_comparable" if distance == "direct" else "one_hop_seed_mechanism"
    elif distance == "ambiguous":
        lane = "reviewable_context_relation"
        lane_reason = "ambiguous_seed_distance"
    elif not canonical:
        lane = "reviewable_context_relation"
        lane_reason = "canonical_endpoint_not_graph_eligible"
    else:
        lane = "off_seed_relation"
        lane_reason = "no_claim_level_seed_endpoint"
    return {
        "relation_class": relation_class,
        "structural_graph_eligible": structural,
        "seed_distance": distance,
        "evidence_lane": lane,
        "conflict_eligible": conflict_eligible,
        "raw_claim_sign": raw_claim_sign or "unknown",
        "relation_polarity": relation_polarity,
        "subject_perturbation_polarity": subject_perturbation,
        "effective_entity_polarity": effective_polarity,
        "polarity_resolution_status": polarity_status,
        "canonical_endpoint_eligible": canonical,
        "core_gate_passed": bool(core_gate["core_gate_passed"]),
        "core_gate_failures": list(core_gate["core_gate_failures"]),
        "abstract_duplicate_status": duplicate["abstract_duplicate_status"],
        "dedup_action": duplicate["dedup_action"],
        "subject_is_composite": subject_is_composite,
        "object_is_composite": object_is_composite,
        "composite_entity_status": composite_status,
        "base_entity_polarity_derived": bool(subject_perturbation in {"positive", "negative"} and relation_polarity in {"positive", "negative"}),
        "original_intervention_claim_preserved": True,
        "lane_reason": lane_reason,
    }


def _fulltext_record_from_claim(claim: dict[str, Any], source_run: Path) -> dict[str, Any]:
    direction = str(claim.get("polarity") or claim.get("direction") or "").casefold()
    if direction not in {"positive", "negative", "neutral", "unknown", "unclear"}:
        direction = "unknown"
    return {
        **claim,
        "source_scope": "full_text",
        "evidence_source": "fulltext",
        "source_fulltext_run": str(source_run),
        "claim_id": str(claim.get("claim_id") or ""),
        "evidence_id": str(claim.get("claim_id") or ""),
        "subject_raw": claim.get("subject") or claim.get("subject_raw"),
        "object_raw": claim.get("object") or claim.get("object_raw"),
        "relation_raw": claim.get("predicate") or claim.get("relation_raw") or claim.get("relation_family"),
        "direction": "positive" if direction == "positive" else "negative" if direction == "negative" else "unknown",
        "context_slots": claim.get("context") if isinstance(claim.get("context"), dict) else {},
        "section_provenance": {
            "section_title": claim.get("section_title"),
            "section_type": claim.get("section_type"),
            "section_evidence_tier": claim.get("section_evidence_tier"),
            "section_evidence_weight": claim.get("section_evidence_weight"),
            "chunk_id": claim.get("chunk_id"),
            "chunk_hash": claim.get("chunk_hash"),
        },
    }


def _rejection_reason(observation: dict[str, Any]) -> str | None:
    if not observation.get("retained"):
        return str(observation.get("excluded_from_retention_reason") or "not_retained")
    if not observation.get("graph_observation_eligible"):
        return str(observation.get("excluded_from_core_reason") or "not_graph_eligible")
    return None


def _audit_row(claim: dict[str, Any], observation: dict[str, Any] | None, *, source_run: Path, seed_terms: dict[str, list[str]], abstract_rows: list[dict[str, Any]]) -> dict[str, Any]:
    reason = _rejection_reason(observation or {})
    lane = _classify_lane(claim, observation, seed_terms=seed_terms, abstract_rows=abstract_rows)
    reentered = lane["evidence_lane"] == "core_seed_relation"
    return {
        "claim_id": claim.get("claim_id"),
        "pmid": claim.get("pmid"),
        "pmcid": claim.get("pmcid"),
        "subject": claim.get("subject") or claim.get("subject_raw"),
        "relation": claim.get("predicate") or claim.get("relation_raw") or claim.get("relation_family"),
        "object": claim.get("object") or claim.get("object_raw"),
        "sign": claim.get("polarity") or claim.get("direction"),
        "original_evidence_sentence": claim.get("evidence_sentence"),
        "linked_abstract_observation_ids": list(claim.get("linked_abstract_observation_ids") or (observation or {}).get("linked_abstract_observation_ids") or []),
        "section_provenance": {
            "section_title": claim.get("section_title"),
            "section_type": claim.get("section_type"),
            "chunk_id": claim.get("chunk_id"),
            "chunk_hash": claim.get("chunk_hash"),
        },
        "source_fulltext_run": str(source_run),
        "normalization_status": (observation or {}).get("normalization_status") or "not_attempted",
        **lane,
        "graph_eligibility": bool(lane["structural_graph_eligible"]),
        "reentered": reentered,
        "rejection_reason": reason if reason and not (observation or {}).get("retained") else None if lane["evidence_lane"] in {"core_seed_relation", "seed_neighborhood_mechanism", "reviewable_context_relation"} else reason or lane["lane_reason"] or "normalization_not_attempted",
        "merged_observation_id": (observation or {}).get("observation_id") if reentered else None,
    }


def reenter_fulltext_l1_claims(
    run_dir: str | Path,
    *,
    source_fulltext_run: str | Path,
    execute: bool = True,
    network: bool = False,
    api: bool = False,
    entity_network_lookup: bool = False,
    entity_llm_cleaner: bool = False,
) -> dict[str, Any]:
    run = Path(run_dir)
    artifacts = run / "artifacts"
    source_run = Path(source_fulltext_run)
    claims = _rows(artifacts / "l35_fulltext_l1_claims.jsonl")
    abstract_retained = [{**row, "evidence_source": row.get("evidence_source") or "abstract", "source_scope": row.get("source_scope") or "abstract"}
                         for row in _rows(artifacts / "l2_retained_observations.jsonl")]
    abstract_graph = [{**row, "evidence_source": row.get("evidence_source") or "abstract", "source_scope": row.get("source_scope") or "abstract"}
                      for row in _rows(artifacts / "l2_graph_observations.jsonl")]
    abstract_graph_keys = {_source_key(row) for row in abstract_graph}
    abstract_retained_keys = {_source_key(row) for row in abstract_retained}

    if not claims:
        summary = {
            "input_fulltext_claim_count": 0,
            "source_fulltext_claim_count": 0,
            "fulltext_l1_reused": True,
            "fulltext_l1_api_calls": 0,
            "normalization_attempt_count": 0,
            "normalized_fulltext_claim_count": 0,
            "structurally_normalized_claim_count": 0,
            "canonical_verified_claim_count": 0,
            "reentered_observation_count": 0,
            "core_seed_relation_count": 0,
            "seed_neighborhood_mechanism_count": 0,
            "reviewable_context_relation_count": 0,
            "off_seed_relation_count": 0,
            "rejected_fulltext_claim_count": 0,
            "evidence_lane_counts": {},
            "relation_class_counts": {},
            "seed_distance_counts": {},
            "polarity_resolution_status_counts": {},
            "relation_sign_mismatch_count": 0,
            "perturbation_inversion_count": 0,
            "composite_entity_count": 0,
            "conflict_eligible_count": 0,
            "core_gate_pass_count": 0,
            "core_gate_fail_count": 0,
            "core_gate_failure_counts": {},
            "abstract_duplicate_count": 0,
            "abstract_provenance_merge_count": 0,
            "independent_fulltext_body_evidence_count": 0,
            "rejection_reason_counts": {},
            "merged_graph_observation_count": len(abstract_graph),
            "abstract_observation_count": len(abstract_graph),
            "fulltext_observation_count": 0,
            "confirmed_conflict_count": 0,
            "non_comparable_pair_count": 0,
            "hypothesis_count": int(_json(artifacts / "hypothesis_summary.json", {}).get("formal_hypothesis_count", 0) or 0),
            "status": "no_input",
        }
        atomic_write_jsonl(artifacts / "fulltext_reentry_audit.jsonl", iter(()))
        atomic_write_jsonl(artifacts / "fulltext_core_seed_observations.jsonl", iter(()))
        atomic_write_jsonl(artifacts / "fulltext_seed_neighborhood_observations.jsonl", iter(()))
        atomic_write_jsonl(artifacts / "fulltext_reviewable_relations.jsonl", iter(()))
        atomic_write_jsonl(artifacts / "fulltext_off_seed_relations.jsonl", iter(()))
        atomic_write_json(artifacts / "fulltext_reentry_summary.json", summary)
        return summary

    records = [_fulltext_record_from_claim(claim, source_run) for claim in claims]
    observations = _normalize_progressive_records(
        records,
        _json(artifacts / "domain_profile.json", {}),
        run,
        execute=execute,
        network=network,
        api=api,
        entity_network_lookup=entity_network_lookup,
        entity_llm_cleaner=entity_llm_cleaner,
    )
    terms = _seed_terms(_active_seed(artifacts))
    by_claim = {str(row.get("claim_id")): row for row in observations}
    audit = [_audit_row(claim, by_claim.get(str(claim.get("claim_id"))), source_run=source_run, seed_terms=terms, abstract_rows=abstract_retained) for claim in claims]
    audit_by_claim = {str(row.get("claim_id")): row for row in audit}
    annotated_observations = []
    for row in observations:
        lane = {k: v for k, v in audit_by_claim.get(str(row.get("claim_id")), {}).items() if k in {
            "relation_class", "structural_graph_eligible", "seed_distance", "evidence_lane", "conflict_eligible",
            "raw_claim_sign", "relation_polarity", "subject_perturbation_polarity", "effective_entity_polarity",
            "polarity_resolution_status", "canonical_endpoint_eligible", "subject_is_composite",
            "object_is_composite", "composite_entity_status", "base_entity_polarity_derived",
            "original_intervention_claim_preserved", "core_gate_passed", "core_gate_failures",
            "abstract_duplicate_status", "dedup_action", "lane_reason",
        }}
        annotated_observations.append({**row, **lane, "graph_eligibility": bool(lane.get("structural_graph_eligible"))})
    reentered = [row for row in annotated_observations if row.get("evidence_lane") == "core_seed_relation"]
    seed_neighborhood = [row for row in annotated_observations if row.get("evidence_lane") == "seed_neighborhood_mechanism"]
    reviewable = [row for row in annotated_observations if row.get("evidence_lane") == "reviewable_context_relation"]
    off_seed = [row for row in annotated_observations if row.get("evidence_lane") == "off_seed_relation"]
    rejected = [row for row in audit if row.get("rejection_reason")]

    abstract_by_id = {str(row.get("observation_id") or row.get("claim_id") or row.get("triple_id") or ""): row for row in abstract_retained}
    for row in audit:
        if row.get("abstract_duplicate_status") != "linked_abstract_duplicate" or row.get("dedup_action") != "merge_provenance_into_abstract":
            continue
        observation = by_claim.get(str(row.get("claim_id"))) or {}
        linked = list(observation.get("linked_abstract_observation_ids") or [])
        provenance = {
            "claim_id": row.get("claim_id"),
            "pmid": row.get("pmid"),
            "pmcid": row.get("pmcid"),
            "source_fulltext_run": row.get("source_fulltext_run"),
            "section_provenance": row.get("section_provenance"),
            "evidence_sentence": row.get("original_evidence_sentence"),
            "dedup_action": row.get("dedup_action"),
        }
        for linked_id in linked:
            target_row = abstract_by_id.get(str(linked_id))
            if target_row is None:
                continue
            existing = list(target_row.get("merged_fulltext_provenance") or [])
            if not any(item.get("claim_id") == provenance["claim_id"] for item in existing):
                target_row["merged_fulltext_provenance"] = [*existing, provenance]

    merged_retained = list(abstract_retained)
    for row in [x for x in annotated_observations if x.get("retained")]:
        key = _source_key(row)
        if key not in abstract_retained_keys:
            merged_retained.append(row)
            abstract_retained_keys.add(key)

    merged_graph = list(abstract_graph)
    for row in reentered:
        key = _source_key(row)
        if key not in abstract_graph_keys:
            merged_graph.append(row)
            abstract_graph_keys.add(key)

    atomic_write_jsonl(artifacts / "l2_fulltext_observations.jsonl", annotated_observations)
    atomic_write_jsonl(artifacts / "l2_fulltext_graph_observations.jsonl", reentered)
    atomic_write_jsonl(artifacts / "l2_fulltext_seed_neighborhood_observations.jsonl", seed_neighborhood)
    atomic_write_jsonl(artifacts / "fulltext_core_seed_observations.jsonl", reentered)
    atomic_write_jsonl(artifacts / "fulltext_seed_neighborhood_observations.jsonl", seed_neighborhood)
    atomic_write_jsonl(artifacts / "fulltext_reviewable_relations.jsonl", reviewable)
    atomic_write_jsonl(artifacts / "fulltext_off_seed_relations.jsonl", off_seed)
    atomic_write_jsonl(artifacts / "l2_retained_observations.jsonl", merged_retained)
    atomic_write_jsonl(artifacts / "l2_graph_observations.jsonl", merged_graph)
    atomic_write_jsonl(artifacts / "merged_l2_graph_observations.jsonl", merged_graph)
    atomic_write_jsonl(artifacts / "fulltext_reentry_audit.jsonl", audit)

    shared = _json(artifacts / "l35_fulltext_conflict_confirmation_summary.json", {})
    prepared = prepare_discovery_escalation(run, enabled=True)
    discovery_summary = finalize_discovery_escalation(
        run,
        prepared=prepared,
        expected=bool(claims),
        explicitly_disabled=False,
        shared_summary=shared,
        strict_conflict_count=int(shared.get("fulltext_confirmed_conflict_count", 0) or 0),
    )
    l4 = build_l4_context_mining(run)
    build_l5_context_attribution(run)
    l6 = build_l6_mechanism_graph(run)
    hypothesis = _json(artifacts / "hypothesis_summary.json", {})

    reason_counts = Counter(str(row["rejection_reason"]) for row in rejected)
    lane_counts = Counter(str(row.get("evidence_lane") or "unclassified") for row in audit)
    relation_class_counts = Counter(str(row.get("relation_class") or "unknown") for row in audit)
    seed_distance_counts = Counter(str(row.get("seed_distance") or "none") for row in audit)
    polarity_counts = Counter(str(row.get("polarity_resolution_status") or "ambiguous") for row in audit)
    core_gate_failure_counts = Counter(reason for row in audit for reason in (row.get("core_gate_failures") or []))
    summary = {
        "input_fulltext_claim_count": len(claims),
        "source_fulltext_claim_count": len(claims),
        "fulltext_l1_reused": True,
        "fulltext_l1_api_calls": 0,
        "normalization_attempt_count": len(claims),
        "normalized_fulltext_claim_count": len(observations),
        "structurally_normalized_claim_count": len(observations),
        "canonical_verified_claim_count": sum(bool(row.get("canonical_endpoint_eligible")) for row in audit),
        "reentered_observation_count": len(reentered),
        "core_seed_relation_count": len(reentered),
        "seed_neighborhood_mechanism_count": len(seed_neighborhood),
        "reviewable_context_relation_count": len(reviewable),
        "off_seed_relation_count": len(off_seed),
        "rejected_fulltext_claim_count": len(rejected),
        "evidence_lane_counts": dict(sorted(lane_counts.items())),
        "relation_class_counts": dict(sorted(relation_class_counts.items())),
        "seed_distance_counts": dict(sorted(seed_distance_counts.items())),
        "polarity_resolution_status_counts": dict(sorted(polarity_counts.items())),
        "relation_sign_mismatch_count": polarity_counts.get("mismatch", 0),
        "perturbation_inversion_count": sum(bool(row.get("base_entity_polarity_derived")) for row in audit),
        "composite_entity_count": sum(str(row.get("composite_entity_status")) == "composite" for row in audit),
        "conflict_eligible_count": sum(bool(row.get("conflict_eligible")) for row in audit),
        "core_gate_pass_count": sum(bool(row.get("core_gate_passed")) for row in audit),
        "core_gate_fail_count": sum(not bool(row.get("core_gate_passed")) for row in audit),
        "core_gate_failure_counts": dict(sorted(core_gate_failure_counts.items())),
        "abstract_duplicate_count": sum(str(row.get("abstract_duplicate_status")) != "not_duplicate" for row in audit),
        "abstract_provenance_merge_count": sum(str(row.get("dedup_action")) == "merge_provenance_into_abstract" for row in audit),
        "independent_fulltext_body_evidence_count": sum(str(row.get("dedup_action")) == "keep_as_fulltext_body_evidence" for row in audit),
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
        "merged_graph_observation_count": len(merged_graph),
        "abstract_observation_count": len(abstract_graph),
        "fulltext_observation_count": len(reentered),
        "confirmed_conflict_count": int(shared.get("fulltext_confirmed_conflict_count", discovery_summary.get("fulltext_strict_conflict_candidate_count", 0)) or 0),
        "non_comparable_pair_count": int(discovery_summary.get("non_comparable_direction_pair_count", 0) or 0),
        "hypothesis_count": int(hypothesis.get("formal_hypothesis_count", 0) or 0),
        "l4_context_factor_count": int(l4.get("context_factor_count", 0) or 0),
        "l6_mechanism_edge_count": int(l6.get("mechanism_edge_count", 0) or 0),
        "status": "completed",
    }
    atomic_write_json(artifacts / "fulltext_reentry_summary.json", summary)
    return summary


__all__ = ["reenter_fulltext_l1_claims"]
