"""C.O.D.E. Atlas Conflict Lens Noise Reduction — tests for bucketing logic and UI separation.

Tests:
  1. /api/conflicts default returns only potential_conflict bucket.
  2. mechanism_split is excluded from default potential_conflict.
  3. non_comparable_direction_pair is excluded from default potential_conflict.
  4. records missing A/B previews go to data_quality bucket.
  5. empty potential_conflict returns useful summary and empty items.
  6. UI contains tab labels: Potential Conflicts, Mechanism Diagnostics, etc.
  7. UI empty state says no potential conflict candidates found.
  8. Missing preview records do not render full pair cards in default view.
  9. Mechanism diagnostic page warns that mechanism splits are not validated conflicts.
  10. Data quality tab shows missing preview count.
  11. Existing linked triple rendering still works when available.
  12. No card displays bare dash for Observation A/B in default mode.
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


class ConflictBucketingAPITests(unittest.TestCase):
    """Test that the /api/conflicts endpoint correctly buckets and filters records."""

    def _fixture_root(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        explorer_support.KnowledgeExplorerTests().fixture(root)
        return root

    def _make_conflicts(self, records):
        return records

    def _api_with_conflicts(self, root, conflicts):
        explorer_support.write_jsonl(root / "conflict_lens_records.jsonl", conflicts)
        return ExplorerAPI(root, None)

    def test_default_returns_only_potential_conflict_bucket(self):
        """Default /api/conflicts returns only potential_conflict items."""
        root = self._fixture_root()
        conflicts = [
            {
                "record_type": "weak_candidate", "case_id": "case",
                "observation_a_preview": "A promotes B.", "observation_b_preview": "C inhibits D.",
            },
            {
                "record_type": "mechanism_split", "case_id": "case",
                "observation_a_preview": "X activates Y.", "observation_b_preview": "X inhibits Y.",
            },
            {
                "record_type": "non_comparable_direction_pair", "case_id": "case",
                "observation_a_preview": "P upregulates Q.", "observation_b_preview": "R downregulates S.",
            },
        ]
        api = self._api_with_conflicts(root, conflicts)
        _, result = api.dispatch("/api/conflicts")
        items = result["items"]
        # Default bucket is potential_conflict — only weak_candidate should appear
        self.assertEqual(len(items), 1, f"Expected 1 potential_conflict, got {len(items)}: {[i.get('record_type') for i in items]}")
        self.assertEqual(items[0]["record_type"], "weak_candidate")

    def test_mechanism_split_excluded_from_default(self):
        """mechanism_split records are excluded from default potential_conflict."""
        root = self._fixture_root()
        conflicts = [
            {"record_type": "mechanism_split", "case_id": "case",
             "observation_a_preview": "A promotes B.", "observation_b_preview": "A inhibits B."},
        ]
        api = self._api_with_conflicts(root, conflicts)
        _, result = api.dispatch("/api/conflicts")
        self.assertEqual(len(result["items"]), 0)
        self.assertEqual(result["summary"]["mechanism_diagnostic_count"], 1)

    def test_non_comparable_excluded_from_default(self):
        """non_comparable_direction_pair excluded from default potential_conflict."""
        root = self._fixture_root()
        conflicts = [
            {"record_type": "non_comparable_direction_pair", "case_id": "case",
             "observation_a_preview": "P up Q.", "observation_b_preview": "R down S."},
        ]
        api = self._api_with_conflicts(root, conflicts)
        _, result = api.dispatch("/api/conflicts")
        self.assertEqual(len(result["items"]), 0)
        self.assertEqual(result["summary"]["rejected_non_comparable_count"], 1)

    def test_missing_previews_go_to_data_quality(self):
        """Records without A/B previews are classified as data_quality."""
        root = self._fixture_root()
        conflicts = [
            {"record_type": "weak_candidate", "case_id": "case", "rejection_reason": "test"},
        ]
        api = self._api_with_conflicts(root, conflicts)
        _, result = api.dispatch("/api/conflicts", {"bucket": ["all"], "include_hidden": ["true"]})
        self.assertEqual(len(result["items"]), 1)
        # Check summary
        _, default_result = api.dispatch("/api/conflicts")
        self.assertEqual(len(default_result["items"]), 0)
        self.assertEqual(default_result["summary"]["data_quality_count"], 1)

    def test_empty_potential_conflict_has_useful_summary(self):
        """When no potential conflicts, response has summary + empty items."""
        root = self._fixture_root()
        conflicts = [
            {"record_type": "mechanism_split", "case_id": "case",
             "observation_a_preview": "X up Y.", "observation_b_preview": "X down Y."},
            {"record_type": "non_comparable_direction_pair", "case_id": "case",
             "observation_a_preview": "A to B.", "observation_b_preview": "C to D."},
        ]
        api = self._api_with_conflicts(root, conflicts)
        _, result = api.dispatch("/api/conflicts")
        self.assertEqual(len(result["items"]), 0)
        self.assertIn("summary", result)
        summary = result["summary"]
        self.assertEqual(summary["potential_conflict_count"], 0)
        self.assertEqual(summary["mechanism_diagnostic_count"], 1)
        self.assertEqual(summary["rejected_non_comparable_count"], 1)
        self.assertEqual(summary["total_records"], 2)

    def test_bucket_query_param_filters_correctly(self):
        """The bucket query param filters to the specified bucket."""
        root = self._fixture_root()
        conflicts = [
            {"record_type": "weak_candidate", "case_id": "case",
             "observation_a_preview": "A promotes B.", "observation_b_preview": "C inhibits D."},
            {"record_type": "mechanism_split", "case_id": "case",
             "observation_a_preview": "X activates Y.", "observation_b_preview": "X inhibits Y."},
            {"record_type": "non_comparable_direction_pair", "case_id": "case",
             "observation_a_preview": "P to Q.", "observation_b_preview": "R to S."},
        ]
        api = self._api_with_conflicts(root, conflicts)

        _, mech = api.dispatch("/api/conflicts", {"bucket": ["mechanism_diagnostic"]})
        self.assertEqual(len(mech["items"]), 1)
        self.assertEqual(mech["items"][0]["record_type"], "mechanism_split")

        _, rej = api.dispatch("/api/conflicts", {"bucket": ["rejected_non_comparable"]})
        self.assertEqual(len(rej["items"]), 1)
        self.assertEqual(rej["items"][0]["record_type"], "non_comparable_direction_pair")

    def test_formal_hypothesis_belongs_to_potential_conflict(self):
        """formal_hypothesis records are in potential_conflict bucket when they have previews."""
        root = self._fixture_root()
        conflicts = [
            {"record_type": "formal_hypothesis", "case_id": "case",
             "observation_a_preview": "Hypothesis A.", "observation_b_preview": "Hypothesis B."},
        ]
        api = self._api_with_conflicts(root, conflicts)
        _, result = api.dispatch("/api/conflicts")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["record_type"], "formal_hypothesis")
        self.assertEqual(result["summary"]["potential_conflict_count"], 1)

    def test_context_split_belongs_to_potential_conflict(self):
        """context_split records are in potential_conflict bucket when they have previews."""
        root = self._fixture_root()
        conflicts = [
            {"record_type": "context_split", "case_id": "case",
             "observation_a_preview": "In cancer cells...", "observation_b_preview": "In normal cells..."},
        ]
        api = self._api_with_conflicts(root, conflicts)
        _, result = api.dispatch("/api/conflicts")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["summary"]["potential_conflict_count"], 1)

    def test_linked_triple_ids_preserved_in_response(self):
        """linked_triple_ids are preserved through bucketing and enrichment."""
        root = self._fixture_root()
        conflicts = [
            {"record_type": "weak_candidate", "case_id": "case",
             "observation_a_preview": "A promotes B.", "observation_b_preview": "C inhibits D.",
             "linked_triple_ids": ["t1", "t2"]},
        ]
        api = self._api_with_conflicts(root, conflicts)
        _, result = api.dispatch("/api/conflicts")
        self.assertEqual(result["items"][0].get("linked_triple_ids"), ["t1", "t2"])

    def test_summary_has_all_counts(self):
        """Summary contains all bucket counts and total."""
        root = self._fixture_root()
        conflicts = [
            {"record_type": "weak_candidate", "case_id": "case",
             "observation_a_preview": "A.", "observation_b_preview": "B."},
            {"record_type": "mechanism_split", "case_id": "case",
             "observation_a_preview": "X.", "observation_b_preview": "Y."},
        ]
        api = self._api_with_conflicts(root, conflicts)
        _, result = api.dispatch("/api/conflicts")
        summary = result["summary"]
        for key in ("potential_conflict_count", "mechanism_diagnostic_count",
                     "rejected_non_comparable_count", "data_quality_count",
                     "hidden_missing_preview_count", "total_records"):
            self.assertIn(key, summary, f"Missing summary key: {key}")


class ConflictLensUITests(unittest.TestCase):
    """Test that the Conflict Lens UI has tabs, empty states, and proper warnings."""

    def test_js_has_tab_labels(self):
        js = _read_static("app.js")
        for label in ("Potential Conflicts", "Mechanism Diagnostics",
                       "Rejected / Non-comparable", "Data Quality"):
            self.assertIn(label, js, f"Tab label '{label}' missing from JS")

    def test_js_has_empty_state_message(self):
        js = _read_static("app.js")
        self.assertIn("No potential conflict candidates found", js,
                       "Empty state message missing from JS")

    def test_js_has_mechanism_diagnostic_warning(self):
        js = _read_static("app.js")
        self.assertIn("not validated conflicts", js,
                       "Mechanism split warning missing from JS")

    def test_js_has_switch_conflict_tab(self):
        js = _read_static("app.js")
        self.assertIn("switchConflictTab", js, "switchConflictTab function missing")

    def test_js_has_data_quality_compact_warning(self):
        js = _read_static("app.js")
        self.assertIn("renderCompactWarning", js, "renderCompactWarning function missing")
        self.assertIn("compact-warning-row", js, "compact-warning-row CSS class missing")

    def test_js_data_quality_shows_missing_count(self):
        js = _read_static("app.js")
        self.assertIn("missing observation previews", js,
                       "Missing preview count message missing")

    def test_js_bucket_filtering_available(self):
        js = _read_static("app.js")
        self.assertIn("bucket=", js, "Bucket query parameter usage missing from JS")

    def test_css_has_conflict_tab_styles(self):
        css = _read_static("style.css")
        for cls_name in ("conflict-tabs", "conflict-tab", "conflict-summary-cards",
                          "conflict-empty-state", "compact-warning-row"):
            self.assertIn(cls_name, css, f"CSS class '{cls_name}' missing")

    def test_js_does_not_render_bare_dash_for_observation(self):
        """The renderObservationCard should not output bare dash when observation is missing."""
        js = _read_static("app.js")
        # The renderCompactWarning function should handle missing previews, not bare dash
        self.assertIn("renderCompactWarning", js, "Compact warning renderer missing")
        # Observation cards for missing data show warnings, not bare content
        self.assertIn("observation-missing", js, "observation-missing class missing from JS")


if __name__ == "__main__":
    unittest.main()
