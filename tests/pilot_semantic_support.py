"""Authentic frozen linkage replay and explicit source-bound semantic annotations."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json
from code_engine.discovery.ai_review_shadow import file_hash,content_hash
from tests.pilot_comparison_support import ar_comparison,hif_comparison,trib_comparison,null_comparison
from tests.pilot_inclusion_support import write,pin,R
from tests.pilot_linkage_support import OID,RELEASE

RUN=R/'runs/20261028_code_recovery_batch4_6_conservative_grounding_offline'
LIVE=R/'runs/20261027_code_final_owner_authorized_CSA_linkage_live_probe'
OWNER=RUN/'owner_decision_v1.json'

def context(prepared):
 packet=prepared['input'];roles={f['local_factor_id']:f['identity'] for f in packet['components']['factors']}
 catalog=json.loads((RELEASE/'source_evidence_catalog.json').read_text());a=catalog['aliases'];ev=[s['evidence_span_id'] for s in packet['evidence_spans']]
 def role(local,kind,refs,reason):return {'component_identity':roles[local],'role':kind,'evidence_refs':refs,'reason':reason}
 m=packet['components']['measurements'][0]['identity'];result=packet['components']['results'][0]['identity']
 annotation={**{k:packet[k] for k in ('source_identity','observation_identity','core_revision_identity','experiment_scope_identity')},
  'design':'interventional','measurement_identities':[m],
  'roles':[
   role('factor_0','FOCAL_INTERVENTION',['span_12ca872baae54d99be16',a['S0001'],a['S0002']],'Source Results define conditional Ar deletion; F1C binds the tested group to this endpoint'),
   role('factor_1','SHARED_CONDITION',['span_0d34bb1ec674b13c7630',a['S0005']],'Both groups receive CTX TA injury; there is no CTX/no-CTX contrast'),
   role('factor_2','REFERENCE_ARM',[a['S0004'],a['CAP_C']],'Exact no-Cre TAM-treated littermate control definition and F1C control arm'),
   role('factor_3','TESTED_ARM',[a['CAP_C']],'AR(i)sat-/Y is the tested group in F1C, not the result reference'),
   role('factor_4','COHORT_DESCRIPTOR',[a['S0005']],'Young three-month cohort is a descriptor; no measured baseline or age contrast')],
  'orientations':[{'result_identity':result,'tested_arm_identity':roles['factor_3'],'reference_arm_identity':roles['factor_2'],
     'evidence_refs':['span_159818cbf6807defd27a',a['S0004'],a['CAP_C']],'reason':'Source reduction versus control plus exact tested/control group definitions'}],
  'applicability':[{'measurement_identity':m,'experiment_scope_identity':packet['experiment_scope_identity'],'evidence_refs':ev,
     'status':'SOURCE_BOUND_PROVISIONAL','reason':'Existing verified F1C xref/panel, exact group Results and histological method scope; no independent scientific approval'}],
  'baseline_bindings':[],'ambiguities':[],'producer':'explicit_source_bound_Work_annotation_reusing_B4_B4_5_evidence_not_independent_review'}
 return {'annotation':annotation,'historical_provider_requests':[
  {'purpose':'original_V3_extraction','request':pin(R/'runs/20261023_code_renewed_owner_ar_only_live_v3_probe/live/request.canonical.json')},
  {'purpose':'later_linkage_with_supplement','request':pin(LIVE/'approved_request.canonical.json')}],
  'raw_original_provider_response':pin(LIVE/'live/attempt_1/response_body.raw')}


def real_inputs():
 from code_engine.orchestration.pilot_linkage import assess_stage
 prepared=json.loads((LIVE/'source_V3_Core_pre_dispatch_revalidation.json').read_text())
 raw=json.loads((LIVE/'live/attempt_1/response_body.raw').read_text());response=json.loads(raw['choices'][0]['message']['content'])
 assert response==json.loads((LIVE/'assessment/parsed_original_linkage_response.json').read_text())
 outcome=assess_stage(prepared,response,proposal_origin='provider_linkage_response')
 ledger=json.loads((R/'runs/20261028_code_recovery_batch4_scientific_comparison_offline/release_v3/AR/cases/B3-AR/scientific_inclusion_final.json').read_text())
 inclusion=next(x for x in ledger['rows'] if x['scope_level']=='observation' and x['scope_identity']==OID)
 return prepared,outcome,context(prepared),inclusion


def attach_config(req,path,observations=None):
 now=datetime.now(timezone.utc)
 cfg={'schema_version':'conservative_grounding_configuration_v1','owner_decision':pin(OWNER),
      'issued_at':now.isoformat(),'expires_at':(now+timedelta(days=1)).isoformat(),'observations':observations or {}}
 p=write(Path(path)/'semantic_config.json',cfg);req['semantic_grounding']=pin(p);return cfg


def ar_semantic(path):
 backend,cfg,req=ar_comparison(path);prepared,outcome,ctx,inc=real_inputs()
 cp=write(Path(path)/'source_semantic_annotation.json',ctx)
 attach_config(req,path,{OID:pin(cp)})
 # Explicit offline retained-provider replay, not a new provider request or a
 # Work assessment relabelled as model extraction. Bind the actual raw response.
 response=outcome['original_response'];wrapper=write(Path(path)/'original_provider_replay.json',{'response':response,'original_raw_response':pin(LIVE/'live/attempt_1/response_body.raw')})
 backend.linkage_replays[OID]=pin(wrapper)
 existing=backend.linkage_replay
 def replay(oid):
  if oid!=OID:return existing(oid)
  actual=json.loads((LIVE/'live/attempt_1/response_body.raw').read_text())
  assert json.loads(actual['choices'][0]['message']['content'])==response
  return {'response':response,'proposal_origin':'provider_linkage_response','artifact':pin(wrapper),
     'historical_provider_response':pin(LIVE/'live/attempt_1/response_body.raw'),'actual_new_API_dispatches':0}
 backend.linkage_replay=replay
 return backend,cfg,req


def cross_semantic(factory,path):
 b,c,r=factory(path);attach_config(r,path);return b,c,r
