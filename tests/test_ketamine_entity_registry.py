import unittest

from code_engine.normalization.registry import LocalBiomedicalRegistry, PILOT_REGISTRY_PATH
from code_engine.normalization.resolver import ResolverCascade


class KetamineRegistryTests(unittest.TestCase):
    def test_compounds_remain_distinct(self):
        resolver=ResolverCascade(LocalBiomedicalRegistry(PILOT_REGISTRY_PATH))
        ids={name:resolver.resolve_entity(name).canonical_id for name in ("ketamine","esketamine","arketamine","norketamine","hydroxynorketamine")}
        self.assertEqual(len(set(ids.values())),5)
        self.assertTrue(all(ids.values()))


if __name__ == "__main__": unittest.main()
