"""Concrete existing-stage adapters. Construction/experimental gates stay upstream.

Transport is a single HTTP attempt; the executor alone owns paid retries/budget.
Native Core reconstruction is not inferred from a Quality PASS. If no explicit
source-bound native Core exists, hydrate the existing V3 draft and retain the
missing Core as an insufficient-evidence output.
"""
from __future__ import annotations
import copy,json,os,secrets,time,hashlib
from dataclasses import asdict
from pathlib import Path
import httpx
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.orchestration.pilot_budget import cost_nusd
from code_engine.orchestration.pilot_replay import FrozenReplayBackend
from code_engine.system_b.annotation_schemas.registry import canonical_json
from code_engine.fulltext.fulltext_l1_v2 import build_prompt,parse_draft_response,token_budget_preflight,FulltextTokenBudget
from code_engine.fulltext.source_windows import grouped_plan_windows,verify_plan_accounting,construction_window,mapped_evidence_segments,extraction_block
from code_engine.extraction_assets.experimental_core.assembly import assemble_v3
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import TrustedDraftContextV3,hydrate_draft_response_v3
from code_engine.domain.extraction_routing import prepare_v3_prompt,routed_v3_preflight,paper_design,implementation_identity

class RetryableProviderFailure(TimeoutError):
 def __init__(self,reason,retry_after=0,*,safe_to_retry=False):
  super().__init__(reason);self.retry_after=retry_after;self.safe_to_retry=safe_to_retry

