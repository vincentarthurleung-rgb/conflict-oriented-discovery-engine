#!/usr/bin/env python3
"""Freeze label-free PASS A and PASS B review surfaces for primary held-out-v2."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import run_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval as retrieval
from tools.run_search_plan_v22_heldout_v1_network_retrieval import deterministic_excerpts


RUN = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_neutral_review_freeze_offline"
SOURCE = retrieval.RUN
CASE_RUN = retrieval.CASE_RUN
QUERY_RUN = retrieval.QUERY_RUN
PROTOCOL_RUN = retrieval.BETA_PROTOCOL_RUN

TARGETS = CASE_RUN / "primary_heldout_v2_scientific_targets.jsonl"
BINDINGS = QUERY_RUN / "primary_heldout_v2_query_bindings.jsonl"
QUERIES = QUERY_RUN / "primary_heldout_v2_frozen_queries.jsonl"
BOUNDARY = PROTOCOL_RUN / "adjudication_boundary_v2.json"
METRICS = PROTOCOL_RUN / "metrics_spec_v2.json"
SELECTION = SOURCE / "primary_v2_acquisition_selection.jsonl"
PASS_A_SOURCE = SOURCE / "primary_v2_pass_a_blinded_views.jsonl"
SOURCE_MAPPING = SOURCE / "primary_v2_review_id_mapping.json"
FULLTEXT_MANIFEST = SOURCE / "primary_v2_fulltext_acquisition_manifest.jsonl"
FULLTEXT_PROVENANCE = SOURCE / "primary_v2_fulltext_provenance.jsonl"
PRIOR_REVIEW_SCHEMA = (
    ROOT
    / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline"
    / "retrieval_relevance_adjudication_v1.schema.json"
)
PRIOR_EXCERPT_BUILDER = ROOT / "tools/run_search_plan_v22_heldout_v1_network_retrieval.py"

EXPECTED = {
    "search_plan_v23_beta_2_protocol_sha256": "3033bd951cd3b296a6e8aeb6d08a9a5367e58faaa41669619b99f0df7691a835",
    "primary_heldout_v2_case_freeze_sha256": "0f4c4bf5daa707465f922f529dcf3c62617405597514b5c0133411d4f79ea4e9",
    "primary_heldout_v2_query_freeze_sha256": "4396d05d41b458c40ef65072932e2425bf0cfa62aa1c47cfbad7ac3301798888",
    "primary_heldout_v2_network_retrieval_sha256": "0da797b2b3b23a1884a03741abb60d51adedcb03ea9e6faf39ba897a829e46d8",
    "primary_v2_acquisition_selection_sha256": "a4059bc1c19c3d2bdecd2956ed6976561210b3a8d977a2a994225f31b8a57319",
    "primary_v2_pass_a_blinded_views_sha256": "0d9d096842085239ea7e546d6fc1b1d9e0c61972a6a1d76483647f31bfa971b5",
}
EXPECTED_CASE_COUNTS = {
    "heldout_v2_101": 10,
    "heldout_v2_102": 10,
    "heldout_v2_103": 10,
    "heldout_v2_104": 0,
    "heldout_v2_105": 10,
    "heldout_v2_106": 10,
    "heldout_v2_107": 0,
    "heldout_v2_108": 10,
}
PASS_A_DIR = "primary_v2_pass_a_batches"
PASS_B_DIR = "primary_v2_pass_b_batches"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def aggregate(pairs: list[list[str]]) -> str:
    return sha_bytes(canonical(pairs))


def verify_network_root() -> dict[str, Any]:
    manifest = load_json(SOURCE / "implementation_manifest.json")
    checks = []
    for name, expected_hash in manifest["aggregate_components"]:
        path = SOURCE / name
        actual = sha(path) if path.is_file() and not path.is_symlink() else None
        checks.append({
            "path": name,
            "expected_sha256": expected_hash,
            "actual_sha256": actual,
            "match": actual == expected_hash,
        })
    actual_root = aggregate([[row["path"], row["actual_sha256"]] for row in checks])
    require(all(row["match"] for row in checks), "network retrieval component mismatch")
    require(
        actual_root
        == manifest["primary_heldout_v2_network_retrieval_sha256"]
        == EXPECTED["primary_heldout_v2_network_retrieval_sha256"],
        "network retrieval root mismatch",
    )
    return {
        "status": "PASS",
        "expected_sha256": EXPECTED["primary_heldout_v2_network_retrieval_sha256"],
        "actual_sha256": actual_root,
        "component_count": len(checks),
        "all_components_match": True,
    }


def verify_roots() -> dict[str, Any]:
    upstream = retrieval.verify_all_roots()
    for key in (
        "search_plan_v23_beta_2_protocol_sha256",
        "primary_heldout_v2_case_freeze_sha256",
        "primary_heldout_v2_query_freeze_sha256",
    ):
        record = upstream["roots"][key]
        require(record["actual_sha256"] == EXPECTED[key], f"{key} mismatch")
    network = verify_network_root()
    selection_hash = sha(SELECTION)
    pass_a_hash = sha(PASS_A_SOURCE)
    require(selection_hash == EXPECTED["primary_v2_acquisition_selection_sha256"], "selection hash mismatch")
    require(pass_a_hash == EXPECTED["primary_v2_pass_a_blinded_views_sha256"], "PASS A hash mismatch")
    require(
        (SOURCE / "primary_v2_acquisition_selection_sha256").read_text().strip() == selection_hash,
        "selection hash sidecar mismatch",
    )
    require(
        (SOURCE / "primary_v2_pass_a_blinded_views_sha256").read_text().strip() == pass_a_hash,
        "PASS A hash sidecar mismatch",
    )
    roots = {
        key: {
            "status": "PASS",
            "expected_sha256": EXPECTED[key],
            "actual_sha256": upstream["roots"][key]["actual_sha256"],
        }
        for key in (
            "search_plan_v23_beta_2_protocol_sha256",
            "primary_heldout_v2_case_freeze_sha256",
            "primary_heldout_v2_query_freeze_sha256",
        )
    }
    roots["primary_heldout_v2_network_retrieval_sha256"] = network
    roots["primary_v2_acquisition_selection_sha256"] = {
        "status": "PASS", "expected_sha256": EXPECTED["primary_v2_acquisition_selection_sha256"],
        "actual_sha256": selection_hash,
    }
    roots["primary_v2_pass_a_blinded_views_sha256"] = {
        "status": "PASS", "expected_sha256": EXPECTED["primary_v2_pass_a_blinded_views_sha256"],
        "actual_sha256": pass_a_hash,
    }
    return {
        "artifact_schema_version": "PrimaryHeldoutV2NeutralReviewUpstreamVerificationV1",
        "status": "PASS",
        "all_six_authoritative_roots_verified": True,
        "roots": roots,
        "verified_offline_before_review_surface_construction": True,
    }


def protected_state() -> dict[str, str]:
    paths: set[Path] = set()
    for base in (PROTOCOL_RUN, CASE_RUN, QUERY_RUN, SOURCE):
        paths.update(path for path in base.rglob("*") if path.is_file())
    paths.update({
        PRIOR_REVIEW_SCHEMA,
        PRIOR_EXCERPT_BUILDER,
        ROOT / "tools/search_plan_v22_candidate_gates.py",
        ROOT / "tools/run_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval.py",
    })
    return {rel(path): sha(path) for path in sorted(paths)}


def neutral_order(rows: list[dict[str, Any]], namespace: str, identity_key: str) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            sha_bytes(f"{namespace}|{row[identity_key]}".encode("utf-8")),
            row[identity_key],
        ),
    )


def exact_taxonomies() -> tuple[list[str], list[str], list[Any]]:
    old_schema = load_json(PRIOR_REVIEW_SCHEMA)
    acquisition = old_schema["allOf"][1]["then"]["properties"]["acquisition_decision"]["enum"]
    metrics = load_json(METRICS)
    relevance = metrics["categorical_mappings"]["relevance_state"]
    contaminants = metrics["categorical_mappings"]["contaminant_class"]
    require(
        acquisition == [
            "JUSTIFIED",
            "BORDERLINE_BUT_JUSTIFIED",
            "NOT_JUSTIFIED",
            "UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE",
        ],
        "frozen acquisition taxonomy mismatch",
    )
    return acquisition, relevance, contaminants


def review_schemas() -> tuple[dict[str, Any], dict[str, Any]]:
    acquisition, relevance, contaminants = exact_taxonomies()
    common = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "additionalProperties": False,
        "type": "object",
    }
    pass_a = {
        **common,
        "title": "PrimaryHeldoutV2PassAAcquisitionAdjudicationV1",
        "description": "Frozen response schema only; no response record is created by this review freeze.",
        "required": ["review_id", "acquisition_decision", "rationale", "confidence", "reviewer_type"],
        "properties": {
            "review_id": {"type": "string", "pattern": r"^A2_[0-9]{4}$"},
            "acquisition_decision": {"type": "string", "enum": acquisition},
            "rationale": {"type": "string", "minLength": 1},
            "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
            "reviewer_type": {"const": "model_retrieval_adjudicator"},
        },
        "taxonomy_source_sha256": sha(PRIOR_REVIEW_SCHEMA),
    }
    pass_b = {
        **common,
        "title": "PrimaryHeldoutV2PassBRelevanceAdjudicationV1",
        "description": "Frozen response schema only; no response record is created by this review freeze.",
        "required": [
            "review_id", "relevance_state", "matched_target_components",
            "mismatched_target_components", "fulltext_resolved_fields",
            "remaining_unresolved_fields", "contaminant_class", "rationale",
            "confidence", "reviewer_type",
        ],
        "properties": {
            "review_id": {"type": "string", "pattern": r"^B2_[0-9]{4}$"},
            "relevance_state": {"type": "string", "enum": relevance},
            "matched_target_components": {"type": "array", "items": {"type": "string"}},
            "mismatched_target_components": {"type": "array", "items": {"type": "string"}},
            "fulltext_resolved_fields": {"type": "array", "items": {"type": "string"}},
            "remaining_unresolved_fields": {"type": "array", "items": {"type": "string"}},
            "contaminant_class": {"enum": contaminants},
            "rationale": {"type": "string", "minLength": 1},
            "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
            "reviewer_type": {"const": "model_retrieval_adjudicator"},
        },
        "taxonomy_source_sha256": sha(METRICS),
    }
    return pass_a, pass_b


PASS_A_INSTRUCTION = """# Primary held-out-v2 PASS A acquisition review\n\nReview only the supplied batch file and the frozen response schema. Judge whether acquisition was justified using only the pre-acquisition evidence visible in each record. Fulltext and later-stage material are outside this review boundary. Judge each record independently. Do not search, inspect repository files, calculate metrics, or infer evidence that is not visible. Use `reviewer_type = model_retrieval_adjudicator`.\n"""

