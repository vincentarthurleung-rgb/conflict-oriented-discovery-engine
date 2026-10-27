"""B3 scientific applicability and actual-executor regressions, offline only."""
from pathlib import Path
from copy import deepcopy
import json
import pytest
from code_engine.discovery.ai_review_shadow import file_hash,content_hash
from code_engine.orchestration.pilot_inclusion import InclusionLedger,frozen_intake,input_identity,question_identity
from code_engine.orchestration.pilot_case import PilotCaseExecutor,CaseIntegrity
from code_engine.orchestration.pilot_budget import ModelBudget
from code_engine.orchestration.pilot_dataset import verify_dataset
from code_engine.corpus.historical_seen import HistoricalSeen
from code_engine.system_b.persistence.services.pilot_review_display import case_display
from tests.pilot_inclusion_support import ar_case,hif_case,trib_case,bind_assessments,assessment,write,HIF_INTAKE,E,R,pin
from tests.test_pilot_unlimited_integration import offline


def seen():
 p=R/'runs/20261018_code_unlimited_corpus_pipeline_dataset_atlas_offline/historical_seen_root.json'
 return HistoricalSeen(p,'36093a1b0aabdfd37a9ef022f51ccdbfcdfcfcc152c13328268cac9c7ddd3b2a')

@pytest.mark.parametrize('which,func,native',[('AR',ar_case,5),('HIF',hif_case,2),('TRIB3',trib_case,0)])
def test_authentic_actual_executor_source_scope_and_provisional_dataset(tmp_path,which,func,native):
 b,cfg,req=func(tmp_path/'inputs');p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.sqlite',cfg,offline=True),b).run(req)
 assert p['terminal_state']=='NOT_EVALUABLE',p['reason']
 m=p['run_manifest'];assert m['stage_contract_version']=='case_stages_v4'
 data=verify_dataset(tmp_path/'cases'/req['case_id']/'dataset')
 assert data['scientific_counts']['experimental_core']==native
 assert data['scientific_counts']['scientific_inclusion']>0 and not data['pipeline_complete']
 assert m['scientific_inclusion_summary']['real_model_dispatches_this_attempt']==0
 assert data['scientific_counts']['ai_scientific_reviews']==0
 rows=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role']=='scientific_inclusion_final.json'))['rows']
 assert all(r['scientific_authorization'] is False for r in rows)
 assert all(r['decision']=='INCLUDED' for r in rows if r['scope_level']=='paper')
 if which=='AR':
  obs=[r for r in rows if r['scope_level']=='observation'];assert len(obs)==5
  assert sorted(r['decision'] for r in obs)==['EXCLUDED','EXCLUDED','EXCLUDED','INCLUDED','UNCERTAIN']
  csa=next(r for r in obs if r['decision']=='INCLUDED');assert csa['context_semantics']['shared_condition'].startswith('CTX')
  assert 'single-myofiber' in csa['context_semantics']['measurement'] and csa['context_semantics']['time'].startswith('7 dpi')
  assert m['scientific_inclusion_summary']['native_records_excluded_from_downstream']==3
 elif which=='TRIB3':
  obs=next(r for r in rows if r['scope_level']=='observation')
  assert obs['context_semantics']['factor_semantics'].startswith('observational biomarker')
  assert 'unknown' in obs['context_semantics']['native_V3_design_normalization']
  assert data['scientific_counts']['experimental_observations']==0 # no fake projection-hash V3
 else:
  assert m['semantic_intake_trace']['historical_semantic_mode']=='llm_semantic'
  assert m['semantic_intake_trace']['search_plan_status']=='FROZEN_VALIDATED_REUSE'
  assert m['semantic_intake_trace']['current_model_API_calls']==0
  assert m['scientific_inclusion_summary']['observation_decisions']=={'INCLUDED':2,'EXCLUDED':1}
  inventories=[json.loads(a['utf8']) for a in p['artifacts'] if a['role'].endswith('_paper_design_routing.json')]
  assert any(x['mixed_design'] for x in inventories)
 display=case_display(p);assert display['scientific_inclusion_artifacts'] and display['scientific_inclusion_summary']


def null_input(tmp_path):
 packet=json.loads((E/'E1/left/evidence_packet.json').read_text());source={'identity':{k:packet['source'].get(k) for k in ('pmid','pmcid','doi')},'article_path':packet['source']['article_path'],'binding':{'source_sha256':packet['source']['article_sha256']}}
 req={'case_id':'NULL-VEGF','question':'Does reduced oxygen alter VEGF transcript abundance in HCT116 cells?','scope':{'intervention':'5% versus 20% O2','endpoint':'VEGF transcript abundance','biological_system':'HCT116 cells'}}
 vals={k:('SUPPORTED',v) for k,v in req['scope'].items()};row=assessment(req,source,'observation','source_evidence_packet:'+file_hash(E/'E1/left/evidence_packet.json'),packet['evidence_spans'],vals,context={'source_outcome':'No significant VEGF mRNA difference; caption P=0.7 (ns)','null_does_not_prove_equivalence':True})
 path=bind_assessments(req,[row],tmp_path/'assessment.json');return req,source,row,path


