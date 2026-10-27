"""Bounded offline integration; synthetic transport fixtures are never science."""
import json,socket,copy,hashlib
from pathlib import Path
import pytest
from code_engine.acquisition.pilot_corpus import PilotCorpus,ResourcePause
from code_engine.orchestration.pilot_budget import ModelBudget,BudgetStop
from code_engine.orchestration.pilot_case import PilotCaseExecutor
from code_engine.orchestration.pilot_backend import ExistingStagesBackend
from code_engine.orchestration.pilot_dataset import verify_dataset
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.corpus.historical_seen import HistoricalSeen,digest
from code_engine.construction.handoff_adapter import construction
from tests.pilot_offline_support import fixture_budget,request,FrozenSourcesBackend,replay_manifest

@pytest.fixture(autouse=True)
def offline(monkeypatch):
 def deny(*a,**kw):raise AssertionError('NETWORK_OR_MODEL_FORBIDDEN')
 for n in ['connect','connect_ex']:monkeypatch.setattr(socket.socket,n,deny)
 for n in ['create_connection','getaddrinfo']:monkeypatch.setattr(socket,n,deny)

@pytest.fixture
def seen(tmp_path):
 v={'certified':True,'coverage':{'opaque_captures':[]},'source_identity_sets':{'pmid':['24835245','33339852'],'pmcid':['PMC4024011','PMC7749157'],'doi':[],'untyped_ncbi_uid':[]},'candidate_tracking':{'candidate_id':[],'candidate_payload_sha256':[]},'file_inventory':[]};v['root_sha256']=digest(v);p=tmp_path/'TEST_ONLY_EXCLUSION_ROOT.json';p.write_text(json.dumps(v));return HistoricalSeen(p,v['root_sha256'],admission_ledger=tmp_path/'new_exposure.db')

class PagedFixture:
 fixture=True
 def __init__(self,n=25):self.n=n;self.calls=[];self.fetches=0
 def search_page(self,q,*,cursor,page_size):
  self.calls.append((q['query_id'],cursor));end=min(self.n,cursor+page_size)
  return {'records':[{'pmid':str(80000000+i)} for i in range(cursor,end)],'total':self.n,'next_cursor':end if end<self.n else None}
 def metadata(self,r):
  self.fetches+=1;i=r['pmid'];return {**r,'pmcid':'PMC'+i,'doi':'10.9999/test-only-'+i,'title':'EXPLICIT SYNTHETIC PAGINATION FIXTURE NOT SCIENCE','outcome':['positive','negative','null','inconclusive'][int(i)%4]}

def corpus_request(cid='CASE'):
 return {'case_id':cid,'question':'Software paging fixture; not a scientific case','scope':{'fixture':True},'paper_count_limit':None,'inclusion_criteria':['unit fixture identity'],'exclusion_criteria':['historical identifiers'],'queries':[{'query_id':'Q1','query_string':'fixture'},{'query_id':'Q2','query_string':'fixture duplicate'}]}

def test_more_than_twelve_papers_paginate_resume_share_and_preserve_all_directions(tmp_path,seen):
 client=PagedFixture();downloads=[]
 def acquire(meta):
  downloads.append(meta['pmid']);p=tmp_path/(meta['pmid']+'.json');p.write_text(json.dumps({k:meta[k] for k in ('pmid','pmcid','doi')}));return {'status':'available','article_path':str(p),'source_sha256':file_hash(p)}
 c=PilotCorpus(tmp_path/'corpus.db',seen=seen,client=client,relevance=lambda q,m:{'eligible':True,'reason':'Explicit unit fixture; direction ignored'},acquire=acquire,page_size=7,min_interval=0)
 ticks=[0]
 def stop():ticks[0]+=1;return ticks[0]<=2
 with pytest.raises(ResourcePause):c.discover(corpus_request(),continue_work=stop)
 assert c.coverage('CASE')['partial']
 c.discover(corpus_request());assert len(client.calls)==8
 ticks[0]=0
 with pytest.raises(ResourcePause):c.download('CASE',continue_work=stop)
 assert len(downloads)==2
 c.download('CASE');one=c.coverage('CASE');assert one['search_exhausted'] and not one['partial'] and one['unique_case_papers']==25 and one['remaining_unprocessed']==0 and one['duplicate_metadata_rows']==25
 c.discover(corpus_request('SECOND'));c.download('SECOND');assert len(downloads)==25 and len(list(c.selected('SECOND')))==25
 before=len(client.calls);c.discover(corpus_request());c.download('CASE');assert len(client.calls)==before and len(downloads)==25