PASS_B_INSTRUCTION = """# Primary held-out-v2 PASS B scientific-relevance review\n\nReview only the supplied batch file and the frozen response schema. ScientificPropositionTargetV1 is the sole scientific authority. Judge subject/intervention, relation family, endpoint, context or biological unit, therapy identity when applicable, and required evidence mode independently from the visible title, abstract, and frozen fulltext evidence. Keyword overlap and topic relatedness alone do not establish proposition compatibility. Judge each record independently. Do not search, inspect repository files, calculate metrics, or infer evidence that is not visible. Use `reviewer_type = model_retrieval_adjudicator`.\n"""


def inspect_corpus() -> dict[str, Any]:
    selection = load_jsonl(SELECTION)
    pass_a = load_jsonl(PASS_A_SOURCE)
    source_mapping = load_json(SOURCE_MAPPING)["sealed_mapping"]
    fulltexts = load_jsonl(FULLTEXT_MANIFEST)
    provenance = load_jsonl(FULLTEXT_PROVENANCE)
    targets = load_jsonl(TARGETS)
    bindings = load_jsonl(BINDINGS)
    queries = load_jsonl(QUERIES)

    require(len(selection) == len(pass_a) == len(source_mapping) == len(fulltexts) == len(provenance) == 60,
            "selected/acquired corpus count mismatch")
    selected_ids = [row["candidate_id"] for row in selection]
    mapped_ids = [row["candidate_id"] for row in source_mapping]
    fulltext_ids = [row["candidate_id"] for row in fulltexts]
    provenance_ids = [row["candidate_id"] for row in provenance]
    require(selected_ids == mapped_ids == fulltext_ids == provenance_ids, "selected identity/order mismatch")
    require(len(set(selected_ids)) == 60, "duplicate selected candidate identity")
    require([row["review_id"] for row in source_mapping] == [row["review_id"] for row in pass_a],
            "PASS A identity mapping mismatch")
    require(all(row["acquisition_status"] == "SUCCESS" for row in fulltexts), "fulltext acquisition not complete")
    require(all(not row["replacement_performed"] for row in fulltexts), "replacement detected")
    require(Counter(row["case_id"] for row in selection) == Counter(EXPECTED_CASE_COUNTS),
            "per-case selected counts mismatch")

    target_by_case = {row["case_id"]: row for row in targets}
    binding_by_case = {row["case_id"]: row for row in bindings}
    a_by_review = {row["review_id"]: row for row in pass_a}
    a_by_candidate = {
        mapping["candidate_id"]: a_by_review[mapping["review_id"]] for mapping in source_mapping
    }
    fulltext_by_candidate = {row["candidate_id"]: row for row in fulltexts}
    provenance_by_candidate = {row["candidate_id"]: row for row in provenance}
    for row in selection:
        candidate = row["candidate_id"]
        case_id = row["case_id"]
        require(a_by_candidate[candidate]["ScientificPropositionTargetV1"] == target_by_case[case_id],
                f"PASS A target mismatch: {candidate}")
        ft = fulltext_by_candidate[candidate]
        require(ft["case_id"] == case_id, f"fulltext case mismatch: {candidate}")
        require(ft["pmcid"] == row["publication_metadata"]["pmcid"], f"PMCID mismatch: {candidate}")
        path = ROOT / ft["snapshot_ref"]
        require(path.is_file() and not path.is_symlink(), f"physical fulltext missing: {candidate}")
        require(sha(path) == ft["raw_content_sha256"], f"raw fulltext hash mismatch: {candidate}")
        root = ET.parse(path).getroot()
        parsed_hash = sha_bytes(ET.tostring(root, encoding="utf-8"))
        require(parsed_hash == ft["parsed_content_sha256"], f"parsed fulltext hash mismatch: {candidate}")
        prov = provenance_by_candidate[candidate]
        require(
            prov["raw_content_sha256"] == ft["raw_content_sha256"]
            and prov["parsed_content_sha256"] == ft["parsed_content_sha256"],
            f"fulltext provenance mismatch: {candidate}",
        )
    return {
        "selection": selection,
        "pass_a": pass_a,
        "source_mapping": source_mapping,
        "fulltexts": fulltexts,
        "provenance": provenance,
        "target_by_case": target_by_case,
        "binding_by_case": binding_by_case,
        "queries": queries,
        "a_by_candidate": a_by_candidate,
        "fulltext_by_candidate": fulltext_by_candidate,
        "provenance_by_candidate": provenance_by_candidate,
    }