def test_authentic_null_mRNA_included_for_its_own_endpoint_not_equivalence(tmp_path):
 req,source,row,path=null_input(tmp_path);out=InclusionLedger(req).decide(source,scope_level='observation',scope_identity=row['scope_identity'])
 assert out['decision']=='INCLUDED' and out['context_semantics']['null_does_not_prove_equivalence']
 assert any('0.7' in s['text'] and '(ns)' in s['text'] for s in out['evidence_spans'])


@pytest.mark.parametrize('outcome',['negative','null','nonsignificant','unexpected','contradictory','missing_effect_size','unknown_canonical_identity'])
def test_direction_and_identity_neutrality_explicit_SOFTWARE_variants(tmp_path,outcome):
 req,source,row,path=null_input(tmp_path);row['context_semantics']={'SOFTWARE_OUTCOME_VARIANT_NOT_NEW_BIOMEDICAL_EVIDENCE':outcome}
 bind_assessments(req,[row],path);out=InclusionLedger(req).decide(source,scope_level='observation',scope_identity=row['scope_identity']);assert out['decision']=='INCLUDED'


def test_source_unavailable_or_failed_is_not_scientifically_excluded(tmp_path):
 req,source,row,path=null_input(tmp_path)
 for state in ('unavailable','failed','pending','not_yet_assessed'):
  x=deepcopy(source);x['article_path']=None;x['access_state']=state
  out=InclusionLedger(req).decide(x,scope_level='observation',scope_identity=row['scope_identity'])
  assert out['decision']=='UNCERTAIN' and out['assessment_state']=='ACCESS_BLOCKED' and out['source_access_state']==state


@pytest.mark.parametrize('invalid',['hash','coordinate','question','scope','dimension'])
def test_invalid_or_wrong_scope_decisions_fail_reviewably(tmp_path,invalid):
 req,source,row,path=null_input(tmp_path)
 if invalid=='hash':source['binding']['source_sha256']='0'*64
 elif invalid=='coordinate':row['evidence_spans'][0]['char_start']+=1
 elif invalid=='question':req['question']='A different question'
 elif invalid=='scope':row['scope_identity']='different scope'
 elif invalid=='dimension':row['dimension_assessments'][0]['dimension']='desired_contradiction_direction'
 if invalid!='question':bind_assessments(req,[row],path)
 out=InclusionLedger(req).decide(source,scope_level='observation',scope_identity='source_evidence_packet:'+file_hash(E/'E1/left/evidence_packet.json'))
 assert out['decision']=='UNCERTAIN'


def test_missing_malformed_or_question_mismatched_intake_degrades_no_model(tmp_path):
 req={'case_id':'INTAKE','question':'A different scientific question','scope':{}}
 assert frozen_intake(req)[1]['state']=='DEGRADED_ABSENT'
 req['frozen_semantic_intake']=pin(HIF_INTAKE);assert frozen_intake(req)[1]['state']=='DEGRADED_INVALID_OR_INCOMPATIBLE'
 malformed=tmp_path/'malformed.json';malformed.write_text('{broken');req['frozen_semantic_intake']=pin(malformed)
 parsed,trace=frozen_intake(req);assert trace['state']=='DEGRADED_INVALID_OR_INCOMPATIBLE' and parsed['semantic_mode']=='deterministic_degraded' and trace['current_model_API_calls']==0


def test_actual_input_content_drift_invalidates_package_but_keeps_exact_raw_cache(tmp_path):
 b,cfg,req=hif_case(tmp_path/'inputs');copy=tmp_path/'intake.json';copy.write_bytes(HIF_INTAKE.read_bytes());req['frozen_semantic_intake']=pin(copy)
 budget=ModelBudget(tmp_path/'b.sqlite',cfg,offline=True);ex=PilotCaseExecutor(tmp_path/'cases',seen(),budget,b)
 old=ex.run(req);first=len(b.transport.calls);snapshot={a['role']:a['sha256'] for a in old['artifacts']};identity=input_identity(req)
 copy.write_bytes(copy.read_bytes()+b'\n');assert input_identity(req)!=identity
 with pytest.raises(CaseIntegrity,match='input_drift'):ex.run(req)
 req['frozen_semantic_intake']=pin(copy);req['case_id']='NEW-INTAKE-REVISION'
 # Old decision file is now incompatible by case identity, and remains UNCERTAIN.
 new=ex.run(req);assert len(b.transport.calls)==first and new['costs']['accounted_nusd']==0
 assert {a['role']:a['sha256'] for a in old['artifacts']}==snapshot
 assert new['run_manifest']['effective_inclusion_inputs_sha256']!=old['run_manifest']['effective_inclusion_inputs_sha256']


