"""Integrity checks for the fail-closed alpha3.17a offline preflight."""

import hashlib
import json
from pathlib import Path

from scripts.search_plan_v24_alpha317a_safety_audits import leakage_failed, audit_search_plan_inputs


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(name: str):
    return json.loads((RUN / name).read_text())


def test_exact_six_queries_and_bytes() -> None:
    raw = (RUN / "exact_source_queries.jsonl").read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    assert len(rows) == 6
    assert _sha(raw) == (RUN / "exact_source_queries_sha256").read_text().strip()
    assert [row["stratum_order"] for row in rows] == list(range(6))
    assert len({row["query_utf8"] for row in rows}) == 6
    for row in rows:
        assert _sha(row["query_utf8"].encode("utf-8")) == row["query_sha256"]
        assert "2018/01/01" in row["query_utf8"]
        assert "2023/12/31" in row["query_utf8"]
        assert "pmc[filter]" in row["query_utf8"]


def test_upstream_and_sampling_frozen() -> None:
    assert _load("alpha3_17_root_verification.json")["status"] == "PASS"
    assert _load("pool_protocol_verification.json")["status"] == "PASS"
    algorithm = _load("source_sampling_algorithm.json")
    assert algorithm["seed_sha256"] == "e18adf084f442aa798a0008a80176055df45a8f9b7da5e95bded18360f61da53"
    assert algorithm["frame_cap"] == 200
    assert algorithm["sample_cap_per_stratum"] == 12
    assert _sha((RUN / "source_sampling_algorithm.json").read_bytes()) == (RUN / "source_sampling_algorithm_sha256").read_text().strip()
    upstream = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_16_architecture_freeze_fresh_heldout_v3_preregistration_offline"
    manifest = json.loads((upstream / "architecture_freeze_manifest.json").read_text())
    assert manifest["architecture_freeze_sha256"] == _load("pool_protocol_verification.json")["architecture_freeze_sha256"]
    assert all(_sha((ROOT / relative).read_bytes()) == expected for relative, expected in manifest["components"])


def test_builder_cardinality_and_fail_closed_quality() -> None:
    schema = _load("proposition_builder_output_schema.json")["schema"]
    assert schema["properties"]["propositions"]["minItems"] == 0
    assert schema["properties"]["propositions"]["maxItems"] == 1
    config = _load("proposition_builder_provider_config.json")
    assert (config["provider"], config["model"], config["reasoning_effort"]) == ("DeepSeek", "deepseek-v4-pro", "high")
    assert _load("proposition_quality_gate_execution_audit.json")["status"] == "QUALITY_GATE_EXECUTION_NOT_PREREGISTERED"
    assert _load("validation.json")["status"] == "FAILED_CLOSED"
    assert _load("scientific_state_safety_audit.json")["network_calls"] == 0


def test_aggregate_hashes() -> None:
    names = sorted(path.name for path in RUN.iterdir() if path.is_file() and path.name != "search_plan_v24_dev_alpha3_17a_sha256")
    pairs = [[name, _sha((RUN / name).read_bytes())] for name in names]
    data = json.dumps(pairs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    assert _sha(data) == (RUN / "search_plan_v24_dev_alpha3_17a_sha256").read_text().strip()


def test_safety_implementation_hashes_and_lexical_rule() -> None:
    implementation = ROOT / "scripts/search_plan_v24_alpha317a_safety_audits.py"
    actual = _sha(implementation.read_bytes())
    assert _load("leakage_audit_implementation_contract.json")["implementation_sha256"] == actual
    assert _load("anchor_firewall_implementation_contract.json")["implementation_sha256"] == actual
    assert leakage_failed("alpha beta gamma delta epsilon zeta eta theta", "alpha beta gamma delta epsilon zeta eta theta", "")
    assert not leakage_failed("alpha beta gamma", "alpha beta gamma", "")


def test_anchor_firewall_rejects_restricted_input(tmp_path: Path) -> None:
    public = tmp_path / "public"
    anchor = tmp_path / "vault"
    provenance = tmp_path / "provenance"
    for directory in (public, anchor, provenance):
        directory.mkdir()
    allowed = public / "target.json"
    allowed.write_text('{"neutral_proposition":"A changes B"}')
    audit_search_plan_inputs(public, anchor, provenance, [allowed])
    forbidden = public / "bad.json"
    forbidden.write_text('{"PMCID":"PMC12345"}')
    try:
        audit_search_plan_inputs(public, anchor, provenance, [forbidden])
    except ValueError:
        pass
    else:
        raise AssertionError("source identity escaped the firewall")
