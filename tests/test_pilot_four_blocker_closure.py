"""Offline release tests; stubs/costs are engineering fixtures, never science."""
import copy,json,socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from code_engine.orchestration.pilot_budget import ModelBudget,BudgetStop,cost_nusd
from code_engine.orchestration.pilot_case import PilotCaseExecutor,STAGES
from code_engine.orchestration.pilot_delivery import validate_case_package
from code_engine.corpus.historical_seen import HistoricalSeen,SeenBlocked,digest
from tests.pilot_offline_support import FrozenSourcesBackend,fixture_budget,request

@pytest.fixture(autouse=True)
def offline(monkeypatch):
 def deny(*a,**kw):raise AssertionError('network_or_paid_call_forbidden')
 for k in ['connect','connect_ex']:monkeypatch.setattr(socket.socket,k,deny)
 monkeypatch.setattr(socket,'getaddrinfo',deny);monkeypatch.setattr(socket,'create_connection',deny)

@pytest.fixture
def seen(tmp_path):
 # Isolated registry-policy fixture; NOT the certified repository release root.
 v={'schema_version':'repository_historical_seen_exclusion_v1','certified':True,'coverage':{'opaque_captures':[]},'source_identity_sets':{'pmid':['24835245','33339852'],'pmcid':['PMC4024011','PMC7749157'],'doi':['10.1000/old'],'untyped_ncbi_uid':['11111111']},'candidate_tracking':{'candidate_id':['old-candidate'],'candidate_payload_sha256':['a'*64]},'file_inventory':[]}
 v['root_sha256']=digest(v);p=tmp_path/'UNIT_TEST_ONLY_registry.json';p.write_text(json.dumps(v));return HistoricalSeen(p,v['root_sha256'])

def test_budget_concurrent_cap_and_restart(tmp_path):
 cfg=fixture_budget('0.001','0.001');cfg['models']['fixture'].update(max_input_tokens=100,max_output_tokens=100)
 b=ModelBudget(tmp_path/'budget.db',cfg,offline=True)
 def reserve(i):
  try:return b.reserve('case','stage:'+str(i),1,'fixture',100,100)
  except BudgetStop:return None
 with ThreadPoolExecutor(max_workers=12) as ex:r=list(ex.map(reserve,range(30)))
 assert sum(x is not None for x in r)==3
 assert b.snapshot()['accounted_nusd']==900000
 restarted=ModelBudget(tmp_path/'budget.db',cfg,offline=True)
 with pytest.raises(BudgetStop,match='overall_financial_cap|case_financial_cap'):restarted.reserve('case','new',1,'fixture',100,100)


def test_budget_retry_unknown_spend_and_duplicate_dispatch(tmp_path):
 cfg=fixture_budget('1','1');b=ModelBudget(tmp_path/'budget.db',cfg,offline=True)
 one=b.reserve('c','review:s',1,'fixture',100,100);b.dispatch(one)
 with pytest.raises(BudgetStop):b.dispatch(one)
 two=b.reserve('c','review:s',2,'fixture',100,100);b.dispatch(two)
 with pytest.raises(BudgetStop,match='retry_limit'):b.reserve('c','review:s',3,'fixture',100,100)
 assert b.snapshot()['accounted_nusd']==600000
 with pytest.raises(BudgetStop,match='UNVERIFIABLE_SPEND'):b.settle(two,{'provider':'bad'})
 restarted=ModelBudget(tmp_path/'budget.db',cfg,offline=True)
 with pytest.raises(BudgetStop,match='UNVERIFIABLE_SPEND'):restarted.reserve('c','different',1,'fixture',1,1)

@pytest.mark.parametrize('problem',['price','nan','model','limits','live_fixture'])
def test_unverified_budget_fails_closed(tmp_path,problem):
 cfg=fixture_budget()
 if problem=='price':cfg['models']['fixture'].pop('input_usd_per_million')
 if problem=='nan':cfg['models']['fixture']['output_usd_per_million']='NaN'
 if problem=='model':cfg['models']['fixture']['model']=''
 if problem=='limits':cfg['models']['fixture']['max_input_tokens']=False
 with pytest.raises(BudgetStop):ModelBudget(tmp_path/'budget.db',cfg,offline=problem!='live_fixture')


