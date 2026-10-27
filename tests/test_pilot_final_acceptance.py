"""Authentic SEEN packages; all reviewer submissions are isolated workflow fixtures."""
import copy
import json
import re
import socket
from pathlib import Path
import pytest
from sqlalchemy import func,select
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.discovery.pilot_acceptance import export_review_package,validate_review_package,review_queue_row,screen_existing_pair,terminal_state
from code_engine.system_b.persistence.models import Annotation,AnnotationEvent,GoldRecord
from code_engine.system_b.persistence.services.review_service import import_review_items
from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments
from code_engine.system_b.explorer.explorer_server import create_app
from tests.atlas_db_test_utils import add_user,migrate,session_for
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests

ROOT=Path(__file__).resolve().parents[1]
HIF=ROOT/'runs/20261016_code_comparable_evidence_discovery_review_integration_seen_offline'
OLD=ROOT/'runs/20261017_code_ai_first_scientific_review_shadow_seen_offline'

@pytest.fixture(autouse=True)
def offline(monkeypatch):
 def deny(*a,**kw):raise AssertionError('external_network_forbidden')
 for k in ['connect','connect_ex']:monkeypatch.setattr(socket.socket,k,deny)
 monkeypatch.setattr(socket,'create_connection',deny);monkeypatch.setattr(socket,'getaddrinfo',deny)


def authentic_package():
 pmcs=['PMC4024011','PMC7749157']
 return export_review_package('seen_acceptance_hif',
  [HIF/p/'evidence_packet.json' for p in pmcs],[OLD/p/'ai_review.json' for p in pmcs],
  [HIF/p/'v3_core_draft.json' for p in pmcs],OLD/'review_prompt_v1.txt')


