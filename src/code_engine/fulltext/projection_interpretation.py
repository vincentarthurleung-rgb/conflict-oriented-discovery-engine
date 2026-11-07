"""Versioned conservative effective interpretation; raw projections stay raw.

Explicit source-bound provisional annotations, not a clinical classifier or a
P-value threshold. This module issues no scientific or machine authority.
"""
from pathlib import Path
from typing import Literal
import json
from pydantic import Field
from code_engine.discovery.ai_review_shadow import ShadowAuthority,content_hash,file_hash

VERSION='effective_projection_interpretation_v1'
POLICY=Path(__file__).resolve().parents[3]/'docs/contracts/effective_projection_interpretation_v1.md'
AUTH={**ShadowAuthority().model_dump(mode='json'),'machine_reuse_authorized':False,
      'formal_conflict_confirmed':False,'causal_qualification':False}
DERIVED_KEYS={'effective_interpretation','effective_consumer_guards'}


class Annotation(ShadowAuthority):
    observation_id:str
    Core_revision_id:str
    formal_sha256:str
    core_sha256:str
    native_replay_manifest:dict
    study_design:Literal['observational','interventional','unknown']
    factor_semantics:Literal['observational_grouping','assigned_manipulation','exposure','unknown']
    association_direction:Literal['positive','negative','unknown']
    significance:Literal['source_reported_significant','source_reported_nonsignificant','unknown']
    significance_basis:Literal['source_wording','author_methods_and_reported_statistic','unknown']
    null_wording:Literal['reported_absence_of_detection','none_established','unknown']
    equivalence_claim:str|None=None
    evidence_by_dimension:dict[str,list[str]]
    additional_anchor_ids:list[str]=Field(default_factory=list)
    conflicts:list[str]=Field(default_factory=list)
    reason:str=Field(min_length=12)
    producer:str=Field(min_length=12)


def implementation_identity():return {'version':VERSION,'sha256':file_hash(Path(__file__))}


def raw_projection(row):return {k:v for k,v in row.items() if k not in DERIVED_KEYS}


def input_identity(pin):
    from code_engine.orchestration.pilot_comparison import input_identity as transitive
    return transitive({'scientific_comparison_assessments':pin})


def load_configuration(pin):
    if not pin:return None
    from code_engine.orchestration.pilot_inclusion import read_pin
    cfg=read_pin(pin)
    if cfg.get('schema_version')!=VERSION or cfg.get('scientific_authorization') is not False:
        raise ValueError('effective_interpretation_configuration_version_or_authority_invalid')
    from code_engine.orchestration.pilot_semantic_grounding import owner_scope
    owner_scope(cfg['B4_6_owner_decision'])
    for key in ('owner_instruction','policy'):
        p=cfg[key]
        if file_hash(Path(p['path']))!=p['sha256']:raise ValueError('effective_interpretation_policy_or_owner_drift')
    if cfg['policy']['sha256']!=file_hash(POLICY):raise ValueError('effective_interpretation_policy_not_bound')
    rows=cfg.get('annotations',[])
    if not isinstance(rows,list):raise ValueError('effective_annotation_inventory_invalid')
    return cfg


