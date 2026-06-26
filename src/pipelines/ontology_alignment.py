"""Conservative entity normalization for C.O.D.E. v4.0.

This module does not claim full ontology lookup. The MVP performs alias-map
normalization and uppercase fallback, then writes an audit trail for each mapping.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Tuple

from src.schemas import NormalizedEntity


def clean_semantic_token(token: str, synonym_map: Dict[str, str] | None = None) -> NormalizedEntity:
    """Normalize a raw entity using an alias map before uppercase fallback."""

    raw = str(token or "").strip()
    if not raw or "failed_" in raw.lower():
        return NormalizedEntity(
            raw_term=raw,
            canonical_name="UNSPECIFIED",
            mapping_method="rejected_empty_or_failed",
            confidence=0.0,
        )

    synonyms = synonym_map or {}
    lowered = raw.lower().strip()
    if lowered in synonyms:
        return NormalizedEntity(
            raw_term=raw,
            canonical_name=str(synonyms[lowered]).upper().strip(),
            mapping_method="alias_map",
            confidence=0.9,
        )

    return NormalizedEntity(
        raw_term=raw,
        canonical_name=raw.upper().strip(),
        mapping_method="uppercase_fallback",
        confidence=0.55,
    )


def _stable_id(*parts: Any) -> str:
    return hashlib.md5("_".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]


def extract_normalized_observations(
    l1_5_input_dir: str,
    synonym_map: Dict[str, str] | None,
    forbidden_keywords: List[str] | None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load L1.5 raw samples and return normalized causal observations plus audit."""

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
                    if not sub_raw or not obj_raw or sign not in (-1, 0, 1):
                        continue

                    sub_norm = clean_semantic_token(sub_raw, synonym_map)
                    obj_norm = clean_semantic_token(obj_raw, synonym_map)
                    audit.extend([sub_norm.model_dump(), obj_norm.model_dump()])
                    if "UNSPECIFIED" in [sub_norm.canonical_name, obj_norm.canonical_name]:
                        continue

                    evidence_id = _stable_id(asset_id, evidence, sub_norm.canonical_name, obj_norm.canonical_name, sign)
                    triple_id = _stable_id(asset_id, chunk_id, sample_idx, node_idx, evidence_id)
                    observations.append(
                        {
                            "triple_id": triple_id,
                            "subject": sub_norm.canonical_name,
                            "object": obj_norm.canonical_name,
                            "relation_raw": node.get("relation_raw", ""),
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
                        }
                    )

    return observations, audit


def write_normalization_audit(audit: List[Dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"normalization_records": audit}, handle, ensure_ascii=False, indent=2)
