"""Offline guards for ownership, seed binding, exclusion and frozen replay."""

import hashlib
import json
import socket
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import run_search_plan_v24_alpha321b_source_selection_offline as m


def occurrence(pmid, stratum, ordinal, start=0, position=1):
    return {"pmid": pmid, "stratum_id": stratum,
            "raw_acquisition_ordinal": ordinal, "retstart": start,
            "within_page_position": position, "logical_page_id": f"page{ordinal}",
            "raw_response_sha256": "a" * 64, "validator_state": "VALID_NONZERO",
            "trusted_for_normal_acquisition_corpus": True}


def test_owner_is_earliest_stratum_even_when_its_page_arrives_later():
    raw = [occurrence("123", "second", 1),
           occurrence("123", "first", 2, 50, 3)]
    unique = m.deduplicate(raw, ["first", "second"])
    assert len(unique) == 1
    assert unique[0]["owner_stratum"] == "first"
    assert unique[0]["retained_within_stratum_rank"] == 53
    assert {r["raw_acquisition_ordinal"] for r in unique[0]["raw_acquisition_memberships"]} == {1, 2}


@pytest.mark.parametrize("pmid", ["0123", "0", "123.0", " 123", 123])
def test_noncanonical_pmid_fails_closed(pmid):
    with pytest.raises(m.StageFailure, match="PMID_IDENTITY_UNRESOLVED"):
        m.deduplicate([occurrence(pmid, "first", 1)], ["first"])


def test_unbound_ownership_authority_is_not_replaced(monkeypatch):
    original = m.obj

    def read(path):
        value = original(path)
        if path.name == "cross_stratum_dedup_contract.json":
            value["owner"] = "best rank wins"
        return value

    monkeypatch.setattr(m, "obj", read)
    with pytest.raises(m.StageFailure, match="CROSS_STRATUM_OWNERSHIP_AUTHORITY_UNRESOLVED"):
        m.resolve_authorities()


def test_changed_seed_fails_closed(monkeypatch):
    original = m.obj

    def read(path):
        value = original(path)
        if path.name == "alpha3_21_sampling_seed_derivation.json":
            value["sampling_algorithm_seed_text"] = "0" * 64
        return value

    monkeypatch.setattr(m, "obj", read)
    with pytest.raises(m.StageFailure, match="SAMPLING_ALGORITHM_AUTHORITY_UNRESOLVED"):
        m.resolve_authorities()


def test_frozen_sample_handles_short_and_empty_strata_without_topup(monkeypatch):
    state = m.resolve_authorities()
    with TemporaryDirectory(prefix="alpha321b_short_test_", dir=m.RUNS) as temporary:
        monkeypatch.setattr(m, "OUT", Path(temporary))
        strata = state["strata"]
        universe = m.deduplicate([occurrence(str(i + 1), strata[0], i + 1)
                                 for i in range(3)], strata)
        m.freeze_rows("fresh_source_universe_global", universe)
        by_sha = m.put("fresh_source_universe_by_stratum.json", {
            "global_universe_sha256": m.digest(m.OUT / "fresh_source_universe_global.jsonl"),
            "strata": [{"stratum_id": s, "pmids": [r["pmid"] for r in universe
                          if r["owner_stratum"] == s]} for s in strata]})
        m.put_bytes("fresh_source_universe_by_stratum_sha256", (by_sha + "\n").encode())
        m.put("sampling_seed_binding.json", {"seed_artifact": m.ref(state["seed_path"], "seed")})
        result = m.sample_from_frozen_inputs(state)
        assert len(result) == 3
        assert {r["owner_stratum"] for r in result} == {strata[0]}


def test_full_offline_freeze_matches_independent_reference(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Network is prohibited in alpha3.21B")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    with TemporaryDirectory(prefix="alpha321b_execution_test_", dir=m.RUNS) as temporary:
        monkeypatch.setattr(m, "OUT", Path(temporary) / "run")
        result = m.run()
        assert result["status"] == "completed"
        assert m.root_hash(m.OUT, m.ROOT_MARKER) == result[m.ROOT_MARKER]
        assert result["sampling_replay_byte_identical"] is True
        assert all(result[key] == 0 for key in m.NO_CALLS)
        state = m.verify_inputs()
        raw = state["raw"]
        owner = {pmid: next(s for s in state["strata"] if any(
                    r["pmid"] == pmid and r["stratum_id"] == s for r in raw))
                 for pmid in {r["pmid"] for r in raw}}
        fresh = set(owner) - state["seen"]
        expected = []
        for stratum in state["strata"]:
            candidates = [p for p in fresh if owner[p] == stratum]
            candidates.sort(key=lambda p: (hashlib.sha256(
                f"{state['seed_text']}:{stratum}:{p}".encode()).digest(), int(p)))
            expected.extend(candidates[:12])
        sample = m.rows(m.OUT / "sampled_source_manifest.jsonl")
        assert [r["pmid"] for r in sample] == expected
        assert result["fresh_unique_pmid_count"] == len(fresh)
        assert result["preexisting_seen_intersection_count"] == len(set(owner) & state["seen"])
        assert result["current_attempt_exposure_used_as_current_exclusion"] is False
        assert result["sampled_source_count"] > 0  # All exposed IDs were not self-excluded.
        assert len(sample) <= 72
        assert (m.OUT / "sampled_source_manifest.jsonl").read_bytes() == \
            (m.OUT / "sampled_source_manifest_replay.jsonl").read_bytes()
        with pytest.raises(m.StageFailure, match="OUTPUT_ALREADY_EXISTS"):
            m.run()


def test_fresh_universe_tampering_stops_sampling(monkeypatch):
    state = m.resolve_authorities()
    with TemporaryDirectory(prefix="alpha321b_tamper_test_", dir=m.RUNS) as temporary:
        monkeypatch.setattr(m, "OUT", Path(temporary))
        m.freeze_rows("fresh_source_universe_global", [])
        # No by-stratum freeze marker exists, so the sample barrier cannot be passed.
        with pytest.raises((OSError, m.StageFailure)):
            m.sample_from_frozen_inputs(state)
