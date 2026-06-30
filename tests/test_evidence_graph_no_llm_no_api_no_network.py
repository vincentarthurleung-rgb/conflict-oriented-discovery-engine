import ast
import unittest
from pathlib import Path


class DependencyGuardTests(unittest.TestCase):
    def test_no_remote_or_llm_imports(self):
        forbidden={"requests","httpx","openai","deepseek_client"}
        for path in (Path(__file__).parents[1]/"src/code_engine/evidence_graph").glob("*.py"):
            tree=ast.parse(path.read_text())
            names={alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom)) for alias in node.names}
            self.assertFalse(names & forbidden,path)


if __name__ == "__main__": unittest.main()
