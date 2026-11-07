"""Read-only scientific identity evidence preparation, never identity issuance.

Explicit source mentions and existing resolver output remain different from
validated entity type, equivalence, canonical identity and scientific authority.
No eligible integrity states are synthesized by this development adapter.
"""
from pathlib import Path
from typing import Literal
import json
from pydantic import Field
from code_engine.discovery.ai_review_shadow import ShadowAuthority, content_hash, file_hash, load_bound_packet
from code_engine.orchestration.pilot_inclusion import read_pin
from code_engine.orchestration.pilot_native_proposition_binding import _one, _pointer, _stable_proposition
from code_engine.normalization.resolver import ResolverCascade
from code_engine.context_attribution.claim_alignment.scientific_proposition_v1_candidate import StructuredSemanticValueV1
from code_engine.context_attribution.conflict_candidate.entity_identity_authority_v1_candidate import (
    EntityMentionEvidenceV1, decide_local_equivalence_v1, exact_surface_v1)
from code_engine.extraction_assets.scientific_entity_integrity import (
    ScientificEntityIntegrityStateV1, ScientificEntityIntegrityGateV1, require_scientific_entity_integrity)

VERSION='scientific_identity_evidence_preparation_v1'
ROOT=Path(__file__).resolve().parents[3]
POLICY=ROOT/'docs/contracts/scientific_identity_evidence_preparation_v1.md'
REGISTRY=ROOT/'configs/normalization/entity_registry.json'
AUTH={**ShadowAuthority().model_dump(mode='json'),'machine_reuse_authorized':False,
      'approved_identity_verification':False,'operational_measurement_equivalence':False,
      'scientific_identity_authorized':False,'formal_L4_eligible':False,'formal_conflict_confirmed':False}
ROLES={'subject':'subject','object':'object','biological_entity':'subject',
       'measured_entity':'measurement_target_identity','intervention_or_grouping':'intervention_identity',
       'endpoint':'measurement_target_identity','cohort':'metadata','comparison':'metadata','reported_result':'auxiliary'}


class Mention(ShadowAuthority):
    facet_pointer:str
    facet_value:str|None
    raw_mention:str|None=Field(min_length=1)
    evidence_refs:list[str]
    candidate_interpretation:str=Field(min_length=10)
    unresolved:list[str]=Field(min_length=1)


class Item(ShadowAuthority):
    proposition_key:str
    frozen_comparison:dict
    frozen_inclusion:dict
    proposition_revision:str
    native_core:dict|None
    native_observation_id:str|None
    frozen_effective_projections:dict|None
    B4_9_binding_revision:str|None
    supplemental_packet:dict|None=None
    mentions:dict[str,Mention]
    limitations:list[str]=Field(min_length=1)


class Configuration(ShadowAuthority):
    schema_version:Literal['scientific_identity_evidence_preparation_v1']
    policy:dict
    owner_instruction:dict
    registry:dict
    retained_B4_9_bindings:dict|None=None
    items:list[Item]=Field(min_length=1)
    review_decision:str=Field(min_length=15)
    alternatives:list[str]=Field(min_length=2)
    minimal_reviewer_issuer_requirement:str=Field(min_length=15)
    producer:str=Field(min_length=12)


def input_identity(request):
    from code_engine.orchestration.pilot_comparison import input_identity as transitive
    return transitive({'scientific_comparison_assessments':request.get('scientific_identity_evidence')})


def configuration(request):
    pin=request.get('scientific_identity_evidence')
    if pin is None:return None
    cfg=Configuration.model_validate(read_pin(pin))
    for p in (cfg.policy,cfg.owner_instruction,cfg.registry):
        if file_hash(Path(p['path']))!=p['sha256']:raise ValueError('identity_evidence_pin_hash_drift')
    if cfg.policy['sha256']!=file_hash(POLICY) or Path(cfg.registry['path']).resolve()!=REGISTRY:
        raise ValueError('identity_evidence_policy_or_existing_registry_not_selected')
    return cfg


