"""Isolated Atlas workflow verification; accounts/responses are engineering fixtures."""
from pathlib import Path
import json,re
from sqlalchemy import select,func
from code_engine.orchestration.pilot_delivery import case_queue_row,case_review_rows
from code_engine.system_b.persistence.services.review_service import import_review_items
from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments
from code_engine.system_b.persistence.models import Annotation,GoldRecord
from code_engine.system_b.explorer.explorer_server import create_app
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests
from tests.atlas_db_test_utils import migrate,session_for,add_user

def exercise_case_staging(packages,base:Path,*,include_pair_units=False):
 base.mkdir(parents=True,exist_ok=True);display=base/'display';display.mkdir();KnowledgeExplorerTests().fixture(display)
 queue=base/'queue';queue.mkdir();rows=[row for p in packages for row in (case_review_rows(p) if include_pair_units else [case_queue_row(p)])]
 (queue/'manual_review_queue.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
 url='sqlite:///'+str((base/'atlas_staging.db').resolve());migrate(url);Session=session_for(url)
 with Session.begin() as db:
  imported=import_review_items(db,queue,namespace='pilot',import_run_id='FOUR_BLOCKER_SOFTWARE_ACCEPTANCE')
  assert imported['review_items_inserted']==len(rows)
  owner=add_user(db,'staging_test_owner','owner');a=add_user(db,'staging_test_primary');b=add_user(db,'staging_test_secondary');adj=add_user(db,'staging_test_adjudicator','adjudicator')
  project=create_project_with_assignments(db,owner={'user_id':owner.user_id,'role':'owner','authenticated':True},name='OFFLINE CASE DELIVERY SOFTWARE ACCEPTANCE; NOT SCIENTIFIC APPROVAL',namespace='pilot',annotation_schema_version='ai_provisional_case_attempt_v2',primary_reviewer_user_id=a.user_id,secondary_reviewer_user_id=b.user_id,adjudicator_user_id=adj.user_id,item_ids=[r['review_item_id'] for r in rows])
 empty=base/'empty';empty.mkdir()
 app=create_app(display,empty,require_auth=True,secret_key='ISOLATED-OFFLINE-ACCEPTANCE-ONLY',database_url=url,require_database=True,testing=True);client=app.test_client()
 page=client.get('/login');token=re.search(r'name="csrf_token" value="([^"]+)"',page.get_data(as_text=True)).group(1)
 assert client.post('/login',data={'csrf_token':token,'username':'staging_test_primary','password':'correct horse battery staple'}).status_code==302
 with client.session_transaction() as s:csrf=s['csrf_token']
 headers={'X-CSRF-Token':csrf}
 for guideline in client.get('/api/my/onboarding').get_json()['items']:assert client.post('/api/my/onboarding/acknowledge',json=guideline,headers=headers).status_code==200
 results=[]
 for row in rows:
  p=row['review_package']
  item_id=row['review_item_id'];detail=client.get('/api/review-item/'+item_id);assert detail.status_code==200;d=detail.get_json();assert d['review_package']==p and d['form_definition']['configured']
  fields={k:'UNCERTAIN' for k in ['experimental_scope','factor_comparator','measurement_endpoint','observed_result','evidence_linkage','missing_method_limits','permissible_interpretation','alignment_context','terminal_outcome']}
  response=client.post('/api/annotation/'+item_id,json={'assignment_id':d['assignment_id'],'project_id':d['project_id'],'final_label':'UNCLEAR','structured_fields':fields,'notes':'SYNTHETIC WORKFLOW RESPONSE ONLY; NOT HUMAN SCIENTIFIC REVIEW','client_submission_id':'case-delivery-'+p['package_sha256'],'expected_revision':0},headers=headers)
  assert response.status_code==200,response.get_data(as_text=True);saved=response.get_json();assert saved['structured_fields']['package_sha256']==p['package_sha256']
  results.append({'case_id':p['case_id'],'terminal':p['terminal_state'],'item_id':item_id,'detail_display_API':True,'response_hash_bound':True,'scientific_authorization':False})
  (base/(p['case_id']+'_display.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 with Session() as db:
  count=db.scalar(select(func.count()).select_from(Annotation));gold=db.scalar(select(func.count()).select_from(GoldRecord))
 assert count==len(rows) and gold==0
 summary={'imported':len(rows),'attempts_preserved':len(packages),'review_units':len(rows),'annotations':count,'gold':gold,'real_human_reviews':0,'production_writes':0,'cases':results,'database_url':url,'reviewer_responses':'SYNTHETIC SOFTWARE WORKFLOW FIXTURES ONLY'}
 (base/'acceptance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');return summary,app
