import tempfile
import unittest
from pathlib import Path

import code_engine
import code_engine.workflow

from code_engine.workflow.runtime_provenance import (
    build_runtime_provenance,
    contamination_check,
    imported_legacy_modules,
)


class RuntimeImportProvenanceTests(unittest.TestCase):
    def test_installed_package_and_runtime_report_use_src_package(self):
        root=Path(__file__).parents[1]
        legacy_modules_before = imported_legacy_modules()
        with tempfile.TemporaryDirectory() as tmp:
            report=build_runtime_provenance(Path(tmp),repository_root=root,resume_explicit=False,entity_registry_path=None,automatic_pilot_registry=False,l1_mode="abstract_screening",l1_task_cache_enabled=False,update_global_corpus=False,paper_registry_enabled=False,coverage_precheck=False,allow_coverage_short_circuit=False,merge_knowledge_store=False,update_global_knowledge_store=False,execute=False,legacy_modules_before=legacy_modules_before)
        self.assertEqual(Path(code_engine.workflow.__file__).resolve().parent,root/"src/code_engine/workflow")
        self.assertIn("/src/code_engine/", Path(code_engine.__file__).as_posix())
        self.assertEqual(Path(report["code_engine_import_path"]), root/"src/code_engine/__init__.py")
        self.assertFalse(report["import_shadowing_risk"])
        self.assertNotEqual(contamination_check(report)["status"],"blocked")


if __name__ == "__main__": unittest.main()
