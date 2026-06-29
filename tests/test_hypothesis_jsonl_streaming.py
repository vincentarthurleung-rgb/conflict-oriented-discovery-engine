import tempfile
import unittest
from pathlib import Path
from code_engine.hypothesis.io import iter_jsonl, write_jsonl


class HypothesisJSONLStreamingTests(unittest.TestCase):
    def test_generator_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.jsonl"
            self.assertEqual(write_jsonl(path, ({"n": n} for n in range(10000))), 10000)
            stream = iter_jsonl(path)
            self.assertEqual(next(stream), {"n": 0})
            self.assertEqual(sum(1 for _ in stream), 9999)
            source = Path(__file__).parents[1] / "src/code_engine/hypothesis/io.py"
            self.assertNotIn("read_text().splitlines()", source.read_text())


if __name__ == "__main__": unittest.main()
