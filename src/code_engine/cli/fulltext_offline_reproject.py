"""CLI for zero-network fulltext evidence reprojection."""
from __future__ import annotations

import argparse
import json

from code_engine.fulltext.evidence_projection import project_fulltext_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_runs", nargs="+", help="Existing immutable fulltext reentry runs")
    parser.add_argument("--output-root", default=None)
    args = parser.parse_args()
    results = [project_fulltext_run(run, args.output_root) for run in args.source_runs]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
