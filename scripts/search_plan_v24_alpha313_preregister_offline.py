"""Offline alpha3.13 harmonized, arm-blinded review preregistration.

This verifies and packages frozen scientific evidence; it never retrieves,
calls a model, generates a scientific label, or changes a historical artifact.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import inspect
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import freeze_search_plan_v23_beta_2_primary_heldout_v2_neutral_review_offline as historical_builder
from tools import run_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval as historical_retrieval
from tools import run_search_plan_v23_beta_2_primary_heldout_v2_pass_a_adjudication as historical_a_runner
from tools import run_search_plan_v23_beta_2_primary_heldout_v2_pass_b_adjudication as historical_b_runner
from tools.freeze_bounded_lexical_realization_v2_full_retrieval_from_completed_run import verify_frozen_source


RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
SOURCE = ROOT / "runs/20260925_bounded_lexical_realization_v2_development_retrieval"
DELIVERY = ROOT / "runs/20260925_search_plan_v24_dev_bounded_lexical_realization_v2_full_retrieval"
HISTORICAL = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_neutral_review_freeze_offline"
HISTORICAL_RETRIEVAL = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval"
HISTORICAL_A = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_pass_a_adjudication"
HISTORICAL_B = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_pass_b_adjudication"
HISTORICAL_METRICS = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_metrics_unblinding"
PROTOCOL = ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline"
CASES = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_case_freeze_offline"
QUERIES = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_query_freeze_offline"
SOURCE_ROOT = "0a4c44bf4d50bed2185e3c55eaed2acccd03efdcd889ed1ec56d9ef9f380dd60"
SOURCE_CORPUS = "ef989f1a3ec942399dc3a8cbd681a5043261a97c2579140beb806e9f1bf0a097"
DELIVERY_ROOT = "57d0708f4e669ea3b83e19bfd9309c04716ea444d8768a6dc92a3d64ad6c5c51"
DELIVERY_CORPUS = "f753d03b502fd9046456c74ce1fee961c6f166b3596e3b8e1d2b8469ab1588ba"
HISTORICAL_ROOT = "0db9d84b1567d95d78272d6259d5e41f24751d5204b273801025cd595469c971"
CASE_IDS = tuple(f"heldout_v2_{number}" for number in range(101, 109))


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def jsonl(values: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in values)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write(name: str, body: bytes) -> None:
    path = RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == body:
            return
        raise RuntimeError(f"refusing different existing alpha3.13 output: {path}")
    path.write_bytes(body)


def verify_aggregate(run: Path, manifest_name: str, root_field: str, expected: str) -> int:
    manifest = load(run / manifest_name)
    pairs = manifest["aggregate_components"]
    if any(sha(run / name) != value for name, value in pairs) or digest(pairs) != expected or manifest[root_field] != expected:
        raise RuntimeError(f"frozen aggregate drift: {run.name}/{manifest_name}")
    return len(pairs)


def normalize_delivery(value: Any) -> Any:
    source_prefix = str(SOURCE.relative_to(ROOT)) + "/"
    delivery_prefix = str(DELIVERY.relative_to(ROOT)) + "/"
    if isinstance(value, str):
        return source_prefix + value[len(delivery_prefix):] if value.startswith(delivery_prefix) else value
    if isinstance(value, list):
        return [normalize_delivery(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_delivery(item) for key, item in value.items()}
    return value


def reconcile() -> tuple[dict[str, Any], list[list[str]]]:
    preflight = verify_frozen_source()
    delivery_validation = load(DELIVERY / "validation.json")
    pairs = delivery_validation["aggregate_components"]
    if any(sha(DELIVERY / name) != value for name, value in pairs) or digest(pairs) != DELIVERY_ROOT:
        raise RuntimeError("delivery root drift")
    if (DELIVERY / "search_plan_v24_dev_bounded_lexical_realization_v2_full_retrieval_sha256").read_text().strip() != DELIVERY_ROOT:
        raise RuntimeError("delivery root file drift")
    delivery_corpus = load(DELIVERY / "bounded_lexical_realization_v2_development_acquisition_corpus_manifest.json")
    cpairs = delivery_corpus["aggregate_components"]
    if any(sha(DELIVERY / name) != value for name, value in cpairs) or digest(cpairs) != DELIVERY_CORPUS:
        raise RuntimeError("delivery acquisition root drift")
    if (DELIVERY / "bounded_lexical_realization_v2_development_acquisition_corpus_sha256").read_text().strip() != DELIVERY_CORPUS:
        raise RuntimeError("delivery corpus root file drift")
    comparisons = []
    exact = [
        "query_execution_results.jsonl", "case_union_pmids.jsonl", "case_union_provenance.jsonl",
        "metadata_records.jsonl", "candidate_gate_results.jsonl", "p0_results.jsonl", "p1_results.jsonl",
        "p2_results.jsonl", "policy_a_results.jsonl", "candidate_tier_summary.json", "oa_eligibility_results.jsonl",
        "selection_manifest_aggregate_sha256", "tail_application_audit.json", "retrieval_denominator_summary.json",
    ]
    for name in exact:
        same = sha(SOURCE / name) == sha(DELIVERY / name)
        comparisons.append({"component": name, "comparison": "BYTE_IDENTICAL", "equivalent": same, "source_sha256": sha(SOURCE / name), "delivery_sha256": sha(DELIVERY / name)})
    path_rebased = [
        "query_execution_provenance.jsonl", "retrieval_request_manifest.jsonl", "metadata_fetch_manifest.jsonl",
        "fulltext_fetch_manifest.jsonl", "fulltext_acquisition_results.jsonl", "acquired_fulltext_manifest.json",
    ]
    for name in path_rebased:
        parsed_source = rows(SOURCE / name) if name.endswith(".jsonl") else load(SOURCE / name)
        parsed_delivery = rows(DELIVERY / name) if name.endswith(".jsonl") else load(DELIVERY / name)
        same = parsed_source == normalize_delivery(parsed_delivery)
        comparisons.append({"component": name, "comparison": "CANONICAL_AFTER_PATH_REBASE", "equivalent": same, "source_semantic_sha256": digest(parsed_source), "delivery_rebased_semantic_sha256": digest(normalize_delivery(parsed_delivery))})
    for case in CASE_IDS:
        name = f"case_selection_manifests/{case}.json"
        comparisons.append({"component": name, "comparison": "BYTE_IDENTICAL", "equivalent": sha(SOURCE / name) == sha(DELIVERY / name), "source_sha256": sha(SOURCE / name), "delivery_sha256": sha(DELIVERY / name)})
    raw_pairs: list[list[str]] = []
    for path in sorted((SOURCE / "retrieval_assets").rglob("*")):
        if path.is_file() and path.name != "network_events.json":
            relative = str(path.relative_to(SOURCE))
            same = sha(path) == sha(DELIVERY / relative)
            comparisons.append({"component": relative, "comparison": "RAW_NCBI_RESPONSE_BYTE_IDENTICAL", "equivalent": same, "source_sha256": sha(path), "delivery_sha256": sha(DELIVERY / relative)})
            raw_pairs.append([relative, sha(path)])
    source_events = load(SOURCE / "retrieval_assets/network_events.json")
    delivery_events = load(DELIVERY / "retrieval_assets/network_events.json")
    normalized = normalize_delivery(delivery_events)
    for event in normalized["events"]:
        event.pop("source_snapshot_ref", None)
    normalized.pop("source_execution_root_sha256", None)
    normalized.pop("new_network_requests", None)
    comparisons.append({"component": "retrieval_assets/network_events.json", "comparison": "EVENT_GRAPH_AFTER_REBASE_AND_REPLAY_FIELDS_REMOVED", "equivalent": source_events == normalized, "source_semantic_sha256": digest(source_events), "delivery_rebased_semantic_sha256": digest(normalized)})
    if not all(item["equivalent"] for item in comparisons):
        raise RuntimeError("CORPUS_PROVENANCE_RECONCILIATION_REQUIRED")
    if len(rows(SOURCE / "query_execution_results.jsonl")) != 55 or len(rows(SOURCE / "metadata_records.jsonl")) != 66 or len(rows(SOURCE / "fulltext_acquisition_results.jsonl")) != 11 or len(raw_pairs) != 68:
        raise RuntimeError("source scientific payload count mismatch")
    source_fulltexts = rows(SOURCE / "fulltext_acquisition_results.jsonl")
    if any(item["acquisition_status"] != "SUCCESS" or sha(ROOT / item["artifact_snapshot_ref"]) != item["raw_content_sha256"] for item in source_fulltexts):
        raise RuntimeError("source fulltext content mismatch")
    scientific_files = exact + path_rebased + [f"case_selection_manifests/{case}.json" for case in CASE_IDS]
    scientific_pairs = [[name, digest(rows(SOURCE / name) if name.endswith(".jsonl") else load(SOURCE / name)) if name != "selection_manifest_aggregate_sha256" else sha(SOURCE / name)] for name in scientific_files]
    scientific_pairs.extend(raw_pairs)
    scientific_pairs.sort(key=lambda pair: pair[0])
    audit = {"lexical_v2_scientific_payload_equivalent": True, "source_retrieval_root_sha256": SOURCE_ROOT, "source_acquisition_corpus_sha256": SOURCE_CORPUS, "delivery_root_sha256": DELIVERY_ROOT, "delivery_acquisition_corpus_sha256": DELIVERY_CORPUS, "component_count": len(comparisons), "raw_response_count": len(raw_pairs), "query_count": 55, "metadata_record_count": 66, "selection_manifest_count": 8, "acquired_fulltext_count": 11, "comparisons": comparisons, "source_pre_network_verification": preflight}
    return audit, scientific_pairs


def neutral_target(target: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in target.items() if key not in {"case_id", "scientific_proposition_target_id"}}


def historical_reconstruction() -> dict[str, Any]:
    neutral_components = verify_aggregate(HISTORICAL, "freeze_manifest.json", "primary_heldout_v2_neutral_review_freeze_sha256", HISTORICAL_ROOT)
    historical_roots = {}
    for name, directory, field in (
        ("original_pass_a", HISTORICAL_A, "primary_heldout_v2_pass_a_adjudication_sha256"),
        ("original_pass_b", HISTORICAL_B, "primary_heldout_v2_pass_b_adjudication_sha256"),
        ("original_metrics", HISTORICAL_METRICS, "primary_heldout_v2_metrics_unblinding_sha256"),
    ):
        manifest = load(directory / "implementation_manifest.json")
        historical_roots[name] = manifest[field]
        verify_aggregate(directory, "implementation_manifest.json", field, historical_roots[name])
    a_schema = load(HISTORICAL / "primary_v2_pass_a_review_schema.json")
    b_schema = load(HISTORICAL / "primary_v2_pass_b_review_schema.json")
    boundary = load(PROTOCOL / "adjudication_boundary_v2.json")
    metrics = load(PROTOCOL / "metrics_spec_v2.json")
    a_config = load(HISTORICAL_A / "primary_v2_adjudicator_config.json")
    b_config = load(HISTORICAL_B / "primary_v2_pass_b_adjudicator_config.json")
    a_batch = load(HISTORICAL / "primary_v2_pass_a_batch_manifest.json")
    b_batch = load(HISTORICAL / "primary_v2_pass_b_batch_manifest.json")
    selected = load(HISTORICAL / "selected60_identity_manifest.json")
    if selected["selected_paper_count"] != 60 or selected["successfully_acquired_paper_count"] != 60:
        raise RuntimeError("historical review denominator unresolved")
    if a_batch["batch_count"] != b_batch["batch_count"] or a_batch["batch_count"] != 6 or a_batch["batch_size"] != b_batch["batch_size"] or a_batch["batch_size"] != 10:
        raise RuntimeError("historical batch construction unresolved")
    if a_config["provider"] != b_config["provider"] or a_config["model"] != b_config["model"] or a_config["provider"] != "openai":
        raise RuntimeError("historical reviewer provenance mismatch")
    if not boundary["pass_a"]["preacquisition_only"] or boundary["pass_a"]["fulltext_visible"] or boundary["cross_pass_visibility"]["pass_a_may_see_pass_b"] or boundary["cross_pass_visibility"]["pass_b_may_see_pass_a"]:
        raise RuntimeError("historical pass boundary unresolved")
    inventory_paths = [
        HISTORICAL / "freeze_manifest.json", HISTORICAL / "selected60_identity_manifest.json",
        HISTORICAL / "pass_a_evaluator_instruction.md", HISTORICAL / "pass_b_evaluator_instruction.md",
        HISTORICAL / "primary_v2_pass_a_review_schema.json", HISTORICAL / "primary_v2_pass_b_review_schema.json",
        HISTORICAL / "primary_v2_pass_b_blinded_views.jsonl", HISTORICAL / "primary_v2_pass_a_sealed_identity_mapping.json",
        HISTORICAL / "primary_v2_pass_b_sealed_identity_mapping.json", HISTORICAL / "primary_v2_pass_b_fulltext_evidence_manifest.jsonl",
        HISTORICAL / "primary_v2_pass_a_batch_manifest.json", HISTORICAL / "primary_v2_pass_b_batch_manifest.json",
        HISTORICAL_RETRIEVAL / "primary_v2_pass_a_blinded_views.jsonl", HISTORICAL_RETRIEVAL / "primary_v2_acquisition_selection.jsonl",
        PROTOCOL / "adjudication_boundary_v2.json", PROTOCOL / "metrics_spec_v2.json",
        HISTORICAL_A / "primary_v2_adjudicator_config.json", HISTORICAL_B / "primary_v2_pass_b_adjudicator_config.json",
        HISTORICAL_A / "implementation_manifest.json", HISTORICAL_B / "implementation_manifest.json",
        HISTORICAL_METRICS / "implementation_manifest.json", HISTORICAL_METRICS / "primary_metrics.json",
        ROOT / "tools/freeze_search_plan_v23_beta_2_primary_heldout_v2_neutral_review_offline.py",
        ROOT / "tools/run_search_plan_v22_heldout_v1_network_retrieval.py",
        ROOT / "tools/run_search_plan_v23_beta_2_primary_heldout_v2_pass_a_adjudication.py",
        ROOT / "tools/run_search_plan_v23_beta_2_primary_heldout_v2_pass_b_adjudication.py",
        ROOT / "tools/calculate_search_plan_v23_beta_2_primary_heldout_v2_metrics_offline.py",
    ]
    for manifest in (a_batch, b_batch):
        inventory_paths.extend(HISTORICAL / row["path"] for row in manifest["batches"])
    inventory = [{"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size} for path in inventory_paths]
    matrix = [
        {"dimension": "review_denominator_target_paper_identity", "status": "EXACTLY_RECONSTRUCTED", "basis": "selected60_identity_manifest.json"},
        {"dimension": "pass_a_preacquisition_packet_fields", "status": "EXACTLY_RECONSTRUCTED", "basis": "frozen PASS A views and AdjudicationBoundaryV2"},
        {"dimension": "pass_b_title_abstract_fulltext_excerpt_fields", "status": "EXACTLY_RECONSTRUCTED", "basis": "frozen PASS B views and deterministic excerpt builder"},
        {"dimension": "scientific_target_representation", "status": "EXACTLY_RECONSTRUCTED", "basis": "ScientificPropositionTargetV1 in frozen views"},
        {"dimension": "pass_a_and_pass_b_evaluator_instructions", "status": "EXACTLY_RECONSTRUCTED", "basis": "byte-frozen evaluator instruction files"},
        {"dimension": "historical_prompt_wrapper", "status": "EXACTLY_RECONSTRUCTED", "basis": "frozen evaluator_prompt renderer source functions"},
        {"dimension": "implicit_provider_system_instruction", "status": "PARTIALLY_RECONSTRUCTED", "basis": "not separately preserved; original explicit prompt and model configuration are preserved; no invented system text"},
        {"dimension": "response_json_schemas_and_label_enums", "status": "EXACTLY_RECONSTRUCTED", "basis": "frozen Draft 2020-12 schemas"},
        {"dimension": "per_label_natural_language_gloss", "status": "PARTIALLY_RECONSTRUCTED", "basis": "historical prompt specifies component test; individual enum glosses were not separately frozen and are not invented"},
        {"dimension": "contaminant_taxonomy", "status": "EXACTLY_RECONSTRUCTED", "basis": "PASS B schema and MetricsSpecV2"},
        {"dimension": "pass_a_pass_b_semantics_and_blinding", "status": "EXACTLY_RECONSTRUCTED", "basis": "AdjudicationBoundaryV2 and original runner configurations"},
        {"dimension": "batch_count_size_ordering", "status": "EXACTLY_RECONSTRUCTED", "basis": "frozen six-by-ten batch manifests and neutral_order source"},
        {"dimension": "retry_parse_validation_failure_handling", "status": "EXACTLY_RECONSTRUCTED", "basis": "original adjudicator configs and runner parse validation"},
        {"dimension": "original_aggregation_and_metric_formulas", "status": "EXACTLY_RECONSTRUCTED", "basis": "MetricsSpecV2 and original metrics runner"},
    ]
    material_unresolved = sum(row["status"] == "UNRESOLVED" for row in matrix)
    if material_unresolved:
        raise RuntimeError("NEUTRAL_REVIEW_PROTOCOL_RECONSTRUCTION_INCOMPLETE")
    return {"inventory": inventory, "matrix": matrix, "material_unresolved_count": material_unresolved, "historical_roots": historical_roots, "neutral_component_count": neutral_components, "a_schema": a_schema, "b_schema": b_schema, "boundary": boundary, "metrics": metrics, "a_config": a_config, "b_config": b_config, "a_batch": a_batch, "b_batch": b_batch, "selected": selected}


def build_review_units(historical: dict[str, Any]) -> dict[str, Any]:
    old_a_views = {}
    for batch in historical["a_batch"]["batches"]:
        for view in rows(HISTORICAL / batch["path"]):
            old_a_views[view["review_id"]] = view
    old_b_views = {view["review_id"]: view for view in rows(HISTORICAL / "primary_v2_pass_b_blinded_views.jsonl")}
    old_selections = {row["candidate_id"]: row for row in rows(HISTORICAL_RETRIEVAL / "primary_v2_acquisition_selection.jsonl")}
    old_records = historical["selected"]["records"]
    if not (len(old_a_views) == len(old_b_views) == len(old_records) == 60):
        raise RuntimeError("historical view count mismatch")
    targets = {row["case_id"]: row for row in rows(CASES / "primary_heldout_v2_scientific_targets.jsonl")}
    bindings = {row["case_id"]: row for row in rows(QUERIES / "primary_heldout_v2_query_bindings.jsonl")}
    frozen_queries = rows(QUERIES / "primary_heldout_v2_frozen_queries.jsonl")
    query_by_case = {case: [row for row in frozen_queries if row["case_id"] == case] for case in CASE_IDS}
    surfaces = {case: (lambda contract: contract["subject_surfaces"] + contract["endpoint_surfaces"])(historical_retrieval.gate_target(targets[case], bindings[case], query_by_case[case])) for case in CASE_IDS}
    new_metadata = {row["candidate_id"]: row for row in rows(SOURCE / "metadata_records.jsonl")}
    new_fulltexts = rows(SOURCE / "fulltext_acquisition_results.jsonl")
    new_selections = {row["candidate_id"]: row for case in CASE_IDS for row in load(SOURCE / "case_selection_manifests" / f"{case}.json")["ordered_selections"]}
    if len(new_fulltexts) != 11 or len(new_selections) != 11 or any(row["acquisition_status"] != "SUCCESS" for row in new_fulltexts):
        raise RuntimeError("Lexical V2 acquired denominator mismatch")

    candidates = []
    for record in old_records:
        a = old_a_views[record["pass_a_neutral_review_id"]]
        b = old_b_views[record["pass_b_neutral_review_id"]]
        selected = old_selections[record["candidate_id"]]
        if a["ScientificPropositionTargetV1"] != b["ScientificPropositionTargetV1"] or a["title"] != b["title"] or a["abstract"] != b["abstract"]:
            raise RuntimeError("historical Pass A/B evidence mismatch")
        if b["fulltext_excerpt_provenance"]["raw_fulltext_sha256"] != record["fulltext_raw_sha256"] or selected["publication_metadata"]["pmid"] != record["pmid"]:
            raise RuntimeError("historical identity/fulltext mismatch")
        candidates.append({"arm": "ARM_HISTORICAL_V23", "case_id": record["case_id"], "pmid": record["pmid"], "pmcid": record["pmcid"], "raw_fulltext_sha256": record["fulltext_raw_sha256"], "parsed_fulltext_sha256": record["fulltext_parsed_sha256"], "target": a["ScientificPropositionTargetV1"], "title": a["title"], "abstract": a["abstract"], "publication_metadata": a["publication_metadata"], "preacquisition_evidence": a["frozen_preacquisition_retrieval_evidence"], "excerpts": b["frozen_legal_fulltext_excerpts"], "tier": selected["final_preacquisition_tier"], "candidate_id": record["candidate_id"], "selection_id": record["selection_id"], "source_pass_a_id": a["review_id"], "source_pass_b_id": b["review_id"], "source_kind": b["fulltext_excerpt_provenance"]["source_kind"], "evidence_source_ref": str((HISTORICAL / "primary_v2_pass_b_blinded_views.jsonl").relative_to(ROOT))})
    for fulltext in new_fulltexts:
        metadata = new_metadata[fulltext["candidate_id"]]
        selection = new_selections[fulltext["candidate_id"]]
        case = fulltext["case_id"]
        if metadata["pmid"] != fulltext["pmid"] or metadata["pmcid"] != fulltext["pmcid"] or selection["legal_fulltext_identifier"] != fulltext["pmcid"]:
            raise RuntimeError("Lexical V2 selected identity mismatch")
        fulltext_path = ROOT / fulltext["artifact_snapshot_ref"]
        if sha(fulltext_path) != fulltext["raw_content_sha256"]:
            raise RuntimeError("Lexical V2 fulltext bytes mismatch")
        extracted = historical_builder.deterministic_excerpts(fulltext_path, surfaces[case])
        excerpts = [{"paragraph_anchor": f"body-paragraph[{item['paragraph_index']}]", "text": item["text"], "text_sha256": hashlib.sha256(item["text"].encode()).hexdigest()} for item in extracted]
        candidates.append({"arm": "ARM_LEXICAL_V2", "case_id": case, "pmid": metadata["pmid"], "pmcid": metadata["pmcid"], "raw_fulltext_sha256": fulltext["raw_content_sha256"], "parsed_fulltext_sha256": fulltext["parsed_content_sha256"], "target": targets[case], "title": metadata["title"], "abstract": metadata["abstract"], "publication_metadata": {"pmid": metadata["pmid"], "preacquisition_known_pmcid_identifier": metadata["pmcid"], "doi": metadata["doi"], "journal": metadata["journal"], "publication_date": metadata["publication_date"], "publication_type": metadata["publication_type"]}, "preacquisition_evidence": {"metadata_resolution_status": metadata["metadata_resolution_status"], "abstract_availability": "PRESENT" if metadata["abstract"] else "ABSENT", "publication_type_authority": "NCBI_PUBMED_INDEXED_METADATA", "identifier_resolution_status": "PMID_AND_PMCID_RESOLVED" if metadata["pmcid"] else "PMID_RESOLVED"}, "excerpts": excerpts, "tier": selection["final_preacquisition_tier"], "candidate_id": fulltext["candidate_id"], "selection_id": fulltext["selection_id"], "source_pass_a_id": None, "source_pass_b_id": None, "source_kind": "NCBI_PMC_OA_XML", "evidence_source_ref": fulltext["artifact_snapshot_ref"]})

    by_target_pmid: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        item["neutral_target"] = neutral_target(item["target"])
        item["neutral_target_sha256"] = digest(item["neutral_target"])
        by_target_pmid[(item["neutral_target_sha256"], item["pmid"])].append(item)
    duplicate_audit = []
    evidence_mismatches = []
    for key, group in sorted(by_target_pmid.items()):
        if len(group) < 2:
            continue
        evidence_signatures = {digest({"pmcid": item["pmcid"], "raw_fulltext_sha256": item["raw_fulltext_sha256"], "title": item["title"], "abstract": item["abstract"], "excerpts": [(e["paragraph_anchor"], e["text_sha256"]) for e in item["excerpts"]]}) for item in group}
        same_evidence = len(evidence_signatures) == 1
        event = {"neutral_target_sha256": key[0], "pmid": key[1], "arms": sorted(item["arm"] for item in group), "evidence_packet_equivalent": same_evidence, "policy": "MERGE_ONE_UNIT_TWO_HIDDEN_EDGES" if same_evidence else "DUPLICATE_EVIDENCE_MISMATCH_KEEP_SEPARATE"}
        duplicate_audit.append(event)
        if not same_evidence:
            evidence_mismatches.append(event)
    # A mismatch can remain two review units only if the common protocol permits both
    # evidence packets. It is not silently merged and is surfaced for review.
    units: dict[str, dict[str, Any]] = {}
    packets: dict[tuple[str, str], dict[str, Any]] = {}
    hidden = []
    for item in candidates:
        identity = {"target_sha256": item["neutral_target_sha256"], "pmid": item["pmid"], "evidence_source": item["source_kind"], "raw_fulltext_sha256": item["raw_fulltext_sha256"]}
        identifier = "NRV1_" + digest(identity)[:24]
        model_metadata = {key: item["publication_metadata"][key] for key in ("journal", "publication_date", "publication_type")}
        # Identifiers were available in the original historical packet but are
        # non-scientific cues; the shared harmonized packet uses the preserved
        # identifier-resolution state instead, identically for both arms.
        pass_a = {"review_unit_id": identifier, "ScientificPropositionTargetV1": item["neutral_target"], "title": item["title"], "abstract": item["abstract"], "publication_metadata": model_metadata, "frozen_preacquisition_retrieval_evidence": item["preacquisition_evidence"]}
        pass_b = {"review_unit_id": identifier, "ScientificPropositionTargetV1": item["neutral_target"], "title": item["title"], "abstract": item["abstract"], "frozen_legal_fulltext_excerpts": [{"paragraph_anchor": e["paragraph_anchor"], "text": e["text"]} for e in item["excerpts"]], "fulltext_source_kind": item["source_kind"]}
        candidate_packets = {"PASS_A": pass_a, "PASS_B": pass_b}
        if identifier in units:
            if any(packets[(identifier, p)] != candidate_packets[p] for p in ("PASS_A", "PASS_B")):
                raise RuntimeError("duplicate unit evidence mismatch under same ID")
        else:
            units[identifier] = {"artifact_schema_version": "NeutralReviewUnitV1", "review_unit_id": identifier, "neutral_target_sha256": item["neutral_target_sha256"], "pass_a_evidence_sha256": digest(pass_a), "pass_b_evidence_sha256": digest(pass_b), "scientific_label_present": False}
            for p, packet in candidate_packets.items():
                packets[(identifier, p)] = packet
        hidden.append({"review_unit_id": identifier, "arm_membership": item["arm"], "case_id": item["case_id"], "pmid": item["pmid"], "pmcid": item["pmcid"], "candidate_id": item["candidate_id"], "selection_id": item["selection_id"], "frozen_preacquisition_tier": item["tier"], "raw_fulltext_sha256": item["raw_fulltext_sha256"], "parsed_fulltext_sha256": item["parsed_fulltext_sha256"], "evidence_source_ref": item["evidence_source_ref"], "historical_pass_a_review_id": item["source_pass_a_id"], "historical_pass_b_review_id": item["source_pass_b_id"], "fulltext_excerpt_count": len(item["excerpts"])})
    if len(candidates) != 71 or Counter(item["arm_membership"] for item in hidden) != {"ARM_HISTORICAL_V23": 60, "ARM_LEXICAL_V2": 11}:
        raise RuntimeError("harmonized arm denominator mismatch")
    if len(units) != len({row["review_unit_id"] for row in hidden}):
        raise RuntimeError("review-unit identity collision")
    order_seed = digest({"namespace": "ALPHA313_MIXED_ARM_BLINDED_ORDER_V1", "source_root": SOURCE_ROOT, "historical_root": HISTORICAL_ROOT})
    ordered_ids = sorted(units, key=lambda identifier: hashlib.sha256((order_seed + ":" + identifier).encode()).hexdigest())
    ordered_units = [units[identifier] for identifier in ordered_ids]
    ordered_packets = [{"review_unit_id": identifier, "pass": pass_name, "packet": packets[(identifier, pass_name)]} for identifier in ordered_ids for pass_name in ("PASS_A", "PASS_B")]
    hidden.sort(key=lambda item: (item["review_unit_id"], item["arm_membership"]))
    return {"units": ordered_units, "packets": ordered_packets, "hidden": hidden, "ordered_ids": ordered_ids, "order_seed": order_seed, "duplicates": duplicate_audit, "evidence_mismatches": evidence_mismatches, "source_candidate_count": len(candidates), "historical_empty_excerpt_count": sum(not item["excerpts"] and item["arm"] == "ARM_HISTORICAL_V23" for item in candidates), "lexical_empty_excerpt_count": sum(not item["excerpts"] and item["arm"] == "ARM_LEXICAL_V2" for item in candidates)}


def neutral_output_schema(historical_schema: dict[str, Any], pass_name: str) -> dict[str, Any]:
    record = json.loads(json.dumps(historical_schema))
    record["properties"].pop("review_id")
    record["properties"]["review_unit_id"] = {"type": "string", "pattern": "^NRV1_[0-9a-f]{24}$"}
    record["required"] = ["review_unit_id" if field == "review_id" else field for field in record["required"]]
    record["title"] = f"HarmonizedNeutralReview{pass_name}RecordV1"
    record["description"] = "Historical scientific taxonomy retained; only neutral response identity replaces the historical review ID."
    record.pop("taxonomy_source_sha256", None)
    return {"type": "object", "additionalProperties": False, "required": ["records"], "properties": {"records": {"type": "array", "minItems": 1, "maxItems": 10, "items": record}}}


def build_protocol(historical: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    a_instruction = (HISTORICAL / "pass_a_evaluator_instruction.md").read_text(encoding="utf-8").split("\n", 1)[1].strip()
    b_instruction = (HISTORICAL / "pass_b_evaluator_instruction.md").read_text(encoding="utf-8").split("\n", 1)[1].strip()
    common = "You are a fresh isolated neutral-review evaluator for exactly one frozen batch. Use only the supplied instruction, response schema, and packet payload. Do not call tools or access the filesystem, network, previous batches, hidden mappings, or outside knowledge. Judge every record independently. Return one JSON object with a records array, in batch order, and no other text."
    prompt = {"PASS_A": common + "\n\n" + a_instruction + "\n\n--- RESPONSE SCHEMA ---\n{output_schema_json}\n--- PASS A PACKETS ---\n{batch_json}", "PASS_B": common + "\n\n" + b_instruction + "\n\n--- RESPONSE SCHEMA ---\n{output_schema_json}\n--- PASS B PACKETS ---\n{batch_json}"}
    original_deepseek_config = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_reasoning_config_offline/deepseek_query_planner_config_v1_1.json"
    prior = load(original_deepseek_config)
    if prior["provider"] != "deepseek" or prior["model"] != "deepseek-v4-pro" or prior["thinking_mode"] != "enabled" or prior["reasoning_effort"] != "high":
        raise RuntimeError("current DeepSeek configuration is not compatible")
    config = {"artifact_schema_version": "HarmonizedNeutralReviewDeepSeekConfigV1", "provider": "deepseek", "api_surface": "CHAT_COMPLETIONS_API", "model": "deepseek-v4-pro", "thinking_mode": "enabled", "reasoning_effort": "high", "temperature": "OMITTED_IN_THINKING_MODE", "top_p": "OMITTED_IN_THINKING_MODE", "response_format": {"type": "json_object"}, "service_tier": "PROVIDER_DEFAULT_NOT_OVERRIDDEN", "reviewer_type": "model_retrieval_adjudicator", "fresh_isolated_session_per_batch": True, "model_attempts_per_batch": 1, "automatic_retry": False, "scientific_repair": False, "provider_fallback": False, "llm_calls_authorized_in_alpha3_13": 0, "prior_scientific_deepseek_config_ref": str(original_deepseek_config.relative_to(ROOT)), "prior_config_sha256": sha(original_deepseek_config), "provider_compatibility_not_tested_by_this_offline_preregistration": True}
    output_schema = {"PASS_A": neutral_output_schema(historical["a_schema"], "PASS_A"), "PASS_B": neutral_output_schema(historical["b_schema"], "PASS_B")}
    request_schema = {"artifact_schema_version": "HarmonizedNeutralReviewRequestV1", "api_surface": "CHAT_COMPLETIONS_API", "model": "deepseek-v4-pro", "thinking": {"type": "enabled"}, "reasoning_effort": "high", "response_format": {"type": "json_object"}, "temperature_parameter": "OMIT", "top_p_parameter": "OMIT", "messages": [{"role": "user", "content": "render exactly one pass-specific frozen prompt with one contiguous batch"}], "must_not_include": ["arm map", "historical labels", "retrieval provenance", "tier", "selection rank", "metrics"], "offline_static_schema_preflight_required": True}
    chunks = [review["ordered_ids"][index:index + 10] for index in range(0, len(review["ordered_ids"]), 10)]
    if len(chunks) != 8 or [len(chunk) for chunk in chunks] != [10] * 7 + [1]:
        raise RuntimeError("batching plan mismatch")
    batching = {"mixed_order_sha256": digest(review["ordered_ids"]), "unit_count": len(review["ordered_ids"]), "batch_size": 10, "batches_per_pass": 8, "passes": ["PASS_A", "PASS_B"], "planned_model_calls": 16, "authorized_model_calls": 0, "single_fresh_isolated_call_per_batch": True, "pass_a_cannot_see_pass_b": True, "pass_b_cannot_see_pass_a_or_pass_a_outputs": True, "batch_plan": [{"batch_index": index, "unit_ids": chunk, "unit_count": len(chunk), "pass_a_packet_sha256": digest([next(p["packet"] for p in review["packets"] if p["review_unit_id"] == unit and p["pass"] == "PASS_A") for unit in chunk]), "pass_b_packet_sha256": digest([next(p["packet"] for p in review["packets"] if p["review_unit_id"] == unit and p["pass"] == "PASS_B") for unit in chunk])} for index, chunk in enumerate(chunks, 1)]}
    parse = {"response_transport": "JSON_OBJECT", "expected_outer_key": "records", "record_schema": "pass-specific frozen schema", "validation": ["exact batch response count", "exact review_unit_id set and batch order", "Draft 2020-12 schema validation", "no extra fields", "allowed enum values only", "reviewer_type=model_retrieval_adjudicator"], "invalid_schema_behavior": "FAIL_CLOSED_STOP_PASS", "automatic_repair": False, "outcome_informed_rerun": False, "blinded_labels_frozen_before_hidden_arm_map_access": True}
    failure = {"provider_transport_failure": "PRESERVE_RAW_FAILURE_AND_STOP_PASS", "provider_schema_failure": "PRESERVE_RAW_RESPONSE_AND_STOP_PASS", "scientific_postvalidation_failure": "PRESERVE_RAW_RESPONSE_AND_STOP_PASS", "transport_retry_policy": "NO_AUTOMATIC_RETRY_IN_FROZEN_PLAN", "scientific_re_adjudication": "PROHIBITED", "model_provider_switch": "PROHIBITED", "identity_join_before_blinded_freeze": "PROHIBITED", "metrics_before_both_passes_frozen": "PROHIBITED"}
    return {"prompt": prompt, "config": config, "output_schema": output_schema, "request_schema": request_schema, "batching": batching, "parse": parse, "failure": failure}


def metric_plan(historical: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    by_arm_case = {arm: {case: 0 for case in CASE_IDS} for arm in ("ARM_HISTORICAL_V23", "ARM_LEXICAL_V2")}
    for edge in review["hidden"]:
        by_arm_case[edge["arm_membership"]][edge["case_id"]] += 1
    return {"artifact_schema_version": "HarmonizedNeutralReviewMetricsPlanV1", "historical_metrics_spec_sha256": sha(PROTOCOL / "metrics_spec_v2.json"), "original_metrics_spec_unmodified": historical["metrics"], "historical_identity_field_adaptation": {"original": "packet_id", "harmonized": "review_unit_id", "semantics": "same unique target-paper review unit; duplicate labels map to both hidden arm edges"}, "arm_specific_aggregation": True, "arms": [{"arm": arm, "review_denominator": sum(counts.values()), "per_case_review_unit_counts": counts, "case_coverage": sum(bool(n) for n in counts.values()), "missing_case_count": sum(not n for n in counts.values()), "zero_acquisition_case_status": {case: "NO_REVIEW_UNITS_FROM_RETRIEVAL" for case, n in counts.items() if not n}, "micro_aggregation": "sum frozen numerator and denominator counts over all reviewed units in this arm", "macro_by_case_aggregation": "arithmetic mean of defined per-case fractions only; report missing-case count and never treat zero acquisition as scientific negative"} for arm, counts in by_arm_case.items()], "tier_metrics_require_hidden_tier_only_after_blinded_label_freeze": True, "original_v23_metrics_preserved_separately": True, "historical_provider_variation_not_historical_data_correction": True, "no_metrics_computed_in_alpha3_13": True}


def main() -> None:
    if (RUN / "search_plan_v24_dev_alpha3_13_sha256").exists():
        raise RuntimeError(f"refusing already frozen alpha3.13 run: {RUN}")
    reconciliation, scientific_pairs = reconcile()
    historical = historical_reconstruction()
    review = build_review_units(historical)
    protocol = build_protocol(historical, review)
    metrics = metric_plan(historical, review)
    if review["evidence_mismatches"]:
        raise RuntimeError("HARMONIZED_REVIEW_EVIDENCE_INCOMPARABLE")
    historical_hashes_before = {row["path"]: row["sha256"] for row in historical["inventory"]}
    public_packet_text = json.dumps(review["packets"], ensure_ascii=False)
    forbidden = ["heldout_v2_", "v2.3", "v2.4", "alpha3", "CORE_RELATION", "TIER_A", "TIER_B", "query_", "selection_", "historical", "Policy A"]
    leaks = [token for token in forbidden if token in public_packet_text]
    if leaks or any(label in public_packet_text for label in ("DIRECTLY_RELEVANT", "NOT_JUSTIFIED", "WRONG_ENDPOINT")):
        raise RuntimeError(f"reviewer-visible leakage: {leaks}")
    if len(review["units"]) != 71 or len(review["packets"]) != 142 or len(review["hidden"]) != 71:
        raise RuntimeError("review corpus completeness mismatch")

    RUN.mkdir(parents=True, exist_ok=True)
    source_components = load(SOURCE / "bounded_lexical_realization_v2_development_retrieval_validation.json")["aggregate_components"]
    delivery_components = load(DELIVERY / "validation.json")["aggregate_components"]
    write("upstream_root_verification.json", pretty({"alpha3_12_root_sha256": reconciliation["source_pre_network_verification"]["alpha3_12_root_sha256"], "lexical_v2_source_retrieval_sha256": SOURCE_ROOT, "lexical_v2_source_acquisition_sha256": SOURCE_CORPUS, "lexical_v2_delivery_sha256": DELIVERY_ROOT, "lexical_v2_delivery_acquisition_sha256": DELIVERY_CORPUS, "historical_v23_neutral_review_sha256": HISTORICAL_ROOT, "historical_original_roots": historical["historical_roots"], "source_component_count": len(source_components), "delivery_component_count": len(delivery_components), "verified_before_review_corpus_construction": True}))
    write("lexical_v2_source_delivery_equivalence_audit.json", pretty({key: value for key, value in reconciliation.items() if key not in {"comparisons", "source_pre_network_verification"}}))
    write("lexical_v2_scientific_payload_component_comparison.json", pretty({"component_comparisons": reconciliation["comparisons"], "scientific_payload_equivalent": True, "canonical_component_pairs": scientific_pairs}))
    write("lexical_v2_aggregate_root_difference_explanation.json", pretty({"source_retrieval_root_sha256": SOURCE_ROOT, "source_acquisition_root_sha256": SOURCE_CORPUS, "delivery_root_sha256": DELIVERY_ROOT, "delivery_acquisition_root_sha256": DELIVERY_CORPUS, "different_aggregate_roots_expected": True, "reasons": ["delivery has physically copied NCBI snapshots under a new run path", "delivery provenance paths were rebased while scientific records and response bytes were preserved", "delivery adds offline comparison and compliance reporting components", "aggregate roots bind packaging paths and file membership, not only scientific payload"], "scientific_payload_equivalent_after_explicit_component_comparison": True, "historical_aggregate_roots_replaced": False}))
    canonical_root = digest(scientific_pairs)
    write("canonical_lexical_v2_scientific_corpus_binding.json", pretty({"artifact_schema_version": "CanonicalBoundedLexicalRealizationV2ScientificCorpusBindingV1", "canonical_bounded_lexical_realization_v2_scientific_corpus_sha256": canonical_root, "aggregate_algorithm": "sha256(canonical JSON sorted [logical_component,scientific_sha256] pairs)", "component_count": len(scientific_pairs), "source_and_delivery_equivalence_verified": True, "source_retrieval_root_sha256": SOURCE_ROOT, "delivery_root_sha256": DELIVERY_ROOT, "historical_roots_unchanged": True}))
    write("canonical_bounded_lexical_realization_v2_scientific_corpus_sha256", (canonical_root + "\n").encode())
    write("search_tuning_pause_declaration.json", pretty({"SEARCH_PLAN_QUERY_TUNING_PAUSED_FOR_REVIEW": True, "query_modifications": 0, "lexical_changes": 0, "retrieval_calls": 0, "next_scientific_question": "quality of selected acquired papers under harmonized review"}))
    write("historical_v23_review_artifact_inventory.json", pretty({"artifact_count": len(historical["inventory"]), "artifacts": historical["inventory"], "historical_original_provider": "openai", "historical_original_model": "gpt-5.6-sol", "historical_original_metrics_root_sha256": historical["historical_roots"]["original_metrics"]}))
    write("historical_review_reconstruction_matrix.json", pretty({"dimensions": historical["matrix"], "material_unresolved_count": historical["material_unresolved_count"], "partial_dimensions_not_invented": True}))
    write("historical_review_label_schema.json", pretty(historical["b_schema"]))
    write("historical_review_acquisition_justification_schema.json", pretty(historical["a_schema"]))
    write("historical_review_contaminant_schema.json", pretty({"contaminant_class_enum": historical["b_schema"]["properties"]["contaminant_class"]["enum"], "metric_ids": historical["metrics"]["contaminant_metric_ids"], "source_pass_b_schema_sha256": sha(HISTORICAL / "primary_v2_pass_b_review_schema.json"), "source_metrics_spec_sha256": sha(PROTOCOL / "metrics_spec_v2.json"), "definitions_not_invented": True}))
    write("historical_pass_a_b_semantics.json", pretty({"pass_a": historical["boundary"]["pass_a"], "pass_b": historical["boundary"]["pass_b"], "cross_pass_visibility": historical["boundary"]["cross_pass_visibility"], "two_independent_axes_not_two_reviewer_votes": True, "original_majority_vote": False, "original_scientific_repair": False, "original_pass_a_provider_model": {"provider": historical["a_config"]["provider"], "model": historical["a_config"]["model"]}, "original_pass_b_provider_model": {"provider": historical["b_config"]["provider"], "model": historical["b_config"]["model"]}}))
    write("historical_evidence_packet_contract.json", pretty({"pass_a_allowed_fields": historical["boundary"]["pass_a"]["allowed_fields"], "pass_a_forbidden_fields": historical["boundary"]["pass_a"]["forbidden_fields"], "pass_b_allowed_fields": historical["boundary"]["pass_b"]["allowed_fields"], "pass_b_forbidden_fields": historical["boundary"]["pass_b"]["forbidden_fields"], "pass_b_fulltext_construction_mechanism": "heldout_v1_deterministic_excerpts_v1", "excerpt_builder_source_sha256": sha(ROOT / "tools/run_search_plan_v22_heldout_v1_network_retrieval.py"), "historical_pass_a_view_schema_keys": sorted(next(iter(rows(HISTORICAL / historical["a_batch"]["batches"][0]["path"]))).keys()), "historical_pass_b_view_schema_keys": sorted(next(iter(rows(HISTORICAL / "primary_v2_pass_b_blinded_views.jsonl"))).keys()), "harmonized_blinding_redactions": ["case ID and architecture-encoded target ID", "PMID, PMCID and DOI literal identifiers from model-visible PASS A metadata", "fulltext excerpt construction/version and matched-surface provenance from model-visible PASS B"], "scientific_target_and_evidence_text_unchanged": True}))
    write("historical_v23_review_protocol_reconstruction.json", pretty({"review_denominator": 60, "target_representation": "ScientificPropositionTargetV1", "paper_representation": "frozen PubMed title and abstract; PASS A publication metadata and preacquisition statuses; PASS B deterministic PMC OA body excerpts", "original_pass_a_instruction_sha256": sha(HISTORICAL / "pass_a_evaluator_instruction.md"), "original_pass_b_instruction_sha256": sha(HISTORICAL / "pass_b_evaluator_instruction.md"), "original_pass_a_prompt_renderer_sha256": hashlib.sha256(inspect.getsource(historical_a_runner.evaluator_prompt).encode()).hexdigest(), "original_pass_b_prompt_renderer_sha256": hashlib.sha256(inspect.getsource(historical_b_runner.evaluator_prompt).encode()).hexdigest(), "original_pass_a_schema_sha256": sha(HISTORICAL / "primary_v2_pass_a_review_schema.json"), "original_pass_b_schema_sha256": sha(HISTORICAL / "primary_v2_pass_b_review_schema.json"), "original_boundary_sha256": sha(PROTOCOL / "adjudication_boundary_v2.json"), "original_metrics_spec_sha256": sha(PROTOCOL / "metrics_spec_v2.json"), "original_provider": "openai", "original_model": "gpt-5.6-sol", "original_reasoning_effort": "high", "original_service_tier": "default", "batch_count_per_pass": 6, "batch_size": 10, "ordering": "namespace-specific SHA-256 ordering over frozen identity; contiguous groups of ten", "automatic_retry": False, "schema_validation": "Draft 2020-12 plus exact record count and review-ID membership", "invalid_schema_behavior": "FAIL_CLOSED_STOP_RUN", "original_aggregation_source": "MetricsSpecV2 frozen numerator and denominator predicates", "material_unresolved_count": 0, "missing_per_label_gloss_not_invented": True, "implicit_provider_system_text_not_claimed_as_preserved": True}))
    write("harmonized_review_arm_manifest.json", pretty({"arms": [{"arm": row["arm"], "frozen_acquired_membership_count": row["review_denominator"], "per_case_counts": row["per_case_review_unit_counts"], "missing_case_count": row["missing_case_count"]} for row in metrics["arms"]], "rebalanced": False, "downsampled": False, "oversampled": False, "cross_arm_duplicates_reviewed_once": True, "hidden_membership_map_ref": "neutral_review_hidden_arm_map.jsonl", "historical_original_labels_not_used": True}))
    write("cross_arm_duplicate_audit.json", pretty({"cross_arm_same_target_pmid_groups": review["duplicates"], "cross_arm_duplicate_unit_count": sum(event["evidence_packet_equivalent"] for event in review["duplicates"]), "duplicate_evidence_mismatch_count": len(review["evidence_mismatches"]), "mismatch_policy": "keep separate unless exact common packet can be defined; never silently merge", "actual_duplicate_count": 0}))
    write("neutral_review_units.jsonl", jsonl(review["units"]))
    write("neutral_review_evidence_packets.jsonl", jsonl(review["packets"]))
    write("neutral_review_hidden_arm_map.jsonl", jsonl(review["hidden"]))
    write("neutral_review_order.json", pretty({"ordering_namespace_sha256": review["order_seed"], "derivation": "sort sha256(ordering_namespace_sha256 + ':' + opaque_review_unit_id)", "ordered_review_unit_ids": review["ordered_ids"], "mixed_order_sha256": digest(review["ordered_ids"]), "derived_without_arm_case_difficulty_tier_or_historical_labels": True, "frozen_before_provider_call": True}))
    write("neutral_review_prompt_template.txt", pretty(protocol["prompt"]))
    write("neutral_review_provider_config.json", pretty(protocol["config"]))
    write("neutral_review_request_schema.json", pretty(protocol["request_schema"]))
    write("neutral_review_output_schema.json", pretty(protocol["output_schema"]))
    write("neutral_review_batching_plan.json", pretty(protocol["batching"]))
    write("neutral_review_parse_validation_policy.json", pretty(protocol["parse"]))
    write("neutral_review_failure_policy.json", pretty(protocol["failure"]))
    write("neutral_review_metrics_plan.json", pretty(metrics))
    write("reviewer_blinding_audit.json", pretty({"reviewer_arm_blinded": True, "reviewer_visible_packet_count": len(review["packets"]), "reviewer_visible_unit_count": len(review["units"]), "forbidden_token_scan": {token: token in public_packet_text for token in forbidden}, "query_provenance_exposed_to_reviewer": False, "tier_exposed_to_reviewer": False, "selection_rank_exposed_to_reviewer": False, "historical_labels_exposed_to_reviewer": False, "case_id_exposed_to_reviewer": False, "arm_membership_exposed_to_reviewer": False, "prefilled_scientific_labels": 0}))
    write("arm_membership_firewall_audit.json", pretty({"hidden_mapping_file": "neutral_review_hidden_arm_map.jsonl", "model_request_allowlist": ["neutral_review_prompt_template.txt", "neutral_review_output_schema.json", "neutral_review_evidence_packets.jsonl", "neutral_review_batching_plan.json"], "hidden_mapping_in_model_request_allowlist": False, "metrics_access_before_blinded_label_freeze": False, "identity_join_only_after_both_passes_frozen": True, "future_runner_must_enforce_allowlist": True}))
    write("evidence_equivalence_audit.json", pretty({"same_historical_deterministic_excerpt_builder_used_in_both_arms": True, "historical_arm_empty_body_excerpt_count": review["historical_empty_excerpt_count"], "lexical_arm_empty_body_excerpt_count": review["lexical_empty_excerpt_count"], "historical_arm_memberships": 60, "lexical_arm_memberships": 11, "empty_excerpts_preserved_without_reextraction_or_extra_retrieval": True, "same_target_and_packet_field_contract_both_arms": True, "same_blinding_redactions_both_arms": True, "cross_arm_duplicate_evidence_mismatch_count": len(review["evidence_mismatches"]), "evidence_packet_method_comparable": True, "evidence_availability_imbalance_report_required": True}))
    write("original_historical_review_preservation_audit.json", pretty({"original_v23_provider": "openai", "original_v23_model": "gpt-5.6-sol", "original_pass_a_root_sha256": historical["historical_roots"]["original_pass_a"], "original_pass_b_root_sha256": historical["historical_roots"]["original_pass_b"], "original_metrics_root_sha256": historical["historical_roots"]["original_metrics"], "original_labels_copied_into_new_review_packets": False, "original_metrics_overwritten": False, "future_comparison_names": ["ORIGINAL_V23_REVIEW", "HARMONIZED_DEEPSEEK_V23_REVIEW"], "historical_assets_modified": False}))
    write("candidate_content_search_leakage_audit.json", pretty({"candidate_content_read_for_review_packet_construction_only": True, "candidate_content_reads_for_query_design": 0, "query_modifications": 0, "lexical_changes": 0, "retrieval_calls": 0, "search_plan_query_tuning_paused_for_review": True}))
    write("scientific_state_safety_audit.json", pretty({"scientific_relevance_adjudications": 0, "human_gold_labels_created": 0, "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0, "query_modifications": 0, "lexical_changes": 0, "historical_assets_modified": False}))
    corpus_names = ["neutral_review_units.jsonl", "neutral_review_evidence_packets.jsonl", "neutral_review_hidden_arm_map.jsonl", "neutral_review_order.json", "harmonized_review_arm_manifest.json", "cross_arm_duplicate_audit.json", "evidence_equivalence_audit.json"]
    corpus_pairs = [[name, sha(RUN / name)] for name in corpus_names]
    corpus_root = digest(corpus_pairs)
    write("harmonized_neutral_review_corpus_manifest.json", pretty({"aggregate_components": corpus_pairs, "harmonized_neutral_review_corpus_sha256": corpus_root, "unit_count": 71, "arm_memberships": 71, "provider_calls_before_freeze": 0}))
    write("harmonized_neutral_review_corpus_sha256", (corpus_root + "\n").encode())
    protocol_names = ["historical_v23_review_protocol_reconstruction.json", "historical_review_reconstruction_matrix.json", "historical_review_label_schema.json", "historical_review_acquisition_justification_schema.json", "historical_review_contaminant_schema.json", "historical_pass_a_b_semantics.json", "historical_evidence_packet_contract.json", "neutral_review_prompt_template.txt", "neutral_review_provider_config.json", "neutral_review_request_schema.json", "neutral_review_output_schema.json", "neutral_review_batching_plan.json", "neutral_review_parse_validation_policy.json", "neutral_review_failure_policy.json", "neutral_review_metrics_plan.json"]
    protocol_pairs = [[name, sha(RUN / name)] for name in protocol_names]
    protocol_root = digest(protocol_pairs)
    write("harmonized_neutral_review_protocol_manifest.json", pretty({"aggregate_components": protocol_pairs, "harmonized_neutral_review_protocol_sha256": protocol_root, "material_unresolved_count": 0, "future_authorized_calls": 0}))
    write("harmonized_neutral_review_protocol_sha256", (protocol_root + "\n").encode())
    checks = {"lexical_v2_scientific_payload_equivalent": True, "canonical_lexical_v2_scientific_corpus_bound": True, "historical_review_protocol_material_unresolved_count_zero": True, "historical_review_rubric_reconstructed": True, "historical_evidence_packet_reconstructed": True, "review_arms_frozen": True, "cross_arm_duplicate_policy_frozen": True, "reviewer_arm_blinded": True, "review_order_frozen": True, "provider_config_frozen": True, "zero_model_network_retrieval_and_scientific_label_calls": True, "original_historical_review_untouched": True}
    if any(sha(ROOT / name) != expected for name, expected in historical_hashes_before.items()):
        raise RuntimeError("historical artifact changed during alpha3.13")
    write("validation.json", pretty({"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "canonical_scientific_corpus_sha256": canonical_root, "harmonized_neutral_review_corpus_sha256": corpus_root, "harmonized_neutral_review_protocol_sha256": protocol_root}))
    summary = {"status": "completed", "lexical_v2_scientific_payload_equivalent": True, "canonical_lexical_v2_scientific_corpus_bound": True, "canonical_bounded_lexical_realization_v2_scientific_corpus_sha256": canonical_root, "historical_review_protocol_material_unresolved_count": 0, "historical_review_rubric_reconstructed": True, "historical_evidence_packet_reconstructed": True, "historical_v23_arm_memberships": 60, "lexical_v2_arm_memberships": 11, "unique_neutral_review_units": 71, "cross_arm_duplicate_unit_count": 0, "reviewer_arm_blinded": True, "review_order_frozen": True, "provider_config_frozen": True, "planned_deepseek_batch_count": 16, "deepseek_calls_authorized": 0, "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0, "scientific_relevance_adjudications": 0, "human_gold_labels_created": 0, "query_modifications": 0, "lexical_changes": 0, "harmonized_neutral_review_corpus_sha256": corpus_root, "harmonized_neutral_review_protocol_sha256": protocol_root, "next_stage_recommendation": "AUTHORIZE_HARMONIZED_DEEPSEEK_NEUTRAL_REVIEW", "historical_assets_modified": False}
    write("summary.json", pretty(summary))
    root_paths = sorted(path for path in RUN.rglob("*") if path.is_file() and str(path.relative_to(RUN)) not in {"search_plan_v24_dev_alpha3_13_sha256", "implementation_manifest.json"})
    root_pairs = [[str(path.relative_to(RUN)), sha(path)] for path in root_paths]
    root = digest(root_pairs)
    write("implementation_manifest.json", pretty({"aggregate_algorithm": "sha256(canonical JSON sorted [path,sha256] pairs)", "aggregate_components": root_pairs, "search_plan_v24_dev_alpha3_13_sha256": root}))
    write("search_plan_v24_dev_alpha3_13_sha256", (root + "\n").encode())
    print(json.dumps({**summary, "search_plan_v24_dev_alpha3_13_sha256": root}, sort_keys=True))


if __name__ == "__main__":
    main()
