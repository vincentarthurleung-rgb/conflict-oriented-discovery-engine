import os
import unittest
from unittest.mock import patch

from code_engine.extraction.client_factory import OpenAIJSONClient, build_l1_client_from_env_or_config


class ClientFactoryTests(unittest.TestCase):
    def test_no_key_returns_none_without_network(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertIsNone(build_l1_client_from_env_or_config())

    def test_openai_key_builds_client_without_call(self):
        with patch.dict(os.environ,{"OPENAI_API_KEY":"fake"},clear=True):
            self.assertIsInstance(build_l1_client_from_env_or_config(),OpenAIJSONClient)


if __name__ == "__main__": unittest.main()
