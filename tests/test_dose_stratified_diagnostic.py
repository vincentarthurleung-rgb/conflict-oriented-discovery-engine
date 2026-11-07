"""Explicit SOFTWARE_FIXTURE boundaries; frozen FMNT remains manual development."""
from copy import deepcopy
from pathlib import Path
import hashlib,json
import pytest
from code_engine.transport_failure_phase_binding_v2 import validate_schema
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.discovery.directional_discovery import native_direction_record,discover_directions
from code_engine.discovery.dose_stratified_diagnostic import diagnose_dose_stratified_reversal

R=Path(__file__).resolve().parents[1]
SCHEMA=json.loads((R/'docs/contracts/dose_stratified_direction_reversal_v1.schema.json').read_text())

def SOFTWARE_FIXTURE(dose='10 μM',sign='positive',*,agent='SOFTWARE_AGENT',endpoint='SOFTWARE_ENDPOINT',
                     assay='SOFTWARE_ASSAY readout',duration='24 h',system='SOFTWARE_SYSTEM',suffix='',shared=None):
    """In-memory software evidence flags are not real source-validation receipts."""
    text=shared or f'SOFTWARE_FIXTURE Figure 1B. {agent} treatment {dose} for {duration} in {system}, compared with SOFTWARE_CONTROL: {endpoint} {sign}. {assay}. '+suffix
    sid='SOFTWARE_FIXTURE:span:'+hashlib.sha256(text.encode()).hexdigest()
    span={'evidence_span_id':sid,'source_document_id':'SOFTWARE_FIXTURE:PMC','block_id':'SOFTWARE_FIXTURE:block',
        'char_start':0,'char_end':len(text),'text':text,'text_hash':hashlib.sha256(text.encode()).hexdigest(),'section':'results'}
    refs=[sid]
    f={'observation_id':'SOFTWARE_FIXTURE:'+str(dose)+sign,'provenance':{'source_document_id':'SOFTWARE_FIXTURE:PMC','evidence_spans':[span]},
       'experiment':{'evidence_family_id':'SOFTWARE_FIXTURE:Figure1B','experiment_label_raw':f'Figure 1B: {agent} {dose}',
          'experimental_design_raw':f'{agent} {dose} compared with SOFTWARE_CONTROL', 'design_type':'in_vitro',
          'model_system_raw':system,'comparison_arm_raw':agent,'control_arm_raw':'SOFTWARE_CONTROL'},
       'candidate_relation':{'lexical_direction':sign,'subject_mention':agent},
       'interventions':[{'role':'primary','agent_mention':agent,'target_mention':None,'intervention_type_raw':'treatment',
            'intervention_type':'drug_treatment','dose_raw':dose,'duration_raw':duration,'evidence_span_ids':refs}],
       'measurement':{'measured_entity_mention':system,'endpoint_raw':endpoint,'assay_or_readout_raw':assay,
            'measurement_dimension':'unknown','measurement_dimension_raw':'SOFTWARE_FIXTURE_READOUT','evidence_span_ids':refs},
       'observation':{'observed_result':text,'evidence_span_ids':refs},'extraction_warnings':['SOFTWARE_FIXTURE_NOT_SCIENTIFIC_EVIDENCE']}
    row=native_direction_record(f,publication={'pmcid':'SOFTWARE_FIXTURE:PMC','pmid':'SOFTWARE_FIXTURE:PMID'},
        source_binding={'source_sha256':'c'*64})
    row['source_verification']={'packet_sha256':content_hash(span),'source_sha256':'c'*64,
        'verified_packet_evidence':[{**span,'section_index':0,'source_json_pointer':'/SOFTWARE_FIXTURE/0'}]}
    return row


def diagnostic(rows):
    before=deepcopy(rows);d=diagnose_dose_stratified_reversal(rows)
    assert rows==before
    validate_schema(d,SCHEMA)
    assert not d['influences_existing_ABCD'] and not d['scientific_conflict_entropy_computed']
    assert not d['scientific_authorization'] and not d['Work_or_AI_review_consumed']
    return d


def test_SOFTWARE_FIXTURE_valid_reversal_separate_from_exact_ABCD():
    a=SOFTWARE_FIXTURE();b=SOFTWARE_FIXTURE('80 μM','negative')
    d=diagnostic([a,b]);assert d['reversal_family_count']==1
    exact=discover_directions([a,b])
    assert all(v==0 for v in exact['counts'].values()) and len(exact['groups'])==2
    assert exact['dose_stratified_direction_reversal']==d


def test_SOFTWARE_FIXTURE_same_sign_multiple_doses():
    assert diagnostic([SOFTWARE_FIXTURE(),SOFTWARE_FIXTURE('80 μM')])['reversal_family_count']==0


@pytest.mark.parametrize('field,value',[
    ('dose',None),('comparator',None),('endpoint','DIFFERENT_ENDPOINT'),('assay','DIFFERENT_ASSAY readout'),
    ('primary','DIFFERENT_AGENT'),('duration','48 h'),('system','DIFFERENT_SYSTEM'),('reverse',True),
    ('secondary',True),('direction','unclear'),('verification',False)])