def test_zero_Builder_output_leaves_source_relevance_unknown_not_excluded(tmp_path):
 b,cfg,req=hif_case(tmp_path/'inputs');send=b.transport.send
 def empty(provider,body):
  raw=send(provider,body)
  if provider.casefold()=='deepseek':
   parsed=json.loads(raw['choices'][0]['message']['content'])
   if 'candidates' in parsed:parsed['candidates']=[];raw['choices'][0]['message']['content']=json.dumps(parsed)
  return raw
 b.transport.send=empty
 p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.sqlite',cfg,offline=True),b).run(req)
 assert p['reason']=='NO_QUALITY_ELIGIBLE_CLAIMS'
 cov=p['run_manifest']['scientific_inclusion_summary'];assert cov['paper_decisions']=={'INCLUDED':2}
 assert cov['native_records_retained']==0 and not cov['zero_Builder_candidates_imply_zero_relevant_observations']


def test_no_fulltext_in_actual_executor_retains_unavailable_unknown_scope(tmp_path):
 b,cfg,req=hif_case(tmp_path/'inputs');meta=b.catalog.specs[0]['identity'];b.catalog.specs=[]
 b.coverage=lambda cid:{'case_id':cid,'partial':False,'retrieved_metadata_rows':1,'unique_case_papers':1,'duplicate_metadata_rows':0,'papers':[{'metadata':{**meta,'software_fixture':'simulated access failure, not an authentic new paper'},'status':'unavailable','decision':'eligible','reason':'SOFTWARE ACCESS FAILURE FIXTURE'}]}
 p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.sqlite',cfg,offline=True),b).run(req)
 rows=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role']=='scientific_inclusion_final.json'))['rows']
 assert len(rows)==1 and rows[0]['source_access_state']=='unavailable' and rows[0]['decision']=='UNCERTAIN'
 assert rows[0]['retrieval_eligibility']=='eligible' and not rows[0]['downstream_processing_permitted']


def test_PMID_only_unavailable_sources_keep_independent_denominator(tmp_path):
 b,cfg,req=hif_case(tmp_path/'inputs');b.catalog.specs=[]
 b.coverage=lambda cid:{'case_id':cid,'partial':False,'papers':[{'metadata':{'pmid':pmid,'pmcid':None,'doi':None,'SOFTWARE_METADATA_ONLY':True},'status':'unavailable','decision':'eligible'} for pmid in ('11111111','22222222')]}
 p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.sqlite',cfg,offline=True),b).run(req)
 assert p['run_manifest']['scientific_inclusion_summary']['source_access_states']=={'unavailable':2}


def test_real_window_accounting_distinguishes_exclusion_from_processing(tmp_path):
 b,cfg,req=hif_case(tmp_path/'inputs')
 req['question']='SOFTWARE ACCOUNTING FIXTURE ONLY: an intentionally incompatible endpoint'
 req['scope']={'endpoint':'SOFTWARE_INCOMPATIBLE_ENDPOINT_NOT_BIOMEDICAL_EVIDENCE'}
 req.pop('frozen_semantic_intake');req.pop('frozen_search_plan')
 rows=[]
 for s in b.catalog.specs:
  article=json.loads(Path(s['article_path']).read_text());text=article['sections'][0]['text']
  # A frozen source span is preserved; the mismatch label and fake query are
  # explicit accounting fixtures, not a new scientific assessment.
  span={'evidence_span_id':'SOFTWARE_ACCOUNTING_ANCHOR_'+s['identity']['pmcid'],'section_index':0,'char_start':0,'char_end':len(text),'text':text,'text_hash':__import__('hashlib').sha256(text.encode()).hexdigest()}
  rows.append(assessment(req,s,'paper',s['identity']['pmcid'],[span],{'endpoint':('MISMATCH','Actual source endpoints; artificial test label')},reason='SOFTWARE EXCLUSION ACCOUNTING FIXTURE ONLY'))
 b.catalog.window_source=lambda spec:{'article':json.loads(Path(spec['article_path']).read_text()),'token':spec['source_token']}
 bind_assessments(req,rows,tmp_path/'window_fixture_assessments.json')
 p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.sqlite',cfg,offline=True),b).run(req)
 c=p['run_manifest']['scientific_inclusion_summary']
 assert c['windows_planned']>0 and c['processing_eligible_windows']==0
 assert c['windows_scientifically_excluded']==c['windows_planned'] and c['windows_V3_processed']==0
 assert len(b.transport.calls)==0 and not c['source_fully_extracted']
