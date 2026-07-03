"""Multi-case System B aggregation and infrastructure coverage reporting."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .bundle_loader import CaseBundleLoader
from .case_card import CaseCardBuilder
from .limitation_reporter import LimitationReporter
from .quality_classifier import QualityClassifier
from .report_exporter import ReportExporter
from .schema_validator import BundleSchemaValidator

VALIDATORS = (
    "lincs_l1000", "chembl", "reactome", "enrichr", "pubmed_post_cutoff",
    "opentargets", "uniprot", "string", "geo", "clinicaltrials", "pubchem",
)
COMPARISON_COLUMNS = (
    "case_id", "case_role", "quality_class", "comparison_readiness", "ready_for_system_b",
    "pipeline_complete", "core_observation_count", "true_graph_conflict_count",
    "formal_hypothesis_count", "manual_review_followup_count", "executed_validators",
    "unavailable_validators", "external_validation_status", "lincs_interpretation",
    "overall_validation_score", "fulltext_confirmation_status",
    "fulltext_confirmed_conflict_count", "system_b_use", "recommended_next_step",
)


def discover_bundles(roots: Iterable[str | Path], case_glob: str = "*") -> list[Path]:
    found: list[Path] = []
    for root_value in roots:
        root = Path(root_value)
        if not root.is_dir():
            continue
        found.extend(path for path in root.glob(case_glob) if path.is_dir() and (path / "case_bundle_manifest.json").is_file())
    return sorted(found, key=lambda path: str(path))


class SystemBBatchIngestor:
    def run(
        self, bundle_roots: Iterable[str | Path], output_root: str | Path,
        registry_path: str | Path, case_glob: str = "*", overwrite: bool = False,
        strict: bool = False, write_markdown: bool = False, write_csv: bool = False,
    ) -> dict[str, Any]:
        output_root = Path(output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        registry_path = Path(registry_path)
        existing = self._existing_cases(registry_path) if not overwrite else []
        by_key = {(item["case_id"], item.get("case_version", "v1")): item for item in existing}
        batch_warnings: list[str] = []

        next_label = len(by_key) + 1
        for path in discover_bundles(bundle_roots, case_glob):
            bundle = CaseBundleLoader(path).load()
            manifest = bundle["manifest"]
            version = manifest.get("case_version") or "v1"
            key = (bundle["case_id"], version)
            if key in by_key and not overwrite:
                warning = f"duplicate_case_version: {key[0]}:{key[1]}"
                if strict:
                    raise ValueError(warning)
                batch_warnings.append(warning)
                by_key[key].setdefault("warnings", []).append("duplicate_case_version")
                continue
            validation = BundleSchemaValidator().validate(bundle)
            if strict and (validation["errors"] or validation["warnings"]):
                raise ValueError(f"strict ingestion rejected {path}: {validation}")
            card = CaseCardBuilder().build(bundle)
            quality = QualityClassifier().classify(bundle, validation)
            limitations = LimitationReporter().generate(bundle, card)
            output_label = card["case_id"] if version == "v1" else f"{card['case_id']}__{version}"
            ReportExporter().export(output_root, card, quality, validation, limitations, output_label)
            label = manifest.get("case_label") or f"case_{next_label:03d}"
            next_label += 1
            row = self._registry_row(bundle, card, quality, validation, path, output_root, output_label, label, version)
            by_key[key] = row

        cases = sorted(by_key.values(), key=lambda item: (item["case_id"], item.get("case_version", "v1")))
        registry = {
            "schema_version": "system_b_case_registry_v1", "created_at": _now(),
            "case_count": len(cases), "cases": cases, "warnings": batch_warnings,
        }
        comparison = {"schema_version": "system_b_case_comparison_v1", "case_count": len(cases), "columns": list(COMPARISON_COLUMNS), "cases": [self._comparison_row(item) for item in cases]}
        matrix = {"schema_version": "system_b_validator_coverage_v1", "case_count": len(cases), "validators": list(VALIDATORS), "cases": [self._validator_row(item) for item in cases]}
        domain = self._domain_coverage(cases, matrix["cases"])
        recommendation = self._recommendations(cases)
        summary = self._batch_summary(cases, recommendation)

        _write_json(registry_path, registry)
        _write_json(output_root / "case_comparison_table.json", comparison)
        _write_json(output_root / "validator_coverage_matrix.json", matrix)
        _write_json(output_root / "domain_coverage_summary.json", domain)
        _write_json(output_root / "next_case_recommendations.json", recommendation)
        _write_json(output_root / "system_b_batch_summary.json", summary)
        if write_markdown:
            registry_path.with_suffix(".md").write_text(self._registry_md(registry), encoding="utf-8")
            (output_root / "case_comparison_table.md").write_text(_table_md(COMPARISON_COLUMNS, comparison["cases"], "System B Case Comparison"), encoding="utf-8")
            matrix_columns = ("case_id",) + VALIDATORS
            (output_root / "validator_coverage_matrix.md").write_text(_table_md(matrix_columns, matrix["cases"], "Validator Coverage Matrix"), encoding="utf-8")
            (output_root / "domain_coverage_summary.md").write_text(self._domain_md(domain), encoding="utf-8")
            (output_root / "next_case_recommendations.md").write_text(self._recommendation_md(recommendation), encoding="utf-8")
            (output_root / "system_b_batch_summary.md").write_text(self._summary_md(summary), encoding="utf-8")
        if write_csv:
            _write_csv(output_root / "case_comparison_table.csv", COMPARISON_COLUMNS, comparison["cases"])
            _write_csv(output_root / "validator_coverage_matrix.csv", ("case_id",) + VALIDATORS, matrix["cases"])
        warning_count = sum(len(case.get("warnings", [])) for case in cases)
        return {"registry": registry, "comparison": comparison, "matrix": matrix, "domain": domain, "recommendation": recommendation, "summary": summary, "warning_count": warning_count}

    @staticmethod
    def _existing_cases(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        value = json.loads(path.read_text(encoding="utf-8"))
        return value.get("cases", []) if isinstance(value, dict) else []

    @staticmethod
    def _registry_row(bundle, card, quality, validation, path, output_root, output_label, label, version):
        m, e, v = bundle["manifest"], card["evidence_summary"], card["validation_summary"]
        selection = bundle.get("validator_selection", {}).get("validator_selection", {})
        return {
            "case_id": card["case_id"], "case_version": version,
            "bundle_created_at": m.get("created_at"), "source_run_id": m.get("source_run_id"), "final_run_id": m.get("final_run_id"),
            "case_label": label, "bundle_path": str(path), "system_b_output_path": str(output_root / output_label),
            "quality_class": quality["quality_class"], "comparison_readiness": quality["comparison_readiness"],
            "ready_for_system_b": validation["ready_for_system_b"], "pipeline_complete": card["pipeline_status"]["pipeline_complete"],
            "case_role": card["case_role"], "executed_validators": v["executed_validators"], "unavailable_validators": v["unavailable_validators"],
            "selected_validators": selection.get("selected_validators", v["executed_validators"]),
            "core_observation_count": e["core_observation_count"], "true_graph_conflict_count": e["true_graph_conflict_count"],
            "formal_hypothesis_count": e["formal_hypothesis_count"], "manual_review_followup_count": e["manual_review_followup_count"],
            "external_validation_status": v["external_validation_status"], "fulltext_confirmation_status": card["fulltext_summary"]["status"],
            "fulltext_confirmed_conflict_count": m.get("fulltext_confirmed_conflict_count", 0),
            "lincs_interpretation": v["lincs_interpretation"], "overall_validation_score": v["overall_validation_score"],
            "system_b_use": quality["system_b_use"], "warnings": validation["warnings"],
        }

    @staticmethod
    def _comparison_row(case):
        row = {key: case.get(key) for key in COMPARISON_COLUMNS}
        row["recommended_next_step"] = _case_next_step(case)
        return row

    @staticmethod
    def _validator_row(case):
        executed = set(case.get("executed_validators", []))
        selected = set(case.get("selected_validators", []))
        unavailable = set(case.get("unavailable_validators", []))
        row = {"case_id": case["case_id"]}
        for validator in VALIDATORS:
            row[validator] = "executed" if validator in executed else ("selected_not_executed" if validator in selected else ("recommended_unavailable" if validator in unavailable else "unknown"))
        return row

    @staticmethod
    def _domain_coverage(cases, validator_rows):
        positive = [case for case in cases if case.get("case_role") == "positive_control_whitebox"]
        conflicts = [case for case in cases if case.get("case_role") == "conflict_enriched" or case.get("true_graph_conflict_count", 0) > 0]
        transcriptomic = [case for case in cases if "lincs_l1000" in case.get("executed_validators", [])]
        domain_counts = {
            "drug_perturbation_transcriptomic": len(transcriptomic), "pathway_mechanism": 0,
            "temporal_literature": 0, "conflict_enriched": len(conflicts), "positive_control_whitebox": len(positive),
        }
        coverage = {}
        if transcriptomic:
            relevant = [row for row in validator_rows if any(case["case_id"] == row["case_id"] for case in transcriptomic)]
            coverage["drug_perturbation_transcriptomic"] = {validator: _aggregate_status([row[validator] for row in relevant]) for validator in VALIDATORS if any(row[validator] != "unknown" for row in relevant)}
        gaps = []
        if not conflicts:
            gaps.append("No true conflict-enriched case ingested yet.")
        unavailable = sorted({validator for case in cases for validator in case.get("unavailable_validators", [])})
        if unavailable:
            display = {"reactome": "Reactome", "enrichr": "Enrichr", "opentargets": "OpenTargets", "pubmed_post_cutoff": "PubMed post-cutoff"}
            named = [display[item] for item in ("reactome", "enrichr", "opentargets", "pubmed_post_cutoff") if item in unavailable]
            if named:
                gaps.append(f"{'/'.join(named)} unavailable in current infrastructure.")
        return {"schema_version": "system_b_domain_coverage_v1", "inference_source": "case_role_and_validator_execution", "domain_counts": domain_counts, "validator_coverage_by_domain": coverage, "coverage_gaps": gaps}

    @staticmethod
    def _recommendations(cases):
        has_positive = any(case.get("case_role") == "positive_control_whitebox" for case in cases)
        conflict_cases = [case for case in cases if case.get("case_role") == "conflict_enriched" or case.get("true_graph_conflict_count", 0) > 0]
        pending_fulltext = any(case.get("true_graph_conflict_count", 0) > 0 and case.get("fulltext_confirmation_status") in {"not_enabled", "not_run", "unavailable", "unknown"} for case in cases)
        if not has_positive:
            primary, suggested = "Ingest a positive-control white-box case first.", "positive_control_whitebox"
        elif not conflict_cases:
            primary, suggested = "Proceed to first conflict-enriched case.", "conflict_enriched"
        elif pending_fulltext:
            primary, suggested = "Run full-text confirmation for conflict-enriched cases.", "fulltext_confirmation"
        else:
            primary, suggested = "Expand coverage into under-represented domains.", "under_covered_domain"
        unavailable = Counter(validator for case in cases for validator in case.get("unavailable_validators", []))
        infrastructure = [f"{validator} production validator" for validator in ("pubmed_post_cutoff", "reactome", "enrichr") if unavailable[validator]]
        return {
            "primary_recommendation": primary, "suggested_case_type": suggested,
            "suggested_case_examples": ["autophagy_cancer_chemoresistance", "tgf_beta_cancer_context", "ros_apoptosis_cancer", "nfkb_inflammation_cancer", "ferroptosis_drug_resistance"],
            "recommended_flags": ["--enable-fulltext-confirmation", "--fulltext-max-papers 20", "--fulltext-max-sections-per-paper 12", "--fulltext-max-total-chunks 200"],
            "infrastructure_gaps_to_address": infrastructure,
        }

    @staticmethod
    def _batch_summary(cases, recommendation):
        executed = Counter(validator for case in cases for validator in case.get("executed_validators", []))
        unavailable = Counter(validator for case in cases for validator in case.get("unavailable_validators", []))
        ready = sum(bool(case.get("ready_for_system_b")) for case in cases)
        return {
            "schema_version": "system_b_batch_summary_v1", "case_count": len(cases), "ready_count": ready,
            "not_ready_count": len(cases) - ready,
            "positive_control_count": sum(case.get("case_role") == "positive_control_whitebox" for case in cases),
            "conflict_enriched_count": sum(case.get("case_role") == "conflict_enriched" or case.get("true_graph_conflict_count", 0) > 0 for case in cases),
            "cases_with_true_graph_conflicts": sum(case.get("true_graph_conflict_count", 0) > 0 for case in cases),
            "cases_with_fulltext_confirmation": sum(case.get("fulltext_confirmation_status") in {"completed", "confirmed"} for case in cases),
            "executed_validator_counts": dict(executed), "recommended_unavailable_validator_counts": dict(unavailable),
            "primary_next_step": recommendation["primary_recommendation"],
        }

    @staticmethod
    def _registry_md(registry):
        columns = ("case_label", "case_id", "case_version", "case_role", "quality_class", "comparison_readiness", "ready_for_system_b")
        return _table_md(columns, registry["cases"], "System B Case Registry")

    @staticmethod
    def _domain_md(domain):
        counts = "\n".join(f"- {key}: {value}" for key, value in domain["domain_counts"].items())
        gaps = "\n".join(f"- {item}" for item in domain["coverage_gaps"]) or "- None"
        return f"# Domain Coverage Summary\n\n## Domain Counts\n\n{counts}\n\n## Coverage Gaps\n\n{gaps}\n"

    @staticmethod
    def _recommendation_md(value):
        examples = "\n".join(f"- {item}" for item in value["suggested_case_examples"])
        flags = "\n".join(f"- `{item}`" for item in value["recommended_flags"])
        gaps = "\n".join(f"- {item}" for item in value["infrastructure_gaps_to_address"]) or "- None"
        return f"# Next-Case Recommendations\n\n## Primary Recommendation\n\n{value['primary_recommendation']}\n\n## Suggested Examples\n\n{examples}\n\n## Recommended Flags\n\n{flags}\n\n## Infrastructure Gaps\n\n{gaps}\n"

    @staticmethod
    def _summary_md(value):
        return f"# System B Batch Summary\n\n- Cases: {value['case_count']}\n- Ready: {value['ready_count']}\n- Not ready: {value['not_ready_count']}\n- Positive controls: {value['positive_control_count']}\n- Conflict-enriched cases: {value['conflict_enriched_count']}\n\n## Primary Next Step\n\n{value['primary_next_step']}\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, columns, rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value for key, value in row.items()})


def _table_md(columns, rows, title) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(_cell(row.get(column, "")) for column in columns) + " |" for row in rows]
    return f"# {title}\n\n" + "\n".join([header, separator, *body]) + "\n"


def _cell(value) -> str:
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def _aggregate_status(statuses) -> str:
    if "executed" in statuses:
        return "covered"
    if "recommended_unavailable" in statuses:
        return "recommended_unavailable"
    if "selected_not_executed" in statuses:
        return "selected_not_executed"
    if "not_applicable" in statuses:
        return "not_applicable"
    return "unknown"


def _case_next_step(case) -> str:
    if case.get("case_role") == "positive_control_whitebox" and case.get("true_graph_conflict_count", 0) == 0:
        return "Proceed to first conflict-enriched case."
    if case.get("true_graph_conflict_count", 0) > 0 and case.get("fulltext_confirmation_status") in {"not_enabled", "not_run", "unavailable", "unknown"}:
        return "Run full-text confirmation."
    if not case.get("executed_validators"):
        return "Expand validator infrastructure."
    return "Include in cross-case comparison."
