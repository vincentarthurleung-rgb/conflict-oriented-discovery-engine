"""Read-only integrity and gate checks for the frozen alpha3.18A.6 replay."""

import json
import stat
from collections import Counter

from scripts import search_plan_v24_alpha318a6_replay_license_offline as run


def load_rows(name):
    return [json.loads(line) for line in (run.OUT / name).read_text().splitlines()]


def test_frozen_roots_and_jats_integrity():
    data = run.preflight()
    assert len(data['paths']) == 38
    assert run.v3_root() == run.V3_SHA
    files = sorted(path for path in run.OUT.rglob('*')
                   if path.is_file() and path.name != run.ROOT_MARKER)
    root = run.sha(run.base.canonical([[str(path.relative_to(run.OUT)), run.digest(path)]
                                       for path in files]))
    assert root == (run.OUT / run.ROOT_MARKER).read_text().strip()
    assert not any(path.is_symlink() for path in run.OUT.rglob('*'))


def test_all_38_machine_licenses_replayed_from_frozen_jats():
    data = run.preflight()
    records = load_rows('license_representation_replay_results.jsonl')
    assert len(records) == 38
    for record in records:
        expected = run.license_v2.extract_license_v2(data['paths'][record['pmid']].read_bytes())
        for key, value in expected.items():
            assert record[key] == value
    assert Counter(record['state'] for record in records) == {
        'ELIGIBLE': 30, 'INELIGIBLE': 6, 'UNRESOLVED': 2}


def test_oa_source_and_builder_cardinality():
    oa = load_rows('construction_oa_eligibility_results_v4.jsonl')
    types = load_rows('source_type_mechanical_eligibility_results_v4.jsonl')
    sources = load_rows('construction_source_manifest_v4.jsonl')
    requests = load_rows('proposition_builder_v2_request_manifest_v4.jsonl')
    vault = load_rows('private_anchor_vault_source_manifest_v4.jsonl')
    assert len(oa) == 42
    assert Counter(record['state'] for record in oa) == {
        'CONSTRUCTION_OA_ELIGIBLE': 30,
        'CONSTRUCTION_OA_INELIGIBLE': 10,
        'CONSTRUCTION_OA_UNRESOLVED': 2}
    assert len(types) == 30
    assert len(sources) == len(requests) == len(vault) == 28
    assert {x['source_token'] for x in sources} == {x['source_token'] for x in requests}
    for item in sources:
        assert run.digest(run.OUT / item['document_path']) == item['document_sha256']
    budget = json.loads((run.OUT / 'actual_builder_call_budget_v4.json').read_text())
    assert budget['actual_builder_scientific_call_count_v4'] == 28
    assert stat.S_IMODE((run.OUT / 'private_anchor_vault_source_manifest_v4.jsonl').stat().st_mode) == 0o600


def test_no_network_or_model_call_and_all_sha_markers():
    safety = json.loads((run.OUT / 'scientific_state_safety_audit.json').read_text())
    assert safety['network_calls'] == safety['provider_calls'] == safety['llm_calls'] == 0
    for stem, suffix in (
        ('construction_license_extraction_v2', '.json'),
        ('construction_oa_eligibility_v2', '.json'),
        ('construction_source_manifest_v4', '.jsonl'),
        ('proposition_builder_v2_request_manifest_v4', '.jsonl')):
        assert run.digest(run.OUT / (stem + suffix)) == (
            run.OUT / (stem + '_sha256')).read_text().strip()
