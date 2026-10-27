"""Batch 2 focused acceptance. Frozen science, explicit software faults, no network."""
from copy import deepcopy
from pathlib import Path
import json,socket
import pytest

from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.orchestration.pilot_linkage import prepare_stage,assess_stage
from code_engine.orchestration.pilot_budget import ModelBudget
from code_engine.orchestration.pilot_case import PilotCaseExecutor,CaseIntegrity
from code_engine.orchestration.pilot_dataset import verify_dataset,export_attempt_dataset
from code_engine.orchestration.pilot_delivery import validate_case_package
from code_engine.orchestration.pilot_model_cache import SourceModelCache
from code_engine.corpus.historical_seen import HistoricalSeen,digest
from code_engine.system_b.persistence.services.pilot_review_display import scientific_page,case_display
from tests.pilot_linkage_support import inputs,backend_fixture,OID,pin,RELEASE,LIVE
from tests.test_pilot_unlimited_integration import offline

@pytest.fixture
def ar_seen(tmp_path):
 v={'certified':True,'coverage':{'opaque_captures':[]},'source_identity_sets':{'pmid':['42715313'],'pmcid':['PMC13557098'],'doi':[],'untyped_ncbi_uid':[]},'candidate_tracking':{'candidate_id':[],'candidate_payload_sha256':[]},'file_inventory':[]}
 v['root_sha256']=digest(v);p=tmp_path/'AR_SEEN_SOFTWARE_EXCLUSION_FIXTURE.json';p.write_text(json.dumps(v));return HistoricalSeen(p,v['root_sha256'],admission_ledger=tmp_path/'exposure.db')


def prep(tmp_path):
 a,l,s,r,_,_=inputs(tmp_path/'inputs');p=prepare_stage(a['envelope'],l,supplement=s)
 return a,l,s,r,p


def test_genuine_CSA_exact_lineage_components_and_no_scientific_promotion(tmp_path):
 a,l,s,r,p=prep(tmp_path);before=content_hash(a)
 o=assess_stage(p,r,proposal_origin='interactive_Work_source_review_not_provider_linkage_output')
 assert len(o['sidecar']['native_candidate_linkages'])==2 and o['model_proposed'] is False
 assert len(o['sidecar']['materialization_decisions'])==2
 assert all(x['status']=='rejected' for x in o['sidecar']['materialization_decisions'])
 assert all({'authority_not_validated_source_grounded','grounding_version_absent'}<=set(x['reason_codes']) for x in o['sidecar']['materialization_decisions'])
 assert o['v2_diagnostic']['original_linkage_v2']['full_machine_reuse_linkage']=='blocked_missing_factor_application'
 assert o['v2_diagnostic']['linkage_v2']['full_machine_reuse_linkage']=='complete_with_limitations'
 assert not o['scientific_authorization'] and not o['independent_scientific_authorization'] and o['materialized_links']==0
 assert content_hash(a)==before
 assert len(p['source_resolution_envelopes'])==3
 assert all(x['source_scope_completeness']=='partial' for x in p['source_resolution_envelopes'])
 spans=p['input']['evidence_spans'];caption=next(x['text'] for x in spans if 'Myofiber CSA of control' in x['text'])
 assert 'TA 7 dpi' in caption
 assert any('QuPath' in x['text'] for x in spans)
 core=a['envelope']['ExperimentalCore']
 assert all(x['source_ref']!=core['factors'][1]['identity'] for x in r['proposals']) # CTX not contrast
 assert 'unknown'==a['envelope']['ExperimentalObservationV3']['measurement']['measurement_dimension']
 assert p['lineage']['response']['sha256']=='76744536ffc57bf4b21b486069e4ecac42b2f744b4397b4bc950e335634dc070'


