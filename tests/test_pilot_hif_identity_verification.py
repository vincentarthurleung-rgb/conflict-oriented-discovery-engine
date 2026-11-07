"""Genuine owner-limited source checks; adversarial edits are SOFTWARE_FIXTURE."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import json
import pytest
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.orchestration.pilot_hif_identity_verification import (
    VERSION,RECEIPT,run_bounded_hif_verification,verify_local_receipt,input_identity,_stamp)
from tests.pilot_hif_identity_verification_support import authority,genuine_B410_HIF,B410
from tests.pilot_inclusion_support import pin,write


@pytest.fixture(scope='module')
def real(tmp_path_factory):
    root=tmp_path_factory.mktemp('real_HIF_bounded')
    ref=authority(root/'authority');cfg=json.loads(Path(ref['path']).read_text());owner=json.loads(Path(cfg['owner_authorization']['path']).read_text())
    return ref,cfg,genuine_B410_HIF(),owner['issued_at']


def run(ref,data,now):
    return run_bounded_hif_verification({'bounded_hif_identity_verification':ref},data,dependencies='SOFTWARE_TEST_DEPENDENCY_CONTEXT_ONLY',now=now)


def verify(receipt,cfg,now,**change):
    return verify_local_receipt(receipt,owner_authorization=cfg['owner_authorization'],current_lifecycle=cfg['current_lifecycle'],now=now,**change)


def test_two_genuine_sources_verify_only_local_protein_type_role_and_remain_gate_blocked(real):
    ref,cfg,data,now=real;out=run(ref,data,now)
    assert out['status']=='BOUNDED_VERIFICATION_COMPLETE' and len(out['rows'])==2
    assert out['correspondence']['status']=='LOCALLY_VERIFIED_BROAD_PROTEIN_TARGET_CORRESPONDENCE'
    assert out['correspondence']['existing_contract_decision']['external_canonical_authority']=='local_identity_only'
    for row in out['rows']:
        v=row['verification'];a=v['verified_assessment']
        assert v['status']=='VERIFIED_BOUNDED_LOCAL_TYPE_ROLE' and a['reported_type']=='protein'
        assert a['mention']['entity_type']=='protein' and not a['mention']['canonical_ids']
        assert a['mention']['proposition_role']=='measurement_target_identity'
        assert row['actual_gate_decision']['eligibility_status']=='blocked_upstream_entity_integrity'
        assert row['original_subject_identity'] is row['original_object_target_identity'] is None
        assert not row['external_identity_verified'] and not row['independent_scientific_validation']
        assert not row['machine_reuse_authorized'] and not row['formal_scientific_promotion_authorized']
        assert not row['operational_equivalence_verified'] and not row['comparator_orientation_verified']
        assert a['dimensions']['C_exposure_role']['canonical_exposure_identity'] is None
        assert a['structured_value']['canonical_identity'] is None
        assert row['actual_require_rejection']
    a549=next(r for r in out['rows'] if r['proposition_key']=='PMC7749157')['verification']['verified_assessment']
    assert a549['nominal_reference_concentration_percent'] is None
    assert '24 hours'==a549['context']['time']['value']
    assert 'DMSO' in a549['context']['reference_arm']['value']
    assert data==genuine_B410_HIF()


def fixture_receipt(real,tmp_path,kind):
    ref,cfg,data,now=real;cfg=deepcopy(cfg);receipt=json.loads(Path(cfg['receipts'][0]['path']).read_text())
    if kind=='gene':receipt['assessment']['reported_type']='gene'
    elif kind=='mRNA':receipt['assessment']['reported_target']='HIF1A mRNA'
    elif kind=='isoform':receipt['assessment']['mention']['source_surface']='HIF-1α isoform 2'
    elif kind=='wrong_source':receipt['evidence_binding']['source_input_hashes']['source']='0'*64
    elif kind=='wrong_Core':receipt['evidence_binding']['Core_revision']='SOFTWARE_FIXTURE_wrong_revision'
    elif kind=='assay_equivalence':receipt['assessment']['operational_equivalence_verified']=True
    elif kind=='causal_role':receipt['assessment']['scientific_type_role_scope']='causal HIF1A gene regulation of transcription'
    elif kind=='unapproved_issuer':receipt['issuer']['issuer_identity']='SOFTWARE_FIXTURE_unapproved_issuer'
    elif kind=='insufficient_evidence':receipt['assessment']['affirmative_evidence']=[]
    elif kind=='canonical_alias':receipt['assessment']['structured_value']['canonical_identity']='SOFTWARE_FIXTURE_canonical'
    elif kind=='short_expiry':receipt['expires_at']=(_stamp(now)+timedelta(seconds=1)).isoformat()
    receipt['assessment_sha256']=content_hash(receipt['assessment'])
    receipt['revision_identity']=RECEIPT+':'+content_hash({k:v for k,v in receipt.items() if k!='revision_identity'})
    # A separate, explicitly selected SOFTWARE_FIXTURE lifecycle makes hashes
    # current even for this bad receipt. Evidence and issuer verification must
    # still reject it; receipt hash/lifecycle membership alone is insufficient.
    lifecycle=json.loads(Path(cfg['current_lifecycle']['path']).read_text())
    lifecycle['current_receipt_by_observation'][receipt['observation_id']]=receipt['revision_identity']
    lifecycle['revision_identity']='bounded_hif_identity_lifecycle:'+content_hash({k:v for k,v in lifecycle.items() if k!='revision_identity'})
    cfg['current_lifecycle']=pin(write(tmp_path/'SOFTWARE_FIXTURE_checkpoint.json',lifecycle))
    return receipt,cfg,now


@pytest.mark.parametrize('kind',['gene','mRNA','isoform','wrong_source','wrong_Core','assay_equivalence','causal_role','unapproved_issuer','insufficient_evidence','canonical_alias'])
def test_SOFTWARE_FIXTURE_current_well_formed_receipt_cannot_self_authenticate_science(real,tmp_path,kind):
    receipt,cfg,now=fixture_receipt(real,tmp_path,kind)
    out=verify(receipt,cfg,now)
    assert out['status']=='BLOCKED' and out['reason_codes'] and not out['local_type_role_verified']
    assert not out['formal_scientific_promotion_authorized'] and not out['machine_reuse_authorized']


@pytest.mark.parametrize('kind',['wrong_cell','wrong_time','wrong_oxygen','invented_normoxia','wrong_reference','wrong_observation','gene_alias','protein_mRNA','current_source','current_Core','current_provenance'])
def test_SOFTWARE_FIXTURE_current_context_or_target_cannot_reuse_valid_receipt(real,kind):
    ref,cfg,original,now=real;data=deepcopy(original);row=data['rows'][1]
    if kind=='wrong_cell':row['context_and_measurement']['cell_type']['value']='HCT116'
    elif kind=='wrong_time':row['context_and_measurement']['time']['value']='72 hours'
    elif kind=='wrong_oxygen':row['context_and_measurement']['dose']['value']='5% versus 20% O2'
    elif kind=='invented_normoxia':row['context_and_measurement']['reference_arm']['value']='21% O2 A549 with DMSO'
    elif kind=='wrong_reference':row['context_and_measurement']['reference_arm']['value']='HIF inhibitor arm'
    elif kind=='wrong_observation':row['native_observation_id']='SOFTWARE_FIXTURE_wrong_observation'
    elif kind=='current_source':row['source_sha256']='0'*64
    elif kind=='current_Core':row['native_Core_revision']='SOFTWARE_FIXTURE_wrong_Core'
    elif kind=='current_provenance':row['native_original_source_provenance']['fulltext_source_hash']='0'*64
    elif kind=='gene_alias':next(f for f in row['identity_fields'] if f['field']=='measured_entity')['raw_source_mention']='HIF1A'
    else:row['context_and_measurement']['endpoint']['value']='HIF1A mRNA abundance'
    row['identity_evidence_revision']='scientific_identity_evidence_preparation_v1:'+content_hash({k:v for k,v in row.items() if k!='identity_evidence_revision'})
    out=run(ref,data,now)
    assert out['status'] in ('BOUNDED_VERIFICATION_BLOCKED','ABSTAIN_OUT_OF_SCOPE')
    assert out['correspondence'] is None
    assert any(not r['verification']['local_type_role_verified'] for r in out['rows']) if out['rows'] else True


@pytest.mark.parametrize('kind',['expired','revoked','superseded','missing_lifecycle','missing_owner','wrong_scope','future'])
def test_SOFTWARE_FIXTURE_trusted_current_revision_and_time_required(real,tmp_path,kind):
    ref,cfg,data,now=real;cfg=deepcopy(cfg);receipt=json.loads(Path(cfg['receipts'][0]['path']).read_text());change={}
    if kind=='expired':now=receipt['expires_at']
    elif kind=='future':now=(_stamp(now)-timedelta(seconds=1)).isoformat()
    elif kind in ('revoked','superseded'):
        lifecycle=json.loads(Path(cfg['current_lifecycle']['path']).read_text())
        if kind=='revoked':lifecycle['revoked_receipts']=[receipt['revision_identity']]
        else:lifecycle['current_receipt_by_observation'][receipt['observation_id']]='SOFTWARE_FIXTURE_new_revision'
        lifecycle['revision_identity']='bounded_hif_identity_lifecycle:'+content_hash({k:v for k,v in lifecycle.items() if k!='revision_identity'})
        cfg['current_lifecycle']=pin(write(tmp_path/'SOFTWARE_FIXTURE_lifecycle.json',lifecycle))
    elif kind=='missing_lifecycle':cfg['current_lifecycle']=None
    elif kind=='missing_owner':cfg['owner_authorization']=None
    elif kind=='wrong_scope':change['requested_scope']='materialize_causal_relation'
    out=verify(receipt,cfg,now,**change)
    assert out['status']=='BLOCKED' and not out['local_type_role_verified']


def test_SOFTWARE_FIXTURE_receipt_expiry_inside_active_owner_window_is_enforced(real,tmp_path):
    receipt,cfg,now=fixture_receipt(real,tmp_path,'short_expiry')
    out=verify(receipt,cfg,(_stamp(now)+timedelta(seconds=2)).isoformat())
    assert 'bounded_receipt_expired_or_invalid_time' in out['reason_codes']


def test_SOFTWARE_FIXTURE_valid_receipt_fails_when_actual_scientific_evidence_is_missing(real,monkeypatch):
    ref,cfg,data,now=real;receipt=json.loads(Path(cfg['receipts'][0]['path']).read_text())
    def missing(*args,**kwargs):raise ValueError('SOFTWARE_FIXTURE_affirmative_scientific_evidence_unavailable')
    monkeypatch.setattr('code_engine.orchestration.pilot_hif_identity_verification.assess_source',missing)
    out=verify(receipt,cfg,now)
    assert out['status']=='BLOCKED' and any('affirmative_scientific_evidence_unavailable' in x for x in out['reason_codes'])


@pytest.mark.parametrize('label',['TRIB3','AR','HIF_NULL'])
def test_real_cross_case_authority_does_not_leak(real,label):
    ref,cfg,data,now=real;root=next((B410/label/'cases').glob('B3-*'))
    other=json.loads((root/'scientific_identity_evidence.json').read_text())
    out=run(ref,other,now)
    assert out['status']=='ABSTAIN_OUT_OF_SCOPE' and out['rows']==[] and out['correspondence'] is None


def test_receipt_time_phase_invalidates_only_derived_identity(real):
    ref,cfg,data,now=real;request={'bounded_hif_identity_verification':ref}
    owner=json.loads(Path(cfg['owner_authorization']['path']).read_text())
    assert input_identity(request,now=now)!=input_identity(request,now=owner['expires_at'])


def test_no_selected_policy_grants_no_local_verification(real):
    out=run_bounded_hif_verification({},real[2],dependencies='SOFTWARE_FIXTURE')
    assert out['status']=='NOT_EVALUATED' and out['rows']==[]
