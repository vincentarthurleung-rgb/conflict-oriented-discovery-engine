"""Import supplied PASS A labels verbatim; verify and freeze without evaluation."""
from collections import Counter
import json
from pathlib import Path

try:
    from tools.build_search_plan_v22_heldout_v1_blinded_views_offline import (
        ROOT, SOURCE, PROTOCOL, RETRIEVAL, RUN as BLINDED, PROTOCOL_HASH,
        CORPUS_HASH, root_check, canonical, digest, sha, readj, readl, require)
except ModuleNotFoundError:
    from build_search_plan_v22_heldout_v1_blinded_views_offline import (
        ROOT, SOURCE, PROTOCOL, RETRIEVAL, RUN as BLINDED, PROTOCOL_HASH,
        CORPUS_HASH, root_check, canonical, digest, sha, readj, readl, require)

INPUT = Path('/home/vincent/.codex/attachments/b5f718d3-7359-4aa1-a11d-23049143c860/pasted-text.txt')
RUN = ROOT / 'runs/20260910_search_plan_v22_heldout_v1_pass_a_acquisition_adjudication_freeze_offline'
BLINDED_HASH = '2940e058b63df5dc02fb6ed07d970f651a74f9a000c9b6784affe3e6fac1dc0e'
FIELDS = ['packet_id', 'acquisition_decision', 'rationale', 'confidence', 'reviewer_type']
DECISIONS = ['JUSTIFIED', 'BORDERLINE_BUT_JUSTIFIED', 'NOT_JUSTIFIED',
             'UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE']
CONFIDENCE = ['high', 'moderate-high', 'moderate', 'moderate-low', 'low']
REVIEWER = 'model_retrieval_adjudicator'
ZERO = dict.fromkeys(['network_calls', 'provider_calls', 'llm_calls', 'downloads',
                     'scientific_extraction_calls', 'new_adjudication_calls'], 0)
UNCHANGED = dict.fromkeys(['case_modifications', 'target_modifications', 'query_modifications',
    'gate_modifications', 'budget_modifications', 'sample_modifications', 'batch_assignment_modifications'], 0)


def parse_submission(raw):
    """Parse exact `field: value` records. Remove only the syntactic delimiter."""
    lines = raw.decode('utf-8').splitlines()
    records, row = [], {}
    for number, line in enumerate(lines, 1):
        if line == '' and not row:
            continue
        field = FIELDS[len(row)]
        prefix = field + ': '
        require(line.startswith(prefix), f'Malformed or unexpected field at line {number}; no repair')
        row[field] = line[len(prefix):]
        if len(row) == len(FIELDS):
            records.append(row)
            row = {}
    require(not row, 'Incomplete submitted record')
    return records


def validate_records(records, expected_ids):
    observed = [r.get('packet_id') for r in records]
    require(len(expected_ids) == len(set(expected_ids)) == 70, 'Invalid expected packet set')
    require(len(records) == 70, 'Expected exactly 70 submitted records')
    require(Counter(observed) == Counter(expected_ids), 'Missing, extra or duplicate packet IDs')
    for row in records:
        require(set(row) == set(FIELDS), 'Unexpected or missing record fields')
        require(all(isinstance(row[f], str) for f in FIELDS), 'All submitted values must be strings')
        require(row['acquisition_decision'] in DECISIONS, 'Invalid acquisition_decision')
        require(row['confidence'] in CONFIDENCE, 'Invalid confidence')
        require(row['reviewer_type'] == REVIEWER, 'Invalid reviewer_type')
        require(bool(row['rationale'].strip()), 'Missing rationale; no inference')
    lookup = {r['packet_id']: r for r in records}
    return [lookup[pid] for pid in expected_ids]


