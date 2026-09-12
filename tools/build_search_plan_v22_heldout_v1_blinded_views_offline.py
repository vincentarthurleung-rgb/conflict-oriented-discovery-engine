"""Add immutable, independently rendered PASS A/B views without adjudication."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'runs/20260910_search_plan_v22_heldout_v1_neutral_review_freeze_offline'
PROTOCOL = ROOT / 'runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline'
RETRIEVAL = ROOT / 'runs/20260909_search_plan_v22_heldout_v1_network_retrieval'
RUN = ROOT / 'runs/20260910_search_plan_v22_heldout_v1_blinded_adjudication_views_offline'
SCHEMA = ROOT / 'runs/20260906_retrieval_relevance_audit_packaging_v1_offline/retrieval_relevance_adjudication_v1.schema.json'
PROTOCOL_HASH = '2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127'
CORPUS_HASH = 'f2cfe4f1657667a66b18d3123e82d76cc4bf1af9da2863ac6b10f9efc3d092fb'
A_FIELDS = ['acquisition_decision', 'rationale', 'confidence', 'reviewer_type']
B_FIELDS = ['relevance_state', 'matched_target_components', 'mismatched_target_components',
            'fulltext_resolved_fields', 'remaining_unresolved_fields', 'contaminant_class',
            'rationale', 'confidence', 'reviewer_type']
ZERO = dict.fromkeys(['network_calls', 'provider_calls', 'llm_calls', 'downloads', 'extraction_calls'], 0)
UNCHANGED = dict.fromkeys(['query_modifications', 'target_modifications', 'gate_modifications',
                           'budget_modifications', 'case_replacements', 'papers_added', 'papers_removed'], 0)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def readj(path):
    return json.loads(path.read_bytes())


def readl(path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def root_check(base, key, expected):
    manifest = readj(base / 'freeze_manifest.json')
    components = []
    for row in manifest['components']:
        actual = sha(base / row['path'])
        require(actual == row['sha256'], f'Frozen component mismatch: {base / row["path"]}')
        components.append({'path': row['path'], 'sha256': actual})
    actual = digest(canonical([(r['path'], r['sha256']) for r in components]))
    require(actual == manifest[key] == expected, f'Frozen root mismatch: {key}')
    return {'root': str(base.relative_to(ROOT)), key: actual, 'match': True, 'components': components}


def protected_state():
    paths = [p for base in (SOURCE, PROTOCOL, RETRIEVAL) for p in base.rglob('*') if p.is_file()]
    paths += [SCHEMA, ROOT / 'tools/search_plan_v22_candidate_gates.py',
              ROOT / 'tools/freeze_search_plan_v22_heldout_v1_neutral_review_offline.py',
              ROOT / 'tools/generate_search_plan_v2_multicase_stress_test_offline.py']
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def projection(packet, phase):
    """Explicit allowlist: never pass the canonical packet to a renderer."""
    pub = packet['publication_identity']
    names = ['title', 'pmid', 'doi', 'publication_types'] if phase == 'a' else ['title', 'pmid', 'pmcid', 'doi']
    view = {key: packet[key] for key in ['packet_id', 'case_id', 'ambiguity', 'scientific_target', 'abstract']}
    view['publication_identity'] = {key: pub[key] for key in names if key in pub}
    if phase == 'a':
        view['retrieval_target'] = packet['retrieval_target']
    else:
        view.update({key: packet[key] for key in ['deterministic_fulltext_excerpts', 'fulltext_ref',
                                                'fulltext_sha256', 'fields_expected_to_resolve']})
    return view


def render_packet(view, fields):
    # One packet at a time; no global string replacement by case or publication.
    lines = [f"### Packet {view['packet_id']}", '', f"Case: {view['case_id']}",
             f"Ambiguity: {view['ambiguity']}", '', 'ScientificPropositionTargetV1:',
             '```json', json.dumps(view['scientific_target'], ensure_ascii=False, indent=2), '```']
    if 'retrieval_target' in view:
        lines += ['', 'RetrievalTargetV2 (retrieval intent):', '```json',
                  json.dumps(view['retrieval_target'], ensure_ascii=False, indent=2), '```']
    lines += ['', 'Publication:', '```json', json.dumps(view['publication_identity'], ensure_ascii=False, indent=2),
              '```', '', 'Abstract:', view['abstract'] if view['abstract'] is not None else '[not available]']
    if 'deterministic_fulltext_excerpts' in view:
        lines += ['', 'Frozen fulltext provenance:', view['fulltext_ref'],
                  f"SHA-256: {view['fulltext_sha256']}", '', 'Frozen fulltext excerpts:',
                  '```json', json.dumps(view['deterministic_fulltext_excerpts'], ensure_ascii=False, indent=2),
                  '```', '', 'Fields fulltext was expected to resolve:',
                  json.dumps(view['fields_expected_to_resolve'], ensure_ascii=False)]
    lines += ['', 'ADJUDICATION'] + [f'{field}:' for field in fields]
    return '\n'.join(lines) + '\n'


def sections(markdown):
    parts = re.split(r'^### Packet (\S+)\n', markdown, flags=re.M)
    return list(zip(parts[1::2], parts[2::2]))


def anomaly_audit(packets, batches):
    upstream = {(r['case_id'], r['pmid']): r for r in readl(RETRIEVAL / 'metadata_inventory.jsonl')}
    by_id = {p['packet_id']: p for p in packets}
    anomalies = []
    for number, ids in enumerate(batches, 1):
        original = dict(sections((SOURCE / f'heldout_review_batch_{number:02d}.md').read_text()))
        for pid in ids:
            p = by_id[pid]
            depths = re.findall(r'^Metadata depth: (.*)$', original[pid], re.M)
            if depths != [str(p['metadata_depth'])]:
                peers = [by_id[x] for x in ids if by_id[x]['case_id'] == p['case_id']]
                anomalies.append({'packet_id': pid,
                    'anomaly_type': 'duplicate_depth_rendering' if len(depths) > 1 else 'missing_depth_rendering',
                    'classification': 'other deterministic presentation issue: global case-line replacement',
                    'source_field_paths': [f'frozen_neutral_review_packets.jsonl#{x["packet_id"]}/metadata_depth' for x in peers],
                    'source_values': {x['packet_id']: x['metadata_depth'] for x in peers},
                    'rendered_values': depths, 'canonical_source_affected': False,
                    'scientific_sample_identity_affected': False,
                    'cause': 'render_batch replaces the first identical Case line once per packet; second depth is inserted in the first packet, leaving the second packet without depth',
                    'recommended_future_renderer_fix': 'Render each packet independently from its own allowlisted fields; blinded views omit depth.'})
            q = p['query_family_variant_provenance']
            keys = [(r['query_family_id'], r['query_variant_id']) for r in q]
            if len(keys) != len(set(keys)):
                u = upstream[p['case_id'], p['publication_identity']['pmid']]['query_provenance']
                rendered = re.findall(r'^Query family / variant: (.*)$', original[pid], re.M)
                anomalies.append({'packet_id': pid, 'anomaly_type': 'repeated_query_family_variant',
                    'source_field_paths': [f'frozen_neutral_review_packets.jsonl#{pid}/query_family_variant_provenance',
                        f'metadata_inventory.jsonl#{p["case_id"]}/{p["publication_identity"]["pmid"]}/query_provenance'],
                    'source_values': {'canonical': q, 'upstream': u},
                    'rendered_values': [json.loads(x) for x in rendered],
                    'canonical_source_affected': True, 'scientific_sample_identity_affected': False,
                    'upstream_provenance_affected': q == u,
                    'duplicate_full_provenance_records': len(q) - len({canonical(x) for x in q}),
                    'cause': 'Repeated family/variant observations with distinct query_rank values already occur upstream; renderer projects away rank.',
                    'recommended_future_renderer_fix': 'Omit query provenance in blinded views; future audit views can distinguish observations by rank without rewriting frozen provenance.'})
    counts = Counter(a['anomaly_type'] for a in anomalies)
    return {'anomalies': anomalies, 'anomaly_counts': dict(counts),
            'scientific_sample_identity_affected': False, 'historical_artifacts_repaired': False,
            'canonical_provenance_duplicates_preserved': True}


def generate():
    roots = [root_check(PROTOCOL, 'heldout_v1_protocol_sha256', PROTOCOL_HASH),
             root_check(SOURCE, 'heldout_v1_review_corpus_sha256', CORPUS_HASH)]
    before = protected_state()
    packets = readl(SOURCE / 'frozen_neutral_review_packets.jsonl')
    assignment = readl(SOURCE / 'review_batch_assignment.jsonl')
    ids = [p['packet_id'] for p in packets]
    by_id = {p['packet_id']: p for p in packets}
    identity = [(p['case_id'], p['publication_identity']['pmid'], p['publication_identity']['pmcid']) for p in packets]
    require(len(ids) == len(set(ids)) == len(set(identity)) == 70, 'Canonical identity/count mismatch')
    require(Counter(r['packet_id'] for r in assignment) == Counter(ids), 'Frozen assignment mismatch')
    batches = []
    for n in range(1, 6):
        group = sorted([r for r in assignment if r['batch_id'] == f'batch_{n:02d}'], key=lambda r: r['within_batch_order'])
        batch = [r['packet_id'] for r in group]
        old = [pid for pid, _ in sections((SOURCE / f'heldout_review_batch_{n:02d}.md').read_text())]
        require(len(batch) == 14 and batch == old, 'Frozen Markdown/assignment mismatch')
        batches.append(batch)
    require(Counter(x for batch in batches for x in batch) == Counter(ids), 'Batch membership mismatch')
    schema = readj(SCHEMA)
    require(sha(SCHEMA) == readj(SOURCE / 'schema_compatibility.json')['schema_sha256'], 'Frozen schema mismatch')
    enums = {}
    for rule in schema['allOf']:
        for key, spec in rule['then']['properties'].items():
            enums[key] = spec['enum']
    outputs = {}
    def put(name, value):
        outputs[name] = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode()
    def putl(name, rows):
        outputs[name] = b''.join(canonical(row) + b'\n' for row in rows)
    hashes = {'heldout_v1_protocol_sha256': PROTOCOL_HASH, 'heldout_v1_review_corpus_sha256': CORPUS_HASH}
    put('root_hash_verification.json', {'roots': roots, **hashes, 'protocol_hash_match': True,
        'review_corpus_hash_match': True, 'canonical_packet_count': 70, 'batch_count': 5,
        'batch_size': 14, 'packet_membership_unchanged': True, 'batch_assignment_unchanged': True})
    policy = {'presentation_only': True, 'taxonomies': enums, 'schema_ref': str(SCHEMA.relative_to(ROOT)),
        'schema_sha256': sha(SCHEMA), 'pass_a_fields': A_FIELDS, 'pass_b_fields': B_FIELDS,
        'pass_a_allowed_source_fields': list(projection(packets[0], 'a')),
        'pass_b_allowed_source_fields': list(projection(packets[0], 'b')),
        'pass_a_publication_fields': ['title', 'pmid', 'doi', 'publication_types'],
        'pass_b_publication_fields': ['title', 'pmid', 'pmcid', 'doi'],
        'expected_reviewer_type': 'model_retrieval_adjudicator', 'reviewer_type_prefilled': False,
        'fresh_evaluator_sessions_required': True, 'current_conversation_eligible_as_strictly_blinded_evaluator': False,
        'human_validation_is_separate': True, 'scientific_equivalence_authority': 'ScientificPropositionTargetV1',
        'execution_order': ['PHASE_A: review all 70 acquisition packets without fulltext',
            'freeze complete acquisition adjudication corpus',
            'PHASE_B: review all 70 relevance packets without PASS A judgments',
            'freeze complete relevance adjudication corpus', 'deterministic merge by packet_id',
            'only then open preregistered held-out evaluation'],
        'partial_metrics_allowed': False,
        'phase_a_scientific_label_only': 'acquisition_decision',
        'phase_a_supporting_fields': ['rationale', 'confidence', 'reviewer_type'],
        'phase_b_may_access_phase_a_artifacts': False,
        'evaluator_delivery': 'Only the current phase batch files; internal manifests and audits are not evaluator inputs.',
        'later_import_must_verify': list(hashes) + ['heldout_v1_blinded_adjudication_views_sha256']}
    put('blinded_field_policy.json', policy)
    neutral_checks = []
    exposure_checks = []
    for phase, fields, label, kind in [('a', A_FIELDS, 'acquisition_decision', 'acquisition'),
                                      ('b', B_FIELDS, 'relevance_state', 'relevance')]:
        views = {pid: projection(by_id[pid], phase) for pid in ids}
        manifest_rows = [{'packet_id': pid, 'case_id': by_id[pid]['case_id'],
            'canonical_source_ref': str((SOURCE / 'frozen_neutral_review_packets.jsonl').relative_to(ROOT)),
            'canonical_source_record_sha256': digest(canonical(by_id[pid])),
            'source_order': ids.index(pid) + 1, 'visible_fields': views[pid]} for pid in ids]
        putl(f'pass_{phase}_packet_manifest.jsonl', manifest_rows)
        blanks = [{'packet_id': pid, **{f: None for f in fields}} for pid in ids]
        putl(f'blank_{kind}_adjudications_all.jsonl', blanks)
        verification = []
        for n, batch in enumerate(batches, 1):
            intro = [f'# Held-out PASS {phase.upper()} — {kind} review', '',
                'Use a fresh evaluator session for this phase. Expected reviewer type: model_retrieval_adjudicator.',
                'All adjudication fields are blank. Complete all 70 judgments in this phase before freezing its corpus.',
                'Do not calculate partial or running metrics.', '',
                'Allowed ' + label + ': ' + ', '.join(enums[label]), '']
            md = '\n'.join(intro) + '\n' + '\n'.join(render_packet(views[pid], fields) for pid in batch)
            outputs[f'heldout_{kind}_blind_batch_{n:02d}.md'] = md.encode()
            rendered_ids = [pid for pid, _ in sections(md)]
            require(rendered_ids == batch, 'Derivative packet order mismatch')
            for _, body in sections(md):
                form = body.rsplit('\nADJUDICATION\n', 1)[1]
                neutral_checks.append(form.strip().splitlines() == [f'{f}:' for f in fields])
            verification.append({'batch_id': f'batch_{n:02d}', 'packet_count': len(batch),
                                 'frozen_packet_ids': batch, 'rendered_packet_ids': rendered_ids, 'match': True})
        put(f'pass_{phase}_batch_assignment_verification.json', {'batches': verification,
            'packet_identity_bijection': True, 'batch_assignment_identity_preserved': True})
        prohibited = {'tier', 'pre_acquisition_gate_states', 'metadata_depth', 'query_family_variant_provenance',
                      'adjudication', 'automatic_relevance_prediction', 'acquisition_quality_prediction', 'confidence_prediction'}
        if phase == 'a':
            prohibited |= {'deterministic_fulltext_excerpts', 'fulltext_ref', 'fulltext_sha256', 'fields_expected_to_resolve'}
        else:
            prohibited |= {'retrieval_target', 'acquisition_decision'}
        unexpected = {pid: sorted(prohibited.intersection(view)) for pid, view in views.items() if prohibited.intersection(view)}
        exposure_checks.append(not unexpected)
        put(f'pass_{phase}_field_exposure_audit.json', {'packet_count': 70,
            'audit_method': 'allowlisted source projections plus dedicated packet renderer; source-paper language is not a system verdict',
            'unexpected_source_fields': unexpected, 'tier_exposed': False, 'gate_states_exposed': False,
            'why_acquired_exposed': False, 'metadata_depth_exposed': False, 'query_rank_exposed': False,
            'known_plausible_fields_exposed': False, 'fulltext_exposed': phase == 'b',
            'relevance_label_exposed': False, 'acquisition_decision_exposed': phase == 'a',
            'populated_acquisition_decision_exposed': False, 'pass_a_judgments_exposed': False,
            'scientific_target_exposed': True, 'pmcid_exposed': phase == 'b',
            'aggregate_metrics_exposed': False, 'rendered_from_projection_only': True})
    put('renderer_provenance_anomaly_audit.json', anomaly_audit(packets, batches))
    require(all(neutral_checks) and all(exposure_checks), 'Blinding or blank-field audit failed')
    put('neutrality_audit.json', {'prefilled_scientific_labels': 0, 'all_forms_blank': all(neutral_checks),
        'reviewer_type_prefilled': False, 'labels_created': False, 'heldout_metrics_calculated': False})
    put('protocol_leakage_audit.json', {**UNCHANGED, 'heldout_metrics_calculated': False,
        'heldout_primary_adjudication_started': False, 'heldout_primary_results_frozen': False,
        'evaluation_opened': False, 'rules_tuned': False})
    require(before == protected_state(), 'Historical files changed')
    put('scientific_state_safety_audit.json', {**ZERO, 'offline_only': True,
        'historical_assets_modified': False, 'canonical_source_modified': False,
        'existing_review_batches_modified': False, 'git_mutation_invoked': False,
        'protected_hashes_before': before, 'protected_hashes_after': before})
    # All derived payloads and policies are bound; exclude only aggregate/validation bookkeeping.
    components = [{'path': name, 'sha256': digest(data)} for name, data in sorted(outputs.items())]
    blinded_hash = digest(canonical([(c['path'], c['sha256']) for c in components]))
    hashes['heldout_v1_blinded_adjudication_views_sha256'] = blinded_hash
    put('freeze_manifest.json', {**hashes, 'components': components,
        'aggregate_algorithm': 'sha256(canonical JSON ordered [path, sha256] pairs)',
        'derivative_presentation_layer_only': True, 'does_not_replace_frozen_roots': True,
        'later_import_must_verify_all_three_hashes': True})
    summary = {'status': 'completed', **hashes, **ZERO, **UNCHANGED,
        'canonical_packet_count': 70, 'pass_a_packet_count': 70, 'pass_b_packet_count': 70,
        'pass_a_batch_count': 5, 'pass_b_batch_count': 5, 'batch_size': 14,
        'packet_identity_bijection': True, 'batch_assignment_identity_preserved': True,
        'canonical_source_modified': False, 'existing_review_batches_modified': False,
        'tier_exposed_pass_a': False, 'tier_exposed_pass_b': False,
        'fulltext_exposed_pass_a': False, 'fulltext_exposed_pass_b': True,
        'gate_states_exposed_pass_a': False, 'gate_states_exposed_pass_b': False,
        'acquisition_decision_exposed_pass_b': False, 'prefilled_scientific_labels': 0,
        'blank_acquisition_adjudication_count': 70, 'blank_relevance_adjudication_count': 70,
        'heldout_metrics_calculated': False, 'historical_assets_modified': False,
        'heldout_primary_adjudication_started': False, 'heldout_primary_results_frozen': False}
    put('summary.json', summary)
    put('validation.json', {**summary, 'status': 'PASS', 'checks': {
        'frozen_roots_verified': True, 'canonical_identity_unique': len(set(identity)) == 70,
        'source_batch_order_matches_assignment': True, 'derivative_batch_order_matches_source': True,
        'all_adjudication_forms_blank': all(neutral_checks), 'allowlist_exposure_valid': all(exposure_checks),
        'historical_state_unchanged': before == protected_state(),
        'frozen_taxonomies_reused': True, 'no_adjudication_or_evaluation': True}})
    put('manifest.json', {'required_artifact_count': len(outputs) + 1,
        'required_artifacts': sorted([*outputs, 'manifest.json']), **hashes,
        'files': [{'path': name, 'sha256': digest(data), 'bytes': len(data)} for name, data in sorted(outputs.items())]})
    return outputs


def main():
    outputs = generate()
    # A replay verifies the existing derivative freeze; it never rewrites it.
    if RUN.exists():
        require({p.name for p in RUN.iterdir()} == set(outputs), 'Existing output membership differs; stop')
        require(all((RUN / name).read_bytes() == data for name, data in outputs.items()),
                'Existing derivative freeze differs; stop without overwriting')
    else:
        RUN.mkdir()
        for name, data in outputs.items():
            with (RUN / name).open('xb') as handle:
                handle.write(data)
    print(outputs['summary.json'].decode())


if __name__ == '__main__':
    main()