def test_case_unified_same_source_lineage_and_replay(tmp_path,seen):
 backend=FrozenSourcesBackend();budget=ModelBudget(tmp_path/'billing.db',fixture_budget(),offline=True)
 executor=PilotCaseExecutor(tmp_path/'cases',seen,budget,backend);r=request('authentic-case');p=executor.run(r)
 assert p['terminal_state']=='NO_CONTRADICTION_AFTER_COMPARISON',p['reason']
 assert [s['stage'] for s in p['run_manifest']['stages']]==list(STAGES)
 assert all(s['case_id']=='authentic-case' for s in p['run_manifest']['stages'])
 assert all(s['status']=='executed' for s in p['run_manifest']['stages'] if s['stage']!='hypothesis')
 assert p['pair_packages'][0]['alignment']['hypotheses']==[]
 assert len(backend.calls)==8
 projected=json.loads((tmp_path/'cases/authentic-case/projected_native_observations.json').read_text())
 assert len(projected)==2 and all(r['scientific_authorization'] is False and r['derived_causal_sign'] is None for r in projected)
 count=len(backend.calls);assert executor.run(r)['package_sha256']==p['package_sha256'];assert len(backend.calls)==count
 validate_case_package(p)

@pytest.mark.parametrize('name,count,fail,incomplete,expected',[
 ('zero',0,None,False,'NOT_EVALUABLE'),('single',1,None,False,'INSUFFICIENT_EVIDENCE'),
 ('failed',2,'builder_v4',False,'MODEL_FAILED'),('missing',2,None,True,'INSUFFICIENT_EVIDENCE')])
def test_all_failed_outcomes_are_deliverable(tmp_path,seen,name,count,fail,incomplete,expected):
 backend=FrozenSourcesBackend(fail_stage=fail,incomplete=incomplete);budget=ModelBudget(tmp_path/'billing.db',fixture_budget(),offline=True)
 p=PilotCaseExecutor(tmp_path/'cases',seen,budget,backend).run(request(name,count))
 assert p['terminal_state']==expected,p['reason'];validate_case_package(p)
 assert (tmp_path/'cases'/name/'manual_review_queue.jsonl').is_file()
 assert len(p['run_manifest']['stages'])==len(STAGES)


def test_budget_stop_case_is_deliverable(tmp_path,seen):
 b=ModelBudget(tmp_path/'billing.db',fixture_budget('0','0'),offline=True)
 p=PilotCaseExecutor(tmp_path/'cases',seen,b,FrozenSourcesBackend()).run(request('budget-stopped'))
 assert p['terminal_state']=='BUDGET_STOP';assert p['costs']['accounted_nusd']==0;validate_case_package(p)


def test_source_exclusion_and_candidate_tracking(seen):
 with pytest.raises(SeenBlocked,match='historical_source'):seen.check_source({'pmid':'24835245','pmcid':'PMC4024011','doi':'10.x/old'},binding={})
 with pytest.raises(SeenBlocked,match='identity_information'):seen.check_source({'pmid':'999'},binding={})
 with pytest.raises(SeenBlocked,match='unverifiable'):seen.check_source({'pmid':'98765432','pmcid':'PMC98765432','doi':'10.1000/new'},binding={})
 with pytest.raises(SeenBlocked,match='candidate_excluded'):seen.check_candidate('old-candidate','b'*64)
 with pytest.raises(SeenBlocked,match='historical_source'):seen.check_source({'pmid':'11111111','pmcid':'PMC11111111','doi':'10.1000/unknown'},binding={})


def test_real_pilot_cannot_consume_fixture_backend(tmp_path,seen):
 b=ModelBudget(tmp_path/'billing.db',fixture_budget(),offline=True);r=request('not-live');r['evidence_mode']='authorized_new_pilot'
 p=PilotCaseExecutor(tmp_path/'cases',seen,b,FrozenSourcesBackend()).run(r)
 assert p['terminal_state']=='INTEGRITY_FAILED' and not p['costs']['requests'];validate_case_package(p)


def test_interrupted_model_dispatch_recovers_terminal_not_paid_retry(tmp_path,seen):
 class Crash(FrozenSourcesBackend):
  def complete(self,*a,**kw):raise KeyboardInterrupt('offline crash injection')
 backend=Crash();cfg=fixture_budget();budget=ModelBudget(tmp_path/'billing.db',cfg,offline=True);executor=PilotCaseExecutor(tmp_path/'cases',seen,budget,backend);r=request('interrupted')
 with pytest.raises(KeyboardInterrupt):executor.run(r)
 reserved=budget.snapshot('interrupted')['accounted_nusd'];assert reserved>0
 restored=ModelBudget(tmp_path/'billing.db',cfg,offline=True)
 p=PilotCaseExecutor(tmp_path/'cases',seen,restored,backend).run(r)
 assert p['terminal_state']=='MODEL_FAILED';assert p['costs']['accounted_nusd']==reserved
 assert len(p['run_manifest']['stages'])==len(STAGES);validate_case_package(p)


