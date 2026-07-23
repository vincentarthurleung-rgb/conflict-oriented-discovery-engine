from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from .composition import composition_identity, load_composition_policy
from .identities import IDENTITY_BUNDLE_VERSION, resolve_policy_identities
from .models import ContextExtraction, ContextPairAttribution, EXTRACTION_SCHEMA_VERSION, PAIR_SCHEMA_VERSION
from .registry import RegistryResolution, load_registry, resolve_factors, resolve_registry
from .validation import (
    HYDRATOR_VERSION, LOCAL_CHAIN_INFERENCE_POLICY_VERSION, VALIDATOR_VERSION,
)
from .token_spans import (
    ANCHOR_TOKENIZER_VERSION, EXPLICIT_SPAN_VERSION, SPAN_HYDRATOR_VERSION,
    attach_token_catalog,
)

PROMPT_VERSION = "context_attribution_prompts_v5"
CANDIDATE_POLICY_VERSION = "deterministic_conflict_candidates_v1"
COMPARABILITY_POLICY_VERSION = "context_comparability_policy_v1"

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
    return attach_token_catalog({
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
    })

def build_fulltext_input(observation: dict[str, Any], profiles: list[str]) -> dict[str, Any]:
    provenance = observation.get("provenance") or {}
    anchors = provenance.get("evidence_spans") or observation.get("evidence_anchors") or []
    span_to_anchor = {
        str(anchor.get("evidence_span_id") or anchor.get("anchor_id")):
        str(anchor.get("anchor_id") or anchor.get("evidence_span_id"))
        for anchor in anchors
    }
    def authoritative_ids(values: Any) -> list[str]:
        return [span_to_anchor.get(str(value), str(value)) for value in list(values or [])]
    def anchor_ids(value: Any) -> list[str]:
        if isinstance(value, dict):
            return authoritative_ids(value.get("evidence_span_ids"))
        return []
    experiment, interventions = observation.get("experiment") or {}, list(observation.get("interventions") or [])
    measurement, observed = observation.get("measurement") or {}, observation.get("observation") or {}
    chain = {
        "experimental_system": {
            "value": experiment,
            "authoritative_evidence_anchor_ids": authoritative_ids(observation.get("evidence_span_ids"))
        },
        "intervention_or_exposure": {
            "value": interventions, "combination_mode": observation.get("combination_mode"),
            "authoritative_evidence_anchor_ids": sorted({x for item in interventions for x in anchor_ids(item)})
        },
        "comparator_or_control": {
            "value": {
                "comparison_arm_raw": experiment.get("comparison_arm_raw"),
                "control_arm_raw": experiment.get("control_arm_raw"),
            },
            "authoritative_evidence_anchor_ids": authoritative_ids(observation.get("evidence_span_ids"))
        },
        "measurement": {"value": measurement, "authoritative_evidence_anchor_ids": anchor_ids(measurement)},
        "observed_result": {"value": observed, "authoritative_evidence_anchor_ids": anchor_ids(observed)},
        "interpretation": {
            "value": observation.get("interpretation_raw"),
            "authoritative_evidence_anchor_ids": authoritative_ids(
                observation.get("interpretation_evidence_span_ids")
            )
        },
    }
    direct = next((a.get("text") for a in anchors if a.get("span_type") == "observation"), _evidence(observation))
    return attach_token_catalog({
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
    })