@pytest.mark.parametrize('fault',['no_factor','no_comparator','wrong_scope','wrong_figure','wrong_methods','unsupported','wrong_endpoint','wrong_anchor','wrong_revision','wrong_raw','wrong_hash'])
def test_source_binding_or_proposal_rejections(tmp_path,fault):
 a,l,s,r,p=prep(tmp_path)
 if fault.startswith('no_'):
  # Remove both native and supplemental evidence choices for the relevant factor.
  n=0 if fault=='no_factor' else 1
  r['proposals'][n]['evidence_refs']=[p['input']['evidence_spans'][-1]['evidence_span_id']]
  out=assess_stage(p,r,proposal_origin='test_invalid_evidence')
  assert len(out['rejected_proposals'])==1 and 'source_evidence_missing' in out['rejected_proposals'][0]['reason'];return
 if fault=='unsupported':
  r['proposals'][0]['relation_type']='causes'
  out=assess_stage(p,r,proposal_origin='test_invalid_relation');assert len(out['rejected_proposals'])==1;return
 if fault in ('wrong_endpoint','wrong_anchor'):
  r['proposals'][0]['target_ref' if fault=='wrong_endpoint' else 'evidence_refs']='OTHER' if fault=='wrong_endpoint' else ['OTHER']
  out=assess_stage(p,r,proposal_origin='test_invalid_binding');assert len(out['rejected_proposals'])==1;return
 if fault=='wrong_revision':
  r['core_revision_identity']='OTHER'
  with pytest.raises(ValueError,match='revision_binding'):assess_stage(p,r,proposal_origin='test_wrong_revision')
  return
 if fault=='wrong_raw':
  path=tmp_path/'wrong_response.json';path.write_text('{}');l['response']=pin(path)
 elif fault=='wrong_hash':l['response']['sha256']='0'*64
 else:
  binding=json.loads(Path(s['binding']['path']).read_text())
  if fault=='wrong_scope':binding['experiment_scope_identity']='OTHER'
  elif fault=='wrong_figure':binding['cross_region_applicability'][0]['explicit_xref_text']='Fig. 2C'
  else:binding['cross_region_applicability'][1]['methods_xpath']=binding['cross_region_applicability'][0]['results_xpath']
  path=tmp_path/'wrong_binding.json';path.write_text(json.dumps(binding));s['binding']=pin(path)
 with pytest.raises((ValueError,KeyError)):prepare_stage(a['envelope'],l,supplement=s)


def test_zero_proposal_diagnostic_is_not_empty_success(tmp_path):
 _,_,_,r,p=prep(tmp_path);r['proposals']=[];r['unresolved_information']=['No supported links']
 o=assess_stage(p,r,proposal_origin='software_empty_response')
 assert o['status']=='zero_accepted_candidates' and o['sidecar']['response']['unresolved_information']
 assert o['v2_diagnostic']['linkage_v2']==o['v2_diagnostic']['original_linkage_v2']


def test_actual_unified_executor_exports_CSA_provisional_decisions_and_original_evidence(tmp_path,ar_seen):
 backend,cfg,req=backend_fixture(tmp_path/'inputs')
 ex=PilotCaseExecutor(tmp_path/'cases',ar_seen,ModelBudget(tmp_path/'b.db',cfg,offline=True),backend)
 p=ex.run(req);validate_case_package(p)
 assert p['terminal_state']=='INSUFFICIENT_EVIDENCE',p['reason']
 assert p['run_manifest']['stage_contract_version']=='case_stages_v4'
 stage=next(s for s in p['run_manifest']['stages'] if s['stage']=='source_grounded_linkage');assert stage['status']=='executed'
 d=verify_dataset(tmp_path/'cases'/req['case_id']/'dataset')
 assert d['scientific_counts']['linkage_stage_inputs']==1 and d['scientific_counts']['linkage_stage_outcomes']==1
 assert d['scientific_counts']['scientific_stage_completion']==1 and d['scientific_counts']['experimental_core']==1
 assert d['pipeline_complete'] is False and not d['scientific_stage_completion']['full_L0_L6_scientific_execution']
 assert d['scientific_counts']['hypotheses']==0 and d['scientific_counts']['human_reviews']==0
 display=case_display(p);assert display['linkage_stage_count']==1
 page=scientific_page(p);assert page['total']==1
 data=json.loads(page['items'][0]['original_evidence']['utf8']);out=json.loads(page['items'][0]['candidate_decisions']['utf8'])
 assert data['input']['observation_identity']==OID and len(out['sidecar']['native_candidate_linkages'])==2
 assert not out['model_proposed'] and out['materialized_links']==0
 assert json.loads(next(a['utf8'] for a in p['artifacts'] if a['role'].endswith('/core.json')))==json.loads(json.loads((LIVE/'assessment/derived_response.json').read_text())['records'][2]['core_utf8'])
 assert len(backend.transport.calls)==2 # B/Q software stubs only; real V3 replay, no linkage dispatch


def tree(root):return {str(p.relative_to(root)):file_hash(p) for p in root.rglob('*') if p.is_file()}


