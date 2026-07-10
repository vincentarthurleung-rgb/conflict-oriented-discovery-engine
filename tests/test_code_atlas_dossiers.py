import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from code_engine.system_b.explorer.explorer_server import create_app
from code_engine.system_b.explorer.auth import hash_password,write_user_store
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests,write_jsonl


class AtlasDossierTests(unittest.TestCase):
    def test_dossier_id_stable_evidence_context_paths_and_review_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);KnowledgeExplorerTests().fixture(root)
            write_jsonl(root/"manual_review_queue.jsonl",[{"review_item_id":"case::fulltext_l1_claim::claims.jsonl::1","case_id":"case","item_type":"fulltext_l1_claim","subject":"A","relation":"promotes","object":"B","evidence_sentence":"A promotes B.","source_file":"claims.jsonl","source_line":1}])
            api=ExplorerAPI(root,root)
            _,listed=api.dispatch("/api/dossiers",{"limit":["1"]})
            dossier_id=listed["items"][0]["dossier_id"]
            self.assertEqual(dossier_id,api.dossiers.resolve("t1"))
            self.assertEqual(dossier_id,api.dossiers.resolve(dossier_id))
            _,detail=api.dispatch(f"/api/dossier/{dossier_id}")
            self.assertEqual(detail["humanized_statement"],"A 促进 B")
            self.assertEqual(detail["evidence_summary"]["fulltext_count"],1)
            _,evidence=api.dispatch(f"/api/dossier/{dossier_id}/evidence")
            self.assertEqual(evidence["groups"]["supporting"][0]["evidence_sentence"],"A promotes B.")
            _,matrix=api.dispatch(f"/api/dossier/{dossier_id}/context-matrix")
            self.assertEqual(matrix["items"][0]["species"],"未报告")
            _,paths=api.dispatch(f"/api/dossier/{dossier_id}/paths")
            self.assertEqual(paths["items"][0]["chain_id"],"c1")
            _,target=api.dispatch(f"/api/dossier/{dossier_id}/review-target")
            self.assertTrue(target["reviewable"])

    def test_review_target_does_not_fabricate_and_reviewer_redacts_debug(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);KnowledgeExplorerTests().fixture(root)
            api=ExplorerAPI(root,root/"missing")
            did=api.dossiers.resolve("t1")
            self.assertEqual(api.dispatch(f"/api/dossier/{did}/review-target")[1]["reason"],"no_matching_review_item")
            users=root/"users.json";write_user_store(users,{"reviewer":{"username":"reviewer","password_hash":hash_password("correct horse battery staple"),"display_name":"Reviewer","role":"reviewer","enabled":True}},[])
            client=create_app(root,root,require_auth=True,users_file=users,secret_key="x",testing=True).test_client()
            page=client.get("/login").get_data(as_text=True);token=page.split('name="csrf_token" value="',1)[1].split('"',1)[0]
            client.post("/login",data={"username":"reviewer","password":"correct horse battery staple","csrf_token":token})
            payload=client.get(f"/api/dossier/{did}").get_json()
            self.assertNotIn("backing_triple_id",payload)
            self.assertNotIn("source_file",str(payload))


if __name__=="__main__":
    unittest.main()
