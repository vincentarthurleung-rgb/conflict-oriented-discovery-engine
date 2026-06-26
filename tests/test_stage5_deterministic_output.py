import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.config.loader import load_pipeline_config
from src.pipelines.conflict_discovery import build_conflict_graph
from src.pipelines.ontology_alignment import extract_normalized_observations


FIXTURE_DIR = Path("tests/fixtures")


class Stage5DeterministicOutputTests(unittest.TestCase):
    def test_stage5_modules_emit_stable_output_shape(self):
        with TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "l1_5"
            input_dir.mkdir()
            shutil.copyfile(FIXTURE_DIR / "stage5_minimal_l1_5.json", input_dir / "FIXTURE_PAPER_refined.json")

            config = load_pipeline_config(str(FIXTURE_DIR / "stage5_minimal_config.json"))
            observations, audit = extract_normalized_observations(
                str(input_dir),
                synonym_map=config.synonym_map,
                forbidden_keywords=config.forbidden_object_keywords,
            )
            self.assertTrue(audit)
            self.assertEqual({(obs["subject"], obs["object"]) for obs in observations}, {("KETAMINE", "BDNF")})

            graph, conflict_edges, context_attribution, report = build_conflict_graph(
                observations,
                latent_pool=config.latent_pool,
                thresholds=config.thresholds,
            )
            self.assertEqual(len(graph), 1)
            self.assertEqual(len(conflict_edges), 1)
            self.assertEqual(len(context_attribution), 1)
            self.assertIn("marginal_entropy_H_R", graph[0])
            self.assertIn("conflict_attribution_type", graph[0])
            self.assertEqual(conflict_edges[0]["source"], "KETAMINE")
            self.assertEqual(conflict_edges[0]["target"], "BDNF")
            self.assertIn("conflict_status", conflict_edges[0])
            self.assertTrue(context_attribution[0]["ranked_contexts"])
            self.assertEqual(report["total_pairs_evaluated"], 1)

            graph2, conflict_edges2, context_attribution2, report2 = build_conflict_graph(
                observations,
                latent_pool=config.latent_pool,
                thresholds=config.thresholds,
            )
            self.assertEqual(json.dumps(graph, sort_keys=True), json.dumps(graph2, sort_keys=True))
            self.assertEqual(json.dumps(conflict_edges, sort_keys=True), json.dumps(conflict_edges2, sort_keys=True))
            self.assertEqual(json.dumps(context_attribution, sort_keys=True), json.dumps(context_attribution2, sort_keys=True))
            self.assertEqual(report, report2)


if __name__ == "__main__":
    unittest.main()
