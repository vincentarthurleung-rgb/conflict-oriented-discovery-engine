import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from code_engine.cli.repair_fulltext_candidate_pmcids import repair_fulltext_candidate_pmcids
from code_engine.fulltext.candidate_bridge import canonical_fulltext_candidates, write_candidate_bridge_audit
from code_engine.fulltext.pmc_id_resolver import resolve_authoritative_pmcid_for_pmid


def authoritative(mapping, reverse=None):
    reverse = reverse or {pmcid: pmid for pmid, pmcid in mapping.items() if pmcid}
    def resolve(pmid, **_):
        value = mapping.get(pmid, "NO_MAPPING")
        if value == "NETWORK":
            return {"pmid": pmid, "resolved_pmcid": None, "forward_resolution_status": "network_unavailable", "reverse_observed_pmid": None,
                    "reverse_verification_status": "network_unavailable", "canonical_pmcid_status": "unverified", "resolution_source": "ncbi_idconv", "cache_hit": False, "reason": "offline"}
        if value in {"NO_MAPPING", None}:
            return {"pmid": pmid, "resolved_pmcid": None, "forward_resolution_status": "no_mapping", "reverse_observed_pmid": None,
                    "reverse_verification_status": "missing", "canonical_pmcid_status": "no_pmc_mapping", "resolution_source": "ncbi_idconv", "cache_hit": False, "reason": "none"}
        observed = reverse.get(value)
        verified = observed == pmid
        return {"pmid": pmid, "resolved_pmcid": value, "forward_resolution_status": "resolved", "reverse_observed_pmid": observed,
                "reverse_verification_status": "verified" if verified else "mismatch", "canonical_pmcid_status": "verified" if verified else "rejected",
                "resolution_source": "ncbi_idconv", "cache_hit": False, "reason": "mock"}
    return resolve


def write_source(root: Path, rows: list[dict], name="fulltext_discovery_escalation_candidates.jsonl") -> Path:
    source = root / "source"; artifacts = source / "artifacts"; artifacts.mkdir(parents=True)
    (artifacts / name).write_text("".join(json.dumps(x) + "\n" for x in rows))
    return source