def test_strategy_drift_and_article_caps_rejected(tmp_path,seen):
 c=PilotCorpus(tmp_path/'c.db',seen=seen,client=PagedFixture(0),relevance=None,acquire=None,min_interval=0);r=corpus_request();c.freeze_case(r)
 with pytest.raises(ValueError,match='drift'):c.freeze_case({**r,'question':'post-hoc change'})
 with pytest.raises(ValueError,match='cap'):c.freeze_case({**r,'paper_count_limit':12})

class FrozenCatalog:
 """Actual frozen source bytes, adapted locally; no new acquisition claimed."""
 def __init__(self,manifest,root):
  self.manifest=manifest;self.root=Path(root);self.fingerprint=content_hash(manifest);self.specs=[]
  for s in manifest['sources']:
   packet=json.loads(Path(s['packet']).read_text());source=packet['source'];article=Path(source['article_path']);identity={'pmid':str(source['pmid']),'pmcid':s['pmcid'],'doi':None}
   self.specs.append({'identity':identity,'article_path':str(article),'jats_path':str(article.parent/'article.xml'),'source_token':'src_'+hashlib.sha256(('PRIVATE OFFLINE SOURCE TOKEN '+s['pmcid']).encode()).hexdigest(),'binding':{'source_sha256':file_hash(article)}})
 def select_sources(self,request):return self.specs
 def coverage(self,cid):return {'case_id':cid,'partial':False,'search_exhausted':None,'fixture_inventory_exhausted':True,'paper_count_limit':None,'sources':len(self.specs),'acquisition_execution':'frozen_local_source_replay; no new retrieval'}
 def construction_bundle(self,s):return None # BioC/ArticleJSON offline fixture, never a new-source JATS handoff.

class SourceBoundTransport:
 fixture=True
 def __init__(self,catalog):self.catalog=catalog;self.stub=FrozenSourcesBackend();self.calls=[]
 def send(self,provider,body):
  self.calls.append((provider,body['model']));user=body['messages'][-1]['content']
  if provider.casefold()=='openai':
   payload=json.loads(user);pmc=payload['packet']['source']['pmcid'];review=json.loads(self.stub.files[pmc]['review'].read_text());out={'choices':[{'message':{'content':json.dumps(review)},'finish_reason':'stop'}]}
  else:
   stage='quality_v2' if 'judgments' in body['messages'][0]['content'] or 'judgments' in user.split('\n')[-1] else 'builder_v4'
   if stage=='builder_v4':
    token=user.split('\n',1)[0].split(': ',1)[1];pmc=next(s['identity']['pmcid'] for s in self.catalog.specs if s['source_token']==token)
   else:
    packets=json.JSONDecoder().raw_decode(user)[0]
    from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import candidate_id
    chosen=next(s for s in self.catalog.specs if candidate_id(s['source_token'],self.stub.candidate(s['identity']['pmcid']))==packets[0]['candidate_id'])
    pmc=chosen['identity']['pmcid'];self.stub._tokens[pmc]=chosen['source_token']
   out,_=self.stub.complete(stage,pmc,body,provider=provider,model=body['model'],max_output_tokens=body['max_tokens'])
  out.update(model=body['model'],usage={'prompt_tokens':100,'completion_tokens':50});return out
 def _candidate_matches(self,key,token,packets):
  from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import candidate_id
  return candidate_id(token,self.stub.candidate(key))==packets[0]['candidate_id']

def existing_backend(tmp_path):
 manifest=replay_manifest();catalog=FrozenCatalog(manifest,tmp_path);transport=SourceBoundTransport(catalog)
 cfg=fixture_budget('20','10');deep=cfg['models'].pop('fixture');deep.update(provider='DeepSeek',model='deepseek-flash',input_usd_per_million='0.30',output_usd_per_million='1.20');cfg['models']['batch']=deep;cfg['models']['review']={**deep,'provider':'OpenAI','model':'gpt-offline-review-replay'}
 annotations={s['pmcid']:{k:{'path':s[k],'sha256':manifest['pins'][s[k]]} for k in ('packet','core','prompt')} for s in manifest['sources']}
 pricing={k:cfg['models']['review' if k=='ai_review' else 'batch'] for k in ['builder_v4','quality_v2','experimental_v3_core','ai_review']}
 backend=ExistingStagesBackend(repository=Path.cwd(),catalog=catalog,transport=transport,pricing=pricing,annotations=annotations)
 return backend,cfg

