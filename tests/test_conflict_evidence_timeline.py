import unittest

from code_engine.temporal.evidence_timeline import build_conflict_evidence_timelines
from code_engine.temporal.windows import TimelineConfig


def evidence(year, direction, context=None):
    return {"evidence_id": f"e{year}", "paper_id": f"p{year}", "publication_year": year, "direction": direction,
            "subject_canonical_id": "S", "object_canonical_id": "O", "relation_family": "affects", "polarity_type": "effect",
            "evidence_span": f"span {year}", "context_variables": context or {}}


class EvidenceTimelineTests(unittest.TestCase):
    def test_traceable_sorted_timeline(self):
        records = [evidence(y,d) for y,d in [(2013,"decrease"),(2010,"increase"),(2011,"decrease"),(2012,"increase"),(2017,"increase")]]
        timeline = build_conflict_evidence_timelines([{"candidate_id":"c","subject_canonical_id":"S","object_canonical_id":"O","relation_family":"affects","polarity_type":"effect"}], records, config=TimelineConfig())[0]
        self.assertEqual([x["year"] for x in timeline.evidence_timeline], sorted(x["year"] for x in timeline.evidence_timeline))
        self.assertTrue(timeline.human_review_required)
        self.assertEqual(timeline.system_judgment, "non_decisive")
        self.assertNotIn("resolved", timeline.status)


if __name__ == "__main__": unittest.main()
