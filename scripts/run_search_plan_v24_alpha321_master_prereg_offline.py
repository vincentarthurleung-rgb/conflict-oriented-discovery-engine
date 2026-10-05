#!/usr/bin/env python3
"""Freeze alpha3.21 fresh-primary master protocol; never perform acquisition."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import candidate_id


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
F = RUNS / "20261004_search_plan_v24_dev_alpha3_20f_final_builder_v4_contract_freeze_offline"
F1 = RUNS / "20261005_search_plan_v24_dev_alpha3_20f1_selected_prompt_hash_authority_audit_offline"
M20 = RUNS / "20261002_search_plan_v24_dev_alpha3_20_post_alpha3_19_development_master_preregistration_offline"
A19 = RUNS / "20261001_search_plan_v24_dev_alpha3_19a_new_source_acquisition_preregistration_offline"
A19_FAILED = RUNS / "20261002_search_plan_v24_dev_alpha3_19a_ncbi_only_source_acquisition"
A19_RESTART = RUNS / "20261002_search_plan_v24_dev_alpha3_19a2_full_six_frame_ncbi_restart"
G19 = RUNS / "20261002_search_plan_v24_dev_alpha3_19g_primary_attempt_closure_offline"
C19 = RUNS / "20261002_search_plan_v24_dev_alpha3_19c_pubmed_metadata_eligibility"
D19 = RUNS / "20261002_search_plan_v24_dev_alpha3_19d_pmc_oa_jats_construction_eligibility"
D1_19 = RUNS / "20261002_search_plan_v24_dev_alpha3_19d1_updateof_resolution_offline"
M19 = RUNS / "20261001_search_plan_v24_dev_alpha3_19_fresh_heldout_attempt2_master_preregistration_offline"
A18 = RUNS / "20261001_search_plan_v24_dev_alpha3_18a5_primary_citation_identity_binding_offline"
A18_CONTRACT = RUNS / "20260927_search_plan_v24_dev_alpha3_18a1_source_contract_resolution_offline"
B18 = RUNS / "20261001_search_plan_v24_dev_alpha3_18b_builder_execution_preregistration_offline"
Q17 = RUNS / "20260927_search_plan_v24_dev_alpha3_17d_independent_quality_adjudication_v2_preregistration_offline"
ARCH = RUNS / "20260927_search_plan_v24_dev_alpha3_16_architecture_freeze_fresh_heldout_v3_preregistration_offline"
C20 = RUNS / "20261002_search_plan_v24_dev_alpha3_20c_builder_v4_development_execution"
D20 = RUNS / "20261003_search_plan_v24_dev_alpha3_20d_deterministic_variant_evaluation_offline"
B20 = RUNS / "20261002_search_plan_v24_dev_alpha3_20b_proposition_abstraction_prompt_freeze_offline"
OUT = RUNS / "20261005_search_plan_v24_primary_alpha3_21_fresh_primary_master_preregistration_offline"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21_master_prereg_sha256"
F_ROOT = "cc76b168c80634510168a759815dbf7ab905d5e67292b3393a6b9c6a537847c6"
F1_ROOT = "1458b853a6647138094a992c5509f750026a2d08fb2f91f5d8468f8b080e5797"
M20_ROOT = "8a8edb619c2ad2a31e4b0f6398ae43e3d05de74ae31baddeb611b0cd3e0cd3e6"
CONTRACT_SHA = "53b50a78694b6ed53369347fa8ade3675fd9d28395735b3607f2e3329871436e"
BUNDLE_SHA = "c9fd917fd44aab8e70face99f3bc1a2630d7177462dbdb09a73fe03821c69158"
PROMPT_SHA = "6af5b7f3cd8b23cc65e4ee9c3e85eb955d760f7f06e88a48722be213454d7592"
SCHEMA_SHA = "e6b65571708d196b9fb7a4b8c4af71f46e8680b4b078a6ebedd9ece28658f1c1"
GROUNDING_SHA = "429a11294f1df2c40564f4249ea9f54ce637824cbca13d3450b7afef83c4717b"
EVIDENCE_SHA = "156424459bd499272f6dba5a466216ffbe72fe96039045ae8bc44dd7b40b5612"
ABSTRACTION_SHA = "5ab84eebd9fb8b6a4d7d7600869c5860aa19fbd815ad6dc4c139a6332550fc99"
QUALITY_SHA = "89009283963c1db3dd00d57917d932b4d0a542dcb27863ad071dc30f8c0cd751"
ENVELOPE_SHA = "25ad0b448a6d7fd9f6598841824c19cab33ba4b40eb92e2c2260d871d06e4a1d"
QUERY_SET_SHA = "45536e1b734d1eeb54e0d111d6878c1b6dee58d1a762ad934d66b7d40089885e"
ARCH_SHA = "ba82369f45c8a4fcee373fb36011e7bd5817af1e9568765ce0be7801518ff5d1"
ARCH_ROOT = "810f39e106d867042bb3ab692e4b1f04c3b39c7227993db63596b47dcdd93335"
CLASSIFICATION = "FRESH_PRIMARY_ALPHA3_21_FULL_PROTOCOL_PREREGISTERED_WITH_FROZEN_BUILDER_V4"
NEXT = "PREREGISTER_ALPHA3_21A_FRESH_SOURCE_ACQUISITION"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def obj(path: Path) -> dict:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


def root_hash(directory: Path, marker: str) -> str:
    require(not any(p.is_symlink() for p in directory.rglob("*")),
            "FROZEN_SYMLINK_FORBIDDEN")
    files = sorted(p for p in directory.rglob("*") if p.is_file()
                   and p.name != marker)
    return sha(canonical([[str(p.relative_to(directory)), digest(p)]
                          for p in files]))


def ref(path: Path, role: str) -> dict:
    return {"artifact_role": role, "artifact_path": str(path.relative_to(ROOT)),
            "sha256": digest(path), "immutable_frozen": True}


def put(name: str, value: object) -> str:
    raw = canonical(value) + b"\n"
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def put_rows(name: str, values: list[dict]) -> str:
    raw = b"".join(canonical(value) + b"\n" for value in values)
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def marker(name: str, value: str) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write((value + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())


def verify_root(directory: Path, marker_name: str, expected: str) -> None:
    require((directory / marker_name).read_text().strip() == expected
            and root_hash(directory, marker_name) == expected,
            "FROZEN_ROOT_MISMATCH:" + marker_name)


def derive_queries() -> list[dict]:
    source = A19 / "alpha3_19_source_query_set.jsonl"
    require(digest(source) == QUERY_SET_SHA
            and (A19 / "alpha3_19_source_query_set_sha256").read_text().strip()
                == QUERY_SET_SHA, "SOURCE_QUERY_AUTHORITY_UNRESOLVED")
    originals = rows(source)
    require(len(originals) == 6
            and [row["ordinal"] for row in originals] == list(range(1, 7))
            and len({row["stratum_id"] for row in originals}) == 6,
            "SOURCE_QUERY_SIX_STRATUM_AUTHORITY_UNRESOLVED")
    derived = []
    for row in originals:
        query = row["query_utf8"]
        require(query.count('"2024/01/01"[Date - Publication]') == 1
                and query.count('"2025/12/31"[Date - Publication]') == 1
                and '"pubmed pmc"[sb]' in query and "pmc[filter]" not in query
                and sha(query.encode("utf-8")) == row["query_sha256"]
                and row["sort"] == "relevance"
                and row["page_size"] == 50
                and row["retstart_sequence"] == [0, 50, 100, 150],
                "SOURCE_QUERY_BASE_TEMPLATE_MISMATCH")
        replacement = query.replace('"2024/01/01"[Date - Publication]',
                                    '"2026/01/01"[Date - Publication]')
        replacement = replacement.replace('"2025/12/31"[Date - Publication]',
                                          '"2026/09/30"[Date - Publication]')
        require(replacement.replace('"2026/01/01"[Date - Publication]',
                                    '"2024/01/01"[Date - Publication]')
                .replace('"2026/09/30"[Date - Publication]',
                         '"2025/12/31"[Date - Publication]') == query,
                "NON_DATE_QUERY_DELTA")
        derived.append({**row, "query_utf8": replacement,
                        "query_sha256": sha(replacement.encode("utf-8")),
                        "publication_window_start": "2026-01-01",
                        "publication_window_end": "2026-09-30",
                        "only_date_interval_changed": True})
    return derived


def build_registry() -> dict:
    base_path = M20 / "alpha3_20_combined_seen_source_registry.jsonl"
    candidate_path = M20 / "alpha3_20_combined_seen_candidate_registry.jsonl"
    g_path = G19 / "alpha3_19_seen_source_registry.jsonl"
    failed_path = A19_FAILED / "source_query_execution_results.jsonl"
    restart_path = A19_RESTART / "source_query_execution_results.jsonl"
    b18_meta_path = A18 / "sampled_source_metadata_records_v2.jsonl"
    c19_meta_path = C19 / "sampled_metadata_records_v3.jsonl"
    raw_candidate_path = C20 / "alpha3_20c_raw_candidate_manifest.jsonl"
    identity_path = D20 / "alpha3_20d_candidate_identity_manifest.jsonl"
    identity_contract_path = B18 / "builder_candidate_identity_contract.json"
    identity_contract = obj(identity_contract_path)
    impl = identity_contract["implementation"]
    require(digest(ROOT / impl["path"]) == impl["sha256"],
            "CANDIDATE_IDENTITY_IMPLEMENTATION_AUTHORITY_MISMATCH")
    base_sources = rows(base_path)
    require(len(base_sources) == len({row["pmid"] for row in base_sources}),
            "BASE_SEEN_SOURCE_DUPLICATE")
    sources: dict[str, dict] = {}
    for row in base_sources:
        pmid = row["pmid"]
        require(pmid.isdecimal(), "INVALID_SEEN_PMID")
        sources[pmid] = {"pmid": pmid, "pmcid": None, "doi": None,
                         "seen_lineages": sorted(row["seen_generations"])}
    g_rows = rows(g_path)
    for row in g_rows:
        require(row["pmid"] in sources, "ALPHA319_G_REGISTRY_NOT_IN_BASE")
        sources[row["pmid"]]["seen_lineages"] = sorted(set(
            sources[row["pmid"]]["seen_lineages"] + row["exposure_lineages"]))
    failed_ids = {str(pmid) for row in rows(failed_path)
                  for pmid in ((row.get("validity") or {}).get("idlist") or [])}
    require(failed_ids and all(pmid.isdecimal() for pmid in failed_ids),
            "FAILED_BRANCH_PMID_IDENTITY_UNRESOLVED")
    additional_failed = len(failed_ids - sources.keys())
    for pmid in failed_ids:
        if pmid not in sources:
            sources[pmid] = {"pmid": pmid, "pmcid": None, "doi": None,
                             "seen_lineages": []}
        sources[pmid]["seen_lineages"] = sorted(set(
            sources[pmid]["seen_lineages"] +
            ["alpha3_19a_failed_partial_valid_page"]))
    restart_ids = {str(pmid) for row in rows(restart_path)
                   for pmid in row["idlist"]}
    require(restart_ids and restart_ids <= sources.keys(),
            "ALPHA319_A2_FROZEN_FRAME_REGISTRY_MISMATCH")
    for pmid in restart_ids:
        sources[pmid]["seen_lineages"] = sorted(set(
            sources[pmid]["seen_lineages"] + ["alpha3_19a2_frozen_source_frame"]))
    prior_development_metadata_paths = sorted(RUNS.glob("*/metadata_records.jsonl"))
    require(prior_development_metadata_paths
            and all("dev" in path.parent.name or "development" in path.parent.name
                    for path in prior_development_metadata_paths),
            "EARLIER_DEVELOPMENT_METADATA_SCOPE_UNRESOLVED")
    prior_development_metadata_rows = []
    for path in prior_development_metadata_paths:
        for row in rows(path):
            pmid = str(row.get("pmid") or "")
            require(pmid.isdecimal(), "EARLIER_DEVELOPMENT_PMID_UNRESOLVED")
            if pmid not in sources:
                sources[pmid] = {"pmid": pmid, "pmcid": None, "doi": None,
                                 "seen_lineages": []}
            sources[pmid]["seen_lineages"] = sorted(set(
                sources[pmid]["seen_lineages"] +
                ["earlier_search_plan_development_metadata"]))
            prior_development_metadata_rows.append(row)

    def bind_alias(pmid: str, key: str, value: str | None) -> None:
        if not value:
            return
        require(pmid in sources and isinstance(value, str),
                "SOURCE_ALIAS_IDENTITY_UNRESOLVED")
        previous = sources[pmid][key]
        require(previous in (None, value), "SOURCE_ALIAS_CONFLICT:" + pmid + ":" + key)
        sources[pmid][key] = value

    for row in g_rows:
        for key in ("pmcid", "doi"):
            bind_alias(row["pmid"], key, row.get(key))
    for row in rows(b18_meta_path):
        if row["state"] == "RESOLVED":
            metadata = row["metadata"]
            require(metadata["pmid"] == row["pmid"],
                    "ALPHA318_METADATA_PRIMARY_IDENTITY_CONFLICT")
            for key in ("pmcid", "doi"):
                bind_alias(row["pmid"], key, metadata.get(key))
    for row in rows(c19_meta_path):
        if row["metadata_state"] == "RESOLVED" and not row["identity_unresolved_reasons"]:
            for key in ("pmcid", "doi"):
                bind_alias(row["pmid"], key, row.get(key))
    for row in prior_development_metadata_rows:
        if row.get("metadata_resolution_status") == "RESOLVED":
            for key in ("pmcid", "doi"):
                bind_alias(str(row["pmid"]), key, row.get(key))
    for key in ("pmcid", "doi"):
        owner: dict[str, str] = {}
        for row in sources.values():
            alias = row[key]
            if alias:
                require(alias not in owner or owner[alias] == row["pmid"],
                        "CROSS_PMID_SOURCE_ALIAS_CONFLICT:" + key)
                owner[alias] = row["pmid"]

    baseline_candidates = rows(candidate_path)
    raw_candidates = rows(raw_candidate_path)
    frozen_identities = rows(identity_path)
    require(len(raw_candidates) == len(frozen_identities) == 126,
            "ALPHA320C_CANDIDATE_UNIVERSE_MISMATCH")
    recomputed = {(candidate_id(row["source_record_token"], row["candidate"]),
                   sha(canonical(row["candidate"]))) for row in raw_candidates}
    frozen = {(row["historical_controller_payload_id"],
               row["candidate_payload_sha256"]) for row in frozen_identities}
    require(recomputed == frozen and len(recomputed) == 126,
            "CANDIDATE_IDENTITY_RECOMPUTATION_MISMATCH")
    candidates: dict[str, dict] = {}
    for row in baseline_candidates:
        candidates[row["candidate_id"]] = {
            "candidate_id": row["candidate_id"],
            "candidate_payload_sha256": row["candidate_payload_sha256"],
            "seen_lineages": [row["seen_generation"]],
            "historical_identity_aliases": []}
    development_aliases = {
        row["historical_controller_payload_id"]: row["development_candidate_id"]
        for row in frozen_identities}
    require(len(development_aliases) == len(frozen_identities)
            and len(set(development_aliases.values())) == len(frozen_identities),
            "DEVELOPMENT_CANDIDATE_IDENTITY_ALIAS_COLLISION")
    for cid, payload in frozen:
        if cid in candidates:
            require(candidates[cid]["candidate_payload_sha256"] == payload,
                    "CANDIDATE_IDENTITY_PAYLOAD_CONFLICT")
            candidates[cid]["seen_lineages"].append("alpha3_20c")
            candidates[cid]["historical_identity_aliases"].append(
                development_aliases[cid])
        else:
            candidates[cid] = {"candidate_id": cid,
                               "candidate_payload_sha256": payload,
                               "seen_lineages": ["alpha3_20c"],
                               "historical_identity_aliases":
                                   [development_aliases[cid]]}
    for row in candidates.values():
        row["seen_lineages"] = sorted(set(row["seen_lineages"]))
    seen_cases = obj(ARCH / "seen_development_case_registry.json")
    require(all(row["status"] == "SEEN_DEVELOPMENT_CASES"
                for row in seen_cases["cases"]),
            "EARLIER_SEEN_DEVELOPMENT_CASE_AUTHORITY_MISMATCH")
    return {"sources": sorted(sources.values(), key=lambda row: int(row["pmid"])),
            "candidates": sorted(candidates.values(), key=lambda row: row["candidate_id"]),
            "seen_development_case_ids": sorted(row["case_id"]
                                                for row in seen_cases["cases"]),
            "failed_partial_unique_pmids": len(failed_ids),
            "failed_partial_new_to_prior_combined_registry": additional_failed,
            "a2_unique_pmids": len(restart_ids),
            "earlier_development_metadata_unique_pmids": len({
                str(row["pmid"]) for row in prior_development_metadata_rows}),
            "input_refs": [ref(path, role) for path, role in (
                (base_path, "alpha3_18_alpha3_19_combined_seen_sources"),
                (candidate_path, "alpha3_18_alpha3_19_combined_seen_candidates"),
                (g_path, "alpha3_19_seen_source_aliases_and_lineages"),
                (failed_path, "alpha3_19_failed_partial_valid_pages"),
                (restart_path, "alpha3_19a2_frozen_source_frames"),
                (b18_meta_path, "alpha3_18_resolved_source_aliases"),
                (c19_meta_path, "alpha3_19_resolved_source_aliases"),
                (raw_candidate_path, "alpha3_20c_raw_candidates"),
                (identity_path, "alpha3_20d_frozen_candidate_identities"),
                (identity_contract_path, "canonical_candidate_identity_contract"),
                (ARCH / "seen_development_case_registry.json",
                 "earlier_seen_development_cases"))] +
                [ref(path, "earlier_search_plan_development_metadata")
                 for path in prior_development_metadata_paths]}


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA321_MASTER_OUTPUT_ALREADY_EXISTS")
    verify_root(F, "search_plan_v24_dev_alpha3_20f_sha256", F_ROOT)
    verify_root(F1, "search_plan_v24_dev_alpha3_20f1_sha256", F1_ROOT)
    verify_root(M20, "search_plan_v24_dev_alpha3_20_master_prereg_sha256", M20_ROOT)
    verify_root(ARCH, "search_plan_v24_dev_alpha3_16_sha256", ARCH_ROOT)
    for directory, marker_name in (
        (A19, "search_plan_v24_dev_alpha3_19a_prereg_sha256"),
        (M19, "search_plan_v24_dev_alpha3_19_master_prereg_sha256"),
        (Q17, "search_plan_v24_dev_alpha3_17d_sha256"),
    ):
        require(root_hash(directory, marker_name) ==
                (directory / marker_name).read_text().strip(),
                "INHERITED_FROZEN_AUTHORITY_ROOT_MISMATCH:" + marker_name)
    required = (
        (F / "search_plan_builder_v4_final_contract.json", CONTRACT_SHA),
        (F / "builder_v4_reproducibility_bundle.json", BUNDLE_SHA),
        (F / "final_selected_builder_v4_prompt.txt", PROMPT_SHA),
        (B20 / "builder_output_schema_v4.json", SCHEMA_SHA),
        (B20 / "builder_grounding_contract_v4.json", GROUNDING_SHA),
        (M20 / "evidence_reference_contract_v4.json", EVIDENCE_SHA),
        (M20 / "proposition_abstraction_contract_v1.json", ABSTRACTION_SHA),
        (M19 / "quality_response_envelope_v3.json", ENVELOPE_SHA),
    )
    require(all(digest(path) == expected for path, expected in required),
            "FROZEN_BUILDER_OR_QUALITY_COMPONENT_MISMATCH")
    require((Q17 / "proposition_quality_adjudication_v2_protocol_sha256")
                .read_text().strip() == QUALITY_SHA
            and obj(F1 / "validation.json")["alpha3_20f1_classification"] ==
                "ALPHA3_20F_REPORT_ONLY_HASH_TRANSCRIPTION_ERROR"
            and obj(F1 / "validation.json")["builder_v4_contract_ready_for_fresh_attempt"]
                is True,
            "FROZEN_QUALITY_OR_F1_AUTHORITY_MISMATCH")
    quality_runtime = obj(M19 / "quality_provider_binding_alpha3_19.json")
    esearch_validity = obj(RUNS /
        "20261002_search_plan_v24_dev_alpha3_19a1_ncbi_esearch_backend_failure_audit_offline/pubmed_esearch_response_validity_v2_1.json")
    require(quality_runtime["provider"] == "DeepSeek"
            and quality_runtime["model"] == "deepseek-flash"
            and quality_runtime["automatic_retry"] is False
            and quality_runtime["scientific_inferences_per_source_group"] == 1
            and esearch_validity["schema_version"] ==
                "PubMedESearchResponseValidityV2_1"
            and digest(ROOT / esearch_validity["implementation"]["path"]) ==
                esearch_validity["implementation"]["sha256"],
            "INHERITED_QUALITY_OR_ESEARCH_RUNTIME_MISMATCH")
    contract = obj(F / "search_plan_builder_v4_final_contract.json")
    require(contract["builder_v4_contract_status"] ==
                "FROZEN_FOR_NEXT_FRESH_PRIMARY_ATTEMPT"
            and contract["selected_abstraction_variant"] == "V1"
            and contract["selected_abstraction_mode"] == "relation_sentence"
            and obj(F / "validation.json")["selected_prompt_byte_identical_to_alpha3_20b_v1"]
                is True,
            "BUILDER_V4_FINAL_STATUS_MISMATCH")
    manifest = obj(ARCH / "architecture_freeze_manifest.json")
    require(manifest["architecture_freeze_sha256"] == ARCH_SHA
            and (ARCH / "architecture_freeze_sha256").read_text().strip() == ARCH_SHA
            and all(digest(ROOT / path) == expected
                    for path, expected in manifest["components"]),
            "SEARCH_PLAN_ARCHITECTURE_AUTHORITY_UNRESOLVED")
    return {"queries": derive_queries(), "registry": build_registry(),
            "architecture_manifest": manifest}


def freeze(state: dict) -> dict:
    OUT.mkdir()
    queries = state["queries"]
    registry = state["registry"]
    seed_preimage = (F1_ROOT + "\n" +
                     "alpha3.21_fresh_primary_sampling_v1").encode("utf-8")
    seed_bytes = hashlib.sha256(seed_preimage).digest()
    seed_sha = sha(seed_bytes)
    for name, root in (("alpha3_20f_root_verification.json", F_ROOT),
                       ("alpha3_20f1_root_verification.json", F1_ROOT)):
        put(name, {"verified": True, "root_sha256": root})
    put("builder_v4_final_contract_binding.json", {
        "contract": ref(F / "search_plan_builder_v4_final_contract.json",
                        "immutable_final_builder_v4_contract"),
        "expected_sha256": CONTRACT_SHA,
        "scientific_modification_allowed": False})
    put("builder_v4_reproducibility_bundle_binding.json", {
        "bundle": ref(F / "builder_v4_reproducibility_bundle.json",
                      "immutable_builder_v4_reproducibility_bundle"),
        "expected_sha256": BUNDLE_SHA})
    put("final_selected_prompt_binding.json", {
        "prompt": ref(F / "final_selected_builder_v4_prompt.txt",
                      "selected_v1_relation_sentence_prompt"),
        "expected_sha256": PROMPT_SHA,
        "selected_variant": "V1", "selected_mode": "relation_sentence",
        "prompt_editing_allowed": False})
    put("alpha3_21_primary_identity.json", {
        "attempt_id": "alpha3.21",
        "classification": "FRESH_PRIMARY_PROPOSITION_CONSTRUCTION_ATTEMPT_ALPHA3_21",
        "fresh_primary_attempt": True, "development_mode": False,
        "alpha3_20_development_closed": True,
        "master_preregistration_only": True})
    put("alpha3_21_publication_window.json", {
        "publication_window_start": "2026-01-01",
        "publication_window_end": "2026-09-30",
        "end_inclusive": True, "outcome_dependent_extension_allowed": False})
    query_sha = put_rows("alpha3_21_source_query_set.jsonl", queries)
    put("alpha3_21_six_stratum_query_authority.json", {
        "base_query_set": ref(A19 / "alpha3_19_source_query_set.jsonl",
                              "alpha3_19_exact_six_source_queries"),
        "derived_query_set": ref(OUT / "alpha3_21_source_query_set.jsonl",
                                 "alpha3_21_date_only_derived_queries"),
        "derived_query_set_sha256": query_sha,
        "source_stratum_count": 6,
        "stratum_ids": [row["stratum_id"] for row in queries],
        "only_query_delta": ["2024/01/01 -> 2026/01/01",
                             "2025/12/31 -> 2026/09/30"],
        "pmc_subset_clause": '"pubmed pmc"[sb]',
        "scientific_query_terms_changed": False,
        "queries_executed_now": 0})
    acquisition = obj(A19 / "source_frame_execution_contract.json")
    require(acquisition["max_records_per_stratum"] == 200
            and acquisition["page_size"] == 50
            and acquisition["max_attempts_per_request"] == 4
            and acquisition["timeout_seconds"] == 60
            and acquisition["sort"] == "relevance"
            and acquisition["stratum_order"] ==
                [row["stratum_id"] for row in queries]
            and acquisition["backoff_seconds"] == [2, 4, 8],
            "ALPHA319_ACQUISITION_POLICY_MISMATCH")
    put("alpha3_21_source_acquisition_policy.json", {
        "inherited_frame_policy": ref(A19 / "source_frame_execution_contract.json",
                                      "frozen_source_frame_policy"),
        "sort": "relevance", "page_size": 50,
        "max_records_per_stratum": 200,
        "max_ordinary_pages_per_stratum": 4,
        "max_attempts_per_page": 4, "timeout_seconds": 60,
        "backoff_seconds": [2, 4, 8],
        "all_frames_before_sampling": True,
        "adaptive_query_expansion": False,
        "network_execution_authorized_now": False})
    put("alpha3_21_esearch_validity_binding.json", {
        "hardened_validator": ref(RUNS /
            "20261002_search_plan_v24_dev_alpha3_19a1_ncbi_esearch_backend_failure_audit_offline/pubmed_esearch_response_validity_v2_1.json",
            "pubmed_esearch_response_validity_v2_1"),
        "required_checks": ["transport_success", "http_status", "json_parseability",
                            "expected_esearch_schema", "ErrorList", "WarningList",
                            "count_idlist_consistency"],
        "execute_now": False})
    source_rows = registry["sources"]
    candidate_rows = registry["candidates"]
    source_registry = {
        "schema_version": "Alpha3_21PreexistingSeenContaminationRegistry",
        "source_identities": source_rows,
        "candidate_identities": candidate_rows,
        "seen_development_case_ids": registry["seen_development_case_ids"],
        "source_input_provenance": registry["input_refs"],
        "candidate_identity_implementation": ref(ROOT /
            "scripts/search_plan_v24_alpha317c_reconcile_builder_offline.py",
            "canonical_pcv2_candidate_identity_implementation"),
        "failed_partial_valid_page_unique_pmids": registry["failed_partial_unique_pmids"],
        "failed_partial_pmids_added_beyond_alpha3_20_combined":
            registry["failed_partial_new_to_prior_combined_registry"],
        "a2_frozen_frame_unique_pmids": registry["a2_unique_pmids"],
        "earlier_development_metadata_unique_pmids":
            registry["earlier_development_metadata_unique_pmids"],
        "seen_unique_pmids": len(source_rows),
        "seen_unique_pmcids": len({row["pmcid"] for row in source_rows
                                   if row["pmcid"]}),
        "seen_unique_dois": len({row["doi"] for row in source_rows
                                 if row["doi"]}),
        "seen_unique_candidate_identities": len(candidate_rows),
        "seen_unique_candidate_payload_hashes": len({
            row["candidate_payload_sha256"] for row in candidate_rows}),
        "future_fresh_source_or_candidate_reuse_prohibited": True}
    registry_sha = put("alpha3_21_seen_contamination_registry.json", source_registry)
    marker("alpha3_21_seen_contamination_registry_sha256", registry_sha)
    put("alpha3_21_candidate_identity_authority.json", {
        "frozen_contract": ref(B18 / "builder_candidate_identity_contract.json",
                               "canonical_candidate_identity_contract"),
        "implementation": ref(ROOT /
            "scripts/search_plan_v24_alpha317c_reconcile_builder_offline.py",
            "canonical_pcv2_candidate_identity_implementation"),
        "alpha3_20c_raw_candidates_recomputed": len(rows(C20 /
            "alpha3_20c_raw_candidate_manifest.jsonl")),
        "alpha3_20d_identity_manifest": ref(D20 /
            "alpha3_20d_candidate_identity_manifest.jsonl",
            "frozen_development_candidate_identity_manifest"),
        "identity_recomputation_matches_frozen_manifest": True,
        "new_identity_function_invented": False})
    put("alpha3_21_freshness_contract.json", {
        "preexisting_registry": ref(OUT /
            "alpha3_21_seen_contamination_registry.json",
            "preexisting_seen_contamination_registry"),
        "pre_sample_exclusion": "exact seen PMID",
        "post_metadata_alias_exclusion": "exact known PMCID or DOI equality",
        "post_sample_alias_contamination_state":
            "POST_SAMPLE_EXACT_SOURCE_CONTAMINATION",
        "semantic_similarity_heuristic": False,
        "source_replacement_after_exclusion": False})
    put("alpha3_21_sampling_order_contract.json", {
        "stage_order": ["acquire_all_frozen_query_frames",
                        "parse_and_validate_all_frames",
                        "deterministic_pmid_dedup_and_earliest_stratum_ownership",
                        "exclude_preexisting_seen_pmids",
                        "freeze_fresh_source_universe",
                        "deterministic_within_stratum_sampling",
                        "metadata_oa_construction_downstream"],
        "dedup_authority": ref(A19 / "cross_stratum_dedup_contract.json",
                               "exact_pmid_earliest_stratum_dedup"),
        "seen_exclusion_before_sampling": True,
        "downstream_outcome_informed_resampling": False})
    put("alpha3_21_sampling_seed_derivation.json", {
        "procedure": "SHA256(UTF8(alpha3_20f1_root + LF + literal_context))",
        "alpha3_20f1_root_ascii": F1_ROOT,
        "literal_context_ascii": "alpha3.21_fresh_primary_sampling_v1",
        "preimage_utf8_hex": seed_preimage.hex(),
        "derived_seed_bytes_hex": seed_bytes.hex(),
        "derived_seed_bytes_sha256": seed_sha,
        "sampling_algorithm_seed_text": seed_bytes.hex(),
        "sampling_algorithm_seed_text_encoding": "lowercase hex ASCII/UTF-8",
        "outcome_dependent_randomness": False})
    put("alpha3_21_sampling_policy.json", {
        "strata": 6, "maximum_per_stratum": 12,
        "maximum_total": 72,
        "sampling_seed_sha256": seed_sha,
        "sampling_algorithm":
            "SHA256(UTF8(seed_hex + ':' + stratum_id + ':' + canonical PMID)); ascending; first 12",
        "sampling_algorithm_authority": ref(RUNS /
            "20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline/source_sampling_algorithm.json",
            "frozen_deterministic_sampling_algorithm_only"),
        "alpha3_19_sample_before_seen_order_inherited": False,
        "take_all_if_less_than_twelve": True,
        "cross_stratum_topup_allowed": False,
        "downstream_replacement_allowed": False,
        "sample_freeze_before_downstream_scientific_outcomes": True})
    put("alpha3_21_metadata_policy_binding.json", {
        "sampled_metadata": ref(A19 / "sampled_metadata_contract.json",
                                "frozen_sampled_pubmed_metadata"),
        "publication_date": ref(A19 / "publication_date_execution_contract.json",
                                "frozen_publication_date_rule"),
        "publication_type": ref(A19 / "publication_type_execution_contract.json",
                                "frozen_publication_type_rule"),
        "correction_reference": ref(A19 /
            "correction_reference_execution_contract.json",
            "frozen_correction_reference_rule"),
        "updateof_resolution_example": ref(D1_19 / "updateof_resolution.json",
            "frozen_updateof_resolution_provenance"),
        "source_type": ref(A18_CONTRACT /
            "source_type_mechanical_eligibility_v1.json",
            "frozen_mechanical_source_type_rule"),
        "on_terminal_source_failure": "exclude_source_without_replacement",
        "scientific_content_rescue_allowed": False})
    put("alpha3_21_pmc_oa_policy_binding.json", {
        "oa_subset": ref(A19 / "pmc_oa_subset_execution_contract.json",
                         "frozen_pmc_oa_subset_rule"),
        "jats": ref(A19 / "pmc_jats_acquisition_contract.json",
                   "frozen_pmc_jats_acquisition_rule"),
        "construction_handoff": ref(A19 / "jats_handoff_manifest_contract.json",
                                    "frozen_jats_handoff_rule"),
        "historical_validation": ref(D19 / "validation.json",
                                     "alpha3_19d_execution_validation"),
        "primary_citation_binding_required": True,
        "article_level_license_required": True,
        "per_source_failure_isolation": True,
        "source_replacement_allowed": False})
    put("alpha3_21_construction_document_binding.json", {
        "document_contract": ref(A18_CONTRACT /
            "construction_evidence_document_v1_contract.json",
            "canonical_construction_evidence_document"),
        "anchor_contract": ref(A18_CONTRACT / "evidence_span_anchor_v1_contract.json",
            "frozen_evidence_span_anchor"),
        "builder_evidence_surface": "canonical BODY only",
        "abstract_quote_surface_allowed": False})
    put("alpha3_21_builder_v4_binding.json", {
        "final_composite_contract": ref(F / "search_plan_builder_v4_final_contract.json",
                                         "frozen_builder_v4_final_contract"),
        "selected_prompt": ref(F / "final_selected_builder_v4_prompt.txt",
                               "frozen_v1_relation_sentence_prompt"),
        "output_schema": ref(B20 / "builder_output_schema_v4.json",
                             "builder_output_schema_v4"),
        "grounding": ref(B20 / "builder_grounding_contract_v4.json",
                         "builder_grounding_contract_v4"),
        "evidence_reference": ref(M20 / "evidence_reference_contract_v4.json",
                                  "evidence_reference_contract_v4"),
        "proposition_abstraction": ref(M20 /
            "proposition_abstraction_contract_v1.json",
            "proposition_abstraction_contract_v1"),
        "source_record_token_role": "OPAQUE_NONSEMANTIC_RESPONSE_BINDING_HANDLE",
        "candidate_cardinality": {"minimum": 0, "maximum": 3},
        "scientific_modification_allowed": False})
    put("alpha3_21_builder_runtime_binding.json", {
        "frozen_runtime_policy": ref(B20 / "alpha3_20c_runtime_policy.json",
                                     "builder_v4_runtime_policy"),
        "provider": "DeepSeek", "model": "deepseek-flash",
        "thinking": "enabled", "reasoning_effort": "high",
        "one_scientific_inference_per_frozen_request": True,
        "one_request_per_valid_construction_source": True,
        "call_count_frozen_at_later_request_freeze": True,
        "calls_authorized_now": 0,
        "completed_invalid_response_scientific_retry": False,
        "zero_candidate_response_scientific_retry": False})
    put("alpha3_21_deterministic_candidate_gate_contract.json", {
        "stage_order": ["schema_and_binding", "v4_exact_body_grounding",
                        "frozen_structural_checks", "frozen_lexical_leakage_gate",
                        "exact_seen_candidate_contamination_gate"],
        "postprocessing": ref(F / "final_builder_v4_postprocessing_order.json",
                              "frozen_builder_v4_postprocessing_order"),
        "grounding": ref(B20 / "builder_grounding_contract_v4.json",
                         "frozen_v4_grounding"),
        "structural_checks": ref(B20 / "structural_completeness_contract.json",
                                 "frozen_structural_completeness"),
        "leakage": ref(B20 / "leakage_policy_preservation.json",
                       "frozen_lexical_leakage_policy"),
        "survivor_state": "FRESH_PRIMARY_DETERMINISTIC_SURVIVOR",
        "survivor_not_quality_pass": True})
    put("alpha3_21_candidate_contamination_gate.json", {
        "registry": ref(OUT / "alpha3_21_seen_contamination_registry.json",
                        "preexisting_exact_candidate_identities"),
        "identity_authority": ref(B18 / "builder_candidate_identity_contract.json",
                                  "canonical_candidate_identity_contract"),
        "exact_candidate_id_or_payload_hash_match_excludes": True,
        "exclusion_state": "EXACT_SEEN_CANDIDATE_CONTAMINATION",
        "semantic_contamination_matching_used": False,
        "replacement_or_rewriting_allowed": False})
    put("alpha3_21_quality_v2_binding.json", {
        "quality_v2_protocol_marker": ref(Q17 /
            "proposition_quality_adjudication_v2_protocol_sha256",
            "quality_v2_scientific_protocol_marker"),
        "quality_v2_protocol_sha256": QUALITY_SHA,
        "overall_eligibility_rule": ref(Q17 /
            "overall_quality_eligibility_rule.json",
            "all_required_pass_quality_eligibility"),
        "one_source_per_call": ref(Q17 /
            "one_source_per_quality_call_contract.json",
            "quality_source_grouping_rule"),
        "zero_input_quality_calls": 0,
        "zero_input_terminal_state": "FRESH_PRIMARY_TERMINATED_WITH_ZERO_QUALITY_INPUT",
        "scientific_rubric_changed": False})
    put("alpha3_21_quality_response_envelope_v3_binding.json", {
        "envelope": ref(M19 / "quality_response_envelope_v3.json",
                        "frozen_quality_response_envelope_v3"),
        "controller_owns_protocol_metadata": True,
        "model_owns_scientific_judgments": True,
        "missing_scientific_judgments_controller_filled": False})
    put("alpha3_21_quality_runtime_binding.json", {
        "provider_binding": ref(M19 / "quality_provider_binding_alpha3_19.json",
                                "frozen_quality_provider_runtime"),
        "provider": "DeepSeek", "model": "deepseek-flash",
        "one_request_per_nonempty_source_group": True,
        "freeze_all_requests_and_candidate_sets_before_execution": True,
        "invalid_completed_response_counts_inference": True,
        "invalid_completed_response_scientific_retry": False,
        "openai_fallback": False,
        "calls_authorized_now": 0})
    put("alpha3_21_final_pool_contract.json", {
        "input": "Quality V2 valid judgments over frozen deterministic survivors",
        "inclusion_rule": "all frozen required Quality V2 criteria PASS",
        "pool_state": "FRESH_PRIMARY_ELIGIBLE_PROPOSITION_POOL",
        "post_quality_hand_selection_allowed": False,
        "human_gold_claim": False,
        "reporting_dimensions": ["sampled_source_count",
            "construction_valid_source_count", "builder_calls",
            "raw_builder_candidate_count", "v4_grounded_count",
            "structural_pass_count", "leakage_pass_count",
            "exact_fresh_candidate_count", "quality_input_count",
            "quality_valid_group_count", "quality_pass_eligible_proposition_count",
            "distinct_eligible_source_group_count"],
        "weighted_score": None})
    put("alpha3_21_hidden_source_provenance_contract.json", {
        "controller_private_bindings_when_available": ["PMID", "PMCID",
            "source_record_token", "evidence_anchor"],
        "originating_source_group_preserved": True,
        "model_visible_retrieval_target_contains_provenance": False})
    put("alpha3_21_future_retrieval_leakage_firewall.json", {
        "forbidden_future_model_visible_fields": ["originating PMID", "PMCID",
            "DOI", "article title as provenance", "source token",
            "hidden evidence anchor", "Quality outcome"],
        "query_target": "scientific proposition only",
        "future_retrieval_authorized_now": False})
    put("alpha3_21_evaluation_readiness_contract.json", {
        "minimum_distinct_eligible_source_groups": 8,
        "below_threshold": "report pool; search_plan_primary_evaluation_ready=false",
        "at_or_above_threshold":
            "search_plan_primary_evaluation_ready=true; separately preregister retrieval",
        "eight_cases_selected_now": False,
        "outcome_dependent_topup_allowed": False})
    put("alpha3_21_search_plan_architecture_binding.json", {
        "prospective_architecture_freeze_manifest": ref(ARCH /
            "architecture_freeze_manifest.json",
            "preexisting_search_plan_v24_architecture_freeze"),
        "architecture_freeze_sha256": ARCH_SHA,
        "architecture_run_root_sha256": ARCH_ROOT,
        "component_count": len(state["architecture_manifest"]["components"]),
        "all_components_verified": True,
        "architecture_modification_allowed": False,
        "retrieval_evaluation_started": False})
    phases = ["alpha3.21A_source_acquisition", "alpha3.21B_dedup_seen_sampling",
              "alpha3.21C_metadata_source_type_correction",
              "alpha3.21D_pmc_oa_jats_construction_source",
              "alpha3.21E_document_builder_request_freeze",
              "alpha3.21F_builder_v4_execution",
              "alpha3.21G_deterministic_candidate_gates",
              "alpha3.21H_quality_v2_request_freeze",
              "alpha3.21I_quality_v2_execution",
              "alpha3.21J_fresh_primary_pool_closure"]
    put("alpha3_21_phase_plan.json", {"ordered_phases": phases,
        "current_stage": "master_preregistration_only",
        "automatic_progression_to_scientific_inference": False})
    put("alpha3_21_phase_barriers.json", {
        "21E_executes_builder": False, "21F_executes_quality": False,
        "21G_modifies_builder": False, "21H_executes_quality": False,
        "21I_starts_retrieval_evaluation": False,
        "phase_transition_requires_separate_authority": True})
    put("alpha3_21_primary_negative_outcome_contract.json", {
        "valid_negative_outcomes": ["zero_fresh_sampled_sources",
            "zero_construction_sources", "zero_builder_candidates",
            "zero_deterministic_survivors", "zero_quality_input",
            "zero_quality_pass_propositions",
            "fewer_than_eight_eligible_source_groups"],
        "convert_negative_primary_to_in_attempt_development": False})
    put("alpha3_21_inference_accounting_initialization.json", {
        "builder": 0, "quality": 0, "other_scientific_llm": 0,
        "provider_calls": 0, "network_calls": 0,
        "master_preregistration_new_inferences": 0})
    put("scientific_policy_nonadaptation_audit.json", {
        "builder_v4_changed": False, "source_queries_changed_except_date": False,
        "leakage_changed": False, "quality_changed": False,
        "outcome_informed_tuning_allowed": False})
    put("historical_development_nonuse_audit.json", {
        "alpha3_19_alpha3_20_outcomes_used_as_primary_thresholds": False,
        "historical_assets_used_only_for_authority_and_seen_exclusion": True,
        "alpha3_20_development_reopened": False})
    put("fresh_primary_not_started_audit.json", {
        "fresh_primary_source_acquisition_started": False,
        "fresh_builder_execution_started": False,
        "fresh_quality_execution_started": False,
        "fresh_retrieval_evaluation_started": False,
        "fresh_source_query_network_executions": 0})
    require(root_hash(F, "search_plan_v24_dev_alpha3_20f_sha256") == F_ROOT
            and root_hash(F1, "search_plan_v24_dev_alpha3_20f1_sha256") == F1_ROOT,
            "HISTORICAL_ROOT_CHANGED_DURING_MASTER_FREEZE")
    put("scientific_state_safety_audit.json", {
        "historical_assets_modified": False,
        "scientific_policy_changed": False,
        "new_scientific_sources_acquired": False,
        "provider_calls": 0, "llm_calls": 0, "builder_calls": 0,
        "quality_calls": 0, "network_calls": 0,
        "pubmed_calls": 0, "pmc_calls": 0})
    plan = {"schema_version": "Alpha3_21FreshPrimaryMasterExecutionPlan",
        "fresh_primary_attempt": True,
        "publication_window": ["2026-01-01", "2026-09-30"],
        "query_set": ref(OUT / "alpha3_21_source_query_set.jsonl",
                         "frozen_six_stratum_date_only_queries"),
        "preexisting_seen_registry": ref(OUT /
            "alpha3_21_seen_contamination_registry.json",
            "frozen_preexisting_seen_registry"),
        "builder_v4_final_contract": ref(F /
            "search_plan_builder_v4_final_contract.json",
            "frozen_builder_v4_contract"),
        "quality_v2_protocol_sha256": QUALITY_SHA,
        "quality_response_envelope_v3": ref(M19 /
            "quality_response_envelope_v3.json",
            "frozen_quality_response_envelope_v3"),
        "sampling_seed_sha256": seed_sha,
        "sampling_order": ref(OUT / "alpha3_21_sampling_order_contract.json",
                              "prospective_sampling_order"),
        "phase_plan": ref(OUT / "alpha3_21_phase_plan.json",
                          "prospective_phase_plan"),
        "future_execution_requires_separate_authorization": True}
    plan_sha = put("alpha3_21_master_execution_plan.json", plan)
    marker("alpha3_21_master_execution_plan_sha256", plan_sha)
    validation = {"status": "completed",
        "alpha3_21_master_classification": CLASSIFICATION,
        "alpha3_20f_root_verified": True,
        "alpha3_20f1_root_verified": True,
        "fresh_primary_attempt": True, "development_mode": False,
        "publication_window_start": "2026-01-01",
        "publication_window_end": "2026-09-30",
        "source_stratum_count": 6,
        "max_records_per_stratum": 200,
        "target_sample_per_stratum": 12,
        "max_sampled_sources": 72,
        "seen_exclusion_before_sampling": True,
        "downstream_replacement_allowed": False,
        "cross_stratum_topup_allowed": False,
        "seen_unique_pmids": source_registry["seen_unique_pmids"],
        "seen_unique_pmcids": source_registry["seen_unique_pmcids"],
        "seen_unique_dois": source_registry["seen_unique_dois"],
        "seen_unique_candidate_identities":
            source_registry["seen_unique_candidate_identities"],
        "alpha3_21_seen_contamination_registry_sha256": registry_sha,
        "sampling_seed_sha256": seed_sha,
        "builder_v4_contract_sha256": CONTRACT_SHA,
        "selected_builder_prompt_sha256": PROMPT_SHA,
        "selected_builder_variant": "V1",
        "selected_builder_mode": "relation_sentence",
        "builder_provider": "DeepSeek", "builder_model": "deepseek-flash",
        "quality_v2_protocol_sha256": QUALITY_SHA,
        "quality_response_envelope_v3_sha256": ENVELOPE_SHA,
        "quality_provider": "DeepSeek", "quality_model": "deepseek-flash",
        "exact_seen_candidate_contamination_gate": True,
        "semantic_contamination_matching_used": False,
        "minimum_distinct_eligible_source_groups_for_retrieval_evaluation": 8,
        "fresh_primary_source_acquisition_started": False,
        "fresh_builder_execution_started": False,
        "fresh_quality_execution_started": False,
        "fresh_retrieval_evaluation_started": False,
        "provider_calls": 0, "llm_calls": 0, "builder_calls": 0,
        "quality_calls": 0, "network_calls": 0,
        "pubmed_calls": 0, "pmc_calls": 0,
        "alpha3_21_master_execution_plan_sha256": plan_sha,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False}
    put("validation.json", validation)
    put("summary.json", {"status": "completed",
        "classification": CLASSIFICATION,
        "seen_unique_pmids": source_registry["seen_unique_pmids"],
        "seen_unique_candidate_identities":
            source_registry["seen_unique_candidate_identities"],
        "next_stage_recommendation": NEXT})
    root = root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    return {**validation, ROOT_MARKER: root}


def run() -> dict:
    return freeze(preflight())


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
