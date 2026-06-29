import json
import tempfile
import unittest
from pathlib import Path

from code_engine.validation.index_manifest import ValidationIndexManifest, compute_index_checksum, validate_validation_index_manifest
from code_engine.validation.index_schema import load_validation_index_schema, validate_index_record_against_schema


class ValidationIndexSchemaTests(unittest.TestCase):
    def test_schema_manifest_record_and_checksum(self):
        schema = load_validation_index_schema("chembl")
        self.assertTrue(validate_index_record_against_schema({"record_id": "1"}, schema).valid)
        self.assertFalse(validate_index_record_against_schema({}, schema).valid)
        manifest = ValidationIndexManifest(index_name="chembl", validator_name="ChEMBLValidator", schema_version="0", source_database="ChEMBL", build_id="b", built_at="now", builder_name="test", builder_version="1", record_count=1, field_count=1, storage_format="jsonl", storage_path="records.jsonl")
        checked = validate_validation_index_manifest(manifest, schema)
        self.assertTrue(checked.blocked)
        self.assertIn("schema_version_mismatch", checked.warnings)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x"
            path.write_bytes(b"abc")
            self.assertTrue(compute_index_checksum(path).startswith("sha256:"))


if __name__ == "__main__": unittest.main()
