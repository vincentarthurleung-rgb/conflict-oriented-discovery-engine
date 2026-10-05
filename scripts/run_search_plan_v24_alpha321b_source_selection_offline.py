#!/usr/bin/env python3
"""Frozen alpha3.21B PMID-only ownership, historical exclusion and sampling."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
MASTER = RUNS / "20261005_search_plan_v24_primary_alpha3_21_fresh_primary_master_preregistration_offline"
A = RUNS / "20261005_search_plan_v24_primary_alpha3_21a_fresh_source_acquisition_preregistration_offline"
A1 = RUNS / "20261005_search_plan_v24_primary_alpha3_21a1_fresh_source_acquisition_execution"
OUT = RUNS / "20261005_search_plan_v24_primary_alpha3_21b_offline_dedup_seen_exclusion_stratified_sampling"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21b_sha256"
MASTER_SHA = "47c0ba15f6acb4e1e581d148edbfa0674a7dc1e82261764876cef20f4184d935"
A_SHA = "16d26159bef61fe84577a4f8f053f8cb13962974ddaa44fdee5ae7ac6fe58146"
A1_SHA = "5b420d2f3dc0511d563e18329e29a45b057c75dae1b7e64e9c59a24f253c3fd4"
CORPUS_SHA = "aa043b4b3945dc433d59c8dc92f5a3a11833d752f6835221bb94cefe24c27ce3"
EXPOSURE_SHA = "f7089bda677383c08cc01fc513a3939d0b79bdbb7def0dce7c4fb8336675683b"
SEEN_SHA = "2c1a5b6cb46d4dace84f77068bc2ba3805760594927e1f5b7e8e11af2e08dab3"
SEED_SHA = "ad531a2b47d4a9ffdea7338c7f3fbabd8d39b404c623ae4777f8bdc4a43adae9"
CLASS_OK = "FRESH_PRIMARY_SOURCE_SAMPLE_FROZEN_AFTER_PREEXISTING_SEEN_EXCLUSION"
CLASS_ZERO = "FRESH_PRIMARY_ZERO_FRESH_SOURCES_AFTER_PREEXISTING_SEEN_EXCLUSION"
NEXT_OK = "PREREGISTER_ALPHA3_21C_METADATA_AND_SOURCE_TYPE_RESOLUTION"
NEXT_ZERO = "CLOSE_ALPHA3_21_PRIMARY_WITH_ZERO_FRESH_SOURCE_SAMPLE"
IDENTITY = "FRESH_PRIMARY_ALPHA3_21_OFFLINE_SOURCE_SELECTION"
PMID = re.compile(r"[1-9][0-9]*\Z")
NO_CALLS = {name: 0 for name in ("network_calls", "pubmed_calls", "pmc_calls",
                                "provider_calls", "llm_calls", "builder_calls",
                                "quality_calls")}


class StageFailure(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise StageFailure(code)


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
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def root_hash(directory: Path, marker: str) -> str:
    require(not directory.is_symlink() and
            not any(p.is_symlink() for p in directory.rglob("*")),
            "FROZEN_SYMLINK_FORBIDDEN")
    files = sorted(p for p in directory.rglob("*") if p.is_file() and p.name != marker)
    return sha(canonical([[str(p.relative_to(directory)), digest(p)] for p in files]))


def ref(path: Path, role: str) -> dict:
    return {"artifact_path": str(path.relative_to(ROOT)), "artifact_role": role,
            "sha256": digest(path), "immutable_frozen": True}


def checked_ref(binding: dict) -> Path:
    path = ROOT / binding.get("artifact_path", binding.get("path", ""))
    require(path.resolve().is_relative_to(ROOT) and path.is_file()
            and not path.is_symlink() and digest(path) == binding["sha256"],
            "INHERITED_AUTHORITY_REFERENCE_MISMATCH")
    return path


def verify_roots() -> None:
    for directory, marker, expected in (
        (MASTER, "search_plan_v24_primary_alpha3_21_master_prereg_sha256", MASTER_SHA),
        (A, "search_plan_v24_primary_alpha3_21a_prereg_sha256", A_SHA),
        (A1, "search_plan_v24_primary_alpha3_21a1_sha256", A1_SHA),
    ):
        require((directory / marker).read_text().strip() == expected
                and root_hash(directory, marker) == expected,
                "UPSTREAM_ROOT_MISMATCH:" + marker)


def resolve_authorities() -> dict:
    order_path = MASTER / "alpha3_21_sampling_order_contract.json"
    order = obj(order_path)
    require(order["stage_order"] == [
        "acquire_all_frozen_query_frames", "parse_and_validate_all_frames",
        "deterministic_pmid_dedup_and_earliest_stratum_ownership",
        "exclude_preexisting_seen_pmids", "freeze_fresh_source_universe",
        "deterministic_within_stratum_sampling", "metadata_oa_construction_downstream"],
        "SELECTION_STAGE_ORDER_AUTHORITY_MISMATCH")
    try:
        dedup_path = checked_ref(order["dedup_authority"])
        dedup = obj(dedup_path)
        cross_path = checked_ref(dedup["policy"])
        cross = obj(cross_path)
        strata = [q["stratum_id"] for q in rows(MASTER / "alpha3_21_source_query_set.jsonl")]
        require(len(strata) == len(set(strata)) == 6
                and cross["earliest_owner_order"] == strata
                and dedup["identity"] == "exact canonical PMID"
                and dedup["owner"] == "earliest frozen stratum in six-stratum order"
                and dedup["all_memberships_preserved_privately"] is True
                and cross["all_memberships_preserved"] is True
                and cross["duplicate_article_constructed_once"] is True,
                "CROSS_STRATUM_CONTRACT_MISMATCH")
    except (StageFailure, KeyError, OSError, ValueError) as exc:
        raise StageFailure("ALPHA3_21B_CROSS_STRATUM_OWNERSHIP_AUTHORITY_UNRESOLVED") from exc
    try:
        policy_path = MASTER / "alpha3_21_sampling_policy.json"
        seed_path = MASTER / "alpha3_21_sampling_seed_derivation.json"
        policy, seed = obj(policy_path), obj(seed_path)
        algorithm_path = checked_ref(policy["sampling_algorithm_authority"])
        algorithm = obj(algorithm_path)
        require(policy["sampling_algorithm"] ==
                "SHA256(UTF8(seed_hex + ':' + stratum_id + ':' + canonical PMID)); ascending; first 12"
                and policy["sampling_seed_sha256"] == SEED_SHA
                and policy["maximum_per_stratum"] == 12
                and policy["maximum_total"] == 72 and policy["strata"] == 6
                and policy["take_all_if_less_than_twelve"] is True
                and policy["cross_stratum_topup_allowed"] is False
                and policy["downstream_replacement_allowed"] is False
                and algorithm["key"] == "SHA256(key_preimage UTF-8 bytes)"
                and algorithm["key_preimage"] ==
                    "ASCII seed_sha256 + ':' + stratum_id + ':' + canonical PMID"
                and algorithm["order"] ==
                    "ascending raw 32-byte digest, then ascending decimal PMID as tie-break"
                and algorithm["source_id"] == "canonical decimal PMID with no leading zeros"
                and algorithm["sample"] == "first min(12, owned frame length)",
                "SAMPLING_ALGORITHM_CONTRACT_MISMATCH")
        seed_bytes = bytes.fromhex(seed["derived_seed_bytes_hex"])
        seed_text = seed["sampling_algorithm_seed_text"]
        require(len(seed_bytes) == 32 and sha(seed_bytes) == SEED_SHA ==
                seed["derived_seed_bytes_sha256"]
                and seed_text == seed_bytes.hex()
                and seed["sampling_algorithm_seed_text_encoding"] == "lowercase hex ASCII/UTF-8"
                and hashlib.sha256(bytes.fromhex(seed["preimage_utf8_hex"])).digest() == seed_bytes,
                "SAMPLING_SEED_AUTHORITY_MISMATCH")
    except (StageFailure, KeyError, OSError, ValueError) as exc:
        raise StageFailure("ALPHA3_21B_SAMPLING_ALGORITHM_AUTHORITY_UNRESOLVED") from exc
    return {"strata": strata, "dedup_path": dedup_path, "cross_path": cross_path,
            "order_path": order_path, "policy_path": policy_path,
            "seed_path": seed_path, "algorithm_path": algorithm_path,
            "seed_text": seed_text, "seed": seed}


def verify_inputs() -> dict:
    verify_roots()
    for path, expected in (
        (A1 / "alpha3_21a1_raw_acquisition_corpus.jsonl", CORPUS_SHA),
        (A1 / "alpha3_21_current_attempt_source_exposure_registry.json", EXPOSURE_SHA),
        (MASTER / "alpha3_21_seen_contamination_registry.json", SEEN_SHA),
    ):
        require(digest(path) == expected, "INPUT_ARTIFACT_HASH_MISMATCH:" + path.name)
    completion = obj(A1 / "validation.json")
    require(completion["status"] == "completed"
            and completion["alpha3_21a1_classification"] ==
                "FRESH_PRIMARY_SOURCE_ACQUISITION_COMPLETE_AND_FROZEN"
            and completion["total_logical_page_requests_executed"] == 24
            and completion["valid_page_response_count"] == 24
            and completion["result_set_count_drift_count"] == 0
            and completion["raw_pmid_occurrence_count"] == 1200
            and completion["unique_exposed_pmid_count"] == 1015,
            "ACQUISITION_COMPLETENESS_GATE_FAILED")
    authorities = resolve_authorities()
    raw = rows(A1 / "alpha3_21a1_raw_acquisition_corpus.jsonl")
    pages = {r["logical_request_id"]: r for r in
             rows(A / "alpha3_21_potential_page_request_manifest.jsonl")}
    accepted = {r["logical_request_id"]: r for r in
                rows(A1 / "all_pubmed_request_attempt_log.jsonl")
                if r["decision"] == "ACCEPT_VALID_PAGE"}
    require(len(raw) == 1200 and len(pages) == len(accepted) == 24,
            "ACQUISITION_PROVENANCE_CARDINALITY_MISMATCH")
    for ordinal, row in enumerate(raw, 1):
        pmid = row["pmid"]
        page = pages.get(row["logical_page_id"])
        result = accepted.get(row["logical_page_id"])
        require(isinstance(pmid, str) and PMID.fullmatch(pmid) is not None,
                "PMID_IDENTITY_UNRESOLVED")
        require(page is not None and result is not None
                and row["raw_acquisition_ordinal"] == ordinal
                and row["stratum_id"] == page["stratum_id"] == result["stratum_id"]
                and row["retstart"] == page["retstart"] == result["retstart"]
                and 1 <= row["within_page_position"] <= 50
                and result["validity"]["idlist"][row["within_page_position"] - 1] == pmid
                and row["raw_response_sha256"] == result["raw_sha256"]
                and row["trusted_for_normal_acquisition_corpus"] is True
                and row["validator_state"] in ("VALID_NONZERO", "VALID_ZERO"),
                "RAW_MEMBERSHIP_PROVENANCE_MISMATCH")
    exposure = obj(A1 / "alpha3_21_current_attempt_source_exposure_registry.json")
    exposed = [r["pmid"] for r in exposure["exposed_unique_pmids"]]
    require(len(exposed) == len(set(exposed)) == 1015
            and set(exposed) == {r["pmid"] for r in raw},
            "ALPHA3_21B_RAW_CORPUS_EXPOSURE_REGISTRY_MISMATCH")
    registry = obj(MASTER / "alpha3_21_seen_contamination_registry.json")
    # Project only PMID identity; historical DOI/PMCID/scientific fields are not selection inputs.
    seen = [r["pmid"] for r in registry["source_identities"]]
    require(len(seen) == len(set(seen)) == registry["seen_unique_pmids"] == 2545
            and all(isinstance(p, str) and PMID.fullmatch(p) for p in seen),
            "PREEXISTING_REGISTRY_IDENTITY_MISMATCH")
    return {**authorities, "raw": raw, "seen": set(seen)}


def deduplicate(raw: list[dict], strata: list[str]) -> list[dict]:
    """Ownership follows frozen stratum order, independently of transport arrival."""
    grouped = defaultdict(list)
    stratum_order = {s: i + 1 for i, s in enumerate(strata)}
    for row in raw:
        require(isinstance(row["pmid"], str) and PMID.fullmatch(row["pmid"]) is not None,
                "PMID_IDENTITY_UNRESOLVED")
        require(row["stratum_id"] in stratum_order, "STRATUM_IDENTITY_UNRESOLVED")
        grouped[row["pmid"]].append(dict(row))
    unique = []
    for pmid, memberships in grouped.items():
        memberships.sort(key=lambda r: (stratum_order[r["stratum_id"]],
                                         r["retstart"] + r["within_page_position"],
                                         r["raw_acquisition_ordinal"]))
        retained = memberships[0]
        unique.append({"pmid": pmid, "owner_stratum": retained["stratum_id"],
            "owner_stratum_ordinal": stratum_order[retained["stratum_id"]],
            "retained_within_stratum_rank": retained["retstart"] + retained["within_page_position"],
            "retained_raw_acquisition_ordinal": retained["raw_acquisition_ordinal"],
            "raw_occurrence_count": len(memberships),
            "raw_acquisition_memberships": memberships,
            "stratum_memberships": [s for s in strata if any(
                r["stratum_id"] == s for r in memberships)],
            "ownership_rule": "earliest frozen stratum in six-stratum order"})
    return sorted(unique, key=lambda r: (r["owner_stratum_ordinal"],
                                         r["retained_within_stratum_rank"], int(r["pmid"])))


def sampling_order(universe: list[dict], stratum: str, seed_text: str) -> list[tuple]:
    return sorted((hashlib.sha256(f"{seed_text}:{stratum}:{r['pmid']}".encode("utf-8")).digest(),
                   int(r["pmid"]), r) for r in universe if r["owner_stratum"] == stratum)


def put_bytes(name: str, raw: bytes) -> str:
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def put(name: str, value: object) -> str:
    return put_bytes(name, canonical(value) + b"\n")


def put_rows(name: str, values: list[dict]) -> str:
    return put_bytes(name, b"".join(canonical(r) + b"\n" for r in values))


def freeze_rows(stem: str, values: list[dict]) -> str:
    value = put_rows(stem + ".jsonl", values)
    put_bytes(stem + "_sha256", (value + "\n").encode("ascii"))
    return value


def sample_from_frozen_inputs(state: dict) -> list[dict]:
    """Reload frozen fresh-universe artifacts and seed independently on each replay."""
    global_path = OUT / "fresh_source_universe_global.jsonl"
    strata_path = OUT / "fresh_source_universe_by_stratum.json"
    require(digest(global_path) == (OUT / "fresh_source_universe_global_sha256").read_text().strip()
            and digest(strata_path) == (OUT / "fresh_source_universe_by_stratum_sha256").read_text().strip()
            and digest(state["seed_path"]) == obj(OUT / "sampling_seed_binding.json")["seed_artifact"]["sha256"],
            "FRESH_UNIVERSE_OR_SEED_FREEZE_BARRIER_FAILED")
    universe, by_stratum = rows(global_path), obj(strata_path)
    seed_text = obj(state["seed_path"])["sampling_algorithm_seed_text"]
    require(seed_text == state["seed_text"], "SAMPLING_SEED_CHANGED")
    require(by_stratum["strata"] == [{"stratum_id": s, "pmids": [r["pmid"] for r in universe
                if r["owner_stratum"] == s]} for s in state["strata"]],
            "GLOBAL_AND_STRATUM_UNIVERSE_MISMATCH")
    sampled = []
    for stratum in state["strata"]:
        ordered = sampling_order(universe, stratum, seed_text)
        for rank, (key, _, source) in enumerate(ordered[:12], 1):
            sampled.append({**source, "freshness_state": "PRE_METADATA_FRESH_SOURCE",
                "sample_rank_in_stratum": rank, "sampling_key_sha256": key.hex(),
                "sampling_key_preimage": f"{seed_text}:{stratum}:{source['pmid']}",
                "selection_rule": "ascending raw SHA256 digest then ascending decimal PMID; first min(12, fresh stratum size)",
                "sampling_seed_sha256": SEED_SHA})
    return sampled


def execute(state: dict) -> dict:
    OUT.mkdir()
    for name, directory, marker, expected in (
        ("alpha3_21a1_root_verification.json", A1, "search_plan_v24_primary_alpha3_21a1_sha256", A1_SHA),
        ("alpha3_21a_root_verification.json", A, "search_plan_v24_primary_alpha3_21a_prereg_sha256", A_SHA),
        ("alpha3_21_master_root_verification.json", MASTER, "search_plan_v24_primary_alpha3_21_master_prereg_sha256", MASTER_SHA),
    ):
        put(name, {"root_sha256": expected, "root_marker": ref(directory / marker, "upstream_root"),
                   "verified_before_source_selection": True})
    for name, path, count in (
        ("raw_acquisition_corpus_verification.json", A1 / "alpha3_21a1_raw_acquisition_corpus.jsonl", 1200),
        ("current_attempt_exposure_registry_verification.json", A1 / "alpha3_21_current_attempt_source_exposure_registry.json", 1015),
        ("preexisting_seen_registry_verification.json", MASTER / "alpha3_21_seen_contamination_registry.json", 2545),
    ):
        put(name, {"frozen_input": ref(path, name.removesuffix(".json")), "count": count, "verified": True})
    put("raw_to_unique_pmid_integrity_audit.json", {
        "raw_pmid_occurrence_count": 1200, "derived_unique_pmid_count": 1015,
        "raw_unique_set_matches_current_exposure_registry": True,
        "exact_canonical_pmid_identity_only": True})
    put("cross_stratum_dedup_authority_binding.json", {
        "master_order_contract": ref(state["order_path"], "current_stage_order_authority"),
        "inherited_dedup_contract": ref(state["dedup_path"], "pmid_ownership_authority"),
        "inherited_cross_stratum_policy": ref(state["cross_path"], "frozen_stratum_owner_order"),
        "earliest_owner_order": state["strata"], "authority_resolved": True,
        "transport_arrival_order_defines_ownership": False,
        "all_raw_memberships_and_ranks_preserved": True})
    put("sampling_seed_binding.json", {
        "seed_artifact": ref(state["seed_path"], "master_frozen_seed"),
        "sampling_seed_sha256": SEED_SHA, "seed_text": state["seed_text"],
        "seed_text_encoding": "lowercase hex ASCII/UTF-8", "seed_changed": False})
    put("sampling_algorithm_authority_binding.json", {
        "master_policy": ref(state["policy_path"], "current_primary_sampling_policy"),
        "inherited_algorithm_only": ref(state["algorithm_path"], "frozen_digest_order_and_numeric_tie_break"),
        "seed_authority": "alpha3.21 master seed artifact; historical algorithm seed is not inherited",
        "candidate_order": "ascending raw 32-byte SHA256 digest then ascending decimal PMID",
        "authority_resolved": True})
    unique = deduplicate(state["raw"], state["strata"])
    require(len(unique) == 1015, "DEDUP_UNIQUE_COUNT_MISMATCH")
    cross_count = sum(len(r["stratum_memberships"]) > 1 for r in unique)
    put_rows("cross_stratum_membership_manifest.jsonl", unique)
    unique_sha = freeze_rows("deduplicated_source_universe", unique)
    seen_ref = ref(MASTER / "alpha3_21_seen_contamination_registry.json", "only_current_historical_exclusion_authority")
    intersection = [{**r, "exclusion_reason": "EXACT_PREEXISTING_PMID_IDENTITY",
                     "historical_seen_registry": seen_ref} for r in unique if r["pmid"] in state["seen"]]
    intersection_sha = freeze_rows("preexisting_seen_pmid_intersection", intersection)
    fresh = [{**r, "freshness_state": "PRE_METADATA_FRESH_SOURCE"}
             for r in unique if r["pmid"] not in state["seen"]]
    require(len(fresh) == 1015 - len(intersection), "FRESH_UNIVERSE_INVARIANT_FAILED")
    fresh_sha = freeze_rows("fresh_source_universe_global", fresh)
    by_stratum_sha = put("fresh_source_universe_by_stratum.json", {
        "global_universe_sha256": fresh_sha,
        "strata": [{"stratum_id": s, "pmids": [r["pmid"] for r in fresh if r["owner_stratum"] == s]}
                   for s in state["strata"]]})
    put_bytes("fresh_source_universe_by_stratum_sha256", (by_stratum_sha + "\n").encode("ascii"))
    input_order = []
    for stratum in state["strata"]:
        input_order.append({"stratum_id": stratum,
            "universe_artifact_pmids": [r["pmid"] for r in fresh if r["owner_stratum"] == stratum],
            "sampler_candidate_order": [{"pmid": r["pmid"], "key_sha256": key.hex()}
                                        for key, _, r in sampling_order(fresh, stratum, state["seed_text"])],
            "input_enumeration_does_not_override_digest_order": True})
    put("sampling_input_order_audit.json", {"strata": input_order,
        "fresh_universe_frozen_before_sampling": True})
    sample = sample_from_frozen_inputs(state)
    sample_sha = freeze_rows("sampled_source_manifest", sample)
    replay = sample_from_frozen_inputs(state)
    replay_sha = put_rows("sampled_source_manifest_replay.jsonl", replay)
    require((OUT / "sampled_source_manifest.jsonl").read_bytes() ==
            (OUT / "sampled_source_manifest_replay.jsonl").read_bytes(),
            "SAMPLING_REPLAY_NOT_BYTE_IDENTICAL")
    sampled_ids = {r["pmid"] for r in sample}
    require(len(sampled_ids) == len(sample) <= 72
            and not sampled_ids & state["seen"], "SAMPLE_IDENTITY_OR_EXCLUSION_INVARIANT_FAILED")
    unsampled = [r for r in fresh if r["pmid"] not in sampled_ids]
    put_rows("unsampled_fresh_source_manifest.jsonl", unsampled)
    funnel = []
    for index, stratum in enumerate(state["strata"], 1):
        fresh_count = sum(r["owner_stratum"] == stratum for r in fresh)
        sampled_count = sum(r["owner_stratum"] == stratum for r in sample)
        require(sampled_count == min(12, fresh_count), "STRATUM_SAMPLE_TARGET_MISMATCH")
        funnel.append({"stratum_id": stratum, "stratum_ordinal": index,
            "raw_occurrences": sum(r["stratum_id"] == stratum for r in state["raw"]),
            "owned_unique_pmids": sum(r["owner_stratum"] == stratum for r in unique),
            "preexisting_seen_excluded": sum(r["owner_stratum"] == stratum for r in intersection),
            "fresh_pmids": fresh_count, "sample_target": min(12, fresh_count),
            "sampled_pmids": sampled_count})
    put("per_stratum_source_funnel.json", {"strata": funnel})
    put("sampling_determinism_audit.json", {"independent_frozen_input_loads": 2,
        "sampled_source_manifest_sha256": sample_sha, "replay_sha256": replay_sha,
        "sampling_replay_byte_identical": True, "outcome_informed_resampling": False})
    put("sample_freeze_barrier.json", {"immutable_sample": ref(OUT / "sampled_source_manifest.jsonl", "only_21c_source_input"),
        "fresh_universe_sha256": fresh_sha, "sampling_replay_byte_identical": True,
        "frozen_before_any_metadata_or_downstream_execution": True,
        "additions_allowed": False, "replacement_allowed": False, "topup_allowed": False})
    put("alpha3_21c_sampled_source_handoff.json", {"sample_manifest": ref(OUT / "sampled_source_manifest.jsonl", "immutable_sample"),
        "sampled_source_count": len(sample), "source_additions_allowed": False,
        "source_replacement_allowed": False, "stratum_topup_allowed": False,
        "metadata_fields_resolved": False, "metadata_execution_authorized_by_this_stage": False,
        "sources": [{"pmid": r["pmid"], "stratum_id": r["owner_stratum"],
                     "sample_rank_in_stratum": r["sample_rank_in_stratum"],
                     "sampling_key_sha256": r["sampling_key_sha256"],
                     "raw_acquisition_memberships": r["raw_acquisition_memberships"]} for r in sample]})
    verify_roots()
    require(digest(A1 / "alpha3_21_current_attempt_source_exposure_registry.json") == EXPOSURE_SHA
            and digest(MASTER / "alpha3_21_seen_contamination_registry.json") == SEEN_SHA,
            "REGISTRY_CHANGED_DURING_SELECTION")
    put("no_self_contamination_audit.json", {
        "current_attempt_exposure_registry_used_for_integrity_only": True,
        "current_attempt_exposure_used_as_current_exclusion": False,
        "current_attempt_exposure_does_not_self_exclude": True,
        "preexisting_registry_is_only_exclusion_authority": True,
        "future_contamination_history_remains_all_1015_exposed_pmids": True})
    put("preexisting_registry_postexecution_verification.json", {"sha256": SEEN_SHA, "unchanged": True})
    put("current_attempt_exposure_postexecution_verification.json", {"sha256": EXPOSURE_SHA, "unchanged": True})
    put("downstream_replacement_prohibition.json", {
        "all_metadata_alias_oa_license_jats_builder_grounding_leakage_quality_failures": "exclude without replacement",
        "unsampled_source_addition_allowed": False, "topup_allowed": False})
    put("fresh_primary_policy_nonadaptation_audit.json", {
        "source_queries_changed": False, "date_interval_changed": False,
        "sampling_seed_changed": False, "sampling_algorithm_changed": False,
        "scientific_policy_changed": False, "cross_stratum_topup_used": False,
        "downstream_replacement_used": False, "scientific_outcome_fields_used_for_selection": []})
    put("builder_v4_nonuse_audit.json", {"builder_calls": 0, "builder_execution_started": False})
    put("quality_nonuse_audit.json", {"quality_calls": 0, "quality_execution_started": False})
    put("historical_preservation_audit.json", {"all_three_upstream_roots_unchanged": True,
        "preexisting_seen_registry_unchanged": True, "current_attempt_exposure_registry_unchanged": True,
        "raw_acquisition_corpus_unchanged": True, "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {**NO_CALLS,
        "metadata_execution_started": False, "builder_execution_started": False,
        "quality_execution_started": False, "retrieval_evaluation_started": False,
        "doi_pmcid_alias_inference_performed": False, "scientific_selection_performed": False})
    put("protocol_compliance_audit.json", {
        "stage_identity": IDENTITY, "stage_order": obj(state["order_path"])["stage_order"][:6],
        "pmid_identity_only": True, "fresh_universe_frozen_before_sampling": True,
        "sampled_manifest_replay_byte_identical": True,
        "downstream_outcomes_not_inspected": True, **NO_CALLS})
    put("execution_implementation_binding.json", ref(Path(__file__).resolve(), "offline_identity_selection_executor"))
    result = {"status": "completed", "stage_identity": IDENTITY,
        "alpha3_21b_classification": CLASS_OK if fresh else CLASS_ZERO,
        "alpha3_21a1_root_verified": True, "alpha3_21a_root_verified": True,
        "alpha3_21_master_root_verified": True,
        "raw_pmid_occurrence_count": 1200, "global_unique_acquired_pmid_count": 1015,
        "raw_unique_set_matches_current_exposure_registry": True,
        "cross_stratum_dedup_authority_resolved": True,
        "cross_stratum_duplicate_unique_pmid_count": cross_count,
        "duplicate_occurrence_count": 1200 - 1015,
        "preexisting_seen_pmid_count": 2545, "preexisting_seen_intersection_count": len(intersection),
        "fresh_unique_pmid_count": len(fresh), "sampled_source_count": len(sample),
        "unsampled_fresh_source_count": len(unsampled),
        "sampling_seed_sha256": SEED_SHA, "sampling_algorithm_authority_resolved": True,
        "sampling_replay_byte_identical": True, "cross_stratum_topup_used": False,
        "downstream_replacement_used": False,
        "current_attempt_exposure_used_as_current_exclusion": False,
        "current_attempt_exposure_does_not_self_exclude": True,
        "preexisting_seen_registry_unchanged": True, "current_attempt_exposure_registry_unchanged": True,
        "deduplicated_source_universe_sha256": unique_sha,
        "preexisting_seen_pmid_intersection_sha256": intersection_sha,
        "fresh_source_universe_global_sha256": fresh_sha,
        "fresh_source_universe_by_stratum_sha256": by_stratum_sha,
        "sampled_source_manifest_sha256": sample_sha,
        "metadata_execution_started": False, "builder_execution_started": False,
        "quality_execution_started": False, "retrieval_evaluation_started": False,
        "next_stage_recommendation": NEXT_OK if fresh else NEXT_ZERO,
        "historical_assets_modified": False, **NO_CALLS}
    for i, entry in enumerate(funnel, 1):
        result[f"stratum_{i}_fresh_count"] = entry["fresh_pmids"]
        result[f"stratum_{i}_sampled_count"] = entry["sampled_pmids"]
    put("validation.json", result)
    put("summary.json", {**result, "per_stratum": funnel})
    root = root_hash(OUT, ROOT_MARKER)
    put_bytes(ROOT_MARKER, (root + "\n").encode("ascii"))
    return {**result, ROOT_MARKER: root}


def run() -> dict:
    require(not OUT.exists(), "ALPHA321B_OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    try:
        state = verify_inputs()
        return execute(state)
    except StageFailure as exc:
        if OUT.exists():
            raise  # Preserve any partial offline output without overwriting decisions.
        OUT.mkdir()
        failure = {"status": "failed", "stage_identity": IDENTITY, "failure_code": exc.code,
                   "source_selection_executed": False, **NO_CALLS}
        if "CROSS_STRATUM" in exc.code:
            failure.update(alpha3_21b_classification="FRESH_PRIMARY_SOURCE_SELECTION_BLOCKED_BY_CROSS_STRATUM_AUTHORITY",
                           next_stage_recommendation="AUDIT_ALPHA3_21B_CROSS_STRATUM_AUTHORITY_OFFLINE")
        elif "SAMPLING_ALGORITHM" in exc.code:
            failure.update(alpha3_21b_classification="FRESH_PRIMARY_SOURCE_SELECTION_BLOCKED_BY_SAMPLING_AUTHORITY",
                           next_stage_recommendation="AUDIT_ALPHA3_21B_SAMPLING_AUTHORITY_OFFLINE")
        else:
            failure.update(alpha3_21b_classification="FRESH_PRIMARY_SOURCE_SELECTION_BLOCKED_BY_ACQUISITION_INTEGRITY_MISMATCH",
                           next_stage_recommendation="AUDIT_ALPHA3_21A1_ACQUISITION_EXPOSURE_INTEGRITY_OFFLINE")
        put("validation.json", failure)
        put("summary.json", failure)
        root = root_hash(OUT, ROOT_MARKER)
        put_bytes(ROOT_MARKER, (root + "\n").encode("ascii"))
        return {**failure, ROOT_MARKER: root}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
