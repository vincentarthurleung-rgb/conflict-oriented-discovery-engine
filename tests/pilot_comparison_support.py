"""Explicit Work B4 scientific assessments of frozen authentic packets.

Fixtures supply construction transport only; biomedical statements below are
source-bound provisional annotations, never synthetic model extractions.
"""
from pathlib import Path
from copy import deepcopy
import json
from code_engine.orchestration.pilot_comparison import VERSION, FACETS, AXES
from code_engine.orchestration.pilot_inclusion import question_identity
from code_engine.discovery.ai_review_shadow import file_hash
from tests.pilot_inclusion_support import (ar_case, hif_case, trib_case, hif_null_case,
    assessment, bind_assessments, write, E, R, LIVE, RELEASE, pin)

HIF=R/'runs/20261016_code_comparable_evidence_discovery_review_integration_seen_offline'


def facet(value=None, refs=(), uncertainty='Source-bound Work interpretation, not independent validation'):
 return {'value':value,'evidence_refs':list(refs),'uncertainty':uncertainty}


def proposition(key,row,*,native=None,experiment=None,packet=None,role='unresolved'):
 return {'key':key,'scope_identity':row['scope_identity'],'experiment_identity':experiment,
         'source_packet_pin':pin(packet) if packet else None,'retained_native_pins':[],
         'native_observation_id':native,'facets':{k:facet() for k in FACETS},'factor_role':role,
         'result':{'direction':'unknown','description':facet(),'effect_size':facet(),
                   'comparator_orientation':'unresolved'},'cohort_dependency':None,
         'missing_information':['No independent scientific validation, canonical identity or materialization authority'],
         'provenance':'Explicit source-grounded Work B4 scientific annotation, not new model extraction'}


def bind(req,props,pairs,path,dependencies):
 data={'schema_version':VERSION,'question_identity':question_identity(req),'scientific_authorization':False,
       'producer':'interactive_Work_B4_source_bound_review_not_independent_validation',
       'propositions':props,'pairs':pairs,'dependency_pins':dependencies}
 p=write(path,data);req['scientific_comparison_assessments']=pin(p)
 req.pop('development_stop_after',None);req['model_stages'].pop('ai_review',None)
 return data


def source_dependencies(backend,props):
 deps=[pin(s['article_path']) for s in backend.catalog.specs]
 for p in props:
  if p.get('source_packet_pin'):
   packet=json.loads(Path(p['source_packet_pin']['path']).read_text());src=packet['source']
   if src.get('original_xml_path'):deps.append(pin(src['original_xml_path']))
 deps.append(pin(R/'runs/20261027_code_recovery_batch3_semantic_inclusion_offline/B2_scientific_contract_decision_memo.md'))
 return deps