def protected():
    paths = [p for base in (SOURCE, PROTOCOL, BLINDED, RETRIEVAL) for p in base.rglob('*') if p.is_file()]
    paths += [ROOT / 'tools/search_plan_v22_candidate_gates.py',
              ROOT / 'tools/generate_search_plan_v2_multicase_stress_test_offline.py', INPUT]
    return {str(p): sha(p) for p in sorted(paths)}


def generate():
    roots = [root_check(PROTOCOL, 'heldout_v1_protocol_sha256', PROTOCOL_HASH),
             root_check(SOURCE, 'heldout_v1_review_corpus_sha256', CORPUS_HASH),
             root_check(BLINDED, 'heldout_v1_blinded_adjudication_views_sha256', BLINDED_HASH)]
    before = protected()
    expected = [r['packet_id'] for r in readl(SOURCE / 'frozen_neutral_review_packets.jsonl')]
    manifest_ids = [r['packet_id'] for r in readl(BLINDED / 'pass_a_packet_manifest.jsonl')]
    require(expected == manifest_ids, 'PASS A identity manifest differs from canonical corpus order')
    policy = readj(BLINDED / 'blinded_field_policy.json')
    require(policy['taxonomies']['acquisition_decision'] == DECISIONS, 'Frozen decision taxonomy mismatch')
    raw = INPUT.read_bytes()
    submitted = parse_submission(raw)
    ordered = validate_records(submitted, expected)
    assignment = readj(BLINDED / 'pass_a_batch_assignment_verification.json')['batches']
    batch_ids = [pid for batch in assignment for pid in batch['frozen_packet_ids']]
    require([r['packet_id'] for r in submitted] == batch_ids, 'Submitted five-batch order mismatch')
    require(len(assignment) == 5 and all(len(b['frozen_packet_ids']) == 14 for b in assignment), 'Batch size mismatch')
    corpus = b''.join(canonical(row) + b'\n' for row in ordered)
    # Round-trip equality checks every exact value; only corpus order changes.
    roundtrip = [json.loads(line) for line in corpus.splitlines()]
    require(roundtrip == ordered, 'Serialization changed submitted values')
    label_hash = digest(corpus)
    hashes = {'heldout_v1_protocol_sha256': PROTOCOL_HASH,
        'heldout_v1_review_corpus_sha256': CORPUS_HASH,
        'heldout_v1_blinded_adjudication_views_sha256': BLINDED_HASH,
        'heldout_v1_pass_a_acquisition_adjudications_sha256': label_hash}
    outputs = {'pass_a_acquisition_adjudications.jsonl': corpus, 'submitted_pass_a_outputs.txt': raw}
    def put(name, obj):
        outputs[name] = (json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()
    identity = {'expected_packet_count': 70, 'observed_adjudication_count': len(ordered),
        'unique_packet_ids': len(set(r['packet_id'] for r in ordered)), 'missing_packet_ids': 0,
        'extra_packet_ids': 0, 'duplicate_packet_ids': 0, 'packet_identity_bijection': True,
        'merge_key': 'packet_id', 'canonical_order_preserved': [r['packet_id'] for r in ordered] == expected}
    put('pass_a_packet_identity_validation.json', identity)
    put('pass_a_schema_validation.json', {'schema_valid': True, 'decision_taxonomy_valid': True,
        'confidence_valid': True, 'allowed_acquisition_decisions': DECISIONS,
        'allowed_confidence_values': CONFIDENCE, 'required_fields': FIELDS,
        'schema_authority': 'User PASS A freeze/import contract; confidence strings preserved without numeric conversion',
        'record_count': 70, 'rationale_verbatim': True, 'scientific_wording_normalized': False})
    put('pass_a_reviewer_validation.json', {'reviewer_type_valid': True, 'record_count': 70,
        'required_reviewer_type': REVIEWER, 'reviewer_type_modified': False,
        'evaluator_completion_authority': 'user-supplied completed blinded evaluator output',
        'fresh_session_blinding_independently_verified': False})
    put('root_hash_verification.json', {'roots': roots, 'all_three_roots_verified': True})
    source_lookup = {r['packet_id']: i for i, r in enumerate(submitted, 1)}
    put('adjudication_import_manifest.json', {'source_path': str(INPUT), 'source_sha256': digest(raw),
        'preserved_raw_source': 'submitted_pass_a_outputs.txt', 'submitted_record_count': 70,
        'input_batch_order_verified': True, 'canonical_order_authority': str(SOURCE / 'frozen_neutral_review_packets.jsonl'),
        'verbatim_fields': FIELDS, 'normalization_performed': False, 'adjudications_modified': False,
        'records': [{'packet_id': r['packet_id'], 'source_record_order': source_lookup[r['packet_id']],
                     'canonical_record_order': i, 'record_sha256': digest(canonical(r))}
                    for i, r in enumerate(ordered, 1)]})
    after = protected()
    require(before == after, 'Protected historical assets changed')
    safety = {**ZERO, **UNCHANGED, 'offline_only': True, 'canonical_source_modified': False,
        'existing_review_batches_modified': False, 'blinded_views_modified': False,
        'historical_assets_modified': False, 'adjudications_modified': False,
        'git_mutation_invoked': False, 'protected_hashes_before': before, 'protected_hashes_after': after}
    put('scientific_state_safety_audit.json', safety)
    put('freeze_manifest.json', {**hashes, 'hash_algorithm': 'sha256(exact canonical ordered UTF-8 JSONL bytes)',
        'canonical_serialization': 'sort_keys=true; ensure_ascii=false; compact separators; LF after each record',
        'corpus': 'pass_a_acquisition_adjudications.jsonl', 'record_count': 70,
        'ordering': 'frozen review-corpus packet order', 'append_only': True,
        'pass_a_corpus_frozen': True, 'future_pass_b_import_must_verify_four_hashes': True,
        'future_import_required_hashes': list(hashes), 'pass_b_merge_performed': False,
        'future_order': ['fresh blinded PASS B evaluator session', '70/70 PASS B completion',
                         'PASS B freeze', 'deterministic packet_id merge', 'primary results freeze',
                         'open preregistered metrics']})
    summary = {**hashes, **identity, **ZERO, **UNCHANGED, 'status': 'completed', 'schema_valid': True,
        'reviewer_type_valid': True, 'adjudications_modified': False, 'heldout_metrics_calculated': False,
        'decision_distribution_reported': False, 'canonical_source_modified': False,
        'existing_review_batches_modified': False, 'blinded_views_modified': False,
        'historical_assets_modified': False, 'pass_a_corpus_frozen': True,
        'pass_b_merge_performed': False, 'primary_results_frozen': False}
    put('summary.json', summary)
    checks = {'three_roots_match': True, 'identity_bijection': True, 'schema_valid': True,
        'reviewer_type_valid': True, 'batch_submission_order_matches': True,
        'canonical_order_matches': True, 'all_five_fields_verbatim': roundtrip == ordered,
        'raw_submission_byte_preserved': outputs['submitted_pass_a_outputs.txt'] == raw,
        'corpus_hash_matches': digest(corpus) == label_hash, 'historical_assets_unchanged': before == after,
        'offline_no_new_adjudication': True, 'no_metrics_or_decision_grouping': True}
    put('validation.json', {'status': 'PASS', 'checks': checks,
        'artifact_hashes': {name: digest(data) for name, data in sorted(outputs.items())}})
    return outputs


def main():
    outputs = generate()
    if RUN.exists():
        require({p.name for p in RUN.iterdir()} == set(outputs), 'Existing freeze membership differs; no overwrite')
        require(all((RUN / name).read_bytes() == data for name, data in outputs.items()),
                'Existing PASS A freeze differs; no overwrite')
    else:
        RUN.mkdir()
        for name, data in outputs.items():
            with (RUN / name).open('xb') as f:
                f.write(data)
    print(outputs['summary.json'].decode())


if __name__ == '__main__':
    main()
