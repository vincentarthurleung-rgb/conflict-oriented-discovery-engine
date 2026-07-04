import json
import tempfile
import unittest
from pathlib import Path
from code_engine.cli.case_factory_batch import main
from tests.case_factory_test_support import QUERY

class CaseFactoryBatchTests(unittest.TestCase):
    def _run(self,suffix,content):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/f"seeds.{suffix}"; source.write_text(content,encoding="utf-8")
            code=main(["--seed-inventory",str(source),"--output-root","generated","--repository-root",tmp,"--no-api","--no-network","--allow-degraded-intake"])
            self.assertEqual(code,0); summary=json.loads((Path(tmp)/"generated/case_factory_batch_summary.json").read_text())
            self.assertEqual(summary["generated_count"],2)
    def test_jsonl_inventory(self):
        self._run("jsonl","\n".join(json.dumps({"case_id":f"case_{i}","query":QUERY,"case_type":"conflict_enriched","year_from":2000,"year_to":2020}) for i in range(2)))
    def test_csv_inventory(self):
        self._run("csv",f"case_id,query,case_type,year_from,year_to\ncase_a,{QUERY},conflict_enriched,2000,2020\ncase_b,{QUERY},conflict_enriched,2001,2021\n")
