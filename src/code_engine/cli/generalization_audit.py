"""Audit generic source for case-specific biological literals."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TERMS = (
    "metformin_ampk_cancer", "autophagy_cancer_chemoresistance", "metformin", "AMPK",
    "autophagy", "chemoresistance", "ATG5", "ATG7", "BECN1", "MTOR", "ULK1", "PRKAA1", "PRKAA2",
)
PATTERN = re.compile("|".join(re.escape(item) for item in sorted(TERMS, key=len, reverse=True)), re.IGNORECASE)
DOC_EXAMPLE_FILES = {
    "cli/generalization_audit.py",
    "reporting/whitebox_case.py",
    "reporting/full_abstract_pipeline.py",
}


def audit(source_root: str | Path, config_root: str | Path, test_root: str | Path) -> dict:
    roots = (("source", Path(source_root)), ("config", Path(config_root)), ("test", Path(test_root)))
    findings = []
    for area, root in roots:
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file() and "__pycache__" not in item.parts):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(lines, 1):
                matches = sorted({match.group(0) for match in PATTERN.finditer(line)}, key=str.casefold)
                if not matches:
                    continue
                relative = path.relative_to(root).as_posix()
                if area == "config":
                    category = "allowed_config"
                elif area == "test":
                    category = "allowed_test_fixture"
                elif any(relative.endswith(item) for item in DOC_EXAMPLE_FILES):
                    category = "allowed_doc_example"
                else:
                    category = "problematic_source_hardcode"
                findings.append({"category": category, "path": str(path), "line": number, "terms": matches, "excerpt": line.strip()[:300]})
    raw_counts = {key: sum(item["category"] == key for item in findings) for key in (
        "allowed_config", "allowed_test_fixture", "allowed_doc_example", "problematic_source_hardcode",
    )}
    counts = {
        "source_hardcode_findings": raw_counts["allowed_doc_example"] + raw_counts["problematic_source_hardcode"],
        "allowed_config_findings": raw_counts["allowed_config"],
        "allowed_test_fixture_findings": raw_counts["allowed_test_fixture"],
        "allowed_doc_example_findings": raw_counts["allowed_doc_example"],
        "problematic_source_hardcode_findings": raw_counts["problematic_source_hardcode"],
    }
    decision = "GENERALIZATION_AUDIT_PASS_WITH_WARNINGS" if findings and not raw_counts["problematic_source_hardcode"] else ("GENERALIZATION_AUDIT_PASS" if not findings else "GENERALIZATION_AUDIT_BLOCKED")
    return {"schema_version": "generalization_audit_v1", "decision": decision, "terms": list(TERMS), "counts": counts, "findings": findings}


def write_report(report: dict, output_root: str | Path) -> None:
    root = Path(output_root); root.mkdir(parents=True, exist_ok=True)
    (root / "generalization_audit_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = report["counts"]
    lines = ["# Generalization Audit Report", "", f"Decision: **{report['decision']}**", "", "## Counts", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in counts.items())
    lines += ["", "## Findings", ""]
    lines.extend(f"- `{item['category']}` — `{item['path']}:{item['line']}` — {', '.join(item['terms'])}" for item in report["findings"])
    (root / "generalization_audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", default="src")
    parser.add_argument("--config-root", default="configs")
    parser.add_argument("--test-root", default="tests")
    parser.add_argument("--output-root", default="audit_reports")
    args = parser.parse_args(argv)
    report = audit(args.source_root, args.config_root, args.test_root)
    write_report(report, args.output_root)
    print(report["decision"])
    return 1 if report["decision"] == "GENERALIZATION_AUDIT_BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
