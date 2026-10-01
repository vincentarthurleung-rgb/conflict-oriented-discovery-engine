"""Offline integrity checks for the prospective 0..3 builder amendment."""

import hashlib
import json
from pathlib import Path

from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import (
    candidate_id, canonicalize_candidates,
)


ROOT = Path(__file__).resolve().parents[1]
UP17 = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17_new_blinded_proposition_pool_preregistration_offline"
UP17A = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17c_builder_cardinality_reconciliation_offline"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(path: Path):
    return json.loads(path.read_text())


def test_authority_and_item_schema_preserved() -> None:
    original = _load(UP17 / "proposition_builder_schema.json")["schema"]
    narrowed = _load(UP17A / "proposition_builder_output_schema.json")["schema"]
    v2 = _load(RUN / "proposition_builder_output_schema_v2.json")["schema"]
    assert (original["properties"]["propositions"]["minItems"], original["properties"]["propositions"]["maxItems"]) == (0, 3)
    assert (narrowed["properties"]["propositions"]["minItems"], narrowed["properties"]["propositions"]["maxItems"]) == (0, 1)
    assert (v2["properties"]["candidates"]["minItems"], v2["properties"]["candidates"]["maxItems"]) == (0, 3)
    assert v2["properties"]["candidates"]["items"] == original["properties"]["propositions"]["items"]
    assert "propositions" not in v2["properties"]
    assert _load(RUN / "validation.json")["authoritative_builder_candidate_cardinality"] == "0_TO_3"


def test_dedup_identity_and_order_independence() -> None:
    a = {"actor_or_intervention": "A", "response_or_endpoint": "B"}
    b = {"actor_or_intervention": "C", "response_or_endpoint": "D"}
    first = canonicalize_candidates("opaque_1", [a, b, a])
    second = canonicalize_candidates("opaque_1", [b, a, a])
    assert len(first) == 2
    assert {x["candidate_id"] for x in first} == {x["candidate_id"] for x in second}
    assert candidate_id("opaque_1", a) != candidate_id("opaque_2", a)
    assert sorted(len(x["original_array_positions"]) for x in first) == [1, 2]
    assert canonicalize_candidates("opaque_1", []) == []


def test_protocol_and_run_hashes() -> None:
    for name, marker in (("proposition_builder_protocol_v2.json", "proposition_builder_protocol_v2_sha256"),
                         ("proposition_builder_output_schema_v2.json", "proposition_builder_output_schema_v2_sha256")):
        assert _sha((RUN / name).read_bytes()) == (RUN / marker).read_text().strip()
    names = sorted(p.name for p in RUN.iterdir() if p.is_file() and p.name != "search_plan_v24_dev_alpha3_17c_sha256")
    pairs = [[name, _sha((RUN / name).read_bytes())] for name in names]
    canonical = json.dumps(pairs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    assert _sha(canonical) == (RUN / "search_plan_v24_dev_alpha3_17c_sha256").read_text().strip()
    safety = _load(RUN / "scientific_state_safety_audit.json")
    assert all(safety[key] == 0 for key in ("provider_calls", "llm_calls", "network_calls", "retrieval_calls", "builder_calls"))
