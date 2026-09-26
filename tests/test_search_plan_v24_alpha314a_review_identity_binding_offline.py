from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/search_plan_v24_alpha314a_review_identity_binding_offline.py"
SPEC = importlib.util.spec_from_file_location("alpha314a_identity_binding", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_permutation_is_identity_valid_but_order_is_preserved_separately() -> None:
    audit = MODULE.identity_audit(["A", "B", "C"], ["B", "C", "A"])
    assert audit["identity_binding"] == "VALID"
    assert audit["provider_returned_order_matches_request_order"] is False
    assert [row["provider_returned_position"] for row in audit["position_mapping"]] == [3, 1, 2]
    assert [row["canonical_request_position"] for row in audit["position_mapping"]] == [1, 2, 3]


def test_duplicate_missing_unknown_and_count_mismatch_fail_closed() -> None:
    expected = ["A", "B", "C"]
    for returned in (["A", "A", "C"], ["A", "B"], ["A", "B", "X"], ["A", "B", "C", "X"]):
        assert MODULE.identity_audit(expected, returned)["identity_binding"] == "INVALID"


def test_opaque_record_splitting_does_not_decode_scientific_values() -> None:
    first = '{"review_unit_id":"NRV1_aaaaaaaaaaaaaaaaaaaaaaaa","rationale":"escaped } and \\"quoted\\" text","relevance_state":"X"}'
    second = '{"review_unit_id":"NRV1_bbbbbbbbbbbbbbbbbbbbbbbb","rationale":"nested [bracket]","relevance_state":"Y"}'
    records = MODULE.opaque_record_slices('{"records":[' + first + ',' + second + ']}')
    assert records == [first, second]
    assert MODULE.extract_ids(records) == ["NRV1_aaaaaaaaaaaaaaaaaaaaaaaa", "NRV1_bbbbbbbbbbbbbbbbbbbbbbbb"]


def test_invalid_or_repeated_id_key_fails_closed() -> None:
    for record in ('{"review_unit_id":"invalid"}',
                   '{"review_unit_id":"NRV1_aaaaaaaaaaaaaaaaaaaaaaaa","review_unit_id":"NRV1_bbbbbbbbbbbbbbbbbbbbbbbb"}',
                   '{"rationale":"no ID"}'):
        try:
            MODULE.extract_ids([record])
        except RuntimeError:
            pass
        else:
            raise AssertionError("invalid ID was accepted")


def test_frozen_amendment_root_and_failed_run_preservation() -> None:
    root = MODULE.RUN
    source = MODULE.SOURCE
    failed = MODULE.FAILED
    assert MODULE.load_structural(root / "validation.json")["status"] == "PASS"
    protocol = MODULE.load_structural(root / "revised_harmonized_review_protocol.json")
    assert MODULE.digest(protocol["aggregate_components"]) == (root / "revised_harmonized_review_protocol_sha256").read_text().strip()
    assert all(MODULE.sha_file((source if name not in {"response_identity_binding_v2_contract.json", "canonicalization_by_id_contract.json"} else root) / name) == checksum
               for name, checksum in protocol["aggregate_components"])
    failure_audit = MODULE.load_structural(root / "partial_review_run_preservation_audit.json")
    assert MODULE.digest(MODULE.file_inventory(failed)) == failure_audit["pre_amendment_file_inventory_sha256"]
    assert MODULE.load_structural(root / "metrics_nonexecution_audit.json")["metrics_computed"] is False
