import os
import unittest
from unittest.mock import patch

from code_engine.extraction.client_factory import (
    OpenAIJSONClient,
    build_entity_cleaner_client_from_config,
    build_l1_client_from_env_or_config,
    diagnose_entity_cleaner_provider,
)


class ClientFactoryTests(unittest.TestCase):
    def test_no_key_returns_none_without_network(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertIsNone(build_l1_client_from_env_or_config())

    def test_openai_key_builds_client_without_call(self):
        with patch.dict(os.environ,{"OPENAI_API_KEY":"fake"},clear=True):
            self.assertIsInstance(build_l1_client_from_env_or_config(),OpenAIJSONClient)

    def test_entity_cleaner_uses_l2_config_over_l1_fallback(self):
        env = {
            "L1_PROVIDER": "openai",
            "MODEL_NAME": "l1-model",
            "OPENAI_API_KEY": "fake-openai",
            "L2_ENTITY_CLEANER_PROVIDER": "deepseek",
            "L2_ENTITY_CLEANER_MODEL": "cleaner-model",
            "DEEPSEEK_API_KEY": "fake-deepseek",
        }
        with patch.dict(os.environ, env, clear=True):
            diagnostic = diagnose_entity_cleaner_provider()
            self.assertTrue(diagnostic["provider_available"])
            self.assertEqual(diagnostic["provider"], "deepseek")
            self.assertEqual(diagnostic["model"], "cleaner-model")
            self.assertIsNotNone(build_entity_cleaner_client_from_config())

    def test_entity_cleaner_requires_model_config(self):
        with patch.dict(os.environ, {"L1_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "fake"}, clear=True):
            diagnostic = diagnose_entity_cleaner_provider()
            self.assertFalse(diagnostic["provider_available"])
            self.assertEqual(diagnostic["provider_error"], "model_not_configured")
            self.assertIsNone(build_entity_cleaner_client_from_config())


if __name__ == "__main__": unittest.main()
