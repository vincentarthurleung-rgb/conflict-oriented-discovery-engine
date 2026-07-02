import json
import tempfile
import unittest
from pathlib import Path

from code_engine.tools.rebuild_graph_hypothesis import rebuild_graph_hypothesis


class OfflineRebuildTests(unittest.TestCase):
    def test_rebuild_reuses_l2_without_api_or_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "run"; artifacts = source / "artifacts"; artifacts.mkdir(parents=True)
            (artifacts / "l2_abstract_observations.json").write_text("[]")
            (artifacts / "runtime_provenance_report.json").write_text("{}")
            output = rebuild_graph_hypothesis(source, output_suffix="test", stages=("graph", "hypothesis"))
            provenance = json.loads((output / "artifacts/runtime_provenance_report.json").read_text())
        self.assertEqual(provenance["rebuild_from_run"]["api_calls"], 0)
        self.assertEqual(provenance["rebuild_from_run"]["network_calls"], 0)
        self.assertTrue(provenance["rebuild_from_run"]["source_l2_reused"])


if __name__ == "__main__": unittest.main()
