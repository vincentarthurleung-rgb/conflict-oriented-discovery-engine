"""Domain-agnostic degraded parsing used only when semantic LLM access is unavailable."""

from __future__ import annotations

import hashlib
import re

from code_engine.encoder.models import DomainRoutingDecision, SemanticIntakeResult, SemanticResearchIntent, SemanticSearchConcept, SemanticSeedTriple


def _language(text: str) -> str:
    return "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en"


def _explicit_domain(text: str, allowed: set[str]) -> str | None:
    match = re.search(r"(?:domain|领域)\s*[:=]\s*([a-z][a-z0-9_-]+)", text, re.I)
    return match.group(1).casefold() if match and match.group(1).casefold() in allowed else None


def _chunks(text: str) -> list[str]:
    # Deliberately lexical, not biomedical: no aliases or domain keyword tables.
    latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", text)
    chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    return list(dict.fromkeys(latin + chinese))[:12]


_STOPWORDS = {"has", "have", "had", "is", "are", "was", "were", "in", "on", "and", "or", "but",
              "with", "without", "role", "roles", "effect", "effects", "result", "results", "associated",
              "association", "a", "an", "the", "of", "to", "for", "from", "by", "as"}
_CONTRAST = re.compile(r"\b(?:but|however|whereas|while|although|yet)\b", re.I)


def _fallback_semantics(query: str) -> tuple[str, str, str, list[str]]:
    """Extract a conservative contrast-aware seed without biomedical dictionaries."""
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", query)
    meaningful = [item for item in tokens if item.casefold() not in _STOPWORDS]
    subject = meaningful[0] if meaningful else (tokens[0] if tokens else "")
    clauses = [part.strip(" ,.;:") for part in _CONTRAST.split(query) if part.strip(" ,.;:")]
    phrases = []
    for clause in clauses:
        words = [item for item in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", clause)
                 if item.casefold() not in _STOPWORDS and item.casefold() != subject.casefold()]
        if words:
            phrases.append(" ".join(words[:5]))
    tail = [item for item in meaningful[1:] if item.casefold() != subject.casefold()]
    contrastive = len(clauses) > 1
    obj = (" ".join(tail[-2:]) if len(tail) >= 2 else (tail[-1] if tail else "")) if contrastive else (tail[0] if tail else "")
    relation = "has_context_dependent_role_in" if contrastive else "unspecified_association"
    if not contrastive:
        phrases = tail[1:]
    return subject, relation, obj, phrases


def deterministic_degraded_intake(query: str, allowed_domain_ids: set[str]) -> SemanticIntakeResult:
    explicit = _explicit_domain(query, allowed_domain_ids)
    domain_id = explicit or "general_biomedical"
    confidence = 0.5 if explicit else 0.3
    review = not bool(explicit)
    routing = DomainRoutingDecision(domain_id=domain_id, domain_profile_id=domain_id, confidence=confidence, reasoning_summary="Explicit domain flag accepted." if explicit else "No semantic classifier available; general profile selected.", ambiguities=[] if explicit else ["Domain semantics were not inferred without an LLM."], requires_manual_review=review)
    concepts = _chunks(query)
    relation = re.match(r"^\s*(.+?)\s*(?:->|=>)\s*(.+?)\s*$", query)
    seeds = []
    if relation:
        subject, obj = relation.groups()
        stable = hashlib.sha256(f"{subject}|explicit_relation|{obj}".encode()).hexdigest()[:16]
        seeds.append(SemanticSeedTriple(triple_id=stable, subject=subject.strip(), relation="explicit_relation", object=obj.strip(), source="deterministic_degraded_fallback", confidence=0.5))
    elif len(concepts) >= 2:
        subject, relation_name, obj, contexts = _fallback_semantics(query)
        stable = hashlib.sha256(f"{subject}|{relation_name}|{obj}|{'|'.join(contexts)}".encode()).hexdigest()[:16]
        seeds.append(SemanticSeedTriple(
            triple_id=stable, subject=subject, relation=relation_name, object=obj,
            source="deterministic_degraded_fallback", confidence=0.3,
            warnings=["weak_seed_triple_requires_human_review"],
        ))
    search_concepts = [SemanticSearchConcept(concept_id=hashlib.sha256(item.encode()).hexdigest()[:12], text=item, concept_type="entity", importance=0.5, source="deterministic_degraded_fallback") for item in concepts]
    fallback_contexts = [] if relation else _fallback_semantics(query)[3]
    intent = SemanticResearchIntent(raw_user_input=query, language=_language(query), task_type="explicit_relation" if relation else "unknown", research_goal="User-provided explicit relation" if relation else "Semantic interpretation unavailable", primary_entities=[relation.group(1).strip()] if relation else ([seeds[0].subject] if seeds else concepts[:1]), secondary_entities=concepts[1:], context_terms=fallback_contexts or ([] if relation else concepts[2:]), domain_routing=routing, confidence=confidence, ambiguities=list(routing.ambiguities))
    warning = "LLM semantic intake disabled; deterministic fallback used."
    return SemanticIntakeResult(research_intent=intent, domain_routing=routing, seed_triples=seeds, search_concepts=search_concepts, recommended_search_queries=[], negative_filters=[], ambiguities=list(routing.ambiguities), warnings=[warning], semantic_mode="deterministic_degraded", api_calls_made=0)