def test_noncomparable_authentic_pair_has_honest_delivery(tmp_path,seen):
 # Extend the isolated policy fixture to the authentic D19 identities.
 seen.sources['pmcid'].update(['PMC6787500','PMC7744182'])
 backend=FrozenSourcesBackend(pair='D19');budget=ModelBudget(tmp_path/'billing.db',fixture_budget(),offline=True)
 r=request('noncomparable');r['question']='How do the specified PLAC8 and PKM2 perturbations affect E-cadherin protein abundance in their respective cell systems?'
 p=PilotCaseExecutor(tmp_path/'cases',seen,budget,backend).run(r)
 assert p['terminal_state']=='NOT_SUFFICIENTLY_COMPARABLE',p['reason'];validate_case_package(p)
 assert p['pair_packages'][0]['alignment']['hypotheses']==[]


def test_new_exposure_is_persisted_before_acquisition_and_bound_downstream(tmp_path,seen):
 seen.admission_ledger=tmp_path/'exposure.db'
 identity={'pmid':'98765432','pmcid':'PMC98765432','doi':'10.1000/new'}
 article=tmp_path/'ARTICLE_ENGINEERING_FIXTURE_NOT_SCIENCE.json';article.write_text(json.dumps(identity));import hashlib
 binding={'verified_identity':identity,'source_sha256':hashlib.sha256(article.read_bytes()).hexdigest(),'verification_basis':'verified_frozen_source_identity','article_path':str(article)}
 seen.register_exposure(identity,'first-attempt');seen.check_source(identity,binding=binding,case_id='first-attempt')
 restored=HistoricalSeen(seen.path,seen.root,admission_ledger=seen.admission_ledger)
 with pytest.raises(SeenBlocked,match='previous_attempt'):restored.register_exposure(identity,'next-attempt')
 article.write_text(json.dumps({**identity,'pmid':'98765431'}))
 with pytest.raises(SeenBlocked,match='unverifiable'):restored.check_source(identity,binding=binding,case_id='first-attempt')


def test_global_cap_across_cases_and_preexisting_reservation_after_freeze(tmp_path):
 cfg=fixture_budget('0.0006','1');b=ModelBudget(tmp_path/'b.db',cfg,offline=True)
 one=b.reserve('one','builder',1,'fixture',100,100);b.dispatch(one)
 two=b.reserve('two','review',1,'fixture',100,100)
 with pytest.raises(BudgetStop,match='overall_financial_cap'):b.reserve('three','builder',1,'fixture',1,1)
 with pytest.raises(BudgetStop,match='UNVERIFIABLE_SPEND'):b.settle(one,{'provider':'bad'})
 with pytest.raises(BudgetStop,match='UNVERIFIABLE_SPEND'):b.dispatch(two)


def test_shadow_package_cannot_manufacture_contradiction_or_formal_authority(tmp_path,seen):
 b=ModelBudget(tmp_path/'b.db',fixture_budget(),offline=True);p=PilotCaseExecutor(tmp_path/'cases',seen,b,FrozenSourcesBackend()).run(request('shadow-only'))
 from code_engine.discovery.ai_review_shadow import content_hash
 for change in ('contradiction','authorization','missing_stage','unselected_source'):
  x=copy.deepcopy(p)
  if change=='contradiction':x['terminal_state']=x['run_manifest']['terminal_state']='PROVISIONAL_CONTRADICTION'
  elif change=='authorization':x['scientific_authorization']=True
  elif change=='missing_stage':x['run_manifest']['stages'].pop()
  else:x['sources'][0]['source_sha256']='0'*64
  x['package_sha256']=content_hash({k:v for k,v in x.items() if k!='package_sha256'})
  with pytest.raises(ValueError):validate_case_package(x)
 from code_engine.fulltext.experimental_projection_handoff import prepare_experimental_handoff
 with pytest.raises(ValueError):prepare_experimental_handoff(p,tmp_path/'SHADOW_PACKAGE')


def test_all_case_terminals_import_display_and_bind_response(tmp_path,seen,monkeypatch):
 monkeypatch.delenv('ATLAS_DATABASE_URL',raising=False)
 from tests.pilot_case_staging_support import exercise_case_staging
 b=ModelBudget(tmp_path/'b.db',fixture_budget(),offline=True);ps=[]
 for name,count,fail,incomplete in [('hif',2,None,False),('zero',0,None,False),('one',1,None,False),('failed',2,'builder_v4',False),('incomplete',2,None,True)]:
  ps.append(PilotCaseExecutor(tmp_path/'cases',seen,b,FrozenSourcesBackend(fail_stage=fail,incomplete=incomplete)).run(request(name,count)))
 stopped=ModelBudget(tmp_path/'stop.db',fixture_budget('0','0'),offline=True)
 ps.append(PilotCaseExecutor(tmp_path/'cases',seen,stopped,FrozenSourcesBackend()).run(request('stopped')))
 result,_=exercise_case_staging(ps,tmp_path/'staging')
 assert result['attempts_preserved']==6 and result['gold']==0


