#!/usr/bin/env python3
"""Prepare three blinded, source-grounded human review packets offline."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import candidate_id
from scripts.search_plan_v24_alpha318b_post_builder_prechecks import (
    validate_builder_response,
)


QUALITY_EXEC = ROOT / "runs/20261013_code_pilot_bound_quality_v2_development_execution"
QUALITY_MARKER = "code_pilot_bound_quality_v2_development_execution_sha256"
QUALITY_ROOT = "5a9b46ce730cbae2b4b757766343b63c198467e4d0c7745643b8c0a9b0696e7d"
BUILDER_EXEC = ROOT / "runs/20261012_code_first_pilot_bound_builder_v4_development_execution"
BUILDER_MARKER = "code_first_pilot_bound_builder_v4_development_execution_sha256"
BUILDER_ROOT = "bebb5b6be579bd39a99f463e7f7f9d71e00001a05b7047ba9c60930f0a60c44f"
ADAPTER = ROOT / "runs/20261012_code_minimal_immutable_handoff_to_construction_adapter_offline"
ADAPTER_MARKER = "code_minimal_immutable_handoff_to_construction_adapter_sha256"
ADAPTER_ROOT = "d8a05a63f48f0fa71c319c25d4f0cf622127cbcee866465e01b7228181f709ea"
QUALITY_FREEZE = ROOT / "runs/20261012_code_pilot_bound_quality_v2_request_freeze_offline"
QUALITY_FREEZE_MARKER = "code_pilot_bound_quality_v2_request_freeze_sha256"
QUALITY_FREEZE_ROOT = "833635c0728ae885f900a5554b771b91e5ce4ea917e2d4b34aeb649d4159f326"
BUILDER_FREEZE = ROOT / "runs/20261012_code_pilot_bound_builder_v4_request_freeze_offline"
BUILDER_FREEZE_MARKER = "code_pilot_bound_builder_v4_request_freeze_sha256"
BUILDER_FREEZE_ROOT = "0ebf44c361fc9e2cde04b7562b5e559c2ee0c25602383083cb62471b3fde307e"

BOUNDARY = (ROOT /
    "runs/20260902_trib3_survival_first_qualified_l4_adjudication_v1_offline/artifacts/human_review_boundary.json")

OUT = ROOT / "runs/20261013_code_blind_evidence_review_three_pilot_propositions_offline"
ROOT_MARKER = "code_blind_evidence_review_three_pilot_propositions_sha256"
FINAL_FILES = {
    "summary.json",
    "blind_review_packets.jsonl",
    "reviewer_instructions.md",
    "provenance_manifest.json",
    "controller_private_quality_comparison.json",
    "historical_preservation.json",
    ROOT_MARKER,
}

CONTEXT_PARAGRAPH_INDEXES = {
    0: [4, 5],
    1: [4, 22, 23, 24],
    2: [29, 30, 31],
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    require(type(value) is dict, "JSON_OBJECT_REQUIRED:" + str(path))
    return value


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(),
            "ARTIFACT_MISSING_OR_SYMLINK:" + str(path))
    return sha(path.read_bytes())


def root_hash(directory: Path, marker: str) -> str:
    require(directory.is_dir() and not directory.is_symlink(),
            "ROOT_DIRECTORY_INVALID:" + str(directory))
    require(not any(path.is_symlink() for path in directory.rglob("*")),
            "FROZEN_SYMLINK_FORBIDDEN:" + str(directory))
    files = sorted(path for path in directory.rglob("*")
                   if path.is_file() and path.name != marker)
    return sha(canonical([[path.relative_to(directory).as_posix(), digest(path)]
                          for path in files]))


def verify_root(directory: Path, marker: str, expected: str) -> dict[str, Any]:
    actual = root_hash(directory, marker)
    recorded = (directory / marker).read_text(encoding="ascii").strip()
    require(actual == recorded == expected,
            "FROZEN_ROOT_MISMATCH:" + directory.name)
    return {
        "artifact_path": directory.relative_to(ROOT).as_posix(),
        "root_marker": marker,
        "sha256": actual,
        "verified": True,
        "immutable_frozen": True,
    }


def write_raw(path: Path, raw: bytes, *, private: bool = False) -> str:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600 if private else 0o644)
    return sha(raw)


def write_json(path: Path, value: Any, *, private: bool = False) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     indent=2).encode("utf-8") + b"\n"
    return write_raw(path, raw, private=private)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> str:
    raw = b"".join(canonical(record) + b"\n" for record in records)
    return write_raw(path, raw)


def exact_quote_ref(body: str, quote: str) -> dict[str, Any]:
    require(body.count(quote) == 1, "EXACT_QUOTE_NOT_UNIQUE")
    start = body.index(quote)
    end = start + len(quote)
    require(body[start:end] == quote, "EXACT_QUOTE_ROUND_TRIP_FAILURE")
    return {
        "body_start_offset": start,
        "body_end_offset": end,
        "coordinate_end_semantics": "exclusive",
        "exact_text": quote,
        "exact_text_sha256": sha(quote.encode("utf-8")),
    }


def documented(body: str, *quotes: str) -> dict[str, Any]:
    return {
        "state": "DOCUMENTED_IN_INCLUDED_FROZEN_BODY_CONTEXT",
        "verbatim_evidence": [exact_quote_ref(body, quote) for quote in quotes],
    }


def absent(reason: str) -> dict[str, Any]:
    return {"state": "NOT_DOCUMENTED_IN_INCLUDED_FROZEN_BODY_CONTEXT",
            "value": None, "reason": reason}


def documented_details(position: int, body: str) -> dict[str, Any]:
    if position == 0:
        return {
            "experiment_identity": documented(body,
                "To evaluate the functional consequences of AR ablation on skeletal muscle regenerative capacities, we subjected young (3-month-old) control and AR(i)sat-/Y mice to acute tibialis anterior (TA) muscle injury via cardiotoxin (CTX) injection 1 month after gene ablation, and assessed histological features of repair at 5, 7, 14, 28, and 42 days postinjury (dpi)."),
            "comparator": documented(body,
                "TAM-treated littermates lacking the Pax7-CreERT2 transgene served as controls."),
            "species_or_subject": documented(body,
                "young (3-month-old) control and AR(i)sat-/Y mice"),
            "cell_or_tissue_type": documented(body,
                "conditional AR deletion in this cell lineage",
                "acute tibialis anterior (TA) muscle injury"),
            "intervention": documented(body,
                "Nine-week-old mice harboring floxed Ar alleles and expressing the Pax7-CreERT2 transgene were treated with tamoxifen (TAM) for 5 days, enabling selective deletion of Ar in MuSC (fig. S1, A to D)."),
            "timing": documented(body,
                "1 month after gene ablation",
                "at 5, 7, 14, 28, and 42 days postinjury (dpi)"),
            "dosage": absent("Tamoxifen duration is documented, but dose is not present in the included frozen BODY context; CTX dose is also not present."),
            "measurement": documented(body,
                "Ultrastructural analyses performed at 7 dpi, a time point at which mononuclear cells fuse to form myosyncytia and primary regenerative outcomes are captured (), revealed that AR(i)sat-/Y muscles displayed disorganized sarcomeres, with misaligned triads characterized by dilated T-tubules, disrupted Z-lines, and poorly defined or absent M-lines (Fig. 1B).",
                "These structural muscle defects correlated with a significant reduction in myofiber cross-sectional area (CSA; Fig. 1C), which translated into a significant reduction in contractile force at 28 dpi (Fig. 1D)."),
            "observed_result": documented(body,
                "However, at 7 dpi, AR(i)sat-/Y mice exhibited regenerative defects, including persistent inflammation, and aberrant fiber morphology that persisted until 42 dpi and were not due to the CreERT2 knock-in (Fig. 1A and fig. S1H).",
                "Muscle dysfunction was accompanied by a marked reduction in the MuSC pool at 7 dpi (Fig. 1, E and F), which persisted at 28 dpi (fig. S1, I and J)"),
            "direct_observation_excerpts": documented(body,
                "These structural muscle defects correlated with a significant reduction in myofiber cross-sectional area (CSA; Fig. 1C), which translated into a significant reduction in contractile force at 28 dpi (Fig. 1D)."),
            "author_interpretation_excerpts": documented(body,
                "showing that loss of AR in MuSC severely impairs regenerative capacity in young male mice."),
        }
    if position == 1:
        return {
            "experiment_identity": documented(body,
                "To test this, we subjected control and AR(i)sat-/Y muscles to a secondary CTX-induced injury 28 days after the primary injury and assessed tissue morphology 7 days later (28 + 7 dpi)."),
            "comparator": documented(body,
                "control and AR(i)sat-/Y muscles"),
            "species_or_subject": documented(body,
                "young (3-month-old) control and AR(i)sat-/Y mice"),
            "cell_or_tissue_type": documented(body,
                "To investigate the division modalities of MuSC, we performed a series of immunofluorescence analyses."),
            "intervention": documented(body,
                "Nine-week-old mice harboring floxed Ar alleles and expressing the Pax7-CreERT2 transgene were treated with tamoxifen (TAM) for 5 days, enabling selective deletion of Ar in MuSC (fig. S1, A to D).",
                "a secondary CTX-induced injury 28 days after the primary injury"),
            "timing": documented(body,
                "Double staining for PAX7 and KI67 in injured TA muscles from control and AR(i)sat-/Y mice at 5 and 7 dpi revealed a significant reduction in proliferating MuSC in mutant mice (Fig. 4, D to F), indicative of impaired symmetric stem cell divisions.",
                "7 days later (28 + 7 dpi)"),
            "dosage": absent("Tamoxifen and CTX doses are not present in the included frozen BODY context."),
            "measurement": documented(body,
                "Double staining for PAX7 and KI67 in injured TA muscles from control and AR(i)sat-/Y mice at 5 and 7 dpi",
                "we performed MYOG and KI67 double immunostaining on injured TA muscles at 5 and 7 dpi",
                "quantification of PAX7-positive MuSC at 28 + 7 dpi (Fig. 4N)"),
            "observed_result": documented(body,
                "Quantification confirmed that MYOG+/KI67+ cells were more abundant in AR(i)sat-/Y muscles at both 5 and 7 dpi (Fig. 4K)",
                "These defects were accompanied by a threefold reduction in MuSC numbers in AR(i)sat-/Y mice compared to controls, as revealed by quantification of PAX7-positive MuSC at 28 + 7 dpi (Fig. 4N)."),
            "direct_observation_excerpts": documented(body,
                "Quantification confirmed that MYOG+/KI67+ cells were more abundant in AR(i)sat-/Y muscles at both 5 and 7 dpi (Fig. 4K)",
                "These defects were accompanied by a threefold reduction in MuSC numbers in AR(i)sat-/Y mice compared to controls, as revealed by quantification of PAX7-positive MuSC at 28 + 7 dpi (Fig. 4N)."),
            "author_interpretation_excerpts": documented(body,
                "Overall, these results indicate that AR signaling in MuSC is essential for maintaining the stem cell pool by preventing premature differentiation (Fig. 4O), thereby ensuring effective regenerative capacity during both primary and subsequent injuries."),
        }
    require(position == 2, "UNEXPECTED_BUILDER_POSITION")
    return {
        "experiment_identity": documented(body,
            "We thereby supplemented old mice with 5-α-dihydrotestosterone (DHT) using implants."),
        "comparator": documented(body,
            "sham-operated or 5-α-dihydrotestosterone (DHT)–supplemented mice"),
        "species_or_subject": documented(body,
            "1-year-old (hereafter old) control and mutant mice",
            "DHT-supplemented old mouse TA"),
        "cell_or_tissue_type": documented(body,
            "gastrocnemius skeletal muscle",
            "old mouse TA"),
        "intervention": documented(body,
            "We thereby supplemented old mice with 5-α-dihydrotestosterone (DHT) using implants."),
        "timing": documented(body,
            "1 week after implantation",
            "At 7 dpi, DHT-treated mice exhibited significantly improved muscle regeneration, as evidenced by enhanced myofiber morphology and an increased number of nuclei per regenerating fiber (Fig. 6M)."),
        "dosage": absent("DHT dose and implant release rate are not present in the included frozen BODY context."),
        "measurement": documented(body,
            "H&E staining and corresponding quantification of centronuclei average in TA of sham-operated or 5-α-dihydrotestosterone (DHT)–supplemented mice, 7 dpi.",
            "PAX7 (green) and KI67 (magenta) (O), MYOG (red) (P), and F4/80 (green) (Q) immunofluorescence and corresponding quantifications in sham-operated or DHT-supplemented old mouse TA, 7 dpi."),
        "observed_result": documented(body,
            "At 7 dpi, DHT-treated mice exhibited significantly improved muscle regeneration, as evidenced by enhanced myofiber morphology and an increased number of nuclei per regenerating fiber (Fig. 6M).",
            "No significant differences were detected in differentiation capacity or immune infiltration, as assessed by MYOG and F4/80 staining, respectively (Fig. 6, P and Q)."),
        "direct_observation_excerpts": documented(body,
            "At 7 dpi, DHT-treated mice exhibited significantly improved muscle regeneration, as evidenced by enhanced myofiber morphology and an increased number of nuclei per regenerating fiber (Fig. 6M)."),
        "author_interpretation_excerpts": documented(body,
            "Together, these findings provide direct evidence that age-related androgen deficiency causally contributes to impaired aging skeletal muscle regeneration."),
    }


def paragraph_record(paragraph: dict[str, Any]) -> dict[str, Any]:
    return {
        "paragraph_span_id": paragraph["span_id"],
        "section_headings": paragraph["section_headings"],
        "section_path": paragraph["section_path"],
        "paragraph_ordinal_within_section": paragraph["ordinal"],
        "body_start_offset": paragraph["start_offset"],
        "body_end_offset": paragraph["end_offset"],
        "coordinate_end_semantics": "exclusive",
        "verbatim_text": paragraph["text"],
        "text_sha256": sha(paragraph["text"].encode("utf-8")),
    }


def reviewer_instructions() -> str:
    return """# Independent blind evidence review instructions