def retained_binding_artifact(request):
    """Verify accepted frozen bytes/identities; do not rerun 36 correspondences."""
    cfg=configuration(request)
    if cfg is None or cfg.retained_B4_9_bindings is None:return None
    d=read_pin(cfg.retained_B4_9_bindings)
    from code_engine.orchestration.pilot_native_proposition_binding import VERSION as BV, input_identity as bi, POLICY as bp
    if (d['schema_version']!=BV or d['revision_identity']!=BV+':'+content_hash({k:v for k,v in d.items() if k!='revision_identity'})
            or d['input_identity']!=bi({'native_proposition_binding':d['configuration_pin']})
            or d['policy_sha256']!=file_hash(bp)
            or d['implementation_sha256']!=file_hash(ROOT/'src/code_engine/orchestration/pilot_native_proposition_binding.py')):
        raise ValueError('identity_retained_binding_revision_or_dependency_mismatch')
    for row in d['rows']:
        if row['binding_revision']!=BV+':'+content_hash({k:v for k,v in row.items() if k!='binding_revision'}):
            raise ValueError('identity_retained_binding_row_hash_mismatch')
        if any(row.get(k) is not False for k in ('scientific_authorization','machine_reuse_authorized','canonical_identity_approved','formal_L4_compatible')):
            raise ValueError('identity_retained_binding_authority_not_provisional')
    return d


def _inclusion(rows,scope):
    r=_one(rows,lambda r:r['scope_level']=='observation' and r['scope_identity']==scope,'identity_B3_scope_missing_or_ambiguous')
    if r['revision_identity']!='scientific_inclusion_revision:'+content_hash({k:v for k,v in r.items() if k!='revision_identity'}):
        raise ValueError('identity_B3_revision_invalid')
    if file_hash(Path(r['source_artifact']))!=r['source_content_sha256']:raise ValueError('identity_B3_source_revision_invalid')
    return r


def _unchanged_inclusion(old,new):
    omit={'source_artifact','revision_identity'}
    if {k:v for k,v in old.items() if k not in omit}!={k:v for k,v in new.items() if k not in omit}:
        raise ValueError('identity_current_B3_decision_or_scope_changed')


