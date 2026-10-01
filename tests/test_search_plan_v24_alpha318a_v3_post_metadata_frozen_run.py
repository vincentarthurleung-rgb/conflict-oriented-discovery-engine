"""Read-only verification of the frozen V3 network run and its zero-source outcome."""

import json
from collections import Counter

from scripts import search_plan_v24_alpha318a_v3_post_metadata_ncbi_continuation as v3


def _rows(name):
    return [json.loads(line) for line in (v3.OUT / name).read_text().splitlines()]


def test_root_and_authoritative_preflight_still_match():
    v3.preflight()
    files = sorted(path for path in v3.OUT.rglob('*')
                   if path.is_file() and path.name != v3.ROOT_MARKER)
    root = v3.sha(v3.base.canonical([[str(path.relative_to(v3.OUT)), v3.digest(path)]
                                    for path in files]))
    assert root == (v3.OUT / v3.ROOT_MARKER).read_text().strip()


def test_exact_ncbi_scope_and_no_invalid_v2_reuse():
    attempts = _rows('ncbi_transport_attempts_v3.jsonl')
    assert len(attempts) == 80
    assert Counter(x['stage'] for x in attempts) == {
        'PMC_OA_SUBSET_V3': 42, 'PMC_JATS_V3': 38}
    assert all(x['endpoint'] in {v3.base.ES, v3.base.EF} for x in attempts)
    assert all(x['raw_path'].startswith(('oa_verification_raw_responses/',
                                         'pmc_jats_raw_responses_v3/')) for x in attempts)
    assert all(v3.digest(v3.OUT / x['raw_path']) == x['raw_sha256'] for x in attempts)
    safety = json.loads((v3.OUT / 'scientific_state_safety_audit.json').read_text())
    assert all(safety[x] == 0 for x in ('builder_calls', 'quality_calls',
                                        'deepseek_calls', 'openai_calls', 'llm_calls',
                                        'non_ncbi_network_calls'))


def test_oa_outcome_is_exact_frozen_license_rule_not_parser_loss():
    oa = _rows('construction_oa_eligibility_results_v3.jsonl')
    jats = _rows('pmc_jats_acquisition_results_v3.jsonl')
    assert len(oa) == 42 and len(jats) == 38
    assert all(x['success'] for x in jats)
    for record in oa:
        canonical = ((v3.OUT / record['canonical_jats_path']).read_bytes()
                     if record['canonical_jats_path'] else None)
        expected = v3.policy.construction_oa_state(
            record['pmcid'], record['subset_result'], canonical)
        assert record['decision'] == expected
    assert Counter(x['state'] for x in oa) == {
        'CONSTRUCTION_OA_UNRESOLVED': 38,
        'CONSTRUCTION_OA_INELIGIBLE': 4}
    assert all(x['decision']['reason'] == 'LICENSE_CONFLICT_OR_INCOMPLETE'
               for x in oa if x['subset_result'] is True)


def test_zero_budget_derived_from_frozen_empty_manifests():
    assert _rows('construction_source_manifest_v3.jsonl') == []
    assert _rows('proposition_builder_v2_request_manifest_v3.jsonl') == []
    budget = json.loads((v3.OUT / 'actual_builder_call_budget_v3.json').read_text())
    assert budget['actual_builder_scientific_call_count'] == 0
    assert budget['derived_from_complete_construction_source_manifest'] is True
    barrier = json.loads((v3.OUT / 'source_phase_completion_barrier_v3.json').read_text())
    assert barrier['all_42_sources_terminal'] is True
