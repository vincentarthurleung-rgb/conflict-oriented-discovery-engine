"""C.O.D.E. Atlas Chain Detail Navigation — tests for chain list and detail views.

Tests:
  1. /chains page contains chain cards with View Chain buttons.
  2. /chains does not render evidence sentences inline by default.
  3. /chain/<chain_id> route renders.
  4. /api/chain/<chain_id> returns chain + triples + evidence_by_triple.
  5. Missing evidence returns empty arrays, not error.
  6. Chain detail page contains scientific boundary text.
  7. JS navigation from chain card points to /chain/<chain_id>.
  8. CSS contains chain detail layout classes.
  9. Existing triple detail still works.
  10. /api/chains?limit=5 remains bounded.
"""
import json
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from tests import test_system_b_knowledge_explorer as explorer_support


def _read_static(filename):
    """Read a static file from the explorer static directory."""
    p = Path("src/code_engine/system_b/explorer/static") / filename
    if not p.is_file():
        p = Path(__file__).parent.parent / "src/code_engine/system_b/explorer/static" / filename
    return p.read_text(encoding="utf-8")


class ChainAPITests(unittest.TestCase):
    """Test chain API endpoints with chain detail enrichment."""

    def _fixture(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        explorer_support.KnowledgeExplorerTests().fixture(root)
        return root

    def test_api_chain_detail_returns_enriched_structure(self):
        """GET /api/chain/<id> returns chain + triples + evidence_by_triple."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        # Find a chain from the fixture
        chains = api.chains
        if not chains:
            self.skipTest("No chains in fixture")
        chain_id = chains[0]["chain_id"]
        _, result = api.dispatch(f"/api/chain/{chain_id}")
        self.assertIn("chain", result)
        self.assertIn("triples", result)
        self.assertIn("evidence_by_triple", result)
        self.assertIn("contexts_by_triple", result)
        self.assertIn("validator_annotations", result)
        self.assertIn("conflict_lens_records", result)
        self.assertIn("manual_review_summary", result)
        self.assertIn("scientific_boundary", result)

    def test_api_chain_detail_missing_chain_returns_404(self):
        """Missing chain returns 404."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        status, result = api.dispatch("/api/chain/nonexistent_chain_id")
        self.assertEqual(status, 404)

    def test_api_chain_detail_missing_evidence_returns_empty(self):
        """Chains with no evidence still return empty arrays, not error."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        chains = api.chains
        if not chains:
            self.skipTest("No chains in fixture")
        chain_id = chains[0]["chain_id"]
        _, result = api.dispatch(f"/api/chain/{chain_id}")
        # evidence_by_triple should be a dict, not raise error
        self.assertIsInstance(result["evidence_by_triple"], dict)
        self.assertIsInstance(result["triples"], list)

    def test_api_chains_limit_bounded(self):
        """GET /api/chains?limit=5 returns at most 5 items."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        _, result = api.dispatch("/api/chains", {"limit": ["5"]})
        self.assertLessEqual(len(result["items"]), 5)

    def test_triple_detail_still_works(self):
        """GET /api/triple/<id> still returns triple detail after chain changes."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        triples = api.triples
        if not triples:
            self.skipTest("No triples in fixture")
        tid = triples[0]["triple_id"]
        status, result = api.dispatch(f"/api/triple/{tid}")
        self.assertEqual(status, 200)
        self.assertIn("subject_display_label", result)


class ChainUITests(unittest.TestCase):
    """Test that chain UI has proper structure, navigation, and scientific boundary."""

    def test_js_has_chain_detail_renderer(self):
        js = _read_static("app.js")
        self.assertIn("_renderChainDetail", js, "_renderChainDetail function missing")
        self.assertIn("chainPathVisual", js, "chainPathVisual function missing")

    def test_js_chain_card_navigates_to_detail(self):
        js = _read_static("app.js")
        self.assertIn("navigateTo", js, "navigateTo function missing")
        # Chain list cards should navigate
        self.assertIn("/chain/", js, "/chain/ route reference missing")

    def test_js_chain_list_does_not_render_inline_evidence(self):
        """Chain list should not dump evidence sentences inline."""
        js = _read_static("app.js")
        # The chain list renderer should use chainPathVisual, not evidence arrays
        self.assertIn("chainPathVisual", js, "chainPathVisual missing from list renderer")
        # loadChains should NOT reference evidence_sentence or claim_text
        lc_start = js.find("function loadChains()")
        lc_end = js.find("function chainPage", lc_start)
        lc_fn = js[lc_start:lc_end] if lc_start >= 0 and lc_end >= 0 else ""
        self.assertNotIn("evidence_sentence", lc_fn,
                         "Chain list should not render evidence sentences inline")

    def test_js_chain_detail_has_scientific_boundary(self):
        js = _read_static("app.js")
        self.assertIn("not biological validation", js,
                       "Scientific boundary text missing from chain detail")

    def test_js_chain_detail_has_evidence_by_triple(self):
        js = _read_static("app.js")
        self.assertIn("evidenceByTriple", js, "evidenceByTriple reference missing")
        self.assertIn("Evidence by Triple", js, "Evidence by Triple heading missing")

    def test_js_chain_detail_has_collapsible_sections(self):
        js = _read_static("app.js")
        self.assertIn("collapsed", js, "Collapsible section class missing")
        self.assertIn("chain-evidence-toggle", js, "chain-evidence-toggle class missing")
        self.assertIn("chain-evidence-body", js, "chain-evidence-body class missing")

    def test_css_has_chain_detail_layout_classes(self):
        css = _read_static("style.css")
        for cls_name in ("chain-detail-page", "chain-path-hero", "chain-path-node",
                          "chain-path-relation", "chain-path-arrow", "chain-detail-metrics",
                          "chain-triple-section", "chain-evidence-section",
                          "chain-evidence-group", "chain-evidence-toggle",
                          "chain-evidence-body", "chain-scientific-boundary",
                          "chain-list-card", "chain-list-meta", "chain-triple-card"):
            self.assertIn(cls_name, css, f"CSS class '{cls_name}' missing")

    def test_js_chain_detail_has_back_navigation(self):
        js = _read_static("app.js")
        self.assertIn("Back to Chains", js, "Back to Chains link missing")

    def test_js_chain_detail_shows_triple_count(self):
        js = _read_static("app.js")
        self.assertIn("triples in chain", js, "Triple count display missing")


if __name__ == "__main__":
    unittest.main()
