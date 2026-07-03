import io, unittest
from contextlib import redirect_stdout
from code_engine.cli.print_env_template import main
class EnvTemplateTests(unittest.TestCase):
    def test_no_secret_is_read_or_printed(self):
        out=io.StringIO()
        with redirect_stdout(out): self.assertEqual(main(["--provider","deepseek"]),0)
        self.assertIn("DEEPSEEK_API_KEY=...",out.getvalue())