def _validated_annotation(row,cfg):
    formal=row.get('formal_v3_native_payload') or row.get('ExperimentalObservationV3')
    core=row.get('experimental_core') or row.get('ExperimentalCore')
    if not formal or not core:raise ValueError('native_V3_Core_unavailable')
    matches=[a for a in cfg['annotations'] if a.get('observation_id')==formal['observation_id']]
    if len(matches)!=1:raise ValueError('effective_annotation_missing_or_ambiguous')
    a=Annotation.model_validate(matches[0])
    if (a.Core_revision_id!=core['revision']['identity'] or a.formal_sha256!=content_hash(formal)
            or a.core_sha256!=content_hash(core)):
        raise ValueError('effective_annotation_source_Core_or_endpoint_binding_mismatch')
    from code_engine.orchestration.pilot_native_representation import NativeReplayManifest,_lineage
    from code_engine.orchestration.pilot_inclusion import read_pin
    native=NativeReplayManifest.model_validate(read_pin(a.native_replay_manifest))
    article,m,text,anchors,fragments,ctx,hydrated,batch=_lineage(native)
    if hydrated.get(formal['observation_id'])!=formal:raise ValueError('effective_annotation_not_original_source_V3')
    from code_engine.fulltext.evidence_anchors import resolve_anchor
    from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import _span_from_anchor
    spans={s['evidence_span_id']:s for s in formal['provenance']['evidence_spans']}
    for anchor_id in a.additional_anchor_ids:
        anchor=resolve_anchor(anchor_id,anchors,expected_block_id=ctx.block_id,source_text=text,
                              expected_source_document_id=ctx.source_document_id)
        span=_span_from_anchor(anchor,'setup').model_dump(mode='json')
        spans[span['evidence_span_id']]=span
    for dimension in ('study_design','factor_semantics','association_direction','significance','null_wording'):
        refs=a.evidence_by_dimension.get(dimension,[])
        value=getattr(a,dimension)
        if value not in ('unknown','none_established') and (not refs or not set(refs)<=spans.keys()):
            raise ValueError('effective_positive_evidence_missing:'+dimension)
    if a.association_direction!='unknown':
        if (a.association_direction!=formal['candidate_relation']['lexical_direction']
                or not set(a.evidence_by_dimension['association_direction']).intersection(formal['observation']['evidence_span_ids'])):
            raise ValueError('direction_not_established_by_both_source_result_and_original_lexical_extraction')
    if a.significance!='unknown':
        if a.significance_basis=='unknown':raise ValueError('P_value_alone_is_not_significance_authority')
        if a.significance_basis=='author_methods_and_reported_statistic' and not any(
            spans[r]['source_role']=='methods' for r in a.evidence_by_dimension['significance']):
            raise ValueError('author_statistical_methods_evidence_missing')
    if a.study_design=='observational' and a.factor_semantics in ('assigned_manipulation','exposure'):
        raise ValueError('observational_group_cannot_become_assigned_manipulation_or_exposure')
    if a.equivalence_claim:
        refs=a.evidence_by_dimension.get('equivalence_claim',[])
        if not refs or not set(refs)<=spans.keys() or not any(a.equivalence_claim in spans[r]['text'] for r in refs):
            raise ValueError('equivalence_claim_not_bound_to_exact_source; scientific_evaluation_NOT_APPROVED')
    if a.conflicts:raise ValueError('conflicting_source_semantic_assessment')
    return a,formal,core,list(spans.values())


