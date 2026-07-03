"""Fault-tolerant read-only access to System B dashboard source files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DashboardData:
    SOURCES = {
        "registry": "case_registry.json",
        "batch": "system_b_batch_summary.json",
        "comparison": "case_comparison_table.json",
        "validator_coverage": "validator_coverage_matrix.json",
        "domain_coverage": "domain_coverage_summary.json",
        "recommendations": "next_case_recommendations.json",
    }

    def __init__(self, system_b_root: str | Path, kg_root: str | Path):
        self.root, self.kg_root = Path(system_b_root), Path(kg_root)

    def read(self, key: str) -> dict[str, Any]:
        return self._read_json(self.root / self.SOURCES[key])

    def cases(self) -> dict[str, Any]:
        value = self.read("registry")
        return {"schema_version": value.get("schema_version", "system_b_case_registry_v1"), "case_count": value.get("case_count", len(value.get("cases", []))), "cases": value.get("cases", []), "warnings": self.warnings()}

    def case(self, case_id: str) -> dict[str, Any] | None:
        return next((item for item in self.cases()["cases"] if item.get("case_key") == case_id or item.get("case_id") == case_id), None)

    def case_card(self, case_id: str) -> dict[str, Any] | None:
        case = self.case(case_id)
        if not case: return None
        card = self._read_json(self._case_output(case, case_id) / "system_b_case_card.json")
        quality = self._read_json(self._case_output(case, case_id) / "system_b_quality_report.json")
        if not card and not quality: return None
        result = dict(card)
        result.setdefault("case_id", case_id)
        result["quality_class"] = quality.get("quality_class", case.get("quality_class"))
        result["comparison_readiness"] = quality.get("comparison_readiness", case.get("comparison_readiness"))
        result["limitations"] = quality.get("limitations", [])
        return result

    def case_quality(self, case_id: str) -> dict[str, Any] | None:
        case = self.case(case_id)
        if not case: return None
        value = self._read_json(self._case_output(case, case_id) / "system_b_quality_report.json")
        return value or {"case_id": case_id, "quality_class": case.get("quality_class"), "comparison_readiness": case.get("comparison_readiness"), "warnings": ["missing_optional_file: system_b_quality_report.json"]}

    def summary(self) -> dict[str, Any]:
        batch, kg = self.read("batch"), self._read_json(self.kg_root / "kg_summary.json")
        return {
            "schema_version": "system_b_dashboard_summary_v1",
            "case_count": batch.get("case_count", self.cases()["case_count"]),
            "ready_count": batch.get("ready_count", sum(bool(item.get("ready_for_system_b")) for item in self.cases()["cases"])),
            "positive_control_count": batch.get("positive_control_count", 0),
            "conflict_enriched_count": batch.get("conflict_enriched_count", 0),
            "kg": {key: kg.get(key, 0) for key in ("node_count", "edge_count", "evidence_count", "claim_relation_count", "fulltext_claim_count")},
            "executed_validator_counts": batch.get("executed_validator_counts", {}),
            "recommended_unavailable_validator_counts": batch.get("recommended_unavailable_validator_counts", {}),
            "primary_next_step": batch.get("primary_next_step") or self.read("recommendations").get("primary_recommendation"),
            "warnings": [item for item in self.warnings() if "duplicate_case_version" not in item],
        }

    def comparison(self):
        value = self.read("comparison"); return {**value, "cases": value.get("cases", []), "warnings": self._missing_warning("comparison")}

    def validator_coverage(self):
        value = self.read("validator_coverage"); return {**value, "cases": value.get("cases", []), "warnings": self._missing_warning("validator_coverage")}

    def domain_coverage(self):
        value = self.read("domain_coverage"); return {**value, "warnings": self._missing_warning("domain_coverage")}

    def recommendations(self):
        value = self.read("recommendations"); return {**value, "warnings": self._missing_warning("recommendations")}

    def warnings(self) -> list[str]:
        warnings = []
        for key, name in self.SOURCES.items():
            if not (self.root / name).is_file(): warnings.append(f"missing_optional_file: {name}")
        if not (self.kg_root / "kg_summary.json").is_file(): warnings.append("missing_optional_file: kg/kg_summary.json")
        registry = self.read("registry")
        warnings.extend(str(item) for item in registry.get("warnings", []))
        for case in registry.get("cases", []):
            warnings.extend(f"{case.get('case_id')}: {item}" for item in case.get("warnings", []))
        return list(dict.fromkeys(warnings))

    def files(self) -> dict[str, Any]:
        files = []
        if self.root.is_dir():
            files.extend(str(path.relative_to(self.root)) for path in self.root.rglob("*") if path.is_file())
        return {"root": str(self.root), "files": sorted(files), "warnings": self.warnings()}

    def _missing_warning(self, key):
        name = self.SOURCES[key]
        return [] if (self.root / name).is_file() else [f"missing_optional_file: {name}"]

    def _case_output(self, case, case_id):
        configured = case.get("system_b_output_path")
        if configured:
            path = Path(configured)
            if not path.is_absolute(): path = Path.cwd() / path
            return path
        return self.root / case_id

    @staticmethod
    def _read_json(path):
        if not path.is_file(): return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
