"""Pinned authentic-source offline replay adapter. Never a live model client.

Builder/Quality responses are explicit source-bound engineering stubs. Native
experimental packets and AI reviews are replayed byte-for-byte from pinned files.
"""
from pathlib import Path
import copy,json,hashlib
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.orchestration.pilot_budget import cost_nusd
from code_engine.system_b.annotation_schemas.registry import canonical_json
from scripts import search_plan_v24_alpha318b_post_builder_prechecks as prechecks
from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import candidate_id
from scripts.search_plan_v24_alpha320a_v4_localizer import localize_exact_body_quote

class FrozenReplayBackend:
 fixture=True
 def __init__(self,manifest,pricing,*,fail_stage=None,incomplete=False):
  self.pricing=copy.deepcopy(pricing)
  if manifest.get('kind')!='authentic_seen_offline_replay':raise ValueError('explicit_offline_fixture_manifest_required')
  self.fail_stage=fail_stage;self.incomplete=incomplete;self.calls=[]
  self.files={s['pmcid']:{k:Path(s[k]) for k in ('packet','core','review','prompt')} for s in manifest['sources']}
  self.candidates={s['pmcid']:s['stub_candidate'] for s in manifest['sources']}
  self.bmfile=Path(manifest['builder_manifest']);self.qmfile=Path(manifest['quality_manifest'])
  self.pins=dict(manifest['pins'])
  needed={str(p) for f in self.files.values() for p in f.values()}|{str(self.bmfile),str(self.qmfile)}
  for f in self.files.values():
   packet=json.loads(f['packet'].read_text());needed.add(packet['source']['article_path'])
  if not needed<=self.pins.keys():raise ValueError('replay_input_hash_pin_missing')
  self._check_pins()
  self.fingerprint=content_hash({'manifest':manifest,'fail_stage':fail_stage,'incomplete':incomplete})
 def _check_pins(self):
  for p,h in self.pins.items():
   if file_hash(Path(p))!=h:raise RuntimeError('frozen_fixture_changed')
 def select_sources(self,req):
  result=[]
  for pmc in list(self.files)[:req.get('source_count',len(self.files))]:
   f=self.files[pmc];p=json.loads(f['packet'].read_text());source=p['source'];a=Path(source['article_path'])
   result.append({'identity':{'pmid':str(source['pmid']),'pmcid':pmc,'doi':None},'binding':{'verified_identity':{'pmid':str(source['pmid']),'pmcid':pmc,'doi':None},'source_sha256':file_hash(a),'verification_basis':'verified_frozen_source_identity'},'fixture_article':str(a)})
  return result
 def acquire(self,spec):return Path(spec['fixture_article'])
 def builder_request(self,b):
  m=copy.deepcopy(json.loads(self.bmfile.read_text()));doc=b['document'];token=b['token']
  m['request']['model']='deterministic-source-replay';m['provider']='offline-test';m['construction_document_sha256']=content_hash(doc);m['scientific_source_input_sha256']=content_hash({'abstract_text':doc['abstract_text'],'body_text':doc['body_text']});m['opaque_source_token_sha256']=hashlib.sha256(token.encode()).hexdigest()
  m['request']['messages'][1]['content']='Source token: '+token+'\nAbstract: '+doc['abstract_text']+'\nBody: '+doc['body_text']+'\nOutput schema: '+canonical_json(m['expected_response_schema'])+'\n';m['request_sha256']=content_hash(m['request'])
  return m
 def candidate(self,pmc):return copy.deepcopy(self.candidates[pmc])
 def quality_request(self,b,bm,br):
  parsed=json.loads(br['choices'][0]['message']['content']);survivors=[]
  for c in parsed['candidates']:
   cid=candidate_id(b['token'],c);loc=localize_exact_body_quote(c['construction_evidence_span']['exact_text'],b['document']['body_text'],b['document']['paragraphs']);ec=copy.deepcopy(c);ec['construction_evidence_span']={'source_field':'body','start_offset':loc['body_document_start_offset'],'end_offset':loc['body_document_end_offset'],'exact_text':c['construction_evidence_span']['exact_text']};survivors.append({'candidate_id':cid,'candidate_payload_sha256':content_hash(c),'candidate':ec,'original_array_positions':[0]})
  survivors.sort(key=lambda r:(r['candidate_payload_sha256'],r['candidate_id']));payload=prechecks.build_quality_payload(b['token'],survivors,b['document'],b['private_identity']);m=copy.deepcopy(json.loads(self.qmfile.read_text()));m.update(construction_document_sha256=content_hash(b['document']),builder_request_sha256=bm['request_sha256'],builder_response_sha256=content_hash(br),private_source_token_sha256=hashlib.sha256(b['token'].encode()).hexdigest(),quality_payload=payload)
  m['request']['model']='deterministic-source-replay';m['request']['messages'][1]['content']=canonical_json(payload['candidate_packets'])+'\n'+canonical_json(m['expected_response_schema']);m['request_sha256']=content_hash(m['request']);return m
 def complete(self,stage,key,payload,*,provider,model,max_output_tokens):
  self.calls.append((stage,key))
  if stage==self.fail_stage:raise RuntimeError('OFFLINE_INJECTED_MODEL_FAILURE')
  self._check_pins()
  if stage=='builder_v4':
   token=payload['messages'][1]['content'].split('\n',1)[0].split(': ',1)[1];result={'source_record_token':token,'candidates':[self.candidate(key)]}
   output={'model':model,'choices':[{'finish_reason':'stop','message':{'content':canonical_json(result)}}]}
  elif stage=='quality_v2':
   packets=json.JSONDecoder().raw_decode(payload['messages'][1]['content'])[0];q=json.loads(self.qmfile.read_text());criteria=q['expected_response_schema']['properties']['judgments']['items']['properties']['criteria']['required']
   # Source group ID is reproducible from the opaque source token; saved by builder call.
   token=self._tokens[key];group=prechecks.quality.source_group_id(token)
   result={'schema_version':'PropositionQualityAdjudicationV2','source_group_id':group,'judgments':[{'schema_version':'PropositionQualityAdjudicationV2','candidate_id':c['candidate_id'],'criteria':{f:'PASS' for f in criteria},'evidence_support_reference':c['evidence']['exact_evidence_span'][:200]} for c in packets]}
   output={'model':model,'choices':[{'finish_reason':'stop','message':{'content':canonical_json(result)}}]}
  elif stage=='experimental_v3_core':
   f=self.files[key];output=None if self.incomplete else {'packet_utf8':f['packet'].read_text(),'core_utf8':f['core'].read_text(),'review_prompt_utf8':f['prompt'].read_text()}
  elif stage=='ai_review':output=json.loads(self.files[key]['review'].read_text())
  else:raise RuntimeError('unknown_stub_stage')
  if stage=='builder_v4':
   if not hasattr(self,'_tokens'):self._tokens={}
   self._tokens[key]=token
  cfg=self.pricing;cost=cost_nusd(100,50,cfg)
  usage={'provider':provider,'model':model,'input_tokens':100,'output_tokens':50,'cost_usd':str(cost/10**9)}
  return output,usage
