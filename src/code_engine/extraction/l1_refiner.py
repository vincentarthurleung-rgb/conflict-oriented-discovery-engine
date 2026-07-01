"""Deterministic Stage3 compatibility adapters for legacy and L1 v2 input."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code_engine.extraction.converters import legacy_tuple_to_l1_claim, l1_claim_to_legacy_tuple
from code_engine.schemas.l1_extraction import L1ExtractedClaim


def load_l1_claims(path: str | Path) -> list[L1ExtractedClaim]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if "claim_id" in payload:
        return [L1ExtractedClaim.model_validate(payload)]
    claims = []
    paper_id = str(payload.get("asset_id") or payload.get("paper_id") or source.stem.replace("_extracted", ""))
    for chunk in payload.get("chunks_extracted", []):
        chunk_id = str(chunk.get("chunk_id") or chunk.get("chunk_index") or "unknown")
        tuples = []
        for sample in chunk.get("raw_samples", []):
            tuples.extend(sample.get("causal_tuples", []))
        tuples.extend(chunk.get("aggregated_relations", []))
        for item in tuples:
            claims.append(legacy_tuple_to_l1_claim(item, {"paper_id": paper_id, "chunk_id": chunk_id, "section": chunk.get("section", "")}))
    return claims


def refine_l1_claims(claims: list[L1ExtractedClaim]) -> dict[str, Any]:
    records = []
    chunks: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for claim in claims:
        records.append({
            "claim_id": claim.claim_id,
            "paper_id": claim.paper_id,
            "chunk_id": claim.chunk_id,
            "fingerprint": claim.prompt_fingerprint,
            "evidence_sentence": claim.evidence_sentence,
            "subject_raw": claim.subject_raw,
            "relation_raw": claim.relation_raw,
            "relation_family": claim.relation_family,
            "polarity_type": claim.polarity_type,
            "direction": claim.direction,
            "direction_confidence": claim.direction_confidence,
            "object_raw": claim.object_raw,
            "direct_relation_sign": claim.direct_relation_sign,
            "refined_context": dict(claim.context) | {
                key: getattr(claim, key)
                for key in ("species", "sex", "age", "disease_model", "brain_region", "cell_type", "treatment", "dose", "route", "treatment_duration", "time_after_treatment", "assay_or_readout", "behavioral_assay", "clinical_outcome", "genotype", "oxygen_condition", "localization")
                if getattr(claim, key)
            },
            "evidence_record_ready": claim.model_dump(),
        })
        chunks.setdefault((claim.paper_id, claim.chunk_id), []).append(l1_claim_to_legacy_tuple(claim))
    legacy_chunks = [
        {
            "chunk_index": chunk_id,
            "chunk_id": chunk_id,
            "raw_samples": [{"causal_tuples": tuples}],
            "prompt_fingerprints": [item.get("prompt_fingerprint", {}) for item in tuples],
        }
        for (_, chunk_id), tuples in chunks.items()
    ]
    return {
        "schema_version": "l1_5_refined_v2",
        "asset_id": claims[0].paper_id if claims else "UNKNOWN",
        "refined_claims": records,
        "chunks_extracted": legacy_chunks,
    }


def refine_l1_file(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    result = refine_l1_claims(load_l1_claims(input_path))
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
