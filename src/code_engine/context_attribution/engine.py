from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from .models import ContextExtraction, ContextPairAttribution, EXTRACTION_SCHEMA_VERSION, PAIR_SCHEMA_VERSION
from .registry import load_registry, resolve_factors

PROMPT_VERSION = "context_attribution_prompts_v2"
CANDIDATE_POLICY_VERSION = "deterministic_conflict_candidates_v1"

def _hash(value: Any) -> str:
    raw = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()

def _id(row: dict[str, Any]) -> str:
    return str(row.get("observation_id") or row.get("claim_id") or row.get("triple_id") or "")

def _evidence(row: dict[str, Any]) -> str:
    return str(row.get("evidence_sentence") or row.get("direct_evidence_sentence") or "")

def build_abstract_input(observation: dict[str, Any], profiles: list[str]) -> dict[str, Any]:
    """The abstract contract deliberately ignores every full-text-shaped field."""
    oid, sentence = _id(observation), _evidence(observation)
    anchor_id = f"{oid}:abstract_sentence"
    return {
        "contract_version": "abstract_context_input_v1", "input_mode": "abstract_sentence_only",
        "observation_id": oid, "domain_profiles": profiles,
        "read_only_scientific_reference": {
            "canonical_subject": observation.get("subject_canonical_id"),
            "canonical_object": observation.get("object_canonical_id"),
            "polarity": observation.get("polarity") or observation.get("direction_polarity"),
        },
        "evidence_sentence": sentence,
        "evidence_anchors": [{"anchor_id": anchor_id, "text": sentence, "text_hash": _hash(sentence),
                              "char_start": 0, "char_end": len(sentence), "source_role": "abstract",
                              "source_section": observation.get("source_section") or "abstract"}],
        "sentence_provenance": observation.get("sentence_provenance") or {
            "paper_id": observation.get("paper_id"), "source_section": "abstract"
        },
    }

def build_fulltext_input(observation: dict[str, Any], profiles: list[str]) -> dict[str, Any]:
    provenance = observation.get("provenance") or {}
    anchors = provenance.get("evidence_spans") or observation.get("evidence_anchors") or []
    def anchor_ids(value: Any) -> list[str]:
        if isinstance(value, dict):
            return list(value.get("evidence_span_ids") or [])
        return []
    experiment, interventions = observation.get("experiment") or {}, list(observation.get("interventions") or [])
    measurement, observed = observation.get("measurement") or {}, observation.get("observation") or {}
    chain = {
        "experimental_system": {
            "value": experiment, "authoritative_evidence_anchor_ids": list(observation.get("evidence_span_ids") or [])
        },
        "intervention_or_exposure": {
            "value": interventions, "combination_mode": observation.get("combination_mode"),
            "authoritative_evidence_anchor_ids": sorted({x for item in interventions for x in anchor_ids(item)})
        },
        "comparator_or_control": {
            "value": experiment.get("comparison_arm_raw") or experiment.get("control_arm_raw"),
            "authoritative_evidence_anchor_ids": list(observation.get("evidence_span_ids") or [])
        },
        "measurement": {"value": measurement, "authoritative_evidence_anchor_ids": anchor_ids(measurement)},
        "observed_result": {"value": observed, "authoritative_evidence_anchor_ids": anchor_ids(observed)},
        "interpretation": {
            "value": observation.get("interpretation_raw"),
            "authoritative_evidence_anchor_ids": list(observation.get("interpretation_evidence_span_ids") or [])
        },
    }
    direct = next((a.get("text") for a in anchors if a.get("span_type") == "observation"), _evidence(observation))
    return {
        "contract_version": "fulltext_context_input_v1", "input_mode": "fulltext_evidence_chain",
        "observation_id": _id(observation), "domain_profiles": profiles,
        "read_only_scientific_reference": {
            "canonical_subject": observation.get("subject_canonical_id"),
            "canonical_object": observation.get("object_canonical_id"),
            "polarity": observation.get("polarity") or (observation.get("candidate_relation") or {}).get("lexical_direction"),
        },
        "direct_evidence_sentence": direct, "experimental_logic_chain": chain,
        "evidence_anchors": anchors, "provenance": provenance,
        "logic_chain_id": _hash(chain), "experiment_group_id": experiment.get("experiment_id"),
        "intervention_group": {"combination_mode": observation.get("combination_mode"), "interventions": interventions},
        "measurement_identity": _hash(measurement), "source_section": provenance.get("section"),
        "source_role": [a.get("source_role") for a in anchors],
        "evidence_family": experiment.get("evidence_family_id"),
    }

def extraction_cache_identity(contract: dict[str, Any], *, profiles: list[str], provider: str,
                              model: str, thinking_mode: str = "default",
                              max_tokens: int | None = None,
                              registry: dict[str, Any] | None = None) -> str:
    registry = registry or load_registry()
    anchors = contract.get("evidence_anchors") or []
    return _hash({
        "observation_evidence_hash": _hash(contract.get("evidence_sentence") or contract.get("direct_evidence_sentence") or ""),
        "logic_chain_hash": _hash(contract.get("experimental_logic_chain") or {}),
        "anchor_registry_hash": _hash(anchors), "domain_profiles": profiles,
        "domain_profile_version": registry["registry_version"], "prompt_version": PROMPT_VERSION,
        "schema_version": EXTRACTION_SCHEMA_VERSION, "provider": provider, "model": model,
        "thinking_mode": thinking_mode, "max_tokens": max_tokens,
        "normalization_registry_version": registry["normalization_registry_version"],
    })

