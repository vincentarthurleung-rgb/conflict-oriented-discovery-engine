"""Offline alpha2.3 role and safety regressions; no provider or retrieval calls."""

from copy import deepcopy
import json
from pathlib import Path

from code_engine.search.alpha2_linked_relation_v1 import search_only_eligibility_v1_1
from code_engine.search.context_role_ontology_v1 import (
    assess_linked_relation_v1_2, conditioning_context_applicability,
    context_role_mapping, linked_relation_search_only_eligibility_v1_2,
    therapy_context_applicability,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_planner_v2_smoke_101/planner_v2_raw_payload.json"
TARGETS = ROOT / "runs/20260918_search_plan_v24_dev_planner_authority_contract_split_offline/validated_development_plans.jsonl"


def target(case_id: str) -> dict:
    for line in TARGETS.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["case_id"] == case_id:
            return row["validated_plan"]["canonical_proposition"]["target_payload"]
    raise AssertionError(case_id)


def candidate() -> tuple[dict, dict[str, dict]]:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))["parsed_provider_payload"]
    intent = payload["retrieval_intents"][0]
    link = deepcopy(intent["candidate_query_blueprints"][0]["linked_relation_candidates"][0])
    return link, {c["concept_id"]: deepcopy(c) for c in intent["search_concepts"]}


def test_egf_primary_action_not_conditioning():
    t = target("heldout_v2_101")
    assert conditioning_context_applicability(t)["state"] == "NOT_APPLICABLE"
    treatment = [r for r in context_role_mapping(t)["roles"] if r["surface"] == "EGF stimulation"]
    assert len(treatment) == 1 and treatment[0]["role"] == "PRIMARY_INTERVENTION_ACTION"


def test_egf_empty_conditioning_ref_is_valid():
    link, types = candidate()
    assert link["conditioning_context_refs"] == []
    assert assess_linked_relation_v1_2(link, target("heldout_v2_101"), types)["state"] == "STRUCTURALLY_BOUND"


def test_lps_conditioning_required():
    t = target("heldout_v2_106")
    result = conditioning_context_applicability(t)
    assert result["state"] == "REQUIRED" and result["required_surfaces"] == ["LPS stimulation"]
    assert result["source_rows"][0]["role"] == "CONDITIONING_TREATMENT"


def test_required_lps_cannot_be_empty():
    link, types = candidate()
    t = target("heldout_v2_101")
    t["context_qualifier_dimensions"]["treatment_context"] = ["LPS stimulation"]
    assert conditioning_context_applicability(t)["state"] == "REQUIRED"
    assert not assess_linked_relation_v1_2(link, t, types)["checks"]["required_conditioning_context"]


def test_distinct_lps_ref_can_satisfy_context_when_phrase_contains_full_anchor():
    link, types = candidate()
    t = target("heldout_v2_101")
    t["context_qualifier_dimensions"]["treatment_context"] = ["LPS stimulation"]
    link["conditioning_context_refs"] = ["c_nested_egf_stimulation"]
    types["c_nested_egf_stimulation"]["canonical_anchor"] = ["LPS stimulation"]
    link["linked_relation_phrase"] += " under LPS stimulation"
    assert assess_linked_relation_v1_2(link, t, types)["checks"]["required_conditioning_context"]


def test_wrong_context_ref_cannot_be_laundered_by_phrase():
    link, types = candidate()
    t = target("heldout_v2_101")
    t["context_qualifier_dimensions"]["treatment_context"] = ["LPS stimulation"]
    link["conditioning_context_refs"] = ["c_nested_egf_stimulation"]
    link["linked_relation_phrase"] += " under LPS stimulation"
    assert not assess_linked_relation_v1_2(link, t, types)["checks"]["reference_roles"]


def test_therapy_response_roles_distinct():
    for case_id, therapy in (("heldout_v2_107", "trametinib"), ("heldout_v2_108", "temozolomide")):
        t = target(case_id)
        assert therapy_context_applicability(t)["state"] == "REQUIRED"
        assert therapy in therapy_context_applicability(t)["required_surfaces"]
        assert conditioning_context_applicability(t)["state"] == "NOT_APPLICABLE"


def test_required_therapy_ref_cannot_be_empty():
    link, types = candidate()
    t = target("heldout_v2_101")
    t["therapy"] = "trametinib"
    t["context_qualifier_dimensions"]["therapy"] = ["trametinib"]
    assert not assess_linked_relation_v1_2(link, t, types)["checks"]["required_therapy_context"]


def test_therapy_ref_requires_correct_therapy_anchor():
    link, types = candidate()
    t = target("heldout_v2_101")
    t["therapy"] = "trametinib"
    t["context_qualifier_dimensions"]["therapy"] = ["trametinib"]
    types["c_therapy"] = {"concept_type": "therapy", "canonical_anchor": ["other drug"]}
    link["therapy_context_refs"] = ["c_therapy"]
    link["linked_relation_phrase"] += " with trametinib"
    assert not assess_linked_relation_v1_2(link, t, types)["checks"]["reference_roles"]


def test_primary_intervention_ref_cannot_satisfy_therapy():
    link, types = candidate()
    t = target("heldout_v2_101")
    t["therapy"] = "trametinib"
    link["therapy_context_refs"] = [link["subject_concept_ref"]]
    checks = assess_linked_relation_v1_2(link, t, types)["checks"]
    assert not checks["reference_roles"] and not checks["primary_intervention_distinct_from_therapy"]


def test_primary_intervention_ref_cannot_satisfy_conditioning():
    link, types = candidate()
    t = target("heldout_v2_101")
    t["context_qualifier_dimensions"]["treatment_context"] = ["LPS stimulation"]
    link["conditioning_context_refs"] = [link["subject_concept_ref"]]
    checks = assess_linked_relation_v1_2(link, t, types)["checks"]
    assert not checks["reference_roles"] and not checks["primary_intervention_distinct_from_conditioning"]


def test_biological_unit_independent_requirement():
    link, types = candidate()
    link["biological_unit_context_ref"] = None
    checks = assess_linked_relation_v1_2(link, target("heldout_v2_101"), types)["checks"]
    assert not checks["required_biological_unit_context"]


def test_mtorc1_inhibition_primary_not_context():
    t = target("heldout_v2_105")
    assert conditioning_context_applicability(t)["state"] == "NOT_APPLICABLE"
    rows = context_role_mapping(t)["roles"]
    assert any(r["role"] == "PRIMARY_INTERVENTION_ACTION" and "inhibition" in r["surface"] for r in rows)


def test_unknown_same_actor_action_fails_closed():
    t = target("heldout_v2_101")
    t["context_qualifier_dimensions"]["treatment"] = ["EGF inhibition"]
    assert conditioning_context_applicability(t)["state"] == "UNRESOLVED"


def test_no_identity_promotion_and_prior_default_deny():
    link, types = candidate()
    binding = assess_linked_relation_v1_2(link, target("heldout_v2_101"), types)
    assert binding["canonical_identity_promoted"] is False
    assert linked_relation_search_only_eligibility_v1_2(link, target("heldout_v2_101"), types)[0] == "SEARCH_ONLY_EXPANSION"
    assert search_only_eligibility_v1_1("unverified proxy", "subject", target("heldout_v2_101"))[0] == "UNRESOLVED"
