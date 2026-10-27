"""Assemble existing V3 fields; absent explicit experimental links stay absent.

No NLP, Figure rules, ontology additions or scientific authorization. Candidate
component IDs are record identities, never canonical biological identifiers.
"""
from copy import deepcopy
from pathlib import Path
from code_engine.schemas.fulltext_observation import ExperimentalObservationV3
from code_engine.fulltext.experimental_projection_handoff import prepare_experimental_handoff
from .adapters import adapt_explicit_core
from .factors import role_for
from .identities import core_identity
from .models import ExperimentalFactorRecord,MeasurementRecord,ObservedResultRecord,ExperimentalObservationLinkage,StructuredExperimentalObservationRevision
from .linkage import resolve_explicit_links
from .type_policy import assess_observation_type

VERSION='v3_explicit_component_assembly_v1'
def assemble_v3(formal,*,source_artifact,source_blocks,explicit_core=None):
 formal=ExperimentalObservationV3.model_validate(formal).model_dump(mode='json');spans={s['evidence_span_id']:s for s in formal['provenance']['evidence_spans']}
 for s in spans.values():
  import hashlib
  if hashlib.sha256(s['text'].encode()).hexdigest()!=s['text_hash']:raise ValueError('V3_evidence_text_hash_mismatch')
  block=source_blocks.get(s['block_id'])
  if block is None or block[s['char_start']:s['char_end']]!=s['text']:raise ValueError('V3_evidence_source_coordinate_mismatch')
 refs=set(formal['evidence_span_ids'])|set(formal['observation']['evidence_span_ids'])|set(formal['measurement']['evidence_span_ids'])
 refs.update(r for x in formal['interventions'] for r in x['evidence_span_ids'])
 if not refs<=spans.keys():raise ValueError('V3_unknown_component_evidence_reference')
 if explicit_core is not None:
  envelope={'ExperimentalObservationV3':formal,'ExperimentalCore':deepcopy(explicit_core),'scientific_authorization':False,'human_gold':False}
  audit=prepare_experimental_handoff(envelope,Path(source_artifact))['experimental_core_handoff_audit']
  return {'envelope':envelope,'audit':audit,'assembly_mode':'existing_native_core_reuse','missing':[],'strict_core_eligible':False}
 provenance={'producer':VERSION,'producer_version':'1','source_artifact_refs':[str(source_artifact)],'deterministic_rule_refs':['existing_V3_field_projection','legacy_scalar_one_to_one'],'limitations':['AI extraction is unreviewed; absent explicit factor/comparator linkage is not inferred'],'offline':True}
 rev_id=core_identity('structured_experimental_observation_revision_v1',{'source':formal['observation_id'],'formal':formal,'assembler':VERSION});common={'observation_revision_identity':rev_id,'provenance':provenance,'authority_status':'candidate_only','validation_status':'source_bound_candidate'}
 def materialize(model,kind,idkey,payload):
  ident=core_identity(kind,{**payload,'source':formal['observation_id']});return model.model_validate({**payload,idkey:ident,'identity':ident}).model_dump(mode='json')
 factors=[];missing=[]
 for n,x in enumerate(adapt_explicit_core(formal)['factors']):
  role=role_for(x)
  # Unknown/biomarker intervention semantics cannot become an intervention by
  # virtue of occupying the interventions array.
  if x.get('_source')=='interventions' and x.get('normalization_status')!='resolved':role='unresolved'
  raw=x.get('raw_text') or x.get('condition_raw') or x.get('target_mention') or x.get('agent_mention')
  ev=x.get('evidence_span_ids',[])
  if not ev:missing.append('factor_evidence_missing:'+str(n))
  factors.append(materialize(ExperimentalFactorRecord,'experimental_factor_record_v1','factor_id',{**common,'local_factor_id':'factor_'+str(n),'role':role,'raw_text':raw,'extracted_value':{k:v for k,v in x.items() if not k.startswith('_')},'value_state':'source_extracted_unreviewed','order_index':n,'control_or_comparator_status':'explicit_raw_arm_only_unlinked' if role in ('control','comparator') else 'not_control_or_comparator','evidence_anchor_ids':ev,'normalization_status':'unresolved'}))
 m=formal['measurement'];measurement=materialize(MeasurementRecord,'measurement_record_v1','measurement_id',{**common,'local_measurement_id':'measurement_0','measured_entity_raw':m['measured_entity_mention'],'property_or_endpoint_raw':m['endpoint_raw'] or m['outcome_mention'],'measurement_semantic_level':m['measurement_dimension'],'method_raw':m['assay_or_readout_raw'],'evidence_anchor_ids':m['evidence_span_ids'],'normalization_status':m['normalization_status']})
 o=formal['observation'];result=materialize(ObservedResultRecord,'observed_result_record_v1','observed_result_id',{**common,'local_result_id':'result_0','measurement_ref':measurement['measurement_id'],'qualitative_result':o['observed_result'],'direction':formal['candidate_relation']['lexical_direction'],'sign':None,'negation':o['negation'],'quantitative_value_raw':o['quantitative_result_raw'],'statistical_statement':o['statistical_support_raw'],'significance_status':'unassessed','uncertainty_text':o['uncertainty_raw'],'evidence_anchor_ids':o['evidence_span_ids']})
 links=[]
 # Existing scalar V3 schema represents one measurement and its one result.
 # Reuse the existing legacy-scalar rule; factors get no cardinality shortcut.
 for link in resolve_explicit_links(rev_id,factors,[measurement],[result]):
  link.update(provenance=provenance,authority_status='candidate_only');ident=core_identity('experimental_observation_linkage_v1',{k:v for k,v in link.items() if k not in ('identity','linkage_id')});link.update(identity=ident,linkage_id=ident);links.append(ExperimentalObservationLinkage.model_validate(link).model_dump(mode='json'))
 active=any(f['role'] in {'intervention','treatment','exposure','genetic_manipulation'} for f in factors)
 typ,_=assess_observation_type(source=formal,factor_roles={x['role'] for x in factors},measurement_count=1,result_count=1)
 if formal['statement_role']!='current_study_experiment':typ='non_experimental_claim'
 # Retain unresolved observational designs instead of assigning a new enum by
 # keyword or mistakenly turning biomarker strata into an intervention.
 revision=StructuredExperimentalObservationRevision(structured_observation_revision_id=rev_id,identity=rev_id,source_observation_identity=formal['observation_id'],source_fulltext_v3_identity=formal['observation_id'],observation_type=typ,observation_type_authority='candidate_only',experiment_scope_identity=formal['experiment']['experiment_id'],experimental_factor_ids=[f['factor_id'] for f in factors],measurement_ids=[measurement['measurement_id']],observed_result_ids=[result['observed_result_id']],linkage_record_ids=[l['linkage_id'] for l in links],provenance=provenance).model_dump(mode='json')
 envelope={'ExperimentalObservationV3':formal,'ExperimentalCore':{'revision':revision,'factors':factors,'measurements':[measurement],'results':[result],'linkages':links},'scientific_authorization':False,'human_gold':False,'annotation_class':'AI_CONSTRUCTED_SOURCE_BOUND_UNREVIEWED'}
 audit=prepare_experimental_handoff(envelope,Path(source_artifact))['experimental_core_handoff_audit']
 missing+=['explicit_factor_to_measurement_linkage_missing','explicit_comparator_or_baseline_linkage_missing']
 if typ=='unresolved':missing.append('observation_type_unresolved_under_existing_registry')
 if not m['evidence_span_ids']:missing.append('measurement_evidence_missing')
 if not m['assay_or_readout_raw']:missing.append('measurement_method_missing')
 return {'envelope':envelope,'audit':audit,'assembly_mode':'automatic_V3_field_assembly','missing':missing,'strict_core_eligible':False}