def test_raw_linkage_fixture_response_reuse_no_duplicate_charge_and_immutable_revision(tmp_path,ar_seen):
 backend,cfg,req=backend_fixture(tmp_path/'inputs',provider_fixture=True)
 b=ModelBudget(tmp_path/'b.db',cfg,offline=True);cache=SourceModelCache(tmp_path/'cache')
 ex=PilotCaseExecutor(tmp_path/'cases',ar_seen,b,backend,model_cache=cache)
 one=ex.run(req);assert one['terminal_state']=='INSUFFICIENT_EVIDENCE',one['reason']
 assert len(backend.transport.calls)==3
 before=tree(tmp_path/'cases'/req['case_id']);two=ex.run({**req,'case_id':'NEW-IMMUTABLE'})
 assert len(backend.transport.calls)==3 and two['costs']['accounted_nusd']==0
 assert tree(tmp_path/'cases'/req['case_id'])==before
 assert one['costs']['accounted_nusd']>0 # simulated billing only
 assert any('source_grounded_linkage' in a['role'] and a['role'].endswith('_reuse.json') for a in two['artifacts'])
 assert len(list(cache.root.glob('raw_v1_*.json')))==3
 backend.linkage_inputs={}
 with pytest.raises(CaseIntegrity,match='input_drift'):ex.run(req)
 assert tree(tmp_path/'cases'/req['case_id'])==before
 with pytest.raises(ValueError,match='immutable_dataset'):export_attempt_dataset(one['run_manifest'],tmp_path/'cases'/req['case_id'],tmp_path/'cases'/req['case_id']/'dataset')


def test_model_unknown_failure_retained_and_never_resent(tmp_path,ar_seen):
 backend,cfg,req=backend_fixture(tmp_path/'inputs',provider_fixture=True,fail=True)
 ex=PilotCaseExecutor(tmp_path/'cases',ar_seen,ModelBudget(tmp_path/'b.db',cfg,offline=True),backend)
 one=ex.run(req);assert one['terminal_state']=='MODEL_FAILED',one['reason']
 assert len(backend.transport.calls)==3
 outcome=json.loads(next(a['utf8'] for a in one['artifacts'] if a['role'].endswith('_linkage_outcome.json')))
 assert outcome['status']=='model_failed_or_interrupted'
 assert ex.run({**req,'case_id':'NO-RESEND'})['terminal_state']=='BUDGET_STOP'
 assert len(backend.transport.calls)==3
 verify_dataset(tmp_path/'cases'/req['case_id']/'dataset')


def test_zero_link_response_through_executor(tmp_path,ar_seen):
 backend,cfg,req=backend_fixture(tmp_path/'inputs',provider_fixture=True,zero=True)
 p=PilotCaseExecutor(tmp_path/'cases',ar_seen,ModelBudget(tmp_path/'b.db',cfg,offline=True),backend).run(req)
 o=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role'].endswith('_linkage_outcome.json')))
 assert o['status']=='zero_accepted_candidates' and not o['model_proposed']


def test_isolated_Atlas_delivery_has_source_text_candidates_and_zero_reviews(tmp_path,ar_seen):
 from tests.pilot_linkage_support import atlas_delivery
 backend,cfg,req=backend_fixture(tmp_path/'inputs')
 p=PilotCaseExecutor(tmp_path/'cases',ar_seen,ModelBudget(tmp_path/'b.db',cfg,offline=True),backend).run(req)
 assert atlas_delivery(p,tmp_path/'atlas')['annotations']==0


def test_interrupted_linkage_attempt_exports_without_dispatch_retry(tmp_path,ar_seen):
 backend,cfg,req=backend_fixture(tmp_path/'inputs',provider_fixture=True)
 original=backend.transport.send
 def interrupt(provider,body):
  if 'source_grounded_linkage_candidate_prompt_v1' in body['messages'][0]['content']:raise KeyboardInterrupt('SOFTWARE crash before known outcome')
  return original(provider,body)
 backend.transport.send=interrupt
 ex=PilotCaseExecutor(tmp_path/'cases',ar_seen,ModelBudget(tmp_path/'b.db',cfg,offline=True),backend)
 with pytest.raises(KeyboardInterrupt):ex.run(req)
 sends=len(backend.transport.calls)
 p=ex.run(req);assert p['terminal_state']=='MODEL_FAILED'
 assert sends==len(backend.transport.calls)
 o=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role'].endswith('_linkage_outcome.json')))
 assert o['status']=='interrupted_outcome_unknown_no_redispatch'
 assert verify_dataset(tmp_path/'cases'/req['case_id']/'dataset')['pipeline_complete'] is False


@pytest.mark.parametrize('fault',['malformed','partial'])
def test_original_invalid_provider_fixture_response_retained(tmp_path,ar_seen,fault):
 backend,cfg,req=backend_fixture(tmp_path/'inputs',provider_fixture=True)
 original=backend.transport.send
 def invalid(provider,body):
  out=original(provider,body)
  if 'source_grounded_linkage_candidate_prompt_v1' in body['messages'][0]['content']:
   if fault=='partial':out['choices'][0]['finish_reason']='length'
   else:out['choices'][0]['message']['content']='{malformed'
  return out
 backend.transport.send=invalid
 p=PilotCaseExecutor(tmp_path/'cases',ar_seen,ModelBudget(tmp_path/'b.db',cfg,offline=True),backend).run(req)
 o=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role'].endswith('_linkage_outcome.json')))
 assert o['status']=='model_response_invalid' and o['materialized_links']==0
 assert len(backend.transport.calls)==3