def interpret_projection(row,configuration_pin=None):
    raw=raw_projection(row);formal=raw.get('formal_v3_native_payload') or raw.get('ExperimentalObservationV3') or {}
    core=raw.get('experimental_core') or raw.get('ExperimentalCore') or {}
    result=formal.get('observation',{});experiment=formal.get('experiment',{})
    reasons=[];a=None;spans=formal.get('provenance',{}).get('evidence_spans',[])
    try:
        cfg=load_configuration(configuration_pin)
        if cfg is None:raise ValueError('SOURCE_BOUND_EFFECTIVE_ASSESSMENT_MISSING')
        a,formal,core,spans=_validated_annotation(raw,cfg)
    except (ValueError,KeyError,TypeError,IndexError,OSError) as error:reasons.append(str(error))
    observational=bool(a and a.study_design=='observational' and a.factor_semantics=='observational_grouping')
    effective={**AUTH,'schema_version':VERSION,
        'status':'SOURCE_BOUND_PROVISIONAL' if a else 'ABSTAIN',
        'binding':{'raw_projection_sha256':content_hash(raw),'observation_id':formal.get('observation_id') or raw.get('observation_id'),
            'experiment_id':experiment.get('experiment_id'),'Core_revision_id':core.get('revision',{}).get('identity'),
            'formal_sha256':content_hash(formal),'core_sha256':content_hash(core),
            'source_identity':formal.get('provenance'), 'configuration_pin':configuration_pin,
            'actual_interpretation_inputs_sha256':input_identity(configuration_pin)},
        'implementation':implementation_identity(),'policy_sha256':file_hash(POLICY),
        'legacy_fields':{k:raw.get(k) for k in ('scientific_edge_layer','observed_outcome_sign','formal_relation','derived_causal_sign')},
        'legacy_fields_authoritative_for_causality_equality_contradiction_or_reuse':False,
        'study_design':{'source_raw':experiment.get('experimental_design_raw'),'normalized_as_recorded':experiment.get('design_type'),
                        'provisional_assessment':a.study_design if a else 'unknown','evidence_refs':a.evidence_by_dimension['study_design'] if a else []},
        'factor_semantics':{'raw_interventions':formal.get('interventions',[]),'raw_tested_group':experiment.get('comparison_arm_raw'),
            'raw_reference_group':experiment.get('control_arm_raw'),'effective':a.factor_semantics if a else 'unknown',
            'assigned_intervention_established':False,'interventions_array_is_not_manipulation_authority':True},
        'effective_layer':'association' if observational else 'source_outcome_reviewable_unknown',
        'endpoint_as_reported':formal.get('measurement',{}).get('endpoint_raw'),
        'cohort_as_reported':experiment.get('cohort_raw'),
        'reported_association_direction':a.association_direction if a else 'unknown',
        'statistical_significance':{'assessment':a.significance if a else 'unknown','basis':a.significance_basis if a else 'unknown',
            'raw_support':result.get('statistical_support_raw'),'engine_P_threshold_applied':False,
            'evidence_refs':a.evidence_by_dimension['significance'] if a else []},
        'effect_magnitude':None,'uncertainty_as_reported':result.get('uncertainty_raw'),
        'quantitative_field_as_recorded':result.get('quantitative_result_raw'),'P_value_is_not_effect_magnitude':True,
        'null_or_absence_of_detection':{'assessment':a.null_wording if a else 'unknown','raw_outcome_language':result.get('observed_result')},
        'effective_outcome_sign':None,'zero_effect_asserted':False,
        'equivalence':{'established':False,'noninferiority_established':False,'source_claim':a.equivalence_claim if a else None,
            'decision_proposal':'NOT_APPROVED: separate source-bound equivalence/noninferiority evaluation contract required' if a and a.equivalence_claim else None},
        'causal_direction':{'sign':None,'authority':'NOT_GRANTED','causal_increases':False},
        'formal_admission':{'eligible':False,'machine_reuse_authorized':False,'hypothesis_authority':False},
        'source_evidence':spans,'source_annotation':a.model_dump(mode='json') if a else None,
        'correction_reasons':['interventions_array_does_not_establish_manipulation','legacy_zero_does_not_establish_zero_effect',
            'lexical_association_does_not_establish_causal_regulation'],
        'unknown_reasons':['effect_magnitude_HR_CI_not_established','causal_direction_and_scientific_authority_not_established'],
        'abstention_reasons':reasons,'independent_scientific_validation':False}
    effective['identity']=VERSION+':'+content_hash(effective)
    return effective


def requires_effective(row):
    return bool(row.get('formal_v3_native_payload') or row.get('ExperimentalObservationV3')
                or row.get('scientific_edge_layer') in ('intervention_observation','association')
                or row.get('observed_outcome_sign')==0
                or row.get('intervention_type')=='unknown' or row.get('evidence_design')=='unknown'
                or row.get('causal_design')=='unknown')


