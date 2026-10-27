"""B3: frozen intake and direction-neutral, source-bound inclusion sidecars.

This consumes explicit applicability assessments, not a universal classifier.
Decisions remain AI-provisional and cannot authorize scientific Core reuse.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib,json
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.query.intake import ResearchIntakeResult,parse_research_intake
from code_engine.domain.models import default_domain_profiles
from code_engine.domain.extraction_routing import paper_design
from code_engine.search.planner_authority_contract_split_v1 import validate_validated_plan

VERSION='source_grounded_scientific_inclusion_v1'
INPUT_KEYS=('frozen_semantic_intake','frozen_search_plan','scientific_inclusion_assessments')
DIMENSIONS={'intervention','entity','endpoint','biological_system','comparator','study_design','timepoint'}
AUTHORITY={'authority_label':'AI_PROVISIONAL_NOT_INDEPENDENTLY_VALIDATED','scientific_authorization':False,'human_gold':False,'strict_core_eligible':False}


def read_pin(pin):
 p=Path(pin['path']);h=file_hash(p)
 if h!=pin['sha256']:raise ValueError('frozen_artifact_hash_mismatch')
 return json.loads(p.read_text())


def question_identity(request):
 return content_hash({k:request.get(k) for k in ('case_id','question','scope','case_design_sha256')})


def input_identity(request):
 # Actual bytes, even when malformed/mismatched, invalidate derived packages.
 # Raw request caches intentionally do not include this derived identity.
 rows={}
 for key in INPUT_KEYS:
  ref=request.get(key)
  if ref:
   p=Path(ref.get('path','')) if isinstance(ref,dict) else Path('/__invalid_frozen_input__')
   rows[key]={'declared':ref,'actual_sha256':file_hash(p) if p.is_file() else None}
 return content_hash({'version':VERSION,'inputs':rows,'question_identity':question_identity(request)})


def frozen_intake(request):
 trace={'version':'frozen_semantic_intake_reuse_v1','question_identity':question_identity(request),'current_model_API_calls':0,'search_plan_status':'ABSENT','state':'DEGRADED_ABSENT','historical_LLM_execution_attested':False}
 parsed=None
 if request.get('frozen_semantic_intake'):
  try:
   raw=read_pin(request['frozen_semantic_intake']);parsed=ResearchIntakeResult.model_validate(raw).model_dump(mode='json')
   if parsed['research_intent']['raw_user_input']!=request['question']:raise ValueError('frozen_intake_question_mismatch')
   domain=parsed['research_intent']['domain_id']
   if domain not in {p.domain_id for p in default_domain_profiles()}:raise ValueError('frozen_intake_domain_profile_incompatible')
   if parsed['semantic_mode']=='llm_semantic' and parsed['parser_mode']!='llm_assisted':raise ValueError('frozen_intake_mode_inconsistent')
   trace.update(state='FROZEN_SCHEMA_VALIDATED_REUSE',source=request['frozen_semantic_intake'],historical_parser_mode=parsed['parser_mode'],historical_semantic_mode=parsed['semantic_mode'],historical_api_calls_as_recorded=parsed['api_calls_made'],historical_LLM_execution_attested=False,verification='Exact artifact/schema/question binding; historical mode is retained, not new model execution or independent producer attestation')
  except (ValueError,KeyError,TypeError,OSError) as error:
   parsed=None;trace.update(state='DEGRADED_INVALID_OR_INCOMPATIBLE',reason=type(error).__name__+':'+str(error))
 if parsed is None:
  parsed=parse_research_intake(request['question'],execute=False,use_api=False).model_dump(mode='json')
  trace['fallback']='existing deterministic_degraded parser, no new API call'
 if request.get('frozen_search_plan') or request.get('validated_search_plan'):
  try:
   plan=read_pin(request['frozen_search_plan']) if request.get('frozen_search_plan') else request['validated_search_plan']
   if not isinstance(plan,dict):raise ValueError('frozen_search_plan_object_required')
   if plan.get('artifact_schema_version')=='frozen_search_plan.v1':
    from code_engine.search.search_plan_replay import load_frozen_search_plan
    if not request.get('frozen_search_plan'):raise ValueError('legacy_frozen_plan_requires_pinned_file')
    _,replay=load_frozen_search_plan(request['frozen_search_plan']['path'],fail_if_drift=True)
    if plan.get('query_text')!=request['question'] or plan.get('case_id')!=request.get('frozen_case_identity',request['case_id']):raise ValueError('frozen_search_plan_case_question_mismatch')
    trace.update(search_plan_status='FROZEN_VALIDATED_REUSE',search_plan_sha256=content_hash(plan),original_case_identity=plan.get('case_id'),search_plan_replay=replay,query_provenance=plan['pubmed_queries'])
   else:
    validate_validated_plan(plan)
    target=plan['canonical_proposition']['target_payload']
    if target.get('case_id')!=request['case_id'] or target.get('primary_proposition_meaning')!=request['question']:raise ValueError('frozen_search_plan_case_question_mismatch')
    trace.update(search_plan_status='FROZEN_VALIDATED_REUSE',search_plan_sha256=content_hash(plan))
  except (ValueError,KeyError,TypeError,OSError) as error:trace.update(search_plan_status='INVALID_OR_INCOMPATIBLE',search_plan_reason=type(error).__name__+':'+str(error))
 trace['question_domain']=parsed['research_intent']['domain_id'];trace['paper_domain']='NOT_INFERRED_FROM_QUESTION';trace['relevance']='assessed separately against frozen question scope';trace['derived_input_identity']=input_identity(request)
 return parsed,trace


class InclusionLedger:
 def __init__(self,request):
  self.request=request;self.question_id=question_identity(request);self.rows=[];self.assessments=[];self.input_error=None
  self.criteria={k:v for k,v in request.get('scope',{}).items() if k in DIMENSIONS and isinstance(v,str) and v}
  self.unsupported_scope_fields=[k for k,v in request.get('scope',{}).items() if isinstance(v,str) and v and k not in DIMENSIONS and k not in {'direction','component_test','endpoint_boundary','fixture'}]
  if request.get('scientific_inclusion_assessments'):
   try:
    packet=read_pin(request['scientific_inclusion_assessments'])
    if not isinstance(packet,dict):raise ValueError('inclusion_assessment_object_required')
    if not isinstance(packet.get('assessments'),list) or not all(isinstance(a,dict) for a in packet['assessments']):raise ValueError('inclusion_assessment_rows_invalid')
    if packet.get('schema_version')!=VERSION or packet.get('question_identity')!=self.question_id:raise ValueError('inclusion_assessment_question_or_version_mismatch')
    if packet.get('scientific_authorization') is not False:raise ValueError('inclusion_assessment_cannot_grant_authority')
    self.assessments=packet['assessments']
   except (ValueError,KeyError,TypeError,OSError) as error:self.input_error=type(error).__name__+':'+str(error)

 def decide(self,source,*,scope_level='paper',scope_identity=None,observation=None):
  article_path=source.get('article_path');available=bool(article_path and Path(article_path).is_file())
  identity=source.get('identity',{});expected=(source.get('binding') or {}).get('source_sha256')
  base={**AUTHORITY,'schema_version':VERSION,'question_identity':self.question_id,'case_id':self.request['case_id'],'frozen_question':self.request['question'],'scope':deepcopy(self.request.get('scope',{})),'case_design_sha256':self.request.get('case_design_sha256'),'frozen_semantic_intake_ref':self.request.get('frozen_semantic_intake'),'frozen_search_plan_ref':self.request.get('frozen_search_plan'),'query_source_provenance':{'query_ids':source.get('query_ids',[]),'retrieval_reason':source.get('retrieval_reason'),'source_work_id':source.get('exposure_work_id')},'source_identity':identity,'source_content_sha256':expected,'source_artifact':str(Path(article_path).resolve()) if available else None,'scope_level':scope_level,'scope_identity':scope_identity or identity.get('pmcid') or identity.get('pmid'),'source_access_state':source.get('access_state','available' if available else 'unavailable'),'retrieval_eligibility':source.get('retrieval_eligibility','candidate_for_inspection_not_scientific_inclusion'),'decision':'UNCERTAIN','assessment_state':'NOT_YET_ASSESSED','reason':'No exact source-grounded applicability assessment; retained for review/processing','producer':VERSION,'decision_authority':'AI_PROVISIONAL_APPLICABILITY_ONLY','independent_scientific_verification':False,'question_domain_not_paper_domain':True,'paper_domain':'UNKNOWN','study_design':None,'experiment_context':None,'dimension_assessments':[],'evidence_spans':[],'source_assessment_origin':None,'confidence':None,'uncertainty':['No independent review or formal reuse authority'],'policy_identity':VERSION,'extraction_success_inferred':False,'unsupported_scope_fields':self.unsupported_scope_fields}
  if observation:
   base.update(study_design={'source_raw':observation['experiment'].get('experimental_design_raw'),'design_type_as_recorded':observation['experiment'].get('design_type'),'normalization_status_as_recorded':observation['experiment'].get('design_normalization_status'),'classification_not_added_by_inclusion':True},experiment_context=deepcopy(observation['experiment']),measurement_as_recorded=deepcopy(observation['measurement']),observed_result_as_recorded=deepcopy(observation['observation']))
  matches=[a for a in self.assessments if a.get('source_identity')==identity and a.get('scope_level')==scope_level and a.get('scope_identity')==base['scope_identity']]
  try:
   if self.input_error:raise ValueError(self.input_error)
   if not available:
    base.update(reason='Fulltext unavailable/not inspected; cannot infer scientific exclusion',assessment_state='ACCESS_BLOCKED')
   elif file_hash(Path(article_path))!=expected:raise ValueError('inclusion_source_hash_mismatch')
   elif len(matches)>1:raise ValueError('ambiguous_duplicate_scope_assessments')
   elif matches:
    a=matches[0];article=json.loads(Path(article_path).read_text())
    if a['source_content_sha256']!=expected:raise ValueError('assessment_source_revision_mismatch')
    if str(article['pmid'])!=str(identity.get('pmid')) or article['pmcid']!=identity.get('pmcid'):raise ValueError('assessment_source_identity_mismatch')
    if a.get('scientific_authorization') is not False or not a.get('producer') or not a.get('reason'):raise ValueError('assessment_producer_or_authority_invalid')
    evidence={}
    for span in a['evidence_spans']:
     if span.get('source_xml_pin'):
      from code_engine.orchestration.pilot_linkage import _xml_node
      from scripts.search_plan_v24_alpha318a1_source_contracts import node_text
      pin=span['source_xml_pin']
      if file_hash(Path(pin['path']))!=pin['sha256'] or article.get('original_xml_sha256')!=pin['sha256']:raise ValueError('inclusion_original_XML_binding_mismatch')
      text=node_text(_xml_node(pin['path'],span['source_xpath']))
     else:text=article['sections'][span['section_index']]['text']
     start,end=span['char_start'],span['char_end']
     if not (0<=start<end<=len(text) and text[start:end]==span['text'] and hashlib.sha256(span['text'].encode()).hexdigest()==span['text_hash']):raise ValueError('inclusion_evidence_coordinate_or_hash_mismatch')
     if span['evidence_span_id'] in evidence and span!=evidence[span['evidence_span_id']]:raise ValueError('inclusion_evidence_identity_collision')
     evidence[span['evidence_span_id']]=span
    dims=a['dimension_assessments'];seen=set()
    for d in dims:
     k=d['dimension']
     if k not in self.criteria or k in seen:raise ValueError('unsupported_or_duplicate_inclusion_dimension')
     seen.add(k)
     if d['question_value']!=self.criteria[k] or d['assessment'] not in ('SUPPORTED','MISMATCH','UNKNOWN'):raise ValueError('inclusion_dimension_question_binding_mismatch')
     if d['assessment']!='UNKNOWN' and (not d.get('source_value') or not d.get('evidence_refs') or not set(d['evidence_refs'])<=evidence.keys()):raise ValueError('inclusion_dimension_exact_evidence_required')
    states={d['dimension']:d['assessment'] for d in dims}
    decision='EXCLUDED' if 'MISMATCH' in states.values() else 'INCLUDED' if self.criteria and not self.unsupported_scope_fields and all(states.get(k)=='SUPPORTED' for k in self.criteria) else 'UNCERTAIN'
    base.update(decision=decision,assessment_state='ASSESSED',reason=a['reason'],dimension_assessments=deepcopy(dims),evidence_spans=list(evidence.values()),source_assessment_origin=a['producer'],uncertainty=a.get('uncertainty',[])+['Source applicability assessment is not independent scientific validation'],confidence=a.get('confidence'),context_semantics=a.get('context_semantics',{}))
    # Outcome, significance and identity are neither criteria nor authorization.
   else:base['reason']='No exact decision at this scope; paper inclusion is not inherited'
  except (ValueError,KeyError,TypeError,IndexError,OSError) as error:
   base.update(decision='UNCERTAIN',assessment_state='INVALID_ASSESSMENT',reason=type(error).__name__+':'+str(error))
  base['downstream_processing_permitted']=base['decision']!='EXCLUDED' and available
  base['revision_identity']='scientific_inclusion_revision:'+content_hash(base)
  self.rows.append(base);return base

 def export(self):
  revisions={r['revision_identity']:r for r in self.rows}
  unique={(r['scope_level'],r['scope_identity'],r['source_content_sha256']):r for r in self.rows}
  return {'schema_version':VERSION,'question_identity':self.question_id,'rows':list(unique.values()),'immutable_revisions':list(revisions.values()),'assessment_input_error':self.input_error,**AUTHORITY}


def coverage_accounting(manifest,rows,records,plans,window_states,case_dir):
 """Explicit observed denominators; absent coverage stays unknown, never recall."""
 coverage=manifest.get('literature_coverage') or {};paper=[r for r in rows if r['scope_level']=='paper'];obs=[r for r in rows if r['scope_level']=='observation'];experiments=[r for r in rows if r['scope_level']=='experiment']
 calls=[r for r in manifest.get('_model_usage_rows',[]) if r.get('state') in ('DISPATCHED','SETTLED','UNVERIFIABLE_SPEND')]
 # The caller supplies actual ModelBudget receipts. Offline fixture reservations
 # are separately counted; pinned historical responses are not new dispatches.
 outcomes=[]
 for pmc,plan in plans.items():
  for w in plan['windows']:
   outcomes.append({'pmcid':pmc,'window_id':w['window_id'],'states':window_states.get(pmc,{}).get(w['window_id'],{})})
 incomplete=[];hydrated_ids={json.loads(r['core'].read_text())['ExperimentalObservationV3']['observation_id'] for r in records}
 for p in Path(case_dir).glob('*_incomplete_experimental_records.json'):
  value=json.loads(p.read_text()).get('output') or {};inc=value.get('incomplete') or {}
  hydrated_ids.update(f['observation_id'] for f in inc.get('formal_v3',{}).get('experimental_observations',[]))
  incomplete.append({'artifact':p.name,'parsed_observations':len(inc.get('formal_v3',{}).get('experimental_observations',[])),'rejected':len(inc.get('rejected',[])),'assembly_failures':len(value.get('assembly_failures',[])),'parse_failed':bool(inc.get('provider_parse_error'))})
 return {'schema_version':'scientific_inclusion_coverage_v1','question_identity':manifest.get('scientific_question_identity'),'retrieval_rows_discovered':coverage.get('retrieved_metadata_rows'),'unique_retrieved_papers':coverage.get('unique_case_papers'),'deduplicated_metadata_rows':coverage.get('duplicate_metadata_rows'),'previously_seen_retrieval_exclusions':sum(any(reason in str(p.get('reason','')) for reason in ('historical_source_excluded','previous_attempt_exposure_excluded')) for p in coverage.get('papers',[])),'acquisition_outcomes_as_reported':dict(Counter(p.get('status','unknown') for p in coverage.get('papers',[]))) if coverage.get('papers') else None,'acquisition_is_new_execution':manifest.get('evidence_mode')=='authorized_new_pilot','source_access_states':dict(Counter(r['source_access_state'] for r in paper)),'papers_awaiting_assessment':sum(r['assessment_state']!='ASSESSED' for r in paper),'paper_decisions':dict(Counter(r['decision'] for r in paper)),'experiment_decisions':dict(Counter(r['decision'] for r in experiments)),'observation_decisions':dict(Counter(r['decision'] for r in obs)),'assessment_completion':bool(paper) and all(r['assessment_state']=='ASSESSED' for r in rows),'unresolved_decisions':sum(r['decision']=='UNCERTAIN' for r in rows),'available_source_region_inventory':sum(len(json.loads(Path(r['source_artifact']).read_text()).get('sections',[])) for r in paper if r['source_access_state']=='available' and r.get('source_artifact')),'eligible_window_denominator_known':bool(plans),'regions_planned':sum(len(p['regions']) for p in plans.values()),'windows_planned':len(outcomes),'windows':outcomes,'windows_V3_processed':sum(w['states'].get('experimental_v3_core',{}).get('status')=='processed' for w in outcomes),'windows_scientifically_excluded':sum(w['states'].get('experimental_v3_core',{}).get('status')=='scientifically_excluded' for w in outcomes),'real_model_dispatches_this_attempt':0 if manifest.get('has_deterministic_model_stubs') else len(calls),'software_fixture_model_dispatches':len(calls) if manifest.get('has_deterministic_model_stubs') else 0,'model_dispatch_count_semantics':'budget-committed transport attempts; unknown outcomes are not confirmed HTTP success','confirmed_new_model_responses':0 if manifest.get('has_deterministic_model_stubs') else sum(r['state']=='SETTLED' for r in calls),'unsettled_dispatch_attempts':sum(r['state']!='SETTLED' for r in calls),'raw_receipts_or_reserved_unknown':[{k:r.get(k) for k in ('logical_id','attempt','state')} for r in calls],'observations_hydrated_or_replayed_unique':len(hydrated_ids),'observations_rejected_during_hydration':sum(x['rejected'] for x in incomplete),'observations_unresolved_for_reuse':sum(not r['prepared']['experimental_core_handoff_audit']['readiness']['status'].startswith('machine_reusable') for r in records),'windows_V3_empty_valid_output':sum(w['states'].get('experimental_v3_core',{}).get('output_state')=='empty' and w['states'].get('experimental_v3_core',{}).get('status')=='processed' for w in outcomes),'windows_V3_not_processed':sum(w['states'].get('experimental_v3_core',{}).get('status') in ('pending',None) for w in outcomes),'processing_eligible_windows':sum(w['states'].get('experimental_v3_core',{}).get('status')!='scientifically_excluded' for w in outcomes) if plans else None,'native_records_retained':len(records),'native_records_excluded_from_downstream':sum(r.get('inclusion',{}).get('decision')=='EXCLUDED' for r in records),'linkage_readiness_states':dict(Counter(r['prepared']['experimental_core_handoff_audit']['readiness']['status'] for r in records)),'incomplete_V3_windows':incomplete,'no_publication_recall_estimated':True,'source_fully_extracted':False,'zero_Builder_candidates_imply_zero_relevant_observations':False,'full_L0_L6_scientific_execution':False}
