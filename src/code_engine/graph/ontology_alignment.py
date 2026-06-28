"""Resolver-cascade integration for Layer 2 ontology alignment."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from typing import Any, Dict, List, Tuple

from code_engine.schemas import NormalizedEntity
from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.normalization.models import NormalizationDecision
from code_engine.normalization.resolver import ResolverCascade
from code_engine.domain.router import default_domain_router


def _decision_to_entity(decision: NormalizationDecision) -> NormalizedEntity:
    if decision.canonical_name:
        canonical_name = decision.canonical_name.upper()
    elif decision.normalization_status != "empty_or_invalid" and decision.normalized_surface:
        canonical_name = decision.normalized_surface.upper()
    else:
        canonical_name = "UNSPECIFIED"
    return NormalizedEntity(
        raw_term=decision.raw_text,
        canonical_name=canonical_name,
        canonical_term=decision.canonical_name,
        canonical_id=decision.canonical_id,
        entity_type=decision.entity_type,
        semantic_level=decision.semantic_level,
        external_ids=decision.external_ids,
        relations=[relation.model_dump() for relation in decision.relations],
        normalization_status=decision.normalization_status,
        resolver=decision.resolver,
        match_type=decision.match_type,
        decision_reason=decision.decision_reason,
        allow_high_confidence_graph_use=decision.allow_high_confidence_graph_use,
        warnings=list(decision.warnings),
        candidates=[candidate.model_dump() for candidate in decision.candidates],
        mapping_method=decision.match_type,
        confidence=decision.confidence,
        domain_id=decision.domain_id,
        entity_registry_profile=decision.entity_registry_profile,
        resolver_policy_id=decision.resolver_policy_id,
        domain_specific_resolution_used=decision.domain_specific_resolution_used,
        domain_resolution_warnings=decision.domain_resolution_warnings,
        candidate_count=decision.candidate_count,
        candidate_provider_names=decision.candidate_provider_names,
        selected_candidate_id=decision.selected_candidate_id,
        entity_resolution_status=decision.entity_resolution_status,
        requires_manual_review=decision.requires_manual_review,
        audit_ref=decision.audit_ref,
    )


def _legacy_synonym_entity(token: str, synonym_map: Dict[str, str] | None) -> NormalizedEntity:
    """Reproduce synonym/uppercase behavior only for explicit compatibility runs."""

    lexical = normalize_lexical_surface(str(token or ""))
    if lexical.invalid:
        return NormalizedEntity(
            raw_term=lexical.raw_text,
            canonical_name="UNSPECIFIED",
            normalization_status="empty_or_invalid",
            resolver="legacy_synonym_only",
            match_type="legacy_invalid",
            mapping_method="legacy_invalid",
            confidence=0.0,
            allow_high_confidence_graph_use=False,
            warnings=[*lexical.warnings, "legacy_synonym_only_mode"],
        )
    aliases = {str(key).casefold(): str(value) for key, value in (synonym_map or {}).items()}
    canonical = aliases.get(lexical.normalized_surface, lexical.normalized_surface.upper())
    matched = lexical.normalized_surface in aliases
    return NormalizedEntity(
        raw_term=lexical.raw_text,
        canonical_name=canonical.upper(),
        canonical_term=canonical,
        normalization_status="resolved",
        resolver="legacy_synonym_only",
        match_type="legacy_synonym_map" if matched else "legacy_uppercase_fallback",
        mapping_method="legacy_synonym_map" if matched else "legacy_uppercase_fallback",
        confidence=0.7 if matched else 0.3,
        allow_high_confidence_graph_use=True,
        warnings=["legacy_synonym_only_mode", *lexical.warnings],
    )


def clean_semantic_token(
    token: str,
    synonym_map: Dict[str, str] | None = None,
    *,
    resolver: ResolverCascade | None = None,
    legacy_synonym_only: bool = False,
    context: dict[str, Any] | None = None,
) -> NormalizedEntity:
    """Normalize one token; ResolverCascade is the default mainline path."""

    if legacy_synonym_only:
        return _legacy_synonym_entity(token, synonym_map)
    decision = (resolver or ResolverCascade()).resolve_entity(str(token or ""), context=context)
    entity = _decision_to_entity(decision)
    if synonym_map and decision.normalization_status == "unresolved_fallback" and decision.normalized_surface in synonym_map:
        entity.warnings.append("legacy_synonym_available_but_not_accepted_as_registry_identity")
    return entity


def _stable_id(*parts: Any) -> str:
    return hashlib.md5("_".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]


def extract_normalized_observations(
    l1_5_input_dir: str,
    synonym_map: Dict[str, str] | None,
    forbidden_keywords: List[str] | None,
    *,
    resolver: ResolverCascade | None = None,
    resolver_cascade: bool = True,
    legacy_synonym_only: bool = False,
    registry_path: str | None = None,
    run_dir: str | None = None,
    execute: bool = False,
    network_enabled: bool = False,
    api_enabled: bool = False,
    entity_network_lookup: bool = False,
    entity_llm_proposer: bool = False,
    domain_profile: dict[str, Any] | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load L1.5 tuples and attach complete subject/object decisions."""

    if legacy_synonym_only:
        resolver_cascade = False
    if not resolver_cascade and not legacy_synonym_only:
        raise ValueError("Resolver cascade may only be disabled with legacy_synonym_only=True")
    active_resolver = resolver
    if resolver_cascade and active_resolver is None:
        active_resolver = ResolverCascade(registry_path=registry_path, run_dir=run_dir, execute=execute, network_enabled=network_enabled, api_enabled=api_enabled, entity_network_lookup=entity_network_lookup, entity_llm_proposer=entity_llm_proposer, domain_id=(domain_profile or {}).get("domain_id", "general_biomedical"), entity_registry_profile=(domain_profile or {}).get("entity_registry_profile", "general_entity_resolution_hub"), resolver_policy_id=(domain_profile or {}).get("resolver_policy_id", "conservative_resolver_v2"))

    observations: List[Dict[str, Any]] = []
    audit: List[Dict[str, Any]] = []
    forbidden = [kw.lower() for kw in (forbidden_keywords or [])]

    for fname in sorted(os.listdir(l1_5_input_dir)):
        if not fname.endswith("_refined.json"):
            continue
        with open(os.path.join(l1_5_input_dir, fname), "r", encoding="utf-8") as handle:
            l1_data = json.load(handle)

        asset_id = l1_data.get("asset_id", fname.replace("_refined.json", ""))
        doi_str = str(l1_data.get("doi", "N/A")).strip()
        title_str = str(l1_data.get("article_title", "N/A")).strip()
        belief_weight = float(l1_data.get("belief_weight", 0.6))

        for chunk in l1_data.get("chunks_extracted", []):
            chunk_id = str(chunk.get("chunk_index", "unknown"))
            for sample_idx, sample in enumerate(chunk.get("raw_samples", [])):
                if "causal_tuples" not in sample:
                    continue
                for node_idx, node in enumerate(sample["causal_tuples"]):
                    sub_raw = str(node.get("subject", "")).strip()
                    obj_raw = str(node.get("object", "")).strip()
                    sign = node.get("relation_sign", 1)
                    evidence = str(node.get("evidence_sentence", "")).strip()
                    if any(kw in sub_raw.lower() or kw in obj_raw.lower() for kw in forbidden):
                        continue
                    if sign not in (-1, 0, 1):
                        continue

                    fingerprint = dict(node.get("prompt_fingerprint") or {})
                    node_domain = str(node.get("domain_id") or fingerprint.get("domain_id") or "general_biomedical")
                    domain_profile = default_domain_router().resolve(node_domain)
                    node_resolver = active_resolver
                    if resolver_cascade and domain_profile and (
                        node_resolver is None or node_resolver.domain_id != domain_profile.domain_id
                    ):
                        node_resolver = ResolverCascade(
                            domain_id=domain_profile.domain_id,
                            entity_registry_profile=domain_profile.entity_registry_profile,
                            resolver_policy_id=domain_profile.resolver_policy_id,
                            run_dir=run_dir, execute=execute, network_enabled=network_enabled,
                            api_enabled=api_enabled, entity_network_lookup=entity_network_lookup,
                            entity_llm_proposer=entity_llm_proposer,
                        )
                    sub_norm = clean_semantic_token(
                        sub_raw,
                        synonym_map,
                        resolver=node_resolver,
                        legacy_synonym_only=legacy_synonym_only,
                        context={"expected_entity_type": node.get("subject_type"), "context_text": evidence, "paper_id": asset_id, "claim_id": node.get("claim_id")},
                    )
                    obj_norm = clean_semantic_token(
                        obj_raw,
                        synonym_map,
                        resolver=node_resolver,
                        legacy_synonym_only=legacy_synonym_only,
                        context={"expected_entity_type": node.get("object_type"), "context_text": evidence, "paper_id": asset_id, "claim_id": node.get("claim_id")},
                    )
                    audit.extend([
                        {**sub_norm.model_dump(), "role": "subject", "source_asset": asset_id},
                        {**obj_norm.model_dump(), "role": "object", "source_asset": asset_id},
                    ])
                    if "UNSPECIFIED" in [sub_norm.canonical_name, obj_norm.canonical_name]:
                        continue

                    graph_usable = bool(
                        sub_norm.allow_high_confidence_graph_use
                        and obj_norm.allow_high_confidence_graph_use
                    )
                    normalization_quality = (
                        "resolved_or_acceptable" if graph_usable else "low_confidence"
                    )
                    subject_identity = sub_norm.canonical_id or sub_norm.canonical_name
                    object_identity = obj_norm.canonical_id or obj_norm.canonical_name
                    evidence_id = _stable_id(asset_id, evidence, subject_identity, object_identity, sign)
                    triple_id = _stable_id(asset_id, chunk_id, sample_idx, node_idx, evidence_id)
                    observations.append(
                        {
                            "triple_id": triple_id,
                            "subject": sub_norm.canonical_name,
                            "object": obj_norm.canonical_name,
                            "normalized_subject": sub_norm.canonical_name,
                            "normalized_object": obj_norm.canonical_name,
                            "subject_confidence": sub_norm.confidence,
                            "object_confidence": obj_norm.confidence,
                            "subject_canonical_id": sub_norm.canonical_id,
                            "object_canonical_id": obj_norm.canonical_id,
                            "subject_canonical_name": sub_norm.canonical_term,
                            "object_canonical_name": obj_norm.canonical_term,
                            "subject_entity_type": sub_norm.entity_type,
                            "object_entity_type": obj_norm.entity_type,
                            "subject_semantic_level": sub_norm.semantic_level,
                            "object_semantic_level": obj_norm.semantic_level,
                            "subject_relations": sub_norm.relations,
                            "object_relations": obj_norm.relations,
                            "subject_normalization_status": sub_norm.normalization_status,
                            "object_normalization_status": obj_norm.normalization_status,
                            "subject_resolver": sub_norm.resolver,
                            "object_resolver": obj_norm.resolver,
                            "subject_match_type": sub_norm.match_type,
                            "object_match_type": obj_norm.match_type,
                            "subject_allow_high_confidence_graph_use": sub_norm.allow_high_confidence_graph_use,
                            "object_allow_high_confidence_graph_use": obj_norm.allow_high_confidence_graph_use,
                            "subject_normalization_warnings": sub_norm.warnings,
                            "object_normalization_warnings": obj_norm.warnings,
                            "normalization_quality": normalization_quality,
                            "exclude_from_high_confidence_conflict": not graph_usable,
                            "domain_id": node_domain,
                            "entity_registry_profile": sub_norm.entity_registry_profile,
                            "resolver_policy_id": sub_norm.resolver_policy_id,
                            "relation_raw": node.get("relation_raw", ""),
                            "relation_family": node.get("relation_family", "unknown"),
                            "polarity_type": node.get("polarity_type", "unknown"),
                            "direction": node.get("direction", "unknown"),
                            "direction_confidence": float(node.get("direction_confidence", 0.0)),
                            "relation_sign": sign,
                            "evidence_sentence": evidence,
                            "evidence_id": evidence_id,
                            "context": {k: str(v).upper().strip() for k, v in node.get("context", {}).items()},
                            "source_asset": asset_id,
                            "doi": doi_str,
                            "article_title": title_str,
                            "belief_weight": belief_weight,
                            "chunk_id": chunk_id,
                            "normalization": {
                                "subject": sub_norm.model_dump(),
                                "object": obj_norm.model_dump(),
                            },
                            "allow_high_confidence_graph_use": graph_usable,
                            "subject_entity_resolution_status": sub_norm.entity_resolution_status,
                            "object_entity_resolution_status": obj_norm.entity_resolution_status,
                            "subject_candidate_provider_names": sub_norm.candidate_provider_names,
                            "object_candidate_provider_names": obj_norm.candidate_provider_names,
                            "subject_requires_manual_review": sub_norm.requires_manual_review,
                            "object_requires_manual_review": obj_norm.requires_manual_review,
                            "subject_audit_ref": sub_norm.audit_ref,
                            "object_audit_ref": obj_norm.audit_ref,
                        }
                    )

    return observations, audit