def ar_comparison(path):
 b,c,req=ar_case(path);raw=json.loads(Path(req['scientific_inclusion_assessments']['path']).read_text());rows=[r for r in raw['assessments'] if r['scope_level']=='observation']
 native=json.loads((LIVE/'assessment/derived_response.json').read_text())['records'];props=[]
 for i,(row,record) in enumerate(zip(rows,native)):
  f=record['ExperimentalObservationV3'];ev=[s['evidence_span_id'] for s in row['evidence_spans']];res=f['observation']['evidence_span_ids']
  p=proposition('AR-'+str(i),row,native=f['observation_id'],experiment=f['experiment']['experiment_id'],role='genetic_manipulation');v=p['facets']
  for name,value in {'entity':f['measurement']['measured_entity_mention'],'factor':'Ar conditional deletion in MuSC',
      'shared_conditions':'CTX injury to TA in both groups; 1 month after gene ablation',
      'system':'young mouse TA regeneration','species':'mice','cell_type':'MuSC lineage',
      'tissue':'tibialis anterior skeletal muscle','endpoint':f['measurement']['endpoint_raw'],
      'genotype':'Pax7-CreERT2 / floxed Ar; native broader genotype text remains provisional'}.items():v[name]=facet(value,ev)
  v['tested_arm']=facet('AR(i)sat-/Y mice',ev)
  p['result']['description']=facet(f['observation']['observed_result'],res)
  p['missing_information']+=['Numerical effect size and exact P value unavailable in selected result text',
       'Original native linkage/readiness retained; no provisional link materialized']
  if i==2:
   v['focal_contrast']=facet('Conditional Ar deletion versus TAM-treated Cre-negative littermate control',ev)
   v['reference_arm']=facet('TAM-treated littermates without Pax7-CreERT2',ev)
   v['endpoint']=facet('Histological single-myofiber cross-sectional area',ev)
   v['time']=facet('7 dpi',ev);v['assay']=facet('Dystrophin delineation and QuPath/Groovy single-fiber CSA',ev)
   v['statistical_interpretation']=facet('Reported significant reduction; exact P and effect size unavailable',res)
   p['result'].update(direction='decrease',comparator_orientation='tested_vs_reference')
  elif i==3:
   v['time']=facet('28 dpi; separate contractile force endpoint',ev)
   v['statistical_interpretation']=facet('Reported significant reduction, exact P unavailable',res)
   p['result']['direction']='decrease';p['missing_information']+=['Comparator role not re-grounded by this bounded non-CSA packet']
  elif i==4:
   p['missing_information']+=['Native MuSC persistence anchor known incomplete; unchanged, direction not normalized']
  p['retained_native_pins']=[pin(LIVE/'assessment/validated_formal_v3.json')];props.append(p)
 deps=source_dependencies(b,props)+[pin(RELEASE/'source_evidence_catalog.json'),pin(RELEASE/'CSA/supplemental_source_binding_manifest.json'),pin(R/'runs/20261027_code_final_owner_authorized_CSA_linkage_live_probe/assessment/parsed_original_linkage_response.json')]
 bind(req,props,[],Path(path)/'scientific_comparison_inputs.json',deps);return b,c,req


