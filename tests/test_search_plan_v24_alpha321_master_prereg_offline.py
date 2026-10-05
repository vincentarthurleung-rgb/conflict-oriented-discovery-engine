"""Focused offline checks for alpha3.21 fresh-primary preregistration."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts import run_search_plan_v24_alpha321_master_prereg_offline as m


def test_six_frozen_queries_change_only_publication_dates() -> None:
    old = m.rows(m.A19 / "alpha3_19_source_query_set.jsonl")
    new = m.derive_queries()
    assert len(old) == len(new) == 6
    for source, derived in zip(old, new):
        assert derived["stratum_id"] == source["stratum_id"]
        assert derived["query_utf8"].replace("2026/01/01", "2024/01/01")\
            .replace("2026/09/30", "2025/12/31") == source["query_utf8"]
        assert '"pubmed pmc"[sb]' in derived["query_utf8"]


def test_seen_registry_includes_failed_pages_and_v4_candidates() -> None:
    registry = m.build_registry()
    pmids = {row["pmid"] for row in registry["sources"]}
    base = {row["pmid"] for row in m.rows(m.M20 /
            "alpha3_20_combined_seen_source_registry.jsonl")}
    failed = {str(pmid) for row in m.rows(m.A19_FAILED /
              "source_query_execution_results.jsonl")
              for pmid in ((row.get("validity") or {}).get("idlist") or [])}
    assert base | failed <= pmids
    historical = {row["candidate_id"] for row in m.rows(m.M20 /
                  "alpha3_20_combined_seen_candidate_registry.jsonl")}
    v4 = {row["historical_controller_payload_id"] for row in m.rows(m.D20 /
          "alpha3_20d_candidate_identity_manifest.jsonl")}
    assert {row["candidate_id"] for row in registry["candidates"]} == historical | v4
    assert len(v4) == 126


def test_temp_master_freeze_is_reproducible_without_execution(monkeypatch) -> None:
    with TemporaryDirectory(prefix="alpha321_master_test_", dir=m.RUNS) as temporary:
        output = Path(temporary) / "master"
        monkeypatch.setattr(m, "OUT", output)
        result = m.run()
        assert m.root_hash(output, m.ROOT_MARKER) == result[m.ROOT_MARKER]
        assert result["fresh_primary_attempt"] is True
        assert result["fresh_primary_source_acquisition_started"] is False
        assert result["provider_calls"] == result["network_calls"] == 0
        registry = json.loads((output /
            "alpha3_21_seen_contamination_registry.json").read_text())
        assert result["seen_unique_pmids"] == len(registry["source_identities"])
        assert result["seen_unique_candidate_identities"] == len(
            registry["candidate_identities"])
        seed = json.loads((output / "alpha3_21_sampling_seed_derivation.json").read_text())
        preimage = (m.F1_ROOT + "\n" +
                    "alpha3.21_fresh_primary_sampling_v1").encode("utf-8")
        assert seed["derived_seed_bytes_hex"] == hashlib.sha256(preimage).hexdigest()
        assert seed["derived_seed_bytes_sha256"] == hashlib.sha256(
            bytes.fromhex(seed["derived_seed_bytes_hex"])).hexdigest()
        assert m.root_hash(m.F, "search_plan_v24_dev_alpha3_20f_sha256") == m.F_ROOT
        assert m.root_hash(m.F1, "search_plan_v24_dev_alpha3_20f1_sha256") == m.F1_ROOT
