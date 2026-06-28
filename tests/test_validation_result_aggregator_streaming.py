import tempfile
import unittest
from pathlib import Path

from code_engine.schemas.validation import ValidationAnchor, ValidationQueryPlan, ValidationResourcePolicy, ValidationSignal
from code_engine.validation.result_aggregator import aggregate_validation_signals


class StreamingValidationAggregatorTests(unittest.TestCase):
    def aggregate(self,signals,plan_status="allowed"):
        anchor=ValidationAnchor(anchor_id="A",anchor_type="hypothesis_anchor",entities=[{"canonical_id":"X"}],linked_hypothesis_ids=["H"],validation_intent="expression_direction_check")
        plan=ValidationQueryPlan(query_plan_id="P",anchor_id="A",validator_name="V",query_type="x",query_entities=anchor.entities,status=plan_status)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"signals.jsonl"; path.write_text("".join(item.model_dump_json()+"\n" for item in signals))
            return aggregate_validation_signals(path,[anchor],[plan],ValidationResourcePolicy())

    def sig(self,i,support=None,contradict=None,kind="expression_support",quality=.9):
        return ValidationSignal(signal_id=str(i),validator_name="V",source_database="db",query_plan_id="P",anchor_id="A",signal_type=kind,supports_hypothesis=support,contradicts_hypothesis=contradict,confidence=quality,quality=quality)

    def test_conservative_statuses(self):
        self.assertEqual(self.aggregate([self.sig(1,True,False),self.sig(2,True,False)]).aggregate_status,"supported")
        self.assertEqual(self.aggregate([self.sig(1,False,True),self.sig(2,False,True)]).aggregate_status,"contradicted")
        self.assertEqual(self.aggregate([self.sig(1,True,False),self.sig(2,False,True)]).aggregate_status,"mixed")
        self.assertEqual(self.aggregate([]).aggregate_status,"no_coverage")
        self.assertEqual(self.aggregate([],"no_index").aggregate_status,"external_index_not_configured")
        self.assertEqual(self.aggregate([self.sig(1,quality=.2)]).aggregate_status,"insufficient_quality")
        self.assertEqual(self.aggregate([self.sig(1,kind="trial_existence_signal")]).aggregate_status,"insufficient_quality")
        self.assertEqual(self.aggregate([self.sig(1,kind="binding_support")]).aggregate_status,"insufficient_quality")


if __name__ == "__main__": unittest.main()
