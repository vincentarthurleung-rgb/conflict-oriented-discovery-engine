"""Genuine retained CSA plus labeled software B/Q and billing fixtures, zero network."""
from copy import deepcopy
from pathlib import Path
import hashlib,json

from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.orchestration.pilot_backend import ExistingStagesBackend
from code_engine.fulltext.source_windows import construction_window
from code_engine.orchestration.pilot_replay import FrozenReplayBackend
from code_engine.system_b.annotation_schemas.registry import canonical_json
from tests.pilot_offline_support import fixture_budget
from tests.test_pilot_unlimited_integration import FrozenCatalog,SourceBoundTransport

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/'runs/20261023_code_renewed_owner_ar_only_live_v3_probe'
RELEASE=ROOT/'runs/20261026_code_post_live_v3_grounding_linkage_readiness_offline/release'
PAYLOAD=ROOT/'runs/20261022_code_recovery_batch1_dependency_probe_offline/release_probe/PMC13557098/provider_payload.json'
OID='ftl1v3_d64aa3603e90b4af68eec0e6'


def pin(path):return {'path':str(Path(path).resolve()),'sha256':file_hash(Path(path))}


def inputs(output):
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 payload=json.loads(PAYLOAD.read_text());a=json.loads((LIVE/'assessment/observations/2/assembly.json').read_text())
 record=json.loads((LIVE/'assessment/derived_response.json').read_text())['records'][2]
 catalog=json.loads((RELEASE/'source_evidence_catalog.json').read_text())
 current=json.loads((RELEASE/'CSA/candidate_input.json').read_text())
 original_binding=json.loads((RELEASE/'CSA/supplemental_source_binding_manifest.json').read_text())
 sidecar=json.loads((RELEASE/'CSA/source_review_linkage_candidates.json').read_text())
 factors=current['components']['factors'];measure=current['components']['measurements'][0]['identity']
 refs=catalog['aliases']
 binding={'schema_version':'pilot_linkage_source_applicability_binding_v1','observation_identity':OID,
  'core_revision_identity':current['core_revision_identity'],'experiment_scope_identity':current['experiment_scope_identity'],
  'catalog_sha256':file_hash(RELEASE/'source_evidence_catalog.json'),'evidence_refs':original_binding['evidence_refs'],
  'original_assessment':pin(RELEASE/'CSA/supplemental_source_binding_manifest.json'),
  'source_grounding_assessment_status':'AI_PROVISIONAL_NOT_INDEPENDENTLY_VALIDATED',
  'component_evidence':{factors[2]['identity']:[refs['S0004']],factors[0]['identity']:[refs['S0001'],refs['S0002']]},
  'cross_region_applicability':[]}
 for alias,kind in [('CAP_C','figure_caption'),('M_CSA','methods')]:
  span=catalog['spans'][refs[alias]];origin=catalog['lineage'][refs[alias]]
  use={'kind':kind,'evidence_ref':refs[alias],'span_sha256':content_hash(span),
   'experiment_scope_identity':current['experiment_scope_identity'],'measurement_identity':measure,
   'exact_applicable_text':span['text'],'support_explanation':sidecar['response']['proposals'][0]['support_explanation'],
   'assessment_origin':pin(RELEASE/'CSA/source_review_linkage_candidates.json'),
   'independently_verified':False}
  if kind=='figure_caption':use.update(results_xpath=payload['article']['sections'][6]['source_xpath'],explicit_xref_text='Fig. 1C')
  else:use['methods_xpath']=origin['source_xpath']
  binding['cross_region_applicability'].append(use)
 bpath=output/'source_applicability_binding.json';bpath.write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n')
 lineage={'response':pin(LIVE/'live/attempt_1/raw_provider_response.json'),
  'validated':pin(LIVE/'assessment/validated_formal_v3.json'),
  'hydration_context':json.loads((LIVE/'assessment/original_hydration_context.json').read_text()),
  'source_blocks':{k:v for k,v in catalog['source_blocks'].items() if k==payload['window']['window_id']},'window':payload['window']}
 supplement={'catalog':pin(RELEASE/'source_evidence_catalog.json'),'binding':pin(bpath)}
 return a,lineage,supplement,sidecar['response'],record,payload