Review each packet independently using only the proposition and frozen evidence supplied in that packet. The packets contain no prior Quality V2 judgment, preferred answer, model confidence, aggregate score, or historical answer.

Do not use outside literature or unstated experimental details. A field marked `NOT_DOCUMENTED_IN_INCLUDED_FROZEN_BODY_CONTEXT` must remain unresolved rather than being filled from background knowledge. Treat author interpretation separately from direct reported experimental observations.

For every packet answer:

1. Does the original experiment support the proposition **as written**? Use `SUPPORTED`, `NOT_SUPPORTED`, or `INSUFFICIENT_EVIDENCE`.
2. Is the intervention and comparator correctly represented? Use `CORRECT`, `INCORRECT`, `UNRESOLVED`, or `NOT_APPLICABLE`.
3. Is the measurement endpoint correctly represented? Use the same four states.
4. Are documented species/subject, cell or tissue type, dosage, and timing restrictions retained? Evaluate each separately with `RETAINED`, `NOT_RETAINED`, `UNRESOLVED`, or `NOT_DOCUMENTED`.
5. Does the proposition overstate causality or mechanism? Use `YES`, `NO`, or `UNRESOLVED`.
6. Is the evidence `DIRECT`, `INDIRECT`, or `INSUFFICIENT` for the proposition as written?
7. Cite one or more exact supplied spans that support or contradict the judgment. Copy the text verbatim and retain its BODY start/end offsets.

