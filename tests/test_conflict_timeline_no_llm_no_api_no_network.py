import ast
import unittest
from pathlib import Path


class DependencyGuardTests(unittest.TestCase):
    def test_temporal_package_has_no_remote_imports(self):
        forbidden = {"requests", "httpx", "openai", "deepseek_client"}
        for path in (Path(__file__).parents[1] / "src/code_engine/temporal").glob("*.py"):
            tree = ast.parse(path.read_text())
            imports = {alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
            self.assertFalse(imports & forbidden, path)


if __name__ == "__main__": unittest.main()
