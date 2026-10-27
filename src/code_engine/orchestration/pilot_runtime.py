"""Owner-gated runtime composition, using existing acquisition and model stages."""
from pathlib import Path
import json,time,resource
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.corpus.historical_seen import HistoricalSeen
from code_engine.acquisition.pilot_corpus import PilotCorpus
from code_engine.acquisition.pilot_ncbi import PartitionedNCBIClient
from code_engine.acquisition.pilot_source_adapter import ProspectiveSourceAcquirer,CorpusStageCatalog
from code_engine.orchestration.pilot_budget import ModelBudget
from code_engine.orchestration.pilot_backend import ExistingStagesBackend,PilotProviderTransport
from code_engine.orchestration.pilot_case import PilotCaseExecutor
from code_engine.orchestration.pilot_delivery import case_review_rows
from code_engine.system_b.annotation_schemas.registry import canonical_json


def owner_approval(manifest):
 ref=manifest.get('owner_execution_approval') or {};path=Path(ref.get('path','OWNER_APPROVAL_NOT_PROVIDED'))
 if not path.is_file() or file_hash(path)!=ref.get('sha256'):raise RuntimeError('actual_pilot_execution_not_authorized')
 approved=json.loads(path.read_text());expected=content_hash({k:v for k,v in manifest.items() if k!='owner_execution_approval'})
 if approved.get('scope')!='ten_case_pilot_execution' or approved.get('approved') is not True or approved.get('pilot_manifest_sha256')!=expected:raise RuntimeError('owner_execution_approval_not_bound')
 return approved


def retrieval_screen(request,metadata):
 # Metadata relevance is deliberately not scientific comparability. Download
 # candidate full texts so omitted abstract endpoint terms cannot silently drop
 # eligible experiments. Existing OA/source/correction gates decide access.
 return {'eligible':True,'reason':'Direction-neutral frozen-query candidate; full-text intervention/endpoint/system scope still requires source-bound assessment. Positive, negative, null and inconclusive outcomes are not selection criteria.'}


def run_owner_authorized(manifest,output,repository):
 owner_approval(manifest) # Before metadata clients, credentials or source calls.
 if manifest.get('paper_count_limit') is not None:raise ValueError('paper_count_cap_forbidden')
 root=Path(output).resolve();root.mkdir(parents=True,exist_ok=True)
 seen=HistoricalSeen(Path(manifest['historical_registry']),manifest['historical_root_sha256'],admission_ledger=root/'exposure.sqlite')
 cases=manifest['cases']
 if len(cases)!=10 or len({c['case_id'] for c in cases})!=10:raise ValueError('exact_ten_frozen_questions_required')
 for case in cases:
  if content_hash({k:v for k,v in case.items() if k!='case_design_sha256'})!=case['case_design_sha256']:raise ValueError('question_design_hash_drift')
 if manifest.get('execution_phase')=='metadata_access_inventory':
  from code_engine.acquisition.pilot_corpus import ResourcePause
  client=PartitionedNCBIClient(root/'search_partitions',execute_authorized=True)
  acquirer=ProspectiveSourceAcquirer(root/'source_work',repository=repository,execute_authorized=True)
  corpus=PilotCorpus(root/'corpus.sqlite',seen=seen,client=client,relevance=retrieval_screen,acquire=acquirer,page_size=manifest.get('page_size',100))
  start=time.monotonic();controls=manifest.get('resource_controls',{});wall=controls.get('wall_time_seconds',3600);memory=controls.get('memory_mb',4096)
  if wall<=0 or memory<=0:raise ValueError('positive_resource_controls_required')
  def available_inventory():return time.monotonic()-start<wall and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<memory*1024
  inventory=[]
  for case in cases:
   reason=None
   try:corpus.discover(case,continue_work=available_inventory);corpus.download(case['case_id'],continue_work=available_inventory)
   except ResourcePause as e:reason=str(e)
   inventory.append({'case_id':case['case_id'],'coverage':corpus.coverage(case['case_id']),'interruption':reason})
  result={'phase':'metadata_access_inventory','inventory':inventory,'scientific_completion':False,'actual_model_API_calls':0,'authorization_granted_to_later_processing':False}
  (root/'metadata_access_inventory.json').write_text(canonical_json(result)+'\n');return result
 budget=ModelBudget(root/'budget.sqlite',manifest['model_budget'],offline=False)
 for tranche in manifest.get('additional_spend_approvals',[]):budget.add_authorized_tranche(tranche)
 started=time.monotonic();controls=manifest.get('resource_controls',{});wall=controls.get('wall_time_seconds',3600);memory=controls.get('memory_mb',4096)
 if wall<=0 or memory<=0:raise ValueError('positive_resource_controls_required')
 def available():return time.monotonic()-started<wall and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss< memory*1024
 client=PartitionedNCBIClient(root/'search_partitions',execute_authorized=True)
 acquire=ProspectiveSourceAcquirer(root/'source_work',repository=repository,execute_authorized=True)
 corpus=PilotCorpus(root/'corpus.sqlite',seen=seen,client=client,relevance=retrieval_screen,acquire=acquire,page_size=manifest.get('page_size',100))
 catalog=CorpusStageCatalog(corpus,{c['case_id']:c for c in cases},execute_authorized=True,continue_work=available)
 models=manifest['model_stages'];pricing={k:budget.models[v] for k,v in models.items()}
 backend=ExistingStagesBackend(repository=repository,catalog=catalog,transport=PilotProviderTransport(execute_authorized=True),pricing=pricing,annotations=manifest.get('source_annotations'),review_prompt=manifest.get('scientific_review_prompt'))
 executor=PilotCaseExecutor(root/'cases',seen,budget,backend);packages=[]
 for case in cases:
  request={'case_id':case['case_id'],'question':case['question'],'scope':case['scope'],'evidence_mode':'authorized_new_pilot','model_stages':models}
  if manifest.get('resume_partial'):request['resume_partial']=True
  packages.append(executor.run(request))
 rows=[r for p in packages for r in case_review_rows(p)];(root/'manual_review_queue.jsonl').write_text(''.join(canonical_json(r)+'\n' for r in rows))
 return {'attempts':len(packages),'review_units':len(rows),'terminals':{p['case_id']:p['terminal_state'] for p in packages},'budget':budget.snapshot()}
