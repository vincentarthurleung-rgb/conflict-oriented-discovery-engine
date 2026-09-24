"""Correct post-generation accounting without changing empirical evidence.

The provisional freeze counted rejected, non-executable proposals in the
executable-query nested-conditioning safety total.  Preserve that freeze in a
byte-identical archive, then correct only reporting artifacts and the derived
aggregate root.  No provider or deterministic semantic component is invoked.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import verify_root

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_2_planner_v3_empirical_remaining7"
PROVISIONAL_ROOT = "918eefff4dbf892d5ff8f0537d034b0fa8ccfc46641ec0d22203c34b519e0ba2"
ARCHIVE = ROOT / f"runs/20260922_search_plan_v24_dev_alpha3_2_planner_v3_empirical_remaining7_provisional_reporting_defect_{PROVISIONAL_ROOT[:12]}"
ROOT_FILE = "search_plan_v24_dev_alpha3_2_empirical_v3_sha256"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> Any:
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def write(name: str, value: Any) -> None:
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")


def main() -> None:
    verify_root(RUN, PROVISIONAL_ROOT)
    if ARCHIVE.exists():
        raise ValueError("provisional archive already exists")
    shutil.copytree(RUN, ARCHIVE, copy_function=shutil.copy2)
    verify_root(ARCHIVE, PROVISIONAL_ROOT)

    coverage = [json.loads(line) for line in (RUN / "final_query_coverage.jsonl").read_text(
        encoding="utf-8").splitlines() if line]
    cores = [json.loads(line) for line in (RUN / "relation_core_analysis.jsonl").read_text(
        encoding="utf-8").splitlines() if line]
    executable_keys = {(row["case_id"], row["intent_type"], row["relation_index"])
                       for row in coverage if row.get("compiled_query") is not None}
    nested_flattening = sum(
        not row["checks"]["nested_conditioning_internal_when_required"]
        for row in cores
        if (row["case_id"], row["intent_type"], row["relation_index"]) in executable_keys)
    if nested_flattening != 0:
        raise ValueError("executable nested-conditioning flattening is not zero")

    safety = load("structural_safety_audit.json")
    safety["nested_conditioning_flattening_count"] = 0
    safety["accounting_scope"] = "EXECUTABLE_EMPIRICAL_V3_QUERIES_ONLY"
    safety["rejected_proposals_excluded_from_executable_safety_counts"] = True
    safety["post_generation_accounting_correction"] = True
    write("structural_safety_audit.json", safety)

    criteria = load("structural_readiness_criteria.json")
    criteria["criteria"]["L_nested_conditioning_flattening_zero"] = True
    criteria["passed_count"] = sum(criteria["criteria"].values())
    criteria["empirical_v3_structural_readiness"] = "FAIL"
    criteria["sole_failed_criterion"] = "F_core_direct_coverage_8_of_8"
    criteria["post_generation_accounting_correction"] = True
    write("structural_readiness_criteria.json", criteria)

    recommendation = load("next_stage_recommendation.json")
    recommendation["next_stage_recommendation"] = "DETERMINISTIC_REFINEMENT_NEEDED"
    recommendation["failure_basis"] = {
        "case_id": "heldout_v2_105",
        "failed_criterion": "F_core_direct_coverage_8_of_8",
        "planner_semantic_content_present": True,
        "deterministic_first_loss": "RESPONSE_ORIENTATION_CONTAINMENT",
        "diagnosis": "intervention inhibition token was interpreted as response-down orientation despite explicit increases-autophagic-flux relation",
        "refinement_performed": False,
    }
    recommendation["post_generation_accounting_correction"] = True
    write("next_stage_recommendation.json", recommendation)

    summary = load("summary.json")
    summary["nested_conditioning_flattening_count"] = 0
    summary["next_stage_recommendation"] = "DETERMINISTIC_REFINEMENT_NEEDED"
    summary["empirical_v3_structural_readiness"] = "FAIL"
    summary["post_generation_accounting_correction"] = True
    summary["provisional_root_sha256"] = PROVISIONAL_ROOT
    summary["provisional_freeze_preserved_path"] = str(ARCHIVE.relative_to(ROOT))
    summary["provider_calls_during_accounting_correction"] = 0
    write("summary.json", summary)

    validation = load("validation.json")
    components = [[path.name, digest(path)] for path in sorted(RUN.iterdir())
                  if path.is_file() and path.name not in {"validation.json", ROOT_FILE}]
    root = sha256_value(components)
    validation["aggregate_components"] = components
    validation[ROOT_FILE] = root
    validation["post_generation_accounting_correction"] = True
    validation["provisional_root_sha256"] = PROVISIONAL_ROOT
    validation["provisional_freeze_preserved_path"] = str(ARCHIVE.relative_to(ROOT))
    write("validation.json", validation)
    (RUN / ROOT_FILE).write_text(root + "\n", encoding="utf-8")
    verify_root(RUN, root)
    print(json.dumps({"root": root, "provisional_root": PROVISIONAL_ROOT,
                      "archive": str(ARCHIVE), "nested_conditioning_flattening_count": 0,
                      "next_stage_recommendation": "DETERMINISTIC_REFINEMENT_NEEDED"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
