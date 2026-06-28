import unittest

from code_engine.extraction.polarity import normalize_directional_relation


class PharmacologicalPolarityTests(unittest.TestCase):
    def assert_direction(self, text, direction, polarity, **kwargs):
        result = normalize_directional_relation(text, **kwargs)
        self.assertEqual(result.direction, direction)
        self.assertEqual(result.polarity_type, polarity)
        return result

    def test_english_direction_families(self):
        for term in ("inhibits", "suppresses", "blocks", "attenuates", "is an antagonist of"):
            self.assert_direction(term, "inhibit", "mechanistic", object_type="protein")
        for term in ("activates", "promotes", "enhances", "stimulates", "is an agonist of"):
            self.assert_direction(term, "activate", "mechanistic", object_type="protein")
        self.assert_direction("upregulates gene expression", "increase", "expression")
        self.assert_direction("downregulates gene expression", "decrease", "expression")
        self.assert_direction("improves depression-like behavior", "improve", "phenotypic")
        self.assert_direction("worsens adverse events", "worsen", "safety")
        self.assertEqual(normalize_directional_relation("no significant effect on expression").direction, "no_effect")

    def test_chinese_and_nontherapeutic_inhibition(self):
        cases = (("抑制受体", "inhibit"), ("激活受体", "activate"), ("上调基因表达", "increase"),
                 ("下调基因表达", "decrease"), ("改善抑郁行为", "improve"), ("恶化不良反应", "worsen"),
                 ("无显著影响", "no_effect"))
        for text, direction in cases:
            self.assertEqual(normalize_directional_relation(text, object_type="protein").direction, direction)
        inhibition = normalize_directional_relation("drug inhibits target", subject_type="compound", object_type="protein")
        self.assertEqual(inhibition.polarity_type, "mechanistic")
        self.assertIn("mechanistic_inhibition_has_no_therapeutic_valence", inhibition.warnings)


if __name__ == "__main__": unittest.main()
