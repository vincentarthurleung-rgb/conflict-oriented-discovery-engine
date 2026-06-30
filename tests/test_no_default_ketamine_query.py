import contextlib
import io
import unittest

from code_engine.cli.ingest import main


class NoDefaultKetamineQueryTests(unittest.TestCase):
    def test_ingest_requires_an_explicit_query_or_plan(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main([])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__": unittest.main()
