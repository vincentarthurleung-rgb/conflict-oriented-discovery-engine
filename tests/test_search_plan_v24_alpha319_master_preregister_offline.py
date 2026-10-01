"""Focused checks of the frozen alpha3.19 offline master preregistration."""
import unittest

from scripts import search_plan_v24_alpha319_master_preregister_offline as plan


class Alpha319MasterPreregTests(unittest.TestCase):
    def test_closure_and_root(self):
        self.assertEqual(
            plan.root_hash({"search_plan_v24_dev_alpha3_19_master_prereg_sha256"}),
            (plan.OUT / "search_plan_v24_dev_alpha3_19_master_prereg_sha256").read_text().strip(),
        )
        summary = plan.load(plan.OUT / "summary.json")
        self.assertTrue(summary["alpha3_18_closed_and_preserved"])
        self.assertTrue(summary["alpha3_19_new_attempt"])
        self.assertFalse(summary["alpha3_18_scientific_assets_reused"])
        self.assertEqual(summary["provider_calls"], 0)
        self.assertEqual(summary["network_calls"], 0)

    def test_historical_firewall(self):
        sources = plan.rows(plan.OUT / "alpha3_18_seen_source_registry.jsonl")
        candidates = plan.rows(plan.OUT / "alpha3_18_seen_candidate_registry.jsonl")
        groups = plan.rows(plan.OUT / "alpha3_18_seen_quality_group_registry.jsonl")
        self.assertEqual(len(sources), 1041)
        self.assertEqual(len({r["pmid"] for r in sources}), 1041)
        self.assertEqual(sum(r["sampled"] for r in sources), 72)
        self.assertEqual(sum(r["construction_source"] for r in sources), 28)
        self.assertEqual(len(candidates), 110)
        self.assertEqual(len(groups), 3)
        self.assertEqual(sum(len(g["candidate_ids"]) for g in groups), 5)
        self.assertFalse(any("scientific_fields" in r or "neutral_proposition" in r
                             for r in candidates))

    def test_queries_are_date_only_delta(self):
        old = [r for r in plan.rows(plan.A18 / "source_query_request_manifest.jsonl")
               if r["page_retstart"] == 0]
        new = plan.rows(plan.OUT / "alpha3_19_source_query_templates.jsonl")
        self.assertEqual(len(old), len(new), 6)
        for before, after in zip(old, new):
            self.assertEqual(before["stratum_id"], after["stratum_id"])
            self.assertEqual(
                after["term"].replace('"2024/01/01"[Date - Publication] : '
                                      '"2025/12/31"[Date - Publication]',
                                      '"2018/01/01"[Date - Publication] : '
                                      '"2023/12/31"[Date - Publication]'),
                before["parameters"]["term"],
            )
            self.assertIn('"pubmed pmc"[sb]', after["term"])

    def test_quality_v3_projects_only_deterministic_fields(self):
        original = plan.load(plan.Q2 / "proposition_quality_adjudication_v2_schema.json")["schema"]
        envelope = plan.load(plan.OUT / "quality_response_envelope_v3.json")
        body = envelope["model_response_body_schema"]
        self.assertEqual(set(body["properties"]), {"judgments"})
        item = body["properties"]["judgments"]["items"]
        self.assertEqual(set(item["properties"]),
                         {"candidate_id", "criteria", "evidence_support_reference"})
        self.assertEqual(item["properties"]["criteria"],
                         original["properties"]["judgments"]["items"]["properties"]["criteria"])
        self.assertFalse(envelope["model_schema_version_required"])
        self.assertEqual(envelope["provider_response_format"], "JSON_OBJECT_ONLY")
        validation = plan.load(plan.OUT / "quality_response_validation_v3.json")
        self.assertTrue(validation["exact_candidate_id_set"])
        self.assertFalse(validation["controller_fill_missing_scientific_fields"])

    def test_file_markers(self):
        for stem in ("quality_response_envelope_v3", "alpha3_19_master_execution_plan"):
            self.assertEqual(plan.digest(plan.OUT / (stem + ".json")),
                             (plan.OUT / (stem + "_sha256")).read_text().strip())


if __name__ == "__main__":
    unittest.main()
