"""CLI for the deterministic validation aggregation benchmark."""

import argparse
import json

from code_engine.validation.benchmarks.runner import run_aggregator_benchmark


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark conservative validation aggregation rules")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    metrics = run_aggregator_benchmark(args.cases, args.output)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0 if metrics["status_accuracy"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
