"""Read-only, conservative global knowledge coverage recommendation."""

from __future__ import annotations
import json
import re
from pathlib import Path

from code_engine.corpus.io import iter_jsonl
from code_engine.corpus.models import CoveragePrecheckResult


def _terms(query: str) -> set[str]:
    return {term for term in re.findall(r"[\w-]+", query.casefold()) if len(term) > 2}


def _matches(path: Path, terms: set[str], limit: int = 25) -> list[dict]:
    matches = []
    for item in iter_jsonl(path):
        item_terms = set(re.findall(r"[\w-]+", json.dumps(item, ensure_ascii=False).casefold()))
        if terms and terms.intersection(item_terms):
            matches.append(item)
            if len(matches) >= limit:
                break
    return matches


def run_global_coverage_precheck(query: str, domain_profile: dict | None, corpus_dir: Path, threshold: float = 0.75) -> CoveragePrecheckResult:
    store = Path(corpus_dir) / "knowledge_store"
    terms = _terms(query)
    papers = _matches(store / "papers.jsonl", terms)
    claims = _matches(store / "claims.jsonl", terms)
    conflicts = _matches(store / "conflicts.jsonl", terms)
    mechanisms = _matches(store / "mechanism_edges.jsonl", terms)
    hypotheses = _matches(store / "hypotheses.jsonl", terms)
    validations = _matches(store / "validation_results.jsonl", terms)
    if not any(path.exists() and path.stat().st_size for path in store.glob("*.jsonl")):
        return CoveragePrecheckResult(warnings=["global_knowledge_store_empty"])
    dimensions = {
        "paper_overlap": min(1.0, len(papers) / 2), "entity_pair_coverage": min(1.0, len(claims) / 2),
        "claim_coverage": min(1.0, len(claims) / 3), "conflict_coverage": min(1.0, len(conflicts)),
        "mechanism_coverage": min(1.0, len(mechanisms)), "hypothesis_coverage": min(1.0, len(hypotheses)),
        "validation_coverage": min(1.0, len(validations)),
    }
    score = round(sum(dimensions.values()) / len(dimensions), 6)
    if hypotheses and not validations and sum(value for key, value in dimensions.items() if key != "validation_coverage") / 6 >= threshold:
        action = "run_validation_only"
    elif score >= threshold:
        action = "use_existing_knowledge"
    elif papers and not conflicts:
        action = "run_abstract_l1_only"
    elif conflicts and not mechanisms:
        action = "run_fulltext_escalation"
    else:
        action = "run_incremental_search"
    return CoveragePrecheckResult(coverage_score=score, recommended_action=action, dimensions=dimensions, matched_papers=papers, matched_conflicts=conflicts, matched_hypotheses=hypotheses, warnings=[] if terms else ["query_has_no_indexable_terms"])


__all__ = ["run_global_coverage_precheck"]
