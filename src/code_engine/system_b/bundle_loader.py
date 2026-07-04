"""Read an exported case bundle without invoking any upstream service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CaseBundleLoader:
    REQUIRED_FILES = {
        "manifest": "case_bundle_manifest.json",
        "pipeline": "pipeline_stage_summary.json",
        "validator_selection": "validator_selection_report.json",
        "graph_conflict": "graph_conflict_summary.json",
        "hypothesis": "hypothesis_summary.json",
        "external_validation": "l7_external_validation_summary.json",
    }
    OPTIONAL_FILES = (
        "l7_lincs_validation_summary.json",
        "l7_pubmed_post_cutoff_summary.json", "l7_pubmed_post_cutoff_results.jsonl",
        "l7_reactome_summary.json", "l7_reactome_results.jsonl",
        "l7_enrichr_summary.json", "l7_enrichr_results.jsonl",
        "l35_fulltext_retrieval_summary.json",
        "l35_fulltext_l1_summary.json",
        "l35_fulltext_conflict_confirmation_summary.json",
        "core_observations.jsonl",
        "core_observations_table.md",
        "whitebox_case_report.md",
        "audit_report.md",
        "validator_selection_report.md",
    )

    def __init__(self, case_bundle: str | Path):
        self.path = Path(case_bundle).expanduser().resolve()

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object: {path}")
        return value

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file(): return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def load(self) -> dict[str, Any]:
        missing_required = [name for name in self.REQUIRED_FILES.values() if not (self.path / name).is_file()]
        missing_optional = [name for name in self.OPTIONAL_FILES if not (self.path / name).is_file()]
        data: dict[str, Any] = {
            key: self._read_json(self.path / name) if (self.path / name).is_file() else {}
            for key, name in self.REQUIRED_FILES.items()
        }
        lincs_path = self.path / "l7_lincs_validation_summary.json"
        data["lincs_validation"] = self._read_json(lincs_path) if lincs_path.is_file() else {}
        fulltext = {}
        for name in (
            "l35_fulltext_retrieval_summary.json",
            "l35_fulltext_l1_summary.json",
            "l35_fulltext_conflict_confirmation_summary.json",
        ):
            path = self.path / name
            if path.is_file():
                fulltext[name.removesuffix(".json")] = self._read_json(path)
        manifest = data["manifest"]
        return {
            "case_id": manifest.get("case_id") or self.path.name,
            "bundle_path": str(self.path),
            **data,
            "fulltext": fulltext,
            "discovery_layers": {
                "seed_neighborhood": self._read_jsonl(self.path / "l2_seed_neighborhood_observations.jsonl"),
                "reviewable_graph": self._read_jsonl(self.path / "l2_reviewable_graph_observations.jsonl"),
                "weak_conflicts": self._read_jsonl(self.path / "weak_conflict_candidates.jsonl"),
                "fulltext_escalation": self._read_jsonl(self.path / "l35_fulltext_candidate_papers.jsonl"),
                "excluded_audit": self._read_jsonl(self.path / "discovery_filter_audit.jsonl"),
            },
            "missing_required_files": missing_required,
            "missing_optional_files": missing_optional,
        }
