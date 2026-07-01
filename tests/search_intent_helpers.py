from pathlib import Path
from code_engine.workflow.steps import run_intake_step

PAYLOAD = {
    "mode": "llm", "confidence": 0.82, "manual_review_required": False,
    "seed_triple": {
        "subject": {"name": "metformin", "aliases": ["metformin"]},
        "relation": {"name": "activates_or_modulates", "family": "activation_or_regulation"},
        "object": {"name": "AMPK", "aliases": ["AMPK", "AMP-activated protein kinase"]},
        "context": {"terms": ["cancer", "cancer cells"]},
    },
    "query_groups": {
        "direct_relation": [{"query": "metformin AND AMPK AND cancer", "allowed_for_l1_acquisition": True}],
        "context_only": [{"query": "AMPK AND cancer", "allowed_for_l1_acquisition": False}],
        "broad_recall": [{"query": "metformin cancer", "allowed_for_l1_acquisition": False}],
    }, "warnings": [],
}

class FakePlanner:
    def __init__(self, value=None, fail=False): self.value = value or PAYLOAD; self.fail = fail
    def extract_json(self, prompt, **_):
        if self.fail: raise RuntimeError("planner failed")
        return self.value

def prepare(run: Path):
    (run / "artifacts").mkdir(parents=True, exist_ok=True)
    result = run_intake_step(query="metformin AMPK cancer", run_dir=run, execute=False, api=False, allow_uncertain_intake=True)
    return result
