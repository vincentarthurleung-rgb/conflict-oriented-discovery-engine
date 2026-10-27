"""Bounded display projections; original hash-bound review artifacts stay intact."""
from collections import Counter
import json

def case_display(package):
 p={k:v for k,v in package.items() if k not in ('artifacts','pair_packages','sources','run_manifest','costs')}
 p.update(display_projection=True,source_count=len(package['sources']),sources=[],pair_count=len(package['pair_packages']),pair_packages=[],artifact_count=len(package['artifacts']))
 m=package['run_manifest'];p['run_manifest']={k:m[k] for k in ('case_id','question','has_deterministic_model_stubs','stages','terminal_state','terminal_reason','input_sha256')}
 p['costs']={k:v for k,v in package['costs'].items() if k not in ('requests',)};p['costs']['request_count']=len(package['costs']['requests']);p['costs']['request_states']=dict(Counter(r['state'] for r in package['costs']['requests']))
 p['scientific_comparison_summary']=m.get('scientific_comparison_summary')
 p['scientific_comparison_artifacts']=[a for a in package['artifacts'] if a['role'] in ('scientific_comparison.json','scientific_context_attribution.json','scientific_qualification.json','scientific_hypothesis_constraints.json')]
 p['scientific_inclusion_summary']=m.get('scientific_inclusion_summary')
 p['scientific_inclusion_artifacts']=[a for a in package['artifacts'] if a['role'] in ('scientific_inclusion_final.json','scientific_inclusion_coverage.json','semantic_intake_trace.json')]
 p['linkage_stage_count']=sum(a['role'].endswith('_linkage_outcome.json') for a in package['artifacts'])
 p['scientific_stage_completion']=m.get('scientific_stage_completion')
 p['dataset_version']=m.get('dataset_export',{}).get('dataset_version');return p

def scientific_page(package,offset=0,limit=1):
 if offset<0 or not 1<=limit<=3:raise ValueError('invalid_evidence_page')
 comparison=next((a for a in package['artifacts'] if a['role']=='scientific_comparison.json'),None)
 if comparison and json.loads(comparison['utf8']).get('propositions'):
  d=json.loads(comparison['utf8'])
  items=[{'kind':'provisional_scientific_proposition','proposition':p} for p in d['propositions']]
  items.extend({'kind':'provisional_scientific_pair','pair':p} for p in d['pairs'])
  return {'case_id':package['case_id'],'package_sha256':package['package_sha256'],'offset':offset,'limit':limit,
          'total':len(items),'items':items[offset:offset+limit],'display_projection':True,
          'scientific_authorization':False}
 pairs=package['pair_packages'];selected=[]
 # A single source can have genuine candidate evidence even without a paper pair.
 if not pairs:
  inputs={a['role'].removesuffix('_linkage_input.json'):a for a in package['artifacts'] if a['role'].endswith('_linkage_input.json')}
  outcomes=[a for a in package['artifacts'] if a['role'].endswith('_linkage_outcome.json')]
  items=[]
  for a in outcomes[offset:offset+limit]:
   key=a['role'].removesuffix('_linkage_outcome.json');items.append({'kind':'provisional_linkage_evidence','original_evidence':inputs.get(key),'candidate_decisions':a,'scientific_authorization':False,'human_gold':False,'strict_core_eligible':False})
  return {'case_id':package['case_id'],'package_sha256':package['package_sha256'],'offset':offset,'limit':limit,'total':len(outcomes),'items':items,'source_count':len(package['sources']),'display_projection':True}
 for source in pairs[offset:offset+limit]:
  pair={k:v for k,v in source.items() if k!='blobs'}
  pair['blobs']=[b for b in source['blobs'] if b['role']=='prompt' or not b['role'].endswith(':source')]
  pair['display_projection']=True;selected.append(pair)
 inputs={a['role'].removesuffix('_linkage_input.json'):a for a in package['artifacts'] if a['role'].endswith('_linkage_input.json')}
 outcomes=[a for a in package['artifacts'] if a['role'].endswith('_linkage_outcome.json')]
 linkage_items=[{'kind':'provisional_linkage_evidence','original_evidence':inputs.get(a['role'].removesuffix('_linkage_outcome.json')),'candidate_decisions':a,'scientific_authorization':False} for a in outcomes[offset:offset+limit]]
 return {'case_id':package['case_id'],'package_sha256':package['package_sha256'],'offset':offset,'limit':limit,'total':len(pairs),'items':selected,'linkage_evidence_items':linkage_items,'linkage_total':len(outcomes),'source_count':len(package['sources']),'display_projection':True}
