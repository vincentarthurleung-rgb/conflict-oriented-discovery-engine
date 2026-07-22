"""Offline, fulltext-aware L2 re-adjudication and formal projection.

The projector only reads existing artifacts.  It never invokes retrieval,
providers, cleaners, or L1, and writes a new content-addressed projection.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl, iter_jsonl
from code_engine.normalization.adjudicator import adjudicate_entity_candidates
from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest
from code_engine.normalization.core_eligibility import core_graph_eligibility
from code_engine.normalization.intervention_semantics import apply_evidence_semantics
from code_engine.schemas.evidence_chain import EvidenceReasoningChain

from .profiles import FULLTEXT_EVIDENCE_PROJECTION


SCHEMA_VERSION = "fulltext_evidence_projection_v1.0.8"
ADJUDICATION_VERSION = "fulltext_l2_readjudication_v1.0.8"
CELL_LINE_SPECIES = {
    "hela": "human", "a549": "human", "hek293": "human", "293t": "human",
    "mcf7": "human", "mda-mb-231": "human", "hct116": "human", "sw480": "human",
    "u87": "human", "u251": "human", "ht29": "human", "pc3": "human",
    "4t1": "mouse", "b16": "mouse", "ct26": "mouse", "llc": "mouse",
    "nih3t3": "mouse", "raw264.7": "mouse",
}
SPECIES_MARKERS = {
    "human": ("human", "homo sapiens", "_human", "taxon:9606"),
    "mouse": ("mouse", "murine", "mus musculus", "_mouse", "taxon:10090"),
    "rat": ("rat", "rattus", "_rat", "taxon:10116"),
    "fly": ("drome", "drosophila", "taxon:7227"),
    "goat": ("caphi", "capra hircus", "taxon:9925"),
}


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        return list(iter_jsonl(path))
    except (OSError, ValueError, json.JSONDecodeError):
        return []


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _stable_hash(value: Any, prefix: str = "") -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return prefix + hashlib.sha256(raw.encode()).hexdigest()[:20]


def _norm(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _values(value: Any) -> list[Any]:
    if value in (None, "", [], {}):
        return []
    if not isinstance(value, list):
        value = [value]
    result = []
    for item in value:
        actual = item.get("value") if isinstance(item, dict) and "value" in item else item
        if actual not in (None, "", [], {}):
            result.append(actual)
    return result


def bind_observation_context(
    observation: dict[str, Any], consolidation: dict[str, Any] | None,
    chain: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Bind context by observation precedence and retain field provenance."""
    sources: list[tuple[str, dict[str, Any]]] = []
    explicit = observation.get("context_slots") or observation.get("context") or {}
    sources.append(("evidence_span", explicit if isinstance(explicit, dict) else {}))
    if chain:
        system = chain.get("experimental_system") or {}
        chain_context = {**system}
        interventions = chain.get("interventions") or []
        measurements = chain.get("measurements") or []
        comparators = chain.get("comparators") or []
        if interventions:
            chain_context.update({
                "treatment": [x.get("agent_raw") for x in interventions if x.get("agent_raw")],
                "dose": [x.get("dose") or x.get("concentration") for x in interventions if x.get("dose") or x.get("concentration")],
                "duration": [x.get("duration") or x.get("timing") for x in interventions if x.get("duration") or x.get("timing")],
            })
        if measurements:
            chain_context.update({
                "assay": [x.get("assay") for x in measurements if x.get("assay")],
                "measured_entity": [x.get("endpoint") for x in measurements if x.get("endpoint")],
            })
        if comparators:
            chain_context["comparison_arm"] = comparators
        sources.append(("experiment_chain", chain_context))
    if consolidation:
        consolidated = consolidation.get("consolidated_context") or {}
        sources.append(("context_consolidation", consolidated if isinstance(consolidated, dict) else {}))
    section = observation.get("section_provenance") or {}
    sources.append(("section_provenance", {
        "source_section": observation.get("section_type") or section.get("section_type"),
        "figure": observation.get("figure") or section.get("figure"),
        "table": observation.get("table") or section.get("table"),
    }))

    context: dict[str, Any] = {}
    audit: list[dict[str, Any]] = []
    for rank, (source, payload) in enumerate(sources, 1):
        for field, raw in payload.items():
            vals = _values(raw)
            if not vals:
                continue
            if field not in context:
                context[field] = vals[0] if len(vals) == 1 else vals
                audit.append({"field": field, "value": context[field], "source": source, "precedence": rank})
    species, species_source = infer_observation_species(context)
    if species:
        context["species"] = species
        context["species_source"] = species_source
    return context, audit


def infer_observation_species(context: dict[str, Any]) -> tuple[str | None, str]:
    explicit = " ".join(map(str, _values(context.get("species")))).casefold()
    for species, markers in SPECIES_MARKERS.items():
        if any(marker in explicit for marker in markers):
            return species, "explicit_observation_context"
    cell_text = " ".join(map(str, _values(context.get("cell_line")) + _values(context.get("cell_type")))).casefold()
    for line, species in CELL_LINE_SPECIES.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(line) + r"(?![a-z0-9])", cell_text):
            return species, "cell_line_registry"
    model = " ".join(map(str, _values(context.get("model_system")) + _values(context.get("disease_model")))).casefold()
    for species, markers in SPECIES_MARKERS.items():
        if any(marker in model for marker in markers):
            return species, "model_system"
    return None, "unknown"


