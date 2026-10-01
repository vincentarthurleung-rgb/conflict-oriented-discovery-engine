"""No-network preflight checks for the V3 continuation boundary."""

from scripts import search_plan_v24_alpha318a_v3_post_metadata_ncbi_continuation as v3


def test_preflight_verifies_frozen_42_source_boundary():
    manifest, pre_oa, original = v3.preflight()
    assert len(pre_oa) == 42
    assert original['reference_count'] >= 40
    assert manifest['next_stage_network_routes'] == ['pmc_oa_subset', 'pmc_jats']
    assert manifest['no_source_discovery_or_sampled_metadata_requests'] is True


def test_network_endpoints_and_frozen_retry_policy():
    manifest, _, _ = v3.preflight()
    routes = manifest['frozen_downstream_contracts']['network_routes']
    assert routes['pmc_jats']['endpoint'] == v3.base.EF
    assert v3.base.ES.startswith('https://eutils.ncbi.nlm.nih.gov/')
    retry = v3.base.prior.load(v3.base.prior.SOURCE, 'source_execution_policy.json')
    assert retry['maximum_attempts_per_request'] == 4
    assert retry['timeout_seconds'] == 60
    assert retry['backoff_seconds'] == [2, 4, 8]


def test_request_universe_is_unique_without_replacement():
    _, pre_oa, _ = v3.preflight()
    assert len({row['pmid'] for row in pre_oa}) == 42
    assert len({row['pmcid'] for row in pre_oa}) == 42
