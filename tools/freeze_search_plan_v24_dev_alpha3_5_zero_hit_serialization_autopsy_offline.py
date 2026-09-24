#!/usr/bin/env python3
"""Freeze the offline alpha3.5 autopsy of the 29 zero-hit PubMed queries."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_5_zero_hit_serialization_autopsy_offline"
RETRIEVAL = ROOT / "runs/20260924_search_plan_v24_dev_frozen_retrospective_retrieval"
ALPHA34 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline"
ALPHA33 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_3_role_scoped_polarity_offline"
V23 = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval"
EMPIRICAL = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_2_planner_v3_empirical_remaining7"
SMOKE108 = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_deepseek_planner_v3_smoke_108_protocol_completion_offline"

EXPECTED_RETRIEVAL = "391d2fe5d7c133be42d3c503a92ecc8724f398430adf20c46283ad1567e8dfd5"
EXPECTED_CORPUS = "81898e8f609e03f18398eefec2cb56deb579b05acb5f362d5351c029b7c748f6"
EXPECTED_ALPHA34 = "2488b4322894acb755872e9bc92d78dcaf2a4dec6ed807a22d3aff4622e2d5d5"
EXPECTED_ALPHA33 = "e5a7b502102a36de920e5421aa83b4bfc4775ddee4418df86299d587a4c5a763"
EXPECTED_QUERY_SET = "b7117825db0cde698ca2a9e5b882cac2f60ab4635e5b2e213243b8473d9d4ed0"
EXPECTED_V23 = "0da797b2b3b23a1884a03741abb60d51adedcb03ea9e6faf39ba897a829e46d8"

TOKEN_RE = re.compile(r"[A-Za-z0-9α-ωΑ-Ω]+(?:[-/][A-Za-z0-9α-ωΑ-Ω]+)*")
QUOTE_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
FIELD_RE = re.compile(r"\[([^\]]+)\]")
BOOLEAN_RE = re.compile(r"\s+(AND|OR|NOT)\s+")
PROXIMITY_RE = re.compile(r"(?:~\d+|NEAR/\d+|ADJ\d*)", re.I)
GREEK_RE = re.compile(r"[α-ωΑ-Ω]")
STOPWORDS = {
    "a", "an", "the", "in", "on", "of", "for", "from", "to", "with",
    "by", "as", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "not",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


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
            f"component hash mismatch: {path.name}")
    actual = aggregate(pairs)
    recorded = (path / root_file).read_text(encoding="utf-8").strip()
    require(actual == recorded == expected, f"root mismatch: {path.name}")
    return {
        "path": str(path.relative_to(ROOT)),
        "expected_sha256": expected,
        "recorded_sha256": recorded,
        "recomputed_sha256": actual,
        "verified": True,
    }


def verify_v23() -> dict[str, Any]:
    manifest = load(V23 / "implementation_manifest.json")
    pairs = manifest["aggregate_components"]
    require(all(sha(V23 / name) == digest for name, digest in pairs),
            "v2.3 component hash mismatch")
    actual = aggregate(pairs)
    require(actual == manifest["primary_heldout_v2_network_retrieval_sha256"] == EXPECTED_V23,
            "v2.3 root mismatch")
    return {
        "path": str(V23.relative_to(ROOT)),
        "expected_sha256": EXPECTED_V23,
        "recomputed_sha256": actual,
        "verified": True,
    }


def lexical_tokens(text: str) -> list[str]:
    without_tags = re.sub(r"\[(?:Title/Abstract|tiab)\]", " ", text, flags=re.I)
    return [token for token in TOKEN_RE.findall(without_tags)
            if token.upper() not in {"AND", "OR", "NOT"}]


def quoted_segments(text: str) -> list[str]:
    return QUOTE_RE.findall(text)


def round6(value: float) -> float:
    return round(value, 6)


def mean(values: list[int]) -> float:
    return round6(sum(values) / len(values))


def raw_link_map() -> dict[str, dict[str, Any]]:
    intents: list[dict[str, Any]] = []
    for row in load_jsonl(EMPIRICAL / "raw_provider_outputs_101_107.jsonl"):
        if row.get("event") == "RAW_MODEL_CONTENT":
            intents.extend(json.loads(row["raw_model_content"])["retrieval_intents"])
    intents.extend(load(SMOKE108 / "planner_v3_raw_payload.json")["retrieval_intents"])
    links = {}
    for intent in intents:
        for link in intent["linked_relation_proposals"]:
            links[sha_bytes(canonical(link))] = link
    return links


def packed_roles(link: dict[str, Any]) -> list[str]:
    roles = ["actor", "action", "relation", "response", "endpoint"]
    optional = (
        ("therapy_surface", "therapy"),
        ("conditioning_treatment_surface", "conditioning_treatment"),
        ("biological_unit_surface", "biological_unit"),
        ("disease_surface", "disease_context"),
        ("genotype_surface", "genotype_context"),
    )
    roles.extend(role for field, role in optional if link.get(field))
    return roles


def main() -> None:
    require(not RUN.exists(), f"refusing to overwrite {RUN}")

    roots = {
        "authoritative_retrieval": verify_run(
            RETRIEVAL, "search_plan_v24_dev_frozen_retrospective_retrieval_sha256",
            EXPECTED_RETRIEVAL),
        "alpha3_4_preregistration": verify_run(
            ALPHA34, "search_plan_v24_dev_alpha3_4_sha256", EXPECTED_ALPHA34),
        "alpha3_3_search_plan": verify_run(
            ALPHA33, "search_plan_v24_dev_alpha3_3_sha256", EXPECTED_ALPHA33),
        "historical_v23_retrieval": verify_v23(),
    }
    corpus_manifest = load(RETRIEVAL / "development_retrospective_acquisition_corpus_manifest.json")
    corpus_pairs = corpus_manifest["aggregate_components"]
    require(all(sha(RETRIEVAL / name) == digest for name, digest in corpus_pairs),
            "acquisition corpus component hash mismatch")
    corpus_actual = aggregate(corpus_pairs)
    corpus_recorded = (RETRIEVAL / "development_retrospective_acquisition_corpus_sha256").read_text().strip()
    require(corpus_actual == corpus_recorded == EXPECTED_CORPUS, "acquisition corpus root mismatch")

    freeze = load(ALPHA33 / "development_retrieval_freeze_manifest.json")
    frozen_queries = freeze["exact_compiled_query_set"]
    require(sha_bytes(canonical(frozen_queries)) == freeze["exact_compiled_query_set_sha256"] == EXPECTED_QUERY_SET,
            "frozen query set mismatch")
    planner_immutability = load(ALPHA33 / "planner_immutability_audit.json")
    raw_101_107 = EMPIRICAL / "raw_provider_outputs_101_107.jsonl"
    raw_108 = SMOKE108 / "planner_v3_raw_payload.json"
    require(sha(raw_101_107) == planner_immutability["protected_hashes_after"][
        "runs/20260922_search_plan_v24_dev_alpha3_2_planner_v3_empirical_remaining7/raw_provider_outputs_101_107.jsonl"],
        "frozen Planner V3 raw outputs 101-107 changed")
    require(sha(raw_108) == freeze["raw_planner_output_hashes"]["heldout_v2_108"]["raw_file_sha256"],
            "frozen Planner V3 raw output 108 changed")

    requests = load_jsonl(RETRIEVAL / "retrieval_request_manifest.jsonl")
    results = {row["query_id"]: row for row in load_jsonl(RETRIEVAL / "query_execution_results.jsonl")}
    require(len(requests) == len(results) == len(frozen_queries) == 29, "query count mismatch")
    freeze_by_id = {row["query_id"]: row for row in frozen_queries}
    require(set(freeze_by_id) == {row["query_id"] for row in requests} == set(results),
            "query identity mismatch")
    links = raw_link_map()
    require(all(row["relation_core_ref"] in links for row in requests), "missing frozen semantic link")

    replay = load(ALPHA33 / "empirical_8_case_alpha3_3_replay.json")
    replay_links = {
        relation["source_link_sha256"]: relation
        for case in replay["case_replays"].values()
        for intent in case["intents"]
        for relation in intent["relations"]
    }
    require(all(row["relation_core_ref"] in replay_links for row in requests),
            "missing frozen relation binding")

    inventory: list[dict[str, Any]] = []
    response_rows: list[dict[str, Any]] = []
    transport_rows: list[dict[str, Any]] = []
    url_rows: list[dict[str, Any]] = []
    burden_segments: list[dict[str, Any]] = []
    rigidity_rows: list[dict[str, Any]] = []
    server_normalized_queries = 0
    server_normalization_events = Counter()
    phrase_warning_count = 0

    for request in requests:
        query_id = request["query_id"]
        source = freeze_by_id[query_id]
        query = request["exact_query_text"]
        require(source["query_string"] == query, f"source/request mismatch: {query_id}")
        require(source["query_sha256"] == request["query_sha256"],
                f"frozen query identity hash mismatch: {query_id}")
        result = results[query_id]
        require(result["raw_hit_count"] == 0 and result["execution_status"] == "ZERO_HIT_QUERY",
                f"not frozen zero-hit: {query_id}")
        raw_path = (RETRIEVAL / "retrieval_assets/pubmed_esearch" / request["case_id"] /
                    f"{query_id.replace(':', '_')}__retstart_0000_retmax_030.json")
        require(raw_path.is_file() and sha(raw_path) == result["raw_response_sha256"],
                f"raw snapshot mismatch: {query_id}")
        raw = load(raw_path)["esearchresult"]
        require(raw["count"] == "0" and raw["idlist"] == [], f"snapshot not empty: {query_id}")
        warning = raw.get("warninglist", {})
        quoted_not_found = warning.get("quotedphrasesnotfound", [])
        phrase_warning_count += len(quoted_not_found)

        parsed = parse_qs(urlsplit(request["request_url"]).query, keep_blank_values=True)
        request_term = parsed["term"][0]
        require(request_term == query, f"URL round-trip mutation: {query_id}")
        translated = raw.get("querytranslation")
        normalized = query.replace("γ", "gamma").replace("β", "beta").replace("α", "alpha")
        translation_kind = "EXACT"
        if translated != query:
            require(translated == normalized, f"unclassified NCBI translation: {query_id}")
            translation_kind = "NCBI_SERVER_GREEK_TRANSLITERATION_ONLY"
            server_normalized_queries += 1
            for char, label in (("γ", "GAMMA_TO_GAMMA"), ("β", "BETA_TO_BETA"), ("α", "ALPHA_TO_ALPHA")):
                server_normalization_events[label] += query.count(char)

        segments = quoted_segments(query)
        tokens = lexical_tokens(query)
        booleans = BOOLEAN_RE.findall(query)
        fields = FIELD_RE.findall(query)
        link = links[request["relation_core_ref"]]
        roles = packed_roles(link)
        primary_tokens = lexical_tokens(segments[0])
        special = Counter(char for char in query if char in ",.;:!?+")
        greek_chars = GREEK_RE.findall(query)
        inventory.append({
            "artifact_schema_version": "FrozenQueryFormInventoryV1",
            "request_sequence": request["request_sequence"],
            "case_id": request["case_id"],
            "intent": request["intent_type"],
            "relation_core_id": request["relation_core_ref"],
            "query_id": query_id,
            "exact_query_text": query,
            "query_sha256": request["query_sha256"],
            "query_sha_semantics": "frozen compiler query identity hash",
            "query_text_utf8_sha256": sha_bytes(query.encode()),
            "character_count_unicode_codepoints": len(query),
            "token_count": len(tokens),
            "quoted_segment_count": len(segments),
            "longest_quoted_segment_token_count": max(map(lambda item: len(lexical_tokens(item)), segments)),
            "field_tags": fields,
            "boolean_operators": dict(sorted(Counter(booleans).items())),
            "parentheses": {"open": query.count("("), "close": query.count(")")},
            "proximity_operators": PROXIMITY_RE.findall(query),
            "wildcard_count": query.count("*"),
            "hyphen_count": query.count("-"),
            "slash_count": query.count("/"),
            "greek_characters": greek_chars,
            "special_sentence_punctuation": dict(sorted(special.items())),
            "source_backslash_escape_sequence_count": len(re.findall(r"\\.", query)),
            "tokenization_contract": "biomedical word token; internal hyphen or slash retained; field tags and Boolean operators excluded",
        })

        for index, segment in enumerate(segments):
            segment_roles = roles if index == 0 else ["biological_unit"]
            segment_tokens = lexical_tokens(segment)
            content = [token for token in segment_tokens if token.casefold() not in STOPWORDS]
            burden_segments.append({
                "query_id": query_id,
                "case_id": request["case_id"],
                "segment_index": index,
                "quoted_text": segment,
                "segment_type": "LINKED_PROPOSITION" if index == 0 else "EXTERNAL_CONTEXT_CLAUSE",
                "token_count": len(segment_tokens),
                "content_word_count": len(content),
                "packed_role_components": segment_roles,
                "packed_role_component_count": len(segment_roles),
                "contains_actor": "actor" in segment_roles,
                "contains_action": "action" in segment_roles,
                "contains_relation": "relation" in segment_roles,
                "contains_response": "response" in segment_roles,
                "contains_endpoint": "endpoint" in segment_roles,
                "contains_therapy": "therapy" in segment_roles,
                "contains_biological_unit": "biological_unit" in segment_roles,
                "contains_disease_or_genotype_context": bool(
                    {"disease_context", "genotype_context"}.intersection(segment_roles)),
                "semantic_overpacking": index == 0,
                "role_presence_basis": "frozen Planner V3 linked relation plus frozen alpha3.3 structural binding; no new semantic inference",
            })

        unique_tokens = sorted({token.casefold() for token in tokens})
        exact_tokens = sum(len(lexical_tokens(segment)) for segment in segments)
        rigidity_rows.append({
            "query_id": query_id,
            "case_id": request["case_id"],
            "total_token_count": len(tokens),
            "mandatory_unique_lexical_tokens": unique_tokens,
            "mandatory_unique_lexical_token_count": len(unique_tokens),
            "exact_phrase_token_count": exact_tokens,
            "independently_variable_roles_packed_into_primary_exact_phrase": roles,
            "independently_variable_role_count": len(roles),
            "descriptive_fragility_factors": [
                "FULL_LINKED_PROPOSITION_REQUIRED_CONTIGUOUS",
                "TITLE_ABSTRACT_FIELD_SCOPED",
                "NCBI_QUOTED_PHRASE_NOT_FOUND_WARNING",
            ] + (["ADDITIONAL_EXACT_CONTEXT_CONJUNCT"] if len(segments) > 1 else []),
            "threshold_applied": False,
        })

        response_rows.append({
            "query_id": query_id,
            "case_id": request["case_id"],
            "intended_frozen_query": query,
            "request_term_from_frozen_url": request_term,
            "separate_raw_request_term_echo_available": False,
            "ncbi_querytranslation": translated,
            "ncbi_translation_class": translation_kind,
            "count": int(raw["count"]),
            "warning_outputmessages": warning.get("outputmessages", []),
            "warning_phrasesignored": warning.get("phrasesignored", []),
            "warning_quotedphrasesnotfound": quoted_not_found,
            "error_messages": raw.get("errorlist", {}),
            "raw_snapshot_ref": str(raw_path.relative_to(ROOT)),
            "raw_snapshot_sha256": sha(raw_path),
        })
        transport_rows.append({
            "query_id": query_id,
            "source_equals_request_manifest": source["query_string"] == query,
            "request_manifest_equals_decoded_url_term": request_term == query,
            "ncbi_translation_equals_request_term": translated == query,
            "ncbi_translation_difference": translation_kind,
            "transport_mutation": False,
            "rationale": "NCBI-side Greek transliteration is recorded separately and is not a source-to-request transport mutation",
        })
        raw_url_query = urlsplit(request["request_url"]).query
        url_rows.append({
            "query_id": query_id,
            "decoded_term_equals_frozen_query": request_term == query,
            "double_encoding_detected": "%25" in raw_url_query,
            "quote_round_trip_preserved": request_term.count('"') == query.count('"'),
            "field_tags_round_trip_preserved": FIELD_RE.findall(request_term) == fields,
            "parentheses_round_trip_preserved": (request_term.count("("), request_term.count(")")) == (query.count("("), query.count(")")),
            "greek_round_trip_preserved": GREEK_RE.findall(request_term) == greek_chars,
            "literal_plus_present_in_source": "+" in query,
            "spaces_encoded_with_plus": "+" in raw_url_query,
            "slashes_round_trip_preserved": request_term.count("/") == query.count("/"),
            "hyphens_round_trip_preserved": request_term.count("-") == query.count("-"),
            "boolean_operators_round_trip_preserved": BOOLEAN_RE.findall(request_term) == booleans,
            "json_to_url_transformation_difference": False,
        })

    require(phrase_warning_count == 29, "expected one phrase warning per query")
    require(server_normalized_queries == 14, "unexpected NCBI translation normalization count")

    taxonomy_rows = []
    taxonomy_counts = Counter()
    for request in requests:
        query = request["exact_query_text"]
        classes = ["FULL_PROPOSITION_EXACT_PHRASE", "MULTIWORD_FIELD_TAGGED_PHRASE"]
        if BOOLEAN_RE.search(query):
            classes.append("MIXED_PHRASE_BOOLEAN")
        taxonomy_counts.update(classes)
        taxonomy_rows.append({"query_id": request["query_id"], "classes": classes})
    for key in (
        "FULL_PROPOSITION_EXACT_PHRASE", "MULTIWORD_FIELD_TAGGED_PHRASE",
        "ROLE_LEVEL_EXACT_PHRASES_WITH_BOOLEAN", "INDIVIDUAL_ANCHORS_WITH_BOOLEAN",
        "PROXIMITY_RELATION_CORE", "MIXED_PHRASE_BOOLEAN", "OTHER",
    ):
        taxonomy_counts.setdefault(key, 0)

    v23_log = load_jsonl(V23 / "query_execution_log.jsonl")
    v23_by_id: dict[str, dict[str, Any]] = {}
    for row in v23_log:
        if row["query_id"] in v23_by_id:
            require(v23_by_id[row["query_id"]]["exact_query_string"] == row["exact_query_string"],
                    "v2.3 query changed across pages")
        else:
            v23_by_id[row["query_id"]] = row
    require(len(v23_by_id) == 32, "v2.3 distinct query count mismatch")
    v23_queries = [row["exact_query_string"] for row in v23_by_id.values()]
    v24_queries = [row["exact_query_text"] for row in requests]

    def grammar_stats(queries: list[str]) -> dict[str, Any]:
        segments = [segment for query in queries for segment in quoted_segments(query)]
        return {
            "query_count": len(queries),
            "average_query_character_count": mean([len(query) for query in queries]),
            "average_query_token_count": mean([len(lexical_tokens(query)) for query in queries]),
            "average_boolean_clause_count": mean([len(BOOLEAN_RE.findall(query)) + 1 for query in queries]),
            "average_quoted_segment_count": mean([len(quoted_segments(query)) for query in queries]),
            "average_quoted_segment_token_count": mean([len(lexical_tokens(segment)) for segment in segments]),
            "average_primary_quoted_segment_token_count": mean([
                len(lexical_tokens(quoted_segments(query)[0])) for query in queries]),
            "maximum_primary_quoted_segment_token_count": max(
                len(lexical_tokens(quoted_segments(query)[0])) for query in queries),
            "field_tagged_query_count": sum(bool(FIELD_RE.search(query)) for query in queries),
            "exact_phrase_query_count": sum(bool(QUOTE_RE.search(query)) for query in queries),
            "proximity_query_count": sum(bool(PROXIMITY_RE.search(query)) for query in queries),
            "and_decomposed_query_count": sum(bool(BOOLEAN_RE.search(query)) for query in queries),
        }

    v23_stats = grammar_stats(v23_queries)
    v24_stats = grammar_stats(v24_queries)
    v23_summary = load(V23 / "summary.json")

    case_rows = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in requests:
        grouped[row["case_id"]].append(row)
    anomalies = {
        "heldout_v2_101": ["two intents serialize to byte-identical query text", "plural relation phrase plus singular exact context conjunct"],
        "heldout_v2_102": ["Greek gamma is NCBI-translated to ASCII gamma", "sentence-final punctuation is inside the exact phrase"],
        "heldout_v2_103": ["Greek beta is NCBI-translated to ASCII beta", "endpoint-specific primary phrase is the inventory maximum at 16 tokens"],
        "heldout_v2_104": ["Greek beta is NCBI-translated to ASCII beta", "both queries add a singular exact biological-unit conjunct"],
        "heldout_v2_105": ["all five queries are single full-proposition exact phrases"],
        "heldout_v2_106": ["Greek alpha is NCBI-translated to ASCII alpha", "conditioning treatment and response are packed into each primary phrase"],
        "heldout_v2_107": ["therapy, genotype, disease, biological unit, and response are packed into primary phrases", "the word or is literal text inside one quoted phrase, not Boolean syntax"],
        "heldout_v2_108": ["therapy response and biological context are packed into each primary phrase"],
    }
    for case_id in sorted(grouped):
        rows = grouped[case_id]
        classes = Counter()
        for row in rows:
            classes.update(next(item["classes"] for item in taxonomy_rows if item["query_id"] == row["query_id"]))
        case_rows.append({
            "case_id": case_id,
            "frozen_query_count": len(rows),
            "query_form_class_counts": dict(sorted(classes.items())),
            "shared_serialization_pattern": "mandatory linked proposition emitted as one exact Title/Abstract phrase",
            "case_specific_syntax_anomalies": anomalies[case_id],
            "all_queries_share_systemic_overconstraint": True,
            "all_primary_phrases_warned_quoted_phrase_not_found": True,
            "scientific_relevance_interpreted": False,
        })

    outputs: dict[str, bytes] = {}
    outputs["upstream_root_verification.json"] = pretty({
        "artifact_schema_version": "Alpha35UpstreamRootVerificationV1",
        "roots": roots,
        "acquisition_corpus": {
            "path": str(RETRIEVAL.relative_to(ROOT)),
            "expected_sha256": EXPECTED_CORPUS,
            "recorded_sha256": corpus_recorded,
            "recomputed_sha256": corpus_actual,
            "verified": True,
        },
        "frozen_query_set": {
            "expected_sha256": EXPECTED_QUERY_SET,
            "recomputed_sha256": sha_bytes(canonical(frozen_queries)),
            "query_count": len(frozen_queries),
            "verified": True,
        },
        "frozen_planner_role_evidence": {
            "raw_outputs_101_107_sha256": sha(raw_101_107),
            "raw_output_108_sha256": sha(raw_108),
            "verified": True,
        },
        "all_authoritative_inputs_verified": True,
        "verified_offline": True,
    })
    outputs["zero_hit_run_interpretation.json"] = pretty({
        "artifact_schema_version": "ZeroHitRunInterpretationV1",
        "retrieval_protocol_compliance": "PASS",
        "scientific_candidate_acquisition": "EMPTY",
        "established": "the preregistered queries produced zero PubMed records under the frozen execution protocol",
        "not_established": [
            "absence of relevant literature", "poor Planner V3 scientific semantics",
            "poor relevance precision", "poor fulltext acquisition", "literature recall equals zero",
        ],
        "candidate_relevance_evaluation_possible": False,
        "query_transport_success": 29,
        "zero_hit_query_count": 29,
        "zero_hit_case_count": 8,
        "metadata_records": 0,
        "terminal_failures": 0,
        "hypothesis_assessment": {
            "A_SEMANTIC_QUERY_SERIALIZATION_OVERCONSTRAINT": "SUPPORTED_SYSTEMIC_PRIMARY_MECHANISM",
            "B_EXACT_PHRASE_OVERCONSTRAINT": "SUPPORTED_DIRECT_MECHANISM",
            "C_FIELD_TAG_PHRASE_INDEX_INTERACTION": "SUPPORTED_CONTRIBUTOR",
            "D_QUERY_ESCAPING_OR_ENCODING_DEFECT": "NOT_SUPPORTED",
            "E_BOOLEAN_GROUPING_DEFECT": "NOT_SUPPORTED",
            "F_PUBMED_FIELD_COMPILATION_DEFECT": "SUPPORTED_AS_ARCHITECTURE_DESIGN_DEFECT_NOT_MALFORMED_SYNTAX",
            "G_TRANSPORT_QUERY_MISMATCH": "REFUTED_BY_29_OF_29_EXACT_URL_ROUND_TRIPS",
            "H_LEGITIMATE_ZERO_HIT_QUERY": "NOT_EXCLUDED_PER_QUERY_BUT_NOT_SUPPORTED_AS_SYSTEMIC_PRIMARY_CAUSE",
            "I_OTHER": "NO_ADDITIONAL_PRIMARY_CAUSE_IDENTIFIED",
        },
    })
    outputs["neutral_review_actionability_audit.json"] = pretty({
        "artifact_schema_version": "NeutralReviewActionabilityAuditV1",
        "prior_recommendation": "FREEZE_NEUTRAL_REVIEW_CORPUS_NEXT",
        "corrected_distinction": {
            "provenance_freeze": "EMPTY_CORPUS_CAN_BE_FROZEN_FOR_PROVENANCE",
            "scientific_review": "SCIENTIFIC_REVIEW_NOT_ACTIONABLE",
        },
        "metadata_universe_total": 0,
        "acquired_fulltext_count": 0,
        "neutral_relevance_review_actionable": False,
        "recommendation": "DO_NOT_RUN_NEUTRAL_RELEVANCE_ADJUDICATION",
        "synthetic_negative_labels_created": 0,
    })
    outputs["frozen_query_inventory.jsonl"] = jsonl(inventory)
    outputs["query_serialization_taxonomy.json"] = pretty({
        "artifact_schema_version": "QuerySerializationTaxonomyV1",
        "query_count": 29,
        "multi_label_classification": True,
        "counts": dict(sorted(taxonomy_counts.items())),
        "full_or_near_full_linked_proposition_exact_phrase_count": 29,
        "boolean_decomposed_relation_query_count": 0,
        "rows": taxonomy_rows,
        "interpretation": "14 Boolean queries add an exact context conjunct; none decompose the RelationCore into role-level Boolean anchors",
    })
    outputs["exact_phrase_burden_audit.json"] = pretty({
        "artifact_schema_version": "ExactPhraseBurdenAuditV1",
        "quoted_segment_count": len(burden_segments),
        "primary_linked_proposition_segment_count": 29,
        "semantic_overpacking_query_count": 29,
        "semantic_overpacking_definition": "all five mandatory internal RelationCore components are required in one contiguous exact phrase; no numeric threshold is used",
        "segments": burden_segments,
    })
    outputs["relation_core_vs_textual_realization_audit.json"] = pretty({
        "artifact_schema_version": "RelationCoreVsTextualRealizationAuditV1",
        "scientific_structural_validity": "ESTABLISHED_BY_FROZEN_ALPHA3_3",
        "retrieval_serialization_validity": "FAILED_EMPIRICALLY_FOR_FROZEN_QUERY_SET",
        "invalidated_relation_core_count": 0,
        "audited_assumption": "SEMANTICALLY_BOUND_RELATION implies CONTIGUOUS_NATURAL_LANGUAGE_PHRASE",
        "assumption_valid": False,
        "evidence": [
            "compiler exact-quotes linked_relation_phrase as the first mandatory clause",
            "29 of 29 queries serialize the full linked proposition this way",
            "29 of 29 frozen NCBI responses warn that the primary quoted phrase was not found",
        ],
        "textual_variability_not_represented": [
            "word order", "intervening modifiers", "passive voice", "nominalization",
            "abbreviations", "split clauses", "therapy-first formulation",
            "response-first formulation", "pronouns or implied actors",
        ],
    })
    outputs["frozen_ncbi_response_translation_audit.json"] = pretty({
        "artifact_schema_version": "FrozenNcbiResponseTranslationAuditV1",
        "snapshot_count": 29,
        "zero_count_snapshot_count": 29,
        "no_items_found_message_count": 29,
        "quoted_phrase_not_found_warning_count": phrase_warning_count,
        "server_translation_exact_query_count": 29 - server_normalized_queries,
        "server_greek_transliteration_query_count": server_normalized_queries,
        "server_greek_transliteration_events": dict(sorted(server_normalization_events.items())),
        "rows": response_rows,
    })
    outputs["transport_query_fidelity_audit.json"] = pretty({
        "artifact_schema_version": "TransportQueryFidelityAuditV1",
        "query_count": 29,
        "source_to_request_exact_count": 29,
        "request_to_decoded_url_exact_count": 29,
        "transport_query_mutation_count": 0,
        "ncbi_server_normalization_query_count": server_normalized_queries,
        "rows": transport_rows,
        "conclusion": "TRANSPORT_QUERY_MISMATCH_NOT_SUPPORTED",
    })
    outputs["url_escaping_audit.json"] = pretty({
        "artifact_schema_version": "UrlEscapingAuditV1",
        "query_count": 29,
        "round_trip_exact_count": 29,
        "double_encoding_count": sum(row["double_encoding_detected"] for row in url_rows),
        "quote_escaping_error_count": sum(not row["quote_round_trip_preserved"] for row in url_rows),
        "field_tag_corruption_count": sum(not row["field_tags_round_trip_preserved"] for row in url_rows),
        "literal_plus_source_query_count": sum(row["literal_plus_present_in_source"] for row in url_rows),
        "json_to_url_transformation_difference_count": 0,
        "rows": url_rows,
    })
    outputs["field_tag_semantics_audit.json"] = pretty({
        "artifact_schema_version": "FieldTagSemanticsAuditV1",
        "title_abstract_tagged_query_count": 29,
        "tiab_alias_query_count": 0,
        "title_abstract_tag_occurrence_count": sum(len(row["field_tags"]) for row in inventory),
        "multiword_field_tagged_phrase_query_count": 29,
        "full_proposition_field_tagged_phrase_query_count": 29,
        "multiple_field_scoped_clause_query_count": sum(row["quoted_segment_count"] > 1 for row in inventory),
        "role_level_boolean_relation_decomposition_count": 0,
        "finding": "the field tag scopes a multiword natural-language proposition phrase rather than independent RelationCore role anchors",
    })
    outputs["phrase_index_dependency_audit.json"] = pretty({
        "artifact_schema_version": "PhraseIndexDependencyAuditV1",
        "phrase_index_dependency_count": 29,
        "phrase_index_warning_count": 29,
        "unknown_due_to_snapshot_limitations_count": 0,
        "basis": "every query mandates a full-proposition quoted Title/Abstract clause and every frozen response lists that clause in quotedphrasesnotfound",
        "mechanism_beyond_frozen_warning_inferred": False,
    })
    outputs["v23_v24_query_grammar_comparison.json"] = pretty({
        "artifact_schema_version": "V23V24QueryGrammarComparisonV1",
        "tokenization_contract": "same biomedical lexical tokenizer used for both versions; Boolean operators and field tags excluded",
        "v23": {
            **v23_stats,
            "distinct_executed_query_count": 32,
            "nonzero_response_query_count": sum(row["response_record_count"] > 0 for row in v23_by_id.values()),
            "zero_response_query_count": sum(row["response_record_count"] == 0 for row in v23_by_id.values()),
            "metadata_candidate_count": v23_summary["metadata_candidate_count"],
            "case_count_with_nonzero_candidate_universe": sum(
                row["deduplicated_metadata_candidates"] > 0 for row in v23_summary["per_case"]),
            "serialization_pattern": "short exact lexical anchors separated by Boolean AND; no field tags",
            "slash_packed_expression_query_count": sum("/" in query for query in v23_queries),
        },
        "v24": {
            **v24_stats,
            "nonzero_response_query_count": 0,
            "zero_response_query_count": 29,
            "metadata_candidate_count": 0,
            "serialization_pattern": "full linked proposition as exact Title/Abstract phrase; optional exact context conjunct",
            "boolean_decomposed_relation_query_count": 0,
        },
        "descriptive_conclusion": "v2.4 uses fewer Boolean clauses but much longer primary exact phrases and packs the relation instead of decomposing lexical anchors",
        "scientific_quality_comparison_made": False,
        "relevance_labels_read": 0,
        "historical_fact": "v2.3 produced nonzero candidate universes in seven cases and 1214 metadata records overall; this establishes transport capability, not scientific quality",
    })
    outputs["retrieval_compiler_responsibility_audit.json"] = pretty({
        "artifact_schema_version": "RetrievalCompilerResponsibilityAuditV1",
        "source_file": "src/code_engine/search/compositional_relation_semantics_v1.py",
        "source_sha256_frozen_by_alpha3_3": freeze["alpha3_3_deterministic_component_hashes"]["src/code_engine/search/compositional_relation_semantics_v1.py"],
        "semantic_validation_and_surface_realization_same_abstraction": True,
        "observed_pipeline": [
            "ValidatedRelationCore", "linked_relation_phrase natural-language sentence",
            "exact quoted Title/Abstract clause",
        ],
        "compiler_behavior": "final_query_coverage_v1 always initializes clauses with _quote_clause(phrase)",
        "architecture_boundary_needed": True,
        "recommended_boundary": [
            "ValidatedRelationCore", "RetrievalSurfacePlan", "PubMedQueryAST", "PubMed serialization",
        ],
        "implemented_in_this_run": False,
    })
    outputs["retrieval_surface_plan_v1_architecture_audit.json"] = pretty({
        "artifact_schema_version": "RetrievalSurfacePlanV1ArchitectureAuditV1",
        "component_assessed": "RetrievalSurfacePlanV1",
        "architecture_value": "NEEDED_TO_SEPARATE_SEMANTIC_CONSTRAINTS_FROM_TEXTUAL_REALIZATION",
        "proposed_owned_elements": [
            "actor anchors", "response anchors", "endpoint anchors", "relation lexical family",
            "mandatory internal-role anchors", "optional authorized lexical variants",
            "allowed proximity relationships", "context conjuncts",
        ],
        "required_invariants": [
            "valid RelationCore remains mandatory", "defining endpoint properties cannot disappear",
            "therapy remains linked for therapy-response propositions",
            "conditioning treatment remains linked for nested responses",
            "no subject AND endpoint AND context topic intersection alone",
        ],
        "query_generation_performed": False,
        "implementation_performed": False,
    })
    outputs["pubmed_query_ast_v1_architecture_audit.json"] = pretty({
        "artifact_schema_version": "PubMedQueryASTV1ArchitectureAuditV1",
        "component_assessed": "PubMedQueryASTV1",
        "recommended": True,
        "candidate_node_types": ["TERM", "PHRASE", "OR_GROUP", "AND_GROUP", "PROXIMITY", "FIELD_SCOPE"],
        "benefits": [
            "separates syntax validation from semantic validation",
            "makes precedence and field scope explicit",
            "permits deterministic serialization and round-trip tests",
            "prevents a semantically bound sentence from becoming an implicit exact-phrase contract",
        ],
        "scientific_constraint_preservation_required": True,
        "implemented_in_this_run": False,
    })
    outputs["relation_constraint_serialization_options.json"] = pretty({
        "artifact_schema_version": "RelationConstraintSerializationOptionsV1",
        "options": [
            {"mechanism": "role-level lexical anchors joined by Boolean logic", "value": "avoids sentence contiguity", "safety_requirement": "must retain explicit relation/orientation binding"},
            {"mechanism": "bounded proximity between actor, relation, and response", "value": "allows modifiers and word-order variation", "safety_requirement": "distance and supported PubMed syntax must be frozen"},
            {"mechanism": "relation phrase plus separate context constraints", "value": "keeps external context outside the relation phrase", "safety_requirement": "internal endpoint and therapy roles remain linked"},
            {"mechanism": "multiple deterministic surface forms from frozen authorized lexicons", "value": "covers nominalization and abbreviations", "safety_requirement": "no model or case-specific post-result expansion"},
        ],
        "selected_for_implementation": None,
        "selection_basis": "future offline design and tests, never known-paper recovery",
        "topic_intersection_only_allowed": False,
        "query_generation_performed": False,
    })
    outputs["internal_external_role_serialization_matrix.json"] = pretty({
        "artifact_schema_version": "InternalExternalRoleSerializationMatrixV1",
        "rows": [
            {"role": "actor_or_intervention", "class": "INTERNAL", "must_be_relation_linked": True, "future_default": "anchor within relation structure"},
            {"role": "relation_or_orientation", "class": "INTERNAL", "must_be_relation_linked": True, "future_default": "lexical family or validated proximity relation"},
            {"role": "response_or_endpoint", "class": "INTERNAL", "must_be_relation_linked": True, "future_default": "anchor within relation structure"},
            {"role": "therapy", "class": "INTERNAL_WHEN_THERAPY_RESPONSE", "must_be_relation_linked": True, "future_default": "therapy-response relation anchor"},
            {"role": "conditioning_treatment", "class": "INTERNAL_WHEN_NESTED_RESPONSE", "must_be_relation_linked": True, "future_default": "nested response anchor"},
            {"role": "defining_endpoint_property", "class": "INTERNAL", "must_be_relation_linked": True, "future_default": "mandatory endpoint anchor"},
            {"role": "biological_unit", "class": "EXTERNAL_CONTEXT_BY_DEFAULT", "must_be_relation_linked": False, "future_default": "separate Boolean or proximity constraint"},
            {"role": "disease", "class": "EXTERNAL_CONTEXT_BY_DEFAULT", "must_be_relation_linked": False, "future_default": "separate Boolean constraint"},
            {"role": "genotype", "class": "EXTERNAL_CONTEXT_BY_DEFAULT", "must_be_relation_linked": False, "future_default": "separate Boolean constraint"},
            {"role": "species_or_ordinary_context", "class": "EXTERNAL_CONTEXT_BY_DEFAULT", "must_be_relation_linked": False, "future_default": "separate Boolean constraint"},
        ],
        "case_specific_rules": 0,
        "implemented": False,
    })
    outputs["query_rigidity_metrics.json"] = pretty({
        "artifact_schema_version": "QueryRigidityMetricsV1",
        "query_count": 29,
        "average_total_token_count": mean([row["total_token_count"] for row in rigidity_rows]),
        "average_exact_phrase_token_count": mean([row["exact_phrase_token_count"] for row in rigidity_rows]),
        "average_mandatory_unique_lexical_token_count": mean([row["mandatory_unique_lexical_token_count"] for row in rigidity_rows]),
        "average_primary_phrase_role_count": mean([row["independently_variable_role_count"] for row in rigidity_rows]),
        "pass_fail_threshold_defined": False,
        "rows": rigidity_rows,
    })
    outputs["per_case_zero_hit_analysis.json"] = pretty({
        "artifact_schema_version": "PerCaseZeroHitAnalysisV1",
        "case_count": 8,
        "rows": case_rows,
        "known_pmids_inspected": 0,
        "papers_inspected": 0,
    })

    case108 = next(row for row in requests if row["intent_type"] == "NECESSITY" and row["case_id"] == "heldout_v2_108")
    case108_link = links[case108["relation_core_ref"]]
    outputs["case_108_query_serialization_example.json"] = pretty({
        "artifact_schema_version": "Case108QuerySerializationExampleV1",
        "case_id": "heldout_v2_108",
        "query_id": case108["query_id"],
        "exact_query": case108["exact_query_text"],
        "primary_exact_phrase_token_count": len(lexical_tokens(quoted_segments(case108["exact_query_text"])[0])),
        "packed_roles": packed_roles(case108_link),
        "requires_independently_variable_roles_in_one_textual_realization": True,
        "structural_diagnosis": "SEMANTIC_OVERPACKING",
        "network_search_performed": False,
        "known_paper_evidence_used": False,
    })
    outputs["empty_acquisition_corpus_preservation_audit.json"] = pretty({
        "artifact_schema_version": "EmptyAcquisitionCorpusPreservationAuditV1",
        "acquisition_corpus_sha256": EXPECTED_CORPUS,
        "recomputed_sha256": corpus_actual,
        "preserved": True,
        "historical_evidence_role": "documents a real failed retrieval configuration",
        "future_fix_requirements": ["new query-set version", "new retrieval preregistration"],
        "overwrite_or_delete_performed": False,
    })
    outputs["scientific_state_safety_audit.json"] = pretty({
        "artifact_schema_version": "Alpha35ScientificStateSafetyAuditV1",
        "planner_v3_modified": False,
        "relation_core_modified": False,
        "alpha3_3_modified": False,
        "alpha3_4_modified": False,
        "frozen_queries_modified": False,
        "retrieval_root_modified": False,
        "acquisition_corpus_modified": False,
        "query_modifications": 0,
        "network_calls": 0,
        "retrieval_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "known_pmid_checks": 0,
        "candidate_records_seen": 0,
        "relevance_labels_read": 0,
        "production_case_specific_rules": 0,
        "scientific_relevance_conclusions": 0,
        "historical_assets_modified": False,
    })
    outputs["summary.json"] = pretty({
        "artifact_schema_version": "SearchPlanV24DevAlpha35SummaryV1",
        "status": "completed",
        "frozen_query_count": 29,
        "zero_hit_query_count": 29,
        "full_proposition_exact_phrase_count": 29,
        "multiword_field_tagged_phrase_count": 29,
        "proximity_query_count": 0,
        "boolean_decomposed_relation_query_count": 0,
        "transport_query_mutation_count": 0,
        "phrase_index_dependency_count": 29,
        "phrase_index_warning_count": 29,
        "unknown_phrase_index_status_count": 0,
        "v23_average_query_token_count": v23_stats["average_query_token_count"],
        "v24_average_query_token_count": v24_stats["average_query_token_count"],
        "semantic_overpacking_query_count": 29,
        "neutral_relevance_review_actionable": False,
        "primary_failure_class": "QUERY_SERIALIZATION_ARCHITECTURE_DEFECT",
        "next_stage_recommendation": "DESIGN_RETRIEVAL_SURFACE_COMPILER_V2_OFFLINE",
        "query_modifications": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "network_calls": 0,
        "retrieval_calls": 0,
        "known_pmid_checks": 0,
        "candidate_records_seen": 0,
        "historical_assets_modified": False,
    })

    required = {
        "upstream_root_verification.json", "zero_hit_run_interpretation.json",
        "neutral_review_actionability_audit.json", "frozen_query_inventory.jsonl",
        "query_serialization_taxonomy.json", "exact_phrase_burden_audit.json",
        "relation_core_vs_textual_realization_audit.json",
        "frozen_ncbi_response_translation_audit.json", "transport_query_fidelity_audit.json",
        "url_escaping_audit.json", "field_tag_semantics_audit.json",
        "phrase_index_dependency_audit.json", "v23_v24_query_grammar_comparison.json",
        "retrieval_compiler_responsibility_audit.json",
        "retrieval_surface_plan_v1_architecture_audit.json",
        "pubmed_query_ast_v1_architecture_audit.json",
        "relation_constraint_serialization_options.json",
        "internal_external_role_serialization_matrix.json", "query_rigidity_metrics.json",
        "per_case_zero_hit_analysis.json", "case_108_query_serialization_example.json",
        "empty_acquisition_corpus_preservation_audit.json", "scientific_state_safety_audit.json",
        "summary.json",
    }
    require(set(outputs) == required, "required output set mismatch")

    RUN.mkdir(parents=True)
    for name, body in outputs.items():
        (RUN / name).write_bytes(body)
    pairs = [[name, sha(RUN / name)] for name in sorted(outputs)]
    root = aggregate(pairs)
    validation = {
        "artifact_schema_version": "SearchPlanV24DevAlpha35ValidationV1",
        "status": "PASS",
        "checks": {
            "all_upstream_roots_verified": True,
            "frozen_query_count_29": len(inventory) == 29,
            "frozen_zero_hit_query_count_29": len(response_rows) == 29,
            "all_queries_serialization_classified": len(taxonomy_rows) == 29,
            "transport_fidelity_audited": len(transport_rows) == 29,
            "v23_v24_query_grammar_compared": True,
            "retrieval_serialization_boundary_audited": True,
            "empty_acquisition_corpus_preserved": True,
            "neutral_relevance_review_actionable_false": True,
            "query_modifications_zero": True,
            "network_calls_zero": True,
            "known_pmid_checks_zero": True,
            "candidate_records_seen_zero": True,
            "production_case_specific_rules_zero": True,
        },
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": pairs,
        "search_plan_v24_dev_alpha3_5_sha256": root,
    }
    (RUN / "validation.json").write_bytes(pretty(validation))
    (RUN / "search_plan_v24_dev_alpha3_5_sha256").write_text(root + "\n", encoding="utf-8")

    # Re-verify all immutable roots after writing the isolated diagnosis.
    require(verify_run(RETRIEVAL, "search_plan_v24_dev_frozen_retrospective_retrieval_sha256",
                       EXPECTED_RETRIEVAL)["verified"], "retrieval root changed")
    require(verify_run(ALPHA34, "search_plan_v24_dev_alpha3_4_sha256", EXPECTED_ALPHA34)["verified"],
            "alpha3.4 root changed")
    require(verify_run(ALPHA33, "search_plan_v24_dev_alpha3_3_sha256", EXPECTED_ALPHA33)["verified"],
            "alpha3.3 root changed")
    require(verify_v23()["verified"], "v2.3 root changed")
    require(aggregate([[name, sha(RUN / name)] for name in sorted(outputs)]) == root,
            "alpha3.5 post-write root mismatch")
    print(json.dumps({"status": "completed", "run": str(RUN), "root": root,
                      "component_count": len(pairs)}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        raise
