"""Read-only integrity checks for the frozen alpha3.18A.5 replay."""

import json

from scripts import search_plan_v24_alpha318a5_replay_primary_identity_offline as replay


def test_frozen_upstream_and_output_roots():
    replay.verify_roots()
    sampled, checkpoint = replay.verify_checkpoint()
    assert len(sampled) == 72
    assert checkpoint['valid_source_frames_reused'] is True
    raw, audit = replay.load_raw_metadata(sampled)
    assert len(raw) == audit['complete_verified_raw_responses'] == 72
    root = replay.BASE.prior.all_file_root(replay.OUT, replay.MARKER)
    assert root == (replay.OUT / replay.MARKER).read_text().strip()


def test_replay_counts_and_pre_oa_order():
    summary = json.loads((replay.OUT / 'summary.json').read_text())
    validation = json.loads((replay.OUT / 'validation.json').read_text())
    sampled, _ = replay.verify_checkpoint()
    identity = replay.rows(replay.OUT / 'sampled_metadata_identity_replay_results.jsonl')
    metadata = replay.rows(replay.OUT / 'sampled_source_metadata_records_v2.jsonl')
    pre_oa = replay.rows(replay.OUT / 'post_metadata_pre_oa_source_manifest_v2.jsonl')
    assert [item['pmid'] for item in identity] == [item['pmid'] for item in sampled]
    assert [item['pmid'] for item in metadata] == [item['pmid'] for item in sampled]
    assert all(item['matched_medlinecitation_pmid'] == item['expected_sampled_pmid']
               for item in identity)
    assert all(len(item['direct_pmcid_values']) == 1 for item in identity)
    assert len(pre_oa) == summary['post_metadata_pre_oa_source_count']
    assert all(item['pmid'] in {entry['pmid'] for entry in metadata} for item in pre_oa)
    assert validation['network_calls'] == validation['provider_calls'] == validation['llm_calls'] == 0


def test_every_marker_matches_file_and_future_refs_exist():
    names = ('pubmed_primary_citation_identity_binding_v1',
             'sampled_source_metadata_records_v2',
             'post_metadata_pre_oa_source_manifest_v2',
             'alpha3_18a5_post_metadata_resume_execution_manifest_v3')
    suffixes = ('.json', '.jsonl', '.jsonl', '.json')
    for name, suffix in zip(names, suffixes):
        assert replay.digest(replay.OUT / (name + suffix)) == (
            replay.OUT / (name + '_sha256')).read_text().strip()
    manifest = json.loads((replay.OUT /
        'alpha3_18a5_post_metadata_resume_execution_manifest_v3.json').read_text())
    for key in ('parent_v2_manifest', 'primary_binding_contract', 'corrected_metadata_v2',
                'post_metadata_pre_oa_selection', 'valid_upstream_checkpoint',
                'raw_metadata_completeness'):
        reference = manifest[key]
        assert replay.digest(replay.ROOT / reference['path']) == reference['sha256']
    assert manifest['material_runtime_policy_unresolved_count'] == 0
