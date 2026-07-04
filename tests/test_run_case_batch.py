import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from code_engine.cli.run_case_batch import build_parser, run_case_batch


class Result:
    def __init__(self,code=0): self.returncode=code; self.stdout="mock stdout\n"; self.stderr="mock stderr\n" if code else ""


class RunCaseBatchTests(unittest.TestCase):
    def _args(self,root,ids="a,b",**changes):
        values=dict(generated_case_root=root/"generated",case_ids=ids,case_inventory=None,external_data_root=root/"external",
            api=False,network=False,enable_fulltext_confirmation=False,max_workers=2,l1_concurrency=2,pubmed_concurrency=2,
            validator_concurrency=2,case_start_stagger_seconds=0,max_retries=0,retry_backoff_seconds=0,resume=False,
            overwrite_bundles=False,allow_degraded_intake=False,fail_fast=False,dry_run=True,output_root=root/"batch")
        values.update(changes); return SimpleNamespace(**values)
    def _packages(self,root,ids=("a","b"),valid=True):
        for case_id in ids:
            path=root/"generated"/case_id; path.mkdir(parents=True)
            (path/"case_profile.json").write_text("{}") ; (path/"search_plan.frozen.json").write_text("{}")
            (path/"case_factory_manifest.json").write_text(json.dumps({"semantic_intake_valid":valid,"seed_triple_quality":"high" if valid else "invalid"}))

    def test_multiple_cases_logs_and_max_workers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self._packages(root); active=0; maximum=0; lock=threading.Lock()
            def runner(*args,**kwargs):
                nonlocal active,maximum
                with lock: active+=1; maximum=max(maximum,active)
                time.sleep(.02)
                with lock: active-=1
                return Result()
            result=run_case_batch(self._args(root),subprocess_runner=runner)
            self.assertEqual(result["completed_count"],2); self.assertLessEqual(maximum,2)
            self.assertTrue((root/"batch/logs/a.stdout.log").is_file()); self.assertTrue((root/"batch/batch_report.md").is_file())

    def test_existing_bundle_skipped_and_degraded_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self._packages(root,("a",),valid=True); (root/"batch/bundles/a").mkdir(parents=True)
            result=run_case_batch(self._args(root,"a",max_workers=1),subprocess_runner=lambda *a,**k:Result())
            self.assertEqual(result["skipped_count"],1)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self._packages(root,("a",),valid=False)
            result=run_case_batch(self._args(root,"a",max_workers=1),subprocess_runner=lambda *a,**k:Result())
            self.assertEqual(result["blocked_count"],1)

    def test_failed_case_does_not_stop_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self._packages(root)
            calls=iter((1,0)); result=run_case_batch(self._args(root,max_workers=1),subprocess_runner=lambda *a,**k:Result(next(calls)))
            self.assertEqual(result["failed_count"],1); self.assertEqual(result["completed_count"],1)
