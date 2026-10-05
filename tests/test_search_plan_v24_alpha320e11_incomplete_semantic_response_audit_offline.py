"""Structural-only tests for the alpha3.20E1.1 offline audit."""

from scripts.run_search_plan_v24_alpha320e11_incomplete_semantic_response_audit_offline import (
    diagnostic_transformations,
    independent_strict_json,
    structural_scan,
)


def test_structural_scan_ignores_punctuation_inside_strings() -> None:
    content = '{"x":"a,} [ \\"", "y": 1,}'
    scan = structural_scan(content)
    assert scan["trailing_commas_outside_strings"] == [
        {"position": len(content) - 2, "next_closer": "}"}]
    assert scan["unterminated_string"] is False


def test_independent_parser_rejects_invalid_original() -> None:
    assert independent_strict_json('{"x":1,}')["valid"] is False
    assert independent_strict_json('{"x":1}')["valid"] is True


def test_diagnostic_transformation_never_claims_adjudication_validity() -> None:
    content = '{"candidate_reviews":[{"x":1,},{"x":2,},{"x":3}]}'
    result = diagnostic_transformations(content, structural_scan(content))
    assert result["remove_trailing_commas_only_parseable"] is True
    assert result["diagnostic_parseability_does_not_change_e1_validity"] is True
    assert result["diagnostic_only_no_modified_content_persisted"] is True