Return one response per packet keyed by the exact `review_task_id` and `candidate_id`. Do not rank the three propositions and do not infer a preferred answer from packet order.

Required response shape:

```json
{
  "review_task_id": "...",
  "candidate_id": "...",
  "support_as_written": "SUPPORTED | NOT_SUPPORTED | INSUFFICIENT_EVIDENCE",
  "intervention_and_comparator_representation": "CORRECT | INCORRECT | UNRESOLVED | NOT_APPLICABLE",
  "measurement_endpoint_representation": "CORRECT | INCORRECT | UNRESOLVED | NOT_APPLICABLE",
  "restrictions_retained": {
    "species_or_subject": "RETAINED | NOT_RETAINED | UNRESOLVED | NOT_DOCUMENTED",
    "cell_or_tissue_type": "RETAINED | NOT_RETAINED | UNRESOLVED | NOT_DOCUMENTED",
    "dosage": "RETAINED | NOT_RETAINED | UNRESOLVED | NOT_DOCUMENTED",
    "timing": "RETAINED | NOT_RETAINED | UNRESOLVED | NOT_DOCUMENTED"
  },
  "causality_or_mechanism_overstatement": "YES | NO | UNRESOLVED",
  "evidence_directness": "DIRECT | INDIRECT | INSUFFICIENT",
  "exact_span_assessments": [
    {
      "body_start_offset": 0,
      "body_end_offset": 0,
      "exact_text": "verbatim supplied text",
      "role": "SUPPORTS | CONTRADICTS | NEUTRAL_CONTEXT"
    }
  ],
  "rationale": "source-bounded explanation"
}
```