def test_concrete_backend_native_dataset_and_cross_case_paid_reuse(tmp_path,seen):
 backend,cfg=existing_backend(tmp_path);b=ModelBudget(tmp_path/'budget.db',cfg,offline=True);ex=PilotCaseExecutor(tmp_path/'cases',seen,b,backend)
 req=request('AUTHENTIC');req.pop('source_count');req['model_stages']={k:'review' if k=='ai_review' else 'batch' for k in req['model_stages']}
 p=ex.run(req);assert p['terminal_state']=='NO_CONTRADICTION_AFTER_COMPARISON',p['reason'];assert len(backend.transport.calls)==6
 dataset=verify_dataset(tmp_path/'cases/AUTHENTIC/dataset');assert dataset['scientific_counts']['experimental_observations']==2 and dataset['scientific_counts']['experimental_core']==2;assert not dataset['scientific_authorization'] and not dataset['licensing']['public_release_authorized']
 before=len(backend.transport.calls);req['case_id']='SECOND';two=ex.run(req);assert two['terminal_state']==p['terminal_state'];assert len(backend.transport.calls)==before and two['costs']['accounted_nusd']==0


def test_budget_pause_resume_keeps_case_and_cumulative_usage(tmp_path,seen):
 backend,cfg=existing_backend(tmp_path);cfg['case_cap_usd']='0';cfg['total_cap_usd']='0';b=ModelBudget(tmp_path/'budget.db',cfg,offline=True);ex=PilotCaseExecutor(tmp_path/'cases',seen,b,backend)
 r=request('RESUME');r.pop('source_count');r['model_stages']={k:'review' if k=='ai_review' else 'batch' for k in r['model_stages']}
 stopped=ex.run(r);assert stopped['terminal_state']=='BUDGET_STOP';verify_dataset(tmp_path/'cases/RESUME/dataset')
 approval={'scope':'pilot_model_spend_extension','budget_config_sha256':b.fingerprint,'offline_fixture':True,'total_increase_usd':'20','case_increases_usd':{'RESUME':'10'}}
 b.add_authorized_tranche(approval);b.add_authorized_tranche(approval);assert len(b.snapshot()['funding_tranches'])==1
 resumed=ex.run({**r,'resume_partial':True});assert resumed['case_id']=='RESUME' and resumed['terminal_state']=='NO_CONTRADICTION_AFTER_COMPARISON',resumed['reason'];assert b.snapshot('RESUME')['accounted_nusd']>0
 assert json.loads((tmp_path/'cases/RESUME/review_package.json').read_text())['terminal_state']=='BUDGET_STOP'


def test_actual_prospective_journal_and_verified_handoff_with_authentic_frozen_bytes(tmp_path):
 from code_engine.acquisition.pilot_source_adapter import ProspectiveSourceAcquirer
 from tests.test_prospective_acquisition_integration_offline import SyntheticTransport
 base=Path('runs/20261012_search_plan_v24_dev_alpha3_22f_first_controlled_live_pilot')
 meta=json.loads((base/'frozen_source.json').read_text());index=json.loads((base/'journal/evidence_index.json').read_text())
 gate_paths=[Path(a['gates']['artifact_path']) for a in index['attempts'] if a.get('gates')]
 jats=json.loads((base/'journal/handoff.json').read_text())['sources'][0]['raw_artifact']['artifact_path']
 # Reuse exact historic OA response as well as exact JATS bytes. No constructed
 # positive OA assertion or new source response is inserted.
 oa=next(a for a in index['attempts'] if a['request_id'].endswith(':OA'))
 oa_gate=json.loads(Path(oa['gates']['artifact_path']).read_text());raw_oa=Path(oa_gate['raw_artifact']['artifact_path']).read_bytes()
 transport=SyntheticTransport([raw_oa,Path(jats).read_bytes()]);acquirer=ProspectiveSourceAcquirer(tmp_path/'acq',repository=Path.cwd(),transport=transport)
 result=acquirer(meta);assert result['status']=='available';assert result['acquisition_execution']=='offline_frozen_transport_replay';assert transport.calls==2
 ref=result['construction_envelope'];envelope=json.loads(Path(ref['path']).read_text());assert file_hash(Path(ref['path']))==ref['sha256'];assert envelope['construction_document']['body_text']
 assert not envelope['builder_or_quality_result']
 again=acquirer(meta);assert transport.calls==2 and again['source_sha256']==result['source_sha256']


