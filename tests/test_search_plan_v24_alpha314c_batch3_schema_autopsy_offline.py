from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/search_plan_v24_alpha314c_batch3_schema_autopsy_offline.py"
SPEC = importlib.util.spec_from_file_location("alpha314c_schema_autopsy", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_validator_reports_paths_without_values() -> None:
    schema = {"type": "object", "required": ["state"], "additionalProperties": False,
              "properties": {"state": {"type": "string", "enum": ["VALID"]}}}
    errors = MODULE.validate_structure({"state": "INVALID", "extra": 123}, schema)
    assert errors == [{"path": "$.extra", "failure": "EXTRA_PROHIBITED"},
                      {"path": "$.state", "failure": "ENUM"}]
    assert "INVALID" not in str(errors)


def test_missing_and_wrong_type_are_independent_schema_failures() -> None:
    schema = {"type": "object", "required": ["x"], "properties": {"x": {"type": "string"}}}
    assert MODULE.validate_structure({}, schema) == [{"path": "$.x", "failure": "MISSING_REQUIRED"}]
    assert MODULE.validate_structure({"x": 1}, schema) == [{"path": "$.x", "failure": "TYPE"}]


def test_frozen_autopsy_root_and_no_salvage() -> None:
    root = MODULE.RUN
    pairs = [[path.name, MODULE.sha(path)] for path in sorted(root.iterdir())
             if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14c_sha256"]
    assert MODULE.digest(pairs) == (root / "search_plan_v24_dev_alpha3_14c_sha256").read_text().strip()
    inventory = MODULE.load(root / "batch3_schema_failure_inventory.json")
    assert inventory["batch3_schema_failure_count"] == 7
    assert inventory["batch3_relevance_state_enum_failure_count"] == 6
    assert inventory["batch3_other_schema_failure_count"] == 1
    assert MODULE.load(root / "batch3_reuse_eligibility.json")["PASS_B_BATCH3_REUSABLE_WITHOUT_REINFERENCE"] is False
    assert MODULE.load(root / "arm_firewall_audit.json")["arm_map_accessed"] is False
    assert MODULE.load(root / "metrics_nonexecution_audit.json")["metrics_computed"] is False
    assert not (root / "harmonized_review_output_validation_protocol_v3_sha256").exists()