def rows(path: Path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


class PmcidAuthoritativeRepairTests(unittest.TestCase):
    def test_wrong_historical_is_replaced_and_preserved_in_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = write_source(root, [{"pmid": "1", "pmcid": "PMC99", "title": "Wnt-like"}])
            summary = repair_fulltext_candidate_pmcids(source_run=source, output_run=root / "out", network=True,
                authoritative_resolver=authoritative({"1": "PMC10"}))
            candidate = rows(root / "out/artifacts/fulltext_discovery_escalation_candidates.jsonl")[0]
            audit = rows(root / "out/artifacts/pmcid_enrichment_audit.jsonl")[0]
            self.assertEqual(candidate["pmcid"], "PMC10"); self.assertEqual(candidate["verified_pmcid"], "PMC10")
            self.assertEqual(candidate["historical_pmcids"], ["PMC99"])
            self.assertEqual(audit["historical_pmcids"], ["PMC99"]); self.assertEqual(audit["action_taken"], "replaced_historical")
            self.assertEqual(summary["canonical_verified_pmcid_count"], 1)

    def test_two_historical_values_do_not_block_authoritative_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = root / "source"; art = source / "artifacts"; art.mkdir(parents=True)
            (art / "fulltext_discovery_escalation_candidates.jsonl").write_text(json.dumps({"pmid": "1", "pmcid": "PMC10"}) + "\n")
            (art / "fulltext_escalation_candidates.jsonl").write_text(json.dumps({"pmid": "1", "pmcid": "PMC20"}) + "\n")
            repair_fulltext_candidate_pmcids(source_run=source, output_run=root / "out", network=True, authoritative_resolver=authoritative({"1": "PMC20"}))
            candidates, _ = canonical_fulltext_candidates(root / "out/artifacts")
            self.assertEqual(candidates[0]["pmcid"], "PMC20"); self.assertEqual(candidates[0]["pmcid_integrity_status"], "verified")
            audit = write_candidate_bridge_audit(root / "out/artifacts", candidates)
            self.assertTrue(audit[0]["passed_to_oa_diagnostics"])

    def test_forward_response_is_selected_by_exact_pmid_not_order(self):
        def transport(url):
            identifier = parse_qs(urlparse(url).query)["ids"][0]
            if identifier == "2":
                return {"records": [{"pmid": "1", "pmcid": "PMC10"}, {"pmid": "2", "pmcid": "PMC20"}]}
            return {"records": [{"pmid": "2", "pmcid": "PMC20"}]}
        result = resolve_authoritative_pmcid_for_pmid("2", network_enabled=True, transport=transport)
        self.assertEqual(result["resolved_pmcid"], "PMC20"); self.assertEqual(result["canonical_pmcid_status"], "verified")

    def test_reverse_mismatch_blocks_and_stale_value_is_not_retrieved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = write_source(root, [{"pmid": "1", "pmcid": "PMC99"}])
            repair_fulltext_candidate_pmcids(source_run=source, output_run=root / "out", network=True,
                authoritative_resolver=authoritative({"1": "PMC10"}, {"PMC10": "2"}))
            candidate = rows(root / "out/artifacts/fulltext_discovery_escalation_candidates.jsonl")[0]
            self.assertIsNone(candidate["pmcid"]); self.assertEqual(candidate["pmcid_verification_status"], "rejected")
            canonical, _ = canonical_fulltext_candidates(root / "out/artifacts")
            bridge = write_candidate_bridge_audit(root / "out/artifacts", canonical)[0]
            self.assertFalse(bridge["passed_to_oa_diagnostics"]); self.assertNotEqual(bridge["pmcid"], "PMC99")

    def test_no_mapping_network_failure_and_title_only_are_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = write_source(root, [{"pmid": "1"}, {"pmid": "2"}, {"title": "title only"}])
            summary = repair_fulltext_candidate_pmcids(source_run=source, output_run=root / "out", network=True,
                authoritative_resolver=authoritative({"1": None, "2": "NETWORK"}))
            repaired = rows(root / "out/artifacts/fulltext_discovery_escalation_candidates.jsonl")
            self.assertEqual([x["pmcid_verification_status"] for x in repaired], ["no_pmc_mapping", "network_unavailable", "rejected"])
            # Explicit no mapping value in this mock.
            source2 = write_source(root / "second", [{"pmid": "3"}])
            result = repair_fulltext_candidate_pmcids(source_run=source2, output_run=root / "out2", network=True,
                authoritative_resolver=authoritative({}))
            self.assertEqual(result["no_pmc_mapping_count"], 1)

    def test_cache_is_keyed_by_pmid_and_transient_error_is_not_cached(self):
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td); calls = []
            def ok(url):
                identifier = parse_qs(urlparse(url).query)["ids"][0]; calls.append(identifier)
                return {"records": [{"pmid": identifier, "pmcid": "PMC" + identifier}]}
            resolve_authoritative_pmcid_for_pmid("10", network_enabled=True, cache_dir=cache, transport=ok)
            cached = resolve_authoritative_pmcid_for_pmid("10", cache_dir=cache)
            self.assertTrue(cached["cache_hit"]); self.assertTrue((cache / "pmid_10.json").is_file())
            failed = resolve_authoritative_pmcid_for_pmid("11", network_enabled=True, cache_dir=cache, transport=lambda _: (_ for _ in ()).throw(OSError("down")))
            self.assertEqual(failed["forward_resolution_status"], "network_unavailable")
            self.assertFalse((cache / "pmid_11.json").exists())

    def test_existing_valid_ros_like_value_stays_verified(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = write_source(root, [{"pmid": "7", "pmcid": "PMC70"}])
            repair_fulltext_candidate_pmcids(source_run=source, output_run=root / "out", network=True,
                authoritative_resolver=authoritative({"7": "PMC70"}))
            candidate = rows(root / "out/artifacts/fulltext_discovery_escalation_candidates.jsonl")[0]
            self.assertEqual(candidate["pmcid"], "PMC70"); self.assertEqual(candidate["pmcid_verification_status"], "verified")


if __name__ == "__main__":
    unittest.main()
