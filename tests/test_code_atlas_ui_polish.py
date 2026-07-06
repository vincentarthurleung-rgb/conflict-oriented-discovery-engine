"""C.O.D.E. Atlas UI Polish — static verification tests.

Verifies that the layout and visual hierarchy improvements
are present in CSS, JS, and HTML without regressions.
"""
import unittest
from pathlib import Path


def _read_static(filename):
    """Read a static file from the explorer static directory."""
    p = Path("src/code_engine/system_b/explorer/static") / filename
    if not p.is_file():
        p = Path(__file__).parent.parent / "src/code_engine/system_b/explorer/static" / filename
    return p.read_text(encoding="utf-8")


class ReviewLayoutTests(unittest.TestCase):
    """Tests for review workspace grid layout and responsive design."""

    def test_css_review_workspace_uses_grid(self):
        css = _read_static("style.css")
        self.assertIn("review-workspace", css, "review-workspace CSS class missing")
        self.assertIn("grid-template-columns", css, "CSS grid layout missing for review-workspace")

    def test_css_responsive_media_queries_for_review(self):
        css = _read_static("style.css")
        # Must have responsive breakpoints
        self.assertIn("max-width:1200px", css, "1200px responsive breakpoint missing")
        self.assertIn("max-width:900px", css, "900px responsive breakpoint missing")
        # Review workspace must adapt at breakpoints
        # Verify the 1200px breakpoint adapts review layout
        self.assertTrue(
            "review-workspace" in css.split("max-width:1200px")[1].split("max-width:900px")[0]
            if "max-width:1200px" in css and "max-width:900px" in css
            else False,
            "review-workspace not adapted in 1200px breakpoint",
        )

    def test_css_metric_grid_uses_auto_fit_minmax(self):
        css = _read_static("style.css")
        self.assertIn("metric-grid", css, "metric-grid CSS class missing")
        self.assertIn("auto-fit", css, "auto-fit missing from metric grid")
        self.assertIn("minmax(180px,1fr)", css, "minmax(180px,1fr) missing from metric grid")

    def test_css_review_choice_active_states(self):
        css = _read_static("style.css")
        self.assertIn("review-choice.active", css, "review-choice.active CSS missing")
        # Data-label specific active states
        for label in ("VALID", "PARTIAL", "INVALID", "UNCLEAR"):
            self.assertIn(
                f'review-choice[data-label="{label}"].active',
                css,
                f"data-label active state missing for {label}",
            )

    def test_css_secondary_field_grid_exists(self):
        css = _read_static("style.css")
        self.assertIn("secondary-field-grid", css, "secondary-field-grid CSS missing")

    def test_css_field_control_exists(self):
        css = _read_static("style.css")
        self.assertIn("field-control", css, "field-control CSS missing")

    def test_css_detail_panel_sections_exist(self):
        css = _read_static("style.css")
        for cls_name in ("review-section", "evidence-box", "extraction-grid",
                          "judgment-button-row", "review-actions"):
            self.assertIn(cls_name, css, f"{cls_name} CSS missing")

    def test_css_compact_hero(self):
        css = _read_static("style.css")
        # Hero should have reduced padding/font compared to previous 30px padding
        self.assertIn(".hero", css, ".hero CSS missing")
        # Verify hero h1 font-size is 28px (was 30px)
        self.assertIn(".hero h1", css, ".hero h1 CSS rule missing")
        self.assertIn("font-size:28px", css, "Hero h1 font-size not reduced to 28px")
        # Hero padding should be compact
        self.assertIn("padding:28px 32px", css, "Hero padding not compact (28px 32px)")

    def test_css_no_overflow_x_on_body(self):
        css = _read_static("style.css")
        self.assertIn("overflow-x:hidden", css, "overflow-x:hidden missing on body")

    def test_css_conflict_pair_grid_uses_minmax(self):
        css = _read_static("style.css")
        self.assertIn("conflict-pair-grid", css, "conflict-pair-grid CSS missing")
        self.assertIn("minmax(0,1fr)", css, "minmax(0,1fr) missing from conflict grid")

    def test_css_case_sidebar_sticky_and_scrollable(self):
        css = _read_static("style.css")
        self.assertIn("case-review-sidebar", css, "case-review-sidebar CSS missing")
        self.assertIn("sticky", css, "sticky positioning missing")
        self.assertIn("overflow-y:auto", css, "overflow-y:auto missing on sidebar")


class JSHtmlStructureTests(unittest.TestCase):
    """Tests for JS-rendered HTML structure and naming."""

    def test_js_review_page_has_case_layer_detail_structure(self):
        js = _read_static("app.js")
        for container in ("case-review-sidebar", "review-layer-list", "review-detail-panel"):
            self.assertIn(container, js, f"{container} missing from JS review rendering")

    def test_js_review_uses_metric_grid(self):
        js = _read_static("app.js")
        self.assertIn("metric-grid", js, "metric-grid class missing from JS review rendering")

    def test_js_review_uses_judgment_button_row(self):
        js = _read_static("app.js")
        self.assertIn("judgment-button-row", js, "judgment-button-row missing from JS")

    def test_js_review_uses_secondary_field_grid(self):
        js = _read_static("app.js")
        self.assertIn("secondary-field-grid", js, "secondary-field-grid missing from JS")

    def test_js_review_uses_field_control(self):
        js = _read_static("app.js")
        self.assertIn("field-control", js, "field-control missing from JS")

    def test_js_review_uses_evidence_box(self):
        js = _read_static("app.js")
        self.assertIn("evidence-box", js, "evidence-box missing from JS")

    def test_js_review_uses_extraction_grid(self):
        js = _read_static("app.js")
        self.assertIn("extraction-grid", js, "extraction-grid missing from JS")

    def test_js_review_uses_review_section(self):
        js = _read_static("app.js")
        self.assertIn("review-section", js, "review-section missing from JS")

    def test_js_review_uses_review_actions(self):
        js = _read_static("app.js")
        self.assertIn("review-actions", js, "review-actions missing from JS")

    def test_js_review_uses_review_toolbar(self):
        js = _read_static("app.js")
        self.assertIn("review-toolbar", js, "review-toolbar missing from JS")

    def test_no_system_b_in_user_facing_files(self):
        """Neither HTML nor JS should contain 'System B' in user-visible text."""
        html = _read_static("index.html")
        js = _read_static("app.js")
        self.assertNotIn("System B", html, "System B found in HTML")
        self.assertNotIn("System B", js, "System B found in JS")

    def test_html_uses_code_atlas_branding(self):
        html = _read_static("index.html")
        self.assertIn("C.O.D.E. Atlas", html, "C.O.D.E. Atlas branding missing from HTML")

    def test_js_conflict_lens_uses_observation_side_card(self):
        js = _read_static("app.js")
        self.assertIn("observation-side-card", js, "observation-side-card missing from JS")
        self.assertIn("conflict-pair-grid", js, "conflict-pair-grid missing from JS conflict rendering")

    def test_css_graph_triple_rows_present(self):
        css = _read_static("style.css")
        for cls_name in ("triple-row", "triple-node", "triple-relation", "triple-arrow"):
            self.assertIn(cls_name, css, f"{cls_name} CSS missing for graph rows")


if __name__ == "__main__":
    unittest.main()
