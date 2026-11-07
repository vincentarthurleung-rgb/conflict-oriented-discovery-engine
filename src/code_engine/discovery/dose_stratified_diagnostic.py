"""Source-local dose-only sign reversal; independent of exact A/B/C/D discovery.

Exact labels and verified component references are preliminary source bindings,
not independent validation, canonical identity, contradiction or causal authority.
"""
from collections import defaultdict
from decimal import Decimal
from itertools import combinations
import re
import unicodedata

from code_engine.discovery.ai_review_shadow import content_hash

VERSION = 'dose_stratified_direction_reversal_v1'
LABEL = 'DOSE_STRATIFIED_DIRECTION_REVERSAL'
AUTH = {'scientific_authorization': False, 'human_gold': False,
        'strict_core_eligible': False, 'qualified_for_l4': False, 'formal_conflict': False}


def _text(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).split())


def _label(value):
    return _text(value).casefold()


def _known(value):
    label = _label(value).replace('_', ' ')
    return bool(label and label not in ('none', 'null') and not re.search(
        r'\b(?:unknown|unclear|unspecified|unreported|missing|not available|not reported|not stated|not specified)\b', label))


def _literal(value, text):
    return bool(value and re.search(r'(?<!\w)' + re.escape(_label(value)) + r'(?!\w)', _label(text)))


def _dose(raw):
    # Preserve range statements as one stratum; no unit conversion or bin filling.
    match = re.fullmatch(r'(\d+(?:\.\d+)?)(?:\s*[–-]\s*(\d+(?:\.\d+)?))?\s*([A-Za-zμµ%]+(?:/[A-Za-z]+)?)', _text(raw))
    if not match:
        return None
    start, end, unit = match.groups();end = end or start
    if Decimal(end) < Decimal(start):
        return None
    return {'raw': raw, 'kind': 'range' if match.group(2) else 'single',
            'lower': start, 'upper': end, 'unit': unit, 'aggregate_statement': bool(match.group(2))}


def _without_dose(value, raw):
    return _label(value).replace(_label(raw), '{dose_context}')