def canonical_id_species(canonical_id: Any, canonical_name: Any = None, candidate_species: Any = None) -> str | None:
    text = " ".join(map(str, (canonical_id or "", canonical_name or "", candidate_species or ""))).casefold()
    for species, markers in SPECIES_MARKERS.items():
        if any(marker in text for marker in markers):
            return species
    # MONDO is a disease ontology, never a gene/protein taxonomy.
    if "mondo:" in text or "_mondo" in text:
        return "disease_ontology"
    # UniProt mnemonic suffixes encode an organism.  Treat unrecognised
    # suffixes as species-specific so an unknown-species observation cannot
    # accidentally select ARATH/BRAOL/etc. as a generic gene representation.
    if re.search(r"_[a-z0-9]{3,6}(?:\b|$)", str(canonical_name or "").casefold()):
        return "other_species"
    return None


def species_compatibility(
    evidence_species: str | None, canonical_species: str | None,
    ortholog_provenance: dict[str, Any] | None = None,
) -> tuple[str, str | None]:
    if not evidence_species:
        if canonical_species is not None:
            return "ambiguous", "species_unknown_specific_candidate"
        return "unknown", None
    if canonical_species is None:
        return "unspecified", None
    if evidence_species == canonical_species:
        return "compatible", None
    if ortholog_provenance:
        return "ortholog_projected", None
    return "incompatible", "species_incompatible_without_ortholog_provenance"