This is an independent development review, not a Gold-label or threshold-setting exercise.
"""


def main() -> None:
    require(not OUT.exists(), "OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    roots = {
        "quality_execution": verify_root(QUALITY_EXEC, QUALITY_MARKER, QUALITY_ROOT),
        "builder_execution": verify_root(BUILDER_EXEC, BUILDER_MARKER, BUILDER_ROOT),
        "construction_adapter": verify_root(ADAPTER, ADAPTER_MARKER, ADAPTER_ROOT),
        "quality_request_freeze": verify_root(
            QUALITY_FREEZE, QUALITY_FREEZE_MARKER, QUALITY_FREEZE_ROOT),
        "builder_request_freeze": verify_root(
            BUILDER_FREEZE, BUILDER_FREEZE_MARKER, BUILDER_FREEZE_ROOT),
    }

    boundary = read_json(BOUNDARY)
    require(boundary["preferred_answer_included"] is False and
            boundary["historical_answer_included"] is False and
            boundary["system_formal_prediction_included"] is False and
            boundary["score_recommendation_included"] is False,
            "EXISTING_HUMAN_REVIEW_BOUNDARY_INCOMPATIBLE")

    source_manifest_path = ADAPTER / "source_manifest.json"
    require((source_manifest_path.stat().st_mode & 0o777) == 0o600,
            "PRIVATE_SOURCE_MANIFEST_NOT_PRIVATE")
    source_manifest = read_json(source_manifest_path)
    envelope = source_manifest["verified_construction_input"]
    document = envelope["construction_document"]
    token_authority = source_manifest["opaque_source_token_authority"]
    private_token = token_authority["opaque_source_token"]
    require(document["schema_version"] == "ConstructionEvidenceDocumentV1" and
            document["article_title_visible"] is False and
            document["bibliography_visible"] is False and
            sha(canonical(document)) == envelope["construction_document_sha256"] ==
                "5b6750308b2cfdf496200f21383399ae27431c75923c1d7af18cca5a24476c8f" and
            len(document["body_text"]) == 60000,
            "CONSTRUCTION_DOCUMENT_BINDING_MISMATCH")

    builder_freeze = read_json(BUILDER_FREEZE / "builder_request_manifest.json")
    provider_path = BUILDER_EXEC / "provider_response.json"
    provider = read_json(provider_path)
    require(digest(provider_path) ==
            "a7edfb40d2d84847007e996764161469873863765475f3a76577636367271315" and
            provider.get("model") == "deepseek-flash" and
            provider["choices"][0]["finish_reason"] == "stop",
            "AUTHENTIC_BUILDER_RESPONSE_MISMATCH")
    parsed = validate_builder_response(
        provider["choices"][0]["message"]["content"].encode("utf-8"),
        private_token, builder_freeze["expected_response_schema"])
    require(len(parsed["candidates"]) == 3,
            "AUTHENTIC_BUILDER_CANDIDATE_COUNT_MISMATCH")

    quality_freeze = read_json(QUALITY_FREEZE / "quality_request_manifest.json")
    original_order = quality_freeze["original_builder_candidate_order"]
    require(len(original_order) == 3 and
            [row["original_array_position"] for row in original_order] == [0, 1, 2],
            "FROZEN_ORIGINAL_BUILDER_ORDER_MISMATCH")
    body = document["body_text"]
    paragraphs = document["paragraphs"]
    packets: list[dict[str, Any]] = []
    packet_binding_records = []
    for position, candidate in enumerate(parsed["candidates"]):
        row = original_order[position]
        candidate_payload_sha = sha(canonical(candidate))
        cid = candidate_id(private_token, candidate)
        require(cid == row["candidate_id"] and
                candidate_payload_sha == row["candidate_payload_sha256"],
                "BUILDER_CANDIDATE_ID_OR_PAYLOAD_MISMATCH")
        start = row["body_start_offset"]
        end = row["body_end_offset"]
        exact_span = candidate["construction_evidence_span"]["exact_text"]
        require(body[start:end] == exact_span and
                sha(exact_span.encode("utf-8")) == row["exact_evidence_sha256"],
                "BUILDER_EXACT_EVIDENCE_OFFSET_MISMATCH")
        containing = [p for p in paragraphs
                      if p["start_offset"] <= start and end <= p["end_offset"]]
        require(len(containing) == 1 and
                containing[0]["span_id"] == row["anchor_id"],
                "BUILDER_PARAGRAPH_ANCHOR_MISMATCH")
        context_records = [paragraph_record(paragraphs[index])
                           for index in CONTEXT_PARAGRAPH_INDEXES[position]]
        require(all(body[record["body_start_offset"]:record["body_end_offset"]] ==
                    record["verbatim_text"] for record in context_records),
                "CONTEXT_PARAGRAPH_ROUND_TRIP_FAILURE")
        details = documented_details(position, body)
        packet = {
            "schema_version": "CODEBlindPilotPropositionEvidenceReviewPacketV1",
            "packet_id": f"pilot_blind_evidence_review_{position + 1:03d}",
            "review_task_id": f"pilot_human_review_task_{position + 1:03d}",
            "candidate_id": cid,
            "original_builder_array_position": position,
            "packet_order_role": "ORIGINAL_BUILDER_ORDER_NOT_RANKING",
            "scientific_proposition": candidate["neutral_proposition"],
            "builder_scientific_fields_as_written": {
                key: candidate[key] for key in (
                    "actor_or_intervention", "action", "relation_direction",
                    "response_or_endpoint", "biological_unit", "species",
                    "intrinsic_conditioning", "intrinsic_therapy_context",
                    "intrinsic_disease_or_genotype_context")
            },
            "cited_evidence_spans": [{
                "source_field": "body",
                "body_start_offset": start,
                "body_end_offset": end,
                "coordinate_end_semantics": "exclusive",
                "exact_text": exact_span,
                "exact_text_sha256": row["exact_evidence_sha256"],
                "paragraph_span_id": row["anchor_id"],
            }],
            "surrounding_results_context": context_records,
            "methods_context_state": "NOT_AVAILABLE_IN_FROZEN_60000_CHARACTER_BODY",
            "documented_experimental_details": details,
            "observation_interpretation_boundary": {
                "direct_observation_excerpts": details[
                    "direct_observation_excerpts"],
                "author_interpretation_excerpts": details[
                    "author_interpretation_excerpts"],
                "reviewer_must_assess_link": True,
                "packet_does_not_prejudge_support": True,
            },
            "private_provenance_references": {
                "construction_document_sha256": envelope[
                    "construction_document_sha256"],
                "canonical_body_sha256": envelope[
                    "controller_private_provenance"][
                        "canonical_body_sha256_revalidated"],
                "builder_provider_response_sha256": digest(provider_path),
                "builder_candidate_payload_sha256": candidate_payload_sha,
                "paragraph_span_ids": [record["paragraph_span_id"]
                                       for record in context_records],
                "provenance_manifest_record_id":
                    f"pilot_proposition_provenance_{position + 1:03d}",
            },
            "review_questions": [
                "Does the original experiment support the proposition AS WRITTEN?",
                "Is the intervention and comparator correctly represented?",
                "Is the measurement endpoint correctly represented?",
                "Are species or subject, cell or tissue type, dosage, and timing restrictions retained?",
                "Does the proposition overstate causality or mechanism?",
                "Is the evidence direct, indirect, or insufficient?",
                "Which exact supplied span supports or contradicts the judgment?",
            ],
            "review_response": None,
            "historical_answer": None,
            "preferred_answer": None,
            "system_prediction": None,
            "score_recommendation": None,
            "gold_label": None,
        }
        packets.append(packet)
        packet_binding_records.append({
            "record_id": packet["private_provenance_references"][
                "provenance_manifest_record_id"],
            "packet_id": packet["packet_id"],
            "candidate_id": cid,
            "original_builder_array_position": position,
            "candidate_payload_sha256": candidate_payload_sha,
            "exact_evidence_sha256": row["exact_evidence_sha256"],
            "body_start_offset": start,
            "body_end_offset": end,
            "paragraph_span_id": row["anchor_id"],
        })

    require(len(packets) == 3 and
            [packet["original_builder_array_position"] for packet in packets] ==
                [0, 1, 2] and
            len({packet["candidate_id"] for packet in packets}) == 3,
            "BLIND_PACKET_COUNT_ORDER_OR_IDENTITY_MISMATCH")

    packet_bytes = b"".join(canonical(packet) + b"\n" for packet in packets)
    token = private_token.encode("utf-8")
    forbidden_judgment_tokens = [
        b"QUALITY_PASS", b"QUALITY_FAIL", b"QUALITY_UNRESOLVED",
        b"EVIDENCE_SUPPORTS_PROPOSITION", b"SCIENTIFICALLY_COHERENT",
    ]
    require(token not in packet_bytes and
            all(value not in packet_bytes for value in forbidden_judgment_tokens),
            "BLIND_PACKET_LEAKAGE_DETECTED")

    quality_results_path = QUALITY_EXEC / "candidate_quality_results.json"
    quality_results = read_json(quality_results_path)
    quality_records = quality_results["candidate_records"]
    require(len(quality_records) == 3 and
            {record["candidate_id"] for record in quality_records} ==
                {packet["candidate_id"] for packet in packets},
            "PRIVATE_QUALITY_COMPARISON_IDENTITY_MISMATCH")

    roots_before = roots
    OUT.mkdir()
    packet_sha = write_jsonl(OUT / "blind_review_packets.jsonl", packets)
    instructions_raw = reviewer_instructions().encode("utf-8")
    instructions_sha = write_raw(OUT / "reviewer_instructions.md",
                                 instructions_raw)

    comparison_sha = write_json(
        OUT / "controller_private_quality_comparison.json", {
            "schema_version": "CODEControllerPrivateQualityComparisonV1",
            "access_classification": "CONTROLLER_PRIVATE_NOT_REVIEWER_VISIBLE",
            "comparison_locked_until":
                "ALL_THREE_INDEPENDENT_HUMAN_REVIEWS_COMPLETED_AND_FROZEN",
            "quality_execution_root_sha256": QUALITY_ROOT,
            "quality_results_source": {
                "artifact_path": quality_results_path.relative_to(ROOT).as_posix(),
                "sha256": digest(quality_results_path),
            },
            "records_by_opaque_candidate_id": sorted(
                quality_records, key=lambda record: record["candidate_id"]),
            "array_position_used_for_binding": False,
        }, private=True)

    provenance = {
        "schema_version": "CODEBlindPilotReviewProvenanceManifestV1",
        "reviewer_facing_file_allowlist": [
            "blind_review_packets.jsonl", "reviewer_instructions.md"],
        "controller_private_files": [
            "provenance_manifest.json",
            "controller_private_quality_comparison.json"],
        "authoritative_roots": roots_before,
        "supporting_artifacts": {
            "construction_source_manifest": {
                "artifact_path": source_manifest_path.relative_to(ROOT).as_posix(),
                "sha256": digest(source_manifest_path),
                "file_mode": "0600",
            },
            "construction_document_sha256": envelope[
                "construction_document_sha256"],
            "builder_provider_response": {
                "artifact_path": provider_path.relative_to(ROOT).as_posix(),
                "sha256": digest(provider_path),
                "file_mode": "0600",
            },
            "builder_original_order_binding": {
                "artifact_path": str((QUALITY_FREEZE /
                    "quality_request_manifest.json").relative_to(ROOT)),
                "sha256": digest(QUALITY_FREEZE /
                    "quality_request_manifest.json"),
                "controller_private": True,
            },
            "existing_bounded_human_review_boundary": {
                "artifact_path": BOUNDARY.relative_to(ROOT).as_posix(),
                "sha256": digest(BOUNDARY),
                "compatible_fields_reused": [
                    "answer is unfilled", "historical answer absent",
                    "preferred answer absent", "system prediction absent",
                    "score recommendation absent"],
                "scientific_schema_substitution": False,
            },
        },
        "packet_bindings": packet_binding_records,
        "packet_file_sha256": packet_sha,
        "reviewer_instructions_sha256": instructions_sha,
        "controller_private_quality_comparison_sha256": comparison_sha,
        "opaque_source_token_or_mapping_in_reviewer_files": False,
        "bibliographic_identity_in_reviewer_files": False,
        "quality_judgments_in_reviewer_files": False,
    }
    provenance_sha = write_json(OUT / "provenance_manifest.json",
                                provenance, private=True)

    roots_after = {
        "quality_execution": verify_root(QUALITY_EXEC, QUALITY_MARKER, QUALITY_ROOT),
        "builder_execution": verify_root(BUILDER_EXEC, BUILDER_MARKER, BUILDER_ROOT),
        "construction_adapter": verify_root(ADAPTER, ADAPTER_MARKER, ADAPTER_ROOT),
        "quality_request_freeze": verify_root(
            QUALITY_FREEZE, QUALITY_FREEZE_MARKER, QUALITY_FREEZE_ROOT),
        "builder_request_freeze": verify_root(
            BUILDER_FREEZE, BUILDER_FREEZE_MARKER, BUILDER_FREEZE_ROOT),
    }
    preservation = {
        "schema_version": "CODEBlindPilotReviewHistoricalPreservationV1",
        "authoritative_roots_before": roots_before,
        "authoritative_roots_after": roots_after,
        "authoritative_roots_unchanged": roots_before == roots_after,
        "quality_reexecuted": False,
        "builder_reexecuted": False,
        "papers_acquired": 0,
        "fresh_primary_started": False,
        "scientific_rules_modified": False,
        "historical_assets_modified": False,
        "network_calls": 0,
        "llm_calls": 0,
        "builder_calls": 0,
        "quality_calls": 0,
    }
    require(preservation["authoritative_roots_unchanged"],
            "AUTHORITATIVE_ROOT_CHANGED")
    preservation_sha = write_json(OUT / "historical_preservation.json",
                                  preservation)

    summary = {
        "schema_version": "CODEBlindPilotEvidenceReviewPreparationSummaryV1",
        "status": "PASS",
        "mode": "OFFLINE_REVIEW_PACKET_PREPARATION",
        "packet_count": 3,
        "complete_packet_count": 3,
        "all_three_packets_complete": True,
        "ready_for_independent_review": True,
        "original_builder_order_preserved": True,
        "propositions_regenerated_rewritten_filtered_or_ranked": False,
        "methods_context_available_in_frozen_body": False,
        "absent_experimental_details_inferred": False,
        "quality_judgments_in_reviewer_files": False,
        "controller_private_quality_comparison_present": True,
        "controller_private_quality_comparison_file_mode": "0600",
        "blind_review_packets_sha256": packet_sha,
        "reviewer_instructions_sha256": instructions_sha,
        "provenance_manifest_sha256": provenance_sha,
        "controller_private_quality_comparison_sha256": comparison_sha,
        "historical_preservation_sha256": preservation_sha,
        "network_calls": 0,
        "llm_calls": 0,
        "builder_calls": 0,
        "quality_calls": 0,
        "fresh_primary_started": False,
        "scientific_policy_changed": False,
        "historical_assets_modified": False,
        "next_stage_recommendation":
            "CONDUCT_AND_FREEZE_THREE_INDEPENDENT_HUMAN_REVIEWS_BEFORE_CONTROLLER_COMPARISON",
        "root_marker": ROOT_MARKER,
        "root_hash_algorithm": (
            "SHA256(compact canonical JSON of sorted "
            "[relative_path,SHA256(file)] pairs; root marker excluded; no final LF "
            "in hashed JSON)"),
    }
    write_json(OUT / "summary.json", summary)

    require({path.name for path in OUT.iterdir() if path.is_file()} ==
            FINAL_FILES - {ROOT_MARKER},
            "UNEXPECTED_FINAL_FILE_SET_BEFORE_MARKER")
    final_root = root_hash(OUT, ROOT_MARKER)
    write_raw(OUT / ROOT_MARKER, (final_root + "\n").encode("ascii"))
    require(root_hash(OUT, ROOT_MARKER) == final_root,
            "FINAL_ROOT_RECOMPUTATION_FAILED")
    require((OUT / "controller_private_quality_comparison.json").stat().st_mode &
            0o777 == 0o600 and
            (OUT / "provenance_manifest.json").stat().st_mode & 0o777 == 0o600,
            "CONTROLLER_PRIVATE_FILE_MODE_INVALID")
    print(json.dumps({
        "status": "PASS",
        "packet_count": 3,
        "ready_for_independent_review": True,
        "quality_judgments_in_reviewer_files": False,
        "network_calls": 0,
        "llm_calls": 0,
        "freeze_root_sha256": final_root,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
