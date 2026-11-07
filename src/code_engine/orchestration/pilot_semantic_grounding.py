"""Conservative D1–D5 sidecars and receipt mechanics; no machine issuer.

Consumes explicit source-bound semantic annotations, not a text classifier.
Never mutates native records or supplies new authority to materialize_linkage.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
import hashlib,json

from pydantic import BaseModel,ConfigDict,Field
from code_engine.discovery.ai_review_shadow import ShadowAuthority,content_hash,file_hash
from code_engine.orchestration.pilot_inclusion import read_pin
from code_engine.orchestration.pilot_linkage import candidate_input
from code_engine.extraction_assets.experimental_core.source_resolution_models import SourceResolutionEnvelope

VERSION='conservative_source_semantic_assessment_v1'
RECEIPT_VERSION='provisional_grounding_receipt_v1'
ISSUER='code_engine.orchestration.pilot_semantic_grounding:assess_candidates'
POLICY_PATH=Path(__file__).resolve().parents[3]/'docs/contracts/source_semantic_grounding_assessment_v1.md'
FORBIDDEN=('machine_reuse_issuance','validated_source_grounded','active_deterministic_grounding_version',
           'scientific_authorization','human_gold','strict_core','formal_L4_qualification','causal_qualification')
NO_AUTHORITY={**ShadowAuthority().model_dump(mode='json'),'machine_reuse_authorized':False,
              'formal_conflict_confirmed':False,'causal_qualification':False}

class Strict(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True,frozen=True)

class Role(Strict):
 component_identity:str
 role:Literal['FOCAL_INTERVENTION','EXPOSURE','OBSERVATIONAL_GROUP','SHARED_CONDITION','TESTED_ARM',
              'REFERENCE_ARM','COHORT_DESCRIPTOR','MEASURED_BASELINE','UNRESOLVED']
 evidence_refs:list[str]=Field(min_length=1)
 reason:str=Field(min_length=12)

class Orientation(Strict):
 result_identity:str
 tested_arm_identity:str
 reference_arm_identity:str
 evidence_refs:list[str]=Field(min_length=1)
 reason:str=Field(min_length=12)

class Applicability(Strict):
 measurement_identity:str
 experiment_scope_identity:str
 evidence_refs:list[str]=Field(min_length=1)
 status:Literal['SOURCE_BOUND_PROVISIONAL','AMBIGUOUS','UNRESOLVED']
 reason:str=Field(min_length=12)

class SemanticAnnotation(ShadowAuthority):
 schema_version:Literal['source_bound_semantic_annotation_v1']='source_bound_semantic_annotation_v1'
 source_identity:dict
 observation_identity:str
 core_revision_identity:str
 experiment_scope_identity:str
 design:Literal['interventional','observational','unknown']
 measurement_identities:list[str]
 roles:list[Role]
 orientations:list[Orientation]
 applicability:list[Applicability]
 baseline_bindings:list[Orientation]=Field(default_factory=list)
 ambiguities:list[str]=Field(default_factory=list)
 producer:str=Field(min_length=12)

class IssuerPermission(Strict):
 issuer_identity:str
 issuer_kind:Literal['software_provisional_assessor','SOFTWARE_FIXTURE']
 scopes:list[str]
 authorization_reference:str
 enabled:bool
 environment:Literal['development_provisional','software_fixture']

class Receipt(ShadowAuthority):
 schema_version:Literal['provisional_grounding_receipt_v1']=RECEIPT_VERSION
 binding:dict
 assessment:dict
 assessment_sha256:str
 policy:dict
 owner_decision:dict
 issuer:IssuerPermission
 validator_implementation:dict
 issued_at:str
 expires_at:str
 revision_identity:str
 supersedes_revision_identity:str|None=None
 revoked:bool=False


def implementation_identity():
 return {'path':str(Path(__file__).resolve()),'sha256':file_hash(Path(__file__))}


def input_identity(request):
 from code_engine.orchestration.pilot_comparison import input_identity as transitive
 return content_hash({'version':VERSION,'inputs':transitive({'scientific_comparison_assessments':request.get('semantic_grounding')})})


def owner_scope(pin):
 d=read_pin(pin)
 identity=d.get('decision_identity');payload={k:v for k,v in d.items() if k!='decision_identity'}
 if identity!='owner_conservative_semantic_scope_v1:'+content_hash(payload):raise ValueError('owner_decision_identity_mismatch')
 if d.get('schema_version')!='owner_conservative_semantic_scope_v1':raise ValueError('owner_scope_version_mismatch')
 p=d.get('permissions',{})
 if p.get('provisional_semantic_assessment') is not True or p.get('receipt_verification_infrastructure') is not True or any(p.get(k) is not False for k in FORBIDDEN):
  raise ValueError('owner_scope_cannot_enable_scientific_issuance')
 if d.get('D6')!='OPTION_A_RETAIN_REVIEWABLE_UNKNOWN' or d.get('trusted_machine_issuance_policy')!='NOT_APPROVED':raise ValueError('owner_scope_scientific_policy_not_permitted')
 for ref in [d['owner_instruction'],d['instruction_origin'],d['assessment_policy'],d['canonical_B4_5_acceptance'],*d['review_basis'].values()]:
  if file_hash(Path(ref['path']))!=ref['sha256']:raise ValueError('owner_scope_dependency_hash_drift')
 if d['assessment_policy']['sha256']!=file_hash(POLICY_PATH):raise ValueError('installed_semantic_policy_not_owner_bound')
 return d


def _annotation(prepared,raw):
 a=SemanticAnnotation.model_validate(raw);packet=prepared['input']
 if any(getattr(a,k)!=packet[k] for k in ('source_identity','observation_identity','core_revision_identity','experiment_scope_identity')):
  raise ValueError('semantic_annotation_revision_or_source_mismatch')
 refs={s['evidence_span_id'] for s in packet['evidence_spans']}
 factors={x['identity'] for x in packet['components']['factors']};measure={x['identity'] for x in packet['components']['measurements']};results={x['identity'] for x in packet['components']['results']}
 if not set(a.measurement_identities)<=measure:raise ValueError('semantic_measurement_identity_mismatch')
 for role in a.roles:
  if role.component_identity not in factors or not set(role.evidence_refs)<=refs:raise ValueError('semantic_role_endpoint_or_evidence_mismatch')
 for o in a.orientations+a.baseline_bindings:
  if o.result_identity not in results or o.tested_arm_identity not in factors or o.reference_arm_identity not in factors or not set(o.evidence_refs)<=refs:
   raise ValueError('semantic_orientation_endpoint_or_evidence_mismatch')
 for x in a.applicability:
  if x.measurement_identity not in measure or x.experiment_scope_identity!=packet['experiment_scope_identity'] or not set(x.evidence_refs)<=refs:
   raise ValueError('semantic_scope_or_evidence_mismatch')
 return a


def _binding(prepared,proposal,index,outcome,context):
 packet=prepared['input'];links=(outcome.get('sidecar') or {}).get('native_candidate_linkages',[])
 match=next((x for x in links if (x['relation_type'],x['source_ref'],x['target_ref'])==(proposal['relation_type'],proposal['source_ref'],proposal['target_ref'])),None)
 return {'original_proposal_index':index,'original_proposal_id':proposal.get('proposal_id'),
  'genuine_candidate_identity':match['identity'] if match else None,'original_proposal':proposal,
  'original_response_sha256':content_hash(outcome['original_response']),
  'observation_identity':packet['observation_identity'],'core_revision_identity':packet['core_revision_identity'],
  'source_identity':packet['source_identity'],'source_artifact_sha256':packet['source_artifact_sha256'],
  'source_blocks_sha256':packet['source_blocks_sha256'],'evidence_spans_sha256':content_hash(packet['evidence_spans']),
  'experiment_scope_identity':packet['experiment_scope_identity'],'components_sha256':content_hash(packet['components']),
  'source_envelopes_sha256':content_hash(prepared.get('source_resolution_envelopes',[])),
  'semantic_annotation_sha256':content_hash(context),'input_sha256':content_hash(packet)}


def _assess(prepared,p,index,outcome,annotation,inclusion,exposure):
 packet=prepared['input'];native=prepared['assembled']['envelope']['ExperimentalCore'];parts=packet['components']
 ids={k:{x['identity'] for x in v} for k,v in parts.items()};known={s['evidence_span_id'] for s in packet['evidence_spans']}
 relation=p['relation_type'];src=p['source_ref'];tgt=p['target_ref'];refs=set(p['evidence_refs'])
 endpoints={'factor_applies_to_measurement':(ids['factors'],ids['measurements']),
  'measurement_produces_result':(ids['measurements'],ids['results']),
  'result_compared_against_factor':(ids['results'],ids['factors']),
  'result_uses_baseline':(ids['results'],ids['factors']),
  'observation_belongs_to_experiment_scope':({packet['observation_identity'],packet['core_revision_identity']},{packet['experiment_scope_identity']})}
 roles={};conflicts=[]
 if annotation:
  for r in annotation.roles:
   if r.component_identity in roles and roles[r.component_identity].role!=r.role:conflicts.append(r.component_identity)
   roles[r.component_identity]=r
  for values in (annotation.orientations,annotation.baseline_bindings):
   seen={}
   for o in values:
    value=(o.tested_arm_identity,o.reference_arm_identity)
    if o.tested_arm_identity==o.reference_arm_identity or (o.result_identity in seen and seen[o.result_identity]!=value):conflicts.append(o.result_identity)
    seen[o.result_identity]=value
 structure=next((x for x in outcome.get('rejected_proposals',[]) if x['proposal_index']==index),None)
 row={**NO_AUTHORITY,'original_proposal_index':index,'original_proposal':p,
  'structural_result':'REJECTED' if structure else 'ACCEPTED','structural_rejection':structure,
  'semantic_status':'ABSTAIN','reason_codes':[],'evidence_refs':p['evidence_refs'],
  'historical_provider_exposure':[exposure[r] for r in p['evidence_refs'] if r in exposure],
  'inclusion_revision':inclusion.get('revision_identity'),'inclusion_decision':inclusion.get('decision'),
  'measurement_classification_as_recorded':[x.get('measurement_semantic_level') for x in parts['measurements']],
  'new_measurement_classification':None,'interpretation':'Source-bound provisional relation only, no independent verification or causal authority',
  'causal_mode':'observational_association' if annotation and annotation.design=='observational' else 'unresolved_or_source_intervention_only',
  'source_semantics_origin':annotation.producer if annotation else None}
 def decide(status,code):row.update(semantic_status=status,reason_codes=[code]);return row
 if relation not in endpoints or src not in endpoints[relation][0] or tgt not in endpoints[relation][1]:return decide('UNSUPPORTED','INVALID_TYPED_ENDPOINT')
 if not refs or not refs<=known:return decide('ABSTAIN','POSITIVE_SOURCE_EVIDENCE_MISSING')
 if inclusion.get('decision')!='INCLUDED':return decide('ABSTAIN','B3_'+str(inclusion.get('decision','UNASSESSED'))+'_NOT_OVERRIDDEN')
 if annotation is None:return decide('ABSTAIN','EXPLICIT_SOURCE_SEMANTIC_ANNOTATION_MISSING')
 if annotation.ambiguities or conflicts:return decide('AMBIGUOUS','CONFLICTING_OR_UNRESOLVED_SOURCE_INTERPRETATION')
 if not annotation.measurement_identities:return decide('ABSTAIN','MEASUREMENT_IDENTITY_MISSING')
 if not exposure or any(r not in exposure for r in refs):return decide('ABSTAIN','HISTORICAL_EXPOSURE_ACCOUNTING_MISSING')
 # Applicability is a supplied source-bound Work assessment, not a new authority.
 if not annotation.applicability or any(x.status!='SOURCE_BOUND_PROVISIONAL' for x in annotation.applicability):
  return decide('ABSTAIN','EXPERIMENT_MEASUREMENT_APPLICABILITY_UNRESOLVED')
 measurement=tgt if relation=='factor_applies_to_measurement' else src if relation=='measurement_produces_result' else next((x['measurement_ref'] for x in parts['results'] if x['identity']==src),None)
 if measurement not in annotation.measurement_identities and relation!='observation_belongs_to_experiment_scope':return decide('ABSTAIN','MEASUREMENT_NOT_IN_ASSESSED_SCOPE')
 scope=next((x for x in annotation.applicability if x.measurement_identity==measurement),None)
 if measurement and (scope is None or not refs.intersection(scope.evidence_refs)):
  return decide('ABSTAIN','POSITIVE_ENDPOINT_SCOPE_SUPPORT_MISSING')
 row['applicability']=[x.model_dump(mode='json') for x in annotation.applicability]
 if relation=='measurement_produces_result':
  if any(x['identity']==tgt and x.get('measurement_ref')==src for x in native['results']):return decide('EXISTING_NATIVE_RELATION','DUPLICATE_NATIVE_MEASUREMENT_RESULT')
  return decide('ABSTAIN','EXPLICIT_NEW_MEASUREMENT_RESULT_BINDING_REQUIRED')
 factor=src if relation=='factor_applies_to_measurement' else tgt
 role=roles.get(factor)
 if relation=='observation_belongs_to_experiment_scope':return decide('ABSTAIN','EXPLICIT_OBSERVATION_SCOPE_ASSESSMENT_REQUIRED')
 if role is None:return decide('ABSTAIN','SOURCE_BOUND_COMPONENT_ROLE_UNRESOLVED')
 row['source_assessed_role']=role.model_dump(mode='json')
 if not refs.intersection(role.evidence_refs):return decide('ABSTAIN','PROPOSED_ROLE_POSITIVE_EVIDENCE_ABSENT')
 if relation=='result_uses_baseline':
  if role.role=='COHORT_DESCRIPTOR':return decide('UNSUPPORTED','COHORT_IS_NOT_MEASURED_BASELINE')
  if role.role!='MEASURED_BASELINE' or not any(o.result_identity==src and o.reference_arm_identity==tgt and refs.intersection(o.evidence_refs) for o in annotation.baseline_bindings):return decide('ABSTAIN','MEASURED_BASELINE_BINDING_MISSING')
  return decide('SUPPORTED_PROVISIONAL','EXPLICIT_MEASURED_BASELINE_CANDIDATE_ONLY')
 if relation=='factor_applies_to_measurement':
  if role.role in ('SHARED_CONDITION','COHORT_DESCRIPTOR'):return decide('CONTEXT_ONLY','SHARED_CONDITION_NOT_FOCAL_CONTRAST' if role.role=='SHARED_CONDITION' else 'COHORT_CONTEXT_NO_ESTABLISHED_CONTRAST')
  contrasts=[o for o in annotation.orientations
   if any(x['identity']==o.result_identity and x.get('measurement_ref')==tgt for x in parts['results'])
   and refs.intersection(o.evidence_refs)
   and roles.get(o.tested_arm_identity) and roles[o.tested_arm_identity].role=='TESTED_ARM'
   and roles.get(o.reference_arm_identity) and roles[o.reference_arm_identity].role=='REFERENCE_ARM']
  if role.role=='OBSERVATIONAL_GROUP':
   if annotation.design!='observational':return decide('AMBIGUOUS','OBSERVATIONAL_ROLE_DESIGN_CONFLICT')
   if not contrasts:return decide('ABSTAIN','MEASUREMENT_SPECIFIC_TESTED_REFERENCE_CONTRAST_MISSING')
   return decide('SUPPORTED_PROVISIONAL','OBSERVATIONAL_GROUP_ASSOCIATION_NOT_ASSIGNED_INTERVENTION')
  if role.role not in ('FOCAL_INTERVENTION','EXPOSURE'):return decide('ABSTAIN','FOCAL_CONTRAST_NOT_ESTABLISHED')
  if annotation.design=='observational':return decide('UNSUPPORTED','OBSERVATIONAL_GROUP_CANNOT_BECOME_ASSIGNED_INTERVENTION')
  if annotation.design=='unknown':return decide('ABSTAIN','STUDY_DESIGN_UNRESOLVED')
  if not contrasts:return decide('ABSTAIN','MEASUREMENT_SPECIFIC_TESTED_REFERENCE_CONTRAST_MISSING')
  return decide('SUPPORTED_PROVISIONAL','SOURCE_SUPPORTED_FOCAL_CONTRAST_CANDIDATE')
 orientation=next((o for o in annotation.orientations if o.result_identity==src),None)
 row['comparison_orientation']=orientation.model_dump(mode='json') if orientation else None
 if orientation is None:return decide('ABSTAIN','RESULT_REFERENCE_ORIENTATION_UNRESOLVED')
 if tgt==orientation.tested_arm_identity:return decide('UNSUPPORTED','TESTED_ARM_IS_NOT_ITS_OWN_REFERENCE')
 if tgt!=orientation.reference_arm_identity or role.role!='REFERENCE_ARM':return decide('ABSTAIN','AFFIRMATIVE_REFERENCE_ARM_SUPPORT_MISSING')
 if not refs.intersection(orientation.evidence_refs):return decide('ABSTAIN','RESULT_REFERENCE_POSITIVE_EVIDENCE_ABSENT')
 return decide('SUPPORTED_PROVISIONAL','SOURCE_SUPPORTED_REFERENCE_CANDIDATE')


def _stamp(value):
 d=datetime.fromisoformat(value.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('receipt_timezone_required')
 return d


def provisional_permission(decision):
 return IssuerPermission(issuer_identity=ISSUER,issuer_kind='software_provisional_assessor',
  scopes=['provisional_provenance'],authorization_reference=decision['decision_identity'],enabled=True,environment='development_provisional').model_dump(mode='json')


def make_receipt(binding,assessment,*,decision_pin,decision,issued_at,expires_at):
 issuer=provisional_permission(decision)
 value={**ShadowAuthority().model_dump(mode='json'),'schema_version':RECEIPT_VERSION,
  'binding':binding,'assessment':assessment,'assessment_sha256':content_hash(assessment),
  'policy':decision['assessment_policy'],'owner_decision':decision_pin,'issuer':issuer,
  'validator_implementation':implementation_identity(),'issued_at':issued_at,'expires_at':expires_at,
  'supersedes_revision_identity':None,'revoked':False}
 value['revision_identity']='provisional_grounding_receipt:'+content_hash(value)
 return Receipt.model_validate(value).model_dump(mode='json')


def verify_receipt(receipt,*,expected_binding,expected_assessment,owner_decision_pin,
                   now,permissions,current_revision,revoked_revisions=(),environment='development_provisional',requested_scope='provisional_provenance'):
 """Explicit trusted caller context; receipt claims never establish that context."""
 reasons=[];r=None
 try:
  if receipt is None:raise ValueError('receipt_missing')
  r=Receipt.model_validate(receipt);payload=r.model_dump(mode='json')
  if r.revision_identity!='provisional_grounding_receipt:'+content_hash({k:v for k,v in payload.items() if k!='revision_identity'}):reasons.append('receipt_revision_hash_mismatch')
  decision=owner_scope(owner_decision_pin)
  if r.owner_decision!=owner_decision_pin or r.policy!=decision['assessment_policy']:reasons.append('receipt_owner_policy_binding_mismatch')
  if r.issuer.authorization_reference!=decision['decision_identity']:reasons.append('issuer_authorization_reference_unverified')
  if r.binding!=expected_binding or r.assessment!=expected_assessment or r.assessment_sha256!=content_hash(expected_assessment):reasons.append('receipt_evidence_revision_or_assessment_mismatch')
  if r.validator_implementation!=implementation_identity():reasons.append('validator_implementation_changed')
  if _stamp(r.issued_at)>_stamp(now) or _stamp(r.expires_at)<=_stamp(now) or _stamp(r.expires_at)<=_stamp(r.issued_at):reasons.append('receipt_expired_or_invalid_time')
  if r.revoked or r.revision_identity in revoked_revisions:reasons.append('receipt_revoked')
  if r.revision_identity!=current_revision:reasons.append('receipt_unverified_or_superseded_revision')
  permission=next((IssuerPermission.model_validate(p) for p in permissions if p.get('issuer_identity')==r.issuer.issuer_identity),None)
  if permission is None or permission!=r.issuer or not permission.enabled:reasons.append('issuer_not_explicitly_permitted')
  if requested_scope!='provisional_provenance' or requested_scope not in r.issuer.scopes:reasons.append('receipt_scope_not_permitted')
  if environment!=r.issuer.environment or (r.issuer.issuer_kind=='SOFTWARE_FIXTURE' and environment!='software_fixture'):reasons.append('fixture_or_environment_scope_violation')
 except (ValueError,KeyError,TypeError,OSError) as error:reasons.append(type(error).__name__+':'+str(error))
 return {**NO_AUTHORITY,'schema_version':'provisional_grounding_verification_v1',
  'receipt_revision_identity':r.revision_identity if r else None,
  'status':'VERIFIED_PROVISIONAL_PROVENANCE_ONLY' if not reasons else 'BLOCKED',
  'provisional_provenance_verified':not reasons,'reason_codes':reasons,
  'verified_as_of':now,'expires_at':r.expires_at if r else None,'verification_is_time_bound_provenance_only':True,
  'issuer_authentication':'Explicit local producer permission + exact hashes; NOT independent scientific issuer authentication',
  'machine_issuance_policy':'DISABLED_NOT_APPROVED','independent_source_semantic_authorization':False,
  'verification_identity':content_hash({'receipt':receipt,'binding':expected_binding,'assessment':expected_assessment,
   'owner':owner_decision_pin,'permissions':permissions,'current_revision':current_revision,'revoked':list(revoked_revisions),'environment':environment,'requested_scope':requested_scope,'now':now,'implementation':implementation_identity()})}


def assess_candidates(prepared,outcome,*,context,decision_pin,inclusion,issued_at,expires_at):
 decision=owner_scope(decision_pin)
 packet=candidate_input(prepared['assembled'],source_artifact=prepared['source_artifact'],source_blocks=prepared['source_blocks'],additional_evidence=prepared['additional_evidence'])
 if packet!=prepared['input']:raise ValueError('semantic_prepared_source_input_drift')
 for envelope in prepared.get('source_resolution_envelopes',[]):SourceResolutionEnvelope.model_validate(envelope)
 annotation=_annotation(prepared,context['annotation']) if context.get('annotation') else None
 if inclusion.get('scope_identity')!=packet['observation_identity'] or inclusion.get('source_content_sha256')!=packet['source_identity']['fulltext_source_hash']:
  raise ValueError('semantic_inclusion_scope_mismatch')
 exposure={}
 for ref in context.get('historical_provider_requests',[]):
  body=read_pin(ref['request']);messages='\n'.join(x['content'] for x in body['messages'])
  for s in packet['evidence_spans']:
   entry=exposure.setdefault(s['evidence_span_id'],{'evidence_span_id':s['evidence_span_id'],'requests':[]})
   entry['requests'].append({'request':ref['request'],'purpose':ref['purpose'],
    'quote_present':s['text'] in messages,'anchor_present':bool(s.get('anchor_id') and s['anchor_id'] in messages) or s['evidence_span_id'] in messages,
    'later_evidence_not_retroactive':True})
 rows=[]
 for index,p in enumerate(outcome.get('original_response',{}).get('proposals',[])):
  assessment=_assess(prepared,p,index,outcome,annotation,inclusion,exposure)
  binding=_binding(prepared,p,index,outcome,context)
  receipt=make_receipt(binding,assessment,decision_pin=decision_pin,decision=decision,issued_at=issued_at,expires_at=expires_at)
  verification=verify_receipt(receipt,expected_binding=binding,expected_assessment=assessment,owner_decision_pin=decision_pin,
    now=datetime.now(timezone.utc).isoformat(),permissions=[provisional_permission(decision)],current_revision=receipt['revision_identity'])
  rows.append({'assessment':assessment,'receipt':receipt,'verification':verification})
 return {**NO_AUTHORITY,'schema_version':VERSION,'owner_decision_identity':decision['decision_identity'],
  'policy':decision['assessment_policy'],'rows':rows,'source_semantics_input':context,
  'materializer_decisions_unchanged':(outcome.get('sidecar') or {}).get('materialization_decisions',[]),
  'materialized_links':0,'missing_authority':['trusted_machine_reuse_issuer_not_approved','independent_scientific_authorization_not_granted','measurement_policy_remains_unknown_when_recorded'],
  'original_native_Core_sha256':content_hash(prepared['assembled']['envelope']['ExperimentalCore'])}


def assess_proposition(p):
 """Preserve B4 facts; no Core reconstruction or equivalence from raw strings."""
 mode='observational_association' if p['factor_role']=='observational_biomarker_stratification' else 'source_reported_exposure_or_intervention_only'
 reasons=[]
 if p['inclusion_decision']!='INCLUDED':reasons.append('B3_'+p['inclusion_decision']+'_NOT_OVERRIDDEN')
 if any(p['facets'][k]['value'] is None or str(p['facets'][k]['value']).casefold() in ('unknown','not_available','unresolved') for k in ('entity','endpoint')):reasons.append('MEASUREMENT_IDENTITY_UNRESOLVED')
 if p['native_core_revision'] is None:reasons.append('NATIVE_CORE_UNAVAILABLE_NO_FABRICATION')
 if p['result']['comparator_orientation']!='tested_vs_reference':reasons.append('REFERENCE_ORIENTATION_UNRESOLVED')
 return {**NO_AUTHORITY,'schema_version':VERSION+':proposition_guard','proposition_identity':p['proposition_identity'],
  'status':'ABSTAIN' if reasons else 'PROVISIONAL_SOURCE_CONTEXT_RETAINED','reason_codes':reasons,
  'scientific_mode':mode,'assigned_intervention_inferred':False,'context_fields':p['facets'],
  'result_as_recorded':p['result'],'null_is_not_equivalence_or_negative_effect':True,
  'publication':p['publication'],'experiment_identity':p['experiment_identity'],'cohort_dependency':p['cohort_dependency'],
  'same_direction_does_not_establish_exact_experiment_equivalence':True,
  'measurement_policy':'RAW_AND_REVIEWABLE_UNKNOWN_RETAINED_NO_NEW_CATEGORY'}


def run_semantic_stage(prepared,outcome,request,inclusion):
 """No missing semantic annotation is synthesized from labels or paragraph order."""
 absent={**NO_AUTHORITY,'schema_version':VERSION,'status':'ABSTAIN','rows':[],
  'verification':{'status':'BLOCKED','reason_codes':['SEMANTIC_RECEIPT_OR_SOURCE_INPUT_UNAVAILABLE'],'machine_reuse_authorized':False},
  'missing_authority':['machine_reuse_issuance_DISABLED_NOT_APPROVED'],'materialized_links':0}
 if not request.get('semantic_grounding'):
  return {**absent,'reason_codes':['OWNER_BOUND_SEMANTIC_CONFIGURATION_ABSENT']}
 cfg=read_pin(request['semantic_grounding']);owner_scope(cfg['owner_decision'])
 oid=prepared['input']['observation_identity'] if prepared else None
 entry=cfg.get('observations',{}).get(oid)
 if not prepared or 'original_response' not in outcome or not entry:
  return {**absent,'reason_codes':['SOURCE_ANNOTATION_OR_STRUCTURAL_PROPOSALS_UNAVAILABLE']}
 context=read_pin(entry)
 result=assess_candidates(prepared,outcome,context=context,decision_pin=cfg['owner_decision'],
   inclusion=inclusion,issued_at=cfg['issued_at'],expires_at=cfg['expires_at'])
 return {**result,'status':'PROVISIONAL_ASSESSMENT_COMPLETE','configuration_pin':request['semantic_grounding'],
   'receipt_lifecycle_index':{str(r['assessment']['original_proposal_index']):r['receipt']['revision_identity'] for r in result['rows']}}
