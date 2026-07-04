"""Batch case-factory CLI supporting JSONL and CSV seed inventories."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from code_engine.case_factory import generate_case_package
from code_engine.validation.external_api_smoke import load_dotenv


def load_seed_inventory(path: str | Path) -> list[dict]:
    source = Path(path)
    if source.suffix.casefold() == ".jsonl":
        return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if source.suffix.casefold() == ".csv":
        with source.open(encoding="utf-8", newline="") as handle: return list(csv.DictReader(handle))
    raise ValueError("seed inventory must be .jsonl or .csv")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate modern case packages from a JSONL or CSV seed inventory.")
    parser.add_argument("--seed-inventory", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("configs/generated_cases"))
    parser.add_argument("--api", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--network", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--freeze-search-plan", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--run-readiness", action="store_true"); parser.add_argument("--copy-to-configs", action="store_true")
    parser.add_argument("--overwrite-generated", action="store_true"); parser.add_argument("--overwrite-configs", action="store_true")
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    return parser


def _integer(value): return int(value) if value not in (None, "") else None


def main(argv=None) -> int:
    args = build_parser().parse_args(argv); load_dotenv()
    try: seeds = load_seed_inventory(args.seed_inventory)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "CASE_FACTORY_BATCH_BLOCKED", "error": str(exc)})); return 2
    results=[]; blocked=[]
    for seed in seeds:
        try:
            results.append(generate_case_package(case_id=str(seed["case_id"]), query=str(seed["query"]),
                case_type=str(seed.get("case_type") or "conflict_enriched"), year_from=_integer(seed.get("year_from")),
                year_to=_integer(seed.get("year_to")), output_root=args.output_root, api=args.api, network=args.network,
                freeze_search_plan=args.freeze_search_plan, run_readiness=args.run_readiness,
                copy_to_configs=args.copy_to_configs, overwrite_generated=args.overwrite_generated,
                overwrite_configs=args.overwrite_configs, repository_root=args.repository_root))
        except (KeyError, FileExistsError, RuntimeError, ValueError) as exc:
            blocked.append({"case_id": seed.get("case_id"), "error": str(exc)})
    root=args.repository_root / args.output_root; root.mkdir(parents=True, exist_ok=True)
    summary={"total_cases":len(seeds),"generated_count":len(results),"blocked_count":len(blocked),
             "warning_count":sum(bool(item.get("warnings")) for item in results),
             "case_ids":[str(item.get("case_id")) for item in seeds],"results":results,"blocked":blocked}
    (root/"case_factory_batch_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report=["# Case Factory Batch Report","",f"- Total cases: {len(seeds)}",f"- Generated: {len(results)}",
            f"- Blocked: {len(blocked)}",f"- With warnings: {summary['warning_count']}","","## Cases",""]
    report += [f"- `{case_id}`" for case_id in summary["case_ids"]]
    (root/"case_factory_batch_report.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0 if not blocked else 2


if __name__ == "__main__": raise SystemExit(main())