def test_ten_questions_compiled_without_equivalence_or_direction_fabrication():
 from code_engine.orchestration.pilot_case_selection import frozen_cases
 cases=frozen_cases();assert len(cases)==10 and len({c['case_id'] for c in cases})==10
 assert all(c['paper_count_limit'] is None and not c['execution_authorized'] and not c['replace_after_observing_results'] for c in cases)
 assert all(c['scope']['direction']=='unrestricted' for c in cases)
 assert all(not c['validated_search_plan']['canonical_proposition']['target_payload']['external_canonical_identity_asserted'] for c in cases)


def test_service_partition_has_no_global_ten_thousand_record_ceiling(tmp_path):
 from code_engine.acquisition.pilot_ncbi import PartitionedNCBIClient
 from datetime import date
 import re
 class Fixture(PartitionedNCBIClient):
  fixture=True
  def __init__(self,root):super().__init__(root,sleep=lambda _:None);self.counts=0
  def matching(self,term):
   data=[(date(2020,1,1),7500,0),(date(2025,1,1),7501,7500)]
   for op,lo,hi in re.findall(r'(AND|NOT) \((\d{4}/\d{2}/\d{2}):(\d{4}/\d{2}/\d{2})\[edat\]\)',term):
    start=date(*map(int,lo.split('/')));end=date(*map(int,hi.split('/')));data=[x for x in data if (start<=x[0]<=end)==(op=='AND')]
   return [str(i) for _,n,start in data for i in range(start,start+n)]
  def _count(self,term,source):self.counts+=1;return len(self.matching(term))
  def _request(self,p):
   ids=self.matching(p['term']);start=p.get('retstart',0);return {'count':len(ids),'idlist':ids[start:start+p['retmax']]}
 q={'query_id':'SOFTWARE-FIXTURE','query_string':'EXPLICIT SYNTHETIC METADATA PAGINATION NOT LITERATURE','source':'pubmed'};c=Fixture(tmp_path/'state');cursor=0;found=[]
 while True:
  page=c.search_page(q,cursor=cursor,page_size=1000);found.extend(x['pmid'] for x in page['records'])
  if page['next_cursor'] is None:break
  cursor=page['next_cursor']
 assert len(found)==len(set(found))==15001
 restored=Fixture(tmp_path/'state');restored.search_page(q,cursor=0,page_size=1);assert restored.counts==0


def test_dataset_integrity_failure_and_authority_isolation(tmp_path,seen):
 backend,cfg=existing_backend(tmp_path);b=ModelBudget(tmp_path/'b.db',cfg,offline=True);r=request('DATASET');r.pop('source_count');r['model_stages']={s:'review' if s=='ai_review' else 'batch' for s in r['model_stages']}
 p=PilotCaseExecutor(tmp_path/'cases',seen,b,backend).run(r);d=tmp_path/'cases/DATASET/dataset';v=verify_dataset(d)
 assert v['scientific_counts']['evidence_projection']==2 and v['scientific_counts']['human_reviews']==0
 assert not v['human_gold'] and not v['strict_core_eligible']
 (d/'hypotheses.jsonl').write_text('{"fabricated":true}\n')
 with pytest.raises(ValueError,match='integrity'):verify_dataset(d)


def test_gpt_and_paid_transport_not_implicitly_authorized():
 from code_engine.orchestration.pilot_backend import PilotProviderTransport
 with pytest.raises(RuntimeError,match='not_authorized'):PilotProviderTransport().send('DeepSeek',{})