def write_normalization_audit(
    audit: List[Dict[str, Any]],
    path: str,
    markdown_path: str = "reports/entity_normalization_audit.md",
) -> None:
    """Write machine-readable decisions and a compact review summary."""

    statuses = Counter(item.get("normalization_status", "unknown") for item in audit)
    dangerous = {
        "receptor_complex_to_gene_merge", "metabolite_to_parent_merge",
        "phenotype_to_gene_merge", "assay_to_phenotype_merge_without_relation",
    }
    dangerous_summary = Counter(
        warning
        for item in audit
        for warning in item.get("warnings", [])
        if warning in dangerous
    )
    unresolved = Counter(item.get("raw_term", "") for item in audit if item.get("normalization_status") == "unresolved_fallback")
    ambiguous = Counter(item.get("raw_term", "") for item in audit if item.get("normalization_status") == "ambiguous")
    high_confidence_usable = sum(bool(item.get("allow_high_confidence_graph_use")) for item in audit)
    summary = {
        "total_raw_terms": len(audit),
        "resolved_count": statuses.get("resolved", 0),
        "ambiguous_count": statuses.get("ambiguous", 0),
        "unresolved_fallback_count": statuses.get("unresolved_fallback", 0),
        "empty_or_invalid_count": statuses.get("empty_or_invalid", 0),
        "high_confidence_usable_count": high_confidence_usable,
        "low_confidence_excluded_count": len(audit) - high_confidence_usable,
    }
    reference_examples = []  # Pilot-specific examples were removed from the production audit.
    payload = {
        "summary": summary,
        "top_unresolved_terms": [{"term": term, "count": count} for term, count in unresolved.most_common(20)],
        "top_ambiguous_terms": [{"term": term, "count": count} for term, count in ambiguous.most_common(20)],
        "dangerous_warning_summary": dict(dangerous_summary),
        "reference_examples": reference_examples,
        "normalization_records": audit,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(markdown_path), exist_ok=True)
    lines = [
        "# Entity Normalization Audit", "",
        f"- Total raw terms: {summary['total_raw_terms']}",
        f"- Resolved: {summary['resolved_count']}",
        f"- Ambiguous: {summary['ambiguous_count']}",
        f"- Unresolved fallback: {summary['unresolved_fallback_count']}",
        f"- Empty or invalid: {summary['empty_or_invalid_count']}",
        f"- High-confidence usable: {summary['high_confidence_usable_count']}",
        f"- Low-confidence excluded: {summary['low_confidence_excluded_count']}",
        f"- Dangerous warning count: {sum(dangerous_summary.values())}", "",
        "## Top Unresolved Terms", "",
    ]
    lines.extend(f"- {term}: {count}" for term, count in unresolved.most_common(20))
    lines.extend(["", "## Top Ambiguous Terms", ""])
    lines.extend(f"- {term}: {count}" for term, count in ambiguous.most_common(20))
    lines.extend(["", "## Dangerous Warning Summary", ""])
    lines.extend(f"- {warning}: {count}" for warning, count in dangerous_summary.most_common())
    lines.extend(["", "## Reference Examples", ""])
    for example in reference_examples:
        relations = ", ".join(
            f"{relation['predicate']} {relation['object']}" for relation in example["relations"]
        ) or "none"
        lines.append(
            f"- {example['raw_term']} -> {example['canonical_id']} "
            f"({example['entity_type']}); relations: {relations}"
        )
    with open(markdown_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
