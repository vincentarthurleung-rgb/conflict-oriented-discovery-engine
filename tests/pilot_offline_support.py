"""Same-source deterministic Builder/Quality stubs; scientific evidence stays frozen."""
from pathlib import Path
import json,copy,hashlib,unicodedata
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.orchestration.pilot_budget import cost_nusd
from scripts import search_plan_v24_alpha318b_post_builder_prechecks as prechecks
from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import candidate_id
from scripts.search_plan_v24_alpha320a_v4_localizer import localize_exact_body_quote
from code_engine.system_b.annotation_schemas.registry import canonical_json
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/20261016_code_comparable_evidence_discovery_review_integration_seen_offline'
OLD=ROOT/'runs/20261017_code_ai_first_scientific_review_shadow_seen_offline'

def fixture_budget(total='20',per_case='10'):
 return {'kind':'offline_billing_fixture','total_cap_usd':total,'case_cap_usd':per_case,'max_attempts':2,'models':{'fixture':{'provider':'offline-test','model':'deterministic-source-replay','input_usd_per_million':'1','output_usd_per_million':'2','verification_basis':'OFFLINE DETERMINISTIC BILLING FIXTURE, NOT LIVE PRICE OR SPEND AUTHORIZATION','max_input_tokens':500000,'max_output_tokens':100000}}}

def request(cid,count=2):
 return {'case_id':cid,'question':'How does lower oxygen affect HIF-1alpha protein abundance in the specified cell systems?','scope':{'entity':'HIF-1α protein','endpoint':'protein abundance','intervention':'specified oxygen exposure','context':'source-specific oxygen, time and cells'},'evidence_mode':'authentic_seen_replay','source_count':count,'model_stages':{s:'fixture' for s in ['builder_v4','quality_v2','experimental_v3_core','ai_review']}}

def replay_manifest(pair='HIF'):
 from code_engine.orchestration.pilot_replay import FrozenReplayBackend
 sources=[]
 if pair=='HIF':
  paths=[(pmc,BASE/pmc,OLD/pmc/'ai_review.json',OLD/'review_prompt_v1.txt') for pmc in ('PMC4024011','PMC7749157')]
 else:
  d=ROOT/'runs/20261017_code_real_contradiction_candidate_discovery_seen_offline'
  paths=[(pmc,d/'reconstructions/D19'/pmc,d/'reconstructions/D19'/pmc/'ai_review.json',d/'shadow_review_prompt.txt') for pmc in ('PMC6787500','PMC7744182')]
 for pmc,d,review,prompt in paths:
  p=json.loads((d/'evidence_packet.json').read_text());ex=p['experiment']
  raw=p['evidence_spans'][1]['text'] if pmc=='PMC4024011' else p['evidence_spans'][0]['text']
  quote=' '.join(unicodedata.normalize('NFKC',raw).split())
  candidate={'actor_or_intervention':ex['factor'],'action':'oxygen exposure' if pair=='HIF' else ex['kind'],'relation_direction':'DECREASES' if ex.get('direction')=='negative' else 'INCREASES','response_or_endpoint':'HIF-1alpha protein abundance' if pair=='HIF' else ex['entity']+' protein abundance','biological_unit':ex.get('cells',ex.get('cell')),'species':None,'intrinsic_conditioning':ex['factor'],'intrinsic_therapy_context':None,'intrinsic_disease_or_genotype_context':None,'neutral_proposition':'In the stated cell system, '+(ex.get('result') or 'lower oxygen is followed by increased HIF-1alpha protein abundance.'),'construction_evidence_span':{'exact_text':quote}}
  sources.append({'pmcid':pmc,'packet':str(d/'evidence_packet.json'),'core':str(d/'v3_core_draft.json'),'review':str(review),'prompt':str(prompt),'stub_candidate':candidate})
 m={'kind':'authentic_seen_offline_replay','sources':sources,'builder_manifest':str(ROOT/'runs/20261012_code_pilot_bound_builder_v4_request_freeze_offline/builder_request_manifest.json'),'quality_manifest':str(ROOT/'runs/20261012_code_pilot_bound_quality_v2_request_freeze_offline/quality_request_manifest.json')}
 files=[Path(m[k]) for k in ('builder_manifest','quality_manifest')]
 for s in sources:
  files.extend(Path(s[k]) for k in ('packet','core','review','prompt'))
  files.append(Path(json.loads(Path(s['packet']).read_text())['source']['article_path']))
 m['pins']={str(p):file_hash(p) for p in files};return m

from code_engine.orchestration.pilot_replay import FrozenReplayBackend
class FrozenSourcesBackend(FrozenReplayBackend):
 def __init__(self,*,pair='HIF',fail_stage=None,incomplete=False):
  super().__init__(replay_manifest(pair),fixture_budget()['models']['fixture'],fail_stage=fail_stage,incomplete=incomplete)
