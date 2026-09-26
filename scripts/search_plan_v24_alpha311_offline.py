"""Freeze alpha3.11 corpus binding and bounded lexical realization offline."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from code_engine.search.bounded_lexical_realization_v2 import (
    ACTION_MORPHOLOGY, AUTHORITY_CLASSES, ENDPOINT_LEXICON, RELATION_LEXICON,
    MAX_ALTERNATIVES_PER_ROLE, MAX_MORPHOLOGY_VARIANTS_PER_BASE,
    lexicalize_family,
)
from code_engine.search.search_constraint_allocation_v1 import (
    VARIANT_PRIORITY, burden, canonical, compile_family, digest,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_11_bounded_lexical_realization_v2_offline"
SOURCE = ROOT / "runs/20260925_search_constraint_allocation_v1_development_retrieval"
PROJECTION = ROOT / "runs/20260925_search_plan_v24_dev_search_constraint_allocation_v1_full_retrieval"
ALPHA39 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_9_search_constraint_allocation_offline"
ALPHA38 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_8_conjunctive_rigidity_autopsy_offline"
SURFACE = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline"
PLANS = SURFACE / "empirical_v3_to_surface_plan.jsonl"
EXPECTED = {
    SOURCE / "search_constraint_allocation_v1_development_retrieval_sha256": "5680fb62a1bc88259735a960823fc568f363fc0dfbe31623b723840597e231ca",
    SOURCE / "search_constraint_allocation_v1_development_acquisition_corpus_sha256": "6d632ec6e2eb156e296b073f88cb26f6a7b854dcb87e3ae063775f09222da574",
    PROJECTION / "search_plan_v24_dev_search_constraint_allocation_v1_full_retrieval_sha256": "3771887babcccfea43194e3a779205bcedf678caafc8421cd850d5d34ae2e5c7",
    PROJECTION / "search_constraint_allocation_v1_development_acquisition_corpus_sha256": "66a682b4844b63faabbb3d453d6d71241290ea07919fa4a11b7cf4552a5d8828",
    ALPHA39 / "search_plan_v24_dev_alpha3_9_sha256": "823a035ca906b67729fd8cb62b2f555a65ca787facb47d8ac3a0cc07ab76d5cb",
    ALPHA38 / "search_plan_v24_dev_alpha3_8_sha256": "768992cef210e61cfadc97e71fb658079f3ee23c32d8e72bd721c56c73eef60b",
    SURFACE / "search_plan_v24_dev_alpha3_6_sha256": "d043441e59de0c29958b1af8c935868c5f1f233b62178c2476b9a89763377cd0",
}
SCIENTIFIC_FILES = (
    "query_family_contribution_map.json", "query_execution_results.jsonl",
    "query_execution_provenance.jsonl", "case_query_hit_summary.json",
    "case_union_pmids.jsonl", "case_union_provenance.jsonl",
    "metadata_fetch_manifest.jsonl", "metadata_records.jsonl",
    "metadata_failure_records.jsonl", "candidate_gate_results.jsonl",
    "p0_results.jsonl", "p1_results.jsonl", "p2_results.jsonl",
    "policy_a_results.jsonl", "candidate_tier_summary.json",
    "oa_eligibility_results.jsonl", "selection_manifest_aggregate_sha256",
    "fulltext_fetch_manifest.jsonl", "fulltext_acquisition_results.jsonl",
    "fulltext_failure_records.jsonl", "acquired_fulltext_manifest.json",
)
NORMALIZED_PATH_FILES = {
    "query_execution_provenance.jsonl", "metadata_fetch_manifest.jsonl",
    "fulltext_fetch_manifest.jsonl", "fulltext_acquisition_results.jsonl",
    "acquired_fulltext_manifest.json",
}
CASE_IDS = tuple(f"heldout_v2_{i}" for i in range(101, 109))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write(name: str, value: Any, *, json_lines: bool = False) -> None:
    path = RUN / name
    if path.exists():
        raise RuntimeError(f"refusing existing output: {name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if json_lines:
        path.write_bytes(b"".join(canonical(row) + b"\n" for row in value))
    else:
        path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_manifest(run: Path, manifest_name: str, root_key: str, expected: str) -> dict[str, Any]:
    manifest = load(run / manifest_name)
    pairs = manifest["aggregate_components"]
    if any(sha(run / name) != value for name, value in pairs) or digest(pairs) != expected or manifest[root_key] != expected:
        raise RuntimeError(f"frozen root mismatch: {run / manifest_name}")
    return manifest


def verify_roots() -> dict[str, Any]:
    for path, expected in EXPECTED.items():
        if path.read_text(encoding="utf-8").strip() != expected:
            raise RuntimeError(f"root file drift: {path}")
    verify_manifest(SOURCE, "validation.json", "root_sha256", EXPECTED[SOURCE / "search_constraint_allocation_v1_development_retrieval_sha256"])
    verify_manifest(SOURCE, "search_constraint_allocation_v1_development_acquisition_corpus_manifest.json", "corpus_sha256", EXPECTED[SOURCE / "search_constraint_allocation_v1_development_acquisition_corpus_sha256"])
    verify_manifest(PROJECTION, "validation.json", "search_plan_v24_dev_search_constraint_allocation_v1_full_retrieval_sha256", EXPECTED[PROJECTION / "search_plan_v24_dev_search_constraint_allocation_v1_full_retrieval_sha256"])
    verify_manifest(PROJECTION, "search_constraint_allocation_v1_development_acquisition_corpus_manifest.json", "search_constraint_allocation_v1_development_acquisition_corpus_sha256", EXPECTED[PROJECTION / "search_constraint_allocation_v1_development_acquisition_corpus_sha256"])
    verify_manifest(SURFACE, "validation.json", "search_plan_v24_dev_alpha3_6_sha256", EXPECTED[SURFACE / "search_plan_v24_dev_alpha3_6_sha256"])
    # The alpha3.9/3.8 roots use different, pre-existing manifest layouts.
    for run, name in ((ALPHA39, "search_plan_v24_dev_alpha3_9_sha256"), (ALPHA38, "search_plan_v24_dev_alpha3_8_sha256")):
        expected = EXPECTED[run / name]
        validation = load(run / "validation.json")
        pairs = validation.get("aggregate_components")
        if pairs is not None and (any(sha(run / p) != v for p, v in pairs) or digest(pairs) != expected):
            raise RuntimeError(f"upstream component drift: {run}")
        if run == ALPHA39:
            files = {p.name: sha(p) for p in sorted(run.iterdir()) if p.is_file() and p.name != name}
            if digest({"artifact_schema_version": "SearchPlanV24DevAlpha39FreezeV1", "files": files}) != expected:
                raise RuntimeError("alpha3.9 aggregate drift")
    return {str(path.relative_to(ROOT)): {"expected": value, "observed": path.read_text().strip(), "verified": True} for path, value in EXPECTED.items()}


def source_normalized_bytes(name: str, projection_bytes: bytes) -> bytes:
    old = (str(SOURCE.relative_to(ROOT)) + "/retrieval_assets/").encode()
    new = (str(PROJECTION.relative_to(ROOT)) + "/retrieval_assets/").encode()
    return projection_bytes.replace(new, old) if name in NORMALIZED_PATH_FILES else projection_bytes


def reconcile() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    comparison = []
    canonical_pairs = []
    for name in SCIENTIFIC_FILES + tuple(f"case_selection_manifests/{case}.json" for case in CASE_IDS):
        src = (SOURCE / name).read_bytes()
        projected = (PROJECTION / name).read_bytes()
        normalized = source_normalized_bytes(name, projected)
        equivalent = src == normalized
        comparison.append({"component": name, "source_sha256": hashlib.sha256(src).hexdigest(), "projection_sha256": hashlib.sha256(projected).hexdigest(), "comparison_mode": "source_path_normalized" if name in NORMALIZED_PATH_FILES else "byte_identical", "equivalent": equivalent})
        canonical_pairs.append([name, hashlib.sha256(src).hexdigest()])
    source_receipt = load(SOURCE / "retrieval_assets/network_events.json")
    projection_receipt = load(PROJECTION / "retrieval_assets/network_events.json")
    if len(source_receipt["events"]) != 57 or len(source_receipt["events"]) != len(projection_receipt["events"]):
        raise RuntimeError("NCBI response cardinality drift")
    old = str(SOURCE.relative_to(ROOT)) + "/retrieval_assets/"
    new = str(PROJECTION.relative_to(ROOT)) + "/retrieval_assets/"
    normalized_receipt = deepcopy({k: v for k, v in projection_receipt.items() if k not in {"source_execution_root_sha256", "new_network_requests"}})
    for event, projected_event in zip(normalized_receipt["events"], projection_receipt["events"]):
        source_ref = event.pop("source_snapshot_ref")
        if not event["snapshot_ref"].startswith(new) or source_ref != old + event["snapshot_ref"][len(new):]:
            raise RuntimeError("snapshot provenance link differs")
        event["snapshot_ref"] = source_ref
        source_bytes = (ROOT / source_ref).read_bytes()
        projected_bytes = (ROOT / projected_event["snapshot_ref"]).read_bytes()
        if source_bytes != projected_bytes or hashlib.sha256(source_bytes).hexdigest() != event["response_sha256"]:
            raise RuntimeError("raw NCBI response bytes differ")
        canonical_pairs.append(["raw_response:" + source_ref[len(old):], hashlib.sha256(source_bytes).hexdigest()])
    receipt_equal = normalized_receipt == source_receipt
    comparison.append({"component": "retrieval_assets/network_events.json", "comparison_mode": "remove projection wrapper and normalize source_snapshot_ref", "equivalent": receipt_equal, "source_event_count": len(source_receipt["events"]), "projection_event_count": len(projection_receipt["events"])})
    canonical_pairs.append(["network_receipt_semantics", digest(source_receipt)])
    for name in ("retrieval_universe_freeze.json", "selection_freeze_barrier_audit.json"):
        source = load(SOURCE / name)
        projected = load(PROJECTION / name)
        if name.startswith("retrieval_universe"):
            equivalent = source["query_count"] == projected["query_count"] == 55 and source["case_count"] == projected["case_count"] == 8 and projected["source_retrieval_universe_sha256"] == source["retrieval_universe_sha256"]
        else:
            equivalent = projected["case_manifest_components"] == source["case_manifest_components"] and projected["source_retrieval_universe_sha256"] == source["retrieval_universe_sha256"] and projected["source_selection_barrier_sha256"] == sha(SOURCE / name) and source["selection_freeze_barrier_pass"] and projected["selection_freeze_barrier_pass"]
        comparison.append({"component": name, "comparison_mode": "root-binding correspondence", "equivalent": equivalent, "source_sha256": sha(SOURCE / name), "projection_sha256": sha(PROJECTION / name)})
    all_ok = all(x["equivalent"] for x in comparison)
    binding = {"artifact_schema_version": "CanonicalSearchConstraintAllocationV1ScientificCorpusBindingV1", "scientific_payload_equivalent": all_ok, "canonical_search_constraint_allocation_v1_scientific_corpus_sha256": digest(canonical_pairs) if all_ok else None, "aggregate_algorithm": "sha256(canonical ordered [logical component, source-normalized sha256] pairs)", "canonical_components": canonical_pairs if all_ok else [], "source_retrieval_root_sha256": EXPECTED[SOURCE / "search_constraint_allocation_v1_development_retrieval_sha256"], "verified_projection_root_sha256": EXPECTED[PROJECTION / "search_plan_v24_dev_search_constraint_allocation_v1_full_retrieval_sha256"], "neither_historical_root_replaced": True}
    source_files = {str(p.relative_to(SOURCE)): sha(p) for p in SOURCE.rglob("*") if p.is_file()}
    projection_files = {str(p.relative_to(PROJECTION)): sha(p) for p in PROJECTION.rglob("*") if p.is_file()}
    differing = sorted(set(source_files) & set(projection_files) - {k for k in set(source_files) & set(projection_files) if source_files[k] == projection_files[k]})
    difference = {"artifact_schema_version": "AggregateRootDifferenceExplanationV1", "source_root_sha256": binding["source_retrieval_root_sha256"], "projection_root_sha256": binding["verified_projection_root_sha256"], "source_file_count": len(source_files), "projection_file_count": len(projection_files), "common_path_changed_sha256": differing, "source_only_files": sorted(set(source_files) - set(projection_files)), "projection_only_files": sorted(set(projection_files) - set(source_files)), "observed_difference_classes": ["run-path references in provenance manifests", "independently recomputed retrieval-universe and acquisition aggregate roots", "replay and verification wrapper files", "source-only network-run verification wrappers", "projection-only reporting and compliance wrappers"], "scientific_payload_equivalent": all_ok, "no_reason_inferred_from_uninspected_content": True}
    audit = {"artifact_schema_version": "SourceVerifiedCopyEquivalenceAuditV1", "scientific_payload_equivalent": all_ok, "components_compared": len(comparison), "raw_ncbi_responses_byte_identical": True, "raw_ncbi_response_count": len(source_receipt["events"]), "source_root_verified": True, "projection_root_verified": True, "canonical_binding_created": all_ok}
    return audit, {"artifact_schema_version": "ScientificPayloadComponentComparisonV1", "components": comparison, "all_equivalent": all_ok}, difference, binding


def _roles(node: dict[str, Any]) -> set[str]:
    kind = node["node_type"]
    if kind in {"AND_GROUP", "OR_GROUP"}:
        return set().union(*(_roles(c) for c in node["children"]))
    return set(node.get("semantic_roles", []))


def family_rows_from_contributions(contributions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    families: dict[tuple[str, str], dict[str, Any]] = {}
    for item in contributions:
        key = (item["case_id"], item["surface_plan_id"])
        family = families.setdefault(key, {
            "artifact_schema_version": "EmpiricalLexicalizedQueryFamilyV2",
            "case_id": item["case_id"],
            "surface_plan_id": item["surface_plan_id"],
            "intent_type": item["intent_type"],
            "relation_core_sha256": item["relation_core_sha256"],
            "search_constraint_allocation_certificate_sha256": digest(item["search_constraint_allocation_certificate"]),
            "variants": [],
        })
        family["variants"].append({
            "variant_class": item["variant_class"], "query_id": item["query_id"],
            "query_sha256": item["query_sha256"], "ast_sha256": item["ast_sha256"],
            "minimum_relational_evidence_certificate_sha256": digest(item["minimum_relational_retrieval_evidence_certificate"]),
            "lexical_alternative_set_ids": item["lexical_alternative_set_ids"],
        })
    if len(families) != 29 or any(tuple(VARIANT_PRIORITY.index(v["variant_class"]) for v in f["variants"]) != tuple(sorted(VARIANT_PRIORITY.index(v["variant_class"]) for v in f["variants"])) for f in families.values()):
        raise RuntimeError("lexicalized family structure mismatch")
    return list(families.values())


def compile_offline(plans: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    families = [lexicalize_family(plan) for plan in plans]
    alternative_sets = [item for family in families for _, item in sorted(family["role_sets"].items())]
    alternative_sets = list({item["lexical_alternative_set_id"]: item for item in alternative_sets}.values())
    cert_rows, ast_rows, contribution_rows = [], [], []
    unique_by_case: dict[str, dict[bytes, dict[str, Any]]] = defaultdict(dict)
    baseline_by_case: dict[str, dict[bytes, list[int]]] = defaultdict(dict)
    new_role_counts: dict[tuple[str, bytes], list[int]] = {}
    for plan, family in zip(plans, families):
        baseline = compile_family(plan)
        for member, old in zip(family["members"], baseline["members"]):
            case = family["case_id"]
            query = member["query"]
            query_bytes = query.encode("utf-8")
            qid = "v24blrv2q:" + hashlib.sha256(query_bytes).hexdigest()
            cert = {**member["lexical_coverage_certificate"], "query_id": qid}
            cert_rows.append(cert)
            ast_rows.append({"case_id": case, "surface_plan_id": family["surface_plan_id"], "intent_type": family["intent_type"], "variant_class": member["variant_class"], "query_id": qid, "ast": member["ast"], "lexical_alternative_set_ids": member["ast"]["lexical_alternative_set_ids"]})
            contribution = {"case_id": case, "surface_plan_id": family["surface_plan_id"], "intent_type": family["intent_type"], "variant_class": member["variant_class"], "query_id": qid, "query_sha256": hashlib.sha256(query_bytes).hexdigest(), "query": query, "relation_core_sha256": plan["source_relation_core_sha256"], "search_constraint_allocation_certificate": family["allocation"], "minimum_relational_retrieval_evidence_certificate": member["certificate"], "lexical_alternative_set_ids": member["ast"]["lexical_alternative_set_ids"], "lexical_coverage_certificate": cert, "ast_sha256": member["ast"]["ast_sha256"]}
            contribution_rows.append(contribution)
            entry = unique_by_case[case].setdefault(query_bytes, {"case_id": case, "query_id": qid, "query_sha256": contribution["query_sha256"], "query": query, "contributions": []})
            entry["contributions"].append({"surface_plan_id": family["surface_plan_id"], "intent_type": family["intent_type"], "variant_class": member["variant_class"], "relation_core_sha256": plan["source_relation_core_sha256"], "allocation_certificate_sha256": digest(family["allocation"]), "minimum_relational_evidence_certificate_sha256": digest(member["certificate"]), "lexical_coverage_certificate_sha256": digest(cert), "ast_sha256": member["ast"]["ast_sha256"]})
            used = sorted(_roles(member["ast"]["root"]))
            new_counts = [len(family["role_sets"][role]["alternatives"]) for role in used]
            existing = new_role_counts.setdefault((case, query_bytes), new_counts)
            if existing != new_counts:
                raise RuntimeError("deduplicated query has inconsistent lexical coverage")
            old_used = sorted(_roles(old["ast"]["root"]))
            old_counts = [len(plan["surface_roles"].get(role, plan["external_contexts"].get(role, []))) for role in old_used]
            baseline_by_case[case].setdefault(old["query"].encode(), old_counts)
    unique_rows = [row for case in sorted(unique_by_case) for row in unique_by_case[case].values()]
    baseline_counts = [n for case in sorted(baseline_by_case) for vals in baseline_by_case[case].values() for n in vals]
    new_counts = [n for vals in new_role_counts.values() for n in vals]
    if len(contribution_rows) != 63 or len(unique_rows) != 55 or len(new_counts) != len(baseline_counts) or any(len(v) > 12 for v in unique_by_case.values()):
        raise RuntimeError("query-family cardinality or budget regression")
    write("lexical_alternative_sets.jsonl", alternative_sets, json_lines=True)
    write("lexical_coverage_certificates.jsonl", cert_rows, json_lines=True)
    write("empirical_lexicalized_query_family.jsonl", family_rows_from_contributions(contribution_rows), json_lines=True)
    write("empirical_lexicalized_ast.jsonl", ast_rows, json_lines=True)
    write("empirical_serialized_queries.jsonl", contribution_rows, json_lines=True)
    write("search_plan_v24_dev_bounded_lexical_realization_v2_query_set.jsonl", unique_rows, json_lines=True)
    query_sha = sha(RUN / "search_plan_v24_dev_bounded_lexical_realization_v2_query_set.jsonl")
    (RUN / "search_plan_v24_dev_bounded_lexical_realization_v2_query_set_sha256").write_text(query_sha + "\n")
    coverage = {"artifact_schema_version": "LexicalCoverageDeltaV2", "alpha3_8_single_surface_role_occurrences": 153, "alpha3_8_role_occurrences": 170, "alpha3_9_same_family_single_surface_role_occurrences": sum(n == 1 for n in baseline_counts), "alpha3_9_same_family_role_occurrences": len(baseline_counts), "new_single_surface_role_occurrences": sum(n == 1 for n in new_counts), "new_role_occurrences": len(new_counts), "new_single_surface_role_fraction": round(sum(n == 1 for n in new_counts) / len(new_counts), 6), "same_family_single_surface_reduction": sum(n == 1 for n in baseline_counts) - sum(n == 1 for n in new_counts), "alpha3_8_absolute_count_not_directly_comparable_due_to_query_family_size": True, "retrieval_outcomes_not_inspected_for_query_design": True}
    write("lexical_coverage_delta.json", coverage)
    write("query_deduplication_audit.json", {"artifact_schema_version": "LexicalQueryDeduplicationAuditV2", "relation_contribution_count": len(contribution_rows), "byte_unique_query_count": len(unique_rows), "per_case_unique_query_count": {case: len(v) for case, v in sorted(unique_by_case.items())}, "max_queries_per_target": 12, "query_budget_pass": True, "deduplication_scope": "within_case_byte_exact", "source_contributions_preserved": True})
    return {"families": families, "alternative_sets": alternative_sets, "contributions": contribution_rows, "unique_rows": unique_rows, "query_sha": query_sha, "coverage": coverage}, {"baseline_counts": baseline_counts, "new_counts": new_counts}


def main() -> None:
    if RUN.exists():
        raise RuntimeError(f"refusing existing alpha3.11 run: {RUN}")
    verified = verify_roots()
    protected = {str(p.relative_to(ROOT)): sha(p) for p in list(EXPECTED) + [PLANS, ALPHA39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl", SOURCE / "validation.json", PROJECTION / "validation.json"]}
    equivalence, comparison, root_diff, binding = reconcile()
    if not equivalence["scientific_payload_equivalent"]:
        raise RuntimeError("scientific corpus equivalence failed; lexical compilation prohibited")
    plans = rows(PLANS)
    if len(plans) != 29 or len({p["case_id"] for p in plans}) != 8:
        raise RuntimeError("frozen Planner V3 plan corpus mismatch")
    RUN.mkdir(parents=True)
    write("upstream_root_verification.json", {"artifact_schema_version": "Alpha311UpstreamRootVerificationV1", "roots": verified, "verified": True})
    write("source_verified_copy_equivalence_audit.json", equivalence)
    write("scientific_payload_component_comparison.json", comparison)
    write("aggregate_root_difference_explanation.json", root_diff)
    write("canonical_scientific_corpus_binding.json", binding)
    write("bounded_lexical_realization_v2_contract.json", {"artifact_schema_version": "BoundedLexicalRealizationV2", "defined": True, "purpose": "bounded textual realization without changing scientific target or allocation", "source_planner": "frozen Planner V3", "relation_core_semantics": "frozen", "search_constraint_allocation": "V1 unchanged", "query_family": "RelationalQueryFamilyV3 unchanged", "retrieval_or_relevance_authority": False, "case_specific_rules": 0})
    write("lexical_authority_class_contract.json", {"artifact_schema_version": "LexicalAuthorityClassContractV2", "allowed_classes": AUTHORITY_CLASSES, "unresolved_executable": False, "entity_alternatives_only_from": ["CANONICAL_SURFACE", "AUTHORIZED_ALIAS", "VALIDATED_PLANNER_SURFACE"], "paper_derived_alternatives": False, "source_origin_mapping": {"CANONICAL_TARGET_SURFACE": "CANONICAL_SURFACE", "VALIDATED_PLANNER_V3_LEXICAL_PROPOSAL": "VALIDATED_PLANNER_SURFACE", "VALIDATED_RELATION_CORE_EVIDENCE": "VALIDATED_PLANNER_SURFACE", "VALIDATED_EXTERNAL_CONTEXT": "VALIDATED_PLANNER_SURFACE"}})
    write("deterministic_morphology_contract.json", {"artifact_schema_version": "DeterministicMorphologyContractV2", "method": "explicit generic whitelist", "max_variants_per_base": MAX_MORPHOLOGY_VARIANTS_PER_BASE, "unrestricted_stemming": False, "fuzzy_matching": False, "identity_promotion": False, "semantic_role_change": False, "action_morphology": ACTION_MORPHOLOGY})
    write("relation_lexicon_v2.json", {"artifact_schema_version": "RelationLexiconV2", "families": RELATION_LEXICON, "polarity_preserved": True, "class_to_class_synonym_inference": False, "case_specific_phrases": 0, "excluded_unvalidated_classes": ["ACTIVATE", "INHIBIT", "RESISTANCE_UP", "RESISTANCE_DOWN", "SECRETION_UP", "ACCUMULATION_UP"]})
    write("endpoint_lexicon_v2.json", {"artifact_schema_version": "EndpointLexiconV2", "grammatical_pairs": ENDPOINT_LEXICON, "generic_autophagy_for_flux": False, "generic_activation_for_phosphorylation": False, "generic_expression_for_surface_expression": False, "generic_therapeutic_response_for_sensitivity": False})
    write("lexical_budget_policy.json", {"artifact_schema_version": "LexicalBudgetPolicyV2", "max_alternatives_per_semantic_role": MAX_ALTERNATIVES_PER_ROLE, "max_morphology_variants_per_base": MAX_MORPHOLOGY_VARIANTS_PER_BASE, "max_queries_per_target": 12, "or_groups_within_role": True, "cross_product_query_multiplication": False, "ATM_global_fallback": False, "hit_count_tuning": False})
    compiled, counts = compile_offline(plans)
    families = compiled["families"]
    identity_safe = all(item["canonical_target_link"] == plan["source_target_sha256"] and item["source_provenance"]["canonical_identity_promoted"] is False for plan, family in zip(plans, families) for set_ in family["role_sets"].values() for item in set_["alternatives"])
    sources_authorized = all(item["authority_class"] in AUTHORITY_CLASSES[:-1] and (item["derived_from"] is None or item["surface"] in ACTION_MORPHOLOGY.get(item["derived_from"], ()) or item["surface"] in ENDPOINT_LEXICON.get(item["derived_from"], ()) or any(item["surface"] in forms for family in RELATION_LEXICON.values() for base, forms in family.items() if base == item["derived_from"])) for family in families for set_ in family["role_sets"].values() for item in set_["alternatives"])
    if not identity_safe or not sources_authorized:
        raise RuntimeError("identity or lexical whitelist violation")
    write("identity_safety_audit.json", {"artifact_schema_version": "LexicalIdentitySafetyAuditV2", "identity_safety_pass": identity_safe, "new_scientific_identity_count": 0, "identity_promotion_count": 0, "tnf_to_tnf_alpha_promotion": False, "rptor_to_mtorc1_promotion": False, "entity_roles_have_no_generated_morphology": True})
    write("semantic_broadening_audit.json", {"artifact_schema_version": "LexicalSemanticBroadeningAuditV2", "semantic_broadening_count": 0, "whitelist_verified": sources_authorized, "direction_inversion": False, "generic_autophagy_replaces_flux": False, "generic_expression_replaces_surface_expression": False, "generic_therapy_response_replaces_sensitivity": False, "biological_unit_broadening": False})
    allocations_same = all(f["allocation"] == compile_family(p)["allocation"] for p, f in zip(plans, families))
    variants_same = all(tuple(m["variant_class"] for m in f["members"]) == tuple(m["variant_class"] for m in compile_family(p)["members"]) for p, f in zip(plans, families))
    therapy = all("THERAPY" in m["certificate"]["relation_internal_roles"] for f in families for m in f["members"] if "THERAPY" in f["allocation"]["relation_internal_roles"])
    conditioning = all("CONDITIONING_TREATMENT" in m["certificate"]["relation_internal_roles"] for f in families for m in f["members"] if "CONDITIONING_TREATMENT" in f["allocation"]["relation_internal_roles"])
    endpoint = all("DEFINING_ENDPOINT_PROPERTY" in m["certificate"]["search_required_roles"] for f in families for m in f["members"])
    if not all((allocations_same, variants_same, therapy, conditioning, endpoint)):
        raise RuntimeError("scientific allocation or internality regression")
    write("search_constraint_allocation_immutability_audit.json", {"artifact_schema_version": "SearchConstraintAllocationImmutabilityAuditV2", "unchanged": allocations_same, "semantic_allocations_unchanged": True, "lexical_validation_surface_hash_projection_only": True})
    write("query_family_immutability_audit.json", {"artifact_schema_version": "QueryFamilyImmutabilityAuditV2", "variant_semantics_unchanged": variants_same, "variant_priority": VARIANT_PRIORITY, "relation_contribution_count": 63, "therapy_internality_preserved": therapy, "nested_conditioning_internality_preserved": conditioning, "endpoint_internality_preserved": endpoint})
    prior = load(ALPHA39 / "v23_exact_surfacev2_alpha39_rigidity_comparison.json")
    new_burdens = [burden(m["ast"]) for f in families for m in f["members"]]
    structural = {"artifact_schema_version": "FiveArchitectureStructuralComparisonV2", "method_limit": "offline structural only; historical query grammars not all role-comparable; no retrieval prediction", "v23": prior["v23"], "exact": prior["exact"], "surface_v2": prior["surface_v2"], "alpha39": prior["alpha39"], "alpha311": {"query_count": len(compiled["unique_rows"]), "relation_contribution_count": len(compiled["contributions"]), "single_surface_role_occurrences": compiled["coverage"]["new_single_surface_role_occurrences"], "role_occurrences": compiled["coverage"]["new_role_occurrences"], "mean_mandatory_lexical_atom_count": round(sum(b["mandatory_unique_lexical_atom_count"] for b in new_burdens)/len(new_burdens), 4), "mean_mandatory_semantic_role_count": round(sum(b["mandatory_semantic_role_count"] for b in new_burdens)/len(new_burdens), 4), "relation_bearing_contributions": len(new_burdens), "mandatory_external_context_contributions": sum(bool(b["mandatory_external_context_roles"]) for b in new_burdens), "variant_structure": dict(Counter(c["variant_class"] for c in compiled["contributions"]))}, "precision_or_recall_inference": False}
    write("five_architecture_structural_comparison.json", structural)
    protected_after = {str(p.relative_to(ROOT)): sha(p) for p in list(EXPECTED) + [PLANS, ALPHA39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl", SOURCE / "validation.json", PROJECTION / "validation.json"]}
    preservation = protected == protected_after
    write("historical_corpus_preservation_audit.json", {"artifact_schema_version": "HistoricalCorpusPreservationAuditV2", "historical_assets_modified": not preservation, "protected_sha256_before": protected, "protected_sha256_after": protected_after})
    write("candidate_content_blinding_audit.json", {"artifact_schema_version": "CandidateContentBlindingAuditV2", "metadata_or_fulltext_content_used_for_query_design": False, "candidate_content_reads_for_query_design": 0, "raw_bytes_hashed_only_for_equivalence": True, "known_pmid_checks": 0, "historical_label_reads": 0, "relevance_adjudications": 0})
    write("planner_immutability_audit.json", {"artifact_schema_version": "PlannerImmutabilityAuditV2", "source_plans_sha256_before": protected[str(PLANS.relative_to(ROOT))], "source_plans_sha256_after": protected_after[str(PLANS.relative_to(ROOT))], "planner_calls": 0, "planner_outputs_modified": False})
    write("scientific_state_safety_audit.json", {"artifact_schema_version": "ScientificStateSafetyAuditV2", "scientific_targets_modified": False, "relation_cores_modified": False, "SearchConstraintAllocationV1_modified": False, "P0_P1_P2_Policy_A_modified": False, "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0, "relevance_adjudication_calls": 0})
    valid = all((equivalence["scientific_payload_equivalent"], preservation, identity_safe, sources_authorized, allocations_same, variants_same, therapy, conditioning, endpoint, compiled["coverage"]["same_family_single_surface_reduction"] > 0))
    recommendation = "PREREGISTER_BOUNDED_LEXICAL_REALIZATION_V2_RETRIEVAL" if valid else "LEXICAL_REALIZATION_V2_INSUFFICIENT"
    summary = {"artifact_schema_version": "SearchPlanV24DevAlpha311SummaryV1", "status": "completed" if valid else "failed", "scientific_payload_equivalence_verified": equivalence["scientific_payload_equivalent"], "canonical_scientific_corpus_bound": binding["canonical_search_constraint_allocation_v1_scientific_corpus_sha256"] is not None, "canonical_search_constraint_allocation_v1_scientific_corpus_sha256": binding["canonical_search_constraint_allocation_v1_scientific_corpus_sha256"], "bounded_lexical_realization_v2_defined": True, "previous_single_surface_role_occurrences": 153, "new_single_surface_role_occurrences": compiled["coverage"]["new_single_surface_role_occurrences"], "new_role_occurrences": compiled["coverage"]["new_role_occurrences"], "same_family_single_surface_reduction": compiled["coverage"]["same_family_single_surface_reduction"], "relation_contribution_count": 63, "byte_unique_query_count": 55, "search_constraint_allocation_changed": False, "query_family_semantics_changed": False, "new_scientific_identity_count": 0, "identity_promotion_count": 0, "semantic_broadening_count": 0, "therapy_internality_preserved": therapy, "nested_conditioning_internality_preserved": conditioning, "endpoint_internality_preserved": endpoint, "candidate_content_reads_for_query_design": 0, "known_pmid_checks": 0, "new_query_set_created": True, "search_plan_v24_dev_bounded_lexical_realization_v2_query_set_sha256": compiled["query_sha"], "next_stage_recommendation": recommendation, "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0, "historical_assets_modified": not preservation}
    write("summary.json", summary)
    if not valid:
        raise RuntimeError("alpha3.11 safety validation failed closed")
    files = sorted(p for p in RUN.rglob("*") if p.is_file() and p.name not in {"validation.json", "search_plan_v24_dev_alpha3_11_sha256"})
    pairs = [[str(p.relative_to(RUN)), sha(p)] for p in files]
    root_hash = digest(pairs)
    write("validation.json", {"artifact_schema_version": "SearchPlanV24DevAlpha311ValidationV1", "valid": True, "aggregate_components": pairs, "search_plan_v24_dev_alpha3_11_sha256": root_hash, "checks": {"corpus_equivalence": True, "canonical_binding": True, "safe_lexical_expansion": True, "query_budget": True, "historical_preservation": True}})
    (RUN / "search_plan_v24_dev_alpha3_11_sha256").write_text(root_hash + "\n")
    print(json.dumps({**summary, "search_plan_v24_dev_alpha3_11_sha256": root_hash}, sort_keys=True))


def complete_missing_family_draft() -> None:
    """Correct only this turn's known incomplete alpha3.11 packaging draft."""
    old_root = "778e2fe7ecb469fad463b86f8c46af016490b64798978063fa6fd258959e7301"
    root_file = RUN / "search_plan_v24_dev_alpha3_11_sha256"
    missing = RUN / "empirical_lexicalized_query_family.jsonl"
    validation_path = RUN / "validation.json"
    if not RUN.is_dir() or not root_file.is_file() or root_file.read_text().strip() != old_root or missing.exists():
        raise RuntimeError("not the known incomplete alpha3.11 draft")
    validation = load(validation_path)
    old_pairs = validation["aggregate_components"]
    if validation["search_plan_v24_dev_alpha3_11_sha256"] != old_root or digest(old_pairs) != old_root or any(sha(RUN / name) != value for name, value in old_pairs):
        raise RuntimeError("draft components drifted")
    write("empirical_lexicalized_query_family.jsonl", family_rows_from_contributions(rows(RUN / "empirical_serialized_queries.jsonl")), json_lines=True)
    files = sorted(p for p in RUN.rglob("*") if p.is_file() and p.name not in {"validation.json", "search_plan_v24_dev_alpha3_11_sha256"})
    pairs = [[str(p.relative_to(RUN)), sha(p)] for p in files]
    root_hash = digest(pairs)
    validation["aggregate_components"] = pairs
    validation["search_plan_v24_dev_alpha3_11_sha256"] = root_hash
    validation_path.write_text(json.dumps(validation, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    root_file.write_text(root_hash + "\n", encoding="utf-8")
    print(json.dumps({"draft_packaging_completed": True, "family_count": len(rows(missing)), "search_plan_v24_dev_alpha3_11_sha256": root_hash}, sort_keys=True))


if __name__ == "__main__":
    if sys.argv[1:] == ["--complete-draft"]:
        complete_missing_family_draft()
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("unsupported argument")