def test_SOFTWARE_FIXTURE_abstentions_and_non_dose_differences(field,value):
    a=SOFTWARE_FIXTURE();kwargs={}
    if field in ('endpoint','assay','duration','system'):kwargs[field]=value
    if field=='primary':kwargs['agent']=value
    b=SOFTWARE_FIXTURE(None if field=='dose' else '80 μM',value if field=='direction' else 'negative',**kwargs)
    if field=='comparator':b['reference_arm']=None
    if field=='reverse':b['tested_arm'],b['reference_arm']=b['reference_arm'],b['tested_arm']
    if field=='secondary':b['all_interventions'].append({'role':'secondary','agent_mention':'SOFTWARE_INHIBITOR'})
    if field=='verification':b.pop('source_verification')
    assert diagnostic([a,b])['reversal_family_count']==0


def test_SOFTWARE_FIXTURE_shared_result_span_and_repeated_extraction_dependency():
    a=SOFTWARE_FIXTURE('2.5–40 μM')
    shared='SOFTWARE_FIXTURE Figure 1B. SOFTWARE_AGENT treatment 80 or 100 μM for 24 h in SOFTWARE_SYSTEM compared with SOFTWARE_CONTROL: SOFTWARE_ENDPOINT decreased. SOFTWARE_ASSAY readout.'
    b=SOFTWARE_FIXTURE('80 μM','negative',shared=shared);c=SOFTWARE_FIXTURE('100 μM','negative',shared=shared)
    duplicate=deepcopy(b);duplicate['observation_id']='SOFTWARE_FIXTURE:repeat';duplicate['record_identity']=content_hash(duplicate)
    d=diagnostic([a,b,c,duplicate]);assert len(d['duplicates'])==1
    f=d['families'][0];dep=f['dependency']
    assert len(f['strata'])==3 and f['strata'][0]['dose']['aggregate_statement']
    assert dep['distinct_original_result_spans']==2 and len(dep['shared_original_result_spans'])==1
    assert dep['publication_count']==1 and dep['independent_publication_replications']==0
    assert dep['independent_experimental_replications'] is None


def test_SOFTWARE_FIXTURE_unscoped_NS_does_not_delete_direction_or_assert_NS():
    a=SOFTWARE_FIXTURE();b=SOFTWARE_FIXTURE('80 μM','negative',suffix='NS, not significant.')
    assert b['statistical_significance_status']=='UNKNOWN' and b['effective_direction']==-1
    assert diagnostic([a,b])['reversal_family_count']==1


def test_SOFTWARE_FIXTURE_scoped_NS_is_not_screening_support():
    a=SOFTWARE_FIXTURE();b=SOFTWARE_FIXTURE('80 μM','negative',suffix='SOFTWARE_AGENT compared with SOFTWARE_CONTROL: SOFTWARE_ENDPOINT decreased, not significant.')
    assert b['statistical_significance_status']=='NONSIGNIFICANT' and b['effective_direction']==-1
    assert not b['conflict_screen_eligibility']['eligible']
    assert diagnostic([a,b])['reversal_family_count']==0


def test_SOFTWARE_FIXTURE_overlapping_range_not_invented_bins_and_no_cross_publication():
    assert diagnostic([SOFTWARE_FIXTURE('2.5–40 μM'),SOFTWARE_FIXTURE('20 μM','negative')])['reversal_family_count']==0
    a=SOFTWARE_FIXTURE();b=SOFTWARE_FIXTURE('80 μM','negative');b['publication']['pmcid']='SOFTWARE_FIXTURE:OTHER_PMC'
    assert diagnostic([a,b])['reversal_family_count']==0


def test_SOFTWARE_FIXTURE_conflicting_same_dose_abstains():
    d=diagnostic([SOFTWARE_FIXTURE(),SOFTWARE_FIXTURE('10 μM','negative'),SOFTWARE_FIXTURE('80 μM','negative')])
    assert d['reversal_family_count']==0
    assert any('CONFLICTING_DIRECTIONS_FOR_SAME_DOSE' in r['reasons'] for r in d['abstentions'])


@pytest.mark.parametrize('reference',['unknown','not_reported','unspecified'])
def test_SOFTWARE_FIXTURE_unknown_reference_never_wildcard(reference):
    a=SOFTWARE_FIXTURE();b=SOFTWARE_FIXTURE('80 μM','negative')
    a['reference_arm']=b['reference_arm']=reference
    assert diagnostic([a,b])['reversal_family_count']==0


def test_SOFTWARE_FIXTURE_ambiguous_agent_and_generic_system_abstain():
    assert diagnostic([SOFTWARE_FIXTURE(agent='SOFTWARE_A or SOFTWARE_B'),
        SOFTWARE_FIXTURE('80 μM','negative',agent='SOFTWARE_A or SOFTWARE_B')])['reversal_family_count']==0
    assert diagnostic([SOFTWARE_FIXTURE(system='cultured cells'),
        SOFTWARE_FIXTURE('80 μM','negative',system='cultured cells')])['reversal_family_count']==0


def test_genuine_FMNT_manual_namespace_via_production_source_validation():
    from code_engine.discovery.directional_discovery import run_initial_discovery
    base=R/'runs/20261104_code_fmnt_source_transcription_component_offline'
    records=json.loads((base/'production_component_inputs.json').read_text())
    old=json.loads((base/'production_initial_discovery_result.json').read_text())
    d=run_initial_discovery(records,dependencies='SOFTWARE_FIXTURE_CALLER_IDENTITY')
    assert d['counts']==old['counts'] and not d['rejected']
    new=d['dose_stratified_direction_reversal'];validate_schema(new,SCHEMA)
    assert new['reversal_family_count']==1
    assert all('DEV_FMNT_SOURCE_TRANSCRIPTION' in s['observation_id'] for s in new['families'][0]['strata'])