def extraction_cache_identity(contract: dict[str, Any], *, profiles: list[str], provider: str,
                              model: str, thinking_mode: str = "default",
                              max_tokens: int | None = None,
                              registry: dict[str, Any] | None = None,
                              registry_resolution: RegistryResolution | None = None) -> str:
    registry_resolution = registry_resolution or resolve_registry()
    registry = registry or load_registry(resolution=registry_resolution)
    composition_policy, _ = load_composition_policy()
    composition = composition_identity()
    normalization_identity, comparator_identity = resolve_policy_identities(
        registry=registry,
        registry_path=registry_resolution.registry_path,
        registry_sha256=registry_resolution.registry_content_sha256,
        composition_policy=composition_policy,
        composition_path=composition["composition_policy_path"],
        composition_sha256=composition["composition_policy_content_sha256"],
    )
    anchors = contract.get("evidence_anchors") or []
    observation_token_identity = contract.get("observation_token_catalog_identity") or {}
    return _hash({
        "identity_bundle_version": IDENTITY_BUNDLE_VERSION,
        "observation_evidence_hash": _hash(contract.get("evidence_sentence") or contract.get("direct_evidence_sentence") or ""),
        "logic_chain_hash": _hash(contract.get("experimental_logic_chain") or {}),
        "anchor_registry_hash": _hash(anchors), "domain_profiles": profiles,
        "observation_id": contract.get("observation_id"),
        "authoritative_anchor_contract_identity": _hash(anchors),
        "registry_version": registry_resolution.registry_version,
        "registry_content_sha256": registry_resolution.registry_content_sha256,
        "registry_schema_version": registry_resolution.registry_schema_version,
        "prompt_version": PROMPT_VERSION,
        "extraction_schema_version": EXTRACTION_SCHEMA_VERSION, "provider": provider, "model": model,
        "thinking_mode": thinking_mode, "max_tokens": max_tokens,
        "validator_version": VALIDATOR_VERSION, "hydrator_version": HYDRATOR_VERSION,
        "anchor_tokenizer_version": ANCHOR_TOKENIZER_VERSION,
        "explicit_span_version": EXPLICIT_SPAN_VERSION,
        "explicit_span_hydrator_version": SPAN_HYDRATOR_VERSION,
        "observation_token_catalog_identity_sha256":
            observation_token_identity.get("observation_token_catalog_sha256"),
        "observation_anchor_text_identity_sha256":
            observation_token_identity.get("observation_anchor_text_identity_sha256"),
        "normalization_policy_identity_sha256": normalization_identity.identity_sha256,
        "comparator_normalization_policy_identity_sha256":
            comparator_identity.identity_sha256,
        "local_chain_inference_policy_version": LOCAL_CHAIN_INFERENCE_POLICY_VERSION,
        **composition,
        "normalization_registry_version": registry["normalization_registry_version"],
    })