def _prepare(row):
    reasons = []
    verification = row.get('source_verification') or {}
    source_hash = verification.get('source_sha256')
    binding = row.get('source_binding') or {}
    packet_spans = verification.get('verified_packet_evidence') or []
    if not source_hash or binding.get('source_sha256') != source_hash or not verification.get('packet_sha256'):
        reasons.append('VERIFIED_SOURCE_BINDING_REQUIRED')
    verified = {s['evidence_span_id']: s for s in packet_spans}
    spans = {s['evidence_span_id']: s for s in row['source_evidence']}
    interventions = row.get('all_interventions') or []
    if len(interventions) != 1 or interventions[0].get('role') != 'primary':
        return None, reasons + ['SINGLE_UNAMBIGUOUS_PRIMARY_INTERVENTION_REQUIRED; secondary/rescue/inhibitor combinations excluded']
    factor = interventions[0];m = row['measurement'];e = row['experiment_context']
    agent = factor.get('agent_mention') or factor.get('target_mention')
    subject = row.get('source_relation_subject')
    if not (_known(agent) and _known(subject) and _label(subject) == _label(agent)):
        reasons.append('TESTED_RELATION_SUBJECT_NOT_BOUND_TO_PRIMARY_AGENT')
    if re.search(r'\b(?:or|and)\b|[+/]', _label(agent)):
        reasons.append('AMBIGUOUS_OR_COMPOSITE_PRIMARY_AGENT')
    if row['relationship_kind'] != 'observed_contrast':
        reasons.append('SOURCE_LOCAL_TREATMENT_CONTRAST_REQUIRED')
    required = {'operation': factor.get('intervention_type_raw'), 'target': m.get('measured_entity_mention'),
        'endpoint': m.get('endpoint_raw'), 'assay': m.get('assay_or_readout_raw'),
        'system': e.get('model_system_raw'), 'duration': factor.get('duration_raw'),
        'tested': row.get('tested_arm'), 'reference': row.get('reference_arm'),
        'family': e.get('evidence_family_id'), 'design': e.get('experimental_design_raw')}
    if not _known(factor.get('intervention_type')):
        reasons.append('CONTROLLED_INTERVENTION_OPERATION_UNRESOLVED')
    reasons.extend('MISSING_OR_UNKNOWN_' + k.upper() for k, v in required.items() if not _known(v))
    if _label(required['system']) in ('cells','cultured cells','cell lines','animals','mice','patients','cancer cells','tumor cells','in vitro','in vivo'):
        reasons.append('EXPERIMENTAL_SYSTEM_NOT_SPECIFIC')
    if row.get('orientation') != 'source_tested_vs_reference' or _label(required['tested']) == _label(required['reference']):
        reasons.append('SOURCE_TESTED_REFERENCE_ORIENTATION_UNVERIFIED')
    if _known(agent) and not _literal(agent, required['tested']):
        reasons.append('TESTED_ARM_DOES_NOT_IDENTIFY_PRIMARY_AGENT')
    dose = _dose(factor.get('dose_raw'))
    if dose is None:
        reasons.append('EXPLICIT_QUANTITATIVE_DOSE_REQUIRED')
    refs = list(dict.fromkeys(row['result_evidence_refs'] + row['measurement_evidence_refs'] + factor.get('evidence_span_ids', [])))
    if not factor.get('evidence_span_ids') or not refs or any(r not in spans or r not in verified for r in refs):
        reasons.append('VERIFIED_COMPONENT_EVIDENCE_REFERENCES_REQUIRED')
    elif any(any(spans[r].get(k) != verified[r].get(k) for k in ('text', 'text_hash', 'source_document_id')) for r in refs):
        reasons.append('VERIFIED_COMPONENT_EVIDENCE_MISMATCH')
    else:
        evidence = ' '.join(spans[r]['text'] for r in refs)
        # These are exact surface checks over already bound component evidence,
        # not a synonym resolver or a scientific-method approval.
        for k, v in {'agent': agent, 'target': required['target'], 'endpoint': required['endpoint'],
                     'system': required['system'], 'duration': required['duration'],
                     'tested': required['tested'], 'reference': required['reference']}.items():
            if _known(v) and not _literal(v, evidence):
                reasons.append('SOURCE_SURFACE_NOT_ATTESTED_' + k.upper())
        # Descriptive assay strings need not occur as one contiguous phrase, but
        # every content token must occur in the exact measurement-bound source.
        assay_text = ' '.join(spans[r]['text'] for r in row['measurement_evidence_refs'])
        assay_tokens = re.findall(r'[\wμ%]+', _label(required['assay']))
        if not assay_tokens or any(not _literal(t, assay_text) for t in assay_tokens if t not in {'a','an','the','at','as','of','in','to','for','and'}):
            reasons.append('ASSAY_READOUT_SURFACES_NOT_SOURCE_ATTESTED')
        if dose:
            dose_text = ' '.join(spans[r]['text'] for r in factor['evidence_span_ids'])
            if any(not _literal(v, dose_text) for v in (dose['lower'], dose['upper'], dose['unit'])):
                reasons.append('DOSE_VALUES_OR_UNIT_NOT_SOURCE_ATTESTED')
    sign = row['effective_direction'] if row['conflict_screen_eligibility']['eligible'] else None
    if sign not in (-1, 1) or row['source_reported_sign'] != sign:
        reasons.append('ELIGIBLE_EXPLICIT_DIRECTION_REQUIRED')
    if reasons:
        return None, sorted(set(reasons))
    publication = row['publication']
    if not (publication.get('pmcid') and publication.get('pmid')):
        return None, ['SOURCE_PUBLICATION_IDENTITY_UNRESOLVED']
    key = {'source': {'pmcid': publication['pmcid'], 'pmid': str(publication['pmid']), 'sha256': source_hash},
        'source_family': required['family'], 'relationship_kind': row['relationship_kind'],
        'agent': _label(agent), 'tested_subject': _label(subject), 'role': factor['role'],
        'operation': _label(required['operation']), 'intervention_type': factor.get('intervention_type'),
        'target': _label(required['target']), 'endpoint': _label(required['endpoint']),
        'measurement_dimension': m.get('measurement_dimension'), 'measurement_dimension_raw': _label(m.get('measurement_dimension_raw')),
        'assay': _label(required['assay']), 'system': _label(required['system']),
        'duration': _label(required['duration']), 'tested': _label(required['tested']), 'reference': _label(required['reference']),
        'dose_unit': dose['unit'],
        'other_factor_context': {k: _label(factor.get(k)) for k in ('target_mention','method_raw','route_raw','condition_raw')},
        'other_system_context': {k: _label(e.get(k)) for k in ('species_raw','experimental_unit_raw','tissue_raw','disease_model_raw','genotype_raw','cohort_raw','sample_raw')},
        'design_without_declared_dose': _without_dose(required['design'], dose['raw']),
        'scope_without_declared_dose': _without_dose(e.get('experiment_label_raw'), dose['raw'])}
    result_spans = [verified[r] for r in row['result_evidence_refs']]
    result_identity = sorted({content_hash([source_hash, s.get('source_json_pointer') or s.get('section_index', s['block_id']),
        s['char_start'], s['char_end'], s['text_hash']]) for s in result_spans})
    stratum = {'observation_id': row['observation_id'], 'record_identity': row['record_identity'],
        'native_revision_sha256': row['native_revision_sha256'], 'dose': dose,
        'raw_extracted_sign': row['raw_extracted_sign'], 'source_reported_direction': row['source_reported_direction'],
        'effective_direction': row['effective_direction'], 'screening_direction': sign,
        'statistical_significance_status': row['statistical_significance_status'],
        'statistical_scope_uncertainty': row['uncertainty_reasons'],
        'tested_arm': row['tested_arm'], 'reference_arm': row['reference_arm'],
        'original_result_span_identities': result_identity, 'source_result_evidence': result_spans,
        'verified_packet_sha256': verification['packet_sha256'],
        'extraction_warnings': row['extraction_warnings']}
    return (key, stratum), []