def test_same_case_concurrent_execution_is_one_attempt(tmp_path,seen):
 b=ModelBudget(tmp_path/'b.db',fixture_budget(),offline=True);backend=FrozenSourcesBackend();ex=PilotCaseExecutor(tmp_path/'cases',seen,b,backend)
 with ThreadPoolExecutor(max_workers=4) as pool:packages=list(pool.map(lambda _:ex.run(request('one-identity')),range(4)))
 assert len({p['package_sha256'] for p in packages})==1 and len(backend.calls)==8


def test_history_freeze_covers_archives_databases_and_parseable_fixture_ids(tmp_path):
 from code_engine.corpus.historical_seen import freeze_history
 import sqlite3
 for d in ['runs/old','runs/old/local_engineering_fixtures','archived_experiments/old','data']: (tmp_path/d).mkdir(parents=True,exist_ok=True)
 (tmp_path/'runs/old/identity.json').write_text(json.dumps({'pmid':'12345678','candidate_id':'builder-old'}))
 (tmp_path/'runs/old/local_engineering_fixtures/good.json').write_text(json.dumps({'pmcid':'PMC12345678'}))
 (tmp_path/'runs/old/local_engineering_fixtures/bad.xml').write_text('<synthetic>')
 (tmp_path/'archived_experiments/old/doi.json').write_text(json.dumps({'doi':'10.1000/archive'}))
 db=sqlite3.connect(tmp_path/'data/history.db');db.execute('CREATE TABLE old (payload TEXT)');db.execute('INSERT INTO old VALUES (?)',(json.dumps({'pmid':'12345679'}),));db.commit();db.close()
 v=freeze_history(tmp_path,tmp_path/'runs/new-development/root.json')
 assert v['certified'] and '12345679' in v['source_identity_sets']['pmid']
 assert 'PMC12345678' in v['source_identity_sets']['pmcid'] and '10.1000/archive' in v['source_identity_sets']['doi']
 assert len(v['coverage']['engineering_malformed_dispositions'])==1


def test_unresolved_real_history_cannot_certify(tmp_path):
 from code_engine.corpus.historical_seen import freeze_history
 d=tmp_path/'runs/old';d.mkdir(parents=True);(d/'ledger.json').write_text(json.dumps({'pmid':'12345678','candidate_id':'old'}));(d/'partial.json').write_text('{"pmid":')
 v=freeze_history(tmp_path,tmp_path/'runs/current/root.json');assert not v['certified']
 with pytest.raises(SeenBlocked,match='not_certified'):HistoricalSeen(tmp_path/'runs/current/root.json',v['root_sha256'])


def test_unparseable_usage_freezes_other_reservations_and_fractional_caps_floor(tmp_path):
 cfg=fixture_budget();b=ModelBudget(tmp_path/'b.db',cfg,offline=True);rid=b.reserve('case','stage',1,'fixture',100,100);b.dispatch(rid)
 with pytest.raises(BudgetStop,match='UNVERIFIABLE_SPEND'):b.settle(rid,None)
 with pytest.raises(BudgetStop,match='UNVERIFIABLE_SPEND'):b.reserve('another','stage',1,'fixture',1,1)
 from code_engine.orchestration.pilot_budget import money_nusd
 assert money_nusd('0.0000000009',cap=True)==0


@pytest.mark.parametrize('cap,always_timeout,terminal',[('10',False,'MODEL_FAILED'),('0.9',False,'MODEL_FAILED'),('10',True,'MODEL_FAILED')])
def test_executor_retry_remains_inside_shared_budget(tmp_path,seen,cap,always_timeout,terminal):
 class Retry(FrozenSourcesBackend):
  timeouts=0
  def complete(self,stage,key,payload,**kw):
   if stage=='builder_v4' and key=='PMC4024011' and (always_timeout or self.timeouts==0):
    self.timeouts+=1;raise TimeoutError('OFFLINE TIMEOUT FIXTURE')
   return super().complete(stage,key,payload,**kw)
 budget=ModelBudget(tmp_path/'b.db',fixture_budget(cap,cap),offline=True);p=PilotCaseExecutor(tmp_path/'cases',seen,budget,Retry()).run(request('retry-case'))
 assert p['terminal_state']==terminal,p['reason'];validate_case_package(p)
 rows=p['costs']['requests'];assert rows and rows[0]['case_id']=='retry-case'
 unknown=[r for r in rows if r['charged'] is None];assert unknown
 assert p['costs']['accounted_nusd']<=budget.case_cap
 if terminal=='NO_CONTRADICTION_AFTER_COMPARISON':assert len(rows)==9 and len(unknown)==1
 if terminal=='BUDGET_STOP':assert len(rows)==1
 if terminal=='MODEL_FAILED':assert len(rows)==1 and 'unknown_paid_dispatch_requires_reconciliation' in p['reason']
