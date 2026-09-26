"""Focused read-only checks for the frozen alpha3.13 review preregistration."""

import hashlib
import json
from pathlib import Path

from scripts import search_plan_v24_alpha313_preregister_offline as alpha313


RUN = alpha313.RUN


def _root(manifest_name: str, root_name: str, root_field: str) -> None:
    manifest = json.loads((RUN / manifest_name).read_text())
    pairs = manifest["aggregate_components"]
    actual = hashlib.sha256(alpha313.canonical(pairs)).hexdigest()
    assert actual == manifest[root_field]
    assert actual == (RUN / root_name).read_text().strip()
    assert all(alpha313.sha(RUN / path) == expected for path, expected in pairs)


def test_reconciliation_and_all_three_roots() -> None:
    audit, pairs = alpha313.reconcile()
    assert audit["lexical_v2_scientific_payload_equivalent"] is True
    assert alpha313.digest(pairs) == (RUN / "canonical_bounded_lexical_realization_v2_scientific_corpus_sha256").read_text().strip()
    _root("harmonized_neutral_review_corpus_manifest.json", "harmonized_neutral_review_corpus_sha256", "harmonized_neutral_review_corpus_sha256")
    _root("harmonized_neutral_review_protocol_manifest.json", "harmonized_neutral_review_protocol_sha256", "harmonized_neutral_review_protocol_sha256")
    _root("implementation_manifest.json", "search_plan_v24_dev_alpha3_13_sha256", "search_plan_v24_dev_alpha3_13_sha256")
    assert not any(path.is_symlink() for path in RUN.rglob("*"))


def test_historical_preservation_and_neutral_units() -> None:
    historical = alpha313.historical_reconstruction()
    rebuilt = alpha313.build_review_units(historical)
    assert historical["material_unresolved_count"] == 0
    assert len(rebuilt["units"]) == 71
    assert len(rebuilt["packets"]) == 142
    assert len(rebuilt["hidden"]) == 71
    assert not rebuilt["duplicates"]
    assert alpha313.jsonl(rebuilt["units"]) == (RUN / "neutral_review_units.jsonl").read_bytes()
    assert alpha313.jsonl(rebuilt["packets"]) == (RUN / "neutral_review_evidence_packets.jsonl").read_bytes()
    assert alpha313.jsonl(rebuilt["hidden"]) == (RUN / "neutral_review_hidden_arm_map.jsonl").read_bytes()
    assert all(alpha313.sha(alpha313.ROOT / item["path"]) == item["sha256"] for item in historical["inventory"])
    packets_text = (RUN / "neutral_review_evidence_packets.jsonl").read_text()
    assert not any(token in packets_text for token in ("heldout_v2_", "ARM_", "CORE_RELATION", "TIER_A", "TIER_B", "query_", "selection_"))


def test_scientific_taxonomies_and_future_call_boundary() -> None:
    output = json.loads((RUN / "neutral_review_output_schema.json").read_text())
    historical_a = json.loads((RUN / "historical_review_acquisition_justification_schema.json").read_text())
    historical_b = json.loads((RUN / "historical_review_label_schema.json").read_text())
    assert output["PASS_A"]["properties"]["records"]["items"]["properties"]["acquisition_decision"]["enum"] == historical_a["properties"]["acquisition_decision"]["enum"]
    assert output["PASS_B"]["properties"]["records"]["items"]["properties"]["relevance_state"]["enum"] == historical_b["properties"]["relevance_state"]["enum"]
    batches = json.loads((RUN / "neutral_review_batching_plan.json").read_text())
    summary = json.loads((RUN / "summary.json").read_text())
    assert [row["unit_count"] for row in batches["batch_plan"]] == [10] * 7 + [1]
    assert batches["planned_model_calls"] == 16
    assert batches["authorized_model_calls"] == summary["deepseek_calls"] == summary["llm_calls"] == 0
    assert summary["scientific_relevance_adjudications"] == summary["network_calls"] == summary["retrieval_calls"] == 0