def test_automatic_draft_hydration_does_not_fake_complete_core(tmp_path,seen):
 from code_engine.schemas.fulltext_observation_draft import fulltext_l1_draft_prompt_examples
 backend,cfg=existing_backend(tmp_path);original=backend.transport.send;empty_calls=[]
 def respond(provider,body):
  if len(body['messages'])==1:
   empty_calls.append(1)
   empty,_=fulltext_l1_draft_prompt_examples();return {'model':body['model'],'usage':{'prompt_tokens':100,'completion_tokens':50},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(empty)}}]}
  return original(provider,body)
 backend.transport.send=respond;backend.annotations={};b=ModelBudget(tmp_path/'b.db',cfg,offline=True);r=request('CORE-MISSING');r.pop('source_count');r['model_stages']={s:'review' if s=='ai_review' else 'batch' for s in r['model_stages']}
 # The old test sent an entire paper through the V3 component adapter, bypassing
 # its frozen input preflight. That path must now stop before any V3 dispatch.
 p=PilotCaseExecutor(tmp_path/'cases',seen,b,backend).run(r);assert p['terminal_state']=='INTEGRITY_FAILED',p['reason']
 assert 'frozen_V3_preflight' in p['reason'] and not empty_calls
 v=verify_dataset(tmp_path/'cases/CORE-MISSING/dataset');assert v['scientific_counts']['experimental_core']==0
 # Retain the original empty-hydration assertion using an authentic bounded
 # Results window. This is a software transport fixture, not extracted evidence.
 from tests.test_fulltext_window_core_integration import ar_view
 from code_engine.fulltext.source_windows import grouped_plan_windows
 article=ar_view();source=tmp_path/'AR_view.json';source.write_text(json.dumps(article))
 window=next(w for w in grouped_plan_windows(article,file_hash(source))['windows'] if w['section_title'].startswith('results'))
 out,_=backend.complete('experimental_v3_core',article['pmcid'],{'article':article,'window':window,'source_sha256':file_hash(source),'source_artifact':str(source)},provider='deepseek',model='deepseek-flash',max_output_tokens=32768)
 assert out['records']==[] and out['incomplete']['formal_v3']['experimental_observations']==[] and len(empty_calls)==1


def test_owner_execution_gate_blocks_before_any_source_call(tmp_path):
 from code_engine.orchestration.pilot_runtime import run_owner_authorized
 with pytest.raises(RuntimeError,match='not_authorized'):run_owner_authorized({'paper_count_limit':None},tmp_path,Path.cwd())


def test_pubmed_pilot_metadata_preserves_existing_correction_contract():
 from code_engine.acquisition.literature_search import NCBILiteratureClient
 class Fixture(NCBILiteratureClient):
  def fetch(self,record,source):
   assert source=='pubmed' and record.get('pmid')=='12345678' and not record.get('pmcid')
   return '<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345678</PMID><Article><ArticleTitle>SOFTWARE FIXTURE</ArticleTitle><PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList></Article><CommentsCorrectionsList><CommentsCorrections RefType="RetractionIn"><RefSource>Source</RefSource><PMID>12345679</PMID></CommentsCorrections></CommentsCorrectionsList></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="pubmed">12345678</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>'
 m=Fixture().metadata({'pmid':'12345678','pmcid':'PMC12345678'})
 assert m['correction_relationships']==[{'ref_type':'RetractionIn','linked_pmid':'12345679','ref_source':'Source'}]


def test_dataset_reexport_is_reproducible(tmp_path,seen):
 from code_engine.orchestration.pilot_dataset import export_attempt_dataset
 backend,cfg=existing_backend(tmp_path);b=ModelBudget(tmp_path/'b.db',cfg,offline=True);r=request('REEXPORT');r.pop('source_count');r['model_stages']={s:'review' if s=='ai_review' else 'batch' for s in r['model_stages']}
 p=PilotCaseExecutor(tmp_path/'cases',seen,b,backend).run(r);case=tmp_path/'cases/REEXPORT';original=verify_dataset(case/'dataset');again=export_attempt_dataset(p['run_manifest'],case,tmp_path/'reexport',pairs=p['pair_packages'])
 assert original['dataset_version']==again['dataset_version']


