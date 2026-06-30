import unittest
from pathlib import Path


class DefaultConfigNeutralityTests(unittest.TestCase):
    def test_default_configs_do_not_contain_pilot_terms(self):
        root = Path(__file__).parents[1]
        paths = (
            root / "configs/domain_routing_fallback.json",
            root / "configs/domains/domain_spec.json",
            root / "configs/normalization/entity_registry.json",
            root / "configs/normalization/l2_l3_ontology_rules.json",
            root / "configs/prompts/l1/base_extraction_rules.txt",
            root / "configs/prompts/l1/l1_5_refiner_rules.json",
            root / "configs/validators/curated_omics_registry.json",
        )
        forbidden = ("ketamine", "esketamine", "bdnf", "mtor")
        for path in paths:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8").casefold()
                self.assertFalse(any(term in text for term in forbidden))


if __name__ == "__main__": unittest.main()