def diagnose_dose_stratified_reversal(rows):
    """One family label, never pooled conflict entropy or contradiction probability."""
    groups = {};abstentions = [];duplicates = [];seen = set()
    for row in rows:
        prepared, reasons = _prepare(row)
        if reasons:
            abstentions.append({'observation_id': row['observation_id'], 'record_identity': row['record_identity'], 'reasons': reasons})
            continue
        key, stratum = prepared
        identity = content_hash([key, stratum['dose'], stratum['original_result_span_identities'], stratum['screening_direction']])
        if identity in seen:
            duplicates.append({'observation_id': row['observation_id'], 'reason': 'REPEATED_SOURCE_DOSE_RESULT'})
            continue
        seen.add(identity);gid = content_hash(key)
        groups.setdefault(gid, {'identity': key, 'strata': []})['strata'].append(stratum)
    families = []
    for gid, group in sorted(groups.items()):
        strata = group['strata'];dose_signs = defaultdict(set)
        for s in strata:dose_signs[content_hash(s['dose'])].add(s['screening_direction'])
        if any(len(v) > 1 for v in dose_signs.values()):
            abstentions.append({'context_comparison_identity': gid, 'reasons': ['CONFLICTING_DIRECTIONS_FOR_SAME_DOSE']})
            continue
        comparisons = []
        for a, b in combinations(strata, 2):
            if a['screening_direction'] == b['screening_direction']:continue
            da, db = a['dose'], b['dose']
            if not (Decimal(da['upper']) < Decimal(db['lower']) or Decimal(db['upper']) < Decimal(da['lower'])):
                continue  # Overlapping aggregate ranges cannot create dose bins.
            comparisons.append({'observation_ids': [a['observation_id'], b['observation_id']],
                'doses': [da['raw'], db['raw']], 'source_reported_directions': [a['source_reported_direction'], b['source_reported_direction']],
                'independent_comparison': False})
        if not comparisons:continue
        span_groups = defaultdict(list)
        for s in strata:
            for identity in s['original_result_span_identities']:span_groups[identity].append(s['observation_id'])
        families.append({**AUTH, 'diagnostic': LABEL, 'context_comparison_identity': gid,
            'context_comparison_key': group['identity'], 'varying_context_fields': ['dose_raw'], 'strata': strata,
            'opposing_dose_comparisons': comparisons,
            'dependency': {'publication_count': 1, 'source_document_count': 1,
                'dose_observation_count': len(strata), 'distinct_dose_contexts': len(dose_signs),
                'distinct_original_result_spans': len(span_groups),
                'shared_original_result_spans': [{'source_span_identity': k, 'observation_ids': v} for k,v in span_groups.items() if len(v)>1],
                'independent_publication_replications': 0, 'independent_experimental_replications': None,
                'independent_biological_studies': None, 'independence_status': 'NOT_ESTABLISHED; shared source family, not independent observations'},
            'interpretation': 'source-supported context-dependent direction only; not a scientific contradiction'})
    return {**AUTH, 'schema_version': VERSION, 'diagnostic': LABEL, 'scope': 'source_local_dose_only',
        'families': families, 'reversal_family_count': len(families), 'eligible_source_families': len(groups),
        'abstentions': abstentions, 'duplicates': duplicates,
        'influences_existing_ABCD': False, 'scientific_conflict_entropy_computed': False,
        'contradiction_probability_estimated': False, 'Work_or_AI_review_consumed': False}
