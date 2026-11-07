"""D1–D5 provisional semantics and D7 disabled-issuer infrastructure, offline."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import json
import pytest
from code_engine.orchestration.pilot_semantic_grounding import (
 assess_candidates,owner_scope,verify_receipt,provisional_permission,assess_proposition,input_identity,ISSUER)
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.orchestration.pilot_case import PilotCaseExecutor,CaseIntegrity
from code_engine.orchestration.pilot_budget import ModelBudget
from code_engine.orchestration.pilot_dataset import verify_dataset
from tests.pilot_semantic_support import (real_inputs,OWNER,pin,ar_semantic,cross_semantic,
 hif_comparison,trib_comparison,null_comparison,R)
from tests.test_pilot_scientific_inclusion import seen
from tests.test_pilot_unlimited_integration import offline

@pytest.fixture
def real():
 prepared,outcome,ctx,inc=real_inputs();now=datetime.now(timezone.utc)
 args={'decision_pin':pin(OWNER),'inclusion':inc,'issued_at':now.isoformat(),'expires_at':(now+timedelta(days=1)).isoformat()}
 return prepared,outcome,ctx,args

@pytest.fixture
def assessed(real):
 p,o,c,k=real;return assess_candidates(p,o,context=c,**k)


def test_genuine_eight_structural_and_semantic_statuses_are_separate_without_promotion(assessed,real):
 rows=assessed['rows'];assert [x['assessment']['semantic_status'] for x in rows]==[
  'EXISTING_NATIVE_RELATION','UNSUPPORTED','CONTEXT_ONLY','SUPPORTED_PROVISIONAL','UNSUPPORTED','SUPPORTED_PROVISIONAL','UNSUPPORTED','CONTEXT_ONLY']
 assert [x['assessment']['structural_result'] for x in rows]==['ACCEPTED','REJECTED','ACCEPTED','ACCEPTED','REJECTED','ACCEPTED','REJECTED','REJECTED']
 p,o,c,k=real;assert [x['assessment']['original_proposal'] for x in rows]==o['original_response']['proposals']
 assert all(not x['verification']['machine_reuse_authorized'] and not x['receipt']['scientific_authorization'] for x in rows)
 assert all(x['verification']['status']=='VERIFIED_PROVISIONAL_PROVENANCE_ONLY' for x in rows)
 assert all(x['status']=='rejected' for x in assessed['materializer_decisions_unchanged'])
 assert assessed['materialized_links']==0


def test_receipt_binding_has_exact_source_revision_evidence_and_immutable_no_signature(assessed):
 r=assessed['rows'][3]['receipt'];b=r['binding']
 assert b['genuine_candidate_identity'] and b['original_proposal_index']==3 and b['original_proposal_id'] is None
 assert b['source_blocks_sha256'] and b['evidence_spans_sha256'] and b['core_revision_identity']
 assert r['revision_identity'] and r['policy']['sha256'] and r['validator_implementation']['sha256']
 assert owner_scope(pin(OWNER))['signature'] is None
 assert 'deterministic_grounding_version' not in r


def verify(row,**change):
 receipt=row['receipt'];args={'expected_binding':receipt['binding'],'expected_assessment':row['assessment'],'owner_decision_pin':pin(OWNER),
 'now':datetime.now(timezone.utc).isoformat(),'permissions':[provisional_permission(owner_scope(pin(OWNER)))],
 'current_revision':receipt['revision_identity']}
 args.update(change);return verify_receipt(receipt,**args)

@pytest.mark.parametrize('bad',['missing','unverified','expired','superseded','revoked','out_of_scope','issuer','binding','policy','validator','tampered_assessment','future','no_permission','fixture_production'])
def test_receipt_fail_closed(real,assessed,bad):
 row=deepcopy(assessed['rows'][3]);r=row['receipt'];kw={}
 if bad=='missing':row['receipt']=None
 elif bad=='unverified':kw['current_revision']=None
 elif bad=='expired':kw['now']=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
 elif bad=='superseded':kw['current_revision']='new_immutable_revision'
 elif bad=='revoked':kw['revoked_revisions']=[r['revision_identity']]
 elif bad=='out_of_scope':kw['requested_scope']='machine_reuse'
 elif bad=='issuer':r['issuer']['issuer_identity']='unapproved_producer'
 elif bad=='binding':kw['expected_binding']={**r['binding'],'core_revision_identity':'different_revision'}
 elif bad=='policy':r['policy']['sha256']='0'*64
 elif bad=='validator':r['validator_implementation']['sha256']='0'*64
 elif bad=='tampered_assessment':r['assessment']['semantic_status']='APPROVED'
 elif bad=='future':kw['now']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
 elif bad=='no_permission':kw['permissions']=[]
 elif bad=='fixture_production':r['issuer']['issuer_kind']='SOFTWARE_FIXTURE';kw['environment']='production'
 if row['receipt'] is None:
  base=assessed['rows'][3];out=verify_receipt(None,expected_binding=base['receipt']['binding'],expected_assessment=base['assessment'],owner_decision_pin=pin(OWNER),now=datetime.now(timezone.utc).isoformat(),permissions=[],current_revision=None)
 else:out=verify(row,**kw)
 assert out['status']=='BLOCKED' and out['reason_codes']
 assert not out['machine_reuse_authorized'] and not out['scientific_authorization'] and not out['strict_core_eligible']


@pytest.mark.parametrize('change',['unknown_measurement','ambiguous','conflicting_roles','uncertain','excluded','missing_orientation'])
def test_semantic_abstention_and_ambiguity_are_not_forced_support(real,change):
 p,o,c,k=deepcopy(real)
 if change=='unknown_measurement':c['annotation']['measurement_identities']=[]
 elif change=='ambiguous':c['annotation']['ambiguities']=['Source interpretation not resolved']
 elif change=='conflicting_roles':c['annotation']['roles'].append({**c['annotation']['roles'][0],'role':'SHARED_CONDITION'})
 elif change in ('uncertain','excluded'):k['inclusion']['decision']=change.upper()
 elif change=='missing_orientation':c['annotation']['orientations']=[]
 out=assess_candidates(p,o,context=c,**k)
 assert all(x['assessment']['semantic_status']!='SUPPORTED_PROVISIONAL' for x in out['rows'])
 assert all(not x['verification']['machine_reuse_authorized'] for x in out['rows'])


def test_positive_receipt_does_not_depend_on_semantic_support(assessed):
 # Valid provenance may document a rejection/context-only result, never approve it.
 for row in assessed['rows']:
  assert verify(row)['provisional_provenance_verified']
  assert not verify(row)['independent_source_semantic_authorization']


def test_authentic_actual_unified_Pilot_exports_all_eight_and_unchanged_Core(tmp_path):
 b,c,r=ar_semantic(tmp_path/'inputs');p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.db',c,offline=True),b).run(r)
 assert p['terminal_state']=='NOT_EVALUABLE',p['reason']
 semantic=[json.loads(a['utf8']) for a in p['artifacts'] if a['role'].endswith('_semantic_assessment.json')]
 actual=next(d for d in semantic if len(d.get('rows',[]))==8)
 assert sum(x['assessment']['semantic_status']=='SUPPORTED_PROVISIONAL' for x in actual['rows'])==2
 data=verify_dataset(tmp_path/'cases'/r['case_id']/'dataset')
 assert data['scientific_counts']['semantic_receipts']==8 and data['scientific_counts']['experimental_core']==5
 assert data['scientific_counts']['semantic_proposition_guards']==5 and not data['pipeline_complete']
 original=json.loads((R/'runs/20261023_code_renewed_owner_ar_only_live_v3_probe/assessment/derived_response.json').read_text())['records']
 saved=[json.loads(a['utf8']) for a in p['artifacts'] if a['role'].endswith('/core.json')]
 assert {content_hash(x) for x in saved}=={content_hash(json.loads(x['core_utf8'])) for x in original}


@pytest.mark.parametrize('factory,expected',[(hif_comparison,2),(trib_comparison,6),(null_comparison,1)])
def test_authentic_cross_design_proposition_guards_retain_null_and_observational_semantics(tmp_path,factory,expected):
 b,c,r=cross_semantic(factory,tmp_path/'inputs');p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.db',c,offline=True),b).run(r)
 assert p['terminal_state']=='NOT_EVALUABLE',p['reason']
 guards=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role']=='semantic_proposition_guards.json'))['rows'];assert len(guards)==expected
 if factory==trib_comparison:
  assert all(x['scientific_mode']=='observational_association' and not x['assigned_intervention_inferred'] for x in guards)
  assert all(x['status']=='ABSTAIN' for x in guards)
 elif factory==null_comparison:assert guards[0]['result_as_recorded']['direction']=='not_significant' and guards[0]['null_is_not_equivalence_or_negative_effect']
 else:
  assert guards[0]['context_fields']['cell_type']!=guards[1]['context_fields']['cell_type']
  assert guards[0]['context_fields']['time']!=guards[1]['context_fields']['time']
 assert all(not x['scientific_authorization'] for x in guards)


def test_conflicting_reference_bindings_are_ambiguous_not_first_item_selected(real):
 p,o,c,k=deepcopy(real);a=c['annotation']['orientations'][0];c['annotation']['orientations'].append({**a,'reference_arm_identity':a['tested_arm_identity']})
 out=assess_candidates(p,o,context=c,**k)
 assert all(x['assessment']['semantic_status']!='SUPPORTED_PROVISIONAL' for x in out['rows'])
 assert any(x['assessment']['semantic_status']=='AMBIGUOUS' for x in out['rows'])


def test_SOFTWARE_FIXTURE_valid_provenance_can_never_acquire_production_or_machine_scope(assessed):
 row=deepcopy(assessed['rows'][3]);r=row['receipt']
 r['issuer'].update(issuer_kind='SOFTWARE_FIXTURE',issuer_identity='SOFTWARE_FIXTURE:receipt_mechanics_only',environment='software_fixture')
 r['revision_identity']='provisional_grounding_receipt:'+content_hash({k:v for k,v in r.items() if k!='revision_identity'})
 out=verify(row,permissions=[r['issuer']],environment='software_fixture')
 assert out['status']=='VERIFIED_PROVISIONAL_PROVENANCE_ONLY'
 assert not out['machine_reuse_authorized'] and not out['scientific_authorization']
 assert verify(row,permissions=[r['issuer']],environment='production')['status']=='BLOCKED'
 assert verify(row,permissions=[r['issuer']],environment='software_fixture',requested_scope='machine_reuse')['status']=='BLOCKED'


def test_derived_semantic_input_drift_prevents_completed_reuse_without_more_dispatch(tmp_path):
 b,c,r=ar_semantic(tmp_path/'inputs');ex=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.db',c,offline=True),b);p=ex.run(r)
 cfg=json.loads(Path(r['semantic_grounding']['path']).read_text());annot=next(iter(cfg['observations'].values()));path=Path(annot['path']);data=json.loads(path.read_text());old=input_identity(r);calls=len(b.transport.calls)
 data['annotation']['ambiguities']=['Revised source interpretation pending review'];path.write_text(json.dumps(data))
 assert input_identity(r)!=old
 with pytest.raises(CaseIntegrity,match='input_drift'):ex.run(r)
 assert len(b.transport.calls)==calls


def test_unknown_measurement_proposition_abstains_and_NULL_never_becomes_negative():
 d=json.loads((R/'runs/20261028_code_recovery_batch4_scientific_comparison_offline/release_v3/HIF_NULL/cases/B3-HIF-NULL/scientific_comparison.json').read_text())['propositions'][0]
 d['facets']['entity']['value']=None;out=assess_proposition(d)
 assert out['status']=='ABSTAIN' and 'MEASUREMENT_IDENTITY_UNRESOLVED' in out['reason_codes']
 assert out['result_as_recorded']['direction']=='not_significant'


@pytest.mark.parametrize('change',['unknown_design','unbound_contrast_evidence','unresolved_reference_role'])
def test_focal_candidate_requires_measurement_specific_evidenced_contrast(real,change):
 p,o,c,k=deepcopy(real)
 if change=='unknown_design':c['annotation']['design']='unknown'
 elif change=='unbound_contrast_evidence':
  proposal_refs=set(o['original_response']['proposals'][3]['evidence_refs'])
  other=next(s['evidence_span_id'] for s in p['input']['evidence_spans'] if s['evidence_span_id'] not in proposal_refs)
  c['annotation']['orientations'][0]['evidence_refs']=[other]
 else:
  ref=c['annotation']['orientations'][0]['reference_arm_identity']
  next(x for x in c['annotation']['roles'] if x['component_identity']==ref)['role']='UNRESOLVED'
 out=assess_candidates(p,o,context=c,**k)
 assert out['rows'][3]['assessment']['semantic_status']=='ABSTAIN'
 assert not out['rows'][3]['verification']['machine_reuse_authorized']
