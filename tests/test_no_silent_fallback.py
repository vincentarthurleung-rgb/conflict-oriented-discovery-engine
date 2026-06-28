import unittest
from unittest.mock import patch

from src.config.loader import load_pipeline_config


class NoSilentFallbackTests(unittest.TestCase):
    def test_missing_config_raises_without_explicit_fallback(self):
        with self.assertRaises(FileNotFoundError):
            load_pipeline_config("missing_config_for_test.json", allow_fallback=False, strict_config=True)

    def test_missing_config_can_fallback_when_explicit(self):
        with patch("code_engine.config.loader.write_fallback_audit"):
            cfg = load_pipeline_config("missing_config_for_test.json", allow_fallback=True, strict_config=False)
        self.assertTrue(cfg.allow_fallback)
        self.assertTrue(cfg.fallback_events)


if __name__ == "__main__":
    unittest.main()