def hif_comparison(path):
 b,c,req=hif_case(path);raw=json.loads(Path(req['scientific_inclusion_assessments']['path']).read_text());props=[]
 for pmc in ('PMC4024011','PMC7749157'):
  packet_path=HIF/pmc/'evidence_packet.json';packet=json.loads(packet_path.read_text());core=json.loads((HIF/pmc/'v3_core_draft.json').read_text());f=core['ExperimentalObservationV3'];row=next(r for r in raw['assessments'] if r['scope_identity']==f['observation_id']);ev=[s['evidence_span_id'] for s in packet['evidence_spans']]
  p=proposition(pmc,row,native=f['observation_id'],experiment=f['experiment']['experiment_id'],packet=packet_path,role='exposure');v=p['facets'];refs=ev[:2]
  specific={'PMC4024011':{'tested_arm':'5% O2 HCT116','reference_arm':'20% O2 HCT116','system':'HCT116 colon cancer cell line','cell_type':'HCT116','time':'72 hours','dose':'5% versus 20% O2','shared_conditions':'HCT116 cultured oxygen comparison; medium described in Methods'},
            'PMC7749157':{'tested_arm':'1% O2 A549 with DMSO','reference_arm':'normoxia A549 with DMSO','system':'A549 lung carcinoma cell line','cell_type':'A549','time':'24 hours','dose':'1% O2 versus normoxia; normoxia percentage not specified in selected caption','shared_conditions':'DMSO in selected arms; inhibitor-treated arms excluded'}}[pmc]
  for name,value in {**specific,'entity':'HIF-1α protein','endpoint':'HIF-1α protein abundance',
        'assay':'Western blot of cell protein lysate','factor':'source-specified reduced oxygen exposure',
        'focal_contrast':specific['tested_arm']+' versus '+specific['reference_arm']}.items():v[name]=facet(value,ev if name in ('assay','shared_conditions') else refs)
  p['result']['description']=facet('HIF-1α protein increases at 5% versus 20% O2' if pmc=='PMC4024011' else 'Caption HIF-1α normoxia/DMSO 1.00 ± 0.73; hypoxia/DMSO 6.83 ± 2.62, normalized to actin',refs)
  if pmc=='PMC7749157':p['result']['effect_size']=facet('Raw arm values 1.00 ± 0.73 and 6.83 ± 2.62; mean ± SEM, 3 independent experiments; no derived ratio',refs)
  p['result'].update(direction='increase',comparator_orientation='tested_vs_reference')
  p['missing_information']+=packet['unresolved_information'];props.append(p)
 evs=[[s['evidence_span_id'] for s in json.loads((HIF/pmc/'evidence_packet.json').read_text())['evidence_spans']] for pmc in ('PMC4024011','PMC7749157')]
 decisions={'biological_entity':('MATCH','Both selected caption/Results name HIF-1α protein; local provisional match only, no external canonical authority'),
  'intervention':('COMPATIBLE','Both manipulate oxygen tension, but 5% physioxia versus 1% hypoxia is not an identical dose'),
  'contrast':('COMPATIBLE','Selected reduced-oxygen arm versus own higher-oxygen reference; DMSO matched in the A549 contrast'),
  'endpoint':('MATCH','Both measure HIF-1α protein abundance; neither is mRNA nor transcriptional activity'),
  'assay':('COMPATIBLE','Western blots of cell lysate support directional protein comparison; absolute quantitation equivalence not established'),
  'system':('COMPATIBLE','Both selected experiments are cultured cancer cells; colon HCT116 and lung A549 remain distinct contexts'),
  'conditions':('COMPATIBLE','Oxygen dose and duration differ; permits bounded broad-question alignment review, not effect-size pooling'),
  'source_support':('COMPATIBLE','Exact original captions and Results support direction and arm assignment; significance and mechanistic inference remain limited')}
 axes=[{'dimension':key,'decision':decisions[key][0],'reason':decisions[key][1],'evidence_refs_a':evs[0],'evidence_refs_b':evs[1]} for key in AXES]
 ctx=[]
 for name,status,reason in [('endpoint','same','Both explicitly assay HIF-1α protein abundance'),('assay','same','Both use Western blot; exact antibody equivalence is not established'),('system','different','HCT116 colon versus A549 lung cancer cells'),('time','different','Caption exposure 72 hours versus 24 hours'),('dose','different','5% versus 20% O2 and 1% versus normoxia; do not invent normoxia concentration'),('reference_arm','different','Each experiment has its own oxygen reference and A549 DMSO condition'),('species','missing_both','Species not independently normalized from cell-line names in these selected packets'),('genotype','missing_both','Genotype not established in selected scope')]:ctx.append({'axis':name,'facet':name,'status':status,'reason':reason})
 pairs=[{'left':props[0]['key'],'right':props[1]['key'],'axes':axes,'contexts':ctx,'producer':'interactive_Work_B4_source_bound_assessment_not_independent'}]
 bind(req,props,pairs,Path(path)/'scientific_comparison_inputs.json',source_dependencies(b,props)+[pin(HIF/p['key']/'v3_core_draft.json') for p in props]);return b,c,req