def pair_cache_identity(a_identity: str, b_identity: str, profiles: list[str], *,
                        pair_id: str | None = None, provider: str | None = None,
                        model: str | None = None, thinking_mode: str | None = None,
                        registry_resolution: RegistryResolution | None = None) -> str:
    registry_resolution = registry_resolution or resolve_registry()
    registry = load_registry(resolution=registry_resolution)
    return _hash({"pair_id": pair_id, "validated_extraction_identities": [a_identity, b_identity],
                  "identity_bundle_version": IDENTITY_BUNDLE_VERSION,
                  "claim_a_validated_extraction_identity": a_identity,
                  "claim_b_validated_extraction_identity": b_identity,
                  "prompt_version": PROMPT_VERSION,
                  "comparison_schema_version": PAIR_SCHEMA_VERSION, "profiles": profiles,
                  "registry_version": registry_resolution.registry_version,
                  "registry_content_sha256": registry_resolution.registry_content_sha256,
                  "registry_schema_version": registry_resolution.registry_schema_version,
                  "normalization_registry_version": registry["normalization_registry_version"],
                  "comparability_policy_version": COMPARABILITY_POLICY_VERSION,
                  "provider": provider, "model": model, "thinking_mode": thinking_mode,
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

def extraction_prompt(contract: dict[str, Any], profiles: list[str],
                      registry: dict[str, Any] | None = None) -> str:
    factors = resolve_factors(profiles, registry)
    return _prompt("observation_context_extraction", contract, factors)

def pair_prompt(payload: dict[str, Any], profiles: list[str],
                registry: dict[str, Any] | None = None) -> str:
    factors = resolve_factors(profiles, registry)
    return _prompt("observation_pair_context_attribution", payload, factors)

def _prompt(task: str, payload: dict[str, Any], factors: dict[str, Any]) -> str:
    rules = (
        "Return exactly one valid JSON object. Do not output Markdown or any text outside the JSON object. "
        "Use only factor_id values present in factor_registry. Select evidence_anchor_ids only from the "
        "authoritative anchor IDs in this observation input; never create a span ID, hash ID, temporary ID, "
        "or any other anchor. For status explicit, set raw_value=null and select exactly one explicit_span "
        "using evidence_anchor_id, start_token_id, and end_token_id from the same supplied anchor. Do not copy "
        "surface text or provide quotes. The selected contiguous span must directly express the factor and "
        "must be narrow enough to exclude irrelevant prose. The deterministic hydrator alone slices raw_value "
        "from Unicode code-point offsets. Preserve word order. Never expand abbreviations, "
        "substitute synonyms, summarize outcomes, or add absent words. Thus CRC cannot become colorectal "
        "cancer; 'mRNA expression of CSN8' cannot become 'CSN8 mRNA expression'; absent 'versus control' or "
        "'in vitro' cannot be added. raw_value and normalized_value have different meanings. Put any model normalization "
        "proposal in normalized_candidate and set normalized_value to null; only the deterministic resolver "
        "fills normalized_value. A normalization must never replace raw_value. Omit evidence_text and "
        "authoritative_evidence: the deterministic hydrator fills them from selected anchors. Never output "
        "the phrase 'Locally supported value:' or any summarized/paraphrased evidence_text. For status "
        "inferred_from_local_chain, raw_value must be null. Provide raw_components, source_chain_node_ids, "
        "supporting evidence_anchor_ids, and an allowed inference_rule. Every component must name a supplied "
        "chain_node_id and allowed field_path, copy one continuous surface from that field, and cite anchors "
        "owned by that node. Never combine multiple fields into one component, never choose component order "
        "freely, and never output composed_value, composition_rule, or composition_provenance; the deterministic "
        "composer creates them. Use unknown with raw_value=null, no anchors, no chain nodes, no components, "
        "no rule, and no normalization whenever the "
        "supplied evidence is insufficient. "
        "Use only supplied evidence; never use external knowledge. Output unknown when unsupported. "
        "Do not treat Methods as an observed result. Never infer species from a cell line: A549 may support "
        "cell_line='A549' but species must be unknown unless a supplied surface or controlled rule supports it. "
        "Never invent species, tissue, dose, time, comparator, or design. A549 is a valid cell_line span but "
        "cannot be used as a species span. If no direct single span or active local-chain rule exists, use unknown. "
        "Every non-unknown value needs anchors belonging to that observation. Abstract inputs may use only "
        "the abstract evidence sentence; fulltext inputs may use only its local evidence chain. Preserve "
        "multi-intervention combinations. Distinguish same from semantically equivalent. Different does not "
        "automatically mean non-comparable; missing never means same. Never alter polarity, strict core, "
        "canonical relation, canonical edges, canonical identity, strict core, confirmed/formal-conflict "
        "status, projection authority, or hypothesis eligibility. Pair comparison may use only its two "
        "validated extractions. Factor comparison status uses same, equivalent, different, or conflicting; "
        "unknown asymmetry uses missing_a, missing_b, or missing_both, and pair-level not-comparable output "
        "uses comparability=non_comparable. Missing information is not a context difference, and unknown "
        "versus explicit must remain asymmetric. "
        "Return concise evidence-grounded reasoning_summary, never hidden chain-of-thought."
    )
    examples = _schema_valid_cross_domain_examples()
    schema_valid_json_example = (
        examples["extraction_examples"][0]["output"]
        if task == "observation_context_extraction"
        else examples["pair_example"]["output"]
    )
    composition_policy, _ = load_composition_policy()
    active_rules = set(composition_policy["rules"])
    factors = {
        factor_id: {
            **definition,
            "allowed_local_inference_rules": [
                rule for rule in definition.get("allowed_local_inference_rules", [])
                if rule in active_rules
            ],
        }
        for factor_id, definition in factors.items()
    }
    return json.dumps({"task": task, "prompt_version": PROMPT_VERSION, "rules": rules,
                       "schema_valid_json_example": schema_valid_json_example,
                       "examples": examples, "factor_registry": factors,
                       "local_chain_composition_policy": composition_policy,
                       "input": payload},
                      ensure_ascii=False, sort_keys=True)

def _schema_valid_cross_domain_examples() -> dict[str, Any]:
    def provider_dump(value: ContextExtraction) -> dict[str, Any]:
        payload = value.model_dump(mode="json")
        for factor in payload["context_factors"]:
            for field in (
                "evidence_text", "authoritative_evidence", "composed_value",
                "composition_rule", "composition_provenance", "legacy_unverifiable",
                "raw_value_source", "explicit_span_resolution",
            ):
                factor.pop(field, None)
        return payload

    explicit_input = attach_token_catalog({
        "observation_id": "example_biomedical_explicit",
        "input_mode": "fulltext_evidence_chain",
        "evidence_anchors": [{
            "anchor_id": "bio:A1", "text": "Human A549 cells were treated for 24 h.",
            "source_role": "current", "source_section": "Results",
        }],
    })
    explicit_output = ContextExtraction(
        observation_id=explicit_input["observation_id"], domain_profiles=["generic", "biomedical"],
        input_mode="fulltext_evidence_chain",
        context_factors=[{
            "factor_id": "species", "raw_value": None, "normalized_value": None,
            "normalized_candidate": "Homo sapiens",
            "status": "explicit", "evidence_anchor_ids": ["bio:A1"], "confidence": .9,
            "explicit_span": {
                "evidence_anchor_id": "bio:A1",
                "start_token_id": "bio:A1:T0", "end_token_id": "bio:A1:T0",
            },
        }],
    )
    explicit_output = provider_dump(explicit_output)
    cell_line_input = attach_token_catalog({
        "observation_id": "example_a549_cell_line",
        "input_mode": "fulltext_evidence_chain",
        "evidence_anchors": [{
            "anchor_id": "bio:A5", "text": "A549 cells showed an increased endpoint.",
            "source_role": "current", "source_section": "Results",
        }],
    })
    cell_line_output = provider_dump(ContextExtraction(
        observation_id=cell_line_input["observation_id"],
        domain_profiles=["generic", "biomedical"],
        input_mode="fulltext_evidence_chain",
        context_factors=[{
            "factor_id": "cell_line", "raw_value": None, "status": "explicit",
            "evidence_anchor_ids": ["bio:A5"],
            "explicit_span": {
                "evidence_anchor_id": "bio:A5",
                "start_token_id": "bio:A5:T0", "end_token_id": "bio:A5:T0",
            },
            "confidence": .9,
        }, {
            "factor_id": "species", "raw_value": None, "status": "unknown",
            "evidence_anchor_ids": [], "confidence": 1.0,
        }],
        missing_critical_information=["species"],
    ))
    multi_input = attach_token_catalog({
        "observation_id": "example_multi_token",
        "input_mode": "fulltext_evidence_chain",
        "evidence_anchors": [{
            "anchor_id": "bio:A6", "text": "HCT116 and DLD-1 cells were compared.",
            "source_role": "current", "source_section": "Results",
        }],
    })
    multi_output = provider_dump(ContextExtraction(
        observation_id=multi_input["observation_id"],
        domain_profiles=["generic", "biomedical"],
        input_mode="fulltext_evidence_chain",
        context_factors=[{
            "factor_id": "cell_line", "raw_value": None, "status": "explicit",
            "evidence_anchor_ids": ["bio:A6"],
            "explicit_span": {
                "evidence_anchor_id": "bio:A6",
                "start_token_id": "bio:A6:T0", "end_token_id": "bio:A6:T4",
            },
            "confidence": .9,
        }],
    ))
    crc_input = attach_token_catalog({
        "observation_id": "example_crc",
        "input_mode": "fulltext_evidence_chain",
        "evidence_anchors": [{
            "anchor_id": "bio:A7", "text": "CRC samples showed the endpoint.",
            "source_role": "current", "source_section": "Results",
        }],
    })
    crc_output = provider_dump(ContextExtraction(
        observation_id=crc_input["observation_id"],
        domain_profiles=["generic", "biomedical"],
        input_mode="fulltext_evidence_chain",
        context_factors=[{
            "factor_id": "disease", "raw_value": None, "status": "explicit",
            "evidence_anchor_ids": ["bio:A7"],
            "explicit_span": {
                "evidence_anchor_id": "bio:A7",
                "start_token_id": "bio:A7:T0", "end_token_id": "bio:A7:T0",
            },
            "confidence": .9,
        }],
    ))
    unknown_input = attach_token_catalog({
        "observation_id": "example_biomedical_unknown",
        "input_mode": "fulltext_evidence_chain",
        "evidence_anchors": [{
            "anchor_id": "bio:A2", "text": "A549 cells showed an increased endpoint.",
            "source_role": "current", "source_section": "Results",
        }],
    })
    unknown_output = ContextExtraction(
        observation_id=unknown_input["observation_id"], domain_profiles=["generic", "biomedical"],
        input_mode="fulltext_evidence_chain",
        context_factors=[{
            "factor_id": "species", "raw_value": None, "normalized_value": None,
            "status": "unknown", "evidence_anchor_ids": [], "confidence": 1.0,
        }],
        missing_critical_information=["species"],
    )
    unknown_output = provider_dump(unknown_output)
    inferred_input = attach_token_catalog({
        "observation_id": "example_biomedical_inferred",
        "input_mode": "fulltext_evidence_chain",
        "evidence_anchors": [{
            "anchor_id": "bio:A3", "text": "CSN8 perturbation changed the endpoint.",
            "source_role": "setup", "source_section": "Results",
        }],
        "experimental_logic_chain": {
            "intervention_or_exposure": {
                "value": [{
                    "target_mention": "CSN8",
                    "intervention_type_raw": "perturbation",
                }],
                "authoritative_evidence_anchor_ids": ["bio:A3"],
            },
        },
    })
    inferred_output = ContextExtraction(
        observation_id=inferred_input["observation_id"],
        domain_profiles=["generic", "biomedical"],
        input_mode="fulltext_evidence_chain",
        context_factors=[{
            "factor_id": "intervention", "raw_value": None,
            "normalized_candidate": None, "normalized_value": None,
            "status": "inferred_from_local_chain",
            "evidence_anchor_ids": ["bio:A3"],
            "source_chain_node_ids": ["intervention_or_exposure"],
            "inference_rule": "compose_intervention_target_and_type",
            "raw_components": [
                {
                    "chain_node_id": "intervention_or_exposure",
                    "field_path": "target_mention", "surface": "CSN8",
                    "evidence_anchor_ids": ["bio:A3"],
                },
                {
                    "chain_node_id": "intervention_or_exposure",
                    "field_path": "intervention_type_raw", "surface": "perturbation",
                    "evidence_anchor_ids": ["bio:A3"],
                },
            ],
            "confidence": .9,
        }],
    )
    inferred_output = provider_dump(inferred_output)
    comparator_input = attach_token_catalog({
        "observation_id": "example_comparator",
        "input_mode": "fulltext_evidence_chain",
        "evidence_anchors": [{
            "anchor_id": "bio:A4", "text": "The control arm was measured in parallel.",
            "source_role": "setup", "source_section": "Methods",
        }],
        "experimental_logic_chain": {
            "comparator_or_control": {
                "value": {"control_arm_raw": "control"},
                "authoritative_evidence_anchor_ids": ["bio:A4"],
            },
        },
    })
    comparator_output = ContextExtraction(
        observation_id=comparator_input["observation_id"],
        domain_profiles=["generic", "biomedical"],
        input_mode="fulltext_evidence_chain",
        context_factors=[{
            "factor_id": "comparator", "raw_value": None,
            "status": "inferred_from_local_chain",
            "evidence_anchor_ids": ["bio:A4"],
            "source_chain_node_ids": ["comparator_or_control"],
            "inference_rule": "project_comparator_control_surface",
            "raw_components": [{
                "chain_node_id": "comparator_or_control",
                "field_path": "control_arm_raw", "surface": "control",
                "evidence_anchor_ids": ["bio:A4"],
            }],
            "confidence": .9,
        }],
    )
    comparator_output = provider_dump(comparator_output)
    examples = [
        {"description": "Explicit surface value with separate controlled normalization",
         "input": explicit_input, "output": explicit_output},
        {"description": "A549 is a cell_line span while species remains unknown",
         "input": cell_line_input, "output": cell_line_output},
        {"description": "Exact multi-token HCT116 and DLD-1 span preserves punctuation",
         "input": multi_input, "output": multi_output},
        {"description": "CRC remains the exact disease raw surface and is not expanded",
         "input": crc_input, "output": crc_output},
        {"description": "Two field-level components are deterministically composed within one intervention node",
         "input": inferred_input, "output": inferred_output},
        {"description": "Comparator provenance comes from a comparator/control node containing control",
         "input": comparator_input, "output": comparator_output},
        {"description": "Unknown remains unknown when the local evidence is silent",
         "input": unknown_input, "output": unknown_output},
    ]
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
    return {
        "extraction_examples": examples,
        "pair_example": {
            "description": "Compare only the two supplied validated extractions",
            "input": {
                "pair_id": "example_chemistry_pair",
                "claim_a_observation_id": "example_chemistry_a",
                "claim_b_observation_id": "example_chemistry_b",
            },
            "output": pair,
        },
    }
