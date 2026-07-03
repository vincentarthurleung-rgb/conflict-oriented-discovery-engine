"""Canonical identifiers and records for the System B knowledge graph."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

NODE_TYPES = {"entity", "paper", "case", "hypothesis", "validator", "evidence", "context", "pathway"}
EDGE_TYPES = {"claim_relation", "supports", "contradicts", "mentioned_in", "derived_from", "validated_by", "has_context", "part_of_case"}


def normalize_entity(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip().lower()
    text = text.replace("κ", "k").replace("–", "-").replace("—", "-")
    text = re.sub(r"nf[\s_-]*-?[kκ]b", "nf-kb", text)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_").replace("nf_kb", "nf-kb")
    return text


def entity_id(label: str) -> str:
    return f"entity:{normalize_entity(label)}"


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return f"{prefix}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def node(node_id: str, label: str, node_type: str, case_ids=None, aliases=None, metadata=None) -> dict[str, Any]:
    if node_type not in NODE_TYPES:
        raise ValueError(f"unsupported node type: {node_type}")
    return {"id": node_id, "label": label, "type": node_type, "aliases": aliases or [], "case_ids": case_ids or [], "source_count": 0, "metadata": metadata or {}}


def edge(edge_id: str, source: str, target: str, predicate: str, edge_type: str, case_id: str, **values) -> dict[str, Any]:
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"unsupported edge type: {edge_type}")
    result = {"id": edge_id, "source": source, "target": target, "predicate": predicate, "edge_type": edge_type, "polarity": values.pop("polarity", None), "case_id": case_id, "paper_ids": values.pop("paper_ids", []), "evidence_ids": values.pop("evidence_ids", []), "confidence": values.pop("confidence", None), "source_scope": values.pop("source_scope", None), "metadata": values.pop("metadata", {})}
    result.update(values)
    return result
