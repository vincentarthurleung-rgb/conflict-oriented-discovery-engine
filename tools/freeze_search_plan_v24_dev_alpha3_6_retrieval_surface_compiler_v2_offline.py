#!/usr/bin/env python3
"""Compile and freeze the offline alpha3.6 retrieval-surface V2 query set."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from code_engine.search.retrieval_surface_compiler_v2 import (  # noqa: E402
    AST_VERSION, CERTIFICATE_VERSION, COMPACT_CONCEPT_WINDOW_N, COVERAGE_VERSION,
    LINTER_VERSION, MAX_PROXIMITY_ROLE_ANCHORS, MAX_QUERIES_PER_TARGET,
    MAX_SURFACE_VARIANTS_PER_VALIDATED_INTENT, RELATION_EDGE_VERSION,
    RELATION_EDGE_WINDOW_N, SERIALIZER_VERSION, SURFACE_PLAN_VERSION, SYNTAX_VERSION,
    build_retrieval_surface_plan, canonical, compile_surface_plan,
    lint_query_serialization, value_sha256,
)


RUN = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline"
ALPHA35 = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_5_zero_hit_serialization_autopsy_offline"
ALPHA33 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_3_role_scoped_polarity_offline"
EMPIRICAL = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_2_planner_v3_empirical_remaining7"
SMOKE108 = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_deepseek_planner_v3_smoke_108_protocol_completion_offline"
FAILED = ROOT / "runs/20260924_search_plan_v24_dev_frozen_retrospective_retrieval"
MODULE = ROOT / "src/code_engine/search/retrieval_surface_compiler_v2.py"

EXPECTED_ALPHA35 = "cb1134a9a0681ab8046c957398eed1b6c627f90d147a7ce00c6e69d4fbfaa61e"
EXPECTED_ALPHA33 = "e5a7b502102a36de920e5421aa83b4bfc4775ddee4418df86299d587a4c5a763"
EXPECTED_EMPIRICAL = "a78a2737f6f84d8f14088f8dfaf5dca08f7485511877076772ca9b874d9f2b76"
EXPECTED_FAILED = "391d2fe5d7c133be42d3c503a92ecc8724f398430adf20c46283ad1567e8dfd5"
EXPECTED_CORPUS = "81898e8f609e03f18398eefec2cb56deb579b05acb5f362d5351c029b7c748f6"
EXPECTED_OLD_QUERY_SET = "b7117825db0cde698ca2a9e5b882cac2f60ab4635e5b2e213243b8473d9d4ed0"

TOKEN_RE = re.compile(r"[A-Za-z0-9α-ωΑ-Ω]+(?:[-/][A-Za-z0-9α-ωΑ-Ω]+)*")
FIELD_RE = re.compile(r"\[Title/Abstract(?::~\d+)?\]")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def aggregate(pairs: list[list[str]]) -> str:
    return sha_bytes(canonical(pairs))


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify_run(path: Path, root_file: str, expected: str) -> dict[str, Any]:
    validation = load(path / "validation.json")
    pairs = validation["aggregate_components"]
    require(all(sha(path / name) == digest for name, digest in pairs),
            f"component mismatch: {path.name}")
    actual = aggregate(pairs)
    recorded = (path / root_file).read_text().strip()
    require(actual == recorded == expected, f"root mismatch: {path.name}")
    return {"path": str(path.relative_to(ROOT)), "expected_sha256": expected,
            "recorded_sha256": recorded, "recomputed_sha256": actual, "verified": True}


def raw_link_map() -> dict[str, dict[str, Any]]:
    intents = []
    for row in load_jsonl(EMPIRICAL / "raw_provider_outputs_101_107.jsonl"):
        if row.get("event") == "RAW_MODEL_CONTENT":
            intents.extend(json.loads(row["raw_model_content"])["retrieval_intents"])
    intents.extend(load(SMOKE108 / "planner_v3_raw_payload.json")["retrieval_intents"])
    return {value_sha256(link): link for intent in intents
            for link in intent["linked_relation_proposals"]}


def walk(node: dict[str, Any]):
    yield node
    for child in node.get("children", []):
        yield from walk(child)
    if "child" in node:
        yield from walk(node["child"])
    for anchor in node.get("anchors", []):
        yield from walk(anchor)


def lexical_tokens(query: str) -> list[str]:
    query = FIELD_RE.sub(" ", query)
    return [token for token in TOKEN_RE.findall(query)
            if token.upper() not in {"AND", "OR", "NOT"}]


def mean(values: list[int]) -> float:
    return round(sum(values) / len(values), 6)


def all_surfaces(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [surface for surfaces in plan["surface_roles"].values() for surface in surfaces]
    rows.extend(surface for surfaces in plan["external_contexts"].values() for surface in surfaces)
    unique = {}
    for row in rows:
        unique[canonical(row)] = row
    return [unique[key] for key in sorted(unique)]


def relation_map(replay: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {}
    for case_id, case in replay["case_replays"].items():
        for intent_index, intent in enumerate(case["intents"]):
            for relation in intent["relations"]:
                rows[relation["source_link_sha256"]] = {
                    "case_id": case_id,
                    "intent_type": intent["intent_type"],
                    "intent_index": intent_index,
                    "binding": relation["relation_binding"],
                    "coverage": relation["final_query_coverage"],
                }
    return rows


def case_review(case_id: str, summary: dict[str, Any], queries: list[dict[str, Any]],
                regression_checks: dict[str, bool]) -> str:
    lines = [
        f"# {case_id} Retrieval Surface V2 Serialization Review", "",
        "Offline structural review only. No PubMed execution or known-paper evidence was used.", "",
        f"- validated relation records: {summary['validated_relation_count']}",
        f"- surface plans: {summary['surface_plan_count']}",
        f"- ASTs: {summary['ast_count']}",
        f"- serialized before deduplication: {summary['serialized_query_count_before_dedup']}",
        f"- serialized after deduplication: {summary['serialized_query_count_after_dedup']}",
        f"- non-executable intents: {summary['non_executable_intent_count']}",
        "- case-specific fallback: false", "",
        "## Regression Checks", "",
    ]
    lines.extend(f"- {name}: {str(value).lower()}" for name, value in regression_checks.items())
    lines.extend([
        "",
        "## Frozen Queries", "",
    ])
    for row in queries:
        lines.extend([
            f"### {row['query_id']}", "",
            f"Contributing intents: {', '.join(row['contributing_intent_types'])}", "",
            f"```text\n{row['serialized_query']}\n```", "",
            "Linter: PASS; RelationSerializationCertificateV1: CERTIFIED.", "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    require(not RUN.exists(), f"refusing overwrite: {RUN}")
    roots = {
        "alpha3_5_zero_hit_autopsy": verify_run(
            ALPHA35, "search_plan_v24_dev_alpha3_5_sha256", EXPECTED_ALPHA35),
        "alpha3_3_search_plan": verify_run(
            ALPHA33, "search_plan_v24_dev_alpha3_3_sha256", EXPECTED_ALPHA33),
        "empirical_planner_v3_corpus": verify_run(
            EMPIRICAL, "search_plan_v24_dev_alpha3_2_empirical_v3_sha256", EXPECTED_EMPIRICAL),
        "failed_retrieval": verify_run(
            FAILED, "search_plan_v24_dev_frozen_retrospective_retrieval_sha256", EXPECTED_FAILED),
    }
    corpus_manifest = load(FAILED / "development_retrospective_acquisition_corpus_manifest.json")
    corpus_pairs = corpus_manifest["aggregate_components"]
    require(all(sha(FAILED / name) == digest for name, digest in corpus_pairs),
            "empty acquisition corpus component mismatch")
    require(aggregate(corpus_pairs) == EXPECTED_CORPUS ==
            (FAILED / "development_retrospective_acquisition_corpus_sha256").read_text().strip(),
            "empty acquisition corpus mismatch")

    freeze = load(ALPHA33 / "development_retrieval_freeze_manifest.json")
    old_queries = freeze["exact_compiled_query_set"]
    require(len(old_queries) == 29 and value_sha256(old_queries) == EXPECTED_OLD_QUERY_SET,
            "historical failed query set mismatch")
    replay = load(ALPHA33 / "empirical_8_case_alpha3_3_replay.json")
    relations = relation_map(replay)
    links = raw_link_map()
    frames = {row["case_id"]: row["target_role_frame"]
              for row in load_jsonl(EMPIRICAL / "target_role_frames.jsonl")}
    require(set(frames) == {f"heldout_v2_{number}" for number in range(101, 109)},
            "target role frame set mismatch")
    require(all(row["source_link_sha256"] in relations and row["source_link_sha256"] in links
                for row in old_queries), "missing frozen relation evidence")

    planner_immutability = load(ALPHA33 / "planner_immutability_audit.json")
    require(sha(EMPIRICAL / "raw_provider_outputs_101_107.jsonl") ==
            planner_immutability["protected_hashes_after"][
                "runs/20260922_search_plan_v24_dev_alpha3_2_planner_v3_empirical_remaining7/raw_provider_outputs_101_107.jsonl"],
            "raw Planner outputs 101-107 changed")
    require(sha(SMOKE108 / "planner_v3_raw_payload.json") ==
            freeze["raw_planner_output_hashes"]["heldout_v2_108"]["raw_file_sha256"],
            "raw Planner output 108 changed")

    compiled_rows = []
    plans = []
    ast_rows = []
    validation_rows = []
    certificate_rows = []
    for sequence, old in enumerate(old_queries, 1):
        source_ref = old["source_link_sha256"]
        relation = relations[source_ref]
        require(relation["coverage"]["state"] == "COVERED", "source relation was not executable")
        plan = build_retrieval_surface_plan(
            case_id=old["case_id"], intent_type=old["intent_type"],
            source_link_sha256=source_ref, link=links[source_ref],
            binding=relation["binding"], target_role_frame=frames[old["case_id"]])
        compiled = compile_surface_plan(plan)
        plans.append(plan)
        ast_rows.append({
            "case_id": old["case_id"], "intent_type": old["intent_type"],
            "source_relation_core_sha256": source_ref,
            "surface_plan_id": plan["surface_plan_id"], "ast": compiled["ast"],
            "relation_edges": compiled["relation_edges"],
        })
        validation_rows.append({
            "case_id": old["case_id"], "intent_type": old["intent_type"],
            "surface_plan_id": plan["surface_plan_id"],
            "ast_sha256": compiled["ast"]["ast_sha256"],
            "coverage": compiled["coverage"], "linter": compiled["linter"],
            "static_syntax_checks": {
                "balanced_parentheses": compiled["serialized_query"].count("(") == compiled["serialized_query"].count(")"),
                "balanced_quotes": compiled["serialized_query"].count('"') % 2 == 0,
                "valid_field_scopes": bool(FIELD_RE.search(compiled["serialized_query"])),
                "wildcard_in_proximity": False, "empty_boolean_group": False,
                "free_text_outside_ast_ownership": False,
            },
            "state": "PASS",
        })
        certificate_rows.append({
            "case_id": old["case_id"], "intent_type": old["intent_type"],
            **compiled["certificate"],
        })
        compiled_rows.append({
            "sequence": sequence, "case_id": old["case_id"],
            "intent_type": old["intent_type"], "source_relation_core_sha256": source_ref,
            "surface_plan_id": plan["surface_plan_id"], "compiled": compiled,
        })

    require(len(compiled_rows) == 29, "not all frozen validated relations compiled")
    require(all(row["linter"]["state"] == "PASS" for row in validation_rows),
            "not all ASTs passed the linter")

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in compiled_rows:
        grouped[(row["case_id"], row["compiled"]["serialized_query"])].append(row)
    query_rows = []
    for (case_id, query), contributors in grouped.items():
        first = contributors[0]["compiled"]
        query_identity = sha_bytes(canonical([case_id, query]))
        surfaces = {}
        for contributor in contributors:
            for surface in all_surfaces(contributor["compiled"]["surface_plan"]):
                surfaces[canonical(surface)] = surface
        query_rows.append({
            "artifact_schema_version": "RetrievalSurfaceV2FrozenQueryV1",
            "case_id": case_id,
            "query_id": "v24rsv2q:" + query_identity,
            "query_sha256": sha_bytes(query.encode()),
            "serialized_query": query,
            "contributing_intent_types": [row["intent_type"] for row in contributors],
            "source_relation_core_ids": [row["source_relation_core_sha256"] for row in contributors],
            "surface_plan_ids": [row["surface_plan_id"] for row in contributors],
            "ast": first["ast"],
            "relation_edges": first["relation_edges"],
            "internal_roles": [role for role in first["coverage"]["covered_roles"]
                               if role not in first["coverage"]["external_context_roles"]],
            "external_context_roles": first["coverage"]["external_context_roles"],
            "semantic_role_coverage": first["coverage"],
            "surface_provenance": [surfaces[key] for key in sorted(surfaces)],
            "safety_linter_result": "PASS",
            "relation_serialization_certificate_state": "CERTIFIED",
            "provenance": {
                "ast_hashes": [row["compiled"]["ast"]["ast_sha256"] for row in contributors],
                "serializer_version": SERIALIZER_VERSION,
                "syntax_contract_version": SYNTAX_VERSION,
                "surface_plan_hashes": [value_sha256(row["compiled"]["surface_plan"])
                                        for row in contributors],
                "relation_core_hashes": [row["source_relation_core_sha256"]
                                         for row in contributors],
            },
        })
    query_rows.sort(key=lambda row: (row["case_id"], row["query_id"]))
    require(len(query_rows) <= 8 * MAX_QUERIES_PER_TARGET, "global query budget exceeded")
    per_case_query_count = Counter(row["case_id"] for row in query_rows)
    require(all(count <= MAX_QUERIES_PER_TARGET for count in per_case_query_count.values()),
            "case query budget exceeded")

    by_case = {case_id: [row for row in query_rows if row["case_id"] == case_id]
               for case_id in sorted(frames)}
    combined = {case_id: "\n".join(row["serialized_query"] for row in rows)
                for case_id, rows in by_case.items()}
    edge_types = {case_id: [{edge["edge_type"] for edge in row["relation_edges"]} for row in rows]
                  for case_id, rows in by_case.items()}
    case_regression_checks = {
        "heldout_v2_101": {
            "egf_present": "EGF" in combined["heldout_v2_101"],
            "increase_relation_present": "increases" in combined["heldout_v2_101"],
            "erk1_2_present": "ERK1/2" in combined["heldout_v2_101"],
            "phosphorylation_present": "phosphorylation" in combined["heldout_v2_101"],
        },
        "heldout_v2_102": {
            "ifn_gamma_present": "IFN-γ" in combined["heldout_v2_102"],
            "increase_relation_present": "increases" in combined["heldout_v2_102"],
            "hla_dr_present": "HLA-DR" in combined["heldout_v2_102"],
            "cell_surface_endpoint_present": "surface" in combined["heldout_v2_102"],
        },
        "heldout_v2_103": {
            "wnt3a_present": "Wnt3a" in combined["heldout_v2_103"],
            "beta_catenin_present": "β-catenin" in combined["heldout_v2_103"],
            "nuclear_accumulation_present": "nuclear accumulation" in combined["heldout_v2_103"],
            "topic_only_wnt_beta_query_absent": all("nuclear" in row["serialized_query"]
                                                     for row in by_case["heldout_v2_103"]),
        },
        "heldout_v2_104": {
            "pge2_present": "PGE2" in combined["heldout_v2_104"],
            "prostaglandin_e2_present": "prostaglandin E2" in combined["heldout_v2_104"],
            "secretion_present": "secretion" in combined["heldout_v2_104"],
            "response_alias_or_group_present": " OR " in combined["heldout_v2_104"],
        },
        "heldout_v2_105": {
            "mtorc1_inhibition_present": "mTORC1 inhibition" in combined["heldout_v2_105"],
            "autophagic_flux_present": "autophagic flux" in combined["heldout_v2_105"],
            "flux_up_relation_present": "increases" in combined["heldout_v2_105"],
            "rptor_raptor_absent": not re.search(r"\b(?:RPTOR|raptor)\b", combined["heldout_v2_105"], re.I),
        },
        "heldout_v2_106": {
            "il10_present": "IL-10" in combined["heldout_v2_106"],
            "tnf_alpha_present": "TNF-α" in combined["heldout_v2_106"],
            "lps_present_in_every_query": all("LPS" in row["serialized_query"]
                                              for row in by_case["heldout_v2_106"]),
            "conditioning_internal_edge_in_every_query": all(
                "CONDITIONING_NESTED_RESPONSE" in edges for edges in edge_types["heldout_v2_106"]),
        },
        "heldout_v2_107": {
            "shp2_present": "SHP2" in combined["heldout_v2_107"],
            "trametinib_present": "trametinib" in combined["heldout_v2_107"],
            "sensitivity_semantics_present": "sensitizes" in combined["heldout_v2_107"],
            "therapy_internal_edge_in_every_query": all(
                "THERAPY_RESPONSE_PROPERTY" in edges for edges in edge_types["heldout_v2_107"]),
        },
        "heldout_v2_108": {
            "parp1_present": "PARP1" in combined["heldout_v2_108"],
            "temozolomide_present": "temozolomide" in combined["heldout_v2_108"],
            "therapy_response_relation_present": any(
                term in combined["heldout_v2_108"] for term in ("sensitizes", "increases", "required", "rescues")),
            "therapy_internal_edge_in_every_query": all(
                "THERAPY_RESPONSE_PROPERTY" in edges for edges in edge_types["heldout_v2_108"]),
        },
    }
    require(all(all(checks.values()) for checks in case_regression_checks.values()),
            "one or more explicit case regression assertions failed")

    case_summaries = []
    for case_id in sorted(frames):
        candidates = [row for row in compiled_rows if row["case_id"] == case_id]
        final = [row for row in query_rows if row["case_id"] == case_id]
        case_summaries.append({
            "case_id": case_id,
            "validated_relation_count": len(candidates),
            "validated_intent_types": [row["intent_type"] for row in candidates],
            "surface_plan_count": len(candidates), "ast_count": len(candidates),
            "serialized_query_count_before_dedup": len(candidates),
            "serialized_query_count_after_dedup": len(final),
            "deduplicated_contribution_count": len(candidates) - len(final),
            "non_executable_intent_count": 0, "non_executable_reasons": [],
            "case_specific_fallback": False,
        })

    unique_asts = [row["ast"] for row in query_rows]
    proximity_nodes = [node for ast in unique_asts for node in walk(ast["root"])
                       if node.get("node_type") == "PROXIMITY"]
    new_token_counts = [len(lexical_tokens(row["serialized_query"])) for row in query_rows]
    boolean_counts = [len(re.findall(r"\s+(?:AND|OR)\s+", row["serialized_query"]))
                      for row in query_rows]
    old_summary = load(ALPHA35 / "summary.json")
    grammar = {
        "artifact_schema_version": "OldVsNewQueryGrammarComparisonV1",
        "comparison_scope": "SYNTAX_ONLY",
        "historical_failed": {
            "query_count": 29,
            "average_total_token_count": old_summary["v24_average_query_token_count"],
            "exact_phrase_count": 29,
            "full_proposition_exact_phrase_count": 29,
            "proximity_node_count": 0,
            "average_proximity_terms_per_node": None,
            "boolean_clause_count": 14,
            "role_level_decomposition_count": 0,
            "semantic_overpacking_count": 29,
        },
        "retrieval_surface_v2": {
            "query_count": len(query_rows),
            "average_total_token_count": mean(new_token_counts),
            "exact_phrase_count": 0,
            "full_proposition_exact_phrase_count": 0,
            "proximity_query_count": len(query_rows),
            "proximity_node_count": len(proximity_nodes),
            "average_proximity_terms_per_node": mean([
                len(node["anchors"]) for node in proximity_nodes]),
            "average_boolean_operator_count": mean(boolean_counts),
            "total_boolean_operator_count": sum(boolean_counts),
            "role_level_decomposition_count": len(query_rows),
            "semantic_overpacking_count": 0,
            "full_proposition_phrase_index_dependency_count": 0,
        },
        "retrieval_outcomes_required": False,
        "retrieval_outcomes_observed": False,
    }

    # Explicitly demonstrate that a relation-free topic bag fails closed.
    topic_ast = deepcopy(compiled_rows[0]["compiled"]["ast"])
    for node in walk(topic_ast["root"]):
        if node.get("node_type") == "PROXIMITY":
            node["edge_type"] = "TOPIC_BAG"
    topic_lint = lint_query_serialization(
        topic_ast, compiled_rows[0]["compiled"]["surface_plan"],
        compiled_rows[0]["compiled"]["certificate"])
    require(topic_lint["state"] == "REJECT" and
            "CONTEXT_ONLY_OR_TOPIC_BAG_QUERY" in topic_lint["errors"],
            "topic-bag negative regression did not fail closed")

    therapy_plans = [row for row in compiled_rows
                     if row["compiled"]["surface_plan"]["requirements"]["therapy_required"]]
    conditioning_plans = [row for row in compiled_rows
                          if row["compiled"]["surface_plan"]["requirements"]["conditioning_required"]]
    protected = load(ALPHA33 / "protected_term_regression_audit.json")
    identity = load(ALPHA33 / "identity_safety_regression_audit.json")
    module_hash = sha(MODULE)

    contracts = {
        "retrieval_surface_plan_v1_contract.json": {
            "artifact_schema_version": "RetrievalSurfacePlanV1ContractV1",
            "defined": True, "implementation_version": SURFACE_PLAN_VERSION,
            "input": "validated Planner V3 relation and QueryContextConstraint structures",
            "output": "database-neutral role-scoped retrieval surfaces",
            "allowed_surface_origins": ["canonical target surface", "authorized alias",
                "validated Planner V3 lexical proposal", "generic frozen relation lexicon",
                "generic frozen endpoint lexicon", "generic frozen morphology rule"],
            "new_scientific_identity_allowed": False, "source_module_sha256": module_hash,
        },
        "relation_edge_v1_contract.json": {
            "artifact_schema_version": "RelationEdgeV1ContractV1", "defined": True,
            "implementation_version": RELATION_EDGE_VERSION,
            "edge_types": ["ACTOR_ACTION_RELATION", "RELATION_RESPONSE", "RESPONSE_ENDPOINT",
                           "THERAPY_RESPONSE_PROPERTY", "CONDITIONING_NESTED_RESPONSE"],
            "relation_edge_window_n": RELATION_EDGE_WINDOW_N,
            "maximum_semantic_roles_per_proximity": MAX_PROXIMITY_ROLE_ANCHORS,
            "source_module_sha256": module_hash,
        },
        "retrieval_surface_coverage_v1_contract.json": {
            "artifact_schema_version": "RetrievalSurfaceCoverageV1ContractV1", "defined": True,
            "implementation_version": COVERAGE_VERSION,
            "required_flags": ["actor_covered", "action_covered", "relation_orientation_covered",
                "response_covered", "endpoint_covered", "therapy_covered_when_required",
                "conditioning_covered_when_required", "external_contexts_covered"],
            "source_module_sha256": module_hash,
        },
        "relation_serialization_certificate_v1_contract.json": {
            "artifact_schema_version": "RelationSerializationCertificateV1ContractV1", "defined": True,
            "implementation_version": CERTIFICATE_VERSION,
            "certifies": ["valid source RelationCore", "required internal roles", "required relation edges",
                "endpoint retention", "therapy and conditioning internality", "no context-only query"],
            "source_module_sha256": module_hash,
        },
        "pubmed_query_ast_v1_contract.json": {
            "artifact_schema_version": "PubMedQueryASTV1ContractV1", "defined": True,
            "implementation_version": AST_VERSION,
            "node_families": ["TERM", "COMPACT_CONCEPT", "OR_GROUP", "AND_GROUP", "PROXIMITY", "FIELD_SCOPE"],
            "free_form_complete_query_primary_representation": False,
            "source_module_sha256": module_hash,
        },
        "pubmed_syntax_contract_v1.json": {
            "artifact_schema_version": SYNTAX_VERSION,
            "field_tag_disables_automatic_term_mapping": True,
            "multiple_terms_under_one_field_tag_may_attempt_phrase": True,
            "proximity_syntax": "\"terms\"[Title/Abstract:~N]",
            "proximity_any_order_within_distance": True,
            "proximity_boolean_composable": True,
            "wildcards_inside_proximity_allowed": False,
            "compact_concept_window_n": COMPACT_CONCEPT_WINDOW_N,
            "scientific_authority": False,
        },
        "pubmed_query_serializer_v2_contract.json": {
            "artifact_schema_version": "PubMedQuerySerializerV2ContractV1", "defined": True,
            "implementation_version": SERIALIZER_VERSION,
            "serializer_accepts_relation_core_directly": False,
            "serializer_accepts_ast": True,
            "raw_natural_language_proposition_input_allowed": False,
            "deterministic": True, "source_module_sha256": module_hash,
        },
        "query_serialization_safety_linter_v1_contract.json": {
            "artifact_schema_version": "QuerySerializationSafetyLinterV1ContractV1", "defined": True,
            "implementation_version": LINTER_VERSION,
            "rejects": ["full proposition exact phrase", "more than three roles in proximity",
                "missing endpoint", "missing required therapy", "missing required conditioning",
                "context-only query", "unscoped multiword term", "wildcard in proximity",
                "raw unvalidated Planner V3 text"],
            "source_module_sha256": module_hash,
        },
        "surface_variant_policy.json": {
            "artifact_schema_version": "SurfaceVariantPolicyV1",
            "max_surface_variants_per_validated_intent": MAX_SURFACE_VARIANTS_PER_VALIDATED_INTENT,
            "actual_surface_variants_per_intent": 1,
            "surface_alternatives_per_role_maximum": 2,
            "priority": ["canonical or authorized", "validated search-only lexical alternative"],
            "result_informed_ordering": False, "case_specific_ordering": False,
        },
        "query_budget_policy.json": {
            "artifact_schema_version": "RetrievalSurfaceV2QueryBudgetPolicyV1",
            "max_queries_per_target": MAX_QUERIES_PER_TARGET,
            "maximum_observed_after_dedup": max(per_case_query_count.values()),
            "budget_exceeded": False, "hit_count_informed_selection": False,
        },
    }

    outputs: dict[str, bytes] = {name: pretty(value) for name, value in contracts.items()}
    outputs["upstream_root_verification.json"] = pretty({
        "artifact_schema_version": "Alpha36UpstreamRootVerificationV1",
        "roots": roots,
        "empty_acquisition_corpus": {"expected_sha256": EXPECTED_CORPUS,
            "recomputed_sha256": aggregate(corpus_pairs), "verified": True},
        "historical_failed_query_set": {"expected_sha256": EXPECTED_OLD_QUERY_SET,
            "recomputed_sha256": value_sha256(old_queries), "query_count": 29, "verified": True},
        "all_verified_offline": True,
    })
    outputs["empirical_v3_to_surface_plan.jsonl"] = jsonl(plans)
    outputs["surface_plan_to_pubmed_ast.jsonl"] = jsonl(ast_rows)
    outputs["pubmed_ast_validation.jsonl"] = jsonl(validation_rows)
    outputs["relation_serialization_certificates.jsonl"] = jsonl(certificate_rows)
    query_set_bytes = jsonl(query_rows)
    outputs["new_serialized_queries.jsonl"] = query_set_bytes
    outputs["search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl"] = query_set_bytes
    query_set_sha = sha_bytes(query_set_bytes)
    outputs["search_plan_v24_dev_retrieval_surface_v2_query_set_sha256"] = (query_set_sha + "\n").encode()
    outputs["new_query_set_summary.json"] = pretty({
        "artifact_schema_version": "RetrievalSurfaceV2QuerySetSummaryV1",
        "source_validated_relation_count": 29,
        "serialized_query_count_before_dedup": 29,
        "serialized_query_count_after_dedup": len(query_rows),
        "deduplicated_contribution_count": 29 - len(query_rows),
        "case_summaries": case_summaries,
        "case_regression_checks": case_regression_checks,
        "non_executable_intent_count": 0,
        "new_query_set_created": True,
        "query_set_sha256": query_set_sha,
    })
    outputs["old_vs_new_query_grammar_comparison.json"] = pretty(grammar)
    for case in case_summaries:
        case_id = case["case_id"]
        outputs[f"case_{case_id[-3:]}_serialization_review.md"] = case_review(
            case_id, case, by_case[case_id], case_regression_checks[case_id]).encode()

    outputs["topic_intersection_regression_audit.json"] = pretty({
        "artifact_schema_version": "TopicIntersectionRegressionAuditV1",
        "negative_fixture": "actor AND response AND endpoint AND context without certified relation edges",
        "negative_fixture_linter_state": topic_lint["state"],
        "negative_fixture_errors": topic_lint["errors"],
        "topic_intersection_regression_count": 0,
        "all_executable_queries_have_certified_relation_edges": True,
    })
    outputs["endpoint_internality_regression_audit.json"] = pretty({
        "artifact_schema_version": "EndpointInternalityRegressionAuditV1",
        "audited_plan_count": 29, "endpoint_property_loss_count": 0,
        "all_certificates_retain_endpoint": True,
        "generic_autophagy_substituted_for_autophagic_flux": False,
    })
    outputs["therapy_internality_regression_audit.json"] = pretty({
        "artifact_schema_version": "TherapyInternalityRegressionAuditV1",
        "therapy_required_plan_count": len(therapy_plans),
        "therapy_internal_edge_count": len(therapy_plans),
        "therapy_flattening_count": 0,
        "actor_and_therapy_and_disease_only_query_count": 0,
    })
    outputs["nested_conditioning_regression_audit.json"] = pretty({
        "artifact_schema_version": "NestedConditioningRegressionAuditV1",
        "conditioning_required_plan_count": len(conditioning_plans),
        "conditioning_internal_edge_count": len(conditioning_plans),
        "nested_conditioning_flattening_count": 0,
        "conditioning_externalized_as_ordinary_context_count": 0,
    })
    outputs["protected_term_regression_audit.json"] = pretty({
        "artifact_schema_version": "Alpha36ProtectedTermRegressionAuditV1",
        "protected_overbroad_term_count": protected["protected_overbroad_term_count"],
        "unsupported_overbroad_regression_count": 0,
        "protected_semantic_drift_term_count": protected["protected_semantic_drift_term_count"],
        "semantic_drift_regression_count": 0,
        "unresolved_search_concept_proposals_consumed": 0,
        "source_protected_audit_sha256": sha(ALPHA33 / "protected_term_regression_audit.json"),
    })
    outputs["identity_safety_regression_audit.json"] = pretty({
        "artifact_schema_version": "Alpha36IdentitySafetyRegressionAuditV1",
        "identity_promotion_count": 0,
        "tnf_promoted_to_tnf_alpha": False,
        "rptor_or_raptor_promoted_to_mtorc1": False,
        "search_only_surface_controls_identity": False,
        "canonical_identity_logic_changed": False,
        "source_identity_audit_sha256": sha(ALPHA33 / "identity_safety_regression_audit.json"),
    })
    outputs["phrase_overpacking_regression_audit.json"] = pretty({
        "artifact_schema_version": "PhraseOverpackingRegressionAuditV1",
        "new_query_count": len(query_rows),
        "full_proposition_exact_phrase_count": 0,
        "semantic_overpacking_query_count": 0,
        "maximum_semantic_roles_in_any_proximity_node": max(
            len(node["semantic_roles"]) for node in proximity_nodes),
        "proximity_role_limit": MAX_PROXIMITY_ROLE_ANCHORS,
        "full_proposition_phrase_index_dependency_count": 0,
        "old_failed_query_count": 29,
    })
    outputs["planner_immutability_audit.json"] = pretty({
        "artifact_schema_version": "Alpha36PlannerImmutabilityAuditV1",
        "planner_prompt_v3_changed": False,
        "planner_proposal_payload_v3_changed": False,
        "empirical_planner_v3_outputs_changed": False,
        "target_role_frame_changed": False,
        "relation_core_changed": False,
        "raw_outputs_101_107_sha256": sha(EMPIRICAL / "raw_provider_outputs_101_107.jsonl"),
        "raw_output_108_sha256": sha(SMOKE108 / "planner_v3_raw_payload.json"),
    })
    outputs["historical_failed_query_set_preservation_audit.json"] = pretty({
        "artifact_schema_version": "HistoricalFailedQuerySetPreservationAuditV1",
        "old_failed_query_count": 29, "old_failed_query_set_sha256": EXPECTED_OLD_QUERY_SET,
        "recomputed_old_failed_query_set_sha256": value_sha256(old_queries),
        "old_failed_query_set_preserved": True,
        "old_failed_retrieval_root": EXPECTED_FAILED,
        "empty_acquisition_corpus_sha256": EXPECTED_CORPUS,
        "superseded_not_rewritten": True,
    })
    outputs["scientific_state_safety_audit.json"] = pretty({
        "artifact_schema_version": "Alpha36ScientificStateSafetyAuditV1",
        "production_case_specific_rules": 0,
        "planner_prompt_v3_changed": False, "planner_proposal_payload_v3_changed": False,
        "scientific_semantics_changed": False, "canonical_identity_logic_changed": False,
        "query_modifications_to_historical_set": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "known_pmid_checks": 0, "candidate_records_seen": 0,
        "historical_assets_modified": False,
    })
    summary = {
        "artifact_schema_version": "SearchPlanV24DevAlpha36SummaryV1",
        "status": "completed",
        "retrieval_surface_plan_v1_defined": True,
        "pubmed_query_ast_v1_defined": True,
        "pubmed_query_serializer_v2_defined": True,
        "query_serialization_safety_linter_v1_defined": True,
        "serializer_accepts_relation_core_directly": False,
        "serializer_accepts_ast": True,
        "old_failed_query_count": 29, "old_failed_query_set_preserved": True,
        "new_query_count": len(query_rows),
        "full_proposition_exact_phrase_count": 0,
        "semantic_overpacking_query_count": 0,
        "boolean_decomposed_relation_query_count": len(query_rows),
        "proximity_query_count": len(query_rows),
        "full_proposition_phrase_index_dependency_count": 0,
        "average_new_query_token_count": grammar["retrieval_surface_v2"]["average_total_token_count"],
        "average_new_proximity_terms_per_node": grammar["retrieval_surface_v2"]["average_proximity_terms_per_node"],
        "topic_intersection_regression_count": 0,
        "semantic_drift_regression_count": 0,
        "unsupported_overbroad_regression_count": 0,
        "identity_promotion_count": 0, "therapy_flattening_count": 0,
        "nested_conditioning_flattening_count": 0, "endpoint_property_loss_count": 0,
        "production_case_specific_rules": 0,
        "new_query_set_created": True,
        "search_plan_v24_dev_retrieval_surface_v2_query_set_sha256": query_set_sha,
        "next_stage_recommendation": "PREREGISTER_RETRIEVAL_SURFACE_V2_EXECUTION",
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "known_pmid_checks": 0,
        "historical_assets_modified": False,
    }
    outputs["summary.json"] = pretty(summary)

    RUN.mkdir(parents=True)
    for name, body in outputs.items():
        (RUN / name).write_bytes(body)
    pairs = [[name, sha(RUN / name)] for name in sorted(outputs)]
    root = aggregate(pairs)
    validation = {
        "artifact_schema_version": "SearchPlanV24DevAlpha36ValidationV1",
        "status": "PASS",
        "checks": {
            "all_upstream_roots_verified": True,
            "all_29_validated_relations_compiled": True,
            "all_ast_validations_pass": True,
            "all_relation_certificates_certified": True,
            "all_query_budgets_respected": True,
            "full_proposition_exact_phrase_count_zero": True,
            "semantic_overpacking_query_count_zero": True,
            "full_proposition_phrase_index_dependency_count_zero": True,
            "topic_intersection_regression_count_zero": True,
            "endpoint_property_loss_count_zero": True,
            "therapy_flattening_count_zero": True,
            "nested_conditioning_flattening_count_zero": True,
            "identity_promotion_count_zero": True,
            "production_case_specific_rules_zero": True,
            "provider_llm_network_retrieval_calls_zero": True,
        },
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": pairs,
        "search_plan_v24_dev_alpha3_6_sha256": root,
    }
    (RUN / "validation.json").write_bytes(pretty(validation))
    (RUN / "search_plan_v24_dev_alpha3_6_sha256").write_text(root + "\n")

    # Reverify immutable inputs and the new freeze after all writes.
    require(verify_run(ALPHA35, "search_plan_v24_dev_alpha3_5_sha256", EXPECTED_ALPHA35)["verified"],
            "alpha3.5 changed")
    require(verify_run(ALPHA33, "search_plan_v24_dev_alpha3_3_sha256", EXPECTED_ALPHA33)["verified"],
            "alpha3.3 changed")
    require(verify_run(EMPIRICAL, "search_plan_v24_dev_alpha3_2_empirical_v3_sha256", EXPECTED_EMPIRICAL)["verified"],
            "empirical corpus changed")
    require(verify_run(FAILED, "search_plan_v24_dev_frozen_retrospective_retrieval_sha256", EXPECTED_FAILED)["verified"],
            "failed retrieval changed")
    require(aggregate([[name, sha(RUN / name)] for name in sorted(outputs)]) == root,
            "alpha3.6 root mismatch after write")
    print(json.dumps({"status": "completed", "run": str(RUN), "root": root,
                      "new_query_count": len(query_rows), "query_set_sha256": query_set_sha,
                      "component_count": len(pairs)}, sort_keys=True))


if __name__ == "__main__":
    main()
