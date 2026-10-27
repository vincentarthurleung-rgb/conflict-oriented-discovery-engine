"""Authentic source-bound B3 inputs; new decisions are explicit Work assessments."""
from pathlib import Path
from copy import deepcopy
import json,hashlib
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.orchestration.pilot_inclusion import VERSION,question_identity
from tests.pilot_linkage_support import backend_fixture,LIVE,RELEASE,pin
from tests.test_pilot_unlimited_integration import existing_backend,FrozenCatalog,SourceBoundTransport
from code_engine.orchestration.pilot_backend import ExistingStagesBackend
from code_engine.orchestration.pilot_replay import FrozenReplayBackend
from tests.pilot_offline_support import replay_manifest
R=Path(__file__).resolve().parents[1]
HIF_INTAKE=R/'runs/20260723_171527_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_v3_recovered_reentry/artifacts/intake.json'
HIF_PLAN=HIF_INTAKE.with_name('search_plan.json')
E=R/'runs/20261017_code_ai_first_scientific_review_shadow_seen_offline'


def write(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');return path


def assessment(request,source,scope_level,scope_identity,spans,values,*,context=None,reason='Explicit source-grounded applicability review; no directional selection'):
 dims=[]
 for key,value in request['scope'].items():
  if key not in ('intervention','entity','endpoint','biological_system','comparator','study_design','timepoint'):continue
  state,source_value=values.get(key,('UNKNOWN','NOT_AVAILABLE'))
  dims.append({'dimension':key,'question_value':value,'source_value':source_value,'assessment':state,'evidence_refs':[s['evidence_span_id'] for s in spans] if state!='UNKNOWN' else []})
 return {'source_identity':source['identity'],'source_content_sha256':source['binding']['source_sha256'],'scope_level':scope_level,'scope_identity':scope_identity,'dimension_assessments':dims,'evidence_spans':spans,'reason':reason,'producer':'interactive_Work_B3_source_applicability_assessment_not_model_extraction','scientific_authorization':False,'uncertainty':['Not independent scientific validation; no formal Core authority'],'context_semantics':context or {}}


def bind_assessments(request,rows,path):
 p=write(path,{'schema_version':VERSION,'question_identity':question_identity(request),'assessments':rows,'scientific_authorization':False});request['scientific_inclusion_assessments']=pin(p);return p


def ar_case(path):
 backend,cfg,req=backend_fixture(path);req['case_id']='B3-AR';req['development_stop_after']='experimental_v3_core';req['scope']={'intervention':'conditional Ar deletion in MuSC','endpoint':'histological single-myofiber CSA','biological_system':'TA skeletal muscle in young mice','timepoint':'7 dpi'}
 req['frozen_semantic_intake']=pin(R/'runs/20261026_code_recovery_batch2_linkage_integration_offline/cases/AR-CSA-B2/intake.json')
 allrecords=json.loads((LIVE/'assessment/derived_response.json').read_text())['records']
 reused=backend.reuse
 def reuse(stage,key,payload):
  if stage!='experimental_v3_core':return None
  one=reused(stage,key,payload);lineage=one['response']['v3_lineage']
  return {'response':{'records':[{**r,'v3_lineage':lineage} for r in allrecords]},'provenance':'all five genuine retained 20261023 V3 observations, no new extraction','cost_usd':'0'}
 backend.reuse=reuse
 source=backend.catalog.specs[0];catalog=json.loads((RELEASE/'source_evidence_catalog.json').read_text());aliases=catalog['aliases']
 def spans_for(index):return deepcopy(json.loads(allrecords[index]['packet_utf8'])['evidence_spans'])
 def caption(alias):
  s=deepcopy(catalog['spans'][aliases[alias]]);origin=catalog['lineage'][s['evidence_span_id']]
  s['source_xml_pin']={'path':origin['original_xml_path'],'sha256':origin['original_xml_sha256']};s['source_xpath']=origin['source_xpath'];s['coordinate_space']='source_contracts.node_text normalized JATS node Unicode chars, not XML byte offsets';return s
 method=deepcopy(catalog['spans'][aliases['M_CSA']]);method['section_index']=catalog['lineage'][method['evidence_span_id']]['section_index']
 coretext=spans_for(2)+[caption('CAP_C'),method]
 common={'intervention':('SUPPORTED','Pax7-CreERT2/TAM conditional Ar deletion'), 'biological_system':('SUPPORTED','mouse TA skeletal muscle')}
 csa={**common,'endpoint':('SUPPORTED','myofiber CSA by histology'),'timepoint':('SUPPORTED','7 dpi in F1C')}
 context={'focal_contrast':'Ar conditional deletion vs TAM-treated Cre-negative control','shared_condition':'CTX injury in both groups','reference_arm':'TAM-treated no-Cre littermates','tested_arm':'AR(i)sat-/Y','measurement':'single-myofiber histological CSA, not whole-muscle geometric CSA','time':'7 dpi from F1C','canonical_identity':'UNKNOWN','measurement_registry':'UNKNOWN'}
 rows=[assessment(req,source,'paper',source['identity']['pmcid'],coretext,csa,context=context,reason='Contains explicit F1C experiment meeting this question stratum; not all paper experiments are included')]
 for i,record in enumerate(allrecords):
  f=record['ExperimentalObservationV3'];spans=spans_for(i)
  if i==2:vals=csa;spans=coretext;reason='F1C quantitative myofiber area in TA at 7 dpi'
  elif i==3:vals={**common,'endpoint':('MISMATCH','contractile force / specific force'),'timepoint':('MISMATCH','28 dpi')};spans+= [caption('CAP_D')];reason='Force at 28 dpi is outside the CSA/7dpi stratum, regardless of negative direction'
  elif i==0:vals={**common,'endpoint':('UNKNOWN','broad histological abnormalities'), 'timepoint':('UNKNOWN','7–42 dpi range')};reason='Broad morphology/time range does not establish the same quantitative CSA endpoint'
  else:vals={**common,'endpoint':('MISMATCH','ultrastructure' if i==1 else 'MuSC pool / PAX7 count'),'timepoint':('UNKNOWN','source-specific, not reassigned')};reason='Different measured endpoint; original timing/binding uncertainty remains unchanged'
  rows.append(assessment(req,source,'observation',f['observation_id'],spans,vals,context=context if i==2 else {},reason=reason))
  rows.append(assessment(req,source,'experiment',f['experiment']['experiment_id'],spans,vals,context={'scope_authority':'native V3 experiment_id, candidate scope only; not a claim of independent experiments'},reason=reason))
 bind_assessments(req,rows,Path(path)/'inclusion_assessments.json');return backend,cfg,req


def hif_case(path):
 backend,cfg=existing_backend(path)
 intake=json.loads(HIF_INTAKE.read_text())
 req={'case_id':'B3-HIF','development_stop_after':'experimental_v3_core','question':intake['research_intent']['raw_user_input'],'scope':{'intervention':'source-specified reduced oxygen versus matched oxygen control','entity':'HIF-1alpha protein','endpoint':'protein abundance','biological_system':'cultured cancer cells'},'evidence_mode':'authentic_seen_replay','model_stages':{k:'review' if k=='ai_review' else 'batch' for k in backend.pricing},'frozen_semantic_intake':pin(HIF_INTAKE),'frozen_search_plan':pin(HIF_PLAN),'frozen_case_identity':json.loads(HIF_PLAN.read_text())['case_id']}
 rows=[]
 for s in backend.catalog.specs:
  pmc=s['identity']['pmcid'];record=next(r for r in replay_manifest()['sources'] if r['pmcid']==pmc)
  packet=json.loads(Path(record['packet']).read_text());formal=json.loads(Path(record['core']).read_text())['ExperimentalObservationV3'];ev=packet['evidence_spans']
  values={k:('SUPPORTED',str(packet['experiment'].get({'intervention':'factor','entity':'measured_entity','endpoint':'endpoint','biological_system':'cells'}[k]))) for k in req['scope']}
  for level,identity in [('paper',pmc),('experiment',formal['experiment']['experiment_id']),('observation',formal['observation_id'])]:rows.append(assessment(req,s,level,identity,ev,values,context={'experiment_design':'in vitro selected cell experiment','paper_design_is_inventory_not_scope_inheritance':True}))
  if pmc=='PMC4024011':
   extra=json.loads((E/'E1/left/evidence_packet.json').read_text());scope='source_evidence_packet:'+file_hash(E/'E1/left/evidence_packet.json')
   vals={**values,'entity':('MISMATCH','VEGF transcript'),'endpoint':('MISMATCH','mRNA abundance')}
   rows.append(assessment(req,s,'observation',scope,extra['evidence_spans'],vals,reason='Authentic VEGF mRNA null finding is outside this PROTEIN endpoint stratum; not excluded for null direction'))
 bind_assessments(req,rows,Path(path)/'inclusion_assessments.json');return backend,cfg,req


def trib_case(path):
 # Reuse existing construction/replay plumbing with the genuine saved clinical
 # source packet. No conversion of raw-XML V3 hash to ArticleJSON is fabricated.
 backend,cfg=existing_backend(path);packet_path=E/'E3/right/evidence_packet.json';packet=json.loads(packet_path.read_text());source=packet['source'];article=json.loads(Path(source['article_path']).read_text())
 meta={'identity':{k:source.get(k) for k in ('pmid','pmcid','doi')},'article_path':source['article_path'],'binding':{'source_sha256':source['article_sha256']},'source_token':'src_'+hashlib.sha256(b'B3_TRIB3_CLINICAL_SOFTWARE_HANDOFF').hexdigest()}
 backend.catalog.specs=[meta];backend.catalog.fingerprint=content_hash(meta)
 from code_engine.fulltext.source_windows import plan_windows,construction_window
 focused=next(w for w in plan_windows(article,source['article_sha256'],max_chars=4000)['windows'] if w['section_index']==packet['evidence_spans'][0]['section_index'])
 backend.construction_bundle=lambda spec:{'source':spec,'token':spec['source_token'],'document':construction_window(focused,spec['source_token']),'private_identity':{**spec['identity'],'title_1':source['title']}}
 # Existing frozen source adapter can build a software B/Q candidate from an
 # actual quote without claiming new model extraction or clinical causation.
 stub=backend.transport.stub;pmc=source['pmcid'];prior=next(iter(stub.files.values()))
 stub.files[pmc]=prior;stub.candidates[pmc]=deepcopy(next(iter(stub.candidates.values())))
 candidate=stub.candidates[pmc];candidate.update(biological_unit='human neuroblastoma patients',actor_or_intervention='TRIB3 biomarker grouping',action='observational association',response_or_endpoint='overall survival',neutral_proposition='SOFTWARE B/Q HANDOFF FIXTURE ONLY: clinical expression strata and overall survival; not an assigned intervention',construction_evidence_span={'exact_text':' '.join(packet['evidence_spans'][0]['text'].split())})
 backend.annotations={pmc:{'packet':pin(packet_path),'core':pin(R/'runs/20260902_single_source_provider_extraction_smoke_pmc10515557_v1/artifacts/validated_observations.jsonl'),'prompt':pin(Path(next(iter(backend.annotations.values()))['prompt']['path']))}}
 def reuse(stage,key,payload):
  if stage=='experimental_v3_core':return {'response':{'records':[],'incomplete':{'retained_source_observation_packet':packet,'frozen_V3_reference':backend.annotations[pmc]['core'],'unresolved':'Original genuine V3 binds original XML hash; no replacement with projection hash and no invented current native Core','scientific_authorization':False}},'provenance':'retained actual source evidence; native handoff incompatibility disclosed','cost_usd':'0'}
  return None
 backend.reuse=reuse
 req={'case_id':'B3-TRIB3','development_stop_after':'experimental_v3_core','question':'How does TRIB3 expression grouping relate to overall survival in neuroblastoma patients?','scope':{'intervention':'observed TRIB3-positive versus TRIB3-negative biomarker strata','endpoint':'overall survival','biological_system':'neuroblastoma patients'},'evidence_mode':'authentic_seen_replay','model_stages':{k:'review' if k=='ai_review' else 'batch' for k in backend.pricing}}
 vals={'intervention':('SUPPORTED','TRIB3 IHC expression strata; no intervention assigned'),'endpoint':('SUPPORTED','overall survival'),'biological_system':('SUPPORTED','archival neuroblastoma patient cohort')};context={'factor_semantics':'observational biomarker grouping, not experimental intervention','study_design':'retrospective clinical cohort supported by actual cohort Methods','native_V3_design_normalization':'unknown / reviewable_unknown remains unchanged','scope':'Figure3A low-risk NB subgroup; not all patients'}
 scope='source_evidence_packet:'+file_hash(packet_path)
 rows=[assessment(req,meta,'paper',pmc,packet['evidence_spans'],vals,context=context),assessment(req,meta,'observation',scope,packet['evidence_spans'],vals,context=context)]
 # Figure scope is explicit in the already frozen packet; not a new boundary.
 rows.append(assessment(req,meta,'experiment',scope+':Figure3A_low_risk',packet['evidence_spans'],vals,context=context))
 bind_assessments(req,rows,Path(path)/'inclusion_assessments.json');return backend,cfg,req


def hif_null_case(path):
 b,cfg,req=hif_case(path);req['case_id']='B3-HIF-NULL';req['scope']={'intervention':'5% versus 20% O2','endpoint':'VEGF transcript abundance','biological_system':'HCT116 cells'}
 b.catalog.specs=[s for s in b.catalog.specs if s['identity']['pmcid']=='PMC4024011'];b.catalog.fingerprint=content_hash(b.catalog.specs)
 s=b.catalog.specs[0];packet_path=E/'E1/left/evidence_packet.json';packet=json.loads(packet_path.read_text());scope='source_evidence_packet:'+file_hash(packet_path)
 vals={k:('SUPPORTED',v) for k,v in req['scope'].items()};context={'source_result':'No significant VEGF mRNA difference; caption P=0.7 (ns)','null_is_not_equivalence':True,'record_type':'retained source evidence packet, not a newly extracted V3'}
 rows=[assessment(req,s,'paper',s['identity']['pmcid'],packet['evidence_spans'],vals,context=context),assessment(req,s,'observation',scope,packet['evidence_spans'],vals,context=context)]
 native_manifest=next(x for x in replay_manifest()['sources'] if x['pmcid']==s['identity']['pmcid']);f=json.loads(Path(native_manifest['core']).read_text())['ExperimentalObservationV3']
 ev=json.loads(Path(native_manifest['packet']).read_text())['evidence_spans'];different={**vals,'endpoint':('MISMATCH','HIF-1alpha protein abundance, not VEGF transcript')}
 rows.append(assessment(req,s,'observation',f['observation_id'],ev,different,reason='Retained native protein observation remains in dataset but is outside this VEGF mRNA question stratum'))
 bind_assessments(req,rows,Path(path)/'null_inclusion_assessments.json');return b,cfg,req