def backend_fixture(output,*,provider_fixture=False,fail=False,zero=False):
 a,lineage,supplement,response,record,payload=inputs(output)
 paths={}
 for key,value in [('packet',record['packet_utf8']),('core',record['core_utf8']),('prompt',record['review_prompt_utf8'])]:
  path=Path(output)/(key+'.'+('txt' if key=='prompt' else 'json'));path.write_text(value);paths[key]=str(path.resolve())
 # Unused review file is required only by the old software fixture adapter.
 paths['review']=str((LIVE/'assessment/validated_formal_v3.json').resolve())
 quote=' '.join(a['envelope']['ExperimentalObservationV3']['provenance']['evidence_spans'][-1]['text'].split())
 stub={'actor_or_intervention':'Ar conditional deletion','action':'conditional deletion','relation_direction':'DECREASES',
  'response_or_endpoint':'myofiber cross-sectional area','biological_unit':'TA myofibers','species':None,
  'intrinsic_conditioning':None,'intrinsic_therapy_context':None,'intrinsic_disease_or_genotype_context':None,
  'neutral_proposition':'SOFTWARE B/Q STUB ONLY: source reports reduced myofiber cross-sectional area.',
  'construction_evidence_span':{'exact_text':quote}}
 manifest={'kind':'authentic_seen_offline_replay','sources':[{'pmcid':'PMC13557098',**paths,'stub_candidate':stub}],
  'builder_manifest':str(ROOT/'runs/20261012_code_pilot_bound_builder_v4_request_freeze_offline/builder_request_manifest.json'),
  'quality_manifest':str(ROOT/'runs/20261012_code_pilot_bound_quality_v2_request_freeze_offline/quality_request_manifest.json')}
 allpaths=[*paths.values(),manifest['builder_manifest'],manifest['quality_manifest'],payload['source_artifact']]
 manifest['pins']={p:file_hash(Path(p)) for p in allpaths}
 catalog=FrozenCatalog(manifest,output);transport=SourceBoundTransport(catalog)
 cfg=fixture_budget();deep=cfg['models'].pop('fixture');deep.update(provider='DeepSeek',model='deepseek-flash',max_output_tokens=8192)
 cfg['models']['batch']=deep
 pricing={k:deep for k in ['builder_v4','quality_v2','experimental_v3_core','source_grounded_linkage']}
 backend=ExistingStagesBackend(repository=ROOT,catalog=catalog,transport=transport,pricing=pricing,
  annotations={'PMC13557098':{k:pin(paths[k]) for k in ('packet','core','prompt')}},
  linkage_inputs={OID:supplement},linkage_replays={} if provider_fixture else {OID:pin(RELEASE/'CSA/source_review_linkage_candidates.json')})
 transport.stub=FrozenReplayBackend(manifest,deep)
 def bundle(spec):
  return {'source':spec,'token':spec['source_token'],'document':construction_window(payload['window'],spec['source_token']),
   'private_identity':{**spec['identity'],'title_1':payload['article']['title']}}
 backend.construction_bundle=bundle
 def reuse(stage,key,p):
  if stage!='experimental_v3_core':return None
  assert p['source_sha256']==payload['source_sha256']
  return {'response':{**record,'v3_lineage':lineage},'provenance':'genuine 20261023 DeepSeek response, observation 2 replay; no new extraction','cost_usd':'0'}
 backend.reuse=reuse
 send=transport.send
 def offline_send(provider,body):
  if 'source_grounded_linkage_candidate_prompt_v1' in body['messages'][0]['content']:
   transport.calls.append(('SOFTWARE_LINKAGE_TRANSPORT_FIXTURE',body['model']))
   if fail:raise TimeoutError('SOFTWARE unknown-outcome fixture; no network dispatch')
   out=deepcopy(response)
   if zero:out['proposals']=[];out['unresolved_information']=['SOFTWARE zero-link fixture']
   return {'model':body['model'],'choices':[{'finish_reason':'stop','message':{'content':canonical_json(out)}}],
           'usage':{'prompt_tokens':100,'completion_tokens':50},'fixture':'NOT_A_REAL_LINKAGE_MODEL_RESPONSE'}
  return send(provider,body)
 transport.send=offline_send
 req={'case_id':'AR-CSA-B2','question':'How does conditional Ar deletion in MuSC affect regenerating TA myofiber CSA?',
  'scope':{'component_test':'genuine retained V3 CSA; B/Q software stubs; not full-paper execution'},
  'evidence_mode':'authentic_seen_replay','model_stages':{k:'batch' for k in ['builder_v4','quality_v2','experimental_v3_core']}}
 if provider_fixture:req['model_stages']['source_grounded_linkage']='batch'
 return backend,cfg,req


