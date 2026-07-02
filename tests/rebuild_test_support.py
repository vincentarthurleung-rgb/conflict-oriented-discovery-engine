import json
from pathlib import Path

from code_engine.tools.rebuild_graph_hypothesis import rebuild_graph_hypothesis


TRIPLE = "T1"


def make_rebuild(tmp: str) -> tuple[Path, Path]:
    source = Path(tmp) / "source"; artifacts = source / "artifacts"; artifacts.mkdir(parents=True)
    state = {"run_id": "source", "query": "q", "api_calls_made": 9, "network_calls_made": 4,
             "summary": {"triple_metadata": {"triple_id": TRIPLE, "query_hash": "Q", "seed_triple": {"triple_id": TRIPLE}}}}
    (source / "run_state.json").write_text(json.dumps(state))
    provenance = {"run_dir": str(source.resolve()), "artifacts_dir": str(artifacts.resolve()),
                  "triple_id": TRIPLE, "query_hash": "Q", "seed_triple": {"triple_id": TRIPLE},
                  "search_reproducibility": {"planner_mode": "frozen_replay", "frozen_search_plan_used": True,
                    "executable_query_hash": "HASH", "pubmed_date_syntax": "pdat_range", "pubmed_query_strings": ["Q"]}}
    (artifacts / "runtime_provenance_report.json").write_text(json.dumps(provenance))
    (artifacts / "intake.json").write_text(json.dumps({"unified_seed_triple": {"triple_id": TRIPLE}}))
    (artifacts / "semantic_search_intent.json").write_text(json.dumps({"seed_triple": {"triple_id": TRIPLE}}))
    (artifacts / "search_plan.json").write_text(json.dumps({"seed_triple": {"triple_id": TRIPLE}, "paper_year_filter": {
        "enabled": True, "paper_year_from": 2000, "paper_year_to": 2020, "temporal_role": "discovery"}}))
    (artifacts / "l2_abstract_observations.json").write_text("[]")
    (artifacts / "conflict_evidence_timelines.jsonl").write_text(json.dumps({"conflict_id": "OLD"}) + "\n")
    (artifacts / "conflict_evidence_timeline_summary.json").write_text(json.dumps({"graph_conflict_candidates_used": 2}))
    output = rebuild_graph_hypothesis(source, output_suffix="rebuilt", stages=("graph", "hypothesis"))
    return source, output