def exercise_staging(package,base):
 """Real DB/HTTP workflow, synthetic accounts/response, never scientific approval."""
 base.mkdir(parents=True,exist_ok=True);display=base/'display';display.mkdir();KnowledgeExplorerTests().fixture(display)
 queue=base/'queue';queue.mkdir();row=review_queue_row(package);item_id=row['review_item_id']
 (queue/'manual_review_queue.jsonl').write_text(json.dumps(row,ensure_ascii=False)+'\n')
 url='sqlite:///'+str((base/'atlas_staging.db').resolve());migrate(url);Session=session_for(url)
 with Session.begin() as db:
  report=import_review_items(db,queue,namespace='pilot',import_run_id='ISOLATED_ACCEPTANCE_TEST')
  assert report['review_items_inserted']==1
  owner=add_user(db,'staging_test_owner','owner');a=add_user(db,'staging_test_primary');b=add_user(db,'staging_test_secondary');adj=add_user(db,'staging_test_adjudicator','adjudicator')
  setup=create_project_with_assignments(db,owner={'user_id':owner.user_id,'role':'owner','authenticated':True},name='ISOLATED SOFTWARE ACCEPTANCE; NOT SCIENTIFIC REVIEW',namespace='pilot',annotation_schema_version='ai_provisional_experimental_package_v1',primary_reviewer_user_id=a.user_id,secondary_reviewer_user_id=b.user_id,adjudicator_user_id=adj.user_id,item_ids=[item_id])
  user_id=a.user_id
 empty=base/'empty';empty.mkdir()
 app=create_app(display,empty,require_auth=True,secret_key='isolated-acceptance-test-key',database_url=url,require_database=True,testing=True)
 client=app.test_client();page=client.get('/login');token=re.search(r'name="csrf_token" value="([^"]+)"',page.get_data(as_text=True)).group(1)
 assert client.post('/login',data={'csrf_token':token,'username':'staging_test_primary','password':'correct horse battery staple'}).status_code==302
 with client.session_transaction() as s:csrf=s['csrf_token']
 headers={'X-CSRF-Token':csrf}
 for guideline in client.get('/api/my/onboarding').get_json()['items']:
  assert client.post('/api/my/onboarding/acknowledge',json=guideline,headers=headers).status_code==200
 detail=client.get('/api/review-item/'+item_id);assert detail.status_code==200;d=detail.get_json()
 assert d['review_package']['package_sha256']==package['package_sha256'];assert d['form_definition']['configured']
 fields={k:'CLARIFICATION_REQUIRED' for k in ['experimental_scope','factor_comparator','measurement_endpoint','observed_result','evidence_linkage','missing_method_limits','permissible_interpretation','alignment_context','terminal_outcome']}
 payload={'assignment_id':d['assignment_id'],'project_id':d['project_id'],'final_label':'UNCLEAR','structured_fields':fields,'notes':'SYNTHETIC WORKFLOW RESPONSE ONLY; NOT HUMAN SCIENTIFIC REVIEW','client_submission_id':'acceptance-once','expected_revision':0}
 response=client.post('/api/annotation/'+item_id,json=payload,headers=headers);assert response.status_code==200,response.get_data(as_text=True);saved=response.get_json()
 assert saved['reviewer_user_id']==user_id
 assert saved['structured_fields']['package_sha256']==package['package_sha256']
 assert client.post('/api/annotation/'+item_id,json=payload,headers=headers).status_code==403
 assert client.post('/api/annotation/'+item_id,json={**payload,'client_submission_id':'stale-again','expected_revision':0},headers=headers).status_code==403
 with Session() as db:
  count=db.scalar(select(func.count()).select_from(Annotation));events=db.scalar(select(func.count()).select_from(AnnotationEvent));gold=db.scalar(select(func.count()).select_from(GoldRecord))
  assert count==1 and events>=1 and gold==0
 (base/'display_payload.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 (base/'saved_synthetic_response.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n')
 return {'import_validated':True,'authenticated_assigned_reviewer_API_display':True,'schema_configured':True,'response_persisted':True,'response_packet_hash_bound':True,'closed_assignment_replay_rejected_without_write':True,'closed_assignment_stale_write_rejected':True,'annotations':count,'annotation_events':events,'gold':gold,'database_url':url,'synthetic_response_not_human_validation':True,'production_writes':0},app


def test_authentic_export_and_portable_validation():
 p=authentic_package();validate_review_package(p);assert p['terminal_state']=='NO_CONTRADICTION_AFTER_COMPARISON'
 assert p['alignment']['hypotheses']==[]

@pytest.mark.parametrize('field',['blob','terminal','authority','anchor'])
def test_invalid_package_cannot_import(field,tmp_path):
 p=authentic_package()
 if field=='blob':p['blobs'][0]['utf8']+='bad'
 if field=='terminal':p['terminal_state']='PROVISIONAL_CONTRADICTION'
 if field=='authority':p['scientific_authorization']=True
 if field=='anchor':
  blob=next(b for b in p['blobs'] if b['role']=='0:packet');packet=json.loads(blob['utf8']);packet['evidence_spans'][0]['text']='fabricated';blob['utf8']=json.dumps(packet)
 p['package_sha256']=content_hash({k:v for k,v in p.items() if k!='package_sha256'})
 with pytest.raises(ValueError):validate_review_package(p)


def test_existing_negative_states_do_not_promote(tmp_path):
 pmcs=['PMC4024011','PMC7749157'];packets=[HIF/p/'evidence_packet.json' for p in pmcs];reviews=[OLD/p/'ai_review.json' for p in pmcs];cores=[HIF/p/'v3_core_draft.json' for p in pmcs];prompt=OLD/'review_prompt_v1.txt'
 assert screen_existing_pair([],reviews,cores,prompt)['terminal_state']=='NOT_EVALUABLE'
 assert screen_existing_pair(packets,[],[],prompt)['terminal_state']=='INSUFFICIENT_EVIDENCE'
 assert screen_existing_pair(packets,reviews,cores,prompt)['terminal_state']=='NO_CONTRADICTION_AFTER_COMPARISON'
 with pytest.raises(ValueError):terminal_state({'alignment_status':'unexpected'})
 with pytest.raises(ValueError):terminal_state({'alignment_status':'DIRECTIONALLY_CONCORDANT','provisional_contradiction':True})


def test_staging_import_display_assignment_response(tmp_path,monkeypatch):
 monkeypatch.delenv('ATLAS_DATABASE_URL',raising=False)
 result,_=exercise_staging(authentic_package(),tmp_path/'staging')
 assert result['gold']==0 and result['response_packet_hash_bound']


def test_production_import_is_disabled(tmp_path,monkeypatch):
 monkeypatch.delenv('ATLAS_DATABASE_URL',raising=False)
 row=review_queue_row(authentic_package());(tmp_path/'manual_review_queue.jsonl').write_text(json.dumps(row)+'\n')
 with pytest.raises(ValueError,match='production_import_disabled'):import_review_items(None,tmp_path,namespace='production')


def test_synthetic_model_review_is_not_Atlas_input():
 p=authentic_package()
 for b in p['blobs']:
  if b['role']=='0:review':
   r=json.loads(b['utf8']);r['model_family']='SYNTHETIC_TEST_CONTROL';b['utf8']=json.dumps(r);import hashlib
   b['sha256']=hashlib.sha256(b['utf8'].encode()).hexdigest();p['members'][0]['hashes']['review']=b['sha256']
 p['package_sha256']=content_hash({k:v for k,v in p.items() if k!='package_sha256'})
 with pytest.raises(ValueError,match='synthetic_review_forbidden'):validate_review_package(p)


def test_export_from_noncomparable_authentic_records():
 root=ROOT/'runs/20261017_code_real_contradiction_candidate_discovery_seen_offline'
 d=[root/'reconstructions/D19'/p for p in ['PMC6787500','PMC7744182']]
 p=export_review_package('seen_acceptance_D19',[x/'evidence_packet.json' for x in d],[x/'ai_review.json' for x in d],[x/'v3_core_draft.json' for x in d],root/'shadow_review_prompt.txt')
 assert p['terminal_state']=='NOT_SUFFICIENTLY_COMPARABLE'
 assert p['alignment']['hypotheses']==[]