def atlas_delivery(package,output):
 """Only import/read in an isolated SQLite Atlas; no annotations or approvals."""
 import re
 from sqlalchemy import select,func
 from tests.atlas_db_test_utils import migrate,session_for,add_user
 from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests
 from code_engine.system_b.persistence.services.review_service import import_review_items
 from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments
 from code_engine.system_b.persistence.models import Annotation,GoldRecord
 from code_engine.system_b.explorer.explorer_server import create_app
 from code_engine.orchestration.pilot_delivery import case_review_rows
 output=Path(output);output.mkdir(parents=True,exist_ok=True);display=output/'display';display.mkdir();KnowledgeExplorerTests().fixture(display)
 queue=output/'queue';queue.mkdir();rows=case_review_rows(package)
 (queue/'manual_review_queue.jsonl').write_text(''.join(canonical_json(r)+'\n' for r in rows))
 url='sqlite:///'+str((output/'ISOLATED_ATLAS_SOFTWARE_TEST.db').resolve());migrate(url);Session=session_for(url)
 with Session.begin() as db:
  imported=import_review_items(db,queue,namespace='pilot',import_run_id='B2_OFFLINE_NOT_SCIENTIFIC_REVIEW')
  owner=add_user(db,'b2_software_owner','owner');a=add_user(db,'b2_software_primary');b=add_user(db,'b2_software_secondary');adj=add_user(db,'b2_software_adj','adjudicator')
  create_project_with_assignments(db,owner={'user_id':owner.user_id,'role':'owner','authenticated':True},name='B2 SOFTWARE DISPLAY ACCEPTANCE ONLY',namespace='pilot',annotation_schema_version='ai_provisional_case_attempt_v2',primary_reviewer_user_id=a.user_id,secondary_reviewer_user_id=b.user_id,adjudicator_user_id=adj.user_id,item_ids=[r['review_item_id'] for r in rows])
 empty=output/'empty';empty.mkdir()
 app=create_app(display,empty,require_auth=True,secret_key='OFFLINE_SOFTWARE_TEST_ONLY',database_url=url,require_database=True,testing=True);client=app.test_client()
 page=client.get('/login');token=re.search(r'name="csrf_token" value="([^"]+)"',page.get_data(as_text=True)).group(1)
 assert client.post('/login',data={'csrf_token':token,'username':'b2_software_primary','password':'correct horse battery staple'}).status_code==302
 with client.session_transaction() as s:csrf=s['csrf_token']
 for guideline in client.get('/api/my/onboarding').get_json()['items']:assert client.post('/api/my/onboarding/acknowledge',json=guideline,headers={'X-CSRF-Token':csrf}).status_code==200
 item=rows[0]['review_item_id'];detail=client.get('/api/review-item/'+item);assert detail.status_code==200
 evidence=client.get('/api/review-item/'+item+'/scientific-page?offset=0&limit=1');assert evidence.status_code==200
 data=evidence.get_json();assert data['items'][0]['kind']=='provisional_linkage_evidence'
 assert json.loads(data['items'][0]['original_evidence']['utf8'])['input']['observation_identity']==OID
 (output/'evidence_page.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 with Session() as db:
  annotations=db.scalar(select(func.count()).select_from(Annotation));gold=db.scalar(select(func.count()).select_from(GoldRecord))
 assert annotations==gold==0
 return {'imported_software_staging_items':imported['review_items_inserted'],'authenticated_read_API':detail.status_code,'evidence_page_API':evidence.status_code,'annotations':annotations,'human_gold':gold,'production_operations':0,'scientific_authorization':False}
