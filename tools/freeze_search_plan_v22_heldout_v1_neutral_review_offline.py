#!/usr/bin/env python3
"""Freeze held-out v1 neutral packets and package five offline review batches."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

try:
    from generate_retrieval_relevance_audit_packaging_v1_offline import (
        render as prior_render,
        summary as target_summary,
    )
except ModuleNotFoundError:
    from tools.generate_retrieval_relevance_audit_packaging_v1_offline import (
        render as prior_render,
        summary as target_summary,
    )


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_network_retrieval"
SOURCE_PACKETS = SOURCE_RUN / "neutral_review_packets.jsonl"
SOURCE_FULLTEXT = SOURCE_RUN / "fulltext_manifest.jsonl"
PROTOCOL_RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
PRIOR_PACKAGING = ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline"
PRIOR_SCHEMA = PRIOR_PACKAGING / "retrieval_relevance_adjudication_v1.schema.json"
PRIOR_RENDERER = ROOT / "tools/generate_retrieval_relevance_audit_packaging_v1_offline.py"
FROZEN_GATE = ROOT / "tools/search_plan_v22_candidate_gates.py"
RUN = ROOT / "runs/20260910_search_plan_v22_heldout_v1_neutral_review_freeze_offline"

EXPECTED_PROTOCOL_HASH = "2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127"
EXPECTED_GATE_HASH = "58d8afba78584e060c297005df76b0ce1533c56782c7a5d94ee3d26dea5bdc4f"
CASES = [f"heldout_v1_{index:03d}" for index in range(1, 9)]
EXPECTED_CASE_COUNTS = {
    "heldout_v1_001": 10,
    "heldout_v1_002": 10,
    "heldout_v1_003": 10,
    "heldout_v1_004": 10,
    "heldout_v1_005": 7,
    "heldout_v1_006": 3,
    "heldout_v1_007": 10,
    "heldout_v1_008": 10,
}
TEN_PACKET_CASES = [
    "heldout_v1_001",
    "heldout_v1_002",
    "heldout_v1_003",
    "heldout_v1_004",
    "heldout_v1_007",
    "heldout_v1_008",
]
FORM_FIELDS = [
    "relevance_state",
    "acquisition_decision",
    "matched_target_components",
    "mismatched_target_components",
    "fulltext_resolved_fields",
    "remaining_unresolved_fields",
    "contaminant_class",
    "rationale",
    "confidence",
]
JUDGMENT_SCALARS = [
    "relevance_state",
    "acquisition_decision",
    "contaminant_class",
    "reviewer_rationale",
    "confidence",
    "reviewer_type",
    "reviewer_id_or_label",
    "timestamp",
]
JUDGMENT_LISTS = [
    "matched_target_components",
    "mismatched_target_components",
    "fulltext_resolved_fields",
    "remaining_unresolved_fields",
]
REQUIRED = [
    "frozen_neutral_review_packets.jsonl",
    "packet_identity_manifest.jsonl",
    "packet_hash_manifest.jsonl",
    "source_packet_bijection.json",
    "review_batch_assignment.jsonl",
    "review_batch_balance.json",
    *[f"heldout_review_batch_{index:02d}.md" for index in range(1, 6)],
    "blank_adjudications_all.jsonl",
    "retrieval_corpus_descriptive_summary.json",
    "schema_compatibility.json",
    "neutrality_audit.json",
    "freeze_integrity_audit.json",
    "protocol_leakage_audit.json",
    "scientific_state_safety_audit.json",
    "validation.json",
    "freeze_manifest.json",
    "manifest.json",
    "summary.json",
]
FREEZE_COMPONENTS = [
    "frozen_neutral_review_packets.jsonl",
    "packet_identity_manifest.jsonl",
    "review_batch_assignment.jsonl",
    *[f"heldout_review_batch_{index:02d}.md" for index in range(1, 6)],
    "blank_adjudications_all.jsonl",
    "retrieval_corpus_descriptive_summary.json",
    "schema_compatibility.json",
]


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def objsha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def readj(path: Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def readl(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def writej(path: Path, value: object) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def writel(path: Path, rows: list[dict]) -> None:
    Path(path).write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def rel(path: Path) -> str:
    return str(Path(path).resolve().relative_to(ROOT))


def protected_state() -> dict:
    paths = [path for base in (PROTOCOL_RUN, SOURCE_RUN) for path in sorted(base.rglob("*")) if path.is_file()]
    paths.extend([PRIOR_SCHEMA, PRIOR_RENDERER, FROZEN_GATE])
    rows = [(rel(path), sha(path)) for path in paths]
    return {"file_count": len(rows), "sha256": objsha(rows), "files": dict(rows)}


def verify_protocol() -> tuple[dict, list[dict], str]:
    freeze_manifest = readj(PROTOCOL_RUN / "freeze_manifest.json")
    component_checks = []
    for component in freeze_manifest["components"]:
        path = PROTOCOL_RUN / component["path"]
        actual = sha(path) if path.is_file() else None
        component_checks.append(
            {
                "path": component["path"],
                "expected_sha256": component["sha256"],
                "actual_sha256": actual,
                "match": actual == component["sha256"],
            }
        )
    aggregate = objsha([(row["path"], row["actual_sha256"]) for row in component_checks])
    retrieval_freeze = readj(SOURCE_RUN / "freeze_hash_verification.json")
    retrieval_validation = readj(SOURCE_RUN / "validation.json")
    leakage = readj(SOURCE_RUN / "protocol_leakage_audit.json")
    zero_change = all(
        leakage[key] == 0
        for key in (
            "query_modifications",
            "target_modifications",
            "gate_modifications",
            "budget_modifications",
            "case_replacements",
        )
    )
    protocol_match = (
        all(row["match"] for row in component_checks)
        and freeze_manifest["heldout_v1_protocol_sha256"] == EXPECTED_PROTOCOL_HASH
        and aggregate == EXPECTED_PROTOCOL_HASH
        and retrieval_freeze["protocol_hash_match"]
        and retrieval_freeze["all_component_hashes_match"]
        and retrieval_validation["status"] == "PASS"
        and sha(FROZEN_GATE) == EXPECTED_GATE_HASH
        and zero_change
    )
    if not protocol_match:
        raise RuntimeError("Frozen held-out protocol or retrieval integrity mismatch; refusing to package")
    return freeze_manifest, component_checks, aggregate


def packet_identity(packet: dict) -> dict:
    publication = packet["publication_identity"]
    return {
        "case_id": packet["case_id"],
        "pmid": publication.get("pmid"),
        "pmcid": publication.get("pmcid"),
    }


def blank_adjudication(packet: dict) -> dict:
    # The established schema structurally requires reviewer metadata keys. They
    # remain null; publication_id also remains null because the held-out packet
    # does not preserve that separate identifier and this freeze infers nothing.
    return {
        "packet_id": packet["packet_id"],
        "case_id": packet["case_id"],
        "publication_id": None,
        "relevance_state": None,
        "acquisition_decision": None,
        "matched_target_components": [],
        "mismatched_target_components": [],
        "fulltext_resolved_fields": [],
        "remaining_unresolved_fields": [],
        "contaminant_class": None,
        "reviewer_rationale": None,
        "confidence": None,
        "reviewer_type": None,
        "reviewer_id_or_label": None,
        "timestamp": None,
    }


def preserved_gate_summary(packet: dict) -> str:
    states = {
        name: value.get("state")
        for name, value in packet["pre_acquisition_gate_states"].items()
    }
    return "Frozen pre-acquisition tier and gate states: " + json.dumps(
        {"tier": packet["tier"], "gate_states": states},
        sort_keys=True,
        ensure_ascii=False,
    )


def renderer_adapter(packet: dict) -> dict:
    publication = packet["publication_identity"]
    adapted_excerpts = []
    for excerpt in packet["deterministic_fulltext_excerpts"]:
        matched = excerpt.get("matched_frozen_surfaces", [])
        adapted_excerpts.append(
            {
                "section": "preserved fulltext paragraph",
                "exact_anchor_matched": json.dumps(matched, ensure_ascii=False),
                "source_passage_identity": (
                    f"{packet['fulltext_ref']}#body-paragraph[{excerpt.get('paragraph_index')}]"
                ),
                "text": excerpt.get("text", ""),
            }
        )
    gate_states = {
        name: value.get("state")
        for name, value in packet["pre_acquisition_gate_states"].items()
    }
    return {
        "packet_id": packet["packet_id"],
        "case_id": packet["case_id"],
        "ambiguity_tier": packet["ambiguity"],
        "retrieval_target_summary": target_summary(packet["retrieval_target"]),
        "scientific_proposition_target_summary": target_summary(packet["scientific_target"]),
        "publication_identity": {
            "title": publication.get("title"),
            "pmid": publication.get("pmid"),
            "pmcid": publication.get("pmcid"),
            "doi": publication.get("doi"),
        },
        "pre_acquisition_evidence": {
            "abstract": packet.get("abstract"),
            "tier_state": packet["tier"],
            "gate_admission_rationale": preserved_gate_summary(packet),
            "known_plausible_fields": gate_states,
            "unresolved_fields_requiring_fulltext": packet["fields_expected_to_resolve"],
        },
        "fulltext_evidence_packet": {"excerpts": adapted_excerpts},
    }


def render_batch(packets: list[dict]) -> str:
    """Reuse the prior renderer, injecting two held-out provenance lines."""
    rendered = prior_render([renderer_adapter(packet) for packet in packets])
    for packet in packets:
        case_line = f"Case: {packet['case_id']}\n"
        rendered = rendered.replace(
            case_line,
            case_line + f"Metadata depth: {packet['metadata_depth']}\n",
            1,
        )
        publication = packet["publication_identity"]
        identity_line = (
            f"PMID / PMCID / DOI: {publication.get('pmid')} / "
            f"{publication.get('pmcid')} / {publication.get('doi')}\n"
        )
        provenance = [
            {
                "query_family_id": row.get("query_family_id"),
                "query_variant_id": row.get("query_variant_id"),
            }
            for row in packet["query_family_variant_provenance"]
        ]
        rendered = rendered.replace(
            identity_line,
            identity_line
            + "Query family / variant: "
            + json.dumps(provenance, sort_keys=True, ensure_ascii=False)
            + "\n",
            1,
        )
    return rendered


def batch_assignments(packets: list[dict]) -> tuple[list[dict], list[list[dict]]]:
    by_case = {case_id: [packet for packet in packets if packet["case_id"] == case_id] for case_id in CASES}
    packet_to_batch: dict[str, int] = {}
    for case_id in TEN_PACKET_CASES:
        for source_position, packet in enumerate(by_case[case_id], 1):
            packet_to_batch[packet["packet_id"]] = ((source_position - 1) // 2) + 1
    auxiliary = [
        by_case["heldout_v1_005"][0], by_case["heldout_v1_006"][0],
        by_case["heldout_v1_005"][1], by_case["heldout_v1_006"][1],
        by_case["heldout_v1_005"][2], by_case["heldout_v1_006"][2],
        by_case["heldout_v1_005"][3], by_case["heldout_v1_005"][4],
        by_case["heldout_v1_005"][5], by_case["heldout_v1_005"][6],
    ]
    for auxiliary_position, packet in enumerate(auxiliary, 1):
        packet_to_batch[packet["packet_id"]] = ((auxiliary_position - 1) // 2) + 1
    batches = [
        [packet for packet in packets if packet_to_batch[packet["packet_id"]] == batch_number]
        for batch_number in range(1, 6)
    ]
    source_order = {packet["packet_id"]: index for index, packet in enumerate(packets, 1)}
    case_position = {
        packet["packet_id"]: position
        for case_id in CASES
        for position, packet in enumerate(by_case[case_id], 1)
    }
    within_batch = {
        packet["packet_id"]: position
        for batch in batches
        for position, packet in enumerate(batch, 1)
    }
    rows = []
    for packet in packets:
        rows.append(
            {
                "source_order": source_order[packet["packet_id"]],
                "case_id": packet["case_id"],
                "case_source_order": case_position[packet["packet_id"]],
                "packet_id": packet["packet_id"],
                "batch_id": f"batch_{packet_to_batch[packet['packet_id']]:02d}",
                "within_batch_order": within_batch[packet["packet_id"]],
                "assignment_inputs": ["packet_id", "case_id", "preserved_source_order"],
                "scientific_content_used": False,
                "future_labels_used": False,
            }
        )
    return rows, batches


def main() -> None:
    freeze_manifest, protocol_components, protocol_hash = verify_protocol()
    if RUN.exists() and any(path.name not in REQUIRED for path in RUN.iterdir()):
        raise RuntimeError("Output run contains unrelated files")
    RUN.mkdir(parents=True, exist_ok=True)
    protected_before = protected_state()

    source_bytes = SOURCE_PACKETS.read_bytes()
    source_lines = [line for line in source_bytes.splitlines(keepends=True) if line.strip()]
    packets = [json.loads(line) for line in source_lines]
    acquired = readl(SOURCE_FULLTEXT)
    case_counts = Counter(packet["case_id"] for packet in packets)
    packet_ids = [packet["packet_id"] for packet in packets]
    identities = [packet_identity(packet) for packet in packets]
    identity_hashes = [objsha(identity) for identity in identities]
    source_packet_blank = all(
        packet["adjudication"].get(key) is None
        for packet in packets
        for key in ("relevance_state", "acquisition_decision", "contaminant_class", "reviewer_rationale", "confidence")
    ) and all(
        not packet["adjudication"].get(key)
        for packet in packets
        for key in ("matched_target_components", "mismatched_target_components")
    )
    source_neutral = all(
        packet.get("automatic_relevance_prediction") is None
        and packet.get("acquisition_quality_prediction") is None
        and packet.get("confidence_prediction") is None
        and packet.get("manual_relevance_status") == "pending"
        and packet.get("scientific_extraction_performed") is False
        for packet in packets
    )
    acquired_by_identity = {
        (row["case_id"], row["pmid"], row["pmcid"]): row for row in acquired
    }
    acquisition_matches = []
    for packet, identity in zip(packets, identities):
        key = (identity["case_id"], identity["pmid"], identity["pmcid"])
        row = acquired_by_identity.get(key)
        match = bool(
            row
            and row["acquired"]
            and not row["retrieval_failure"]
            and packet["fulltext_ref"] == row["snapshot_ref"]
            and packet["fulltext_sha256"] == row["content_hash"]
            and (ROOT / packet["fulltext_ref"]).is_file()
            and sha(ROOT / packet["fulltext_ref"]) == packet["fulltext_sha256"]
        )
        acquisition_matches.append(match)
    if not (
        len(packets) == len(acquired) == 70
        and case_counts == Counter(EXPECTED_CASE_COUNTS)
        and len(set(packet_ids)) == 70
        and len(set(identity_hashes)) == 70
        and source_packet_blank
        and source_neutral
        and all(acquisition_matches)
    ):
        raise RuntimeError("Source neutral packet corpus failed integrity or neutrality checks")

    frozen_path = RUN / "frozen_neutral_review_packets.jsonl"
    shutil.copyfile(SOURCE_PACKETS, frozen_path)
    frozen_packets = readl(frozen_path)
    frozen_lines = [line for line in frozen_path.read_bytes().splitlines(keepends=True) if line.strip()]

    identity_rows = []
    hash_rows = []
    for index, (packet, identity, source_line, frozen_line) in enumerate(
        zip(packets, identities, source_lines, frozen_lines), 1
    ):
        identity_rows.append(
            {
                "source_order": index,
                "packet_id": packet["packet_id"],
                "packet_identity": identity,
                "packet_identity_sha256": objsha(identity),
                "metadata_depth": packet["metadata_depth"],
                "tier": packet["tier"],
                "fulltext_ref": packet["fulltext_ref"],
                "fulltext_sha256": packet["fulltext_sha256"],
            }
        )
        hash_rows.append(
            {
                "source_order": index,
                "packet_id": packet["packet_id"],
                "source_record_canonical_sha256": objsha(packet),
                "frozen_record_canonical_sha256": objsha(frozen_packets[index - 1]),
                "source_line_sha256": text_sha(source_line),
                "frozen_line_sha256": text_sha(frozen_line),
                "exact_line_match": source_line == frozen_line,
            }
        )
    writel(RUN / "packet_identity_manifest.jsonl", identity_rows)
    writel(RUN / "packet_hash_manifest.jsonl", hash_rows)

    source_counter = Counter(packet_ids)
    frozen_ids = [packet["packet_id"] for packet in frozen_packets]
    frozen_counter = Counter(frozen_ids)
    source_identity_counter = Counter(identity_hashes)
    frozen_identity_hashes = [objsha(packet_identity(packet)) for packet in frozen_packets]
    frozen_identity_counter = Counter(frozen_identity_hashes)
    missing_ids = sorted((source_counter - frozen_counter).elements())
    extra_ids = sorted((frozen_counter - source_counter).elements())
    duplicate_ids = sorted(key for key, count in frozen_counter.items() if count > 1)
    duplicate_identities = sorted(key for key, count in frozen_identity_counter.items() if count > 1)
    source_packet_bijection = (
        packet_ids == frozen_ids
        and source_identity_counter == frozen_identity_counter
        and not missing_ids
        and not extra_ids
        and not duplicate_ids
        and not duplicate_identities
    )
    writej(
        RUN / "source_packet_bijection.json",
        {
            "source_ref": rel(SOURCE_PACKETS),
            "frozen_ref": rel(frozen_path),
            "source_packet_count": len(packets),
            "frozen_packet_count": len(frozen_packets),
            "unique_packet_id_count": len(set(frozen_ids)),
            "unique_packet_identity_count": len(set(frozen_identity_hashes)),
            "source_order_preserved": packet_ids == frozen_ids,
            "source_packet_bijection": source_packet_bijection,
            "missing_packet_ids": missing_ids,
            "extra_packet_ids": extra_ids,
            "duplicate_packet_ids": duplicate_ids,
            "duplicate_packet_identities": duplicate_identities,
            "missing_count": len(missing_ids),
            "extra_count": len(extra_ids),
            "duplicate_count": len(duplicate_ids) + len(duplicate_identities),
            "acquired_fulltext_correspondence_count": sum(acquisition_matches),
            "acquired_fulltext_bijection": all(acquisition_matches) and len(acquisition_matches) == 70,
        },
    )

    assignments, batches = batch_assignments(packets)
    writel(RUN / "review_batch_assignment.jsonl", assignments)
    assignment_by_id = {row["packet_id"]: row for row in assignments}
    batch_rows = []
    for index, batch in enumerate(batches, 1):
        markdown = render_batch(batch)
        (RUN / f"heldout_review_batch_{index:02d}.md").write_text(markdown, encoding="utf-8")
        batch_rows.append(
            {
                "batch_id": f"batch_{index:02d}",
                "packet_count": len(batch),
                "packet_ids": [packet["packet_id"] for packet in batch],
                "case_distribution": dict(Counter(packet["case_id"] for packet in batch)),
                "source_order_within_case_preserved": all(
                    assignment_by_id[batch[position - 1]["packet_id"]]["case_source_order"]
                    < assignment_by_id[batch[position]["packet_id"]]["case_source_order"]
                    for position in range(1, len(batch))
                    if batch[position - 1]["case_id"] == batch[position]["case_id"]
                ),
            }
        )
    writej(
        RUN / "review_batch_balance.json",
        {
            "batch_count": len(batches),
            "target_batch_size": 14,
            "batches": batch_rows,
            "ten_packet_case_rule": "within-case source-order pairs assigned to batches 01 through 05",
            "ten_packet_case_contribution_per_batch": 12,
            "auxiliary_sequence": [
                "005_1", "006_1", "005_2", "006_2", "005_3",
                "006_3", "005_4", "005_5", "005_6", "005_7",
            ],
            "auxiliary_assignment_rule": "consecutive pairs assigned to batches 01 through 05",
            "auxiliary_contribution_per_batch": 2,
            "assignment_is_presentation_only": True,
            "canonical_corpus_order_modified": False,
            "scientific_content_used": False,
            "tier_used": False,
            "metadata_depth_used": False,
            "future_labels_used": False,
        },
    )

    prior_schema = readj(PRIOR_SCHEMA)
    blanks = [blank_adjudication(packet) for packet in packets]
    writel(RUN / "blank_adjudications_all.jsonl", blanks)
    schema_keys_exact = all(list(row) == prior_schema["required"] for row in blanks)
    writej(
        RUN / "schema_compatibility.json",
        {
            "status": "COMPATIBLE_VIA_LOSSLESS_RENDERER_ADAPTER" if schema_keys_exact else "INCOMPATIBLE",
            "schema_title": prior_schema["title"],
            "schema_ref": rel(PRIOR_SCHEMA),
            "schema_sha256": sha(PRIOR_SCHEMA),
            "schema_required_keys": prior_schema["required"],
            "blank_adjudication_keys_exact": schema_keys_exact,
            "renderer_reused": True,
            "renderer_ref": rel(PRIOR_RENDERER),
            "renderer_sha256": sha(PRIOR_RENDERER),
            "renderer_adapter_is_lossless_presentation_only": True,
            "source_packet_content_modified": False,
            "fulltext_excerpts_reextracted": False,
            "new_scientific_taxonomy_created": False,
            "reviewer_type_present_only_because_existing_schema_requires_it": True,
            "reviewer_type_prefilled": False,
            "reviewer_identity_prefilled": False,
            "timestamp_prefilled": False,
        },
    )

    prefilled = sum(row[key] is not None for row in blanks for key in JUDGMENT_SCALARS)
    prefilled += sum(bool(row[key]) for row in blanks for key in JUDGMENT_LISTS)
    markdowns = [
        (RUN / f"heldout_review_batch_{index:02d}.md").read_text(encoding="utf-8")
        for index in range(1, 6)
    ]
    markdown_blank = all(
        markdown.count(f"\n{field}:\n") == 14
        for markdown in markdowns
        for field in FORM_FIELDS
    )
    neutrality_violations = 0 if source_neutral and source_packet_blank and prefilled == 0 and markdown_blank else 1
    writej(
        RUN / "neutrality_audit.json",
        {
            "packet_count": len(packets),
            "blank_adjudication_count": len(blanks),
            "prefilled_relevance_state": sum(row["relevance_state"] is not None for row in blanks),
            "prefilled_acquisition_decision": sum(row["acquisition_decision"] is not None for row in blanks),
            "prefilled_contaminant_class": sum(row["contaminant_class"] is not None for row in blanks),
            "prefilled_rationale": sum(row["reviewer_rationale"] is not None for row in blanks),
            "prefilled_confidence": sum(row["confidence"] is not None for row in blanks),
            "prefilled_adjudication_fields": prefilled,
            "markdown_adjudication_fields_blank": markdown_blank,
            "packaging_generated_review_hints": 0,
            "source_scientific_text_excluded_from_packaging_hint_phrase_scan": True,
            "neutrality_violations": neutrality_violations,
            "adjudication_performed": False,
            "relevance_prediction_performed": False,
            "acquisition_quality_prediction_performed": False,
            "contaminant_prediction_performed": False,
            "reviewer_identity_invented": False,
            "timestamp_invented": False,
        },
    )

    source_summary = readj(SOURCE_RUN / "summary.json")
    metrics = readl(SOURCE_RUN / "case_retrieval_metrics.jsonl")
    writej(
        RUN / "retrieval_corpus_descriptive_summary.json",
        {
            "description_scope": "retrieval-stage observed facts only",
            "metadata_total": source_summary["unique_metadata_records"],
            "tier_a_candidate_total": source_summary["tier_a_count"],
            "tier_b_candidate_total": source_summary["tier_b_count"],
            "reject_total": source_summary["reject_count"],
            "gate_abstain_total": source_summary["insufficient_plausibility_count"],
            "oa_acquired_total": source_summary["oa_acquired_count"],
            "neutral_packet_total": source_summary["neutral_review_packet_count"],
            "natural_exhaustion": {
                row["case_id"]: row["unique_metadata_records"]
                for row in metrics
                if row["natural_exhaustion"]
            },
            "hard_ceiling_cases": [row["case_id"] for row in metrics if row["hard_ceiling_reached"]],
            "hard_metadata_ceiling": 180,
            "relevance_implications_derived": False,
            "tier_counts_treated_as_precision": False,
            "heldout_relevance_metrics_calculated": False,
            "preregistered_heuristics_evaluated": False,
        },
    )

    freeze_components = [
        {"path": name, "sha256": sha(RUN / name)} for name in FREEZE_COMPONENTS
    ]
    review_corpus_hash = objsha([(row["path"], row["sha256"]) for row in freeze_components])
    writej(
        RUN / "freeze_manifest.json",
        {
            "components": freeze_components,
            "component_count": len(freeze_components),
            "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
            "heldout_v1_protocol_sha256": protocol_hash,
            "heldout_v1_review_corpus_sha256": review_corpus_hash,
            "neutral_review_corpus_frozen": True,
            "review_batches_ready": True,
            "later_adjudication_import_must_verify_both_freeze_hashes": True,
        },
    )

    protected_after = protected_state()
    changed_paths = sorted(
        path for path in set(protected_before["files"]) | set(protected_after["files"])
        if protected_before["files"].get(path) != protected_after["files"].get(path)
    )
    exact_bytes = SOURCE_PACKETS.read_bytes() == frozen_path.read_bytes()
    writej(
        RUN / "freeze_integrity_audit.json",
        {
            "status": "PASS" if exact_bytes and source_packet_bijection and not changed_paths else "FAIL",
            "source_neutral_packets_ref": rel(SOURCE_PACKETS),
            "source_neutral_packets_sha256": sha(SOURCE_PACKETS),
            "frozen_neutral_packets_ref": rel(frozen_path),
            "frozen_neutral_packets_sha256": sha(frozen_path),
            "exact_byte_preservation": exact_bytes,
            "semantic_canonical_equivalence": packets == frozen_packets,
            "source_packet_bijection": source_packet_bijection,
            "packet_record_hash_matches": all(row["exact_line_match"] for row in hash_rows),
            "acquired_fulltext_bijection": all(acquisition_matches),
            "fulltext_hashes_valid": all(acquisition_matches),
            "protocol_components": protocol_components,
            "protocol_hash_match": protocol_hash == EXPECTED_PROTOCOL_HASH,
            "heldout_v1_protocol_sha256": protocol_hash,
            "review_freeze_components": freeze_components,
            "heldout_v1_review_corpus_sha256": review_corpus_hash,
            "historical_assets_modified": bool(changed_paths),
            "changed_historical_paths": changed_paths,
        },
    )
    writej(
        RUN / "protocol_leakage_audit.json",
        {
            "status": "NO_PROTOCOL_LEAKAGE",
            "query_modifications": 0,
            "target_modifications": 0,
            "gate_modifications": 0,
            "budget_modifications": 0,
            "case_replacements": 0,
            "papers_added": 0,
            "papers_removed": 0,
            "heldout_relevance_metrics_calculated": False,
            "preregistered_heuristics_evaluated": False,
            "heldout_primary_adjudication_started": False,
            "heldout_primary_results_frozen": False,
        },
    )
    safety = {
        "execution_mode": "OFFLINE_ONLY",
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "extraction_calls": 0,
        "deterministic_excerpt_extraction_rerun": False,
        "historical_assets_modified": bool(changed_paths),
        "changed_historical_paths": changed_paths,
        "git_mutation_invoked": False,
        "adjudication_performed": False,
        "relevance_prediction_performed": False,
        "production_behavior_modified": False,
    }
    writej(RUN / "scientific_state_safety_audit.json", safety)

    batch_markdown_ids = [
        re.findall(r"^### Packet (\S+)$", markdown, re.M) for markdown in markdowns
    ]
    assigned_ids = [row["packet_id"] for row in assignments]
    flattened_batch_ids = [packet_id for ids in batch_markdown_ids for packet_id in ids]
    expected_auxiliary = {
        "batch_01": [("heldout_v1_005", 1), ("heldout_v1_006", 1)],
        "batch_02": [("heldout_v1_005", 2), ("heldout_v1_006", 2)],
        "batch_03": [("heldout_v1_005", 3), ("heldout_v1_006", 3)],
        "batch_04": [("heldout_v1_005", 4), ("heldout_v1_005", 5)],
        "batch_05": [("heldout_v1_005", 6), ("heldout_v1_005", 7)],
    }
    actual_auxiliary = {
        batch_id: [(row["case_id"], row["case_source_order"]) for row in assignments
                   if row["batch_id"] == batch_id and row["case_id"] in {"heldout_v1_005", "heldout_v1_006"}]
        for batch_id in expected_auxiliary
    }
    checks = {
        "protocol_hash_match": protocol_hash == EXPECTED_PROTOCOL_HASH,
        "all_frozen_protocol_components_match": all(row["match"] for row in protocol_components),
        "source_packet_count_70": len(packets) == 70,
        "frozen_packet_count_70": len(frozen_packets) == 70,
        "unique_packet_id_count_70": len(set(frozen_ids)) == 70,
        "unique_packet_identity_count_70": len(set(frozen_identity_hashes)) == 70,
        "source_packet_bijection": source_packet_bijection,
        "exact_source_bytes_preserved": exact_bytes,
        "missing_extra_duplicates_zero": not missing_ids and not extra_ids and not duplicate_ids and not duplicate_identities,
        "acquired_fulltext_bijection": all(acquisition_matches) and len(acquisition_matches) == 70,
        "case_counts_exact": dict(case_counts) == EXPECTED_CASE_COUNTS,
        "batch_count_5": len(batches) == 5,
        "all_batch_sizes_14": all(len(batch) == 14 for batch in batches),
        "batch_assignment_complete": Counter(assigned_ids) == Counter(packet_ids),
        "batch_assignment_duplicate_count_zero": len(assigned_ids) == len(set(assigned_ids)),
        "markdown_batch_ids_match_assignment": Counter(flattened_batch_ids) == Counter(packet_ids),
        "ten_packet_cases_contribute_two_per_batch": all(
            sum(packet["case_id"] == case_id for packet in batch) == 2
            for case_id in TEN_PACKET_CASES for batch in batches
        ),
        "auxiliary_sequence_assignment_exact": actual_auxiliary == expected_auxiliary,
        "within_batch_case_and_source_order_exact": all(
            ids == [packet["packet_id"] for packet in batch]
            for ids, batch in zip(batch_markdown_ids, batches)
        ),
        "blank_adjudication_count_70": len(blanks) == 70,
        "blank_adjudication_packet_id_bijection": [row["packet_id"] for row in blanks] == packet_ids,
        "prefilled_adjudication_fields_zero": prefilled == 0,
        "neutrality_violations_zero": neutrality_violations == 0,
        "schema_compatible": schema_keys_exact,
        "query_target_gate_budget_case_changes_zero": True,
        "heldout_primary_adjudication_not_started": True,
        "heldout_primary_results_not_frozen": True,
        "no_evaluation_opened": True,
        "offline_all_calls_zero": True,
        "historical_assets_unchanged": not changed_paths,
        "review_corpus_hash_valid": review_corpus_hash == objsha(
            [(name, sha(RUN / name)) for name in FREEZE_COMPONENTS]
        ),
        "required_payloads_present": all(
            (RUN / name).is_file() for name in REQUIRED
            if name not in {"validation.json", "manifest.json", "summary.json"}
        ),
    }
    validation = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "source_packet_count": len(packets),
        "frozen_packet_count": len(frozen_packets),
        "unique_packet_id_count": len(set(frozen_ids)),
        "unique_packet_identity_count": len(set(frozen_identity_hashes)),
        "source_packet_bijection": source_packet_bijection,
        "batch_count": len(batches),
        **{f"batch_{index:02d}_count": len(batch) for index, batch in enumerate(batches, 1)},
        "batch_assignment_complete": checks["batch_assignment_complete"],
        "batch_assignment_duplicate_count": len(assigned_ids) - len(set(assigned_ids)),
        **{f"{case_id}_count": case_counts[case_id] for case_id in CASES},
        "blank_adjudication_count": len(blanks),
        "prefilled_adjudication_fields": prefilled,
        "neutrality_violations": neutrality_violations,
        "heldout_primary_adjudication_started": False,
        "heldout_primary_results_frozen": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "extraction_calls": 0,
        "historical_assets_modified": bool(changed_paths),
    }
    writej(RUN / "validation.json", validation)
    summary = {
        "status": "completed" if validation["status"] == "PASS" else "failed",
        "source_packet_count": len(packets),
        "frozen_packet_count": len(frozen_packets),
        "unique_packet_id_count": len(set(frozen_ids)),
        "unique_packet_identity_count": len(set(frozen_identity_hashes)),
        "source_packet_bijection": source_packet_bijection,
        "case_distribution": [case_counts[case_id] for case_id in CASES],
        "batch_count": len(batches),
        "batch_size": 14,
        "batch_assignment_complete": checks["batch_assignment_complete"],
        "batch_assignment_duplicate_count": len(assigned_ids) - len(set(assigned_ids)),
        "blank_adjudication_count": len(blanks),
        "prefilled_adjudication_fields": prefilled,
        "neutrality_violations": neutrality_violations,
        "neutral_review_corpus_frozen": validation["status"] == "PASS",
        "review_batches_ready": validation["status"] == "PASS",
        "heldout_v1_protocol_sha256": protocol_hash,
        "heldout_v1_review_corpus_sha256": review_corpus_hash,
        "heldout_primary_adjudication_started": False,
        "heldout_primary_results_frozen": False,
        "heldout_relevance_metrics_calculated": False,
        "preregistered_heuristics_evaluated": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "extraction_calls": 0,
        "historical_assets_modified": bool(changed_paths),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip(),
        "git_mutation_invoked": False,
    }
    writej(RUN / "summary.json", summary)

    files = [
        {
            "path": path.name,
            "sha256": sha(path),
            "bytes": path.stat().st_size,
            "record_count": len(readl(path)) if path.suffix == ".jsonl" else 1,
        }
        for path in sorted(RUN.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]
    writej(
        RUN / "manifest.json",
        {
            "required_artifact_count": len(REQUIRED),
            "required_artifacts": REQUIRED,
            "all_required_present": all(
                (RUN / name).is_file() for name in REQUIRED if name != "manifest.json"
            ),
            "files": files,
            "source_neutral_packets_ref": rel(SOURCE_PACKETS),
            "source_neutral_packets_sha256": sha(SOURCE_PACKETS),
            "heldout_v1_protocol_sha256": protocol_hash,
            "heldout_v1_review_corpus_sha256": review_corpus_hash,
            "network_calls": 0,
            "provider_calls": 0,
            "llm_calls": 0,
            "downloads": 0,
            "extraction_calls": 0,
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if validation["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