def pair_cache_identity(a_identity: str, b_identity: str, profiles: list[str]) -> str:
    return _hash({"extraction_identities": [a_identity, b_identity], "prompt_version": PROMPT_VERSION,
                  "schema_version": PAIR_SCHEMA_VERSION, "profiles": profiles,
                  "candidate_pair_policy_version": CANDIDATE_POLICY_VERSION})

def candidate_pairs(observations: list[dict[str, Any]], allowlist: set[str] | None = None) -> list[dict[str, Any]]:
    """Bounded deterministic screening; never performs all-pairs comparison."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        oid = _id(row)
        evidence_ok = bool(_evidence(row) or (row.get("provenance") or {}).get("evidence_spans"))
        endpoint = str(row.get("canonical_endpoint_id") or row.get("object_canonical_id") or row.get("canonical_edge_id") or "")
        relation = str(row.get("relation_class") or row.get("relation_family") or "")
        species = str(row.get("species_canonical_id") or "")
        if oid and evidence_ok and endpoint and relation not in {"incompatible", "non_comparable"}:
            groups[(endpoint, species)].append(row)
    output = []
    for (endpoint, _species), rows in groups.items():
        positives = [x for x in rows if str(x.get("polarity") or x.get("direction_polarity") or x.get("direction")).casefold() in {"positive", "increase", "activate", "1"}]
        negatives = [x for x in rows if str(x.get("polarity") or x.get("direction_polarity") or x.get("direction")).casefold() in {"negative", "decrease", "inhibit", "-1"}]
        for left in positives[:25]:
            for right in negatives[:25]:
                ids = [_id(left), _id(right)]
                pair_id = "context-pair-" + _hash({"endpoint": endpoint, "ids": sorted(ids)})[:20]
                if allowlist is None or pair_id in allowlist:
                    output.append({"pair_id": pair_id, "claim_a": left, "claim_b": right,
                                   "candidate_policy_version": CANDIDATE_POLICY_VERSION})
    return output

def extraction_prompt(contract: dict[str, Any], profiles: list[str]) -> str:
    factors = resolve_factors(profiles)
    return _prompt("observation_context_extraction", contract, factors)

def pair_prompt(payload: dict[str, Any], profiles: list[str]) -> str:
    factors = resolve_factors(profiles)
    return _prompt("observation_pair_context_attribution", payload, factors)

def _prompt(task: str, payload: dict[str, Any], factors: dict[str, Any]) -> str:
    rules = (
        "Return exactly one valid JSON object. Do not output Markdown or any text outside the JSON object. "
        "Use only supplied evidence; never use external knowledge. Output unknown when unsupported. "
        "Do not treat Methods as an observed result. Never invent species, tissue, dose, time, or design. "
        "Every non-unknown value needs anchors belonging to that observation. Abstract inputs may use only "
        "the abstract evidence sentence; fulltext inputs may use only its local evidence chain. Preserve "
        "multi-intervention combinations. Distinguish same from semantically equivalent. Different does not "
        "automatically mean non-comparable; missing never means same. Never alter polarity, strict core, "
        "canonical edges, canonical identity, confirmed-conflict status, or hypothesis eligibility. "
        "Return concise evidence-grounded reasoning_summary, never hidden chain-of-thought."
    )
    examples = _schema_valid_cross_domain_examples()
    schema_valid_json_example = (
        examples["extraction_examples"][0]
        if task == "observation_context_extraction"
        else examples["pair_example"]
    )
    return json.dumps({"task": task, "prompt_version": PROMPT_VERSION, "rules": rules,
                       "schema_valid_json_example": schema_valid_json_example,
                       "examples": examples, "factor_registry": factors, "input": payload},
                      ensure_ascii=False, sort_keys=True)

def _schema_valid_cross_domain_examples() -> dict[str, Any]:
    values = (
        ("biomedical", ["generic", "biomedical"], "species", "mouse", "bio:A1"),
        ("clinical", ["generic", "clinical"], "follow_up", "12 week", "clinical:A1"),
        ("chemistry", ["generic", "chemistry"], "temperature", "298 K", "chem:A1"),
        ("materials_catalysis", ["generic", "materials", "catalysis"], "catalyst_composition", "Pt/Al2O3", "cat:A1"),
    )
    examples = []
    for oid, profiles, factor_id, raw, anchor in values:
        examples.append(ContextExtraction(
            observation_id=f"example_{oid}", domain_profiles=profiles,
            input_mode="fulltext_evidence_chain",
            context_factors=[{"factor_id": factor_id, "raw_value": raw, "normalized_value": None,
                              "status": "explicit", "evidence_anchor_ids": [anchor],
                              "evidence_text": f"Locally supported value: {raw}", "confidence": .9}],
        ).model_dump(mode="json"))
    pair = ContextPairAttribution(
        pair_id="example_chemistry_pair", claim_a_observation_id="example_chemistry_a",
        claim_b_observation_id="example_chemistry_b", comparability="conditionally_comparable",
        factor_comparisons=[{"factor_id": "temperature", "claim_a_value": "25 C",
                             "claim_b_value": "298.15 K", "status": "equivalent",
                             "comparability_effect": "none", "explanatory_strength": "none",
                             "claim_a_anchor_ids": ["chem_a:A1"], "claim_b_anchor_ids": ["chem_b:A1"],
                             "reason": "The locally reported temperatures are safely unit-convertible."}],
        reasoning_summary="Conditions are comparable after deterministic unit validation.", confidence=.9,
    ).model_dump(mode="json")
    return {"extraction_examples": examples, "pair_example": pair}
