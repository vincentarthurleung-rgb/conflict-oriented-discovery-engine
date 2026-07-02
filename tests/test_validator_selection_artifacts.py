import json
import tempfile
import unittest
from pathlib import Path

from code_engine.tools.rebuild_graph_hypothesis import rebuild_graph_hypothesis


class ValidatorSelectionArtifactTests(unittest.TestCase):
    def test_rebuild_paths_are_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"; artifacts = source / "artifacts"; artifacts.mkdir(parents=True)
            (source / "run_state.json").write_text("{}")
            (artifacts / "runtime_provenance_report.json").write_text("{}")
            stale = Path(tmp) / "runs/older_source/artifacts/x.json"
            (artifacts / "validation_plan.json").write_text(json.dumps({"path": str(stale)}))
            output = rebuild_graph_hypothesis(source, output_suffix="routed", stages=())
            value = json.loads((output / "artifacts/validation_plan.json").read_text())
            self.assertIn(str(output), value["path"])
            self.assertNotIn(str(source / "artifacts"), value["path"])


if __name__ == "__main__":
    unittest.main()
