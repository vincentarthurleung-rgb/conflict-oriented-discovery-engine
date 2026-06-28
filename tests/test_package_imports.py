import importlib
import unittest


class PackageImportTests(unittest.TestCase):
    def test_new_package_paths_import(self):
        modules = (
            "code_engine.schemas",
            "code_engine.config",
            "code_engine.graph.conflict_discovery",
            "code_engine.graph.context_mining",
            "code_engine.validation.curated_omics",
            "code_engine.reporting.ranking",
            "code_engine.query.parser",
        )
        for module in modules:
            with self.subTest(module=module):
                importlib.import_module(module)

    def test_legacy_paths_import(self):
        modules = (
            "src.schemas",
            "src.config",
            "src.validators",
            "src.reporting",
            "src.query",
            "src.pipelines.conflict_discovery",
        )
        for module in modules:
            with self.subTest(module=module):
                importlib.import_module(module)

    def test_cli_modules_import_without_execution(self):
        modules = (
            "code_engine.cli.query",
            "code_engine.cli.validate",
            "code_engine.cli.extract",
            "code_engine.cli.visualize",
        )
        for module in modules:
            with self.subTest(module=module):
                importlib.import_module(module)

    def test_legacy_and_new_exports_share_implementations(self):
        from code_engine.graph.conflict_discovery import build_conflict_graph as new_build
        from src.pipelines.conflict_discovery import build_conflict_graph as legacy_build

        self.assertIs(new_build, legacy_build)


if __name__ == "__main__":
    unittest.main()