def prepare_identity_evidence(request,ledger,records,propositions,*,dependencies):
    cfg=configuration(request)
    result={**AUTH,'schema_version':VERSION,'configuration_pin':request.get('scientific_identity_evidence'),
        'actual_input_identity':input_identity(request),'policy_sha256':file_hash(POLICY),
        'implementation_sha256':file_hash(Path(__file__)),'current_dependency_identity':dependencies,
        'rows':[],'review_packets':[],'formal_L4c':'staging_only'}
    if cfg is None:return {**result,'status':'NOT_EVALUATED','reason':'No explicit identity evidence preparation selected'}
    if len({i.proposition_key for i in cfg.items})!=len(cfg.items):raise ValueError('identity_duplicate_proposition')
    retained=retained_binding_artifact(request)
    # Exactly this registry, no cache namespace, external clients, credentials,
    # network/provider execution, LLM proposer or LLM cleaner is installed.
    resolver=ResolverCascade(registry_path=REGISTRY,execute=False,network_enabled=False,api_enabled=False,
        entity_network_lookup=False,entity_llm_proposer=False,entity_llm_cleaner=False,external_clients={})
    for item in cfg.items:
        old=_one(read_pin(item.frozen_comparison)['propositions'],lambda p:p['key']==item.proposition_key,'identity_frozen_proposition_missing')
        p=_one(propositions,lambda p:p['key']==item.proposition_key,'identity_current_proposition_missing')
        if old['proposition_identity']!=item.proposition_revision or _stable_proposition(old)!=_stable_proposition(p):
            raise ValueError('identity_proposition_revision_or_scientific_fields_changed')
        if file_hash(Path(old['source_artifact']))!=old['source_content_sha256']:
            raise ValueError('identity_original_source_revision_changed')
        old_b3=_inclusion(read_pin(item.frozen_inclusion)['rows'],old['scope_identity'])
        new_b3=_inclusion(ledger['rows'],p['scope_identity']);_unchanged_inclusion(old_b3,new_b3)
        envelope=None;current_native=None;frozen_effective=None;current_effective=None;binding=None
        if item.native_core is not None:
            envelope=read_pin(item.native_core);formal=envelope['ExperimentalObservationV3'];oid=formal['observation_id']
            if oid!=item.native_observation_id:raise ValueError('identity_wrong_native_observation')
            current_native=_one(records,lambda r:json.loads(r['core'].read_text())['ExperimentalObservationV3']['observation_id']==oid,'identity_native_record_missing')
            if json.loads(current_native['core'].read_text())!=envelope:raise ValueError('identity_wrong_Core_revision')
            native_old_b3=_inclusion(read_pin(item.frozen_inclusion)['rows'],oid)
            native_now_b3=_inclusion(ledger['rows'],oid);_unchanged_inclusion(native_old_b3,native_now_b3)
            if item.frozen_effective_projections:
                view=_one(read_pin(item.frozen_effective_projections),lambda r:r['observation_id']==oid,'identity_effective_missing')
                # ABSTAIN is a correct effective result for a source not covered
                # by B4.8's clinical annotations; never silently normalize it.
                from code_engine.fulltext.projection_interpretation import consumer_guard
                frozen_effective=view['effective_interpretation'];current_effective=current_native.get('effective_projection')
                guard=consumer_guard(view,'review')
                if frozen_effective['status']=='SOURCE_BOUND_PROVISIONAL' and not guard['allowed_by_effective_layer']:
                    raise ValueError('identity_stale_effective_interpretation')
                if view['formal_v3_native_payload']!=formal or view['ExperimentalCore']!=envelope['ExperimentalCore']:
                    raise ValueError('identity_effective_Core_revision_mismatch')
            if item.B4_9_binding_revision:
                if retained is None:raise ValueError('identity_established_binding_required')
                binding=_one(retained['rows'],lambda r:r['binding_revision']==item.B4_9_binding_revision,'identity_binding_not_retained')
                if (binding['decision']!='SOURCE_BOUND_PROVISIONAL_MATCH' or binding['proposition_key']!=p['key']
                        or binding['observation_id']!=oid or binding['Core_revision']!=envelope['ExperimentalCore']['revision']['identity']
                        or binding['current_proposition_revision']!=old['proposition_identity']):
                    raise ValueError('identity_binding_scope_or_revision_mismatch')
        elif item.native_observation_id is not None or item.B4_9_binding_revision is not None:
            raise ValueError('identity_cannot_synthesize_native_for_source_packet')
        evidence={s['evidence_span_id']:s for s in p['source_evidence']}
        supplemental=None
        if item.supplemental_packet:
            bound=load_bound_packet(Path(item.supplemental_packet['path']),Path(item.supplemental_packet['path']))
            if file_hash(Path(item.supplemental_packet['path']))!=item.supplemental_packet['sha256'] or bound.input_hashes['source']!=p['source_content_sha256']:
                raise ValueError('identity_supplemental_source_mismatch')
            supplemental={'pin':item.supplemental_packet,'verification':bound.input_hashes,
                'authority':'frozen_fulltext_supplement_not_historical_provider_input_authority',
                'evidence_spans':bound.packet['evidence_spans']}
            for s in bound.packet['evidence_spans']:
                if s['evidence_span_id'] in evidence and evidence[s['evidence_span_id']]!=s:raise ValueError('identity_conflicting_source_span')
                evidence[s['evidence_span_id']]=s
        if set(item.mentions)!=set(ROLES):raise ValueError('identity_role_inventory_incomplete')
        roles=[];states=[]
        for name,m in item.mentions.items():
            if _pointer(old,m.facet_pointer)!=m.facet_value:raise ValueError('identity_field_semantics_or_revision_mismatch')
            if not set(m.evidence_refs)<=evidence.keys():raise ValueError('identity_source_reference_missing')
            spans=[evidence[r] for r in m.evidence_refs]
            present=m.raw_mention is not None
            if present and (not m.raw_mention.strip() or not spans or not any(m.raw_mention in s['text'] for s in spans)):
                raise ValueError('identity_raw_mention_not_exact_source_text')
            typed=StructuredSemanticValueV1(value=m.facet_value,canonical_identity=None,
                authority_state='structured_only' if m.facet_value is not None else 'missing',source_refs=m.evidence_refs)
            normalization=resolver.resolve_entity(m.raw_mention) if present else None
            # Exact source text validates the surface only. Validated scientific
            # type/role and cleaner clearance are absent; do not infer them.
            mention=EntityMentionEvidenceV1(mention_ref='identity_evidence_mention:'+content_hash({'prop':p['proposition_identity'],'role':name,'annotation':m.model_dump(mode='json')}),
                observation_ref=item.native_observation_id or p['scope_identity'],publication_ref=p['publication']['pmcid'],
                experiment_ref=envelope['ExperimentalObservationV3']['experiment']['experiment_id'] if envelope else p['scope_identity'],
                proposition_role=ROLES[name],role_family=ROLES[name],source_surface=m.raw_mention,
                validated_surface=m.raw_mention,safe_surface=exact_surface_v1(m.raw_mention),entity_type=None,canonical_ids=[],alias_authority_refs=[],
                raw_lineage_refs=[p['source_content_sha256'],*m.evidence_refs],source_grounded=present,
                extracted_surface_validated=present,cleaner_integrity_state='warning',integrity_blocker=False)
            local=decide_local_equivalence_v1([mention])
            state=ScientificEntityIntegrityStateV1(object_id=p['proposition_identity'],object_type='source_bound_identity_evidence',
                entity_integrity_status='entity_integrity_unresolved',affected_field=name,scientific_role=ROLES[name],source_refs=m.evidence_refs)
            states.append(state)
            roles.append({**AUTH,'field':name,'required_scientific_role':ROLES[name],
                'existing_signature_value':p['scientific_signature'].get({'object':'object_target_identity'}.get(name,name+'_identity')),
                'source_evidence_completeness':'EXACT_MENTION_AND_SPANS_AVAILABLE' if present else 'MISSING_EXACT_MENTION',
                'raw_source_mention':m.raw_mention,'source_evidence':spans,'structured_term':typed.model_dump(mode='json'),
                'normalization_decision':normalization.model_dump(mode='json') if normalization else None,
                'identity_candidate_completeness':'NO_EXISTING_CANDIDATE' if not normalization or not normalization.candidates else 'CANDIDATE_ONLY_NOT_VERIFIED',
                'existing_entity_mention_contract':mention.model_dump(mode='json'),
                'existing_local_equivalence_decision':local.model_dump(mode='json'),
                'approved_verification':'NOT_ESTABLISHED_NO_AUTHORIZED_IDENTITY_POLICY_OR_VERIFICATION_RECORD',
                'operational_measurement_compatibility':'SOURCE_DESCRIPTION_ONLY_NOT_AUTHORIZED_EQUIVALENCE',
                'candidate_interpretation':m.candidate_interpretation,'unresolved':m.unresolved,
                'integrity_state':state.model_dump(mode='json'),
                'missing_dependency':['validated proposition-role entity type/surface and cleaner-integrity evidence',
                    'approved local/external identity verification policy and scoped verifier/issuer',
                    'measurement/contrast scope authorization separate from biological name recognition']})
        gate=ScientificEntityIntegrityGateV1().evaluate(object_id=p['proposition_identity'],object_type='source_bound_identity_evidence',
            consumer='claim_alignment',entity_states=states)
        try:require_scientific_entity_integrity('claim_alignment',[gate])
        except ValueError as error:rejection=str(error)
        else:raise ValueError('identity_preparation_must_not_issue_successful_scientific_authority')
        row={**AUTH,'proposition_key':p['key'],'publication':p['publication'],'scope_identity':p['scope_identity'],
            'source_artifact':p['source_artifact'],'source_sha256':p['source_content_sha256'],
            'frozen_proposition_revision':old['proposition_identity'],'current_proposition_revision':p['proposition_identity'],
            'native_observation_id':item.native_observation_id,'native_Core_revision':envelope['ExperimentalCore']['revision']['identity'] if envelope else None,
            'native_original_source_provenance':envelope['ExperimentalObservationV3']['provenance'] if envelope else None,
            'native_measurement_records':envelope['ExperimentalCore']['measurements'] if envelope else [],
            'native_factor_records':envelope['ExperimentalCore']['factors'] if envelope else [],
            'B3_original_revision':old_b3['revision_identity'],'B3_current_revision':new_b3['revision_identity'],
            'B3_original_decision':old_b3['decision'],'B3_current_decision':new_b3['decision'],
            'B4_8_frozen_effective_revision':frozen_effective.get('identity') if frozen_effective else None,
            'B4_8_current_effective_revision':current_effective.get('identity') if current_effective else None,
            'B4_9_binding_revision':binding['binding_revision'] if binding else None,
            'B4_9_retained_binding_pin':cfg.retained_B4_9_bindings,'cross_representation_lineage':binding['source_lineage'] if binding else None,
            'source_supplement':supplemental,'scientific_signature_unchanged':p['scientific_signature'],
            'context_and_measurement':p['facets'],'reported_result':p['result'],'effective_result':p['effective_interpretation'],
            'identity_fields':roles,'actual_gate_decision':gate.model_dump(mode='json'),'actual_require_rejection':rejection,
            'limitations':item.limitations,'producer':cfg.producer,'current_dependency_identity':dependencies,
            'biological_identity_not_operational_measurement_identity':True,'source_binding_not_scientific_authorization':True}
        row['identity_evidence_revision']=VERSION+':'+content_hash(row);result['rows'].append(row)
    review={**AUTH,'schema_version':'scientific_identity_evidence_review_packet_v1','requested_decision':cfg.review_decision,
        'evidence_item_revisions':[r['identity_evidence_revision'] for r in result['rows']],
        'exact_raw_evidence':[{'proposition_key':r['proposition_key'],'source_sha256':r['source_sha256'],
            'fields':r['identity_fields'],'native_observation_id':r['native_observation_id'],'Core_revision':r['native_Core_revision'],
            'B4_revision':r['current_proposition_revision'],'B4_9_binding':r['B4_9_binding_revision'],
            'source_supplement':r['source_supplement']} for r in result['rows']],
        'candidate_interpretations':[{'proposition_key':r['proposition_key'],'fields':[{'field':f['field'],'interpretation':f['candidate_interpretation'],'unresolved':f['unresolved']} for f in r['identity_fields']]} for r in result['rows']],
        'alternative_interpretations':cfg.alternatives,
        'existing_policy_establishes':'Source provenance, typed structured-only terms and candidate-only local equivalence mechanics; not validated type, identity or assay equivalence',
        'consequence_for_formal_use':'Remain blocked until legitimately verified identity/role and operational scope exist; accepting source mention alone cannot qualify conflict',
        'minimal_authorized_reviewer_or_issuer':cfg.minimal_reviewer_issuer_requirement,
        'allowed_review_responses':['ACCEPT_SPECIFIED_SCOPE','REJECT','REQUEST_CLARIFICATION'],
        'reviewer_assigned':None,'review_decision_recorded':None,'trusted_scientific_verification_path':'NOT_APPROVED_FOR_THIS_DEVELOPMENT_HANDOFF'}
    review['review_packet_identity']='scientific_identity_evidence_review_packet_v1:'+content_hash(review)
    result.update(status='SOURCE_BOUND_IDENTITY_EVIDENCE_PREPARED',review_packets=[review],
        registry_probe={'pin':cfg.registry,'provider_names':[p.name for p in resolver.hub.providers],
            'external_clients_installed':False,'network_enabled':False,'LLM_enabled':False,
            'local_candidate_contract':'candidate_only_not_active_scientific_issuer'})
    result['revision_identity']=VERSION+':'+content_hash(result)
    return result
