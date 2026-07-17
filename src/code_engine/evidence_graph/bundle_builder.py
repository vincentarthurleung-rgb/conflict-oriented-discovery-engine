"""Merge cross-paper evidence edges into canonical relation bundles."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from typing import Iterable

from .models import EvidenceEdge, RelationEvidenceBundle

KNOWN_DIRECTIONS = {"increase", "decrease", "activate", "inhibit", "no_effect", "mixed"}


def stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part or "unknown") for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:20]}"


def entropy(distribution: dict[str, int]) -> float:
    total = sum(distribution.values())
    if not total:
        return 0.0
    return round(max(0.0, -sum((n / total) * math.log2(n / total) for n in distribution.values() if n)), 6)


def bundle_key(edge: EvidenceEdge) -> tuple[str, str, str, str]:
    return (str(edge.source_entity_id or "unknown"), str(edge.target_entity_id or "unknown"),
            edge.relation_family or "unknown", edge.polarity_type or "unknown")


def build_relation_evidence_bundles(evidence_edges: Iterable[EvidenceEdge]) -> list[RelationEvidenceBundle]:
    groups: dict[tuple[str, str, str, str], list[EvidenceEdge]] = defaultdict(list)
    for edge in evidence_edges:
        if not edge.source_entity_id or not edge.target_entity_id:
            continue
        missing_canonical_identity = bool(
            {"missing_subject_canonical_id", "missing_object_canonical_id",
             "unresolved_subject_scoped_fallback_identity", "unresolved_object_scoped_fallback_identity"}
            & set(edge.warnings)
        )
        if missing_canonical_identity:
            if "excluded_from_relation_bundle_reasoning" not in edge.warnings:
                edge.warnings.append("excluded_from_relation_bundle_reasoning")
            if "excluded_from_relation_bundle_reasoning" not in edge.export_warnings:
                edge.export_warnings.append("excluded_from_relation_bundle_reasoning")
            continue
        groups[bundle_key(edge)].append(edge)
    bundles = []
    for key, items in sorted(groups.items()):
        subject, obj, relation, polarity = key
        warnings = sorted({warning for item in items for warning in item.warnings})
        valid = [item for item in items if item.direction in KNOWN_DIRECTIONS]
        if len(valid) != len(items):
            warnings.append("unknown_direction_excluded_from_entropy")
        paper_votes: dict[str, set[str]] = defaultdict(set)
        for item in valid:
            # Missing provenance must not manufacture multiple apparent papers.
            paper = str(item.canonical_paper_id or item.paper_id or item.doi or "UNKNOWN_PAPER")
            paper_votes[paper].add(item.direction)
        collapsed = []
        if any(len(votes) > 1 for votes in paper_votes.values()):
            warnings.append("mixed_direction_within_same_paper")
        for votes in paper_votes.values():
            collapsed.append(next(iter(votes)) if len(votes) == 1 else "mixed")
        paper_distribution = dict(sorted(Counter(collapsed).items()))
        direction_distribution = dict(sorted(Counter(item.direction for item in valid).items()))
        contexts: dict[str, list[str]] = defaultdict(list)
        context_values = []
        for item in valid:
            if item.context_variables not in (None, {}, [], ""):
                value = json.dumps(item.context_variables, ensure_ascii=False, sort_keys=True, default=str)
                contexts[value].append(item.direction); context_values.append(item.context_variables)
        years = sorted({item.publication_year for item in items if item.publication_year is not None})
        papers = sorted({str(item.paper_id) for item in items if item.paper_id})
        canonical = sorted({str(item.canonical_paper_id) for item in items if item.canonical_paper_id})
        bundles.append(RelationEvidenceBundle(
            bundle_id=stable_id("bundle", *key), subject_canonical_id=subject, object_canonical_id=obj,
            relation_family=relation, polarity_type=polarity,
            evidence_edge_ids=sorted(item.evidence_edge_id for item in items),
            observation_ids=sorted({str(item.observation_id) for item in items if item.observation_id}),
            paper_ids=papers, canonical_paper_ids=canonical,
            linked_dois=sorted({str(item.doi) for item in items if item.doi}),
            linked_titles=sorted({str(item.title) for item in items if item.title}),
            linked_journals=sorted({str(item.journal) for item in items if item.journal}),
            publication_year_range=[min(years), max(years)] if years else [],
            paper_count=len(paper_votes), evidence_count=len(items), direction_distribution=direction_distribution,
            paper_level_direction_distribution=paper_distribution, entropy=entropy(paper_distribution),
            distinct_direction_count=len(paper_distribution), context_variables=context_values,
            context_distribution={context: dict(sorted(Counter(directions).items())) for context, directions in sorted(contexts.items())},
            evidence_tier_distribution=dict(sorted(Counter(str(item.evidence_tier or "unknown") for item in items).items())),
            warnings=sorted(set(warnings)),
            subject_name=next((item.subject_name for item in items if item.subject_name), None),
            subject_type=next((item.subject_type for item in items if item.subject_type), None),
            object_name=next((item.object_name for item in items if item.object_name), None),
            object_type=next((item.object_type for item in items if item.object_type), None),
            linked_claim_ids=sorted({value for item in items for value in item.linked_claim_ids}),
            linked_evidence_ids=sorted({value for item in items for value in item.linked_evidence_ids}),
            linked_conflict_ids=sorted({value for item in items for value in item.linked_conflict_ids}),
            linked_mechanism_edge_ids=sorted({value for item in items for value in item.linked_mechanism_edge_ids}),
            linked_mechanism_path_ids=sorted({value for item in items for value in item.linked_mechanism_path_ids}),
            linked_hypothesis_ids=sorted({value for item in items for value in item.linked_hypothesis_ids}),
            run_id=next((item.run_id for item in items if item.run_id), None),
            topic_id=next((item.topic_id for item in items if item.topic_id), None),
            query_id=next((item.query_id for item in items if item.query_id), None),
            export_ready=all(item.export_ready for item in items),
            export_warnings=sorted({value for item in items for value in item.export_warnings}),
        ))
    return bundles
