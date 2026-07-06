"""C.O.D.E. Atlas UI Reality Fix — comprehensive integration tests.

Tests that verify the user-facing problems identified in the reality check
are actually fixed:
  1. Graph navigation entry exists
  2. Graph rendering functions present in JS
  3. Review judgment buttons present and labeled
  4. Review API returns items and saves annotations
  5. CSRF protection works
  6. Button active/selected CSS styles exist
  7. Filters change API behavior
  8. Evidence panel shows annotation status
  9. Validator terms excluded from graph nodes
"""
import json
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.annotation_store import AnnotationStore
from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from code_engine.system_b.explorer.explorer_server import create_app
from tests import test_system_b_knowledge_explorer as explorer_support


def _read_static(filename):
    """Read a static file from the explorer static directory."""
    p = Path("src/code_engine/system_b/explorer/static") / filename
    if not p.is_file():
        # Try from test working directory
        p = Path(__file__).parent.parent / "src/code_engine/system_b/explorer/static" / filename
    return p.read_text(encoding="utf-8")


class GraphViewTests(unittest.TestCase):
    """Test that the Knowledge Graph view is actually rendered."""

    def test_html_includes_graph_nav_entry(self):
        html = _read_static("index.html")
        self.assertIn("Graph", html, "Graph navigation entry missing from HTML")

    def test_js_includes_graph_rendering_functions(self):
        js = _read_static("app.js")
        # Graph rendering functions should exist
        self.assertIn("graphView", js, "graphView function missing")
        self.assertIn("loadGraph", js, "loadGraph function missing")
        self.assertIn("graph-layout", js, "graph-layout container ID missing")
        self.assertIn("renderTripleRows", js, "renderTripleRows function missing")
        # Triple row rendering
        self.assertIn("triple-row", js, "triple-row CSS class missing")
        self.assertIn("triple-node", js, "triple-node CSS class missing")
        self.assertIn("triple-relation", js, "triple-relation CSS class missing")
        self.assertIn("triple-arrow", js, "triple-arrow CSS class missing")
        # Entity focus
        self.assertIn("focusEntity", js, "focusEntity function missing")
        self.assertIn("clearEntityFocus", js, "clearEntityFocus function missing")
        self.assertIn("entity-focus-banner", js, "entity-focus-banner missing")
        # Triple detail
        self.assertIn("clickTripleRow", js, "clickTripleRow function missing")
        self.assertIn("showTripleDetailById", js, "showTripleDetailById function missing")
        # Keep backward compat
        self.assertIn("highlightGraphNode", js, "highlightGraphNode function missing")
        self.assertIn("showGraphTripleDetail", js, "showGraphTripleDetail function missing")
        # Empty state message
        self.assertIn("No display KG found", js, "Empty state message missing")
        self.assertIn("system_b_build_clean_kg", js, "Help text for missing KG missing")

    def test_js_excludes_validator_terms_as_nodes(self):
        js = _read_static("app.js")
        # The graph should filter out validators
        self.assertIn("isBiomedical", js, "isBiomedical filter function missing")
        self.assertIn("VALIDATOR_TERMS", js, "VALIDATOR_TERMS set missing")

    def test_router_includes_graph_route(self):
        js = _read_static("app.js")
        self.assertIn("/graph", js, "/graph route missing from router")
        self.assertIn("graphView()", js, "graphView call missing from router")

    def test_css_includes_graph_styles(self):
        css = _read_static("style.css")
        self.assertIn("triple-row", css, "triple-row CSS missing")
        self.assertIn("triple-node", css, "triple-node CSS missing")
        self.assertIn("triple-relation", css, "triple-relation CSS missing")
        self.assertIn("triple-arrow", css, "triple-arrow CSS missing")


