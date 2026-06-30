import unittest

from code_engine.temporal.reports import render_temporal_evidence_section


class ReportTests(unittest.TestCase):
    def test_conservative_language(self):
        text = "\n".join(render_temporal_evidence_section([{"conflict_id":"c","status":"recent_consensus_signal"}]))
        self.assertIn("human review", text.casefold())
        self.assertNotIn("conflict is solved", text.casefold())


if __name__ == "__main__": unittest.main()
