"""Generic regressions for historical manifest verification."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from code_engine.search.historical_manifest_verifier import verify_frozen_manifest


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class HistoricalManifestVerifierTests(unittest.TestCase):
    def fixture(self, root: Path):
        payloads = {"a.json": b"alpha\n", "b.jsonl": b"beta\n"}
        pairs = []
        for name, body in payloads.items():
            (root / name).write_bytes(body)
            pairs.append([name, hashlib.sha256(body).hexdigest()])
        aggregate = hashlib.sha256(canonical(pairs)).hexdigest()
        (root / "implementation_manifest.json").write_text(json.dumps({
            "aggregate_components": [{"path": name, "sha256": digest} for name, digest in pairs],
            "frozen_root": aggregate,
        }))
        return aggregate

    def test_later_new_tracked_file_does_not_invalidate_historical_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = self.fixture(root)
            (root / "later_new_tracked_file.py").write_text("later\n")
            self.assertEqual(verify_frozen_manifest(root, root_field="frozen_root")["aggregate_sha256"], expected)

    def test_historical_protected_file_modification_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / "a.json").write_bytes(b"changed\n")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_frozen_manifest(root, root_field="frozen_root")

    def test_historical_protected_file_deletion_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / "a.json").unlink()
            with self.assertRaisesRegex(ValueError, "missing or replaced"):
                verify_frozen_manifest(root, root_field="frozen_root")

    def test_historical_protected_file_replacement_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            target = root / "a.json"
            target.unlink()
            target.symlink_to(root / "b.jsonl")
            with self.assertRaisesRegex(ValueError, "missing or replaced"):
                verify_frozen_manifest(root, root_field="frozen_root")

    def test_original_historical_aggregate_hash_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = self.fixture(root)
            result = verify_frozen_manifest(root, root_field="frozen_root")
            self.assertEqual(result["declared_aggregate_sha256"], expected)
            self.assertEqual(result["protected_file_count"], 2)
            self.assertFalse(result["current_repository_membership_enumerated"])


if __name__ == "__main__":
    unittest.main()
