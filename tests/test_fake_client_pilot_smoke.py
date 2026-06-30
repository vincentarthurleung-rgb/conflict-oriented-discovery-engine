import json
import tempfile
import unittest
from pathlib import Path

from code_engine.domain.router import default_domain_router
from code_engine.workflow.models import STEP_ORDER
from code_engine.workflow.orchestrator import run_workflow
from code_engine.workflow.run_state import create_run_state, save_run_state


class FakeClient:
    def extract_json(self, prompt, **_):
        direction = "decrease" if "decreased" in prompt else "increase"
        return {"claims":[{"subject_raw":"ketamine","subject_type":"compound","relation_raw":direction,"object_raw":"BDNF","object_type":"gene","direction":direction,"relation_family":"affects","polarity_type":"effect","evidence_sentence":f"Ketamine {direction}d BDNF."}]}


class FakeClientPilotSmokeTests(unittest.TestCase):
    def test_claim_to_graph_hypothesis_timeline_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); artifacts=root/"artifacts"; artifacts.mkdir()
            papers=[{"paper_id":f"P{i}","canonical_paper_id":f"P{i}","title":f"Paper {i}","publication_year":2010+i,"abstract":"Ketamine decreased BDNF." if i==1 else "Ketamine increased BDNF."} for i in range(3)]
            (artifacts/"acquisition_report.json").write_text(json.dumps({"candidate_papers":papers,"reused_papers":[],"downloaded_papers":[]}))
            (artifacts/"domain_profile.json").write_text(json.dumps(default_domain_router().get_or_default("neuropharmacology").to_dict()))
            (artifacts/"run_paper_manifest.jsonl").write_text("".join(json.dumps(p)+"\n" for p in papers))
            state=create_run_state("ketamine BDNF depression",execute=True,api=True,network=False,until="report",l1_mode="abstract_screening")
            for name in ("intake","search","acquisition","payload"):
                state.steps[name].status="completed"
            save_run_state(state,root)
            result=run_workflow(resume=root,until="report",execute=True,api=True,network=False,allow_uncertain_intake=True,l1_mode="abstract_screening",l1_llm_client=FakeClient(),global_corpus_dir=root/"corpus",merge_knowledge_store=False,pilot_profile="ketamine")
            self.assertGreater(result.steps["evidence_graph_core"].summary["graph_conflict_candidate_count"],0)
            self.assertGreater(result.steps["hypothesis"].summary["hypotheses_from_graph_conflicts"],0)
            self.assertGreater(result.steps["conflict_timeline"].summary["timelines_from_graph_conflicts"],0)
            self.assertTrue((root/"final_report.md").exists())
            self.assertEqual(result.api_calls_made,3)
            self.assertEqual(result.network_calls_made,0)


if __name__ == "__main__": unittest.main()
