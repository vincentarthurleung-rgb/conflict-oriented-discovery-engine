"""Rule-based bilingual parser for local research queries."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

from code_engine.graph.ontology_alignment import clean_semantic_token
from code_engine.query.models import ResearchQuery


DEFAULT_ONTOLOGY_CONFIG = Path("configs/normalization/l2_l3_ontology_rules.json")
CHINESE_ALIASES = {
    "氯胺酮": "ketamine",
    "抑郁症": "depression",
    "脑源性神经营养因子": "BDNF",
    "雷帕霉素靶蛋白": "mTOR",
}


def _load_synonyms(config_path: str | Path | None) -> Dict[str, str]:
    path = Path(config_path or DEFAULT_ONTOLOGY_CONFIG)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k).lower(): str(v) for k, v in payload.get("synonym_map", {}).items()}


def _translate_chinese(text: str) -> str:
    translated = text
    for source, target in CHINESE_ALIASES.items():
        translated = translated.replace(source, target)
    return translated


def _split_query(text: str) -> Tuple[str, str, str, str]:
    for separator in ("->", "=>"):
        if separator in text:
            subject, obj = text.split(separator, 1)
            return subject.strip(), separator, obj.strip(), "directed_relation"

    for pattern in (r"\s+-\s+", r"\s*/\s*", r"\s*,\s*"):
        parts = re.split(pattern, text, maxsplit=1)
        if len(parts) == 2 and all(part.strip() for part in parts):
            return parts[0].strip(), "associated_with", parts[1].strip(), "entity_pair"

    tokens = text.split()
    if len(tokens) >= 3:
        return tokens[0], " ".join(tokens[1:-1]), tokens[-1], "mechanism_path"
    if len(tokens) == 2:
        return tokens[0], "associated_with", tokens[1], "topic"
    if len(tokens) == 1 and tokens[0]:
        return tokens[0], "", "", "topic"
    return "", "", "", "unknown"


def _entity_type(value: str) -> str:
    upper = value.upper()
    if not upper:
        return "unknown"
    if upper in {"KETAMINE", "ESKETAMINE"}:
        return "compound"
    if upper in {"DEPRESSION", "MDD", "ANTIDEPRESSANT RESPONSE"}:
        return "disease_or_phenotype"
    if re.fullmatch(r"[A-Z][A-Z0-9-]{1,12}", upper):
        return "gene_or_protein"
    return "biomedical_entity"


def parse_research_query(
    raw_query: str,
    *,
    ontology_config_path: str | Path | None = None,
) -> ResearchQuery:
    """Parse and normalize a query without network or LLM access."""

    raw = str(raw_query or "").strip()
    language = "zh" if re.search(r"[\u4e00-\u9fff]", raw) else "en"
    translated = _translate_chinese(raw)
    subject_raw, relation_raw, object_raw, query_type = _split_query(translated)
    synonyms = _load_synonyms(ontology_config_path)
    subject = clean_semantic_token(subject_raw, synonyms)
    obj = clean_semantic_token(object_raw, synonyms) if object_raw else None
    normalized_object = obj.canonical_name if obj else ""
    stable_input = "|".join((raw.lower(), subject.canonical_name, relation_raw, normalized_object))

    return ResearchQuery(
        query_id=hashlib.sha256(stable_input.encode("utf-8")).hexdigest()[:12],
        raw_query=raw,
        subject_raw=subject_raw,
        relation_raw=relation_raw,
        object_raw=object_raw,
        query_type=query_type,
        normalized_subject=subject.canonical_name if subject_raw else "",
        normalized_object=normalized_object,
        subject_entity_type=_entity_type(subject.canonical_name),
        object_entity_type=_entity_type(normalized_object),
        language=language,
        created_at=datetime.now(timezone.utc).isoformat(),
        normalization_audit={
            "subject": subject.model_dump(),
            "object": obj.model_dump() if obj else None,
            "normalizer": "type_relation_aware_resolver_cascade_v1",
        },
    )
