import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from code_engine.cli.benchmark_validation_aggregator import main as benchmark_main
from code_engine.cli.build_validation_index import main as build_main
from code_engine.cli.validation_preflight import main as preflight_main


class ExternalValidationHardeningWorkflowTests(unittest.TestCase):
    def test_hardening_clis_are_offline(self):
        fixtures = Path(__file__).parent / "fixtures"
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(build_main(["--validator","reactome","--source",str(fixtures/"validation_sources/reactome_small.jsonl"),"--output-dir",str(Path(tmp)/"index"),"--dry-run"]), 0)
            self.assertEqual(preflight_main(["--validation-index-dir",str(fixtures/"validation_indexes"),"--validation-cache-dir",str(fixtures/"validation_cache"),"--output-dir",tmp,"--json"]), 0)
            self.assertEqual(benchmark_main(["--cases",str(fixtures/"validation_benchmark/benchmark_cases.jsonl"),"--output",str(Path(tmp)/"benchmark.json")]), 0)
            self.assertTrue((Path(tmp)/"validation_preflight_report.json").exists())
            self.assertTrue((Path(tmp)/"benchmark.json").exists())


if __name__ == "__main__": unittest.main()
