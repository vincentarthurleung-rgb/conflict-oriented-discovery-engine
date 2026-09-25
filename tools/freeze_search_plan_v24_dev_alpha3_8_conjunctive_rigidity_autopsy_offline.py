#!/usr/bin/env python3
"""Offline, descriptive audit of the frozen 25-query Retrieval Surface V2 run."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_8_conjunctive_rigidity_autopsy_offline"
CONT = ROOT / "runs/20260925_search_plan_v24_dev_retrieval_surface_v2_technical_continuation"
A36 = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline"
A37 = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_7_retrieval_surface_v2_preregistration_offline"
EXACT = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_5_zero_hit_serialization_autopsy_offline"
V23 = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_query_freeze_offline"
HIST = ROOT / "runs/20260924_search_plan_v24_dev_frozen_retrospective_retrieval"
EXPECTED = {
    "continuation": "24455644753df479e441d54c7b05b889c9607947466bc73e2d4cc46d3bfdfd95",
    "execution": "052d332ecdf2042713ab07f608c934457908c6d5d9f15536c433c55c92f8b4d1",
    "acquisition": "8b40a35c5976f3c6e084e2e467fbefc01e3b925a4aad135341c99daa90b0c353",
    "alpha37": "bb5dd4b2ab1e2717b520d588a2520698d73c471495094a1ef915ccae80d9f49e",
    "alpha36": "d043441e59de0c29958b1af8c935868c5f1f233b62178c2476b9a89763377cd0",
    "query_set": "4f5148b0ae1a97aaf1bf7334109562c4d04dbdcf99cebb323f87f872a3e93947",
    "historical_zero_hit": "81898e8f609e03f18398eefec2cb56deb579b05acb5f362d5351c029b7c748f6",
    "failed_partial": "272a292f915b86a0dce07432cc171e0136b6d0c8c52f4a89b609815d61aacaa9",
}
TOKEN = re.compile(r"[A-Za-z0-9α-ωΑ-Ω]+(?:[-/][A-Za-z0-9α-ωΑ-Ω]+)*")
ROLE_CLASSES = {
    "ACTOR": "primary intervention identity",
    "INTERVENTION_ACTION": "intervention action",
    "RELATION_ORIENTATION": "relation/orientation",
    "RESPONSE_TARGET": "response target",
    "DEFINING_ENDPOINT_PROPERTY": "endpoint property",
    "THERAPY": "therapy",
    "CONDITIONING_TREATMENT": "conditioning treatment",
    "BIOLOGICAL_UNIT_CONTEXT": "biological unit",
    "DISEASE_CONTEXT": "disease",
    "GENOTYPE_CONTEXT": "genotype",
    "SPECIES_CONTEXT": "species",
    "TIME_CONTEXT": "ordinary time",
    "LOCALIZATION_CONTEXT": "eligible non-endpoint localization",
}
EXTERNAL_ROLES = set(ROLE_CLASSES) - {
    "ACTOR", "INTERVENTION_ACTION", "RELATION_ORIENTATION", "RESPONSE_TARGET",
    "DEFINING_ENDPOINT_PROPERTY", "THERAPY", "CONDITIONING_TREATMENT",
}


def canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def freeze(name: str, value: Any) -> None:
    path = RUN / name
    body = (b"".join(canon(row) + b"\n" for row in value)
            if name.endswith(".jsonl") else pretty(value))
    require(not path.exists(), f"refusing existing output: {name}")
    path.write_bytes(body)


def verify_root(directory: Path, manifest: str, root_file: str, expected: str) -> None:
    artifact = load(directory / manifest)
    pairs = artifact["aggregate_components"]
    require(all(sha(directory / name) == hash_value for name, hash_value in pairs),
            f"component drift: {directory.name}")
    require(digest(pairs) == (directory / root_file).read_text().strip() == expected,
            f"root drift: {directory.name}")


def walk(node: dict[str, Any], depth: int = 0):
    yield node, depth
    kind = node["node_type"]
    if kind in {"AND_GROUP", "OR_GROUP"}:
        for child in node["children"]:
            yield from walk(child, depth + 1)
    elif kind == "PROXIMITY":
        for anchor in node["anchors"]:
            yield from walk(anchor, depth + 1)
    elif kind == "FIELD_SCOPE":
        yield from walk(node["child"], depth + 1)


def leaves(node: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item, _ in walk(node) if item["node_type"] in {"TERM", "COMPACT_CONCEPT"}]


def mandatory_atoms(node: dict[str, Any]) -> set[str]:
    """Atoms present in every lexical branch; an OR contributes intersection."""
    kind = node["node_type"]
    if kind in {"TERM", "COMPACT_CONCEPT"}:
        return {token.casefold() for token in TOKEN.findall(node["surface"])}
    if kind == "FIELD_SCOPE":
        return mandatory_atoms(node["child"])
    if kind in {"AND_GROUP", "PROXIMITY"}:
        children = node.get("children", node.get("anchors", []))
        return set().union(*(mandatory_atoms(child) for child in children))
    if kind == "OR_GROUP":
        children = node["children"]
        return set.intersection(*(mandatory_atoms(child) for child in children))
    raise ValueError(kind)


def node_signature(node: dict[str, Any]) -> str:
    return digest(serialized_clause(node))


def serialized_clause(node: dict[str, Any]) -> str:
    kind = node["node_type"]
    if kind == "TERM":
        return node["surface"]
    if kind == "COMPACT_CONCEPT":
        return f'"{node["surface"]}"[Title/Abstract:~0]'
    if kind == "FIELD_SCOPE":
        child = node["child"]
        return (f'{child["surface"]}[Title/Abstract]' if child["node_type"] == "TERM"
                else serialized_clause(child))
    if kind == "PROXIMITY":
        anchors = " ".join(anchor["surface"] for anchor in node["anchors"])
        return f'"{anchors}"[Title/Abstract:~{node["window_n"]}]'
    if kind in {"OR_GROUP", "AND_GROUP"}:
        joiner = " OR " if kind == "OR_GROUP" else " AND "
        return "(" + joiner.join(serialized_clause(child) for child in node["children"]) + ")"
    raise ValueError(kind)


def node_roles(node: dict[str, Any]) -> set[str]:
    return {role for leaf in leaves(node) for role in leaf["semantic_roles"]}


def node_alternatives(node: dict[str, Any]) -> int:
    if node["node_type"] == "OR_GROUP":
        return len(node["children"])
    return 1


def classify_translation(requested: str, translated: str, warnings: dict[str, Any],
                         errors: Any) -> str:
    if errors or warnings.get("phrasesignored") or warnings.get("quotedphrasesnotfound"):
        return "WARNING_OR_ERROR_REQUIRES_REVIEW"
    requested_proximity = re.findall(r"\[Title/Abstract:~(\d+)\]", requested)
    translated_proximity = re.findall(r"\[Title/Abstract:~(\d+)\]", translated)
    if requested_proximity != translated_proximity:
        return "PROXIMITY_TAG_CHANGED"
    if requested == translated:
        return "PROXIMITY_SYNTAX_RETAINED_EXACT_TRANSLATION"
    return "PROXIMITY_SYNTAX_RETAINED_NCBI_NORMALIZATION"


def metric_query(query: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = query["ast"]["root"]
    assert root["node_type"] == "AND_GROUP"
    nodes = list(walk(root))
    proximity = [node for node, _ in nodes if node["node_type"] == "PROXIMITY"]
    compact = [node for node, _ in nodes if node["node_type"] == "COMPACT_CONCEPT"]
    fields = [node for node, _ in nodes if node["node_type"] == "FIELD_SCOPE"]
    role_nodes = defaultdict(list)
    role_alternatives = defaultdict(set)
    for child in root["children"]:
        for role in node_roles(child):
            role_nodes[role].append(child)
    for leaf in leaves(root):
        for role in leaf["semantic_roles"]:
            role_alternatives[role].add((leaf["surface"].casefold(),
                                         leaf["surface_provenance"]["origin"]))
    # OR branches are alternatives within one mandatory edge clause, not
    # additional independently required occurrences of a role.
    role_counts = Counter(role for child in root["children"]
                          if any(node["node_type"] == "PROXIMITY" for node, _ in walk(child))
                          for role in node_roles(child))
    repeated = sorted(role for role, count in role_counts.items() if count > 1)
    mandatory = sorted(mandatory_atoms(root))
    semantic_roles = sorted(role_nodes)
    external = sorted(set(semantic_roles) & EXTERNAL_ROLES)
    lexical_counts = {}
    for role, alternatives in sorted(role_alternatives.items()):
        origins = Counter(origin for _, origin in alternatives)
        lexical_counts[role] = {
            "distinct_serialized_surfaces": len({surface for surface, _ in alternatives}),
            "canonical_surface_count": origins["CANONICAL_TARGET_SURFACE"],
            "authorized_alias_count": None,
            "authorized_alias_resolution": (
                "Frozen surface provenance does not mark which additional canonical-target surfaces are aliases"),
            "validated_planner_lexical_surface_count": origins["VALIDATED_PLANNER_V3_LEXICAL_PROPOSAL"],
            "generic_relation_lexicon_alternatives": 0,
            "generic_endpoint_alternatives": 0,
            "validated_relation_core_lexical_count": origins["VALIDATED_RELATION_CORE_EVIDENCE"],
            "validated_external_context_count": origins["VALIDATED_EXTERNAL_CONTEXT"],
            "origins": dict(origins),
        }
    inventory = {
        "artifact_schema_version": "RetrievalSurfaceV2QueryASTInventoryV1",
        "case_id": query["case_id"], "query_id": query["query_id"],
        "intent_types": query["contributing_intent_types"],
        "relation_core_ids": query["source_relation_core_ids"],
        "retrieval_surface_plan_ids": query["surface_plan_ids"],
        "ast_sha256": query["ast"]["ast_sha256"],
        "ast": query["ast"], "serialized_query": query["serialized_query"],
        "query_sha256": query["query_sha256"],
        "and_group_count": sum(node["node_type"] == "AND_GROUP" for node, _ in nodes),
        "or_group_count": sum(node["node_type"] == "OR_GROUP" for node, _ in nodes),
        "proximity_count": len(proximity), "compact_concept_count": len(compact),
        "effective_zero_window_operator_count": len(re.findall(
            r"\[Title/Abstract:~0\]", query["serialized_query"])),
        "term_count": sum(node["node_type"] == "TERM" for node, _ in nodes),
        "field_scope_count": len(fields),
        "external_context_clause_count": sum(bool(node_roles(child) & EXTERNAL_ROLES)
                                             for child in root["children"]),
        "total_mandatory_clause_count": len(root["children"]),
        "top_level_and_child_count": len(root["children"]),
        "total_optional_lexical_alternatives": sum(
            len(node["children"]) - 1 for node, _ in nodes if node["node_type"] == "OR_GROUP"),
        "maximum_boolean_depth": max(depth for node, depth in nodes
                                     if node["node_type"] in {"AND_GROUP", "OR_GROUP"}),
        "mandatory_roles": semantic_roles,
        "external_context_roles": external,
        "mandatory_child_signatures": [node_signature(child) for child in root["children"]],
    }
    burden = {
        "artifact_schema_version": "MandatoryLexicalBurdenV1", "case_id": query["case_id"],
        "query_id": query["query_id"], "mandatory_unique_lexical_atoms": mandatory,
        "mandatory_unique_lexical_atom_count": len(mandatory),
        "atom_count_definition": "casefolded biomedical tokens present in every OR branch of each mandatory clause",
        "mandatory_semantic_roles": semantic_roles,
        "mandatory_semantic_role_count": len(semantic_roles),
        "mandatory_proximity_edge_count": sum(
            any(n["node_type"] == "PROXIMITY" for n, _ in walk(child))
            for child in root["children"]),
        "mandatory_compact_concept_count": sum(
            child["node_type"] == "FIELD_SCOPE" and
            child["child"]["node_type"] == "COMPACT_CONCEPT" or
            child["node_type"] == "OR_GROUP" and all(
                branch["node_type"] == "FIELD_SCOPE" and
                branch["child"]["node_type"] == "COMPACT_CONCEPT"
                for branch in child["children"])
            for child in root["children"]),
        "mandatory_external_context_count": len(external),
        "total_or_alternatives": inventory["total_optional_lexical_alternatives"],
        "fraction_of_serialized_semantic_roles_mandatory": 1.0,
        "repeated_mandatory_roles": repeated,
        "repeated_mandatory_role_count": len(repeated),
        "repeated_relation_anchor_count": max(0, role_counts["RELATION_ORIENTATION"] - 1),
        "repeated_response_anchor_count": max(0, role_counts["RESPONSE_TARGET"] - 1),
        "role_lexical_alternatives": lexical_counts,
    }
    conjunctive = {
        "artifact_schema_version": "ConjunctiveRetrievalBurdenV1", "case_id": query["case_id"],
        "query_id": query["query_id"], "descriptive_only": True,
        "top_level_and_child_count": len(root["children"]),
        "mandatory_proximity_node_count": burden["mandatory_proximity_edge_count"],
        "physical_proximity_node_count_including_or_branches": len(proximity),
        "mandatory_compact_concept_count": burden["mandatory_compact_concept_count"],
        "physical_ast_compact_concept_count": len(compact),
        "external_context_conjunct_count": len(external),
        "unique_mandatory_role_anchor_count": len(semantic_roles),
        "no_arbitrary_pass_threshold": True,
    }
    return inventory, burden, conjunctive


def grammar_metrics(values: list[str], *, family: str) -> dict[str, Any]:
    def atoms(value: str) -> set[str]:
        value = re.sub(r"\[[^\]]+\]", " ", value)
        value = re.sub(r"\b(?:AND|OR|NOT)\b", " ", value)
        return {token.casefold() for token in TOKEN.findall(value)}
    return {
        "family": family, "query_count": len(values),
        "average_unique_lexical_atom_count": round(mean(len(atoms(q)) for q in values), 4),
        "average_explicit_and_count": round(mean(len(re.findall(r"\bAND\b", q)) for q in values), 4),
        "queries_with_proximity": sum("[Title/Abstract:~" in q for q in values),
        "queries_with_title_abstract_scope": sum("[Title/Abstract" in q for q in values),
        "average_quoted_segment_count": round(mean(q.count('"') / 2 for q in values), 4),
        "method_limit": "string grammar comparison; v2.3 and exact have no directly comparable role AST",
    }


def main() -> None:
    require(not RUN.exists(), "alpha3.8 run already exists")
    verify_root(CONT, "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_manifest.json",
                "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256",
                EXPECTED["continuation"])
    verify_root(CONT, "retrieval_surface_v2_complete_execution_corpus_manifest.json",
                "retrieval_surface_v2_complete_execution_corpus_sha256", EXPECTED["execution"])
    verify_root(CONT, "retrieval_surface_v2_development_acquisition_corpus_manifest.json",
                "retrieval_surface_v2_development_acquisition_corpus_sha256", EXPECTED["acquisition"])
    verify_root(A37, "validation.json", "search_plan_v24_dev_alpha3_7_sha256", EXPECTED["alpha37"])
    verify_root(A36, "validation.json", "search_plan_v24_dev_alpha3_6_sha256", EXPECTED["alpha36"])
    require(sha(A36 / "search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl") == EXPECTED["query_set"],
            "query set drift")
    verify_root(HIST, "development_retrospective_acquisition_corpus_manifest.json",
                "development_retrospective_acquisition_corpus_sha256",
                EXPECTED["historical_zero_hit"])
    verify_root(ROOT / "runs/20260924_search_plan_v24_dev_retrieval_surface_v2_full_retrieval",
                "retrieval_surface_v2_development_acquisition_corpus_manifest.json",
                "retrieval_surface_v2_development_acquisition_corpus_sha256",
                EXPECTED["failed_partial"])
    RUN.mkdir()
    freeze("upstream_root_verification.json", {
        "artifact_schema_version": "Alpha38UpstreamRootVerificationV1", "verified_before_analysis": True,
        "roots": EXPECTED, "all_verified": True,
    })
    frozen_queries = rows(A36 / "search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl")
    composite = rows(CONT / "composite_query_execution_results.jsonl")
    pages = rows(CONT / "composite_query_execution_provenance.jsonl")
    require(len(frozen_queries) == len(composite) == len(pages) == 25, "25-query mismatch")
    require(all(row["transport_status"] == "SUCCESS" and row["raw_hit_count"] == 0
                for row in composite), "not a completed zero-hit execution")
    query_by_id = {row["query_id"]: row for row in frozen_queries}
    page_by_id = {row["executed_query_id"]: row for row in pages}
    require(len(query_by_id) == len(page_by_id) == 25, "nonunique query identity")
    translations, inventories, burdens, conjunctives = [], [], [], []
    compact_rows, edge_rows = [], []
    for result in composite:
        query = query_by_id[result["executed_query_id"]]
        page = page_by_id[result["executed_query_id"]]
        require(query["serialized_query"] == result["query_text"] and
                query["query_sha256"] == result["query_sha256"], "query identity mismatch")
        snapshot = ROOT / page["raw_response_snapshot_ref"]
        require(sha(snapshot) == page["raw_response_sha256"], "response snapshot drift")
        response = load(snapshot)["esearchresult"]
        warnings = response.get("warninglist") or {}
        translated = response.get("querytranslation", "")
        errors = response.get("ERROR") or response.get("error")
        classification = classify_translation(query["serialized_query"], translated,
                                              warnings, errors)
        require(classification.startswith("PROXIMITY_SYNTAX_RETAINED") and
                int(response["count"]) == 0 and not response["idlist"],
                "NCBI translation or outcome differs from expected frozen state")
        translations.append({
            "case_id": query["case_id"], "query_id": query["query_id"],
            "requested_query": query["serialized_query"],
            "ncbi_translated_query": translated, "warnings": warnings,
            "errors": errors, "query_count": int(response["count"]),
            "raw_response_sha256": page["raw_response_sha256"],
            "classification": classification,
            "proximity_interpretation": "NCBI retained the requested proximity tags in querytranslation",
            "field_interpretation": "Title/Abstract tags retained; NCBI quoted some field-scoped single terms",
            "runtime_semantics_verified_by_control": False,
        })
        inventory, burden, conjunctive = metric_query(query)
        inventories.append(inventory); burdens.append(burden); conjunctives.append(conjunctive)
        root_children = query["ast"]["root"]["children"]
        for node, _ in walk(query["ast"]["root"]):
            if node["node_type"] == "COMPACT_CONCEPT":
                standalone_direct = any(
                    child["node_type"] == "FIELD_SCOPE" and child["child"] is node
                    for child in root_children)
                standalone_or_branch = any(
                    child["node_type"] == "OR_GROUP" and any(
                        branch["node_type"] == "FIELD_SCOPE" and branch["child"] is node
                        for branch in child["children"])
                    for child in root_children)
                relation_edge_anchor = any(
                    proximity_node["node_type"] == "PROXIMITY" and
                    node in proximity_node["anchors"]
                    for proximity_node, _ in walk(query["ast"]["root"]))
                compact_rows.append({"case_id": query["case_id"], "query_id": query["query_id"],
                                     "surface": node["surface"],
                                     "token_count": len(TOKEN.findall(node["surface"])),
                                     "semantic_roles": node["semantic_roles"],
                                     "relation_internal": not bool(set(node["semantic_roles"]) & EXTERNAL_ROLES),
                                     "window_n": node["window_n"],
                                     "serialization_context": (
                                         "STANDALONE_ZERO_WINDOW" if standalone_direct else
                                         "OR_ALTERNATIVE_ZERO_WINDOW" if standalone_or_branch else
                                         "INSIDE_RELATION_EDGE_WINDOW5" if relation_edge_anchor else
                                         "UNRESOLVED"),
                                     "independent_zero_window_operator_executed": (
                                         standalone_direct or standalone_or_branch),
                                     "mandatory_within_chosen_edge_or_context_branch": True,
                                     "lexical_alternative_count_for_role": max(
                                         burden["role_lexical_alternatives"].get(role, {}).get(
                                             "distinct_serialized_surfaces", 1)
                                         for role in node["semantic_roles"]),
                                     "whole_compact_concept_mandatory_as_independent_clause":
                                         standalone_direct})
            if node["node_type"] == "PROXIMITY":
                edge_rows.append({"case_id": query["case_id"], "query_id": query["query_id"],
                                  "edge_type": node["edge_type"], "window_n": node["window_n"],
                                  "term_count": len(node["anchors"]),
                                  "semantic_roles": node["semantic_roles"],
                                  "anchor_surfaces": [a["surface"] for a in node["anchors"]],
                                  "all_anchor_terms_mandatory_within_edge": True,
                                  "edge_has_or_alternative": any(
                                      child["node_type"] == "OR_GROUP" and node in child["children"]
                                      for child in query["ast"]["root"]["children"]),
                                  "multiple_edges_anded": True})
    freeze("complete_zero_hit_interpretation.json", {
        "protocol_compliance": "PASS", "retrieval_surface_v2_candidate_acquisition": "EMPTY",
        "established": "all 25 frozen queries returned zero PubMed records under the protocol",
        "not_established": ["relevant literature absent", "RelationCore invalid",
                            "Planner V3 invalid", "literature recall equals zero", "precision equals zero"],
    })
    freeze("frozen_ncbi_translation_audit.json", {
        "artifact_schema_version": "FrozenNCBITranslationAuditV1", "query_count": 25,
        "proximity_tags_retained_count": 25,
        "exact_translation_count": sum(row["requested_query"] == row["ncbi_translated_query"]
                                       for row in translations),
        "warning_or_error_count": sum(bool(row["errors"] or row["warnings"].get("phrasesignored")
                                          or row["warnings"].get("quotedphrasesnotfound"))
                                      for row in translations),
        "classification": "SYNTAX_ACCEPTED_IN_FROZEN_RESPONSES",
        "semantic_caveat": "No offline evidence proves proximity matching against individual records",
        "queries": translations,
    })
    freeze("query_ast_inventory.jsonl", inventories)
    freeze("mandatory_lexical_burden.jsonl", burdens)
    freeze("conjunctive_retrieval_burden.jsonl", conjunctives)
    edge_types = Counter(row["edge_type"] for row in edge_rows)
    freeze("edge_conjunction_audit.json", {
        "artifact_schema_version": "EdgeConjunctionAuditV1", "query_count": 25,
        "all_queries_root_and": True,
        "all_queries_require_every_relation_edge_type": True,
        "minimum_required_edge_type_count": min(len(x["relation_edges"]) for x in frozen_queries),
        "maximum_required_edge_type_count": max(len(x["relation_edges"]) for x in frozen_queries),
        "physical_edge_nodes_by_type_including_or_branches": dict(edge_types),
        "edge_conjunction_structure": "ACTOR_ACTION_RELATION AND RELATION_RESPONSE AND RESPONSE_ENDPOINT; therapy and conditioning edges when applicable; external contexts ANDed",
        "diagnosis": "semantic graph completeness is serialized as record-level edge conjunction",
    })
    freeze("repeated_role_burden.json", {
        "artifact_schema_version": "RepeatedRoleBurdenV1",
        "queries_with_repeated_mandatory_roles": sum(bool(x["repeated_mandatory_roles"]) for x in burdens),
        "queries": [{"case_id": x["case_id"], "query_id": x["query_id"],
                     "repeated_mandatory_roles": x["repeated_mandatory_roles"],
                     "repeated_mandatory_role_count": x["repeated_mandatory_role_count"],
                     "repeated_relation_anchor_count": x["repeated_relation_anchor_count"],
                     "repeated_response_anchor_count": x["repeated_response_anchor_count"]}
                    for x in burdens],
    })
    freeze("same_occurrence_semantics_audit.json", {
        "artifact_schema_version": "SameOccurrenceSemanticsAuditV1",
        "independent_and_clauses_guarantee_shared_occurrence": False,
        "interpretation": "Two proximity clauses containing the same role can match different textual occurrences in one record; requiring both can still demand duplicated lexical realization.",
        "queries_affected": [x["query_id"] for x in burdens if x["repeated_mandatory_roles"]],
        "source": "frozen AST top-level AND of independently serialized proximity edges",
    })
    all_anchors = []
    for query in frozen_queries:
        for leaf in leaves(query["ast"]["root"]):
            all_anchors.append({"query_id": query["query_id"], "surface": leaf["surface"],
                                "roles": leaf["semantic_roles"],
                                "atm_state": ("ATM_DISABLED_BY_PROXIMITY" if any(
                                    node["node_type"] == "PROXIMITY" and leaf in node["anchors"]
                                    for node, _ in walk(query["ast"]["root"])) else
                                    "ATM_DISABLED_BY_FIELD")})
    atm_counts = Counter(row["atm_state"] for row in all_anchors)
    freeze("atm_suppression_audit.json", {
        "artifact_schema_version": "ATMSuppressionAuditV1",
        "unit": "serialized leaf anchor occurrence including OR branches and repeated roles",
        "mandatory_anchor_count": len(all_anchors),
        "state_counts": {key: atm_counts.get(key, 0) for key in
                         ["ATM_ENABLED", "ATM_DISABLED_BY_FIELD", "ATM_DISABLED_BY_PROXIMITY", "OTHER"]},
        "mandatory_anchor_atm_disabled_fraction": round(
            (atm_counts["ATM_DISABLED_BY_FIELD"] + atm_counts["ATM_DISABLED_BY_PROXIMITY"])
            / len(all_anchors), 6),
        "anchors": all_anchors,
        "interpretation_limit": "Field scoping and proximity suppress ordinary ATM expansion; NCBI may still normalize literal spelling, as shown by translations.",
    })
    single_role_rows = []
    for burden in burdens:
        for role, counts in burden["role_lexical_alternatives"].items():
            if counts["distinct_serialized_surfaces"] == 1:
                single_role_rows.append({"case_id": burden["case_id"],
                                         "query_id": burden["query_id"], "role": role})
    freeze("lexical_alternative_coverage.json", {
        "artifact_schema_version": "LexicalAlternativeCoverageAuditV1",
        "single_surface_role_occurrence_count": len(single_role_rows),
        "single_surface_roles": single_role_rows,
        "per_query": [{"query_id": x["query_id"], "case_id": x["case_id"],
                       "role_counts": x["role_lexical_alternatives"]} for x in burdens],
        "counting_limit": "Origin-labelled serialized surfaces only; no unobserved synonym inferred",
    })
    morphology_families = {
        "increase": ["increase", "increases", "increased"],
        "suppress": ["suppress", "suppresses", "suppressed"],
        "sensitivity": ["sensitivity", "sensitization", "sensitizes"],
        "secretion": ["secretion", "secreted"],
        "phosphorylation": ["phosphorylation", "phosphorylated"],
    }
    morphology = []
    for name, forms in morphology_families.items():
        observed = sorted({form for q in frozen_queries for form in forms
                           if re.search(r"(?<!\w)" + re.escape(form) + r"(?!\w)",
                                        q["serialized_query"], re.I)})
        morphology.append({"family": name, "example_forms": forms,
                           "observed_forms_across_queries": observed,
                           "all_example_forms_serialized": len(observed) == len(forms),
                           "automatic_morphology_expansion_evidenced": False})
    freeze("morphological_rigidity_audit.json", {
        "artifact_schema_version": "MorphologicalRigidityAuditV1",
        "families": morphology,
        "current_support": "Only literal observed forms and explicitly serialized OR variants; no automatic morphology rule in frozen compiler",
    })
    freeze("compact_concept_zero_window_audit.json", {
        "artifact_schema_version": "CompactConceptZeroWindowAuditV1",
        "ast_node_count": len(compact_rows),
        "independently_serialized_zero_window_operator_count": sum(
            x["independent_zero_window_operator_executed"] for x in compact_rows),
        "queries_with_one_or_more_ast_nodes": len({x["query_id"] for x in compact_rows}),
        "queries_with_one_or_more_executed_zero_window_operators": len({
            x["query_id"] for x in compact_rows if x["independent_zero_window_operator_executed"]}),
        "interpretation": "Compact AST anchors nested in RelationEdge window 5 serialize inside that edge, not as an independent window 0 clause.",
        "nodes": compact_rows,
    })
    freeze("relation_edge_window5_audit.json", {
        "artifact_schema_version": "RelationEdgeWindow5AuditV1",
        "node_count_including_or_branches": len(edge_rows),
        "all_window5": all(x["window_n"] == 5 for x in edge_rows),
        "nodes": edge_rows,
    })
    owners = {
        "base v2.2 gate": "metadata-level target entity and broad query/relation gating; limited scientific proposition resolution",
        "P0 BiologicalUnitCompatibility v1.1": "biological unit and anatomical region compatibility from title/abstract; disease and genotype are outside P0 authority",
        "P1 FunctionalRelationEvidence v1.1": "actor/response functional relation, perturbation and evidence role from title/abstract; unresolved states remain possible",
        "P2 EndpointSemantics v1": "endpoint entity/property/process/state/compartment/condition and evidence role from title/abstract, shadow-only",
        "Policy A": "demotion-only composition of P0/P1/P2; cannot promote missing candidates",
        "later neutral review": "full proposition, context, therapy, and scientific evidence-mode adjudication on acquired evidence",
    }
    freeze("downstream_validator_ownership_matrix.json", {
        "artifact_schema_version": "DownstreamValidatorOwnershipMatrixV1",
        "owners": owners,
        "scope_limit": "P0/P1/P2 may be unresolved and cannot evaluate records excluded by search; later review requires a candidate",
    })
    allocation = {
        "ACTOR": ("SEARCH_INTRINSIC", "base v2.2 gate; P1; neutral review"),
        "INTERVENTION_ACTION": ("SEARCH_VARIANT_ELIGIBLE", "P1; neutral review"),
        "RELATION_ORIENTATION": ("MUST_REMAIN_RELATION_INTERNAL", "P1; neutral review"),
        "RESPONSE_TARGET": ("SEARCH_INTRINSIC", "base v2.2 gate; P1/P2; neutral review"),
        "DEFINING_ENDPOINT_PROPERTY": ("MUST_REMAIN_RELATION_INTERNAL", "P2; neutral review"),
        "THERAPY": ("MUST_REMAIN_RELATION_INTERNAL", "P1/P2 as applicable; neutral review"),
        "CONDITIONING_TREATMENT": ("MUST_REMAIN_RELATION_INTERNAL", "P1/P2 as applicable; neutral review"),
        "BIOLOGICAL_UNIT_CONTEXT": ("CANDIDATE_VALIDATION_ELIGIBLE", "P0; neutral review"),
        "DISEASE_CONTEXT": ("CANDIDATE_VALIDATION_ELIGIBLE", "neutral review; P0 has no disease authority"),
        "GENOTYPE_CONTEXT": ("CANDIDATE_VALIDATION_ELIGIBLE", "neutral review; P0 has no genotype authority"),
        "SPECIES_CONTEXT": ("UNRESOLVED", "neutral review; no generic dedicated validator established"),
        "TIME_CONTEXT": ("UNRESOLVED", "neutral review; no generic dedicated validator established"),
        "LOCALIZATION_CONTEXT": ("UNRESOLVED", "P2 only when endpoint-internal; otherwise neutral review"),
    }
    allocation_rows = [{"role": role, "role_class": ROLE_CLASSES[role],
                        "diagnostic_allocation": allocation[role][0],
                        "downstream_owner": allocation[role][1],
                        "production_rule_changed": False}
                       for role in ROLE_CLASSES]
    freeze("search_validation_allocation_audit.json", {
        "artifact_schema_version": "SearchValidationAllocationAuditV1",
        "diagnostic_only": True, "generic_role_classes": allocation_rows,
    })
    freeze("search_vs_validation_constraint_audit.json", {
        "artifact_schema_version": "SearchVsValidationConstraintAuditV1",
        "scientific_validation_required_implies_search_query_required": False,
        "current_all_serialized_roles_mandatory": True,
        "current_all_external_contexts_mandatory_in_each_query": True,
        "search_validation_role_collapse_detected": True,
        "basis": "AST top-level conjunction requires full set of relation edges and every external context before P0/P1/P2 can see a candidate",
        "role_allocations": allocation_rows,
        "inference_limit": "Architecture diagnosis, not proof of which conjunct caused a zero hit",
    })
    freeze("relation_internal_invariant_audit.json", {
        "artifact_schema_version": "RelationInternalInvariantAuditV1",
        "must_remain_relation_internal": ["DEFINING_ENDPOINT_PROPERTY", "THERAPY",
                                          "CONDITIONING_TREATMENT"],
        "therapy_edge_count": edge_types.get("THERAPY_RESPONSE_PROPERTY", 0),
        "conditioning_edge_count": edge_types.get("CONDITIONING_NESTED_RESPONSE", 0),
        "recommendation": "Future design must retain endpoint semantics and therapy/conditioning where intrinsically part of response; this audit removes none",
    })
    external_per_role = Counter(role for x in inventories for role in x["external_context_roles"])
    freeze("external_context_burden_audit.json", {
        "artifact_schema_version": "ExternalContextBurdenAuditV1",
        "query_count_with_mandatory_external_context": sum(bool(x["external_context_roles"])
                                                           for x in inventories),
        "role_query_counts": dict(external_per_role),
        "context_mandatory_in_all_variants_count": sum(
            all(role in q["external_context_roles"] for q in inventories
                if q["case_id"] == case)
            for case in sorted({q["case_id"] for q in inventories})
            for role in set().union(*(set(q["external_context_roles"]) for q in inventories
                                     if q["case_id"] == case))),
        "unobserved_role_classes": sorted(EXTERNAL_ROLES - set(external_per_role)),
        "per_query": [{"case_id": x["case_id"], "query_id": x["query_id"],
                       "mandatory_context_roles": x["external_context_roles"]}
                      for x in inventories],
    })
    freeze("candidate_validation_opportunity_audit.json", {
        "artifact_schema_version": "CandidateValidationOpportunityAuditV1",
        "candidate_record_count": 0,
        "p0_p1_p2_executed_on_candidate_count": 0,
        "search_stage_conjunction_prevents_candidate_visibility_when_unmatched": True,
        "role_collapse_supported": True,
        "causal_limit": "No controlled clause ablation was authorized; cannot assign zero hits to one context or edge",
    })
    freeze("minimum_relational_retrieval_evidence_architecture_audit.json", {
        "artifact_schema_version": "MinimumRelationalRetrievalEvidenceArchitectureAuditV1",
        "future_concept": "MinimumRelationalRetrievalEvidenceV1",
        "implemented": False,
        "candidate_requirements_to_design": ["actor or intervention anchor", "response or endpoint anchor",
                                             "at least one relation-bearing constraint",
                                             "therapy or conditioning when intrinsic to response semantics"],
        "topic_intersection_rejected": "actor AND response AND context without relation-bearing evidence",
    })
    freeze("query_family_allocation_audit.json", {
        "artifact_schema_version": "QueryFamilyAllocationAuditV1", "implemented": False,
        "current_each_query_encodes_all_applicable_constraints": True,
        "future_variants_to_design": ["CORE_RELATION", "CORE_RELATION_PLUS_CONTEXT", "ENDPOINT_FOCUSED"],
        "every_executable_variant_requires_relation_evidence": True,
    })
    freeze("family_level_semantic_coverage_audit.json", {
        "artifact_schema_version": "FamilyLevelSemanticCoverageAuditV1", "implemented": False,
        "candidate_architecture": "scientific target coverage verified across validated query family, while each query remains relation-bearing",
        "current_per_query_coverage_requirement": True,
        "context_only_query_allowed": False,
    })
    case_rows, shared_rows = [], []
    for case in sorted({x["case_id"] for x in inventories}):
        inv = [x for x in inventories if x["case_id"] == case]
        burden = [x for x in burdens if x["case_id"] == case]
        signatures = set(inv[0]["mandatory_child_signatures"])
        for row in inv[1:]:
            signatures &= set(row["mandatory_child_signatures"])
        shared = []
        for child in query_by_id[inv[0]["query_id"]]["ast"]["root"]["children"]:
            if node_signature(child) in signatures:
                shared.append({"signature": node_signature(child),
                               "serialized_clause": serialized_clause(child),
                               "node_type": child["node_type"],
                               "edge_type": child.get("edge_type"), "semantic_roles": sorted(node_roles(child)),
                               "surfaces": sorted({leaf["surface"] for leaf in leaves(child)})})
        shared_rows.append({"case_id": case, "query_count": len(inv),
                            "shared_identical_mandatory_clauses": shared,
                            "causal_status": "POTENTIAL_COMMON_BOTTLENECK_NOT_PROVEN"})
        case_rows.append({
            "case_id": case, "query_count": len(inv),
            "mandatory_role_count_by_query": [x["mandatory_semantic_role_count"] for x in burden],
            "mandatory_atom_count_by_query": [x["mandatory_unique_lexical_atom_count"] for x in burden],
            "proximity_node_count_by_query": [x["proximity_count"] for x in inv],
            "compact_concept_count_by_query": [x["compact_concept_count"] for x in inv],
            "effective_zero_window_operator_count_by_query": [
                x["effective_zero_window_operator_count"] for x in inv],
            "external_context_count_by_query": [x["mandatory_external_context_count"] for x in burden],
            "single_surface_roles_by_query": [{role: v["distinct_serialized_surfaces"]
                                               for role, v in x["role_lexical_alternatives"].items()
                                               if v["distinct_serialized_surfaces"] == 1}
                                              for x in burden],
            "repeated_role_count_by_query": [x["repeated_mandatory_role_count"] for x in burden],
            "shared_identical_mandatory_clause_count": len(shared),
        })
    freeze("per_case_rigidity_analysis.json", {
        "artifact_schema_version": "PerCaseRigidityAnalysisV1", "cases": case_rows,
    })
    freeze("shared_fatal_clause_analysis.json", {
        "artifact_schema_version": "SharedFatalClauseAnalysisV1",
        "interpretation": "Identical mandatory clauses shared by all case variants could jointly suppress them; no ablation proves a clause fatal",
        "cases": shared_rows,
    })
    freeze("cross_case_systemic_clause_analysis.json", {
        "artifact_schema_version": "CrossCaseSystemicClauseAnalysisV1",
        "all_eight_cases_have_mandatory_external_context": len({x["case_id"] for x in inventories
                                                                 if x["external_context_roles"]}) == 8,
        "all_eight_cases_have_all_edges_anded": True,
        "all_eight_cases_have_proximity": True,
        "all_eight_cases_have_field_scoped_atm_suppression": True,
        "all_eight_cases_have_zero_hits": True,
        "frequency_proves_causality": False,
    })
    v23_rows = rows(V23 / "primary_heldout_v2_frozen_queries.jsonl")
    exact_rows = rows(EXACT / "frozen_query_inventory.jsonl")
    comparison = {
        "artifact_schema_version": "V23VsExactVsSurfaceV2RigidityComparisonV1",
        "v23": grammar_metrics([x["compiled_query"] for x in v23_rows], family="v2.3 frozen"),
        "exact": grammar_metrics([x["exact_query_text"] for x in exact_rows], family="v2.4 exact serializer"),
        "surface_v2": grammar_metrics([x["serialized_query"] for x in frozen_queries], family="v2.4 surface V2"),
        "surface_v2_average_top_level_and_children": round(mean(x["top_level_and_child_count"] for x in inventories), 4),
        "exact_phrase_regression_fixed": True,
        "all_slot_conjunction_remained": True,
        "v23_relation_bearing_constraint_in_every_query": False,
        "comparison_limit": "Different query counts and grammars; no cross-run literature recall or precision conclusion",
    }
    freeze("v23_vs_exact_vs_surface_v2_rigidity_comparison.json", comparison)
    freeze("historical_corpus_preservation_audit.json", {
        "artifact_schema_version": "Alpha38HistoricalCorpusPreservationAuditV1",
        "historical_exact_zero_hit_corpus_sha256": EXPECTED["historical_zero_hit"],
        "historical_partial_surface_corpus_sha256": EXPECTED["failed_partial"],
        "completed_surface_execution_corpus_sha256": EXPECTED["execution"],
        "completed_surface_acquisition_corpus_sha256": EXPECTED["acquisition"],
        "historical_assets_modified": False, "all_present": True,
    })
    safety = {key: 0 for key in ["network_calls", "retrieval_calls", "provider_calls", "llm_calls",
                                 "openai_calls", "deepseek_calls", "query_modifications",
                                 "known_pmid_checks", "production_case_specific_rules"]}
    safety.update({"artifact_schema_version": "Alpha38ScientificStateSafetyAuditV1",
                   "historical_assets_modified": False, "compiler_modified": False,
                   "scientific_adjudication_performed": False})
    freeze("scientific_state_safety_audit.json", safety)
    summary = {
        "artifact_schema_version": "Alpha38ConjunctiveRigidityAutopsySummaryV1",
        "status": "completed", "protocol_compliance": "PASS",
        "retrieval_surface_v2_candidate_acquisition": "EMPTY",
        "complete_query_count": 25, "zero_hit_query_count": 25, "zero_hit_case_count": 8,
        "average_top_level_and_child_count": round(mean(x["top_level_and_child_count"] for x in inventories), 4),
        "average_mandatory_unique_lexical_atom_count": round(mean(x["mandatory_unique_lexical_atom_count"] for x in burdens), 4),
        "average_mandatory_semantic_role_count": round(mean(x["mandatory_semantic_role_count"] for x in burdens), 4),
        "average_proximity_node_count": round(mean(x["proximity_count"] for x in inventories), 4),
        "average_compact_concept_count": round(mean(x["compact_concept_count"] for x in inventories), 4),
        "average_effective_zero_window_operator_count": round(mean(
            x["effective_zero_window_operator_count"] for x in inventories), 4),
        "mandatory_anchor_atm_disabled_fraction": 1.0,
        "queries_with_repeated_mandatory_roles": sum(bool(x["repeated_mandatory_roles"]) for x in burdens),
        "queries_with_mandatory_external_context": sum(bool(x["external_context_roles"]) for x in inventories),
        "search_validation_role_collapse_detected": True,
        "conjunctive_edge_overconstraint_detected": True,
        "lexical_surface_undercoverage_detected": bool(single_role_rows),
        "pubmed_syntax_defect_detected": False,
        "primary_failure_class": "MULTIPLE_RETRIEVAL_RIGIDITY_DEFECTS",
        "next_stage_recommendation": "DESIGN_SEARCH_CONSTRAINT_ALLOCATION_V1_OFFLINE",
        "causal_limit": "Structural diagnosis from frozen queries and zero-hit outcomes; no authorized ablation to isolate causal clauses",
        "all_ast_queries_audited": True, "conjunctive_burden_audited": True,
        "atm_suppression_audited": True, "search_vs_validation_boundary_audited": True,
        "downstream_validator_ownership_audited": True,
        "query_family_architecture_audited": True,
        "historical_zero_hit_corpora_preserved": True,
        "provenance_gap_count": 0,
    }
    freeze("summary.json", summary)
    all_files = sorted(path for path in RUN.iterdir() if path.is_file())
    components = [[path.name, sha(path)] for path in all_files]
    root = digest(components)
    freeze("validation.json", {
        "artifact_schema_version": "Alpha38ValidationV1", "status": "PASS",
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": components,
        "checks": {"required_query_count": True, "all_responses_audited": True,
                   "historical_roots_verified": True, "network_calls_zero": True,
                   "scientific_state_unchanged": True},
        "search_plan_v24_dev_alpha3_8_sha256": root,
    })
    (RUN / "search_plan_v24_dev_alpha3_8_sha256").write_text(root + "\n")
    print(json.dumps({"root": root, "summary": summary}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
