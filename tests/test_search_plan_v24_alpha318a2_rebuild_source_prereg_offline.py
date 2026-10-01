"""Focused offline checks for the alpha3.18A.2 fail-closed audit."""

import unittest

from scripts import search_plan_v24_alpha318a2_rebuild_source_prereg_offline as audit


class Alpha318A2AuditTest(unittest.TestCase):
    def test_frozen_upstreams_and_queries(self):
        rows = audit.verify()
        self.assertEqual([row["stratum_id"] for row in rows], audit.STRATA)
        self.assertEqual(len(rows), 6)

    def test_correction_reference_rule_is_not_in_frozen_type_decision(self):
        metadata = audit.load(audit.AMEND, "source_metadata_contract_v2.json")
        decision = audit.load(audit.AMEND, "source_type_three_state_decision_table.json")
        self.assertIn("correction_retraction_refs", [field["name"] for field in metadata["fields"]])
        self.assertNotIn("correction_retraction_refs", decision)

    def test_output_remains_non_executable_and_hash_verified(self):
        validation = audit.load(audit.OUT, "validation.json")
        manifest = audit.load(audit.OUT, "alpha3_18a2_source_acquisition_execution_manifest.json")
        self.assertEqual(validation["status"], "FAILED_CLOSED")
        self.assertEqual(manifest["status"], "NON_EXECUTABLE_FAIL_CLOSED")
        self.assertFalse(manifest["network_execution_authorized"])
        self.assertEqual(validation["network_calls"], 0)
        marker = (audit.OUT / "search_plan_v24_dev_alpha3_18a2_prereg_sha256").read_text().strip()
        self.assertEqual(audit.all_file_root(audit.OUT, "search_plan_v24_dev_alpha3_18a2_prereg_sha256"), marker)


if __name__ == "__main__":
    unittest.main()
