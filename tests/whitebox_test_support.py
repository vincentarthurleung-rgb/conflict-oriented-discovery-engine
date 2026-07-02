import json
from pathlib import Path

from code_engine.reporting.whitebox_case import generate_whitebox_case_artifacts


def make_whitebox(root: Path, core_count: int = 5, other_count: int = 10):
    art = root / "artifacts"; art.mkdir(parents=True)
    rows = []
    for i in range(core_count):
        rows.append({"observation_id": f"C{i}", "paper_id": f"P{i}", "pmid": str(i),
            "title": f"Metformin AMPK breast cancer {i}", "publication_year": 2020,
            "subject_canonical_name": "metformin", "object_canonical_name": "AMPK",
            "relation_family": "activation", "direction": "activate", "graph_layer": "core_canonical_graph",
            "context_compatibility_status": "context_matched", "strong_context_match": True,
            "query_context_only": False, "evidence_sentence": "Metformin activates AMPK and inhibits mTOR in breast cancer."})
    layers = ["mechanism_layer", "context_layer", "review_layer", "excluded"]
    for i in range(other_count):
        rows.append({"observation_id": f"X{i}", "paper_id": f"X{i}", "title": "not core",
            "direction": "inhibit", "graph_layer": layers[i % len(layers)], "strong_context_match": True})
    (art / "l2_abstract_observations.json").write_text(json.dumps(rows))
    hypotheses = [{"hypothesis_id": f"H{i}", "hypothesis_type": "abstract_conflict_followup_hypothesis",
        "source_scope": "abstract", "requires_manual_review": True, "high_confidence": False, "overall_score": 0.029}
        for i in range(4)]
    (art / "hypothesis_candidates.jsonl").write_text("".join(json.dumps(x)+"\n" for x in hypotheses))
    (art / "hypothesis_summary.json").write_text(json.dumps({"hypothesis_count": 4, "hypothesis_high_confidence_count": 0}))
    (art / "acquisition_report.json").write_text(json.dumps({"candidate_papers_count": 47}))
    (art / "abstract_l1_summary.json").write_text(json.dumps({"paper_count": 47, "abstract_available_count": 46,
        "successful_l1_papers": 46, "parse_error_count": 0, "schema_error_count": 0, "timeout_count": 0}))
    (art / "l2_abstract_summary.json").write_text(json.dumps({"normalized_observation_count": 495, "retained_observation_count": 308}))
    (art / "merged_evidence_graph_summary.json").write_text(json.dumps({"true_graph_conflict_count": 0}))
    return generate_whitebox_case_artifacts(root)
