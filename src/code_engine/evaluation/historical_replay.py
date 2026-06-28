"""Historical replay benchmark skeleton.

The MVP partitions cached payloads by paper year when available and performs
lightweight entity/context mention checks against future-corpus text.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Dict, List


PAYLOAD_DIR = "data/interim/weighted_payloads"
HYPOTHESIS_PATH = "data/processed/l6/L6_final_ranked_output.json"
RESULT_PATH = "data/evaluation/historical_replay_results.json"
REPORT_PATH = "reports/historical_replay_benchmark.md"


def _extract_year(payload: dict) -> int | None:
    for field in ("year", "publication_year"):
        if payload.get(field):
            try:
                return int(payload[field])
            except ValueError:
                return None
    title = payload.get("article_title", "")
    match = re.search(r"\b(19|20)\d{2}\b", title)
    return int(match.group(0)) if match else None


def load_payloads(payload_dir: str = PAYLOAD_DIR) -> List[Dict]:
    records = []
    if not os.path.exists(payload_dir):
        return records
    for fname in sorted(os.listdir(payload_dir)):
        if not fname.endswith("_payload.json"):
            continue
        with open(os.path.join(payload_dir, fname), "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        text = " ".join(p.get("text", "") for p in payload.get("paragraphs", []))
        records.append({"paper_id": payload.get("pmcid", fname), "year": _extract_year(payload), "text": text})
    return records


def run_replay(cutoff_year: int, future_start: int, future_end: int) -> Dict:
    payloads = load_payloads()
    past = [p for p in payloads if p["year"] is not None and p["year"] <= cutoff_year]
    future = [p for p in payloads if p["year"] is not None and future_start <= p["year"] <= future_end]
    unknown_year = [p for p in payloads if p["year"] is None]

    hypotheses = []
    if os.path.exists(HYPOTHESIS_PATH):
        with open(HYPOTHESIS_PATH, "r", encoding="utf-8") as handle:
            hypotheses = json.load(handle).get("ranked_hypotheses", [])

    future_text = "\n".join(p["text"].upper() for p in future)
    checks = []
    for hyp in hypotheses:
        tokens = [token.strip().upper() for token in str(hyp.get("seed_pair", "")).replace("->", " ").split()]
        tokens = [t for t in tokens if len(t) > 3]
        hits = sorted({t for t in tokens if t in future_text})
        checks.append(
            {
                "hypothesis_id": hyp.get("hypothesis_id"),
                "seed_pair": hyp.get("seed_pair"),
                "future_entity_hits": hits,
                "future_support_status": "entity_overlap_only" if hits else "no_overlap_detected",
            }
        )

    return {
        "cutoff_year": cutoff_year,
        "future_start": future_start,
        "future_end": future_end,
        "past_corpus_count": len(past),
        "future_corpus_count": len(future),
        "unknown_year_count": len(unknown_year),
        "hypothesis_checks": checks,
        "limitations": [
            "MVP only checks entity/context overlap, not full semantic validation.",
            "Many cached payloads may lack publication year metadata.",
        ],
    }


def write_outputs(results: Dict) -> None:
    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        handle.write("# Historical Replay Benchmark\n\n")
        for key in ("cutoff_year", "future_start", "future_end", "past_corpus_count", "future_corpus_count", "unknown_year_count"):
            handle.write(f"- {key}: {results[key]}\n")
        handle.write("\n## Hypothesis Checks\n")
        for check in results["hypothesis_checks"]:
            handle.write(f"- {check['hypothesis_id']}: {check['future_support_status']} ({', '.join(check['future_entity_hits'])})\n")
        handle.write("\n## Limitations\n")
        for item in results["limitations"]:
            handle.write(f"- {item}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run historical replay benchmark skeleton.")
    parser.add_argument("--cutoff-year", type=int, required=True)
    parser.add_argument("--future-start", type=int, required=True)
    parser.add_argument("--future-end", type=int, required=True)
    args = parser.parse_args()
    results = run_replay(args.cutoff_year, args.future_start, args.future_end)
    write_outputs(results)
    print(f"[HistoricalReplay] Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
