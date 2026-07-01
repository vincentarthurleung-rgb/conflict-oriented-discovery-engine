import os
import unittest
from unittest.mock import patch

from code_engine.cli.run import build_parser
from code_engine.extraction.client_factory import resolve_l1_timeout_config


class L1TimeoutConfigTests(unittest.TestCase):
    def test_defaults_environment_and_cli_priority(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_l1_timeout_config(), {"connect_timeout_seconds": 20.0, "read_timeout_seconds": 120.0, "max_retries": 2})
        with patch.dict(os.environ, {"L1_CONNECT_TIMEOUT_SECONDS": "9", "L1_READ_TIMEOUT_SECONDS": "88", "L1_MAX_RETRIES": "4"}, clear=True):
            self.assertEqual(resolve_l1_timeout_config()["read_timeout_seconds"], 88.0)
            self.assertEqual(resolve_l1_timeout_config(read_timeout_seconds=180, max_retries=1)["read_timeout_seconds"], 180.0)
        args = build_parser().parse_args(["--query", "x", "--l1-read-timeout-seconds", "180", "--l1-connect-timeout-seconds", "15", "--l1-max-retries", "3"])
        self.assertEqual((args.l1_read_timeout_seconds, args.l1_connect_timeout_seconds, args.l1_max_retries), (180.0, 15.0, 3))


if __name__ == "__main__": unittest.main()