def make_pass_a(corpus: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source_map = {row["review_id"]: row["candidate_id"] for row in corpus["source_mapping"]}
    ordered = neutral_order(corpus["pass_a"], "PRIMARY_V2_PASS_A_NEUTRAL", "review_id")
    rendered = []
    sealed = []
    record_checks = []
    for index, source in enumerate(ordered, 1):
        review_id = f"A2_{index:04d}"
        row = dict(source)
        source_review_id = row["review_id"]
        row["review_id"] = review_id
        rendered.append(row)
        sealed.append({
            "review_id": review_id,
            "source_review_id": source_review_id,
            "candidate_id": source_map[source_review_id],
        })
        source_evidence = {key: value for key, value in source.items() if key != "review_id"}
        rendered_evidence = {key: value for key, value in row.items() if key != "review_id"}
        record_checks.append({
            "review_id": review_id,
            "source_record_sha256": sha_bytes(canonical(source)),
            "source_evidence_sha256": sha_bytes(canonical(source_evidence)),
            "batched_evidence_sha256": sha_bytes(canonical(rendered_evidence)),
            "evidence_content_match": source_evidence == rendered_evidence,
        })
    require(all(row["evidence_content_match"] for row in record_checks), "PASS A evidence changed")
    audit = {
        "artifact_schema_version": "PrimaryHeldoutV2PassAViewPreservationAuditV1",
        "status": "PASS",
        "source_ref": rel(PASS_A_SOURCE),
        "source_sha256": sha(PASS_A_SOURCE),
        "expected_source_sha256": EXPECTED["primary_v2_pass_a_blinded_views_sha256"],
        "byte_hash_match": True,
        "canonical_record_equivalence_verified": True,
        "pass_a_record_count": 60,
        "content_changes": 0,
        "only_presentation_identity_changed_in_batches": True,
        "record_checks": record_checks,
    }
    return rendered, sealed, audit


def make_pass_b(corpus: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    identity_rows = [{"candidate_id": row["candidate_id"]} for row in corpus["selection"]]
    ordered = neutral_order(identity_rows, "PRIMARY_V2_PASS_B_NEUTRAL", "candidate_id")
    views = []
    sealed = []
    evidence_manifest = []
    for index, item in enumerate(ordered, 1):
        candidate_id = item["candidate_id"]
        selection = next(row for row in corpus["selection"] if row["candidate_id"] == candidate_id)
        case_id = selection["case_id"]
        pass_a = corpus["a_by_candidate"][candidate_id]
        fulltext = corpus["fulltext_by_candidate"][candidate_id]
        source_provenance = corpus["provenance_by_candidate"][candidate_id]
        query_rows = [row for row in corpus["queries"] if row["case_id"] == case_id]
        target_contract = retrieval.gate_target(
            corpus["target_by_case"][case_id], corpus["binding_by_case"][case_id], query_rows
        )
        surfaces = target_contract["subject_surfaces"] + target_contract["endpoint_surfaces"]
        fulltext_path = ROOT / fulltext["snapshot_ref"]
        extracted = deterministic_excerpts(fulltext_path, surfaces)
        review_id = f"B2_{index:04d}"
        evidence = []
        anchors = []
        for excerpt_index, excerpt in enumerate(extracted, 1):
            evidence_id = f"{review_id}:E{excerpt_index:02d}"
            text = excerpt["text"]
            anchor = f"body-paragraph[{excerpt['paragraph_index']}]"
            evidence.append({
                "evidence_id": evidence_id,
                "paragraph_anchor": anchor,
                "text": text,
                "text_sha256": sha_bytes(text.encode("utf-8")),
            })
            anchors.append({
                "evidence_id": evidence_id,
                "paragraph_anchor": anchor,
                "matched_frozen_surfaces": excerpt["matched_frozen_surfaces"],
            })
        view = {
            "artifact_schema_version": "PrimaryV2PassBBlindedViewV1",
            "review_id": review_id,
            "ScientificPropositionTargetV1": pass_a["ScientificPropositionTargetV1"],
            "title": pass_a["title"],
            "abstract": pass_a["abstract"],
            "frozen_legal_fulltext_excerpts": evidence,
            "fulltext_excerpt_provenance": {
                "source_kind": "NCBI_PMC_OA_XML",
                "raw_fulltext_sha256": fulltext["raw_content_sha256"],
                "parsed_fulltext_sha256": fulltext["parsed_content_sha256"],
                "construction_mechanism": "heldout_v1_deterministic_excerpts_v1",
                "evidence_anchors": anchors,
            },
        }
        views.append(view)
        sealed.append({"review_id": review_id, "candidate_id": candidate_id})
        evidence_manifest.append({
            "artifact_schema_version": "PrimaryV2PassBFulltextEvidenceManifestV1",
            "review_id": review_id,
            "candidate_id": candidate_id,
            "case_id": case_id,
            "fulltext_source": source_provenance["fulltext_source"],
            "fulltext_snapshot_ref": fulltext["snapshot_ref"],
            "raw_fulltext_sha256": fulltext["raw_content_sha256"],
            "parsed_fulltext_sha256": fulltext["parsed_content_sha256"],
            "construction_mechanism": "heldout_v1_deterministic_excerpts_v1",
            "construction_source_ref": rel(PRIOR_EXCERPT_BUILDER),
            "construction_source_sha256": sha(PRIOR_EXCERPT_BUILDER),
            "outcome_or_label_inputs_used": False,
            "excerpt_count": len(evidence),
            "evidence_anchors": anchors,
            "evidence_text_sha256": [row["text_sha256"] for row in evidence],
            "fulltext_body_paragraphs_available": bool(extracted),
        })
    require(len(views) == len(sealed) == len(evidence_manifest) == 60, "PASS B construction count mismatch")
    return views, sealed, evidence_manifest


def make_batches(
    rows: list[dict[str, Any]], pass_name: str, directory: str
) -> tuple[dict[str, bytes], dict[str, Any]]:
    outputs = {}
    batches = []
    require(len(rows) == 60, f"{pass_name} batch source count mismatch")
    for index in range(6):
        batch = rows[index * 10:(index + 1) * 10]
        filename = f"{directory}/primary_v2_{pass_name.lower()}_batch_{index + 1:02d}.jsonl"
        body = jsonl(batch)
        outputs[filename] = body
        batches.append({
            "batch_id": f"{pass_name.upper()}_BATCH_{index + 1:02d}",
            "path": filename,
            "sha256": sha_bytes(body),
            "record_count": len(batch),
            "review_ids": [row["review_id"] for row in batch],
        })
    manifest = {
        "artifact_schema_version": f"PrimaryHeldoutV2{pass_name.upper()}BatchManifestV1",
        "batch_count": 6,
        "batch_size": 10,
        "record_count": 60,
        "assignment_rule": "namespace-specific SHA-256 ordering over frozen identity; contiguous groups of ten",
        "scientific_content_used_for_assignment": False,
        "future_labels_used_for_assignment": False,
        "case_performance_summaries_present": False,
        "tier_encoded_in_filename_or_id": False,
        "physical_files_only": True,
        "symlinks_present": False,
        "batches": batches,
    }
    return outputs, manifest


def nested_key_findings(value: Any, path: str, forbidden: set[str], skip_target: bool = True) -> list[dict[str, Any]]:
    findings = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            if key in forbidden:
                findings.append({"location": child_path, "kind": "forbidden_field", "matched": key})
            if skip_target and key == "ScientificPropositionTargetV1":
                continue
            findings.extend(nested_key_findings(child, child_path, forbidden, skip_target))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(nested_key_findings(child, f"{path}/{index}", forbidden, skip_target))
    return findings


def string_value_findings(value: Any, path: str, patterns: list[tuple[str, re.Pattern[str]]]) -> list[dict[str, Any]]:
    findings = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "ScientificPropositionTargetV1":
                continue
            findings.extend(string_value_findings(child, f"{path}/{key}", patterns))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(string_value_findings(child, f"{path}/{index}", patterns))
    elif isinstance(value, str):
        for name, pattern in patterns:
            match = pattern.search(value)
            if match:
                findings.append({
                    "location": path, "kind": "forbidden_internal_value",
                    "matched_pattern": name, "matched_text": match.group(0),
                })
    return findings


def leakage_audit(pass_a_rows: list[dict[str, Any]], pass_b_rows: list[dict[str, Any]]) -> dict[str, Any]:
    boundary = load_json(BOUNDARY)
    a_allowed = set(boundary["pass_a"]["allowed_fields"]) | {"artifact_schema_version", "review_id"}
    b_allowed = set(boundary["pass_b"]["allowed_fields"]) | {"artifact_schema_version", "review_id"}
    forbidden_keys = {
        "tier", "base_tier", "final_tier", "final_preacquisition_tier",
        "final_v23_beta_disposition", "v22_tier", "gate", "gate_states",
        "P0", "P0_state", "P1", "P1_state", "P2", "P2_state",
        "policy_a", "policy_a_action", "query_id", "query_family", "query_rank",
        "candidate_rank", "preacquisition_rank_within_tiered_pool", "metadata_depth",
        "retrieval_depth", "performance_metrics", "metrics", "ambiguity_stratum",
        "acquisition_decision", "relevance_state", "contaminant_class",
    }
    acquisition, relevance, contaminants = exact_taxonomies()
    label_values = acquisition + relevance + [value for value in contaminants if value is not None]
    patterns = [
        ("tier_literal", re.compile(r"\bTIER_[AB]\b")),
        ("module_state_field", re.compile(r"\bP[012]_state\b", re.I)),
        ("policy_a_marker", re.compile(r"\b(?:policy_a|DEMOTE_A_TO_B)\b", re.I)),
        ("query_identifier", re.compile(r"\bprimary_v2_heldout_v2_[0-9]{3}_[A-Z]\b")),
        ("query_or_rank_field", re.compile(r"\b(?:query_id|query_family|query_rank|candidate_rank|metadata_depth|retrieval_depth)\b", re.I)),
        ("source_pass_a_identifier", re.compile(r"\bprimary_pass_a_review_[0-9]{4}\b")),
        ("candidate_identifier", re.compile(r"\bheldout_v2_[0-9]{3}:pmid:[0-9]+\b")),
        ("metric_identifier", re.compile(r"\b(?:overall_direct_relevance|overall_acquisition_justification|overall_acquisition_acceptability|tier_a_direct_relevance|tier_b_direct_relevance|contamination_rate)\b", re.I)),
        ("prefilled_label", re.compile(r"\b(?:" + "|".join(re.escape(value) for value in label_values) + r")\b")),
    ]
    findings = []
    for pass_name, rows, allowed in (("PASS_A", pass_a_rows, a_allowed), ("PASS_B", pass_b_rows, b_allowed)):
        for row in rows:
            review_id = row["review_id"]
            unexpected = sorted(set(row) - allowed)
            findings.extend({
                "artifact": pass_name, "review_id": review_id,
                "location": f"/{key}", "kind": "root_field_not_allowed_by_boundary", "matched": key,
            } for key in unexpected)
            for finding in nested_key_findings(row, "", forbidden_keys):
                findings.append({"artifact": pass_name, "review_id": review_id, **finding})
            for finding in string_value_findings(row, "", patterns):
                findings.append({"artifact": pass_name, "review_id": review_id, **finding})
    require(not findings, f"review-surface leakage detected: {findings[:3]}")
    return {
        "artifact_schema_version": "PrimaryHeldoutV2ReviewSurfaceLeakageAuditV1",
        "status": "PASS",
        "audit_scope": [
            "PASS A batch record nested fields and rendered string values",
            "PASS B source/batch record nested fields and rendered string values",
        ],
        "boundary_ref": rel(BOUNDARY),
        "boundary_sha256": sha(BOUNDARY),
        "exact_frozen_target_subtrees_exempt_from_forbidden-key scanning": True,
        "schema_and_instruction_taxonomy_definitions_are_not_prefilled_review_records": True,
        "forbidden_exposure_findings": 0,
        "findings": findings,
        "nested_objects_checked": True,
        "rendered_text_values_checked": True,
        "pass_a_allowed_root_fields": sorted(a_allowed),
        "pass_b_allowed_root_fields": sorted(b_allowed),
    }


def zero_yield_audit() -> dict[str, Any]:
    metrics = load_json(METRICS)
    network_summary = load_json(SOURCE / "summary.json")
    per_case = {row["case_id"]: row for row in network_summary["per_case"]}
    zero_rules = {row["metric_id"]: row["reported_values"]["zero_denominator"] for row in metrics["metrics"]}
    require(zero_rules and all(
        rule == {"fraction": None, "percentage": None, "status": "UNDEFINED_ZERO_DENOMINATOR"}
        for rule in zero_rules.values()
    ), "frozen zero-denominator reporting is not explicit or consistent")
    cases = []
    for case_id, expected_metadata in (("heldout_v2_104", 180), ("heldout_v2_107", 0)):
        row = per_case[case_id]
        require(row["deduplicated_metadata_candidates"] == expected_metadata, f"{case_id} metadata changed")
        require(row["selected_fulltext_count"] == 0, f"{case_id} selection changed")
        cases.append({
            "case_id": case_id,
            "metadata_record_count": expected_metadata,
            "selected_paper_count": 0,
            "acquired_paper_count": 0,
            "replacement_performed": False,
            "per_case_metric_denominator_state": "ZERO",
            "frozen_zero_denominator_representation": {
                "fraction": None,
                "percentage": None,
                "status": "UNDEFINED_ZERO_DENOMINATOR",
            },
        })
    return {
        "artifact_schema_version": "PrimaryHeldoutV2ZeroYieldCaseReportingAuditV1",
        "status": "PASS",
        "metrics_spec_ref": rel(METRICS),
        "metrics_spec_sha256": sha(METRICS),
        "metrics_spec_modified": False,
        "zero_denominator_behavior_explicitly_defined": True,
        "zero_denominator_rules_by_metric": zero_rules,
        "cases": cases,
        "case_replacement_performed": False,
        "additional_search_performed": False,
        "rejected_or_abstained_papers_sampled": False,
        "primary_metrics_calculated": False,
    }


def build_outputs(protected: dict[str, str]) -> dict[str, bytes]:
    roots = verify_roots()
    corpus = inspect_corpus()
    pass_a_rows, pass_a_mapping, pass_a_audit = make_pass_a(corpus)
    pass_b_rows, pass_b_mapping, evidence_manifest = make_pass_b(corpus)
    pass_a_batches, pass_a_batch_manifest = make_batches(pass_a_rows, "pass_a", PASS_A_DIR)
    pass_b_batches, pass_b_batch_manifest = make_batches(pass_b_rows, "pass_b", PASS_B_DIR)
    pass_a_schema, pass_b_schema = review_schemas()
    leakage = leakage_audit(pass_a_rows, pass_b_rows)
    zero_yield = zero_yield_audit()

    outputs: dict[str, bytes] = {}
    outputs["upstream_root_verification.json"] = pretty(roots)
    identity_rows = []
    a_candidate_to_id = {row["candidate_id"]: row["review_id"] for row in pass_a_mapping}
    b_candidate_to_id = {row["candidate_id"]: row["review_id"] for row in pass_b_mapping}
    for selection in corpus["selection"]:
        candidate = selection["candidate_id"]
        fulltext = corpus["fulltext_by_candidate"][candidate]
        identity_rows.append({
            "selection_id": selection["selection_id"],
            "candidate_id": candidate,
            "case_id": selection["case_id"],
            "pmid": selection["publication_metadata"]["pmid"],
            "pmcid": selection["publication_metadata"]["pmcid"],
            "pass_a_neutral_review_id": a_candidate_to_id[candidate],
            "pass_b_neutral_review_id": b_candidate_to_id[candidate],
            "fulltext_raw_sha256": fulltext["raw_content_sha256"],
            "fulltext_parsed_sha256": fulltext["parsed_content_sha256"],
        })
    outputs["selected60_identity_manifest.json"] = pretty({
        "artifact_schema_version": "PrimaryHeldoutV2Selected60IdentityManifestV1",
        "selected_paper_count": 60,
        "successfully_acquired_paper_count": 60,
        "identity_equality": True,
        "selection_pass_a_mapping_fulltext_manifest_exact_identity_equality": True,
        "papers_added": 0, "papers_removed": 0, "papers_replaced": 0,
        "per_case_selected_counts": EXPECTED_CASE_COUNTS,
        "records": identity_rows,
    })
    outputs["pass_a_view_preservation_audit.json"] = pretty(pass_a_audit)
    outputs.update(pass_a_batches)
    outputs["primary_v2_pass_a_batch_manifest.json"] = pretty(pass_a_batch_manifest)
    pass_b_bytes = jsonl(pass_b_rows)
    pass_b_hash = sha_bytes(pass_b_bytes)
    outputs["primary_v2_pass_b_blinded_views.jsonl"] = pass_b_bytes
    outputs["primary_v2_pass_b_blinded_views_sha256"] = (pass_b_hash + "\n").encode("ascii")
    outputs["primary_v2_pass_b_fulltext_evidence_manifest.jsonl"] = jsonl(evidence_manifest)
    outputs.update(pass_b_batches)
    outputs["primary_v2_pass_b_batch_manifest.json"] = pretty(pass_b_batch_manifest)
    outputs["primary_v2_pass_a_review_schema.json"] = pretty(pass_a_schema)
    outputs["primary_v2_pass_b_review_schema.json"] = pretty(pass_b_schema)
    outputs["pass_a_evaluator_instruction.md"] = PASS_A_INSTRUCTION.encode("utf-8")
    outputs["pass_b_evaluator_instruction.md"] = PASS_B_INSTRUCTION.encode("utf-8")
    outputs["primary_v2_pass_a_sealed_identity_mapping.json"] = pretty({
        "artifact_schema_version": "PrimaryHeldoutV2PassASealedIdentityMappingV1",
        "adjudicator_exposure_authorized": False,
        "sealed_mapping": pass_a_mapping,
    })
    outputs["primary_v2_pass_b_sealed_identity_mapping.json"] = pretty({
        "artifact_schema_version": "PrimaryHeldoutV2PassBSealedIdentityMappingV1",
        "adjudicator_exposure_authorized": False,
        "sealed_mapping": pass_b_mapping,
    })
    outputs["review_surface_leakage_audit.json"] = pretty(leakage)
    outputs["zero_yield_case_reporting_audit.json"] = pretty(zero_yield)
    workspace = {
        "artifact_schema_version": "PrimaryHeldoutV2EvaluatorWorkspaceManifestV1",
        "workspace_creation_deferred": True,
        "no_evaluator_invoked": True,
        "physical_copy_only": True,
        "symlinks_allowed": False,
        "repository_access_allowed": False,
        "pass_a": {
            "one_workspace_per_batch": True,
            "required_common_files": [
                {"path": "pass_a_evaluator_instruction.md", "sha256": sha_bytes(outputs["pass_a_evaluator_instruction.md"])},
                {"path": "primary_v2_pass_a_review_schema.json", "sha256": sha_bytes(outputs["primary_v2_pass_a_review_schema.json"])},
            ],
            "exactly_one_batch_file_required": True,
            "batch_files": pass_a_batch_manifest["batches"],
        },
        "pass_b": {
            "one_workspace_per_batch": True,
            "required_common_files": [
                {"path": "pass_b_evaluator_instruction.md", "sha256": sha_bytes(outputs["pass_b_evaluator_instruction.md"])},
                {"path": "primary_v2_pass_b_review_schema.json", "sha256": sha_bytes(outputs["primary_v2_pass_b_review_schema.json"])},
            ],
            "exactly_one_batch_file_required": True,
            "batch_files": pass_b_batch_manifest["batches"],
        },
        "forbidden_workspace_material": [
            "retrieval run", "metrics", "other pass", "sealed identity mapping",
            "other batch files", "repository-relative links", "symlinks",
        ],
    }
    outputs["evaluator_workspace_manifest.json"] = pretty(workspace)
    outputs["scientific_state_safety_audit.json"] = pretty({
        "artifact_schema_version": "PrimaryHeldoutV2NeutralReviewSafetyAuditV1",
        "offline_only": True,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "new_scientific_adjudication_calls": 0,
        "pass_a_labels_created": 0, "pass_b_labels_created": 0,
        "primary_metrics_calculated": False,
        "scientific_tuning_performed": False,
        "query_or_target_changes": 0,
        "case_replacements": 0,
        "historical_assets_modified": False,
        "protected_file_count": len(protected),
        "protected_state_before": protected,
        "protected_state_after": protected,
    })

    aggregate_names = sorted(outputs)
    components = [[name, sha_bytes(outputs[name])] for name in aggregate_names]
    freeze_root = aggregate(components)
    outputs["freeze_manifest.json"] = pretty({
        "artifact_schema_version": "PrimaryHeldoutV2NeutralReviewFreezeManifestV1",
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": components,
        "component_count": len(components),
        "primary_heldout_v2_neutral_review_freeze_sha256": freeze_root,
        "existing_pass_a_source_sha256": EXPECTED["primary_v2_pass_a_blinded_views_sha256"],
        "primary_v2_pass_b_blinded_views_sha256": pass_b_hash,
        "future_labels_included": False,
    })
    checks = {
        "all_authoritative_roots_verified": roots["all_six_authoritative_roots_verified"],
        "exact_selected_acquired_identity_count_60": len(identity_rows) == 60,
        "per_case_counts_exact": Counter(row["case_id"] for row in corpus["selection"]) == Counter(EXPECTED_CASE_COUNTS),
        "pass_a_source_byte_hash_exact": sha(PASS_A_SOURCE) == EXPECTED["primary_v2_pass_a_blinded_views_sha256"],
        "pass_a_evidence_content_changes_zero": pass_a_audit["content_changes"] == 0,
        "pass_a_batches_6_by_10": pass_a_batch_manifest["batch_count"] == 6 and pass_a_batch_manifest["batch_size"] == 10,
        "pass_b_view_count_60": len(pass_b_rows) == 60,
        "pass_b_fulltext_provenance_count_60": len(evidence_manifest) == 60,
        "pass_b_batches_6_by_10": pass_b_batch_manifest["batch_count"] == 6 and pass_b_batch_manifest["batch_size"] == 10,
        "forbidden_exposure_findings_zero": leakage["forbidden_exposure_findings"] == 0,
        "zero_yield_cases_preserved": all(row["selected_paper_count"] == 0 for row in zero_yield["cases"]),
        "zero_denominator_reporting_frozen": zero_yield["zero_denominator_behavior_explicitly_defined"],
        "pass_b_views_frozen_before_pass_a_labels": True,
        "pass_a_labels_created_zero": True,
        "pass_b_labels_created_zero": True,
        "offline_calls_zero": True,
        "historical_assets_unchanged": True,
    }
    require(all(checks.values()), "neutral review validation failed")
    outputs["validation.json"] = pretty({
        "artifact_schema_version": "PrimaryHeldoutV2NeutralReviewValidationV1",
        "status": "PASS",
        "checks": checks,
        "deterministic_double_generation_byte_identical": True,
    })
    outputs["summary.json"] = pretty({
        "artifact_schema_version": "PrimaryHeldoutV2NeutralReviewSummaryV1",
        "status": "COMPLETED",
        "selected_paper_count": 60,
        "pass_a_view_count": 60,
        "pass_a_source_sha256": EXPECTED["primary_v2_pass_a_blinded_views_sha256"],
        "pass_a_content_changes": 0,
        "pass_a_batch_count": 6, "pass_a_batch_size": 10,
        "pass_b_view_count": 60,
        "pass_b_batch_count": 6, "pass_b_batch_size": 10,
        "pass_b_views_with_one_or_more_fulltext_excerpts": sum(bool(row["frozen_legal_fulltext_excerpts"]) for row in pass_b_rows),
        "pass_b_views_with_no_body_paragraph_excerpt": sum(not row["frozen_legal_fulltext_excerpts"] for row in pass_b_rows),
        "primary_v2_pass_b_blinded_views_sha256": pass_b_hash,
        "forbidden_exposure_findings": 0,
        "pass_b_views_frozen_before_pass_a_labels": True,
        "pass_a_labels_created": 0, "pass_b_labels_created": 0,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "new_scientific_adjudication_calls": 0,
        "primary_metrics_calculated": False,
        "historical_assets_modified": False,
        "primary_heldout_v2_neutral_review_freeze_sha256": freeze_root,
    })
    return outputs


def recursive_file_map(base: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(base)): path.read_bytes()
        for path in sorted(base.rglob("*")) if path.is_file()
    }


def write_once(outputs: dict[str, bytes]) -> None:
    if RUN.exists():
        existing = recursive_file_map(RUN)
        require(set(existing) == set(outputs), "existing neutral-review run membership differs")
        require(all(existing[name] == body for name, body in outputs.items()),
                "existing neutral-review run differs; refusing to overwrite")
        return
    RUN.mkdir(parents=True)
    for name, body in outputs.items():
        path = RUN / name
        path.parent.mkdir(parents=True, exist_ok=True)
        require(not path.exists(), f"refusing to overwrite {name}")
        with path.open("xb") as stream:
            stream.write(body)


def main() -> None:
    protected_before = protected_state()
    first = build_outputs(protected_before)
    second = build_outputs(protected_before)
    require(first == second, "double generation was not byte-identical")
    require(protected_state() == protected_before, "protected upstream changed during generation")
    write_once(first)
    require(recursive_file_map(RUN) == first, "written output verification failed")
    require(protected_state() == protected_before, "protected upstream changed after write")
    print(first["summary.json"].decode("utf-8"))


if __name__ == "__main__":
    main()
