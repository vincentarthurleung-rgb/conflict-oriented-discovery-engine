"""Test that orchestrator run_workflow does not raise NameError for entity_network_lookup."""
import inspect
import unittest

from code_engine.workflow.orchestrator import run_workflow


class OrchestratorEntityNetworkLookupTests(unittest.TestCase):
    """Verify entity_network_lookup and entity_llm_proposer are valid parameters."""

    def test_entity_network_lookup_param_accepted(self):
        """run_workflow accepts entity_network_lookup without NameError."""
        sig = inspect.signature(run_workflow)
        params = list(sig.parameters.keys())
        self.assertIn("entity_network_lookup", params,
                      "entity_network_lookup must be a parameter of run_workflow")
        self.assertIn("entity_llm_proposer", params,
                      "entity_llm_proposer must be a parameter of run_workflow")

    def test_entity_network_lookup_defaults_to_false(self):
        """entity_network_lookup defaults to False when not specified."""
        sig = inspect.signature(run_workflow)
        default = sig.parameters["entity_network_lookup"].default
        self.assertFalse(default, "entity_network_lookup should default to False")

    def test_entity_llm_proposer_defaults_to_false(self):
        """entity_llm_proposer defaults to False when not specified."""
        sig = inspect.signature(run_workflow)
        default = sig.parameters["entity_llm_proposer"].default
        self.assertFalse(default, "entity_llm_proposer should default to False")

    def test_all_callers_pass_valid_params(self):
        """Verify callers that pass entity_network_lookup are compatible with the signature."""
        sig = inspect.signature(run_workflow)
        param = sig.parameters["entity_network_lookup"]
        self.assertFalse(param.default,
                         f"entity_network_lookup should default to False, got {param.default}")

        param = sig.parameters["entity_llm_proposer"]
        self.assertFalse(param.default,
                         f"entity_llm_proposer should default to False, got {param.default}")


if __name__ == "__main__":
    unittest.main()