def _candidate_index(rows: Iterable[dict[str, Any]]) -> dict[str, list[EntityCandidate]]:
    result: dict[str, list[EntityCandidate]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in rows:
        try:
            candidate = EntityCandidate.model_validate(row)
        except Exception:
            continue
        key = _norm(row.get("surface"))
        identity = (key, str(candidate.canonical_id or candidate.candidate_id))
        if key and identity not in seen:
            result[key].append(candidate)
            seen.add(identity)
    return result


def _surface_variants(surface: str) -> list[str]:
    """Deterministic mention heads; never invent a biomedical identifier."""
    values = [surface]
    text = str(surface or "")
    acronym = re.search(r"\(([A-Z][A-Z0-9-]{1,12})\)", text)
    if acronym:
        values.append(acronym.group(1))
    if re.search(r"(?<![A-Za-z0-9])EMT(?![A-Za-z0-9])", text):
        values.append("EMT")
    if re.search(r"epithelial[- ](?:to[- ])?mesenchymal transition", text, re.I):
        values.extend(["EMT", "epithelial-mesenchymal transition"])
    cleaned = re.sub(
        r"\b(?:cmv-driven[- ]*)?(?:overexpression|overexpressed|silencing|silenced|knockdown|knockout|depletion|ablation)(?:\s+of)?\b",
        " ", text, flags=re.I,
    )
    cleaned = re.sub(r"\b(?:process(?:es)?|phenotype|induced by .*)\b", " ", cleaned, flags=re.I)
    if _norm(cleaned):
        values.append(cleaned)
    return list(dict.fromkeys(_norm(x) for x in values if _norm(x)))


def _candidate_pool(surface: str, index: dict[str, list[EntityCandidate]]) -> list[EntityCandidate]:
    pool: list[EntityCandidate] = []
    seen = set()
    variants = _surface_variants(surface)
    for variant in variants:
        for candidate in index.get(variant, []):
            identity = str(candidate.canonical_id or candidate.candidate_id)
            if identity not in seen:
                pool.append(candidate)
                seen.add(identity)
    # If an expanded phrase is present, reject acronym collisions whose label
    # and aliases do not contain that phrase (e.g. EMT as a gene alias).
    expanded_emt = any("epithelial mesenchymal transition" in x for x in variants) or (
        "emt" in variants and bool(re.search(r"\b(?:process|dormancy|hypoxia|mesenchymal)\b", surface, re.I))
    )
    if expanded_emt:
        pool = [x for x in pool if x.entity_type in {"phenotype", "biological_process", "pathway"} and "epithelial" in _norm(" ".join([str(x.canonical_name or ""), *x.aliases])) and "mesenchymal" in _norm(" ".join([str(x.canonical_name or ""), *x.aliases]))]
    if re.search(r"\b(?:overexpression|overexpressed|silencing|silenced|knockdown|knockout|depletion|ablation)\b", surface, re.I):
        molecular = [x for x in pool if x.entity_type in {"gene", "protein", "gene_or_protein", "protein_family"}]
        if molecular:
            pool = molecular
    return pool


def readjudicate_entity(
    observation: dict[str, Any], side: str, context: dict[str, Any],
    candidates: list[EntityCandidate], previous: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = str(observation.get(f"{side}_raw") or observation.get(f"{side}_raw_name") or observation.get(side) or "")
    evidence_species = context.get("species")
    prior_id = (previous or {}).get(f"{side}_canonical_id") or observation.get(f"{side}_canonical_id")
    prior_name = (previous or {}).get(f"{side}_canonical_name") or observation.get(f"{side}_canonical_name")
    prior_norm = ((previous or observation).get("normalization") or {}).get(side) or {}
    prior_decision = str(prior_norm.get("normalization_status") or (previous or observation).get(f"{side}_normalization_status") or "unresolved")
    decision = "ambiguous"
    selected: EntityCandidate | None = None
    reasons: list[str] = []
    if candidates:
        compatible_candidates = []
        for item in candidates:
            item_species = canonical_id_species(item.canonical_id, item.canonical_name, item.candidate_species)
            compatibility, _ = species_compatibility(evidence_species, item_species, item.ortholog_provenance)
            if compatibility not in {"incompatible", "ambiguous"}:
                compatible_candidates.append(item)
        candidates = compatible_candidates
    if candidates:
        request = EntityResolutionRequest(
            surface=raw, species_context=evidence_species,
            l1_entity_type_hint=observation.get(f"{side}_entity_type"),
            paper_id=str(observation.get("paper_id") or observation.get("pmid") or ""),
            claim_id=str(observation.get("claim_id") or ""), endpoint_role=side,
            relation=observation.get("relation_raw"), execute=False, network_enabled=False, api_enabled=False,
        )
        adjudication = adjudicate_entity_candidates(request, candidates)
        decision = adjudication.decision
        selected = adjudication.selected_candidate
        reasons = list(adjudication.decision_reasons) + list(adjudication.hard_exclusions)
        # A sole, exact, grounded and species-neutral cached candidate is the
        # requested safe fallback for unknown species.  This is not provider
        # top-hit guessing: ambiguity-producing alternatives were removed by
        # observation text and species constraints above.
        if decision != "accepted" and len(candidates) == 1:
            sole = candidates[0]
            sole_species = canonical_id_species(sole.canonical_id, sole.canonical_name, sole.candidate_species)
            if (
                sole.is_grounded and sole.final_score >= 0.9
                and (sole.provider_exact_match or sole.match_type in {"exact", "ontology_exact_synonym"})
                and sole_species is None
            ):
                decision, selected = "accepted", sole
                reasons = ["accepted_single_grounded_exact_species_neutral_candidate"]
    elif prior_id:
        prior_species = canonical_id_species(prior_id, prior_name, prior_norm.get("candidate_species"))
        compatibility, reason = species_compatibility(evidence_species, prior_species, prior_norm.get("ortholog_provenance"))
        # A species-neutral ontology/gene-family representation is the safe
        # fallback when observation species is unknown.  Only a species-
        # specific prior is blocked in that situation.
        decision = "accepted" if compatibility in {"compatible", "ortholog_projected", "unknown", "unspecified"} and prior_decision in {"resolved", "accepted", "resolved_runtime_hint"} else "ambiguous"
        reasons = [reason or f"prior_candidate_{compatibility}"]

    canonical_id = selected.canonical_id if selected and decision == "accepted" else prior_id if decision == "accepted" else None
    canonical_name = selected.canonical_name if selected and decision == "accepted" else prior_name if decision == "accepted" else None
    candidate_species = canonical_id_species(canonical_id, canonical_name, selected.candidate_species if selected else prior_norm.get("candidate_species"))
    ortholog = selected.ortholog_provenance if selected else prior_norm.get("ortholog_provenance")
    compatibility, species_reason = species_compatibility(evidence_species, candidate_species, ortholog)
    if species_reason:
        reasons.append(species_reason)
    if compatibility in {"incompatible", "ambiguous"}:
        decision, canonical_id, canonical_name = "ambiguous", None, None
    updated = dict(observation)
    updated[f"{side}_canonical_id"] = canonical_id or ""
    updated[f"{side}_canonical_name"] = canonical_name or raw
    updated[f"{side}_normalization_status"] = "resolved" if decision == "accepted" else "ambiguous"
    endpoint = dict(updated.get(f"{side}_endpoint") or {})
    endpoint.update({
        "canonical_id": canonical_id, "canonical_name": canonical_name,
        "resolution_status": "resolved" if decision == "accepted" else "ambiguous",
    })
    updated[f"{side}_endpoint"] = endpoint
    lineage = {
        "side": side,
        "previous_entity_decision": prior_decision,
        "previous_canonical_id": prior_id,
        "fulltext_entity_decision": decision,
        "fulltext_canonical_id": canonical_id,
        "changed": str(prior_id or "") != str(canonical_id or ""),
        "upgrade_reason": sorted(set(reasons)) or ["fulltext_context_revalidation"],
        "context_evidence": {"species": evidence_species, "species_source": context.get("species_source")},
        "species_compatibility": compatibility,
        "ortholog_provenance": ortholog,
        "adjudication_profile": FULLTEXT_EVIDENCE_PROJECTION.profile_id,
        "adjudication_version": ADJUDICATION_VERSION,
    }
    return updated, lineage


def _measurement_dimension(observation: dict[str, Any], chain: dict[str, Any] | None) -> str | None:
    existing = observation.get("measurement_dimension")
    if existing:
        return str(existing)
    object_text = str(observation.get("object_raw") or "").casefold()
    if any(marker in object_text for marker in ("emt", "mesenchymal transition", "migration", "invasion", "metast", "prolifer", "apopt", "survival", "viability")):
        return "phenotype"
    text = " ".join(str(x) for x in (
        observation.get("object_raw"), observation.get("relation_raw"),
        json.dumps((chain or {}).get("measurements") or [], ensure_ascii=False),
    )).casefold()
    for dimension, markers in {
        "phosphorylation": ("phosphorylat", "p-akt", "pakt"),
        "expression": ("expression", "mrna", "transcript", "protein level", "marker"),
        "activity": ("activity", "activation", "enzyme assay"),
        "localization": ("localization", "translocation", "nuclear"),
        "abundance": ("abundance", "level", "concentration"),
        "phenotype": ("emt", "migration", "invasion", "metast", "prolifer", "apopt", "survival", "viability"),
    }.items():
        if any(marker in text for marker in markers):
            return dimension
    return None


def build_reasoning_chain(
    observation: dict[str, Any], context: dict[str, Any], chain: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    enriched = dict(observation)
    enriched["context"] = context
    enriched["context_slots"] = context
    enriched["evidence_scope"] = "fulltext"
    enriched["active_scientific_profile"] = FULLTEXT_EVIDENCE_PROJECTION.profile_id
    # Do not carry the abstract/reentry gate's false value into the semantic
    # adjudicator.  This is a candidate flag; the deterministic fulltext core
    # gate below remains authoritative.
    enriched["conflict_eligible"] = True
    dimension = _measurement_dimension(enriched, chain)
    if dimension:
        enriched["measurement_dimension"] = dimension
    enriched = apply_evidence_semantics(enriched)
    sign = enriched.get("derived_causal_sign")
    chain_interventions = (chain or {}).get("interventions") or []
    grouped_intervention = len(chain_interventions) > 1
    reviewable_group = grouped_intervention or any("scalar causal sign is unavailable" in str(x) for x in ((chain or {}).get("causal_design") or {}).get("classification_basis", []))
    if reviewable_group:
        sign = None
        enriched["derived_causal_sign"] = None
        enriched["conflict_eligible"] = False
    evidence_id = str(enriched.get("observation_id") or enriched.get("claim_id") or "")
    experiment_id = str((chain or {}).get("chain_id") or enriched.get("chunk_id") or evidence_id)
    paper_id = str(enriched.get("pmid") or enriched.get("paper_id") or (chain or {}).get("paper_id") or "")
    family_id = _stable_hash([paper_id, experiment_id], "ef_")
    anchors = (chain or {}).get("evidence_anchors") or []
    if not anchors and enriched.get("evidence_sentence"):
        anchors = [{
            "section": enriched.get("section_type") or (enriched.get("section_provenance") or {}).get("section_type"),
            "sentence_text": enriched.get("evidence_sentence"), "chunk_id": enriched.get("chunk_id"),
            "figure": enriched.get("figure"), "table": enriched.get("table"),
        }]
    intervention_derived = str(enriched.get("evidence_design") or "") in {
        "gain_of_function", "loss_of_function", "pharmacological_intervention", "rescue",
    }
    complete = bool(not reviewable_group and sign in {-1, 1} and dimension and anchors and (not intervention_derived or enriched.get("intervention_type")))
    warnings = []
    if sign not in {-1, 1}: warnings.append("derived_causal_sign_missing")
    if not dimension: warnings.append("measurement_dimension_missing")
    if not anchors: warnings.append("provenance_anchor_missing")
    if intervention_derived and not enriched.get("intervention_type"): warnings.append("intervention_scope_unresolved")
    if grouped_intervention: warnings.append("multi_intervention_group_not_projected_as_independent_causal_edges")
    if reviewable_group: warnings.append("reviewable_observation_strict_core_blocked")
    payload = EvidenceReasoningChain(
        chain_id=_stable_hash([paper_id, evidence_id, experiment_id], "erc_"), paper_id=paper_id,
        pmid=str(enriched.get("pmid") or "") or None, pmcid=str(enriched.get("pmcid") or "") or None,
        research_question=(chain or {}).get("research_question"), author_claim=enriched.get("evidence_sentence"),
        experimental_design=(chain or {}).get("causal_design") or {}, experiment_id=experiment_id,
        evidence_family_id=family_id, interventions=(chain or {}).get("interventions") or [],
        intervention_target=enriched.get("intervention_target"), intervention_type=enriched.get("intervention_type"),
        intervention_sign=(enriched.get("evidence_semantics") or {}).get("intervention_sign"),
        comparison_arm=(chain or {}).get("comparators") or [], measurements=(chain or {}).get("measurements") or [],
        measured_entity=enriched.get("measured_entity") or enriched.get("object_raw"), measurement_dimension=dimension,
        observed_results=(chain or {}).get("observed_results") or [], observed_outcome_sign=enriched.get("observed_outcome_sign"),
        lexical_direction=str(enriched.get("direction") or "unknown"), derived_causal_sign=sign,
        derived_relation="positive_regulation" if sign == 1 else "negative_regulation" if sign == -1 else None,
        final_formal_polarity="positive" if sign == 1 else "negative" if sign == -1 else "unknown",
        direction_provenance=enriched.get("causal_direction_provenance") or "unresolved",
        author_interpretation=(chain or {}).get("author_interpretation") or {},
        system_interpretation="intervention algebra is authoritative" if intervention_derived else "validated direct causal sign",
        conclusion_scope=enriched.get("section_type"), context=context, provenance=anchors,
        supporting_evidence_ids=[evidence_id] if evidence_id else [], uncertainty=warnings, warnings=warnings,
        chain_complete=complete,
    ).model_dump(mode="json")
    enriched.update({
        "reasoning_chain_id": payload["chain_id"], "evidence_family_id": family_id,
        "final_formal_polarity": payload["final_formal_polarity"],
        "direction": payload["final_formal_polarity"],
        "polarity": payload["final_formal_polarity"],
        "direction_source": payload["direction_provenance"], "reasoning_chain_complete": complete,
    })
    return enriched, payload


def _relation_axis(row: dict[str, Any]) -> str:
    family = str(row.get("formal_relation_family") or row.get("relation_family") or "").casefold()
    if "regulation" in family or row.get("derived_causal_sign") in {-1, 1}:
        return "regulation"
    return family or "unknown"


def _context_class(context: dict[str, Any]) -> str:
    fields = ("species", "cell_line", "cell_type", "tissue", "disease_model", "disease_subtype", "genotype")
    return _stable_hash({key: context.get(key) for key in fields if context.get(key)}, "ctx_")


def _contexts_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for key in ("species", "cell_line", "cell_type", "tissue", "disease_model", "disease_subtype", "genotype"):
        a = {_norm(x) for x in _values(left.get(key)) if _norm(x)}
        b = {_norm(x) for x in _values(right.get(key)) if _norm(x)}
        if a and b and a.isdisjoint(b):
            return False
    return True


def aggregate_canonical_edges(observations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        if row.get("formal_core_graph_eligible"):
            base_groups[(
                str(row.get("subject_canonical_id")), str(row.get("object_canonical_id")), _relation_axis(row),
                str(row.get("final_formal_polarity")), str(row.get("measurement_dimension") or ""),
            )].append(row)
    groups: list[tuple[tuple[str, ...], list[dict[str, Any]], dict[str, Any]]] = []
    for base, rows in base_groups.items():
        partitions: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []
        for row in rows:
            context = row.get("context") or {}
            for members, representative in partitions:
                if _contexts_compatible(context, representative):
                    members.append(row)
                    representative.update({k: v for k, v in context.items() if k not in representative})
                    break
            else:
                partitions.append(([row], dict(context)))
        groups.extend((base, members, representative) for members, representative in partitions)
    exact_seen: set[tuple[str, ...]] = set()
    exact_merges = []
    edges = []
    for base, members, representative in groups:
        key = (*base, _context_class(representative))
        evidence = []
        for row in members:
            exact = key + (
                str(row.get("pmid") or row.get("paper_id") or ""), str(row.get("evidence_family_id") or ""),
                _norm(row.get("evidence_sentence")),
            )
            if exact in exact_seen:
                exact_merges.append({"observation_id": row.get("observation_id"), "action": "exact_duplicate_merged", "canonical_key": list(key)})
                continue
            exact_seen.add(exact)
            evidence.append(row)
        if not evidence:
            continue
        edge_id = _stable_hash(key, "ce_")
        edges.append({
            "schema_version": "canonical_edge_evidence_family_v1", "canonical_edge_id": edge_id,
            "subject_canonical_id": key[0], "object_canonical_id": key[1], "relation_axis": key[2],
            "polarity": key[3], "measurement_dimension": key[4] or None, "context_class": key[5],
            "evidence_record_ids": [str(x.get("observation_id") or x.get("claim_id")) for x in evidence],
            "evidence_family_ids": sorted({str(x.get("evidence_family_id")) for x in evidence}),
            "evidence_count": len(evidence),
            "independent_paper_count": len({str(x.get("pmid") or x.get("paper_id")) for x in evidence}),
            "experiment_family_count": len({str(x.get("evidence_family_id")) for x in evidence}),
            "conflict_eligible": all(x.get("conflict_eligible") is True for x in evidence),
        })
        for row in evidence:
            row["canonical_edge_id"] = edge_id
    return sorted(edges, key=lambda x: x["canonical_edge_id"]), exact_merges


def build_conflict_bundles(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        # Polarity intentionally is not part of bundle identity.
        key = (edge["subject_canonical_id"], edge["object_canonical_id"], edge["relation_axis"], str(edge.get("measurement_dimension") or ""), edge["context_class"])
        grouped[key].append(edge)
    result = []
    for key, members in grouped.items():
        polarities = sorted({x["polarity"] for x in members})
        eligible = all(x.get("conflict_eligible") for x in members)
        result.append({
            "schema_version": "fulltext_conflict_bundle_audit_v1", "bundle_id": _stable_hash(key, "rb_"),
            "bundle_identity": {"subject": key[0], "object": key[1], "relation_axis": key[2], "measurement_dimension": key[3] or None, "context_class": key[4]},
            "canonical_edge_ids": [x["canonical_edge_id"] for x in members], "polarities": polarities,
            "conflict_eligible": eligible, "adjudication": "true_conflict_candidate" if eligible and polarities == ["negative", "positive"] else "concordant_support",
        })
    return sorted(result, key=lambda x: x["bundle_id"])


def project_fulltext_run(source_run: str | Path, output_root: str | Path | None = None) -> dict[str, Any]:
    source = Path(source_run).resolve()
    artifacts = source / "artifacts"
    observations = _rows(artifacts / "l2_fulltext_observations.jsonl")
    if not observations:
        observations = _rows(artifacts / "l35_fulltext_l1_claims.jsonl")
    consolidations = {str(x.get("claim_id")): x for x in _rows(artifacts / "fulltext_context_consolidations.jsonl")}
    chains = {str(x.get("chain_id")): x for x in _rows(artifacts / "experimental_evidence_chains.jsonl")}
    links: dict[str, list[str]] = defaultdict(list)
    for link in _rows(artifacts / "claim_evidence_links.jsonl"):
        links[str(link.get("claim_id"))].append(str(link.get("chain_id")))
    candidates = _candidate_index(_rows(artifacts / "entity_resolution_candidates.jsonl"))
    abstract = _rows(artifacts / "l2_retained_observations.jsonl")
    abstract_by_id = {str(x.get("observation_id") or x.get("claim_id")): x for x in abstract if str(x.get("evidence_source") or "abstract") != "fulltext"}
    input_identity = {
        "source": str(source), "schema": SCHEMA_VERSION,
        "observation_ids": [str(x.get("observation_id") or x.get("claim_id")) for x in observations],
        "context_hashes": [x.get("source_record_hash") for x in consolidations.values()],
    }
    digest = _stable_hash(input_identity)
    root = Path(output_root).resolve() if output_root else source.parent
    output = root / f"{source.name}__fulltext_evidence_projection_{digest}"
    out = output / "artifacts"
    manifest_path = output / "projection_manifest.json"
    existing_summary_path = out / "fulltext_l2_readjudication_summary.json"
    if manifest_path.is_file() and existing_summary_path.is_file():
        manifest = _json(manifest_path)
        if manifest.get("status") == "completed" and manifest.get("content_identity") == digest:
            existing = _json(existing_summary_path)
            return {**existing, "output_run": str(output), "reused_completed_projection": True}
    out.mkdir(parents=True, exist_ok=True)

    projected = []
    entity_audit = []
    context_audit = []
    species_audit = []
    reasoning = []
    for original in observations:
        claim_id = str(original.get("claim_id") or original.get("observation_id") or "")
        linked_chain = chains.get(links.get(claim_id, [""])[0]) if links.get(claim_id) else None
        context, context_rows = bind_observation_context(original, consolidations.get(claim_id), linked_chain)
        linked_abstract_ids = original.get("linked_abstract_observation_ids") or []
        previous_id = str(original.get("matched_abstract_observation_id") or (linked_abstract_ids[0] if linked_abstract_ids else ""))
        previous = abstract_by_id.get(previous_id)
        row = dict(original)
        lineages = []
        for side in ("subject", "object"):
            surface = str(row.get(f"{side}_raw") or row.get(f"{side}_raw_name") or row.get(side) or "")
            row, lineage = readjudicate_entity(row, side, context, _candidate_pool(surface, candidates), previous)
            lineages.append(lineage)
            entity_audit.append({
                "schema_version": "fulltext_entity_upgrade_audit_v1", "abstract_observation_id": previous_id or None,
                "fulltext_observation_id": row.get("observation_id") or claim_id, **lineage,
            })
            species_audit.append({
                "schema_version": "fulltext_species_compatibility_audit_v1", "fulltext_observation_id": row.get("observation_id") or claim_id,
                "side": side, "evidence_species": context.get("species"), "canonical_id": lineage.get("fulltext_canonical_id"),
                "compatibility": lineage.get("species_compatibility"), "ortholog_provenance": lineage.get("ortholog_provenance"),
                "blocked": lineage.get("species_compatibility") in {"incompatible", "ambiguous"},
            })
        row["entity_upgrade_lineage"] = lineages
        row["source_observation_id"] = previous_id or None
        row["supersedes"] = previous_id or None
        row["upgrades"] = previous_id or None
        row["effective_formal_observation_id"] = row.get("observation_id") or claim_id
        row, chain_payload = build_reasoning_chain(row, context, linked_chain)
        endpoints_resolved = all(bool(row.get(f"{side}_canonical_id")) for side in ("subject", "object"))
        row["graph_observation_eligible"] = bool(
            endpoints_resolved
            and chain_payload["chain_complete"]
            and row.get("scientific_edge_layer") == "strict_causal_core"
        )
        gate = core_graph_eligibility(row)
        if not chain_payload["chain_complete"]:
            gate = {**gate, "eligible": False, "conflict_eligible": False, "reason": "missing_evidence_reasoning_chain", "reasons": list(dict.fromkeys([*(gate.get("reasons") or []), "missing_evidence_reasoning_chain"]))}
        semantic_layer = str(row.get("scientific_edge_layer") or "causal_reviewable")
        non_core_layer = semantic_layer if semantic_layer in {
            "intervention_observation", "rescue_supported", "association", "differential_expression", "context_only", "audit_rejected",
        } else "causal_reviewable"
        semantic_tags = set(["intervention"] if row.get("intervention_type") else [])
        if context:
            semantic_tags.add("narrow_context")
        if re.search(r"\b(?:and|or)\b|[,;/+]", str(row.get("object_raw") or ""), re.I):
            semantic_tags.add("multi_endpoint")
        if context.get("cell_line"):
            semantic_tags.add("single_cell_line")
        if context.get("model_system"):
            semantic_tags.add("animal_model")
        row.update({
            "core_gate": gate, "formal_core_graph_eligible": bool(gate["eligible"]),
            "conflict_eligible": bool(gate["conflict_eligible"]),
            "primary_layer": "strict_causal_core" if gate["eligible"] else non_core_layer,
            "semantic_tags": sorted(semantic_tags),
            "core_exclusion_reasons": [] if gate["eligible"] else gate.get("reasons") or [gate.get("reason")],
            "formal_relation": gate.get("formal_relation"), "formal_relation_family": gate.get("relation_family"),
        })
        projected.append(row)
        reasoning.append(chain_payload)
        context_audit.append({
            "schema_version": "fulltext_context_binding_audit_v1", "fulltext_observation_id": row.get("observation_id") or claim_id,
            "experiment_id": chain_payload["experiment_id"], "context": context, "bindings": context_rows,
        })

    edges, exact_merges = aggregate_canonical_edges(projected)
    bundles = build_conflict_bundles(edges)
    core = [x for x in projected if x.get("formal_core_graph_eligible")]
    reviewable = [x for x in projected if not x.get("formal_core_graph_eligible")]
    before = _json(artifacts / "fulltext_reentry_summary.json")
    safety = {
        "wrong_species_canonical_entity_in_strict_core": sum(any(a["fulltext_observation_id"] == (x.get("observation_id") or x.get("claim_id")) and a["blocked"] for a in species_audit) for x in core),
        "unresolved_fallback_in_strict_core": sum(any(str(x.get(f"{s}_canonical_id") or "").startswith(("RUN:", "LOCAL:")) or not x.get(f"{s}_canonical_id") for s in ("subject", "object")) for x in core),
        "sample_condition_endpoint_in_strict_core": sum("sample_context_endpoint" in (x.get("core_exclusion_reasons") or []) for x in core),
        "association_projected_as_regulation": sum("association_projected_as_regulation" in (x.get("core_exclusion_reasons") or []) for x in core),
        "direction_provenance_overwrite": sum(x.get("derived_causal_sign") in {-1, 1} and x.get("final_formal_polarity") != ("positive" if x["derived_causal_sign"] == 1 else "negative") for x in projected),
        "missing_measurement_projection_in_strict_core": sum(not x.get("measurement_dimension") for x in core),
        "strict_core_bypassing_conflict_bundle": sum(not any(x.get("canonical_edge_id") in b["canonical_edge_ids"] for b in bundles) for x in core),
    }
    l1_account = _json(artifacts / "fulltext_l1_v2_summary.json")
    retrieval_account = _json(artifacts / "l35_fulltext_retrieval_summary.json")
    calls = {
        "schema_version": "fulltext_stage_call_accounting_v1",
        "current_abstract_l1_calls": 0,
        "fulltext_l1_calls_in_source_run": int(l1_account.get("api_calls_made") or 0),
        "current_projection_fulltext_l1_calls": 0,
        "retrieval_calls_in_source_run": int(retrieval_account.get("download_attempted_count") or 0),
        "current_projection_retrieval_calls": 0,
        "download_calls_in_source_run": int(retrieval_account.get("download_attempted_count") or 0),
        "current_projection_download_calls": 0,
        "llm_cleaner_calls": 0, "provider_network_calls": 0,
    }
    linkage = []
    abstract_link_counts = Counter(str(x.get("source_observation_id") or "") for x in projected if x.get("source_observation_id"))
    for row in projected:
        abstract_id = row.get("source_observation_id")
        changed = any(x.get("fulltext_observation_id") == (row.get("observation_id") or row.get("claim_id")) and x.get("changed") for x in entity_audit)
        abstract_row = abstract_by_id.get(str(abstract_id or "")) or {}
        old_direction = str(abstract_row.get("direction") or abstract_row.get("polarity") or "").casefold()
        new_direction = str(row.get("final_formal_polarity") or row.get("direction") or "").casefold()
        if not abstract_id:
            linkage_type = "fulltext_only"
        elif abstract_link_counts[str(abstract_id)] > 1:
            linkage_type = "split_by_fulltext"
        elif not row.get("formal_core_graph_eligible"):
            linkage_type = "unsupported_by_fulltext"
        elif {old_direction, new_direction} == {"positive", "negative"}:
            linkage_type = "contradicted_by_fulltext"
        elif changed:
            linkage_type = "corrected_by_fulltext"
        elif row.get("context"):
            linkage_type = "refined_by_fulltext"
        else:
            linkage_type = "confirmed_by_fulltext"
        linkage.append({
            "schema_version": "abstract_fulltext_linkage_v1", "parent_abstract_run_id": row.get("parent_abstract_run_id"),
            "source_abstract_observation_id": abstract_id, "source_paper_id": row.get("paper_id"),
            "linkage_type": linkage_type, "linkage_reason": "deterministic_fulltext_re_adjudication",
            "abstract_prior_candidates": row.get("abstract_prior_candidates") or [],
            "fulltext_effective_observation_id": row.get("observation_id") or row.get("claim_id"),
        })
    summary = {
        "schema_version": "fulltext_l2_readjudication_summary_v1", "source_run": str(source),
        "projection_run": str(output), "adjudication_profile": FULLTEXT_EVIDENCE_PROJECTION.profile_id,
        "abstract_decisions_reused_as_prior": sum(bool(x.get("abstract_observation_id")) for x in entity_audit),
        "fulltext_decisions_changed": sum(bool(x.get("changed")) for x in entity_audit),
        "canonical_id_corrected": sum(bool(x.get("previous_canonical_id") and x.get("fulltext_canonical_id") and x["previous_canonical_id"] != x["fulltext_canonical_id"]) for x in entity_audit),
        "species_conflicts_blocked": sum(bool(x["blocked"]) for x in species_audit),
        "derived_sign_corrections": sum(
            x.get("derived_causal_sign") in {-1, 1}
            and str((x.get("evidence_semantics") or {}).get("lexical_direction") or "unknown") in {"positive", "negative"}
            and x.get("final_formal_polarity") != (x.get("evidence_semantics") or {}).get("lexical_direction")
            for x in projected
        ),
        "exact_duplicate_merges": len(exact_merges),
        "strict_core_observations_before": int(before.get("core_seed_relation_count", 0) or 0),
        "strict_core_observations_after": len(core), "unique_canonical_edges_after": len(edges),
        "evidence_records_after": len(projected), "reviewable_evidence_after": len(reviewable),
        "conflict_candidates_after": sum(x["adjudication"] == "true_conflict_candidate" for x in bundles),
        "true_conflicts_after": sum(x["adjudication"] == "true_conflict_candidate" for x in bundles),
        "safety_violations": safety, "status": "completed",
    }
    upgrade_summary = {
        "schema_version": "abstract_fulltext_upgrade_summary_v1", "evidence_scope": "fulltext",
        "active_scientific_profile": FULLTEXT_EVIDENCE_PROJECTION.profile_id,
        "historical_abstract_preserved": True, "source_artifacts_modified": False,
        "linked_upgrade_count": sum(bool(x.get("abstract_observation_id")) for x in entity_audit),
    }
    atomic_write_jsonl(out / "fulltext_projected_observations.jsonl", projected)
    atomic_write_jsonl(out / "fulltext_entity_upgrade_audit.jsonl", entity_audit)
    atomic_write_jsonl(out / "evidence_reasoning_chains.jsonl", reasoning)
    atomic_write_jsonl(out / "fulltext_context_binding_audit.jsonl", context_audit)
    atomic_write_jsonl(out / "fulltext_species_compatibility_audit.jsonl", species_audit)
    atomic_write_jsonl(out / "canonical_edge_evidence_families.jsonl", edges)
    atomic_write_jsonl(out / "fulltext_conflict_bundle_audit.jsonl", bundles)
    atomic_write_jsonl(out / "abstract_fulltext_linkage_audit.jsonl", linkage)
    atomic_write_jsonl(out / "experimental_evidence_chains.jsonl", reasoning)
    atomic_write_json(out / "fulltext_l2_readjudication_summary.json", summary)
    atomic_write_json(out / "fulltext_core_projection_summary.json", {
        "schema_version": "fulltext_core_projection_summary_v1", "primary_layer_count": dict(Counter(x["primary_layer"] for x in projected)),
        "semantic_tag_count": dict(Counter(tag for x in projected for tag in x.get("semantic_tags") or [])),
        "formal_core_observation_count": len(core), "canonical_edge_count": len(edges), "evidence_record_count": len(projected),
        "safety_violations": safety,
    })
    atomic_write_json(out / "abstract_fulltext_upgrade_summary.json", upgrade_summary)
    atomic_write_json(out / "offline_call_accounting.json", calls)
    atomic_write_json(out / "fulltext_stage_call_accounting.json", calls)
    report = [
        "# Fulltext pipeline consistency report", "", f"- Schema: `{SCHEMA_VERSION}`",
        f"- Source run immutable: `{source}`", f"- Active profile: `{FULLTEXT_EVIDENCE_PROJECTION.profile_id}`",
        f"- Evidence records: {len(projected)}", f"- Formal core observations: {len(core)}",
        f"- Canonical edges: {len(edges)}", f"- Reviewable observations: {len(reviewable)}",
        f"- Conflict candidates: {summary['conflict_candidates_after']}",
        f"- Calls made by this projection stage: 0", "", "## Safety", "",
        *[f"- {key}: {value}" for key, value in safety.items()], "",
        "No source artifact or active Atlas projection was modified.",
    ]
    (out / "fulltext_pipeline_consistency_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (out / "fulltext_end_to_end_consistency_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    atomic_write_json(output / "projection_manifest.json", {
        "schema_version": SCHEMA_VERSION, "status": "completed", "source_run": str(source),
        "content_identity": digest, "immutable": True, "network_used": False, "api_used": False,
        "atlas_published": False, "active_projection_changed": False,
    })
    return {**summary, "output_run": str(output), "linkage_count": len(linkage)}


__all__ = [
    "ADJUDICATION_VERSION", "SCHEMA_VERSION", "aggregate_canonical_edges", "bind_observation_context",
    "build_conflict_bundles", "build_reasoning_chain", "canonical_id_species", "infer_observation_species",
    "project_fulltext_run", "readjudicate_entity", "species_compatibility",
]
