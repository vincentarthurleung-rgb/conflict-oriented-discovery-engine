import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from code_engine.schemas.validation import ValidationQueryPlan
from code_engine.validation.storage import ValidationLocalIndex, stream_jsonl_records, write_jsonl_stream


class ValidationStorageTests(unittest.TestCase):
    def plan(self):
        return ValidationQueryPlan(query_plan_id="P",anchor_id="A",validator_name="V",query_type="x",query_entities=[{"canonical_id":"GENE:MTOR"}],max_records=2,status="allowed")

    def test_jsonl_and_sqlite_streaming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); jsonl=root/"index.jsonl"
            write_jsonl_stream([{"target_id":"GENE:MTOR","record_id":"1"},{"target_id":"OTHER","record_id":"2"}],jsonl)
            records=list(ValidationLocalIndex("x","V","jsonl",jsonl).stream_query(self.plan()))
            self.assertEqual([item["record_id"] for item in records],["1"])
            self.assertEqual(len(list(stream_jsonl_records(jsonl,max_records=1))),1)
            db=root/"index.sqlite"; con=sqlite3.connect(db); con.execute("create table records(target_id text, record_id text)"); con.execute("insert into records values('GENE:MTOR','S1')"); con.commit(); con.close()
            self.assertEqual(list(ValidationLocalIndex("x","V","sqlite",db).stream_query(self.plan()))[0]["record_id"],"S1")
            self.assertFalse(ValidationLocalIndex("x","V","jsonl",root/"missing").is_available())


if __name__ == "__main__": unittest.main()
