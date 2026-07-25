"""Fail-closed atomicity assessment."""
from __future__ import annotations

from typing import Any


def assess_atomicity(measurements: list[dict[str, Any]], results: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if len(measurements) <= 1 and len(results) <= 1:
        return "atomic", []
    refs = [row.get("_explicit_measurement_local_ref") for row in results]
    if all(refs) and len(refs) == len(results):
        return "compound_but_explicitly_linked", []
    issues = []
    if len(measurements) > 1:
        issues.append("multiple_measurements_without_complete_explicit_mapping")
    if len(results) > 1:
        issues.append("multiple_results_without_complete_explicit_mapping")
    return "merged_unrecoverable", issues

