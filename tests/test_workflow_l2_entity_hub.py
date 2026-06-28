import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.steps import run_l2_step


class CountingClient:
    def __init__(self, entity_type): self.calls=0; self.entity_type=entity_type
    def search(self, surface, request=None): self.calls += 1; return [{"id":surface,"canonical_name":surface,"entity_type":self.entity_type,"score":.9}]


class WorkflowL2HubTests(unittest.TestCase):
    def _run_dir(self, root):
        artifacts = root / "artifacts"; data = artifacts / "l1_5_data"; data.mkdir(parents=True)
        (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id":"general_biomedical","entity_registry_profile":"general_entity_resolution_hub","resolver_policy_id":"conservative_resolver_v2"}))
        payload={"asset_id":"P1","chunks_extracted":[{"chunk_index":0,"raw_samples":[{"causal_tuples":[{"subject":"sirolimus","object":"MTOR","relation_sign":1,"evidence_sentence":"Sirolimus affects MTOR."}]}]}]}
        (data / "P1_refined.json").write_text(json.dumps(payload))

    def test_artifacts_provider_usage_and_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self._run_dir(root); client=CountingClient("compound")
            result=run_l2_step(run_dir=root, execute=False, network=False, api=False, entity_network_lookup=True, entity_llm_proposer=True, entity_external_clients={"pubchem":client})
            self.assertEqual(client.calls, 0)
            self.assertIn("entity_resolution_audit", result.artifacts)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self._run_dir(root); pub=CountingClient("compound"); gene=CountingClient("gene")
            result=run_l2_step(run_dir=root, execute=True, network=True, api=False, entity_network_lookup=True, entity_external_clients={"pubchem":pub,"mygene":gene})
            self.assertGreater(pub.calls + gene.calls, 0)
            self.assertTrue(result.summary["provider_usage_counts"])
            self.assertTrue((root/"artifacts/entity_resolution_candidates.jsonl").exists())


if __name__ == "__main__": unittest.main()
