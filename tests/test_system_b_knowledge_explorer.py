import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from code_engine.system_b.explorer.explorer_api import BOUNDARY, ExplorerAPI
from code_engine.system_b.explorer.explorer_server import make_handler

def write_jsonl(path, rows): path.write_text("".join(json.dumps(x) + "\n" for x in rows))

class KnowledgeExplorerTests(unittest.TestCase):
    def fixture(self, root):
        entities=[{"entity_id":"e1","label":"A","display_label":"A","aliases":["A"],"entity_type":"gene","degree":1,"evidence_count":2,"display_priority_score":.8,"source_case_ids":["case"]},{"entity_id":"e2","label":"B","display_label":"B","aliases":["B"],"entity_type":"biological_process","degree":1,"evidence_count":2,"display_priority_score":.7,"source_case_ids":["case"]}]
        triples=[{"triple_id":"t1","subject_id":"e1","subject_display_label":"A","relation_normalized":"promotes","object_id":"e2","object_display_label":"B","evidence_count":2,"fulltext_evidence_count":1,"results_section_evidence_count":1,"case_ids":["case"],"conflict_status":"none","display_priority_score_v2":.8,"ui_badges":["fulltext_supported"]}]
        chains=[{"chain_id":"c1","entity_path":["A","B"],"relation_path":["promotes"],"triple_ids":["t1"],"depth":1,"evidence_count_sum":2,"fulltext_evidence_count_sum":1,"results_section_evidence_count_sum":1,"case_ids":["case"],"conflict_statuses":[],"chain_quality_score":.8}]
        case_t=[{"case_id":"case","triple_id":"t1","subject_label":"A","relation_normalized":"promotes","object_label":"B","case_evidence_count":2,"case_fulltext_evidence_count":1,"case_results_section_evidence_count":1,"case_display_priority_score":.9,"case_display_rank":1}]
        case_c=[{"case_id":"case","chain_id":"c1","entity_path":["A","B"],"relation_path":["promotes"],"triple_ids":["t1"],"case_evidence_count_sum":2,"case_fulltext_evidence_count_sum":1,"case_chain_quality_score":.9,"case_display_rank":1}]
        evidence=[{"triple_id":"t1","case_id":"case","source_scope":"fulltext","section_title":"Results","evidence_sentence":"A promotes B.","source_file":"x.jsonl","source_line":1}]
        for name,rows in (("display_entities_v2.jsonl",entities),("display_triples_v2.jsonl",triples),("display_chains_v2.jsonl",chains),("case_focused_triples.jsonl",case_t),("case_focused_chains.jsonl",case_c),("triple_evidence_links.jsonl",evidence)):write_jsonl(root/name,rows)
        write_jsonl(root/"validator_annotations.jsonl",[{"case_id":"case","validator_name":"reactome","status":"available"}]);write_jsonl(root/"conflict_lens_records.jsonl",[])

    def test_api_cache_filters_details_boundaries_and_missing_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);api=ExplorerAPI(root,root/"missing-review")
            status,summary=api.dispatch("/api/summary");self.assertEqual(status,200);self.assertEqual(summary["display_entities"],2);self.assertEqual(summary["scientific_boundary"],BOUNDARY)
            _,rows=api.dispatch("/api/entities",{"limit":["1"],"q":["A"]});self.assertEqual(rows["total"],1);self.assertEqual(len(rows["items"]),1)
            _,case=api.dispatch("/api/case/case");self.assertEqual(case["triples"][0]["triple_id"],"t1");self.assertEqual(case["chains"][0]["chain_id"],"c1")
            _,triple=api.dispatch("/api/triple/t1");self.assertEqual(triple["evidence_links"][0]["evidence_sentence"],"A promotes B.");self.assertEqual(triple["validator_annotations"][0]["validator_name"],"reactome")
            _,chains=api.dispatch("/api/chains",{"limit":["1"]});self.assertEqual(len(chains["items"]),1)
            self.assertEqual({x["display_label"] for x in api.entities},{"A","B"});self.assertNotIn("reactome",{x["display_label"].lower() for x in api.entities})

    def test_missing_display_files_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(FileNotFoundError,"Run system_b_build_clean_kg first"):ExplorerAPI(tmp)

    def test_templates_render_for_all_views_and_cli_handler_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);handler=make_handler(root,None);server=ThreadingHTTPServer(("127.0.0.1",0),handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                base=f"http://127.0.0.1:{server.server_port}";opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for path in ("/","/cases","/entities","/chains","/conflicts","/case/case","/triple/t1"):
                    text=opener.open(base+path).read().decode();self.assertIn(BOUNDARY,text)
                summary=json.loads(opener.open(base+"/api/summary").read());self.assertEqual(summary["display_triples"],1)
            finally:server.shutdown();thread.join();server.server_close()

if __name__=="__main__":unittest.main()