class PilotProviderTransport:
 fixture=False
 def __init__(self,*,execute_authorized=False,post=None):
  self.authorized=execute_authorized;self.post=post
 def send(self,provider,body):
  if not self.authorized:raise RuntimeError('paid_model_execution_not_authorized')
  endpoints={'deepseek':('https://api.deepseek.com/v1/chat/completions','DEEPSEEK_API_KEY'),'openai':('https://api.openai.com/v1/chat/completions','OPENAI_API_KEY')}
  url,env=endpoints[provider.casefold()];key=os.environ.get(env)
  if not key:raise RuntimeError('configured_provider_credential_missing')
  try:
   # Explicit no automatic retries; every attempt must get its own reservation.
   with httpx.Client(timeout=httpx.Timeout(connect=20,read=120,write=30,pool=20),transport=httpx.HTTPTransport(retries=0)) as client:
    response=(self.post or client.post)(url,content=canonical_json(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    response.raise_for_status();return response.json()
  except httpx.TimeoutException as e:raise RetryableProviderFailure('single_provider_attempt_timed_out') from e
  except httpx.TransportError as e:raise RetryableProviderFailure('single_provider_transport_failure') from e
  except httpx.HTTPStatusError as e:
   if e.response.status_code in (429,500,502,503,504):
    try:delay=float(e.response.headers.get('Retry-After','1'))
    except ValueError:raise RuntimeError('rate_limit_retry_time_unverifiable') from e
    if not 0<=delay<=30:raise RuntimeError('rate_limit_requires_later_resource_resume') from e
    raise RetryableProviderFailure('single_provider_retryable_status:'+str(e.response.status_code),delay,safe_to_retry=e.response.status_code==429) from e
   raise

class ExistingStagesBackend:
 def __init__(self,*,repository,catalog,transport,pricing,annotations=None,review_prompt=None,linkage_inputs=None,linkage_replays=None):
  self.repository=Path(repository);self.catalog=catalog;self.transport=transport;self.fixture=bool(getattr(transport,'fixture',False));self.pricing=pricing;self.annotations=annotations or {};self.review_prompt=review_prompt
  self.bmfile=self.repository/'runs/20261012_code_pilot_bound_builder_v4_request_freeze_offline/builder_request_manifest.json';self.qmfile=self.repository/'runs/20261012_code_pilot_bound_quality_v2_request_freeze_offline/quality_request_manifest.json'
  self._documents={};self._tokens={};self._windowplans={}
  self.linkage_inputs=linkage_inputs or {};self.linkage_replays=linkage_replays or {}
  if self.linkage_replays and not self.fixture:raise ValueError('Work_linkage_replay_requires_explicit_offline_fixture')
  self.question_domain=None;self.question_routing={'status':'not_bound_general_fallback'}
 def dependency_manifest(self):
  from code_engine.orchestration.pilot_dependencies import effective_dependencies
  from code_engine.orchestration.pilot_linkage import pinned_json
  for pins in self.linkage_inputs.values():
   for pin in pins.values():pinned_json(pin)
  for pin in self.linkage_replays.values():pinned_json(pin)
  return effective_dependencies(self.repository,review_prompt=self.review_prompt,contracts=(self.bmfile,self.qmfile),pricing=self.pricing,annotation_pins=self.annotations,catalog_fingerprint=content_hash({'catalog':self.catalog.fingerprint,'linkage_inputs':self.linkage_inputs,'linkage_replays':self.linkage_replays}),fixture=self.fixture)
 @property
 def fingerprint(self):return self.dependency_manifest()['sha256']
 def bind_question_profile(self,intake):
  intent=intake['research_intent'];self.question_domain=intent.get('domain_id')
  self.question_routing={k:intake.get(k) for k in ('parser_mode','semantic_mode','requires_manual_review','semantic_confidence')}
  self.question_routing.update(domain_id=self.question_domain,prompt_profile_id=intent.get('prompt_profile_id'))
  return self.question_routing
 def classify_source(self,article):return paper_design(article)
 def select_sources(self,request):return self.catalog.select_sources(request)
 def cache_fingerprint(self,stage):return content_hash({'implementation':file_hash(Path(__file__)),'routing':implementation_identity(),'stage':stage,'builder_contract':file_hash(self.bmfile),'quality_contract':file_hash(self.qmfile)})
 def prepare_v3_request(self,payload,*,model,max_output_tokens):
  article=payload['article'];w=payload.get('window')
  block=extraction_block(w,article['pmcid'],article['pmid']) if w else {'block_id':article['pmcid']+':complete_source','text':'\n\n'.join(s['text'] for s in article['sections']),'section':{},'paper_metadata':{k:article[k] for k in ('pmcid','pmid')}}
  audit=self._v3_preflight(article,block,max_output_tokens)
  prompt,route=prepare_v3_prompt(article,block,question_domain=self.question_domain)
  route.update(question_intake=self.question_routing,preflight=audit)
  body={'model':model,'messages':[{'role':'system','content':prompt}],'response_format':{'type':'json_object'},'max_tokens':max_output_tokens,'thinking':{'type':'disabled'}}
  route['provider_body_sha256']=content_hash(body)
  return body,block,route
 def linkage_supplement(self,observation_id):return self.linkage_inputs.get(observation_id)
 def linkage_replay(self,observation_id):
  from code_engine.orchestration.pilot_linkage import pinned_json
  pin=self.linkage_replays.get(observation_id)
  if pin is None:return None
  if not self.fixture:raise ValueError('Work_linkage_replay_is_not_provider_response')
  return {'response':pinned_json(pin)['response'],'proposal_origin':'interactive_Work_source_review_not_provider_linkage_output','artifact':pin}
 def request_routing(self,stage,payload):
  if stage=='source_grounded_linkage':return payload['prepared_request']['routing']
  if stage=='experimental_v3_core':
   pmc=payload['article']['pmcid']
   if not payload.get('window') and pmc in self.annotations:
    return {'question_domain':self.question_domain,'prompt_selection':'pinned_native_annotation_reuse_no_model_request','annotation_pins':self.annotations[pmc],'input_sha256':content_hash(payload),'study_design':'not_reclassified_during_historical_reuse'}
   m=self.pricing[stage];return self.prepare_v3_request(payload,model=m['model'],max_output_tokens=m['max_output_tokens'])[2]
  manifest=json.loads((self.bmfile if stage=='builder_v4' else self.qmfile).read_text()) if stage in ('builder_v4','quality_v2') else {}
  return {'question_domain':self.question_domain,'question_intake':self.question_routing,'prompt_selection':'fixed_frozen_prompt' if manifest else 'separate_review_prompt','prompt_profile':stage+'_frozen' if manifest else 'supplied_review_prompt','prompt_version':manifest.get('builder_v4_version') or manifest.get('quality_v2_protocol_sha256') or 'supplied_by_hash','study_design':None,'study_design_state':'not_routed_for_this_fixed_stage','schema_version':manifest.get('schema_version'),'schema_sha256':content_hash(manifest.get('expected_response_schema')),'input_sha256':content_hash(payload),'routing_implementation_sha256':implementation_identity()}
 def retry_wait(self,error):time.sleep(getattr(error,'retry_after',0))
 def continue_work(self):return getattr(self.catalog,'continue_work',lambda:True)()
 def acquire(self,spec):return Path(spec['article_path'])
 def coverage(self,cid):return self.catalog.coverage(cid)
 def source_token(self,spec,cid):
  # Private stable source work token, shared only for exact same source bytes.
  if hasattr(self.catalog,'source_token'):return self.catalog.source_token(spec)
  return spec.get('source_token') or ('src_'+secrets.token_hex(32))
 def construction_bundle(self,spec):
  # Real new-source path must use the verified existing adapter envelope.
  return self.catalog.construction_bundle(spec)
 def construction_bundles(self,spec):
  if not hasattr(self.catalog,'window_source') and not spec.get('complete_source_windows'):return None
  source=self.catalog.window_source(spec) if hasattr(self.catalog,'window_source') else {'article':json.loads(Path(spec['article_path']).read_text()),'token':self.source_token(spec,'')}
  # Conservative byte ceiling additionally checked against the exact complete
  # provider body before dispatch. No text is truncated to make a request fit.
  room=min(self.pricing[k]['max_input_tokens'] for k in ('builder_v4','quality_v2','experimental_v3_core'))-20000
  if room<=0:
   from code_engine.acquisition.pilot_corpus import ResourcePause
   raise ResourcePause('model_context_limit_smaller_than_frozen_prompt_overhead')
  plan=grouped_plan_windows(source['article'],spec['binding']['source_sha256'],max_chars=min(16000,room),overlap_chars=min(256,max(0,min(16000,room)//8)),routing_domain=self.question_domain or 'general_biomedical')
  verify_plan_accounting(source['article'],plan)
  self._windowplans[spec['identity']['pmcid']]=plan
  return [{'source':spec,'token':source['token'],'document':construction_window(w,source['token']),'private_identity':{**spec['identity'],'title_1':source['article'].get('title','')},'window':w} for w in plan['windows']]
 def builder_request(self,b):
  # Reuse request preparation only; there are no replay candidates here.
  m=FrozenReplayBackend.builder_request(self,b);original=json.loads(self.bmfile.read_text())
  m['request']['model']=original['request']['model'];m['provider']=original['provider'];m['request_sha256']=content_hash(m['request']);self._documents[b['source']['identity']['pmcid']]=b
  return m
 def quality_request(self,b,bm,br):
  m=FrozenReplayBackend.quality_request(self,b,bm,br);original=json.loads(self.qmfile.read_text());m['request']['model']=original['request']['model'];m['request_sha256']=content_hash(m['request']);return m
 def reuse(self,stage,key,payload):
  if stage!='experimental_v3_core' or key not in self.annotations:return None
  a=self.annotations[key];result={}
  for name in ('packet','core','prompt'):
   p=Path(a[name]['path'])
   if file_hash(p)!=a[name]['sha256']:raise ValueError('explicit_native_annotation_hash_drift')
   result[{'packet':'packet_utf8','core':'core_utf8','prompt':'review_prompt_utf8'}[name]]=p.read_text()
  return {'response':result,'provenance':'explicit pinned source-bound native annotation; not new model extraction','cost_usd':'0'}
 def input_upper_bound(self,stage,payload):
  m=self.pricing[stage];model=m['model']
  if stage=='source_grounded_linkage':return len(canonical_json(payload['prepared_request']['body']).encode())+1024
  if stage in ('builder_v4','quality_v2'):body={**payload,'max_tokens':m['max_output_tokens']}
  elif stage=='experimental_v3_core':
   body,_,_=self.prepare_v3_request(payload,model=model,max_output_tokens=m['max_output_tokens'])
  else:body={'model':model,'messages':[{'role':'system','content':payload['prompt']},{'role':'user','content':canonical_json({'packet':payload['packet'],'core':payload['core']})}],'response_format':{'type':'json_object'},'max_tokens':m['max_output_tokens']}
  return len(canonical_json(body).encode())
 def _v3_preflight(self,article,block,max_output_tokens):
  audit=routed_v3_preflight(article,block,question_domain=self.question_domain,budget=FulltextTokenBudget(max_tokens=max_output_tokens))
  if audit['preflight_decision']!='execute_as_is':
   raise ValueError('frozen_V3_preflight_requires_source_replanning:'+','.join(audit['preflight_reasons']))
  return audit
 def prepare_model_request(self,stage,payload,*,provider,model,max_output_tokens):
  if stage in ('builder_v4','quality_v2'):
   body=copy.deepcopy(payload)
   if body['model']!=model or provider.casefold()!='deepseek':raise ValueError('frozen_builder_quality_model_provider_mismatch')
  elif stage=='experimental_v3_core':
   article=payload['article'];window=payload.get('window')
   body,block,route=self.prepare_v3_request(payload,model=model,max_output_tokens=max_output_tokens);text=block['text']
  elif stage=='source_grounded_linkage':
   body=copy.deepcopy(payload['prepared_request']['body'])
   if provider.casefold()!='deepseek' or body['model']!=model or body['max_tokens']!=max_output_tokens:raise ValueError('linkage_prepared_model_configuration_mismatch')
  elif stage=='ai_review':
   if provider.casefold()!='openai':raise ValueError('GPT_scientific_review_provider_must_be_separate')
   body={'model':model,'messages':[{'role':'system','content':payload['prompt']},{'role':'user','content':canonical_json({'packet':payload['packet'],'core':payload['core']})}],'response_format':{'type':'json_object'}}
  else:raise ValueError('unknown_paid_stage')
  body['max_tokens']=max_output_tokens
  # The full provider request, including schema/prompt overhead, is bounded.
  if len(canonical_json(body).encode())>self.pricing[stage]['max_input_tokens']:raise ValueError('provider_request_context_limit; source is not silently truncated')
  return body
 def raw_request_identity(self,provider,body):
  endpoint={'deepseek':'https://api.deepseek.com/v1/chat/completions','openai':'https://api.openai.com/v1/chat/completions'}[provider.casefold()]
  return {'schema_version':'exact_provider_request_v1','provider':provider.casefold(),'endpoint':endpoint,'body_sha256':content_hash(body),'fixture':self.fixture}
 def dispatch_raw(self,provider,body):return self.transport.send(provider,body)
 def response_usage(self,stage,raw,*,provider,model):
  usage=raw.get('usage') or {};actual_model=raw.get('model')
  accepted={model,*self.pricing[stage].get('accepted_response_models',[])}
  i=usage.get('prompt_tokens');o=usage.get('completion_tokens')
  cost=str(cost_nusd(i,o,self.pricing[stage])/1e9) if type(i) is int and type(o) is int else None
  return {'provider':provider,'model':model if actual_model in accepted else actual_model,'input_tokens':i,'output_tokens':o,'cost_usd':cost,'provider_response_model':actual_model}
 def complete(self,stage,key,payload,*,provider,model,max_output_tokens):
  body=self.prepare_model_request(stage,payload,provider=provider,model=model,max_output_tokens=max_output_tokens)
  raw=self.dispatch_raw(provider,body)
  receipt=self.response_usage(stage,raw,provider=provider,model=model)
  return self.derive_response(stage,payload,raw,request_body=body),receipt
 def derive_response(self,stage,payload,raw,*,request_body=None):
  if stage=='source_grounded_linkage' and (not raw.get('choices') or raw['choices'][0].get('finish_reason')!='stop'):
   return {'incomplete':{'reason':'linkage_provider_response_not_complete','raw_provider_response':raw},'records':[]}
  if stage=='experimental_v3_core':
   article=payload['article'];window=payload.get('window');m=self.pricing[stage]
   _,block,route=self.prepare_v3_request(payload,model=(request_body or m)['model'],max_output_tokens=request_body['max_tokens'] if request_body else m['max_output_tokens']);text=block['text']
  if stage in ('builder_v4','quality_v2'):out=raw
  else:
   try:out=json.loads(raw['choices'][0]['message']['content'])
   except (ValueError,KeyError,TypeError) as error:
    return {'incomplete':{'provider_parse_error':type(error).__name__+':'+str(error),'raw_provider_response':raw},'records':[]}
   if stage=='experimental_v3_core':
    ctx=TrustedDraftContextV3(run_id='source:'+payload['source_sha256'],block_id=block['block_id'],parent_block_id=None,child_block_id=None,block_text=text,source_block_hash=hashlib.sha256(text.encode()).hexdigest(),source_document_id=article['pmcid'],paper_id=article['pmcid'],pmid=str(article['pmid']),pmcid=article['pmcid'],section=window['section_title'] if window else None,fulltext_source_hash=payload['source_sha256'],source_artifact=payload['source_artifact'])
    try:hydrated=hydrate_draft_response_v3(parse_draft_response(out),ctx)
    except (ValueError,KeyError,TypeError) as error:
     return {'incomplete':{'provider_parse_error':type(error).__name__+':'+str(error),'raw_provider_response':raw},'records':[]}
    from code_engine.extraction_assets.experimental_core.adapters import adapt_explicit_core
    explicit=[adapt_explicit_core(row) for row in hydrated.formal_response['experimental_observations']]
    out={'incomplete':{'formal_v3':hydrated.formal_response,'source_block':{'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'source_artifact':payload['source_artifact']},'prompt_routing':route,'explicit_core_candidates':explicit,'anchor_audit':hydrated.audit,'rejected':hydrated.rejected,'missing':['source-grounded Experimental Core factors/measurement/results and explicit linkage annotation'],'scientific_authorization':False}}
    out['incomplete']['raw_provider_response']=raw
    out['records']=[]
    for formal in hydrated.formal_response['experimental_observations']:
     if window is None:continue # Legacy whole-source diagnostics stay explicit.
     try:rebuilt=assemble_v3(formal,source_artifact=payload['source_artifact'],source_blocks={block['block_id']:text})
     except (ValueError,KeyError,TypeError) as error:
      out.setdefault('assembly_failures',[]).append({'observation_id':formal['observation_id'],'reason':type(error).__name__+':'+str(error)});continue
     mapped=[piece for span in formal['provenance']['evidence_spans'] for piece in mapped_evidence_segments(window,span,block=block)]
     if any(x['section_index'] is None for x in mapped):
      out.setdefault('assembly_failures',[]).append({'observation_id':formal['observation_id'],'reason':'abstract_packet_mapping_requires_explicit_source_section'});continue
     evidence=[{**x,'source_section_text_sha256':hashlib.sha256(article['sections'][x['section_index']]['text'].encode()).hexdigest()} for x in mapped]
     packet={'packet_id':'packet_'+content_hash([formal['observation_id'],mapped]),'source':{**{k:article[k] for k in ('pmid','pmcid')},'article_path':payload['source_artifact'],'article_sha256':payload['source_sha256']},'V3_observation_id':formal['observation_id'],'Core_revision_id':rebuilt['envelope']['ExperimentalCore']['revision']['identity'],'experiment':{'scope':formal['experiment']['experiment_label_raw'],'factor':[x.get('target_mention') or x.get('condition_raw') for x in formal['interventions']],'measurement':formal['measurement'],'result':formal['observation']},'evidence_spans':evidence,'unresolved_information':rebuilt['missing']}
     prompt=Path(self.review_prompt).read_text() if self.review_prompt else (self.repository/'runs/20261017_code_ai_first_scientific_review_shadow_seen_offline/review_prompt_v1.txt').read_text()
     out['records'].append({'ExperimentalObservationV3':formal,'window_id':window['window_id'],'source_evidence':mapped,'packet_utf8':canonical_json(packet),'core_utf8':canonical_json(rebuilt['envelope']),'review_prompt_utf8':prompt,'assembly':{k:v for k,v in rebuilt.items() if k!='envelope'},'v3_lineage_material':{'raw_provider_response':raw,'validated_formal_v3':hydrated.formal_response,'hydration_context':asdict(ctx),'source_blocks':{block['block_id']:text},'window':window}})
  return out
