"""Regression checks for the offline alpha3.19A acquisition freeze."""
import unittest

from scripts import search_plan_v24_alpha319a_preregister_source_acquisition_offline as prereg
from scripts import search_plan_v24_alpha319_master_preregister_offline as master


class Alpha319AAcquisitionPreregTests(unittest.TestCase):
    def test_upstream_roots_and_output_markers(self):
        self.assertEqual(prereg.frozen_root(master.OUT,
            "search_plan_v24_dev_alpha3_19_master_prereg_sha256"), prereg.MASTER_SHA)
        self.assertEqual(prereg.root_hash(),
            (prereg.OUT / "search_plan_v24_dev_alpha3_19a_prereg_sha256").read_text().strip())
        for stem in ("alpha3_19_source_query_set", "alpha3_19a_source_acquisition_execution_manifest"):
            self.assertEqual(master.digest(prereg.OUT / (stem + (".jsonl" if stem.endswith("query_set") else ".json"))),
                             (prereg.OUT / (stem + "_sha256")).read_text().strip())

    def test_query_delta_and_sampling_order(self):
        query_rows = master.rows(prereg.OUT / "alpha3_19_source_query_set.jsonl")
        old_rows = [r for r in master.rows(master.A18 / "source_query_request_manifest.jsonl")
                    if r["page_retstart"] == 0]
        self.assertEqual(len(query_rows), len(old_rows), 6)
        for current, old in zip(query_rows, old_rows):
            self.assertEqual(current["query_utf8"].replace(
                '"2024/01/01"[Date - Publication] : "2025/12/31"[Date - Publication]',
                '"2018/01/01"[Date - Publication] : "2023/12/31"[Date - Publication]'),
                old["parameters"]["term"])
            self.assertIn('"pubmed pmc"[sb]', current["query_utf8"])
        sampling = prereg.load(prereg.OUT / "sampling_execution_contract.json")
        self.assertTrue(sampling["sampling_before_historical_contamination_exclusion"])
        self.assertFalse(sampling["seen_source_pre_filter"])
        self.assertFalse(sampling["replacement_allowed"])

    def test_manifest_frozen_bindings_and_no_runtime_choice(self):
        manifest = prereg.load(prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json")
        self.assertEqual(manifest["material_runtime_policy_unresolved_count"], 0)
        self.assertEqual(manifest["query_count"], 6)
        self.assertIn("sampled_metadata_execution", manifest)
        self.assertIn("jats_handoff", manifest)
        self.assertEqual(manifest["network_scope"]["allowed_host"], "eutils.ncbi.nlm.nih.gov")
        self.assertEqual(set(manifest["network_scope"]["allowed_endpoints"]), {prereg.ES, prereg.EF})

        def visit(value):
            if isinstance(value, dict):
                if "path" in value and "sha256" in value:
                    prereg.check_ref(value)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(manifest)

    def test_identity_and_phase_boundary(self):
        identity = prereg.load(prereg.OUT / "primary_citation_identity_binding_contract.json")
        self.assertFalse(identity["ReferenceList_identity_contribution"])
        self.assertEqual(identity["matching_records_required"], 1)
        self.assertTrue(identity["runtime_assertions"])
        correction = prereg.load(prereg.OUT / "correction_reference_execution_contract.json")
        self.assertIn("defer finalization to 19B", correction["UpdateOf"])
        metadata = prereg.load(prereg.OUT / "sampled_metadata_contract.json")
        self.assertTrue(metadata["all_frozen_sampled_identities_including_seen_matches"])
        safety = prereg.load(prereg.OUT / "scientific_state_safety_audit.json")
        self.assertTrue(safety["license_interpretation_deferred_to_19b"])
        self.assertTrue(safety["source_type_execution_deferred_to_19b"])
        self.assertTrue(safety["construction_document_generation_deferred_to_19b"])
        self.assertEqual((safety["network_calls"], safety["provider_calls"], safety["llm_calls"]),
                         (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
