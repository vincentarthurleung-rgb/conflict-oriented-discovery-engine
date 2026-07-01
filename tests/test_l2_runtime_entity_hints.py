import tempfile,unittest
from pathlib import Path
from code_engine.normalization.layered_grounding import load_runtime_entity_hints,match_runtime_hint
from tests.l2_layered_helpers import INTENT
import json

class RuntimeHintsTests(unittest.TestCase):
    def test_runtime_alias_and_process_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/"artifacts";a.mkdir();(a/"semantic_search_intent.json").write_text(json.dumps(INTENT))
            hints=load_runtime_entity_hints(tmp); match=match_runtime_hint("AMPK activation",hints)
            self.assertEqual(match["canonical_name"],"AMPK");self.assertEqual(match["mention_role"],"process_about_entity")

if __name__=="__main__":unittest.main()
