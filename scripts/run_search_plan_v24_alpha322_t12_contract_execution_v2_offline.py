"""Execution-wrapper correction only: repository-scoped synthetic scratch.

The frozen contract decision, Oracle V2, runtime, scenarios, and first driver
remain untouched. No changes to any transport or journal rule are made here.
"""

import argparse
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from scripts import run_search_plan_v24_alpha322_t12_contract_resolution_offline as run

ORIGINAL_TEMPORARY_DIRECTORY = run.tempfile.TemporaryDirectory
FAILURE = run.OUT / "execution_failure" / "first_attempt.json"


@contextmanager
def repository_scratch(*args, **kwargs):
    kwargs.setdefault("dir", str(run.ROOT / "runs"))
    with ORIGINAL_TEMPORARY_DIRECTORY(*args, **kwargs) as directory:
        yield directory


def bind():
    run.unchanged()
    FAILURE.parent.mkdir()
    run.j.atomic_freeze(FAILURE, run.j.canonical({
        "stage": "focused development execution/reporting before full matrix",
        "initial_driver": run.h.ref(Path(run.__file__), "preserved_original_development_driver"),
        "failure": "Frozen harness ref(path) calls path.relative_to(ROOT); /tmp scratch is outside ROOT, so child reporting raises ValueError. All five focused results were invalid infrastructure outputs, not successful SUT observations.",
        "observed_stdout": "focused T12: False\nfocused T05: False\nfocused T11: False\nfocused T17: False\nfocused T18: False\n",
        "observed_terminal_exception": "KeyError: 'semantic_failure_class' at counterexamples() while reading the invalid focused T12 result",
        "exit_code": 1, "full_matrix_scenarios_dispatched": 0,
        "failure_category": "DEVELOPMENT_EXECUTION_WRAPPER_PATH_CONTRACT",
        "mechanical_correction": "Use new repository-scoped isolated synthetic scratch directories, satisfying the unchanged frozen harness reference contract.",
        "new_execution_wrapper": run.h.ref(Path(__file__), "repository_scratch_binding_only"),
        "original_driver_modified": False, "contract_decision_modified": False, "oracle_modified": False,
        "runtime_modified": False, "scenario_inputs_modified": False,
        "failed_focused_infrastructure_attempts_replaced_in_development_only": 5,
        "further_model_or_network_calls": 0})).artifact_path
    return {"failure_preserved": True, "wrapper_bound": True}


def check():
    run.unchanged()
    record = run.j.strict_json(run.j.read_bytes(FAILURE))
    binding = record["new_execution_wrapper"]
    run.t.require(run.j.sha(run.j.read_bytes(run.ROOT / binding["artifact_path"])) == binding["sha256"], "EXECUTION_WRAPPER_DRIFT")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("bind", "execute", "freeze"))
    args = parser.parse_args()
    with run.master.prior.offline_guard():
        if args.operation == "bind":
            result = bind()
        else:
            check()
            with patch.object(run.tempfile, "TemporaryDirectory", repository_scratch):
                result = getattr(run, args.operation)()
            check()
        print(json.dumps(result, sort_keys=True))
