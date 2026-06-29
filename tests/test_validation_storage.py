import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from code_engine.schemas.validation import ValidationQueryPlan
from code_engine.validation.storage import ValidationLocalIndex, stream_jsonl_records, write_jsonl_stream
from code_engine.validation.index_schema import ValidationIndexSchema, write_validation_index_schema
from code_engine.validation.index_manifest import ValidationIndexManifest, write_validation_index_manifest


class ValidationStorageTests(unittest.TestCase):
    def plan(self):
        return ValidationQueryPlan(query_plan_id="P",anchor_id="A",validator_name="V",query_type="x",query_entities=[{"canonical_id":"GENE:MTOR"}],max_records=2,status="allowed")

    def test_jsonl_and_sqlite_streaming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); jsonl=root/"index.jsonl"
            write_jsonl_stream([{"target_id":"GENE:MTOR","record_id":"1"},{"target_id":"OTHER","record_id":"2"}],jsonl)
            schema=ValidationIndexSchema(index_name="x",validator_name="V",schema_version="1",source_database="fixture",required_fields=["record_id"],optional_fields=["target_id"])
            write_validation_index_schema(schema,root/"schema.json")
            manifest=ValidationIndexManifest(index_name="x",validator_name="V",schema_version="1",source_database="fixture",build_id="b",built_at="2026-01-01T00:00:00Z",builder_name="test",builder_version="1",record_count=2,field_count=2,storage_format="jsonl",storage_path="index.jsonl")
            write_validation_index_manifest(manifest,root/"manifest.json")
            records=list(ValidationLocalIndex("x","V","jsonl",jsonl,root/"schema.json",root/"manifest.json").stream_query(self.plan()))
            self.assertEqual([item["record_id"] for item in records],["1"])
            self.assertEqual(len(list(stream_jsonl_records(jsonl,max_records=1))),1)
            db=root/"index.sqlite"; con=sqlite3.connect(db); con.execute("create table records(target_id text, record_id text)"); con.execute("insert into records values('GENE:MTOR','S1')"); con.commit(); con.close()
            write_validation_index_schema(schema.model_copy(update={"record_format":"sqlite"}),root/"schema.json")
            sqlite_manifest=manifest.model_copy(update={"storage_format":"sqlite","storage_path":"index.sqlite"})
            write_validation_index_manifest(sqlite_manifest,root/"manifest.json")
            self.assertEqual(list(ValidationLocalIndex("x","V","sqlite",db,root/"schema.json",root/"manifest.json").stream_query(self.plan()))[0]["record_id"],"S1")
            self.assertFalse(ValidationLocalIndex("x","V","jsonl",root/"missing").is_available())


if __name__ == "__main__": unittest.main()
