import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.steps import run_l2_abstract_step
from code_engine.normalization.registry import PILOT_REGISTRY_PATH


class ProgressiveResolverWiringTests(unittest.TestCase):
    def test_neuropharmacology_defaults_resolve_pilot_entities(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts=Path(tmp)/"artifacts"; artifacts.mkdir()
            (artifacts/"domain_profile.json").write_text(json.dumps({"domain_id":"neuropharmacology"}))
            claims=[{"claim_id":str(i),"paper_id":f"P{i}","subject_raw":subject,"subject_type":"compound","object_raw":obj,"object_type":"gene","direction":"increase"} for i,(subject,obj) in enumerate((("ketamine","BDNF"),("esketamine","mTOR")))]
            (artifacts/"abstract_l1_claims.jsonl").write_text("".join(json.dumps(x)+"\n" for x in claims))
            run_l2_abstract_step(run_dir=Path(tmp),l1_mode="abstract_screening",entity_registry_path=PILOT_REGISTRY_PATH,pilot_terms=["ketamine","esketamine","BDNF","mTOR"])
            rows=json.loads((artifacts/"l2_abstract_observations.json").read_text())
            self.assertEqual(rows[0]["subject_canonical_id"],"CHEM:KETAMINE")
            self.assertEqual(rows[0]["object_canonical_id"],"GENE:BDNF")
            self.assertEqual(rows[1]["subject_canonical_id"],"CHEM:ESKETAMINE")
            self.assertEqual(rows[1]["object_canonical_id"],"GENE:MTOR")


if __name__ == "__main__": unittest.main()
