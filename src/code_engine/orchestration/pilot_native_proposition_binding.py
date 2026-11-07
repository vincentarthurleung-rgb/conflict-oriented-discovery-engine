"""Source-aware correspondence sidecars; never rewrite scientific records.

The caller supplies explicit, source-bound Work field assessments. This is not
an entity resolver or an automatic clinical classifier. Exact representation
proof and provisional semantic correspondence are separate verification axes.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
from typing import Literal
from pydantic import Field
from code_engine.discovery.ai_review_shadow import ShadowAuthority, content_hash, file_hash, load_bound_packet
from code_engine.orchestration.pilot_inclusion import read_pin
from code_engine.orchestration.pilot_native_representation import recover_native_jsonl, COORDINATES
from code_engine.fulltext.projection_interpretation import consumer_guard
from code_engine.extraction_assets.experimental_core.source_resolution_models import SourceResolutionEnvelope

VERSION = 'source_aware_native_proposition_binding_v1'
POLICY = Path(__file__).resolve().parents[3] / 'docs/contracts/source_aware_native_proposition_binding_v1.md'
AUTH = {**ShadowAuthority().model_dump(mode='json'), 'machine_reuse_authorized': False,
        'independent_scientific_validation': False, 'formal_L4_compatible': False,
        'canonical_identity_approved': False, 'comparator_orientation_validated': False}
FIELDS = ('endpoint', 'subgroup', 'scope_kind', 'study_design', 'measurement',
          'reported_result', 'reported_statistic', 'result_group', 'reference_group', 'time')
REQUIRED = ('endpoint', 'subgroup', 'scope_kind', 'study_design', 'measurement', 'reported_result')
# Both are local source-analysis descriptors, never canonical/ontology identities.


class FieldAssessment(ShadowAuthority):
    value: str | None
    record_pointer: str
    record_value: str | None
    evidence_refs: list[str]
    limitation: str = Field(min_length=8)


class Profile(ShadowAuthority):
    key: str
    record_sha256: str
    revision_identity: str
    inclusion_revision_identity: str
    effective_interpretation_identity: str
    fields: dict[str, FieldAssessment]
    producer: str = Field(min_length=12)


class Configuration(ShadowAuthority):
    schema_version: Literal['source_aware_native_proposition_binding_v1']
    policy: dict
    owner_instruction: dict
    sources: list[dict]
    native_profiles: list[Profile]
    proposition_profiles: list[Profile]
    producer: str = Field(min_length=12)


def input_identity(request):
    from code_engine.orchestration.pilot_comparison import input_identity as transitive
    return transitive({'scientific_comparison_assessments': request.get('native_proposition_binding')})


def _pointer(value, pointer):
    if not pointer.startswith('/'):
        raise ValueError('binding_record_pointer_required')
    for token in pointer[1:].split('/'):
        value = value[token.replace('~1', '/').replace('~0', '~')]
    return value


def _one(items, predicate, reason):
    rows = [r for r in items if predicate(r)]
    if len(rows) != 1:
        raise ValueError(reason)
    return rows[0]


def _verify_spans(spans, article, coordinate):
    for s in spans:
        if s.get('coordinate_system', s.get('coordinate_unit')) != coordinate:
            raise ValueError('binding_wrong_coordinate_representation')
        i = s['section_index']; text = article['sections'][i]['text']
        if (s['source_json_pointer'] != '/sections/' + str(i) + '/text'
                or not 0 <= s['char_start'] < s['char_end'] <= len(text)
                or text[s['char_start']:s['char_end']] != s['text']
                or hashlib.sha256(s['text'].encode()).hexdigest() != s['text_hash']
                or hashlib.sha256(text.encode()).hexdigest() != s['source_section_text_sha256']):
            raise ValueError('binding_source_coordinate_or_hash_mismatch')


def _profile(p, record, spans):
    if content_hash(record) != p.record_sha256 or set(p.fields) != set(FIELDS):
        raise ValueError('binding_profile_record_or_field_inventory_mismatch')
    refs = {s['evidence_span_id'] for s in spans}
    for f in p.fields.values():
        if _pointer(record, f.record_pointer) != f.record_value:
            raise ValueError('binding_field_record_pointer_mismatch')
        if not set(f.evidence_refs) <= refs or (f.value is not None and not f.evidence_refs):
            raise ValueError('binding_missing_source_evidence')
    for key in ('subgroup',):
        f = p.fields[key]
        if f.value is not None and not any(f.value in s['text'] for s in spans if s['evidence_span_id'] in f.evidence_refs):
            raise ValueError('binding_scope_or_group_not_source_attested')
    if p.fields['endpoint'].value != p.fields['endpoint'].record_value:
        raise ValueError('binding_endpoint_relabeling_not_permitted')
    for key in ('result_group', 'reference_group'):
        f = p.fields[key]
        if f.value is not None and (f.record_value is None or f.value not in f.record_value):
            raise ValueError('binding_inconsistent_result_reference_orientation')
    return p.model_dump(mode='json')


def _stable_proposition(p):
    # Frozen B4 scientific fields; dynamic upstream derivation identity is kept
    # separately, never edited to make a historical revision equal a current one.
    keys = ('key', 'scope_identity', 'experiment_identity', 'native_observation_id',
            'facets', 'factor_role', 'result', 'cohort_dependency', 'missing_information',
            'source_packet_pin', 'retained_native_pins', 'publication', 'source_content_sha256')
    return {k: p[k] for k in keys}


def _inclusion(rows, scope, revision):
    r = _one(rows, lambda x: x['scope_level'] == 'observation' and x['scope_identity'] == scope,
             'binding_inclusion_missing_or_ambiguous')
    if r['revision_identity'] != 'scientific_inclusion_revision:' + content_hash({k: v for k, v in r.items() if k != 'revision_identity'}):
        raise ValueError('binding_invalid_B3_revision_content')
    if revision is not None and r['revision_identity'] != revision:
        raise ValueError('binding_stale_B3_inclusion_revision')
    return r


def _semantic_match(n, p, nspans, pspans):
    checks = {}
    for key in FIELDS:
        a, b = n['fields'][key], p['fields'][key]
        checks[key] = 'UNKNOWN' if a['value'] is None or b['value'] is None else (
            'MATCH' if a['value'] == b['value'] else 'NONMATCH')
    # Same words or shared paragraph cannot establish the same analysis. The
    # selected native RESULT sentence must be contained in proposition RESULT
    # evidence at exactly the same projected coordinates, after lineage replay.
    nr = set(n['fields']['reported_result']['evidence_refs'])
    pr = set(p['fields']['reported_result']['evidence_refs'])
    common = [{'native_span_id': a['evidence_span_id'], 'proposition_span_id': b['evidence_span_id'],
               'section_index': a['section_index'], 'char_start': a['char_start'], 'char_end': a['char_end'],
               'text': a['text'], 'text_hash': a['text_hash']}
              for a in nspans for b in pspans if a['evidence_span_id'] in nr and b['evidence_span_id'] in pr
              and a['section_index'] == b['section_index']
              and b['char_start'] <= a['char_start'] < a['char_end'] <= b['char_end']]
    checks['same_result_source_coordinates'] = 'MATCH' if common else 'NOT_ESTABLISHED'
    mismatch = [k for k, v in checks.items() if v == 'NONMATCH']
    unknown = [k for k in REQUIRED if checks[k] == 'UNKNOWN']
    decision = ('NONMATCH' if mismatch else 'UNRESOLVED' if unknown or not common
                else 'SOURCE_BOUND_PROVISIONAL_MATCH')
    return decision, checks, common


def bind_native_propositions(request, ledger, records, propositions, *, dependencies):
    """Explicit opt-in sidecar. Source or revision failures stop this adapter.

    No binding -> no scientific exclusion, inclusion inheritance or legacy
    null-authority path. A missing configuration retains both existing paths.
    """
    pin = request.get('native_proposition_binding')
    base = {**AUTH, 'schema_version': VERSION, 'configuration_pin': pin,
            'current_dependency_identity': dependencies,
            'input_identity': input_identity(request), 'policy_sha256': file_hash(POLICY),
            'implementation_sha256': file_hash(Path(__file__)), 'rows': [],
            'native_inventory': [], 'proposition_inventory': [],
            'formal_L4c': 'staging_only', 'scientific_identity_gate_changed': False}
    if pin is None:
        return {**base, 'status': 'NOT_EVALUATED', 'reason': 'No explicit source correspondence assessment selected; both paths remain independent'}
    cfg = Configuration.model_validate(read_pin(pin))
    if cfg.policy['sha256'] != file_hash(POLICY):
        raise ValueError('binding_policy_not_current')
    read_pin(cfg.policy) if Path(cfg.policy['path']).suffix == '.json' else _check_pin(cfg.policy)
    _check_pin(cfg.owner_instruction)
    if len({s['publication']['pmcid'] for s in cfg.sources}) != len(cfg.sources):
        raise ValueError('binding_duplicate_publication_source')
    native = {}; props = {}; source_info = {}
    for source in cfg.sources:
        frozen_projections = read_pin(source['B4_8_projected_observations'])
        frozen_props = read_pin(source['B4_propositions'])['propositions']
        frozen_ledger = read_pin(source['B3_inclusion_ledger'])['rows']
        old_audit = read_pin(source['B4_7_native_lineage'])
        recovered = recover_native_jsonl(source['native_replay_manifest'])
        if recovered['audit']['batch_rejection_reason'] or recovered['audit']['counts']['rejected_or_unresolved']:
            raise ValueError('binding_native_source_lineage_not_verified')
        lineage = recovered['audit']; rep = lineage['source_representations']
        if rep != old_audit['source_representations']:
            raise ValueError('binding_frozen_source_representation_identity_mismatch')
        article = read_pin(rep['paragraph_projection'])
        from code_engine.orchestration.pilot_native_representation import NativeReplayManifest, _lineage, _spans
        from code_engine.fulltext.evidence_anchors import resolve_anchor
        from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import _span_from_anchor
        manifest = NativeReplayManifest.model_validate(read_pin(source['native_replay_manifest']))
        _, m, text, anchors, fragments, _, _, _ = _lineage(manifest)
        extras = [_span_from_anchor(resolve_anchor(a, anchors, expected_block_id=m['block']['block_id'], source_text=text, expected_source_document_id=article['pmcid']), 'setup').model_dump(mode='json') for a in source.get('additional_anchor_ids', [])]
        if source['publication'] != json.loads(Path(source['native_replay_manifest']['path']).read_text())['source_identity']:
            raise ValueError('binding_publication_mismatch')
        source_info[source['publication']['pmcid']] = {'publication': source['publication'],
            'source_representations': rep, 'transformation_provenance': lineage['transformation_provenance'],
            'fragments': lineage['fragments'], 'lineage_status': 'VERIFIED_SOURCE_LINEAGE',
            'semantic_correspondence_not_implied_by_projection': True}
        for rr in recovered['records']:
            envelope = json.loads(rr['core_utf8']); f = envelope['ExperimentalObservationV3']; oid = f['observation_id']
            current = _one(records, lambda r: json.loads(r['core'].read_text())['ExperimentalObservationV3']['observation_id'] == oid,
                           'binding_current_native_missing_or_ambiguous')
            if json.loads(current['core'].read_text()) != envelope:
                raise ValueError('binding_wrong_observation_or_Core_revision')
            old = _one(old_audit['records'], lambda r: r.get('original_V3_identity') == oid, 'binding_frozen_native_missing')
            if old['derived_revision_identity'] != envelope['ExperimentalCore']['revision']['identity']:
                raise ValueError('binding_frozen_Core_revision_mismatch')
            projection = _one(frozen_projections, lambda r: r['observation_id'] == oid, 'binding_frozen_interpretation_missing')
            if not consumer_guard(projection, 'review')['allowed_by_effective_layer']:
                raise ValueError('binding_stale_B4_8_interpretation')
            if projection['formal_v3_native_payload'] != f or projection['ExperimentalCore'] != envelope['ExperimentalCore']:
                raise ValueError('binding_B4_8_native_revision_mismatch')
            view = current.get('projection_row')
            if not view or not consumer_guard(view, 'review')['allowed_by_effective_layer']:
                raise ValueError('binding_current_interpretation_not_reverified')
            for key in ('study_design', 'reported_association_direction', 'statistical_significance',
                        'endpoint_as_reported', 'cohort_as_reported', 'null_or_absence_of_detection'):
                if view['effective_interpretation'][key] != projection['effective_interpretation'][key]:
                    raise ValueError('binding_current_effective_semantics_drift')
            if oid in native: raise ValueError('binding_duplicate_native')
            extra_formal = {**f, 'provenance': {**f['provenance'], 'evidence_spans': extras}}
            mapped = rr['native_source_lineage']['evidence_mapping'] + _spans(extra_formal, manifest, article, m, text, anchors, fragments)
            native[oid] = {'record': envelope, 'mapped': mapped,
                'frozen_effective': projection['effective_interpretation'], 'current_effective': view['effective_interpretation'],
                'frozen_ledger': frozen_ledger, 'article': article, 'source': source['publication']['pmcid'],
                'source_envelopes': current.get('linkage_prepared', {}).get('source_resolution_envelopes', []),
                'semantic_grounding': current.get('semantic_grounding'),
                'cohort_dependency': rr['native_source_lineage']['cohort_dependency']}
        for p in frozen_props:
            if p['publication'] != source['publication']: continue
            current = _one(propositions, lambda r: r['key'] == p['key'], 'binding_current_proposition_missing_or_ambiguous')
            if _stable_proposition(current) != _stable_proposition(p):
                raise ValueError('binding_B4_proposition_scientific_revision_mismatch')
            packet = load_bound_packet(Path(p['source_packet_pin']['path']), Path(p['source_packet_pin']['path']))
            src = packet.packet['source']
            if (src['original_xml_sha256'] != rep['original_xml']['sha256']
                    or src['article_sha256'] != rep['paragraph_projection']['sha256']
                    or p['source_content_sha256'] != rep['paragraph_projection']['sha256']):
                raise ValueError('binding_proposition_representation_mismatch')
            if p['key'] in props: raise ValueError('binding_duplicate_proposition')
            props[p['key']] = {'record': p, 'current': current, 'mapped': p['source_evidence'],
                'frozen_ledger': frozen_ledger, 'article': article, 'source': source['publication']['pmcid']}
    # Every supplied authentic record in a selected publication must be assessed;
    # missing profiles cannot silently remove a difficult native/proposition row.
    if Counter(p.key for p in cfg.native_profiles) != Counter({k: 1 for k in native}):
        raise ValueError('binding_native_profile_inventory_missing_or_duplicate')
    if Counter(p.key for p in cfg.proposition_profiles) != Counter({k: 1 for k in props}):
        raise ValueError('binding_proposition_profile_inventory_missing_or_duplicate')
    for profiles, items, is_native in ((cfg.native_profiles, native, True), (cfg.proposition_profiles, props, False)):
        for profile in profiles:
            item = items[profile.key]; r = item['record']
            _verify_spans(item['mapped'], item['article'], COORDINATES if is_native else 'Unicode code point; declared source-text representation')
            item['profile'] = _profile(profile, r, item['mapped'])
            e = item['frozen_effective'] if is_native else r['effective_interpretation']
            assoc = e['reported_association_direction']
            nonsignificant = e['statistical_significance']['assessment'] == 'source_reported_nonsignificant' if is_native else e['statistical_null_as_recorded']
            result_value = assoc + '_association' if assoc in ('positive', 'negative') else 'no_significant_association_reported' if nonsignificant else None
            if profile.fields['reported_result'].value != result_value:
                raise ValueError('binding_reported_result_conflicts_with_effective_interpretation')
            design = e['study_design']['provisional_assessment'] if is_native else e['study_design']
            if profile.fields['study_design'].value != design:
                raise ValueError('binding_design_conflicts_with_effective_interpretation')
            revision = r['ExperimentalCore']['revision']['identity'] if is_native else r['proposition_identity']
            effective = item['frozen_effective']['identity'] if is_native else 'source_proposition_interpretation:' + content_hash(r['effective_interpretation'])
            scope = profile.key if is_native else r['scope_identity']
            if revision != profile.revision_identity:
                raise ValueError('binding_wrong_observation_or_Core_revision')
            if profile.effective_interpretation_identity != effective:
                raise ValueError('binding_stale_B4_8_interpretation')
            old = _inclusion(item['frozen_ledger'], scope, profile.inclusion_revision_identity)
            now = _inclusion(ledger['rows'], scope, None)
            excluded = {'source_artifact', 'revision_identity'}
            if ({k:v for k,v in old.items() if k not in excluded} != {k:v for k,v in now.items() if k not in excluded}
                    or file_hash(Path(old['source_artifact'])) != old['source_content_sha256']
                    or file_hash(Path(now['source_artifact'])) != now['source_content_sha256']):
                raise ValueError('binding_current_B3_decision_changed')
            item['frozen_inclusion'] = old
            item['inclusion'] = now
            for e in item.get('source_envelopes', []):
                env = SourceResolutionEnvelope.model_validate(e)
                f = r['ExperimentalObservationV3']
                if (env.observation_identity != f['observation_id'] or env.experiment_scope_identity != f['experiment']['experiment_id']
                        or env.source_document_identity != f['provenance']['source_document_id']):
                    raise ValueError('binding_source_resolution_envelope_scope_mismatch')
    rows = []
    for oid, n in native.items():
        for key, p in props.items():
            if n['source'] != p['source']: continue
            decision, checks, common = _semantic_match(n['profile'], p['profile'], n['mapped'], p['mapped'])
            row = {**AUTH, 'observation_id': oid, 'Core_revision': n['record']['ExperimentalCore']['revision']['identity'],
                'native_experiment_identity': n['record']['ExperimentalObservationV3']['experiment']['experiment_id'],
                'native_formal_sha256': content_hash(n['record']['ExperimentalObservationV3']),
                'native_Core_sha256': content_hash(n['record']['ExperimentalCore']),
                'native_cohort_dependency': n['cohort_dependency'], 'B4_cohort_dependency': p['record']['cohort_dependency'],
                'proposition_key': key, 'frozen_proposition_revision': p['record']['proposition_identity'],
                'frozen_proposition_sha256': content_hash(p['record']),
                'current_proposition_revision': p['current']['proposition_identity'],
                'source_lineage': source_info[n['source']], 'source_integrity': 'VERIFIED_SEPARATELY',
                'decision': decision, 'field_checks': checks, 'same_result_evidence': common,
                'native_fields': n['profile'], 'proposition_fields': p['profile'],
                'native_evidence_coordinates': n['mapped'], 'proposition_evidence_coordinates': p['mapped'],
                'B3_native_decision': n['inclusion'], 'B3_proposition_decision': p['inclusion'],
                'frozen_B3_native_decision': n['frozen_inclusion'], 'frozen_B3_proposition_decision': p['frozen_inclusion'],
                'B3_revision_derivation': 'Original and current revisions distinct; exact decision/evidence unchanged, byte-identical source copied to new run path',
                'B3_decision_inherited': False,
                'frozen_B4_8_interpretation_revision': n['frozen_effective']['identity'],
                'current_effective_interpretation_revision': n['current_effective']['identity'],
                'source_resolution_envelopes': n['source_envelopes'],
                'existing_B4_6_grounding_and_verification': n['semantic_grounding'],
                'binding_does_not_issue_grounding_receipt_or_expand_verifier_scope': True,
                'source_support_limitations': ['Provisional Work correspondence, not independent scientific review',
                    'No formal comparator orientation, measurement equivalence or biological identity approval',
                    'Unestablished timing, quantitative effects and subgroup sample sizes remain unresolved'],
                'producer': cfg.producer, 'assessment_authority': 'source_bound_Work_provisional_only',
                'current_dependency_identity': dependencies}
            rows.append(row)
    resolve_ambiguity(rows)
    for r in rows:
        r['binding_revision'] = VERSION + ':' + content_hash(r)
    def inventory(items, field):
        return [{field: k, 'candidate_Core_retained' if field == 'observation_id' else 'source_proposition_retained': True,
                 'B3_original_decision': v['inclusion'], 'matched_binding_revisions': [r['binding_revision'] for r in rows
                    if r[field] == k and r['decision'] == 'SOURCE_BOUND_PROVISIONAL_MATCH'],
                 'unmatched_is_not_scientific_exclusion': True} for k, v in items.items()]
    base.update(status='SOURCE_BOUND_PROVISIONAL', rows=rows,
        native_inventory=inventory(native, 'observation_id'), proposition_inventory=inventory(props, 'proposition_key'),
        counts=dict(Counter(r['decision'] for r in rows)),
        assessment_producer=cfg.producer, all_paths_retained_independently=True)
    base['revision_identity'] = VERSION + ':' + content_hash(base)
    return base


def _check_pin(pin):
    if file_hash(Path(pin['path'])) != pin['sha256']:
        raise ValueError('binding_pin_hash_drift')


def resolve_ambiguity(rows):
    """Do not choose an arbitrary winner among source-supported candidates."""
    matches = [r for r in rows if r['decision'] == 'SOURCE_BOUND_PROVISIONAL_MATCH']
    nc = Counter(r['observation_id'] for r in matches); pc = Counter(r['proposition_key'] for r in matches)
    for r in rows:
        if r['decision'] == 'SOURCE_BOUND_PROVISIONAL_MATCH' and (nc[r['observation_id']] > 1 or pc[r['proposition_key']] > 1):
            r['decision'] = 'AMBIGUOUS'; r['ambiguity_reason'] = 'Multiple source-supported correspondences; no arbitrary tie break'
    return rows