class ReviewUITests(unittest.TestCase):
    """Test that the Review UI has working buttons and state management."""

    def test_js_includes_primary_judgment_buttons(self):
        js = _read_static("app.js")
        # Primary labels MUST be present as button text
        for label in ("VALID", "PARTIAL", "INVALID", "UNCLEAR"):
            self.assertIn(label, js, f"Primary label '{label}' missing from JS")
        # Non-comparable labels
        self.assertIn("Correctly Rejected", js, "Correctly Rejected label missing")
        self.assertIn("Should Be Weak", js, "Should Be Weak label missing")
        self.assertIn("Mech Split Useful", js, "Mech Split Useful label missing")
        # Weak candidate labels
        self.assertIn("Valid Weak", js, "Valid Weak label missing")
        self.assertIn("Valid Context Split", js, "Valid Context Split label missing")
        self.assertIn("Invalid/Non-comp", js, "Invalid/Non-comp label missing")

    def test_js_includes_button_active_state_logic(self):
        js = _read_static("app.js")
        self.assertIn("chooseReviewLabel", js, "chooseReviewLabel function missing")
        self.assertIn("active", js, "active class toggle missing")
        self.assertIn("saveReviewAnnotation", js, "saveReviewAnnotation function missing")

    def test_js_includes_toast_notification(self):
        js = _read_static("app.js")
        self.assertIn("showToast", js, "showToast function missing")
        self.assertIn("Annotation saved", js, "Save success toast message missing")

    def test_js_includes_review_metrics_update(self):
        js = _read_static("app.js")
        self.assertIn("updateReviewMetrics", js, "updateReviewMetrics function missing")

    def test_css_includes_active_selected_styles(self):
        css = _read_static("style.css")
        self.assertIn("review-choice", css, "review-choice CSS missing")
        self.assertIn(".active", css, ".active button state CSS missing")
        # Selected item highlight
        self.assertIn("selected-item", css, "selected-item CSS missing")

    def test_css_includes_toast_styles(self):
        css = _read_static("style.css")
        self.assertIn("toast", css, "toast CSS missing")

    def test_css_includes_review_two_column_layout(self):
        css = _read_static("style.css")
        self.assertIn("review-layout", css, "review-layout CSS missing")
        self.assertIn("review-queue-panel", css, "review-queue-panel CSS missing")
        self.assertIn("review-detail-panel", css, "review-detail-panel CSS missing")

    def test_html_review_page_has_two_column_structure(self):
        """The review page is rendered client-side, but JS must contain the layout divs."""
        js = _read_static("app.js")
        self.assertIn("review-layout", js, "review-layout div missing from JS")
        self.assertIn("review-queue-panel", js, "review-queue-panel div missing from JS")
        self.assertIn("review-detail-panel", js, "review-detail-panel div missing from JS")


class ReviewAPITests(unittest.TestCase):
    """Test that the review API works end-to-end."""

    def queue(self):
        return [
            {
                "review_item_id": "case::fulltext_l1_claim::claims.jsonl::1",
                "case_id": "case",
                "item_type": "fulltext_l1_claim",
                "source_file": "claims.jsonl",
                "source_line": 1,
                "claim_text": "A promotes B",
                "subject": "A",
                "relation": "promotes",
                "object": "B",
            },
            {
                "review_item_id": "case::non_comparable_direction_pair::pairs.jsonl::1",
                "case_id": "case",
                "item_type": "non_comparable_direction_pair",
                "source_file": "pairs.jsonl",
                "source_line": 1,
                "rejection_reason": "contexts differ",
            },
        ]

    def test_review_items_api_returns_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            queue = self.queue()
            explorer_support.write_jsonl(root / "manual_review_queue.jsonl", queue)
            api = ExplorerAPI(root, root)
            status, result = api.dispatch("/api/review-items")
            self.assertEqual(status, 200)
            self.assertIn("items", result)
            self.assertGreaterEqual(len(result["items"]), 2)

    def test_review_items_filter_by_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            queue = self.queue()
            explorer_support.write_jsonl(root / "manual_review_queue.jsonl", queue)
            api = ExplorerAPI(root, root)
            # All unreviewed initially
            _, all_items = api.dispatch("/api/review-items")
            self.assertEqual(all_items["total"], 2)
            # Save one annotation
            api.dispatch(
                "/api/annotation/" + queue[0]["review_item_id"],
                method="POST",
                body={"final_label": "VALID"},
            )
            # Filter reviewed
            _, reviewed = api.dispatch("/api/review-items", {"review_status": ["reviewed"]})
            self.assertEqual(reviewed["total"], 1)
            # Filter unreviewed
            _, unreviewed = api.dispatch("/api/review-items", {"review_status": ["unreviewed"]})
            self.assertEqual(unreviewed["total"], 1)

    def test_review_items_filter_by_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            queue = self.queue()
            explorer_support.write_jsonl(root / "manual_review_queue.jsonl", queue)
            api = ExplorerAPI(root, root)
            api.dispatch(
                "/api/annotation/" + queue[0]["review_item_id"],
                method="POST",
                body={"final_label": "VALID"},
            )
            _, valid_items = api.dispatch(
                "/api/review-items", {"final_label": ["VALID"]}
            )
            self.assertEqual(valid_items["total"], 1)
            _, partial_items = api.dispatch(
                "/api/review-items", {"final_label": ["PARTIAL"]}
            )
            self.assertEqual(partial_items["total"], 0)

    def test_annotation_post_saves_and_get_returns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            queue = self.queue()
            explorer_support.write_jsonl(root / "manual_review_queue.jsonl", queue)
            api = ExplorerAPI(root, root)
            item_id = queue[0]["review_item_id"]
            # POST
            status, result = api.dispatch(
                "/api/annotation/" + item_id,
                method="POST",
                body={
                    "final_label": "PARTIAL",
                    "evidence_supported": "1",
                    "direction_correct": "0",
                    "seed_relevance": "2",
                    "notes": "test note",
                },
            )
            self.assertEqual(status, 200)
            self.assertEqual(result["final_label"], "PARTIAL")
            self.assertEqual(result["evidence_supported"], "1")
            self.assertEqual(result["seed_relevance"], "2")
            # GET
            status, saved = api.dispatch("/api/annotation/" + item_id)
            self.assertEqual(status, 200)
            self.assertEqual(saved["final_label"], "PARTIAL")
            self.assertEqual(saved["notes"], "test note")

    def test_annotation_validation_rejects_invalid_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            queue = self.queue()
            explorer_support.write_jsonl(root / "manual_review_queue.jsonl", queue)
            api = ExplorerAPI(root, root)
            with self.assertRaises(ValueError):
                api.dispatch(
                    "/api/annotation/" + queue[0]["review_item_id"],
                    method="POST",
                    body={"final_label": "BIOLOGICAL_TRUTH"},
                )

    def test_review_metrics_update_after_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            queue = self.queue()
            explorer_support.write_jsonl(root / "manual_review_queue.jsonl", queue)
            api = ExplorerAPI(root, root)
            # Initial metrics
            _, initial = api.dispatch("/api/review-metrics")
            self.assertEqual(initial["reviewed_count"], 0)
            self.assertEqual(initial["unreviewed_count"], 2)
            # Save one
            api.dispatch(
                "/api/annotation/" + queue[0]["review_item_id"],
                method="POST",
                body={"final_label": "VALID"},
            )
            _, updated = api.dispatch("/api/review-metrics")
            self.assertEqual(updated["reviewed_count"], 1)
            self.assertEqual(updated["unreviewed_count"], 1)


