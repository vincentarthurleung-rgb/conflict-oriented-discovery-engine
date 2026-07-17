import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.steps import run_l2_abstract_step, run_l2_step


class CountingClient:
    def __init__(self, entity_type): self.calls=0; self.entity_type=entity_type
    def search(self, surface, request=None): self.calls += 1; return [{"id":surface,"canonical_name":surface,"entity_type":self.entity_type,"score":.9}]


class RouteClient:
    def __init__(self, records):
        self.calls = 0
        self.records = records
        self.network_call_cost = 1

    def search(self, surface, request=None, ontologies=None):
        self.calls += 1
        return self.records


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

    def test_progressive_l2_runtime_hint_absence_does_not_gate_provider_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts"
            artifacts.mkdir(parents=True)
            (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "general_biomedical"}))
            (artifacts / "semantic_search_intent.json").write_text(json.dumps({}))
            (artifacts / "intake.json").write_text(json.dumps({}))
            claim = {
                "claim_id": "C1",
                "evidence_id": "C1",
                "paper_id": "P1",
                "subject_raw": "EMT",
                "subject_type": "biological_process",
                "object_raw": "TGF-β",
                "object_type": "protein",
                "relation_raw": "induces",
                "relation_family": "regulation",
                "direction": "positive",
                "evidence_sentence": "TGF-β induces EMT.",
            }
            (artifacts / "abstract_l1_claims.jsonl").write_text(json.dumps(claim) + "\n")
            ols = RouteClient([{
                "obo_id": "GO:0001837",
                "label": "epithelial to mesenchymal transition",
                "ontology_name": "go",
                "ontology_prefix": "GO",
                "exact_synonyms": ["EMT"],
                "iri": "http://purl.obolibrary.org/obo/GO_0001837",
            }])
            uniprot = RouteClient([{"canonical_id": "UniProt:P01137", "canonical_name": "Transforming growth factor beta-1", "entity_type": "protein", "score": 0.9}])
            mygene = RouteClient([{"canonical_id": "EntrezGene:7040", "canonical_name": "TGFB1", "entity_type": "protein", "score": 0.9}])

            run_l2_abstract_step(
                run_dir=root,
                execute=True,
                network=True,
                api=True,
                entity_network_lookup=True,
                entity_external_clients={"ols": ols, "uniprot": uniprot, "mygene": mygene},
            )

            self.assertGreater(uniprot.calls, 0)
            self.assertGreater(mygene.calls, 0)
            decisions = [json.loads(line) for line in (artifacts / "entity_resolution_decisions.jsonl").read_text().splitlines()]
            tgf = next(item for item in decisions if item["request"]["surface"] == "TGF-β")
            providers = {trace["provider_name"] for trace in tgf["provider_trace"] if trace["status"] != "not_applicable"}
            self.assertIn("UniProtCandidateProvider", providers)
            self.assertIn("MyGeneCandidateProvider", providers)
            self.assertEqual(tgf["decision_run_id"], root.name)
            candidates_text = (artifacts / "entity_resolution_candidates.jsonl").read_text()
            self.assertIn("UniProt:P01137", candidates_text)
            self.assertNotIn("accepted_into_resolver_decision", candidates_text)
            mention_audit = (artifacts / "l2_entity_resolution_mentions.jsonl").read_text()
            self.assertIn("no_runtime_hint_match_resolver_attempted", mention_audit)
            observations = json.loads((artifacts / "l2_abstract_observations.json").read_text())
            self.assertEqual(observations[0]["subject_canonical_id"], "GO:0001837")

    def test_progressive_l2_hint_only_mode_explicitly_skips_missing_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts"
            artifacts.mkdir(parents=True)
            (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "general_biomedical"}))
            (artifacts / "semantic_search_intent.json").write_text(json.dumps({}))
            (artifacts / "intake.json").write_text(json.dumps({}))
            claim = {
                "claim_id": "C1",
                "evidence_id": "C1",
                "paper_id": "P1",
                "subject_raw": "TGF-β",
                "subject_type": "protein",
                "object_raw": "EMT",
                "object_type": "biological_process",
                "relation_raw": "induces",
                "relation_family": "regulation",
                "direction": "positive",
                "evidence_sentence": "TGF-β induces EMT.",
            }
            (artifacts / "abstract_l1_claims.jsonl").write_text(json.dumps(claim) + "\n")
            uniprot = RouteClient([{"canonical_id": "UniProt:P01137", "canonical_name": "Transforming growth factor beta-1", "entity_type": "protein", "score": 0.9}])

            run_l2_abstract_step(
                run_dir=root,
                execute=True,
                network=True,
                api=True,
                entity_network_lookup=True,
                entity_external_clients={"uniprot": uniprot},
                resolver_mode="hint_only",
            )

            self.assertEqual(uniprot.calls, 0)
            mention_audit = (artifacts / "l2_entity_resolution_mentions.jsonl").read_text()
            self.assertIn("no_runtime_hint_match_hint_only_skip", mention_audit)


if __name__ == "__main__": unittest.main()
