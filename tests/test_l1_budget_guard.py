import unittest

from code_engine.extraction.l1_budget import build_l1_budget_report, enforce_l1_budget, estimate_l1_cost


class L1BudgetGuardTests(unittest.TestCase):
    def test_cost_and_overrun_policy(self):
        estimate=estimate_l1_cost(input_tokens=1000,call_count=10,model_pricing_profile="test")
        denied=enforce_l1_budget(estimate,{"max_l1_calls_per_prompt":2},execute=True)
        allowed=enforce_l1_budget(estimate,{"max_l1_calls_per_prompt":2},execute=True,allow_budget_overrun=True)
        self.assertGreater(estimate["estimated_cost_usd"],0)
        self.assertTrue(denied["blocked"])
        self.assertFalse(allowed["blocked"])
        self.assertEqual(build_l1_budget_report(estimate,denied)["budget_status"],"blocked")


if __name__ == "__main__": unittest.main()