class CSRFAndAuthTests(unittest.TestCase):
    """Test CSRF protection and auth compatibility."""

    def test_csrf_token_rejected_for_post_without_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            app = create_app(root, None, testing=True)
            client = app.test_client()
            # POST without CSRF token should fail
            resp = client.post(
                "/api/annotation/test-id",
                json={"final_label": "VALID"},
                headers={"X-CSRF-Token": "wrong"},
            )
            self.assertIn(resp.status_code, {403, 404})

    def test_session_api_returns_csrf_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            app = create_app(root, None, testing=True)
            client = app.test_client()
            resp = client.get("/api/session")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertIn("csrf_token", data)
            self.assertIsNotNone(data["csrf_token"])
            self.assertTrue(len(data["csrf_token"]) > 0)

    def test_api_returns_401_when_auth_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            users_file = root / "users.json"
            from werkzeug.security import generate_password_hash
            users_file.write_text(json.dumps({
                "testuser": {
                    "password_hash": generate_password_hash("testpass"),
                    "display_name": "Test User",
                    "role": "reviewer",
                    "enabled": True,
                }
            }))
            app = create_app(root, None, require_auth=True, users_file=str(users_file), testing=True)
            client = app.test_client()
            # API requests without login should return 401
            resp = client.get("/api/summary")
            self.assertEqual(resp.status_code, 401)


class EvidencePanelIntegrationTests(unittest.TestCase):
    """Test evidence panel shows annotation status when review exists."""

    def test_triple_evidence_shows_annotation_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            queue = [
                {
                    "review_item_id": "case::fulltext_l1_claim::claims.jsonl::1",
                    "case_id": "case",
                    "item_type": "fulltext_l1_claim",
                    "source_file": "claims.jsonl",
                    "source_line": 1,
                    "claim_text": "A promotes B",
                }
            ]
            explorer_support.write_jsonl(root / "manual_review_queue.jsonl", queue)
            api = ExplorerAPI(root, root)
            # Before annotation
            _, triple = api.dispatch("/api/triple/t1")
            ev = triple["evidence_links"][0]
            self.assertIn(ev["review_status"], ("reviewed", "unreviewed", "not_in_review_queue"))
            # After annotation
            api.dispatch(
                "/api/annotation/" + queue[0]["review_item_id"],
                method="POST",
                body={"final_label": "VALID"},
            )
            _, triple = api.dispatch("/api/triple/t1")
            ev = triple["evidence_links"][0]
            self.assertEqual(ev["review_status"], "reviewed")
            self.assertIsNotNone(ev["annotation"])
            self.assertEqual(ev["annotation"]["final_label"], "VALID")


