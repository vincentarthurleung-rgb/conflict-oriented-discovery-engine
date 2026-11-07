"""Authentic correspondence and isolated SOFTWARE_FIXTURE adversarial controls."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.orchestration.pilot_native_proposition_binding import (
    bind_native_propositions, _semantic_match, _verify_spans, resolve_ambiguity, input_identity)
from code_engine.orchestration.pilot_native_representation import recover_native_jsonl
from tests.pilot_native_proposition_binding_support import configuration, FROZEN
from tests.pilot_inclusion_support import write,pin


@pytest.fixture(scope='module')
def real(tmp_path_factory):
    root=tmp_path_factory.mktemp('binding_authentic')
    ref=configuration(root/'inputs');cfg=json.loads(Path(ref['path']).read_text())
    source=cfg['sources'][0];native=recover_native_jsonl(source['native_replay_manifest'])
    projected=json.loads((FROZEN/'projected_native_observations.json').read_text())
    records=[]
    for i,item in enumerate(native['records']):
        core=write(root/(str(i)+'_core.json'),json.loads(item['core_utf8']));oid=json.loads(item['core_utf8'])['ExperimentalObservationV3']['observation_id']
        link=next(json.loads(p.read_text()) for p in FROZEN.glob('*_linkage_input.json') if json.loads(p.read_text())['input']['observation_identity']==oid)
        records.append({'core':core,'projection_row':next(r for r in projected if r['observation_id']==oid),'linkage_prepared':link})
    ledger=json.loads((FROZEN/'scientific_inclusion_final.json').read_text())
    props=json.loads((FROZEN/'scientific_comparison.json').read_text())['propositions']
    req={'native_proposition_binding':ref}
    return root,req,ledger,records,props


def run(real):
    _,req,ledger,records,props=real
    return bind_native_propositions(req,ledger,records,props,dependencies='SOFTWARE_TEST_DEPENDENCY_ID_ONLY')


def test_authentic_inventory_and_source_matching_without_positional_mapping(real):
    out=run(real)
    assert len(out['native_inventory'])==6 and len(out['proposition_inventory'])==6
    assert len(out['rows'])==36
    for r in out['rows']:
        n=r['native_fields']['fields'];p=r['proposition_fields']['fields']
        if r['decision']=='SOURCE_BOUND_PROVISIONAL_MATCH':
            assert n['endpoint']['value']==p['endpoint']['value']=='overall survival'
            assert n['subgroup']['value']==p['subgroup']['value']
            assert r['same_result_evidence']
        if p['endpoint']['value']=='event-free survival':assert r['decision']=='NONMATCH'
        if n['scope_kind']['value']=='stage':assert r['decision']=='NONMATCH'
        assert r['B3_native_decision']['decision']=='UNCERTAIN' and not r['B3_decision_inherited']
        assert not r['scientific_authorization'] and not r['machine_reuse_authorized'] and not r['formal_L4_compatible']
        assert not r['comparator_orientation_validated'] and not r['canonical_identity_approved']
        assert r['source_lineage']['source_representations']['original_xml']['sha256']!=r['source_lineage']['source_representations']['paragraph_projection']['sha256']
    # Exercise identical genuine records in reversed input order; no inferred pairing.
    root,req,ledger,records,props=real
    reverse=bind_native_propositions(req,ledger,list(reversed(records)),list(reversed(props)),dependencies='SOFTWARE_TEST_DEPENDENCY_ID_ONLY')
    assert out==reverse


@pytest.mark.parametrize('kind',['wrong_xml_hash','wrong_JSON_identity','wrong_coordinate_representation',
    'wrong_Core_revision','wrong_observation','missing_evidence','stale_interpretation','stale_B3',
    'duplicate_native_profile','duplicate_proposition_profile','authority_promotion','wrong_patient_subgroup',
    'reversed_reference','endpoint_relabel'])
def test_SOFTWARE_FIXTURE_invalid_inputs_fail_closed(real,tmp_path,kind):
    root,req,ledger,records,props=real
    request=deepcopy(req);cfg=json.loads(Path(req['native_proposition_binding']['path']).read_text())
    a=cfg['native_profiles'][0]
    if kind in ('wrong_xml_hash','wrong_JSON_identity','wrong_coordinate_representation'):
        src=cfg['sources'][0];manifest=json.loads(Path(src['native_replay_manifest']['path']).read_text())
        if kind=='wrong_xml_hash':manifest['original_xml']['sha256']='0'*64
        elif kind=='wrong_JSON_identity':manifest['article_json']['sha256']='0'*64
        else:manifest['coordinate_mapping']='raw_XML_byte_offsets'
        src['native_replay_manifest']=pin(write(tmp_path/'SOFTWARE_FIXTURE_manifest.json',manifest))
    elif kind=='wrong_Core_revision':a['revision_identity']='SOFTWARE_FIXTURE_wrong_Core'
    elif kind=='wrong_observation':a['key']='SOFTWARE_FIXTURE_wrong_observation'
    elif kind=='missing_evidence':a['fields']['subgroup']['evidence_refs']=[]
    elif kind=='stale_interpretation':a['effective_interpretation_identity']='SOFTWARE_FIXTURE_stale'
    elif kind=='stale_B3':a['inclusion_revision_identity']='SOFTWARE_FIXTURE_stale'
    elif kind=='duplicate_native_profile':cfg['native_profiles'].append(deepcopy(a))
    elif kind=='duplicate_proposition_profile':cfg['proposition_profiles'].append(deepcopy(cfg['proposition_profiles'][0]))
    elif kind=='authority_promotion':a['scientific_authorization']=True
    elif kind=='wrong_patient_subgroup':a['fields']['subgroup']['value']='SOFTWARE_FIXTURE_wrong_patient_group'
    elif kind=='reversed_reference':a['fields']['reference_group']['value']='TRIB3-positive'
    elif kind=='endpoint_relabel':a['fields']['endpoint']['value']='event-free survival'
    request['native_proposition_binding']=pin(write(tmp_path/'SOFTWARE_FIXTURE_config.json',cfg))
    with pytest.raises(ValueError):bind_native_propositions(request,ledger,records,props,dependencies='SOFTWARE_FIXTURE')


@pytest.mark.parametrize('kind',['OVS_EFS','risk_stage','wrong_subgroup','similar_language_different_scope',
                                 'orientation_conflict','missing_required_field'])
def test_SOFTWARE_FIXTURE_semantic_nonmatches_and_uncertainty(real,kind):
    out=run(real)
    row=next(r for r in out['rows'] if r['decision']=='SOURCE_BOUND_PROVISIONAL_MATCH')
    n,p=deepcopy(row['native_fields']),deepcopy(row['proposition_fields'])
    ns,ps=deepcopy(row['native_evidence_coordinates']),deepcopy(row['proposition_evidence_coordinates'])
    if kind=='OVS_EFS':p['fields']['endpoint']['value']='event-free survival'
    elif kind=='risk_stage':p['fields']['scope_kind']['value']='stage'
    elif kind=='wrong_subgroup':p['fields']['subgroup']['value']='SOFTWARE_FIXTURE_unrelated_subgroup'
    elif kind=='similar_language_different_scope':
        for s in ps:s['section_index']+=100
    elif kind=='orientation_conflict':p['fields']['reference_group']['value']='TRIB3-positive'
    else:p['fields']['subgroup']['value']=None
    decision,_,_=_semantic_match(n,p,ns,ps)
    assert decision in ('NONMATCH','UNRESOLVED') and decision!='SOURCE_BOUND_PROVISIONAL_MATCH'


def test_SOFTWARE_FIXTURE_multiple_supported_candidates_abstain_without_tiebreak():
    rows=[{'observation_id':'SOFTWARE_FIXTURE_native','proposition_key':k,'decision':'SOURCE_BOUND_PROVISIONAL_MATCH'} for k in ('a','b')]
    assert all(r['decision']=='AMBIGUOUS' for r in resolve_ambiguity(rows))


def test_SOFTWARE_FIXTURE_wrong_coordinate_representation_and_offsets(real):
    out=run(real);span=deepcopy(out['rows'][0]['proposition_evidence_coordinates'][0])
    article=json.loads(Path(out['rows'][0]['source_lineage']['source_representations']['paragraph_projection']['path']).read_text())
    expected=span['coordinate_unit'];span['coordinate_unit']='SOFTWARE_FIXTURE_XML_BYTES'
    with pytest.raises(ValueError,match='coordinate_representation'):_verify_spans([span],article,expected)
    span['coordinate_unit']=expected;span['char_start']+=1
    with pytest.raises(ValueError,match='coordinate_or_hash'):_verify_spans([span],article,expected)


def test_SOFTWARE_FIXTURE_stale_current_inclusion_content_fails(real):
    root,req,ledger,records,props=real;ledger=deepcopy(ledger)
    next(r for r in ledger['rows'] if r['scope_level']=='observation')['revision_identity']='SOFTWARE_FIXTURE_stale_current_revision'
    with pytest.raises(ValueError,match='B3_revision'):bind_native_propositions(req,ledger,records,props,dependencies='SOFTWARE_FIXTURE')


def test_binding_input_bytes_invalidate_derived_identity(real,tmp_path):
    _,req,_,_,_=real;original=input_identity(req)
    cfg=json.loads(Path(req['native_proposition_binding']['path']).read_text());cfg['producer']+='; revised explanatory commentary'
    new={'native_proposition_binding':pin(write(tmp_path/'revision.json',cfg))}
    assert original!=input_identity(new)


def test_absent_optin_retains_independent_paths():
    r=bind_native_propositions({}, {'rows':[]}, [], [], dependencies='SOFTWARE_FIXTURE')
    assert r['status']=='NOT_EVALUATED' and r['rows']==[] and not r['scientific_authorization']
