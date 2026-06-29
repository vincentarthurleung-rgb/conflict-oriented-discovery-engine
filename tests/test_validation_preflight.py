import tempfile
import unittest
from pathlib import Path

from code_engine.schemas.validation import ValidationResourcePolicy
from code_engine.validation.preflight import run_external_validation_preflight
from code_engine.validation.registry import ValidatorRegistry


class ValidationPreflightTests(unittest.TestCase):
    def test_fixture_indexes_are_read_without_network(self):
        indexes = Path(__file__).parent / "fixtures/validation_indexes"
        report = run_external_validation_preflight(indexes, None, ValidatorRegistry().register_defaults(), ValidationResourcePolicy(index_dir=str(indexes)))
        self.assertIn(report.status, {"ready", "ready_with_warnings"})
        self.assertEqual(report.remote_clients_status, "disabled")
        self.assertEqual(report.index_status["chembl"]["status"], "ready")
        self.assertIn(report.index_status["geo"]["status"], {"not_configured", "ready"})

    def test_missing_schema_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "chembl"
            directory.mkdir()
            (directory / "records.jsonl").write_text("{}\n")
            report = run_external_validation_preflight(Path(tmp), None, ValidatorRegistry().register_defaults(), ValidationResourcePolicy(index_dir=tmp))
            self.assertEqual(report.status, "not_ready")


if __name__ == "__main__": unittest.main()
