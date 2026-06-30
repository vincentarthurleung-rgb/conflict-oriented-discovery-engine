import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.config.loader import load_json_config
from src.config.validation import ConfigValidationError


class ConfigValidationTests(unittest.TestCase):
    def test_missing_config_raises_by_default(self):
        with self.assertRaises(FileNotFoundError):
            load_json_config("missing_config.json", config_type="l2_l3_ontology_rules")

    def test_existing_config_missing_required_section_raises(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"ontology_settings": {}}), encoding="utf-8")
            with self.assertRaises(ConfigValidationError):
                load_json_config(str(path), config_type="l2_l3_ontology_rules")

    def test_allow_fallback_for_invalid_config_returns_audit_event(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"ontology_settings": {}}), encoding="utf-8")
            with patch("code_engine.config.loader.write_fallback_audit"):
                data, events = load_json_config(
                    str(path),
                    config_type="l2_l3_ontology_rules",
                    allow_fallback=True,
                    strict_config=False,
                )
            self.assertIn("synonym_map", data)
            self.assertTrue(events)

    def test_missing_preferred_path_does_not_search_secondary_tree(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            secondary = root / "old_configs/l2_l3_ontology_rules.json"
            secondary.parent.mkdir(parents=True)
            secondary.write_text(
                json.dumps(
                    {
                        "ontology_settings": {"marginal_entropy_conflict_gate": 0.1},
                        "synonym_map": {"ketamine": "KETAMINE"},
                        "forbidden_object_keywords": [],
                        "weak_supervision_pool": ["ACUTE"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(FileNotFoundError):
                _, events = load_json_config(
                    str(root / "configs/normalization/l2_l3_ontology_rules.json"),
                    config_type="l2_l3_ontology_rules",
                )
            self.assertFalse((root / "reports/config_fallback_audit.json").exists())


if __name__ == "__main__":
    unittest.main()
