"""Real source identity preparation; adversarial controls are SOFTWARE_FIXTURE."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.orchestration.pilot_identity_evidence import prepare_identity_evidence,input_identity,retained_binding_artifact
from tests.pilot_identity_evidence_support import configuration,FROZEN
from tests.pilot_inclusion_support import write,pin


@pytest.fixture(scope='module')
def real(tmp_path_factory):
    root=tmp_path_factory.mktemp('identity_authentic');cases={}
    for label,frozen in FROZEN.items():
        ref=configuration(label,root/label)
        props=json.loads((frozen/'scientific_comparison.json').read_text())['propositions']
        ledger=json.loads((frozen/'scientific_inclusion_final.json').read_text())
        projections=json.loads((frozen/'projected_native_observations.json').read_text()) if (frozen/'projected_native_observations.json').exists() else []
        records=[]
        for path in frozen.rglob('core.json'):
            oid=json.loads(path.read_text())['ExperimentalObservationV3']['observation_id']
            view=next((r for r in projections if r['observation_id']==oid),None)
            records.append({'core':path,'effective_projection':view['effective_interpretation'] if view else None})
        cases[label]=({'scientific_identity_evidence':ref},ledger,records,props)
    return cases


def call(data):
    req,ledger,records,props=data
    return prepare_identity_evidence(req,ledger,records,props,dependencies='SOFTWARE_TEST_DEPENDENCIES_ONLY')


def test_real_seven_inputs_remain_source_bound_and_fail_actual_integrity_gate(real):
    outputs={k:call(v) for k,v in real.items()}
    rows=[r for d in outputs.values() for r in d['rows']]
    assert len(rows)==7
    for row in rows:
        assert row['actual_gate_decision']['eligibility_status']=='blocked_upstream_entity_integrity'
        assert row['actual_require_rejection'] and not row['actual_gate_decision']['authoritative_for_scientific_promotion']
        assert not row['scientific_identity_authorized'] and not row['approved_identity_verification'] and not row['formal_L4_eligible']
        assert row['scientific_signature_unchanged']['subject_identity'] is row['scientific_signature_unchanged']['object_target_identity'] is None
        for field in row['identity_fields']:
            assert field['structured_term']['canonical_identity'] is None
            assert not field['existing_local_equivalence_decision']['eligible_for_local_equivalence']
            assert field['existing_entity_mention_contract']['entity_type'] is None
            assert field['identity_candidate_completeness']=='NO_EXISTING_CANDIDATE'
            assert not field['normalization_decision']['canonical_id'] if field['normalization_decision'] else True
    tri=outputs['TRIB3'];assert len(tri['rows'])==3
    assert all('overall survival' in r['proposition_key'] for r in tri['rows'])
    assert all(r['B4_9_binding_revision'] for r in tri['rows'])
    assert {r['B3_current_decision'] for r in tri['rows']}=={'INCLUDED'}
    assert all(r['source_supplement']['authority']=='frozen_fulltext_supplement_not_historical_provider_input_authority' for r in tri['rows'])
    assert len(outputs['HIF']['rows'])==2
    assert outputs['HIF_NULL']['rows'][0]['native_Core_revision'] is None
    assert outputs['HIF_NULL']['rows'][0]['reported_result']['direction']=='not_significant'
    assert not outputs['HIF_NULL']['rows'][0]['effective_result']['zero_effect_asserted']
    for out in outputs.values():
        review=out['review_packets'][0]
        assert review['reviewer_assigned'] is review['review_decision_recorded'] is None
        assert not review['scientific_authorization']
        assert out['registry_probe']['provider_names']==['LocalCuratedProvider','NullProvider']


@pytest.mark.parametrize('kind',['gene_protein_confusion','observational_to_intervention','OVS_to_EFS','missing_authority',
    'wrong_Core','wrong_source','unsupported_alias','incomplete_assay','unverified_orientation','causal_promotion',
    'missing_evidence','empty_surface','wrong_binding','unmatched_stage_native','wrong_B3_revision'])
def test_SOFTWARE_FIXTURE_identity_controls_never_promote(real,tmp_path,kind):
    label='HIF' if kind=='gene_protein_confusion' else 'TRIB3'
    req,ledger,records,props=deepcopy(real[label]);cfg=json.loads(Path(req['scientific_identity_evidence']['path']).read_text())
    item=cfg['items'][0];m=item['mentions']
    must_reject=True
    if kind=='gene_protein_confusion':m['biological_entity']['facet_value']='HIF1A gene identity'
    elif kind=='observational_to_intervention':m['intervention_or_grouping']['facet_value']='assigned TRIB3 knockout'
    elif kind=='OVS_to_EFS':m['endpoint']['facet_value']='event-free survival'
    elif kind=='missing_authority':
        must_reject=False
        # All real inputs already lack authority; exact mentions do not fill it.
    elif kind=='wrong_Core':item['native_core']['sha256']='0'*64
    elif kind=='wrong_source':item['frozen_comparison']['sha256']='0'*64
    elif kind=='unsupported_alias':m['biological_entity']['raw_mention']='SOFTWARE_FIXTURE_unsupported_gene_alias'
    elif kind=='incomplete_assay':
        m['measured_entity']['raw_mention']=None;m['measured_entity']['evidence_refs']=[];must_reject=False
    elif kind=='unverified_orientation':
        m['comparison']['candidate_interpretation']='SOFTWARE_FIXTURE interpretation claims an orientation but contains no approved verification';must_reject=False
    elif kind=='causal_promotion':cfg['scientific_authorization']=True
    elif kind=='missing_evidence':m['biological_entity']['evidence_refs']=[]
    elif kind=='empty_surface':m['biological_entity']['raw_mention']=''
    elif kind=='wrong_binding':item['B4_9_binding_revision']='SOFTWARE_FIXTURE_wrong_binding'
    elif kind=='unmatched_stage_native':item['native_observation_id']='ftl1v3_6e04318a5dd1cb6d540643e6'
    elif kind=='wrong_B3_revision':
        data=json.loads(Path(item['frozen_inclusion']['path']).read_text())
        next(r for r in data['rows'] if r['scope_identity']==props[0]['scope_identity'])['revision_identity']='SOFTWARE_FIXTURE_stale'
        item['frozen_inclusion']=pin(write(tmp_path/'SOFTWARE_FIXTURE_ledger.json',data))
    req['scientific_identity_evidence']=pin(write(tmp_path/'SOFTWARE_FIXTURE_identity.json',cfg))
    if must_reject:
        with pytest.raises(ValueError):call((req,ledger,records,props))
    else:
        out=call((req,ledger,records,props))
        assert all(not r['approved_identity_verification'] and not r['formal_L4_eligible'] and r['actual_require_rejection'] for r in out['rows'])


def test_retained_binding_is_exact_frozen_artifact_without_rematching(real):
    req,_,_,_=real['TRIB3'];before=deepcopy(req)
    retained=retained_binding_artifact(req)
    original=json.loads((FROZEN['TRIB3']/'native_proposition_bindings.json').read_text())
    assert retained==original and req==before
    assert len(retained['rows'])==36 and sum(r['decision']=='SOURCE_BOUND_PROVISIONAL_MATCH' for r in retained['rows'])==3


def test_SOFTWARE_FIXTURE_expired_revoked_or_identity_scope_receipts_cannot_authorize():
    from code_engine.orchestration.pilot_semantic_grounding import verify_receipt,provisional_permission,owner_scope
    from tests.pilot_semantic_support import OWNER
    # Genuine frozen software-provenance receipt; no new receipt, issuer or review.
    old=next(d for p in FROZEN['AR'].glob('*_semantic_assessment.json') if (d:=json.loads(p.read_text())).get('rows'))
    row=next(r for r in old['rows'] if r.get('receipt'));receipt=row['receipt']
    base=dict(expected_binding=receipt['binding'],expected_assessment=row['assessment'],owner_decision_pin=pin(OWNER),
        now=receipt['issued_at'],permissions=[provisional_permission(owner_scope(pin(OWNER)))],current_revision=receipt['revision_identity'])
    cases=[({'now':receipt['expires_at']},'receipt_expired_or_invalid_time'),
           ({'revoked_revisions':[receipt['revision_identity']]},'receipt_revoked'),
           ({'requested_scope':'scientific_identity_verification'},'receipt_scope_not_permitted')]
    for change,reason in cases:
        out=verify_receipt(receipt,**{**base,**change})
        assert out['status']=='BLOCKED' and reason in out['reason_codes']
        assert not out['scientific_authorization'] and not out['independent_source_semantic_authorization']


def test_revision_and_review_content_addressing(real,tmp_path):
    req,ledger,records,props=deepcopy(real['HIF']);before=input_identity(req)
    cfg=json.loads(Path(req['scientific_identity_evidence']['path']).read_text());cfg['review_decision']+=' Clarification wording revised.'
    req['scientific_identity_evidence']=pin(write(tmp_path/'new_revision.json',cfg))
    assert input_identity(req)!=before
    d=call((req,ledger,records,props));review=d['review_packets'][0]
    assert review['review_packet_identity']=='scientific_identity_evidence_review_packet_v1:'+content_hash({k:v for k,v in review.items() if k!='review_packet_identity'})


def test_no_configuration_does_not_issue_identity():
    out=prepare_identity_evidence({}, {'rows':[]},[],[],dependencies='SOFTWARE_FIXTURE')
    assert out['status']=='NOT_EVALUATED' and out['rows']==[] and not out['formal_L4_eligible']
