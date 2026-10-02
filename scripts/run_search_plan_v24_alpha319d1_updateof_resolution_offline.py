#!/usr/bin/env python3
"""Resolve the single alpha3.19D handoff UpdateOf state, offline and mechanically."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts import search_plan_v24_alpha318a3_correction_reference as correction
from scripts import run_search_plan_v24_alpha319c_pubmed_metadata_eligibility as c
from scripts import run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility as d


ROOT = master.ROOT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19d1_updateof_resolution_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19d1_sha256"
C_SHA = "922cc952e03bca7e8605971b9dcb6f4acfe3cfbe02e308ca26c9ab37c3a86689"
D_SHA = "422975cb0706f19a6ee2640bc126fc49892d2e220df34b3f6c25c5a57a5b9a33"
RULE_SHA = "2255fa31b3884b210b76fd636035c84fe448921dfbd7410ebd1a5ff182aa3db2"
IMPLEMENTATION_SHA = "68befecf70cd008a7b0a9154d713decbb14f8e39dc4b945331450d96bf2a3e09"
RULE_PATH = ROOT / (
    "runs/20260927_search_plan_v24_dev_alpha3_18a3_correction_reference_resolution_final_prereg_offline/"
    "correction_reference_eligibility_v1.json")


def require(ok: bool, reason: str):
    if not ok:
        raise RuntimeError(reason)


def load(path: Path):
    return json.loads(path.read_bytes())


def rows(path: Path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def write_json(name: str, value):
    with (OUT / name).open("xb") as handle:
        handle.write(master.canonical(value) + b"\n")


def write_jsonl(name: str, values):
    with (OUT / name).open("xb") as handle:
        for value in values:
            handle.write(master.canonical(value) + b"\n")


def root_hash():
    paths = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != ROOT_MARKER)
    require(not any(path.is_symlink() for path in OUT.rglob("*")), "OUTPUT_SYMLINK_FORBIDDEN")
    return master.sha(master.canonical([[str(path.relative_to(OUT)), master.digest(path)]
                                      for path in paths]))


def preflight():
    require(not OUT.exists(), "ALPHA319D1_OUTPUT_ALREADY_EXISTS_NO_RERUN")
    require(c.root_hash() == C_SHA and (c.OUT / c.ROOT_MARKER).read_text().strip() == C_SHA,
            "ALPHA319C_ROOT_MISMATCH")
    require(d.root_hash() == D_SHA and (d.OUT / d.ROOT_MARKER).read_text().strip() == D_SHA,
            "ALPHA319D_ROOT_MISMATCH")
    rule = load(RULE_PATH)
    require(master.digest(RULE_PATH) == RULE_SHA and
            master.digest(ROOT / rule["implementation"]["path"]) ==
                rule["implementation"]["sha256"] == IMPLEMENTATION_SHA and
            rule["schema_version"] == correction.SCHEMA_VERSION and
            rule["only_clear_admitted"] is True and
            rule["UpdateOf_finalization"] ==
                "provisional UNRESOLVED before JATS; final CLEAR only when frozen independent "
                "SourceTypeMechanicalEligibilityV1 is ELIGIBLE; INELIGIBLE if it is INELIGIBLE; "
                "otherwise UNRESOLVED",
            "FROZEN_UPDATEOF_RULE_MISMATCH")
    d_states = rows(d.OUT / "construction_eligibility_states.jsonl")
    d_handoff = rows(d.OUT / "construction_source_handoff_manifest.jsonl")
    c_records = rows(c.OUT / "sampled_metadata_records_v3.jsonl")
    c_by_pmid = {row["pmid"]: row for row in c_records}
    pending = [row for row in d_handoff
               if row["construction_eligibility_state"] ==
                  "CONDITIONAL_UPDATEOF_PENDING_FROZEN_FINALIZATION"]
    direct = [row for row in d_handoff
              if row["construction_eligibility_state"] == "CONSTRUCTION_SOURCE_ELIGIBLE"]
    excluded = [row for row in d_states
                if row["construction_eligibility_state"] not in
                   {"CONSTRUCTION_SOURCE_ELIGIBLE",
                    "CONDITIONAL_UPDATEOF_PENDING_FROZEN_FINALIZATION"}]
    require(len(d_states) == 42 and len(d_handoff) == 15 and len(direct) == 14 and
            len(pending) == 1 and len(excluded) == 27 and
            len(c_records) == len(c_by_pmid) == 72 and
            len({row["pmid"] for row in d_states}) == 42,
            "ALPHA319D_14_1_27_BOUNDARY_MISMATCH")
    target = pending[0]
    matches = [row for row in d_states if row["pmid"] == target["pmid"]]
    require(len(matches) == 1 and target["pmid"] in c_by_pmid,
            "UPDATEOF_SOURCE_IDENTITY_MISMATCH")
    state = matches[0]
    metadata = c_by_pmid[target["pmid"]]
    require(target["pmcid"] == state["pmcid"] == metadata["pmcid"] and
            target["opaque_source_token"] == state["opaque_source_token"] and
            target["builder_ready"] is False and
            target["updateof_deferred_unresolved"] is True and
            state["updateof_deferred_unresolved"] is True and
            metadata["updateof_deferred_state"] == "DEFERRED_TO_STRUCTURE_STAGE" and
            metadata["correction_reference_state"] == "UNRESOLVED" and
            metadata["correction_unresolved_reasons"] ==
                ["REF_TYPE:UpdateOf:INDEPENDENT_SOURCE_NOT_YET_ELIGIBLE"] and
            metadata["correction_ineligible_reasons"] == [] and
            metadata["correction_relationships"] and
            all(ref["ref_type"] == "UpdateOf" for ref in metadata["correction_relationships"]) and
            state["source_type_state"] in
                {"SOURCE_TYPE_ELIGIBLE", "SOURCE_TYPE_INELIGIBLE", "SOURCE_TYPE_UNRESOLVED"} and
            state["oa_subset_state"] == "OA_SUBSET_ELIGIBLE" and
            state["license_state"] == "ELIGIBLE" and
            state["jats_terminal_state"] == "JATS_CANONICALIZED",
            "UPDATEOF_FROZEN_EVIDENCE_BOUNDARY_MISMATCH")
    return d_states, d_handoff, metadata, state, target, excluded, direct


def main():
    d_states, d_handoff, metadata, state, target, excluded, direct = preflight()
    result = correction.classify(metadata["publication_types"],
                                 metadata["correction_relationships"],
                                 independent_primary_state=state["source_type_state"])
    terminal = result["state"].removeprefix("CORRECTION_REFERENCE_")
    require(terminal in {"CLEAR", "INELIGIBLE", "UNRESOLVED"} and
            result["schema_version"] == correction.SCHEMA_VERSION,
            "UPDATEOF_TERMINAL_STATE_INVALID")
    provenance = {"alpha3_19c_root_sha256": C_SHA, "alpha3_19d_root_sha256": D_SHA,
        "frozen_updateof_rule_sha256": RULE_SHA,
        "frozen_updateof_implementation_sha256": IMPLEMENTATION_SHA,
        "c_metadata_record_sha256": master.sha(master.canonical(metadata)),
        "d_eligibility_record_sha256": master.sha(master.canonical(state)),
        "d_handoff_record_sha256": master.sha(master.canonical(target)),
        "decision_basis": "frozen correction RefType fields and independent frozen mechanical source-type state",
        "scientific_content_or_builder_compatibility_used": False}
    revised_state = dict(state)
    revised_state["correction_reference_final_state"] = result["state"]
    revised_state["updateof_resolution_state"] = terminal
    revised_state["updateof_resolution_provenance"] = provenance
    revised_state["updateof_deferred_unresolved"] = terminal == "UNRESOLVED"
    if terminal == "CLEAR":
        revised_state["construction_eligibility_state"] = "CONSTRUCTION_SOURCE_ELIGIBLE"
    else:
        revised_state["construction_eligibility_state"] = "BLOCKED_UPDATEOF_" + terminal
    revised_handoff = dict(target)
    revised_handoff["correction_reference_final_state"] = result["state"]
    revised_handoff["updateof_resolution_state"] = terminal
    revised_handoff["updateof_resolution_provenance"] = provenance
    revised_handoff["updateof_deferred_unresolved"] = terminal == "UNRESOLVED"
    revised_handoff["construction_eligibility_state"] = revised_state["construction_eligibility_state"]
    revised_handoff["builder_ready"] = terminal == "CLEAR"
    final_states = [revised_state if row["pmid"] == target["pmid"] else row
                    for row in d_states]
    final_handoff = [revised_handoff if row["pmid"] == target["pmid"] else row
                     for row in d_handoff if row["pmid"] != target["pmid"] or terminal == "CLEAR"]
    require(len(final_states) == 42 and
            len(final_handoff) == (15 if terminal == "CLEAR" else 14) and
            [row for row in final_states if row["pmid"] != target["pmid"]] ==
                [row for row in d_states if row["pmid"] != target["pmid"]] and
            [row for row in final_handoff if row["pmid"] != target["pmid"]] == direct and
            [row for row in final_states if row["pmid"] in {x["pmid"] for x in excluded}] == excluded,
            "UNRELATED_SOURCE_STATE_CHANGED")
    OUT.mkdir()
    write_json("updateof_resolution.json", {"pmid": target["pmid"], "pmcid": target["pmcid"],
        "terminal_state": terminal, "frozen_classifier_result": result,
        "independent_source_type_state": state["source_type_state"],
        "provenance": provenance, "replacement_source": False})
    write_jsonl("final_construction_eligibility_states.jsonl", final_states)
    write_jsonl("final_construction_source_manifest.jsonl", final_handoff)
    write_jsonl("source_identity_provenance.jsonl", [
        {"pmid": before["pmid"], "pmcid": before["pmcid"],
         "d_record_sha256": master.sha(master.canonical(before)),
         "d1_record_sha256": master.sha(master.canonical(after)),
         "state_changed": before != after}
        for before, after in zip(d_states, final_states)])
    write_json("validation.json", {"status": "completed",
        "alpha3_19c_root_unchanged": c.root_hash() == C_SHA,
        "alpha3_19d_root_unchanged": d.root_hash() == D_SHA,
        "direct_14_records_unchanged": True, "excluded_27_records_unchanged": True,
        "exactly_one_deferred_handoff_source_resolved": True,
        "terminal_state_valid": terminal in {"CLEAR", "INELIGIBLE", "UNRESOLVED"},
        "final_state_count": len(final_states),
        "final_construction_source_count": len(final_handoff),
        "network_calls": 0, "pubmed_metadata_reruns": 0, "pmc_jats_refetches": 0,
        "model_calls": 0, "builder_calls": 0, "quality_calls": 0,
        "construction_documents_generated": 0, "span_anchors_generated": 0,
        "heldout_cases_created": 0, "sampling_changed": False,
        "oa_license_jats_source_type_decisions_changed": False})
    write_json("summary.json", {"status": "completed",
        "resolved_pmid": target["pmid"], "updateof_terminal_state": terminal,
        "direct_construction_sources_preserved": 14,
        "excluded_sources_preserved": 27,
        "final_construction_source_count": len(final_handoff),
        "final_construction_manifest_sha256": master.digest(
            OUT / "final_construction_source_manifest.jsonl"),
        "source_identity_provenance_sha256": master.digest(
            OUT / "source_identity_provenance.jsonl"),
        "network_calls": 0, "model_calls": 0, "builder_calls": 0,
        "next_boundary": "ALPHA3_19E_BUILDER_PREPARATION_SEPARATE_AUTHORIZATION"})
    (OUT / ROOT_MARKER).write_text(root_hash() + "\n")
    print(json.dumps({"status": "completed", "root_sha256":
        (OUT / ROOT_MARKER).read_text().strip(), "resolved_pmid": target["pmid"],
        "updateof_terminal_state": terminal,
        "final_construction_source_count": len(final_handoff)}, sort_keys=True))


if __name__ == "__main__":
    main()
