#!/usr/bin/env python3
"""Offline alpha3.19B identity deduplication and frozen deterministic sampling."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts import search_plan_v24_alpha319a_preregister_source_acquisition_offline as prereg
from scripts import run_search_plan_v24_alpha319a2_full_six_frame_restart as a2


ROOT = master.ROOT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19b_dedup_seen_source_sampling_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19b_sha256"
A2_SHA = "64b7db6eb803b6464a11876bec2b868eaade5fdcbc7e6eada69a5e675ad7480c"
REGISTRY_SHA = "3ebbe81173200562601ada7de5033aa3f4aed5209481ade651f2b4b5e53140b6"
SEED_SHA = "bad60035a8bf074e565cf0e05739f555d6fb46e918b8989e1761f9014ab1953c"
STRATA = ("basic_cell_signaling", "immunology", "metabolism", "neuroscience",
          "cancer_biology", "therapy_response_biology")


def require(condition: bool, message: str):
    if not condition:
        raise RuntimeError(message)


def read_json(path: Path):
    return json.loads(path.read_bytes())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def write_json(name: str, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(master.canonical(value) + b"\n")


def write_jsonl(name: str, values):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        for value in values:
            handle.write(master.canonical(value) + b"\n")


def root_hash():
    files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != ROOT_MARKER)
    require(not any(path.is_symlink() for path in OUT.rglob("*")), "OUTPUT_SYMLINK_FORBIDDEN")
    return master.sha(master.canonical([[str(path.relative_to(OUT)), master.digest(path)]
                                      for path in files]))


def frozen_inputs():
    require(not OUT.exists(), "ALPHA319B_RUN_ALREADY_EXISTS_NO_RERUN")
    source = a2.OUT
    require(a2.root_hash() == A2_SHA and
            (source / a2.ROOT_MARKER).read_text().strip() == A2_SHA,
            "A2_ROOT_MISMATCH")
    completion = read_json(source / "frame_completion_state.json")
    summary = read_json(source / "alpha3_19a2_source_acquisition_execution_summary.json")
    validation = read_json(source / "validation.json")
    require(completion["source_frames_completed"] == 6 and
            completion["six_source_frames_frozen"] is True and
            completion["failure"] is None and
            summary["raw_source_records"] == 1200 and
            summary["ncbi_attempts"] == 24 and
            summary["source_query_set_sha256"] == a2.QUERY_SHA and
            summary["sampling_seed_changed"] is False and
            validation["all_raw_attempts_frozen"] is True and
            validation["six_frame_barrier_crossed"] is True and
            validation["downstream_actions_executed"] is False,
            "SOURCE_COMPLETION_BARRIER_FAILED")
    frame_paths = sorted((source / "six_source_frame_manifests").glob("*.json"))
    require(len(frame_paths) == 6, "SIX_FRAME_FILE_COUNT_MISMATCH")
    require(master.sha(master.canonical([[p.name, master.digest(p)] for p in frame_paths])) ==
            (source / "six_source_frames_sha256").read_text().strip(),
            "SIX_FRAME_HASH_MISMATCH")
    frames = [read_json(path) for path in frame_paths]
    queries = master.rows(prereg.OUT / "alpha3_19_source_query_set.jsonl")
    require(master.digest(prereg.OUT / "alpha3_19_source_query_set.jsonl") == a2.QUERY_SHA and
            len(queries) == 6, "SOURCE_QUERY_SET_MISMATCH")
    pages = read_jsonl(source / "source_query_execution_results.jsonl")
    attempts = read_jsonl(source / "ncbi_transport_attempts.jsonl")
    require(len(pages) == len(attempts) == 24 and
            all(x["decision"] == "ACCEPT_PAGE" and x["attempt"] == 1 for x in attempts),
            "SOURCE_PAGE_ATTEMPT_MISMATCH")
    raw_count = 0
    for i, (frame, query) in enumerate(zip(frames, queries), 1):
        require(frame["frame_index"] == query["ordinal"] == i and
                frame["stratum_id"] == query["stratum_id"] == STRATA[i - 1] and
                frame["query_sha256"] == query["query_sha256"] and
                frame["terminal_state"] == "COMPLETE_VALID_FRAME" and
                frame["within_frame_deduplication_performed"] is False and
                len(frame["page_records"]) == 4,
                "FRAME_IDENTITY_OR_STATE_MISMATCH")
        concatenated = []
        for j, record in enumerate(frame["page_records"]):
            page = pages[(i - 1) * 4 + j]
            attempt = attempts[(i - 1) * 4 + j]
            require(record["retstart"] == page["retstart"] == attempt["retstart"] == j * 50 and
                    page["frame_index"] == attempt["frame_index"] == i and
                    page["idlist"] == record["pmids"] and
                    page["raw_response_sha256"] == record["raw_response_sha256"] ==
                        attempt["raw_sha256"] == master.digest(source / attempt["raw_path"]) and
                    page["validator_state"] == "VALID_NONZERO" and
                    attempt["validity"]["valid_page"] is True and
                    len(record["pmids"]) == 50,
                    "SOURCE_PAGE_BINDING_MISMATCH")
            concatenated.extend(record["pmids"])
        require(concatenated == frame["raw_pmid_order"] and
                frame["raw_record_count"] == len(concatenated) == 200,
                "SOURCE_FRAME_ORDER_OR_COUNT_MISMATCH")
        raw_count += len(concatenated)
    require(raw_count == 1200, "RAW_SOURCE_RECORD_COUNT_MISMATCH")

    manifest = read_json(prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json")
    for field in ("dedup", "sampling_algorithm", "sampling_seed", "historical_contamination_gate",
                  "historical_contamination_registry"):
        prereg.check_ref(manifest[field])
    contract = read_json(ROOT / manifest["sampling_algorithm"]["path"])
    seed_contract = read_json(ROOT / manifest["sampling_seed"]["path"])
    dedup_contract = read_json(ROOT / manifest["dedup"]["path"])
    gate = read_json(ROOT / manifest["historical_contamination_gate"]["path"])
    master_sample = read_json(master.OUT / "alpha3_19_sampling_contract.json")
    require(contract["algorithm"] == "SHA256(seed || ':' || stratum || ':' || canonical PMID), ascending; first 12" and
            contract["sampling_before_historical_contamination_exclusion"] is True and
            contract["seen_source_pre_filter"] is False and
            contract["seed"] == seed_contract["seed"] == master_sample["seed_sha256"] == SEED_SHA and
            seed_contract["seed"] == master.sha(seed_contract["seed_input"].encode()) and
            contract["sample_cap_per_stratum"] == master_sample["sample_cap_per_stratum"] == 12 and
            contract["replacement_allowed"] is False and contract["refill_allowed"] is False and
            dedup_contract["identity"] == "exact canonical PMID" and
            dedup_contract["owner"] == "earliest frozen stratum in six-stratum order" and
            gate["applies_after_sample_identity_freeze"] is True,
            "FROZEN_DEDUP_OR_SAMPLING_POLICY_MISMATCH")
    registry_path = ROOT / manifest["historical_contamination_registry"]["path"]
    require(master.digest(registry_path) == REGISTRY_SHA, "SEEN_SOURCE_REGISTRY_HASH_MISMATCH")
    registry = read_jsonl(registry_path)
    require(len(registry) == 1041 and
            all(re.fullmatch(r"[1-9][0-9]*", row["pmid"]) and
                row["identity_sha256"] == master.sha(row["pmid"].encode())
                for row in registry) and
            len({row["pmid"] for row in registry}) == 1041,
            "SEEN_SOURCE_REGISTRY_IDENTITY_MISMATCH")
    return frames, {row["pmid"] for row in registry}, manifest


def main():
    frames, seen, manifest = frozen_inputs()
    memberships = {}
    occurrences = Counter()
    owned = {stratum: [] for stratum in STRATA}
    for frame in frames:
        stratum = frame["stratum_id"]
        for rank, pmid in enumerate(frame["raw_pmid_order"], 1):
            require(isinstance(pmid, str) and re.fullmatch(r"[1-9][0-9]*", pmid),
                    "PMID_IDENTITY_UNRESOLVED")
            occurrences[pmid] += 1
            if pmid not in memberships:
                memberships[pmid] = {"pmid": pmid, "owner_stratum": stratum,
                                     "owner_frame_index": frame["frame_index"],
                                     "first_raw_rank": rank, "memberships": []}
                owned[stratum].append(pmid)
            if stratum not in memberships[pmid]["memberships"]:
                memberships[pmid]["memberships"].append(stratum)
    raw_count = sum(len(frame["raw_pmid_order"]) for frame in frames)
    require(raw_count == 1200 and sum(occurrences.values()) == 1200 and
            sum(len(values) for values in owned.values()) == len(memberships),
            "DEDUPLICATION_INVARIANT_FAILED")
    overlap = set(memberships) & seen
    # Frozen alpha3.19A policy freezes sampled identities before exclusion. This
    # user's requested pre-sampling exclusion is equivalent only when overlap=0.
    require(not overlap, "ORDER_CONFLICT_NONZERO_SEEN_SOURCE_OVERLAP_FAILED_CLOSED")
    universe = [dict(memberships[pmid], raw_occurrences=occurrences[pmid],
                     seen_source_match=False)
                for stratum in STRATA for pmid in owned[stratum]]
    sampled = []
    for stratum in STRATA:
        keyed = sorted(((hashlib.sha256(f"{SEED_SHA}:{stratum}:{pmid}".encode()).digest(),
                         int(pmid), pmid) for pmid in owned[stratum]))
        for rank, (digest, _, pmid) in enumerate(keyed[:12], 1):
            sampled.append({"pmid": pmid, "owner_stratum": stratum,
                            "owner_frame_index": memberships[pmid]["owner_frame_index"],
                            "sample_rank_in_stratum": rank, "sampling_key_sha256": digest.hex(),
                            "seen_source_match": False})
    require(len(sampled) == 72 and len({row["pmid"] for row in sampled}) == 72,
            "DETERMINISTIC_SAMPLE_INVARIANT_FAILED")

    OUT.mkdir()
    write_jsonl("deduplicated_sampling_universe.jsonl", universe)
    write_json("deduplication_summary.json", {
        "source_root_sha256": A2_SHA, "raw_record_count": raw_count,
        "unique_pmid_count": len(memberships), "duplicate_record_count": raw_count - len(memberships),
        "identity_key": "exact canonical PMID", "ownership": "earliest frozen stratum",
        "owned_counts_by_stratum": {key: len(owned[key]) for key in STRATA},
        "all_memberships_preserved": True,
        "deduplicated_universe_sha256": master.digest(OUT / "deduplicated_sampling_universe.jsonl")})
    write_json("seen_source_audit.json", {
        "registry_sha256": REGISTRY_SHA, "registry_unique_pmid_count": len(seen),
        "comparison_key": "exact canonical PMID", "audit_after_dedup_before_sampling": True,
        "naturally_overlapping_pmid_count": len(overlap), "excluded_source_count": 0,
        "retained_source_count": len(memberships),
        "frozen_policy_applies_exclusion_after_sample_identity_freeze": True,
        "requested_pre_sample_exclusion_is_no_op": True,
        "order_equivalence_condition": "zero global deduplicated PMID overlap"})
    write_jsonl("sampled_source_manifest.jsonl", sampled)
    write_json("sampling_execution_audit.json", {
        "source_frames_frozen_before_sampling": True, "dedup_completed_before_sampling": True,
        "seen_source_audit_completed_before_sampling": True,
        "zero_overlap_guard_passed": True,
        "sampling_seed_sha256": SEED_SHA, "sampling_seed_changed": False,
        "algorithm": "SHA256(seed:stratum:pmid), ascending digest then decimal PMID",
        "sample_cap_per_stratum": 12, "sampled_count": len(sampled),
        "sampled_counts_by_stratum": {key: sum(x["owner_stratum"] == key for x in sampled)
                                      for key in STRATA},
        "replacement_performed": False, "refill_performed": False,
        "sampled_source_manifest_sha256": master.digest(OUT / "sampled_source_manifest.jsonl")})
    write_json("validation.json", {
        "status": "completed", "a2_root_verified": True, "six_source_frames_frozen": True,
        "source_queries_changed": False, "cohort_changed": False,
        "sampling_seed_changed": False, "scientific_policy_changed": False,
        "registry_hash_verified": True, "global_seen_overlap_zero": True,
        "sampled_identity_count": len(sampled), "network_calls": 0,
        "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
        "metadata_oa_jats_builder_quality_executed": False,
        "historical_assets_modified": False})
    write_json("summary.json", {
        "status": "completed", "source_root_sha256": A2_SHA,
        "raw_record_count": raw_count, "unique_pmid_count": len(memberships),
        "duplicate_record_count": raw_count - len(memberships),
        "seen_registry_count": len(seen), "naturally_overlapping_pmid_count": 0,
        "excluded_source_count": 0, "retained_source_count": len(memberships),
        "sampled_source_count": len(sampled), "sampling_seed_changed": False,
        "scientific_policy_changed": False,
        "ordering_reconciliation": "zero overlap makes pre-sample audit/exclusion a no-op; frozen sample output unchanged",
        "network_calls": 0, "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
        "next_boundary": "ALPHA3_19C_METADATA_AND_SOURCE_ELIGIBILITY"})
    (OUT / ROOT_MARKER).write_text(root_hash() + "\n")
    print(json.dumps({"status": "completed", "root_sha256": (OUT / ROOT_MARKER).read_text().strip(),
                      "unique_pmids": len(memberships), "overlap": 0, "sampled": len(sampled)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
