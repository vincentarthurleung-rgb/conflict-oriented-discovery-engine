"""Print a strict core-canonical observation audit for one run."""

from __future__ import annotations

import argparse
from pathlib import Path

from code_engine.reporting.whitebox_case import generate_whitebox_case_artifacts


def render_core_audit(run: str | Path) -> str:
    rows = generate_whitebox_case_artifacts(run)["rows"]
    lines = [f"CORE OBSERVATIONS: {len(rows)}"]
    for index, row in enumerate(rows, 1):
        lines += ["", f"[{index}] PMID {row.get('pmid') or row.get('paper_id')}", f"Title: {row.get('title')}",
                  f"Relation: {row.get('subject_name')} --{row.get('direction')}--> {row.get('object_name')}",
                  f"Evidence: {row.get('evidence_sentence')}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv); print(render_core_audit(args.run)); return 0


if __name__ == "__main__": raise SystemExit(main())
