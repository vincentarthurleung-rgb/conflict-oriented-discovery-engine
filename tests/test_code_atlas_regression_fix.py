"""C.O.D.E. Atlas Data Loading Regression Tests — verify schema normalization and error resilience.

Tests:
  1. /api/conflicts?bucket=potential_conflict returns JSON with items.
  2. /api/conflicts?bucket=all returns JSON with items.
  3. /api/chains?limit=1 returns {items} and frontend normalizer handles it.
  4. /api/chain/<chain_id> returns required keys.
  5. app.js contains asItems normalization.
  6. app.js contains page-level error fallback.
  7. conflicts renderer handles {items, summary} payload.
  8. chains renderer handles {items} payload.
  9. chain detail renderer handles missing evidence_by_triple.
  10. Graph/review/conflicts/chains routes have error fallback.
  11. static app.js/style.css 200.
  12. No page displays blank on API error.
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


class APISchemaRegressionTests(unittest.TestCase):
    """Test that all API endpoints return consistent schemas."""

    def _fixture(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        explorer_support.KnowledgeExplorerTests().fixture(root)
        return root

    def test_conflicts_potential_returns_items_key(self):
        """GET /api/conflicts?bucket=potential_conflict returns {items, summary}."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        _, result = api.dispatch("/api/conflicts", {"bucket": ["potential_conflict"]})
        self.assertIn("items", result)
        self.assertIn("summary", result)
        self.assertIsInstance(result["items"], list)

    def test_conflicts_all_returns_items_key(self):
        """GET /api/conflicts?bucket=all returns {items, summary}."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        _, result = api.dispatch("/api/conflicts", {"bucket": ["all"]})
        self.assertIn("items", result)
        self.assertIsInstance(result["items"], list)

    def test_conflicts_mechanism_diagnostic_returns_items(self):
        """GET /api/conflicts?bucket=mechanism_diagnostic returns items."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        _, result = api.dispatch("/api/conflicts", {"bucket": ["mechanism_diagnostic"]})
        self.assertIn("items", result)
        self.assertIsInstance(result["items"], list)

    def test_conflicts_data_quality_returns_items(self):
        """GET /api/conflicts?bucket=data_quality returns items."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        _, result = api.dispatch("/api/conflicts", {"bucket": ["data_quality"]})
        self.assertIn("items", result)
        self.assertIsInstance(result["items"], list)

    def test_chains_returns_items_key(self):
        """GET /api/chains returns {items, total}."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        _, result = api.dispatch("/api/chains", {"limit": ["3"]})
        self.assertIn("items", result)
        self.assertIsInstance(result["items"], list)

    def test_chain_detail_has_required_keys(self):
        """GET /api/chain/<id> returns all required keys even if empty."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        chains = api.chains
        if not chains:
            self.skipTest("No chains in fixture")
        cid = chains[0]["chain_id"]
        _, result = api.dispatch(f"/api/chain/{cid}")
        for key in ("chain", "triples", "evidence_by_triple", "contexts_by_triple",
                     "validator_annotations", "conflict_lens_records", "manual_review_summary"):
            self.assertIn(key, result, f"Missing key: {key}")
        # triples should be a list, evidence_by_triple should be a dict
        self.assertIsInstance(result["triples"], list)
        self.assertIsInstance(result["evidence_by_triple"], dict)

    def test_chain_detail_missing_returns_404_not_error(self):
        """Missing chain returns 404, not 500."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        status, _ = api.dispatch("/api/chain/nonexistent_id")
        self.assertEqual(status, 404)

    def test_review_workspace_returns_dict(self):
        """GET /api/review-workspace returns dict with cases."""
        root = self._fixture()
        api = ExplorerAPI(root, root)
        status, result = api.dispatch("/api/review-workspace")
        self.assertEqual(status, 200)
        self.assertIsInstance(result, dict)
        self.assertIn("cases", result)

    def test_cases_returns_items(self):
        """GET /api/cases returns {items}."""
        root = self._fixture()
        api = ExplorerAPI(root, None)
        _, result = api.dispatch("/api/cases")
        self.assertIn("items", result)
        self.assertIsInstance(result["items"], list)


class FrontendNormalizationTests(unittest.TestCase):
    """Test that the frontend JS has normalization helpers and error resilience."""

    def test_js_has_asItems_normalizer(self):
        js = _read_static("app.js")
        self.assertIn("function asItems(", js, "asItems function missing")
        self.assertIn("Array.isArray(payload)", js, "Array.isArray guard missing in asItems")
        self.assertIn("Array.isArray(payload.items)", js, "payload.items guard missing in asItems")

    def test_js_has_asSummary_normalizer(self):
        js = _read_static("app.js")
        self.assertIn("function asSummary(", js, "asSummary function missing")

    def test_js_has_ensureDict(self):
        js = _read_static("app.js")
        self.assertIn("function ensureDict(", js, "ensureDict function missing")

    def test_js_has_ensureArray(self):
        js = _read_static("app.js")
        self.assertIn("function ensureArray(", js, "ensureArray function missing")

    def test_js_has_showPageError(self):
        js = _read_static("app.js")
        self.assertIn("function showPageError(", js, "showPageError function missing")

    def test_js_loadConflicts_uses_normalizers(self):
        js = _read_static("app.js")
        # Find loadConflicts function
        start = js.find("async function loadConflicts()")
        end = js.find("function _renderConflictSummary", start)
        block = js[start:end] if start >= 0 and end >= 0 else ""
        self.assertIn("asItems(d)", block, "loadConflicts must use asItems(d)")
        self.assertIn("asSummary(d)", block, "loadConflicts must use asSummary(d)")

    def test_js_loadChains_uses_normalizers(self):
        js = _read_static("app.js")
        start = js.find("function loadChains()")
        end = js.find("function chainPathVisual", start)
        block = js[start:end] if start >= 0 and end >= 0 else ""
        self.assertIn("asItems(d)", block, "loadChains must use asItems(d)")

    def test_js_renderChainDetail_has_ensure_guards(self):
        js = _read_static("app.js")
        start = js.find("function _renderChainDetail(")
        end = js.find("var html='';", start)
        block = js[start:end] if start >= 0 and end >= 0 else ""
        self.assertIn("ensureArray(triples)", block, "_renderChainDetail must guard triples")
        self.assertIn("ensureDict(evidenceByTriple)", block, "_renderChainDetail must guard evidenceByTriple")
        self.assertIn("ensureDict(contextsByTriple)", block, "_renderChainDetail must guard contextsByTriple")

    def test_js_route_has_error_handler(self):
        js = _read_static("app.js")
        self.assertIn("Unable to load view", js, "Route error handler missing")
        self.assertIn("console.error", js, "Route must log errors to console")

    def test_js_loadGraph_uses_asItems(self):
        js = _read_static("app.js")
        self.assertIn("asItems(triplesData)", js, "loadGraph must use asItems(triplesData)")

    def test_static_files_exist(self):
        """Static files should exist and be readable."""
        js = _read_static("app.js")
        css = _read_static("style.css")
        html = _read_static("index.html")
        self.assertGreater(len(js), 1000, "app.js too small or empty")
        self.assertGreater(len(css), 1000, "style.css too small or empty")
        self.assertGreater(len(html), 200, "index.html too small or empty")


if __name__ == "__main__":
    unittest.main()