def consumer_guard(row,purpose):
    """Only denies authority. Legacy flags/relations cannot confer permission."""
    if not requires_effective(row):
        return {'status':'EXISTING_GATES_REQUIRED','purpose':purpose,'allowed_by_effective_layer':False,
                'applicable':False,'reason_codes':['NO_EFFECTIVE_AUTHORITY_ISSUED']}
    e=row.get('effective_interpretation');reasons=[]
    if not isinstance(e,dict):reasons.append('EFFECTIVE_INTERPRETATION_MISSING')
    else:
        try:
            if e['schema_version']!=VERSION or e['identity']!=VERSION+':'+content_hash({k:v for k,v in e.items() if k!='identity'}):
                reasons.append('EFFECTIVE_INTERPRETATION_VERSION_OR_CONTENT_INVALID')
            if e['binding']['raw_projection_sha256']!=content_hash(raw_projection(row)):reasons.append('RAW_PROJECTION_BINDING_CHANGED')
            if e['implementation']!=implementation_identity() or e['policy_sha256']!=file_hash(POLICY):reasons.append('STALE_EFFECTIVE_IMPLEMENTATION_OR_POLICY')
            if e['binding']['actual_interpretation_inputs_sha256']!=input_identity(e['binding']['configuration_pin']):reasons.append('EFFECTIVE_INPUT_DEPENDENCY_DRIFT')
            if e!=interpret_projection(raw_projection(row),e['binding']['configuration_pin']):reasons.append('EFFECTIVE_INTERPRETATION_NOT_REPRODUCIBLE_FROM_SOURCE')
            if any(e.get(k) is not False for k in AUTH if isinstance(AUTH[k],bool)):reasons.append('EFFECTIVE_AUTHORITY_PROMOTION_FORBIDDEN')
            if e['status']!='SOURCE_BOUND_PROVISIONAL':reasons.append('SOURCE_SEMANTICS_ABSTAINED')
        except (ValueError,KeyError,TypeError,OSError):reasons.append('EFFECTIVE_INTERPRETATION_UNVERIFIABLE')
    review=purpose=='review' and not reasons
    if purpose!='review':reasons.append('PROVISIONAL_INTERPRETATION_IS_NOT_'+purpose.upper()+'_AUTHORITY')
    return {**AUTH,'purpose':purpose,'status':'REVIEWABLE_ASSOCIATION_ONLY' if review else 'ABSTAIN',
            'applicable':True,'allowed_by_effective_layer':review,'raw_evidence_retained':True,'reason_codes':reasons}


def interpret_proposition(p):
    """B4 explicit source packets are independent of legacy/native projections.

    Called only after existing source/refs/inclusion validators. No positional
    mapping to native records and no permission from legacy increase/zero fields.
    """
    role=p.get('factor_role','unresolved')
    observational=role=='observational_biomarker_stratification'
    known_factor=role in ('physical_intervention','genetic_manipulation','exposure')
    direction=p['result']['direction'];null=direction=='not_significant'
    return {**AUTH,'schema_version':VERSION+':source_proposition',
        'source_semantic_binding_sha256':content_hash({k:p.get(k) for k in ('key','scope_identity','source_packet_pin','factor_role','facets','result')}),
        'source_proposition_key':p['key'],'source_packet':p.get('source_packet_pin'),
        'evidence_basis':'Existing explicit B4 source-facet validation; no legacy projection fields consumed',
        'study_design':'observational' if observational else 'source_reported_exposure_or_manipulation' if known_factor else 'unknown',
        'effective_relation_kind':'association' if observational else 'observed_outcome_after_source_contrast' if known_factor else 'unresolved',
        'reported_association_direction':({'increase':'positive','decrease':'negative'}.get(direction,'unknown') if observational else 'not_an_association_assessment'),
        'endpoint_as_reported':p.get('facets',{}).get('endpoint',{}).get('value'),
        'source_reported_result':p['result'].get('description'),
        'source_reported_statistics':p.get('facets',{}).get('statistical_interpretation'),
        'effect_magnitude_as_reported':p['result'].get('effect_size'),
        'effective_comparison_direction':'unknown' if null or observational else direction,
        'raw_reported_direction':direction,'statistical_null_as_recorded':null,
        'effective_outcome_sign':None,'zero_effect_asserted':False,'equivalence_established':False,
        'causal_sign':None,'legacy_projection_authority_consumed':False,
        'effect_contradiction_screening_permitted':known_factor and not null and direction in ('increase','decrease'),
        'interpretation_not_independent_scientific_validation':True}