def trib_comparison(path):
 b,c,req=trib_case(path);raw=json.loads(Path(req['scientific_inclusion_assessments']['path']).read_text());original=next(r for r in raw['assessments'] if r['scope_level']=='observation')
 packet_path=E/'E3/right/evidence_packet.json';packet=json.loads(packet_path.read_text());ev=[s['evidence_span_id'] for s in packet['evidence_spans']];props=[];extra=[]
 for group in ('low-risk','high-risk','all-patient'):
  for endpoint in ('overall survival','event-free survival'):
   if group=='low-risk' and endpoint=='overall survival':row=original
   else:
    row=deepcopy(original);row['scope_identity']=original['scope_identity']+':'+group+':'+endpoint
    for d in row['dimension_assessments']:
     if d['dimension']=='endpoint':d.update(source_value=endpoint,assessment='SUPPORTED' if endpoint=='overall survival' else 'MISMATCH')
    row['reason']='Exact frozen Figure 2/3 Results subgroup and endpoint; event-free survival is a distinct endpoint';extra.append(row)
   p=proposition('TRIB3:'+group+':'+endpoint,row,experiment=None,packet=packet_path,role='observational_biomarker_stratification')
   p['cohort_dependency']='frozen_source:'+packet['source']['pmcid']+':parent_archival_NB_cohort';v=p['facets']
   for name,value in {'entity':'TRIB3 IHC protein positivity biomarker','factor':'Observed TRIB3-positive versus TRIB3-negative strata',
      'tested_arm':'TRIB3-positive '+group+' NB patients','reference_arm':'TRIB3-negative '+group+' NB patients',
      'focal_contrast':'TRIB3-positive versus TRIB3-negative within '+group+' neuroblastoma cohort',
      'system':group+' neuroblastoma patients','species':'human patients','tissue':'archival FFPE neuroblastoma tumor samples',
      'endpoint':endpoint,'assay':'Kaplan-Meier survival / log-rank test by TRIB3 IHC positivity',
      'shared_conditions':'Archival clinical cohort; parent sample count 56 is not subgroup n'}.items():v[name]=facet(value,ev)
   pvalue={'low-risk':{'overall survival':'.034','event-free survival':'.032'},'high-risk':{'overall survival':'.799','event-free survival':'.448'},'all-patient':{'overall survival':'.202','event-free survival':'.172'}}[group][endpoint]
   result='Positive association with survival' if group=='low-risk' else 'No statistically significant survival association reported'
   v['statistical_interpretation']=facet(result+'; P = '+pvalue,ev[3:] if group!='all-patient' else [ev[-1]])
   p['result'].update(direction='increase' if group=='low-risk' else 'not_significant',comparator_orientation='tested_vs_reference',description=facet(result+'; '+endpoint+'; P='+pvalue,ev[3:] if group!='all-patient' else [ev[-1]]))
   p['retained_native_pins']=[b.annotations[packet['source']['pmcid']]['core']]
   p['missing_information']+=['Native V3 original XML hash does not bind ArticleJSON projection; no native Core fabricated',
     'IHC expression cutoff, subgroup n, adjusted hazard ratio and follow-up endpoint definitions remain incomplete',
     'Association from biomarker grouping, not an intervention or causal survival effect'];props.append(p)
 bind_assessments(req,raw['assessments']+extra,Path(path)/'B4_inclusion_assessments.json')
 bind(req,props,[],Path(path)/'scientific_comparison_inputs.json',source_dependencies(b,props));return b,c,req


def null_comparison(path):
 b,c,req=hif_null_case(path);raw=json.loads(Path(req['scientific_inclusion_assessments']['path']).read_text());row=next(r for r in raw['assessments'] if r['scope_level']=='observation' and r['scope_identity'].startswith('source_evidence_packet:'))
 packet_path=E/'E1/left/evidence_packet.json';packet=json.loads(packet_path.read_text());ev=[s['evidence_span_id'] for s in packet['evidence_spans']]
 p=proposition('HIF:VEGF_mRNA_null',row,experiment=None,packet=packet_path,role='exposure');v=p['facets']
 for name,value in {'entity':'VEGF transcript (VEGFA identity not established)','endpoint':'VEGF mRNA abundance',
  'assay':'qRT-PCR','factor':'Reduced oxygen exposure','focal_contrast':'5% versus 20% O2 HCT116 cells',
  'tested_arm':'HCT116 at 5% O2','reference_arm':'HCT116 at 20% O2','system':'HCT116 colon cancer cells',
  'cell_type':'HCT116','time':'24 hours','dose':'5% versus 20% O2',
  'statistical_interpretation':'VEGF P=0.7 (ns), unpaired t-test; no equivalence test'}.items():v[name]=facet(value,ev)
 p['result'].update(direction='not_significant',description=facet('VEGF levels did not increase; caption P=0.7 (ns); effect size unavailable',ev[:2]),comparator_orientation='tested_vs_reference')
 p['missing_information']+=['No native V3 reconstruction or reported experiment ID for this packet','Nonsignificance is not a zero effect, equality, or a direction opposite to HIF-1α protein']
 bind(req,[p],[],Path(path)/'scientific_comparison_inputs.json',source_dependencies(b,[p]));return b,c,req