def test_atlas_paginated_evidence_review_controls_and_owner_export(tmp_path,seen,monkeypatch):
 import re
 from tests.pilot_case_staging_support import exercise_case_staging
 from code_engine.orchestration.pilot_delivery import case_review_rows
 from code_engine.orchestration.pilot_dataset import atlas_review_records,export_attempt_dataset
 from code_engine.system_b.persistence.models import EvaluationProject,GoldRecord
 from sqlalchemy import select,func
 from tests.atlas_db_test_utils import session_for
 monkeypatch.delenv('ATLAS_DATABASE_URL',raising=False)
 backend,cfg=existing_backend(tmp_path);b=ModelBudget(tmp_path/'b.db',cfg,offline=True);r=request('ATLAS-UX');r.pop('source_count');r['model_stages']={s:'review' if s=='ai_review' else 'batch' for s in r['model_stages']}
 p=PilotCaseExecutor(tmp_path/'cases',seen,b,backend).run(r)
 result,app=exercise_case_staging([p],tmp_path/'staging',include_pair_units=True)
 assert result['imported']==2 and result['attempts_preserved']==1 and result['gold']==0
 def login(user):
  c=app.test_client();page=c.get('/login');csrf=re.search(r'name="csrf_token" value="([^"]+)"',page.get_data(as_text=True)).group(1)
  assert c.post('/login',data={'csrf_token':csrf,'username':user,'password':'correct horse battery staple'}).status_code==302
  return c
 reviewer=login('staging_test_primary');rows=reviewer.get('/api/review-items?limit=1').get_json();assert rows['has_more'] and len(rows['items'])==1 and 'review_package' not in rows['items'][0]
 second=reviewer.get('/api/review-items?limit=1&offset=1').get_json();assert not second['has_more'] and second['items'][0]['review_item_id']!=rows['items'][0]['review_item_id']
 item=case_review_rows(p)[0]['review_item_id'];d=reviewer.get('/api/review-item/'+item+'?presentation=summary').get_json();assert d['review_package']['pair_count']==1 and not d['review_package']['pair_packages']
 assert d['annotation']['notes'].startswith('SYNTHETIC')
 page=reviewer.get('/api/review-item/'+item+'/scientific-page?limit=1').get_json();assert page['total']==1 and len(page['items'])==1 and all(not x['role'].endswith(':source') for x in page['items'][0]['blobs'])
 assert reviewer.get('/api/review-item/'+item+'/scientific-page?limit=4').status_code==400
 assert reviewer.get('/api/owner/pilot-reviews/export').status_code==403
 owner=login('staging_test_owner');Session=session_for(result['database_url'])
 with Session() as db:project=db.scalar(select(EvaluationProject.project_id).where(EvaluationProject.name.like('OFFLINE CASE%')))
 pages=[]
 for offset in [0,1]:
  response=owner.get('/api/owner/pilot-reviews/export?project_id='+project+'&limit=1&offset='+str(offset));assert response.status_code==200,response.get_data(as_text=True);pages.append(response.get_json())
 assert pages[0]['has_more'] and not pages[1]['has_more'] and len([r for page in pages for r in page['items']])==2
 records=atlas_review_records({'pages':pages},p);assert len(records)==2 and all(not r['scientific_authorization'] and not r['human_gold'] for r in records)
 exported=export_attempt_dataset(p['run_manifest'],tmp_path/'cases/ATLAS-UX',tmp_path/'reviewed_dataset',pairs=p['pair_packages'],human_reviews=records)
 assert exported['scientific_counts']['workflow_fixture_reviews']==2 and exported['scientific_counts']['human_reviews']==0
 with Session() as db:assert db.scalar(select(func.count()).select_from(GoldRecord))==0


def test_separate_inventory_phase_needs_no_paid_model_configuration(tmp_path,seen,monkeypatch):
 from code_engine.orchestration import pilot_runtime as runtime
 from code_engine.orchestration.pilot_case_selection import frozen_cases
 class EmptyClient:
  fixture=True
  def __init__(self,*a,**kw):pass
  def search_page(self,q,*,cursor,page_size):return {'records':[],'total':0,'next_cursor':None}
 class FastCorpus(PilotCorpus):
  def __init__(self,*a,**kw):super().__init__(*a,**kw,min_interval=0)
 monkeypatch.setattr(runtime,'owner_approval',lambda m:{'explicit_test_only':True})
 monkeypatch.setattr(runtime,'PartitionedNCBIClient',EmptyClient);monkeypatch.setattr(runtime,'PilotCorpus',FastCorpus)
 def no_budget(*a,**kw):raise AssertionError('Inventory cannot construct model budget or invoke model')
 monkeypatch.setattr(runtime,'ModelBudget',no_budget)
 m={'execution_phase':'metadata_access_inventory','paper_count_limit':None,'historical_registry':str(seen.path),'historical_root_sha256':seen.root,'cases':frozen_cases()}
 result=runtime.run_owner_authorized(m,tmp_path/'inventory',Path.cwd())
 assert result['actual_model_API_calls']==0 and len(result['inventory'])==10 and not result['scientific_completion']
 assert all(x['coverage']['queries'] and x['coverage']['search_exhausted'] for x in result['inventory'])
