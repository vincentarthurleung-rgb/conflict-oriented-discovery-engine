"""Lexical normalization and entity typing facade."""

from code_engine.normalization.normalizer import normalize_entity
from code_engine.normalization.models import EntityRelation, NormalizationCandidate, NormalizationDecision
from code_engine.normalization.resolver import ResolverCascade, resolve_entity

__all__ = [
    "normalize_entity", "resolve_entity", "ResolverCascade", "EntityRelation",
    "NormalizationCandidate", "NormalizationDecision",
]
