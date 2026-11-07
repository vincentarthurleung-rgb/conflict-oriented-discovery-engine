"""Software-only regression tests. No model calls or scientific judgments."""
import pytest
from code_engine.fulltext.fulltext_l1_v2 import FulltextTokenBudget, token_budget_preflight


def check(text):
    return token_budget_preflight({}, {"block_id": "SOFTWARE_FIXTURE", "text": text}, FulltextTokenBudget())


@pytest.mark.parametrize("prefix", ["LINKED_METHODS: Assay setup.", "PRECEDING_SETUP: Prior setup."])
def test_context_first_never_hides_later_results(prefix):
    a = check(prefix + "\n\nCURRENT_RESULTS: Figure 3A measured one endpoint. Figure 3B measured another.")
    assert a['figure_experiment_hints'] == ['Figure 3A', 'Figure 3B']
    assert 'multiple_figure_or_experiment_units' in a['preflight_reasons']
    assert a['preflight_decision'] == 'split_before_provider_call'
    assert a['block_body_token_estimate'] > 0


def test_multiline_context_retained_without_counting_methods_figures_as_results():
    a = check('LINKED_METHODS: Figure 9 describes setup.\ncontinued setup\n\nCURRENT_RESULTS: Figure 3B reports growth.\ncontinued result\nLINKED_METHODS: Further setup.')
    assert a['figure_experiment_hints'] == ['Figure 3B']
    assert a['linked_methods_token_estimate'] > 0
    assert a['block_body_token_estimate'] > 0
    assert a['preflight_decision'] == 'execute_as_is'


def test_unframed_results_and_later_current_other_are_still_inspected():
    a = check('Figure 3A reports growth.\nLINKED_METHODS: Setup.\nCURRENT_OTHER: Figure 3C reports a different endpoint.')
    assert a['figure_experiment_hints'] == ['Figure 3A', 'Figure 3C']
    assert a['preflight_decision'] == 'split_before_provider_call'