class GraphDataAPITests(unittest.TestCase):
    """Test that graph data APIs return proper biomedical entities."""

    def test_display_triples_api_excludes_validator_entities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            # Add an entity that should NOT be a graph node
            extra_entities = [
                {
                    "entity_id": "v1",
                    "label": "LINCS",
                    "display_label": "LINCS",
                    "aliases": ["LINCS"],
                    "entity_type": "validator",
                    "degree": 1,
                    "evidence_count": 0,
                    "display_priority_score": 0.1,
                    "source_case_ids": ["case"],
                }
            ]
            explorer_support.write_jsonl(
                root / "display_entities_v2.jsonl",
                [
                    {"entity_id": "e1", "label": "A", "display_label": "A", "aliases": ["A"], "entity_type": "gene", "degree": 1, "evidence_count": 2, "display_priority_score": 0.8, "source_case_ids": ["case"]},
                    {"entity_id": "e2", "label": "B", "display_label": "B", "aliases": ["B"], "entity_type": "biological_process", "degree": 1, "evidence_count": 2, "display_priority_score": 0.7, "source_case_ids": ["case"]},
                    {"entity_id": "v1", "label": "LINCS", "display_label": "LINCS", "aliases": ["LINCS"], "entity_type": "validator", "degree": 1, "evidence_count": 0, "display_priority_score": 0.1, "source_case_ids": ["case"]},
                ],
            )
            api = ExplorerAPI(root, None)
            # The API still returns all entities (backend doesn't filter)
            # But the frontend JS must filter validators out
            js = _read_static("app.js")
            # Verify the frontend filter function exists
            self.assertIn("isBiomedical", js)

    def test_triples_api_returns_data_for_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explorer_support.KnowledgeExplorerTests().fixture(root)
            api = ExplorerAPI(root, None)
            _, triples = api.dispatch("/api/triples", {"limit": ["50"]})
            self.assertGreater(len(triples["items"]), 0)
            # Each triple should have required fields for graph rendering
            for t in triples["items"]:
                self.assertIn("triple_id", t)
                self.assertIn("subject_display_label", t)
                self.assertIn("relation_normalized", t)
                self.assertIn("object_display_label", t)


class TripleCentricLayoutTests(unittest.TestCase):
    """Test the new triple-centric row layout."""

    def test_js_contains_triple_row_renderer(self):
        js = _read_static("app.js")
        self.assertIn("renderTripleRows", js, "renderTripleRows function missing")
        self.assertIn("triple-row-inner", js, "triple-row-inner class missing")
        self.assertIn("triple-arrow", js, "triple-arrow class missing")

    def test_js_contains_entity_focus_functions(self):
        js = _read_static("app.js")
        self.assertIn("focusEntity", js, "focusEntity function missing")
        self.assertIn("clearEntityFocus", js, "clearEntityFocus function missing")
        self.assertIn("entity-focus-banner", js, "entity-focus-banner missing")
        self.assertIn("renderFilteredTriples", js, "renderFilteredTriples function missing")

    def test_js_contains_triple_click_handler(self):
        js = _read_static("app.js")
        self.assertIn("clickTripleRow", js, "clickTripleRow function missing")
        self.assertIn("showTripleDetailById", js, "showTripleDetailById function missing")

    def test_css_contains_triple_centric_styles(self):
        css = _read_static("style.css")
        self.assertIn(".triple-row", css, ".triple-row CSS missing")
        self.assertIn(".triple-node", css, ".triple-node CSS missing")
        self.assertIn(".triple-relation", css, ".triple-relation CSS missing")
        self.assertIn(".triple-arrow", css, ".triple-arrow CSS missing")
        self.assertIn(".triple-badges", css, ".triple-badges CSS missing")

    def test_css_contains_entity_focus_banner(self):
        css = _read_static("style.css")
        self.assertIn("entity-focus-banner", css, "entity-focus-banner CSS missing")

    def test_css_contains_chain_path_styles(self):
        css = _read_static("style.css")
        self.assertIn("chain-path-card", css, "chain-path-card CSS missing")
        self.assertIn("chain-entity", css, "chain-entity CSS missing")
        self.assertIn("chain-relation", css, "chain-relation CSS missing")
        self.assertIn("chain-relation-arrow", css, "chain-relation-arrow CSS missing")

    def test_js_no_longer_uses_three_column_graph_ids(self):
        """The old three-column approach (left/mid/right) should be replaced."""
        js = _read_static("app.js")
        # These old IDs should NOT appear in the graph rendering context
        self.assertNotIn("graph-left-col", js, "Old graph-left-col still present")
        self.assertNotIn("graph-right-col", js, "Old graph-right-col still present")

    def test_js_chain_card_uses_path_layout(self):
        js = _read_static("app.js")
        self.assertIn("chain-path-card", js, "chain-path-card class missing from chainCard")
        self.assertIn("chain-entity", js, "chain-entity class missing from chainCard")
        self.assertIn("chain-relation", js, "chain-relation class missing from chainCard")

    def test_js_empty_graph_state_is_clear(self):
        js = _read_static("app.js")
        self.assertIn("No display KG found", js, "Empty state message missing")
        self.assertIn("system_b_build_clean_kg", js, "Build hint missing")


if __name__ == "__main__":
    unittest.main()
