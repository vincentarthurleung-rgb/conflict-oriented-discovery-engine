import csv
import json
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.annotation_store import AnnotationStore
from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from tests import test_system_b_knowledge_explorer as explorer_support

class AtlasAnnotationTests(unittest.TestCase):
    def queue(self):
        return [{"review_item_id":"case::fulltext_l1_claim::claims.jsonl::1","case_id":"case","item_type":"fulltext_l1_claim","source_file":"claims.jsonl","source_line":1,"claim_text":"A promotes B"},{"review_item_id":"case::non_comparable_direction_pair::pairs.jsonl::1","case_id":"case","item_type":"non_comparable_direction_pair","source_file":"pairs.jsonl","source_line":1,"rejection_reason":"contexts differ"}]

    def test_empty_save_atomic_outputs_update_validation_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);queue=self.queue();store=AnnotationStore(root,queue)
            self.assertEqual(store.records,{});self.assertIsNone(store.metrics()["claim_precision"]);self.assertIsNone(store.metrics()["non_comparable_rejection_accuracy"])
            item=queue[0]["review_item_id"];store.save(item,{"final_label":"VALID","evidence_supported":"1","worth_followup":"1","notes":"first"})
            self.assertTrue((root/"manual_review_annotations_live.json").is_file());self.assertTrue((root/"manual_review_annotations_live.csv").is_file());self.assertTrue((root/"manual_review_metrics_live.json").is_file())
            store.save(item,{"final_label":"PARTIAL","worth_followup":"2","notes":"updated"});self.assertEqual(len(store.records),1);self.assertEqual(store.get(item)["notes"],"updated")
            metrics=store.metrics();self.assertEqual(metrics["reviewed_count"],1);self.assertEqual(metrics["unreviewed_count"],1);self.assertEqual(metrics["claim_precision"],0);self.assertEqual(metrics["claim_usable_rate"],1)
            with self.assertRaisesRegex(ValueError,"final_label"):store.save(item,{"final_label":"TRUE_BIOLOGY"})
            with (root/"manual_review_annotations_live.csv").open() as handle:self.assertIn("final_label",next(csv.reader(handle)))

    def test_review_api_filters_get_post_export_and_evidence_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);explorer_support.KnowledgeExplorerTests().fixture(root);queue=self.queue();explorer_support.write_jsonl(root/"manual_review_queue.jsonl",queue)
            api=ExplorerAPI(root,root);item=queue[0]["review_item_id"]
            status,value=api.dispatch("/api/annotation/"+item,method="POST",body={"final_label":"VALID","seed_relevance":"2"});self.assertEqual(status,200);self.assertEqual(value["final_label"],"VALID")
            self.assertEqual(api.dispatch("/api/annotation/"+item)[1]["seed_relevance"],"2")
            filtered=api.dispatch("/api/review-items",{"review_status":["reviewed"],"final_label":["VALID"]})[1];self.assertEqual(filtered["total"],1)
            with self.assertRaisesRegex(ValueError,"final_label"):api.dispatch("/api/annotation/"+queue[1]["review_item_id"],method="POST",body={"final_label":"BAD"})
            csv_export=api.dispatch("/api/review-export.csv")[1]["_raw"];self.assertIn("final_label",csv_export);self.assertIn("VALID",csv_export)
            triple=api.dispatch("/api/triple/t1")[1];self.assertEqual(triple["evidence_links"][0]["review_status"],"reviewed");self.assertEqual(triple["evidence_links"][0]["annotation"]["final_label"],"VALID")

    def test_missing_review_root_useful_error_and_ui_controls_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);explorer_support.KnowledgeExplorerTests().fixture(root);api=ExplorerAPI(root,root/"missing")
            status,error=api.dispatch("/api/annotation/anything",method="POST",body={"final_label":"VALID"});self.assertIn(status,{404,503});self.assertIn("error",error)
            app=(Path("src/code_engine/system_b/explorer/static/app.js")).read_text()
            for text in ("Interactive Manual Review","Correctly Rejected","Valid Weak","saveAnnotation","Manual review labels assess extraction and triage quality") :self.assertIn(text,app)

if __name__=="__main__":unittest.main()
