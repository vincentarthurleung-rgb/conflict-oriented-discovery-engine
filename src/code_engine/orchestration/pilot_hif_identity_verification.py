"""Owner-scoped, source-backed HIF protein type/role verification.

This adapter issues only the finite local permission in the versioned policy.
Receipts require independent caller-selected authorization/lifecycle context
and freshly recomputed evidence. It is neither a resolver nor causal issuer.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Literal
from code_engine.discovery.ai_review_shadow import ShadowAuthority,content_hash,file_hash,load_bound_packet
from code_engine.orchestration.pilot_inclusion import read_pin
from code_engine.orchestration.pilot_native_proposition_binding import _one
from code_engine.orchestration.pilot_semantic_grounding import IssuerPermission,_stamp
from code_engine.context_attribution.conflict_candidate.entity_identity_authority_v1_candidate import EntityMentionEvidenceV1,decide_local_equivalence_v1,exact_surface_v1
from code_engine.context_attribution.claim_alignment.scientific_proposition_v1_candidate import StructuredSemanticValueV1,ScientificPropositionSignatureV1
from code_engine.extraction_assets.scientific_entity_integrity import ScientificEntityIntegrityStateV1,ScientificEntityIntegrityGateV1,require_scientific_entity_integrity

VERSION='bounded_hif_local_identity_verification_v1'
RECEIPT='bounded_hif_local_identity_receipt_v1'
ROOT=Path(__file__).resolve().parents[3]
POLICY=ROOT/'docs/contracts/bounded_hif_local_identity_verification_v1.md'
PROFILE=ROOT/'docs/contracts/bounded_hif_local_identity_scope_v1.json'
AUTH={**ShadowAuthority().model_dump(mode='json'),'machine_reuse_authorized':False,
      'independent_scientific_validation':False,'formal_scientific_promotion_authorized':False,
      'external_identity_verified':False,'operational_equivalence_verified':False,
      'comparator_orientation_verified':False,'formal_L4_eligible':False,'formal_conflict_confirmed':False}


class LocalReceipt(ShadowAuthority):
    schema_version:Literal['bounded_hif_local_identity_receipt_v1']
    observation_id:str
    evidence_binding:dict
    assessment:dict
    assessment_sha256:str
    owner_record:dict
    policy:dict
    profile:dict
    issuer:IssuerPermission
    validator_implementation:dict
    issued_at:str
    expires_at:str
    revision_identity:str


def implementation_identity():return {'path':str(Path(__file__).resolve()),'sha256':file_hash(Path(__file__))}
def _pin(path):return {'path':str(Path(path).resolve()),'sha256':file_hash(Path(path))}
def _content_identity(prefix,value,key='revision_identity'):return prefix+':'+content_hash({k:v for k,v in value.items() if k!=key})
def _bytes_pin(pin):
    if file_hash(Path(pin['path']))!=pin['sha256']:raise ValueError('bounded_identity_pin_hash_drift')
    return Path(pin['path']).read_bytes()


def input_identity(request,*,now=None):
    from code_engine.orchestration.pilot_comparison import input_identity as transitive
    pin=request.get('bounded_hif_identity_verification');phase=None
    if pin:
        # Expired/future authority cannot reuse a completed active-verification
        # package. No wall-clock seconds enter exact raw model-request identity.
        try:
            cfg=read_pin(pin);owner=read_pin(cfg['owner_authorization']);checkpoint=read_pin(cfg['current_lifecycle'])
            stamp=_stamp(now or datetime.now(timezone.utc).isoformat())
            phase={'owner_active':_stamp(owner['issued_at'])<=stamp<_stamp(owner['expires_at']),
                'lifecycle_effective':_stamp(checkpoint['effective_at'])<=stamp,
                'receipt_active':[(_stamp(r['issued_at'])<=stamp<_stamp(r['expires_at'])) for p in cfg['receipts'] for r in [read_pin(p)]]}
        except (ValueError,KeyError,TypeError,OSError):phase='INVALID_OR_MISSING_AUTHORITY_INPUT'
    return content_hash({'transitive_inputs':transitive({'scientific_comparison_assessments':pin}),'current_validity_phase':phase})


def owner_context(owner_pin,*,now):
    """Explicit caller trust anchor, never extracted from a receipt."""
    owner=read_pin(owner_pin);profile=json.loads(PROFILE.read_text())
    if owner.get('schema_version')!='bounded_hif_owner_authorization_v1' or owner.get('authorization_identity')!=_content_identity('bounded_hif_owner_authorization',owner,'authorization_identity'):
        raise ValueError('bounded_owner_record_invalid')
    if owner['policy']!=_pin(POLICY) or owner['profile']!=_pin(PROFILE):raise ValueError('bounded_owner_policy_or_scope_not_current')
    instruction=_bytes_pin(owner['owner_instruction'])
    if owner['owner_instruction']['sha256']!=profile['owner_instruction_sha256']:
        raise ValueError('bounded_owner_instruction_not_approved_scope')
    if owner['provenance']['origin']!='direct_owner_request_in_current_chat' or owner['provenance']['signature'] is not None:
        raise ValueError('bounded_owner_provenance_not_actual')
    if not _stamp(owner['issued_at'])<=_stamp(now)<_stamp(owner['expires_at']):raise ValueError('bounded_owner_expired_or_future')
    if (_stamp(owner['expires_at'])-_stamp(owner['issued_at'])).total_seconds()>profile['max_validity_seconds']:
        raise ValueError('bounded_owner_expiry_exceeds_policy')
    if owner.get('revoked') is not False:raise ValueError('bounded_owner_revoked')
    if sorted(owner['permitted_observation_ids'])!=sorted(e['observation_id'] for e in profile['entries']):
        raise ValueError('bounded_owner_exact_observation_scope_mismatch')
    permission=IssuerPermission.model_validate(owner['issuer_permission'])
    if (permission.issuer_identity!=profile['issuer_identity'] or permission.scopes!=[profile['permission_scope']]
            or permission.authorization_reference!=owner['authorization_identity_without_permission']
            or permission.environment!='development_provisional' or permission.issuer_kind!='software_provisional_assessor'
            or permission.enabled is not True):raise ValueError('bounded_issuer_permission_invalid')
    # The nonrecursive authorization identity binds the exact request/policy/scope,
    # rather than claiming a cryptographic or independent scientist signature.
    payload={k:v for k,v in owner.items() if k not in ('issuer_permission','authorization_identity','authorization_identity_without_permission')}
    if owner['authorization_identity_without_permission']!='bounded_hif_owner_scope:'+content_hash(payload):
        raise ValueError('bounded_issuer_authorization_binding_invalid')
    return owner,profile,permission


def _entry(profile,oid):
    return _one(profile['entries'],lambda e:e['observation_id']==oid,'bounded_observation_out_of_scope_or_ambiguous')


def assess_source(oid,*,profile=None):
    """Recompute affirmative type/role facts from frozen source, not a receipt."""
    profile=profile or json.loads(PROFILE.read_text());e=_entry(profile,oid)
    evidence=read_pin(e['B4_10_evidence'])
    row=_one(evidence['rows'],lambda r:r['native_observation_id']==oid,'bounded_B4_10_evidence_missing')
    if row['identity_evidence_revision']!=e['B4_10_revision'] or row['identity_evidence_revision']!='scientific_identity_evidence_preparation_v1:'+content_hash({k:v for k,v in row.items() if k!='identity_evidence_revision'}):
        raise ValueError('bounded_B4_10_revision_mismatch')
    if (row['native_Core_revision']!=e['Core_revision'] or row['current_proposition_revision']!=e['B4_proposition_revision']
            or row['B3_current_revision']!=e['B3_revision'] or row['B4_8_current_effective_revision']!=e['B4_8_effective_revision']
            or row['publication']!=e['publication'] or row['source_sha256']!=e['source_sha256']):
        raise ValueError('bounded_frozen_source_or_revision_mismatch')
    core=read_pin(e['native_core']);f=core['ExperimentalObservationV3'];c=core['ExperimentalCore']
    bound=load_bound_packet(Path(e['source_packet']['path']),Path(e['source_packet']['path']),Path(e['native_core']['path']))
    _bytes_pin(e['source_packet'])
    if bound.observation_id!=oid or bound.revision_id!=e['Core_revision'] or bound.input_hashes['source']!=e['source_sha256']:
        raise ValueError('bounded_exact_source_Core_binding_mismatch')
    if f['measurement']['measured_entity_mention']!=profile['permitted_target_surface']:
        raise ValueError('bounded_target_not_exact_reported_protein')
    if row['context_and_measurement'] and any(row['context_and_measurement'][k]!=v for k,v in e['context'].items()):
        raise ValueError('bounded_context_not_approved')
    spans={s['evidence_span_id']:s for s in bound.packet['evidence_spans']}
    primary=spans[e['primary_span_id']]
    if primary['text']!=e['primary_span_text'] or primary['text_hash']!=e['primary_span_text_sha256']:
        raise ValueError('bounded_primary_source_evidence_changed')
    for name,proof in e['affirmative_evidence'].items():
        if not proof['quote'] or proof['quote'] not in spans[proof['span_id']]['text']:
            raise ValueError('bounded_required_affirmative_evidence_missing:'+name)
    if set(e['affirmative_evidence'])!={'protein_target','protein_readout','exposure_reference'}:
        raise ValueError('bounded_affirmative_evidence_inventory_incomplete')
    # Explicit policy-approved quote inventory supplies the semantic scope;
    # no fuzzy matching, gene-name lookup, isoform alias or new entity type.
    target=profile['permitted_target_surface']
    protein_field=_one(row['identity_fields'],lambda x:x['field']=='measured_entity','bounded_measurement_role_missing')
    if protein_field['raw_source_mention']!=target:raise ValueError('bounded_protein_surface_changed')
    prior=protein_field['existing_entity_mention_contract']
    if prior['cleaner_integrity_state']=='blocked' or prior['integrity_blocker']:
        raise ValueError('bounded_historical_cleaner_integrity_blocked')
    if prior['source_surface']!=prior['validated_surface'] or exact_surface_v1(prior['source_surface'])!=prior['safe_surface']:
        raise ValueError('bounded_lossy_surface_not_cleared')
    mention=EntityMentionEvidenceV1(mention_ref='bounded_hif_mention:'+content_hash({'evidence':e['B4_10_revision'],'target':target}),
        observation_ref=oid,publication_ref=e['publication']['pmcid'],experiment_ref=f['experiment']['experiment_id'],
        proposition_role='measurement_target_identity',role_family='measurement_target_identity',
        source_surface=target,validated_surface=target,safe_surface=exact_surface_v1(target),entity_type=profile['permitted_existing_type'],
        canonical_ids=[],alias_authority_refs=[],raw_lineage_refs=[e['B4_10_revision'],e['source_sha256'],e['primary_span_id']],
        source_grounded=True,extracted_surface_validated=True,cleaner_integrity_state='clear',integrity_blocker=False)
    local=decide_local_equivalence_v1([mention])
    if not local.eligible_for_local_equivalence or local.external_canonical_authority!='local_identity_only':
        raise ValueError('bounded_local_candidate_contract_did_not_establish_target')
    assessment={**AUTH,'reported_target':target,'reported_type':'protein','scientific_type_role_scope':'reported protein measurement target and source-described reduced-oxygen exposure role',
        'source_identity_verification':'VERIFIED_EXACT_FROZEN_SOURCE_AND_REVISIONS',
        'local_type_role_verification':'VERIFIED_OWNER_SCOPED_SOURCE_BACKED',
        'mention':mention.model_dump(mode='json'),'local_equivalence':local.model_dump(mode='json'),
        'structured_value':StructuredSemanticValueV1(value=target,canonical_identity=None,authority_state='structured_only',source_refs=[e['primary_span_id']]).model_dump(mode='json'),
        'context':e['context'],'nominal_reference_concentration_percent':e['nominal_reference_concentration_percent'],
        'affirmative_evidence':[{**proof,'dimension':name,'source_span':spans[proof['span_id']]} for name,proof in e['affirmative_evidence'].items()],
        'dimensions':{
            'A_source_mention_integrity':{'status':'VERIFIED','evidence_refs':[e['primary_span_id']]},
            'B_scientific_type':{'status':'VERIFIED_LOCAL_REPORTED_PROTEIN','value':'protein','evidence_refs':[e['affirmative_evidence']['protein_target']['span_id']]},
            'C_exposure_role':{'status':'VERIFIED_SOURCE_DESCRIBED_REDUCED_OXYGEN_ROLE','canonical_exposure_identity':None,'evidence_refs':[e['primary_span_id']]},
            'D_measurement_target_role':{'status':'VERIFIED_REPORTED_PROTEIN_ABUNDANCE_TARGET','evidence_refs':[e['primary_span_id']]},
            'E_local_target_correspondence':{'status':'SINGLE_SOURCE_LOCAL_TARGET_ESTABLISHED_PAIR_NOT_YET_CHECKED','local_identity_key':local.local_identity_key},
            'F_external_canonical_identity':{'status':'UNRESOLVED','canonical_id':None,'isoform':None},
            'G_assay_operational_equivalence':{'status':'NOT_ESTABLISHED','complete_experiment_equivalence':False},
            'H_comparator_orientation':{'status':'SOURCE_REFERENCE_LABELS_ONLY_FORMAL_ORIENTATION_UNRESOLVED','comparison_links_issued':0},
            'I_scientific_machine_reuse':{'status':'NOT_AUTHORIZED','materialized_relations':0}},
        'historical_cleaner_status_modified':False,'new_source_mention_clearance':'Exact uncleaned HIF-1α surface only; does not clear or rewrite historical lineage',
        'limitations':['No external canonical ID, isoform, mechanism or causal direction','Different cells, oxygen doses, exposure durations and source references remain',
            'No assay equivalence, validated subject/object identities, formal comparison orientation, machine reuse or independent expert review']}
    binding={'publication':e['publication'],'observation_id':oid,'Core_revision':e['Core_revision'],'native_core':e['native_core'],
        'source_packet':e['source_packet'],'source_input_hashes':bound.input_hashes,'B4_10_evidence':e['B4_10_evidence'],
        'B4_10_revision':e['B4_10_revision'],'B3_revision':e['B3_revision'],'B4_revision':e['B4_proposition_revision'],
        'B4_8_effective_revision':e['B4_8_effective_revision'],'profile_entry_sha256':content_hash(e)}
    return {'assessment':assessment,'binding':binding,'entry':e}


def issue_local_verification(oid,*,owner_authorization,now):
    owner,profile,permission=owner_context(owner_authorization,now=now)
    source=assess_source(oid,profile=profile)
    value={**ShadowAuthority().model_dump(mode='json'),'schema_version':RECEIPT,'observation_id':oid,
        'evidence_binding':source['binding'],'assessment':source['assessment'],'assessment_sha256':content_hash(source['assessment']),
        'owner_record':owner_authorization,'policy':_pin(POLICY),'profile':_pin(PROFILE),
        'issuer':permission.model_dump(mode='json'),'validator_implementation':implementation_identity(),
        'issued_at':now,'expires_at':owner['expires_at']}
    value['revision_identity']=_content_identity(RECEIPT,value)
    return LocalReceipt.model_validate(value).model_dump(mode='json')


def verify_local_receipt(receipt,*,owner_authorization,current_lifecycle,now,requested_scope='bounded_hif_local_type_role_v1'):
    """Receipt cannot supply trust root, allowed issuer, current revision or facts."""
    reasons=[];r=None;source=None
    try:
        owner,profile,permission=owner_context(owner_authorization,now=now)
        lifecycle=read_pin(current_lifecycle)
        if lifecycle.get('schema_version')!='bounded_hif_identity_lifecycle_v1' or lifecycle.get('revision_identity')!=_content_identity('bounded_hif_identity_lifecycle',lifecycle):
            raise ValueError('bounded_lifecycle_checkpoint_invalid')
        if lifecycle['owner_authorization']!=owner_authorization or lifecycle['policy']!=_pin(POLICY):
            raise ValueError('bounded_lifecycle_owner_scope_mismatch')
        if _stamp(lifecycle['effective_at'])>_stamp(now):raise ValueError('bounded_lifecycle_future')
        r=LocalReceipt.model_validate(receipt);payload=r.model_dump(mode='json')
        if r.revision_identity!=_content_identity(RECEIPT,payload):reasons.append('bounded_receipt_content_hash_mismatch')
        if r.owner_record!=owner_authorization or r.policy!=owner['policy'] or r.profile!=owner['profile']:
            reasons.append('bounded_receipt_owner_policy_scope_mismatch')
        if r.issuer!=permission:reasons.append('bounded_issuer_not_independently_permitted')
        if requested_scope!=profile['permission_scope'] or requested_scope not in permission.scopes:
            reasons.append('bounded_requested_scope_not_permitted')
        if r.validator_implementation!=implementation_identity():reasons.append('bounded_validator_implementation_changed')
        if (not _stamp(r.issued_at)<=_stamp(now)<_stamp(r.expires_at)
                or _stamp(r.issued_at)<_stamp(owner['issued_at']) or _stamp(r.expires_at)>_stamp(owner['expires_at'])
                or (_stamp(r.expires_at)-_stamp(r.issued_at)).total_seconds()>profile['max_validity_seconds']):
            reasons.append('bounded_receipt_expired_or_invalid_time')
        if lifecycle['current_receipt_by_observation'].get(r.observation_id)!=r.revision_identity:
            reasons.append('bounded_receipt_not_current_or_superseded')
        if r.revision_identity in lifecycle['revoked_receipts']:reasons.append('bounded_receipt_revoked')
        source=assess_source(r.observation_id,profile=profile)
        if r.evidence_binding!=source['binding'] or r.assessment!=source['assessment'] or r.assessment_sha256!=content_hash(source['assessment']):
            reasons.append('bounded_receipt_insufficient_or_changed_source_assessment')
    except (ValueError,KeyError,TypeError,OSError,AttributeError) as error:reasons.append(type(error).__name__+':'+str(error))
    value={**AUTH,'schema_version':VERSION+':receipt_verification','status':'VERIFIED_BOUNDED_LOCAL_TYPE_ROLE' if not reasons else 'BLOCKED',
        'local_type_role_verified':not reasons,'source_identity_verified':not reasons,'reason_codes':reasons,
        'receipt_revision':r.revision_identity if r else None,'verified_as_of':now,
        'expires_at':r.expires_at if r else None,'owner_authorization':owner_authorization,
        'trusted_current_lifecycle':current_lifecycle,'requested_scope':requested_scope,
        'trust_basis':'Separately selected explicit owner authorization, scoped issuer permission, current lifecycle and recomputed frozen source; no cryptographic or independent-review claim',
        'verified_assessment':source['assessment'] if source and not reasons else None}
    value['verification_identity']=VERSION+':verification:'+content_hash(value)
    return value


def _current_scope(row,receipt):
    a=receipt['assessment'];b=receipt['evidence_binding']
    if row['identity_evidence_revision']!='scientific_identity_evidence_preparation_v1:'+content_hash({k:v for k,v in row.items() if k!='identity_evidence_revision'}):
        raise ValueError('bounded_current_identity_evidence_revision_invalid')
    profile=json.loads(PROFILE.read_text());e=_entry(profile,receipt['observation_id'])
    frozen=_one(read_pin(e['B4_10_evidence'])['rows'],lambda r:r['native_observation_id']==receipt['observation_id'],'bounded_frozen_evidence_missing')
    core=read_pin(e['native_core'])
    if (row['native_original_source_provenance']!=core['ExperimentalObservationV3']['provenance']
            or row['native_measurement_records']!=core['ExperimentalCore']['measurements']
            or row['native_factor_records']!=core['ExperimentalCore']['factors']
            or row['scientific_signature_unchanged']!=frozen['scientific_signature_unchanged']
            or row['context_and_measurement']!=frozen['context_and_measurement']):
        raise ValueError('bounded_current_native_provenance_or_scientific_scope_changed')
    if (row['native_observation_id']!=receipt['observation_id'] or row['publication']!=b['publication']
            or row['native_Core_revision']!=b['Core_revision'] or row['source_sha256']!=b['source_input_hashes']['source']):
        raise ValueError('bounded_current_observation_Core_source_mismatch')
    if any(row['context_and_measurement'][k]!=v for k,v in a['context'].items()):
        raise ValueError('bounded_current_cell_oxygen_time_assay_or_reference_changed')
    if row['scientific_signature_unchanged']['subject_identity'] is not None or row['scientific_signature_unchanged']['object_target_identity'] is not None:
        raise ValueError('bounded_policy_does_not_fill_or_authorize_subject_object')
    field=_one(row['identity_fields'],lambda f:f['field']=='measured_entity','bounded_current_target_role_missing')
    if field['raw_source_mention']!=a['reported_target'] or field['structured_term']['canonical_identity'] is not None:
        raise ValueError('bounded_current_target_gene_alias_or_canonical_confusion')
    if row['context_and_measurement']['entity']['value']!='HIF-1α protein' or row['context_and_measurement']['endpoint']['value']!='HIF-1α protein abundance':
        raise ValueError('bounded_current_protein_mRNA_or_endpoint_confusion')
    # Preserve existing signature type/role without assigning any new identity.
    ScientificPropositionSignatureV1.model_validate(row['scientific_signature_unchanged'])


def run_bounded_hif_verification(request,identity_evidence,*,dependencies,now=None):
    pin=request.get('bounded_hif_identity_verification')
    result={**AUTH,'schema_version':VERSION,'configuration_pin':pin,'current_dependency_identity':dependencies,
        'actual_input_identity':input_identity(request),'rows':[],'correspondence':None,'formal_L4c':'staging_only'}
    if pin is None:return {**result,'status':'NOT_EVALUATED','reason':'No HIF-only identity permission selected; no cross-case promotion'}
    cfg=read_pin(pin)
    if cfg['schema_version']!=VERSION+':configuration':raise ValueError('bounded_configuration_version_mismatch')
    observed_now=now or datetime.now(timezone.utc).isoformat()
    profile=json.loads(PROFILE.read_text());allowed={e['observation_id'] for e in profile['entries']}
    rows=identity_evidence['rows']
    if {r['native_observation_id'] for r in rows}!=allowed or len(rows)!=len(allowed):
        return {**result,'status':'ABSTAIN_OUT_OF_SCOPE','reason':'Exactly the two approved HIF observations required; no other biological target authorized'}
    receipt_objects=[read_pin(p) for p in cfg['receipts']]
    for row in rows:
        receipt=_one(receipt_objects,lambda r:r['observation_id']==row['native_observation_id'],'bounded_receipt_missing_or_ambiguous')
        verification=verify_local_receipt(receipt,owner_authorization=cfg['owner_authorization'],current_lifecycle=cfg['current_lifecycle'],now=observed_now)
        try:_current_scope(row,receipt)
        except (ValueError,KeyError,TypeError) as error:
            verification={**verification,'status':'BLOCKED','local_type_role_verified':False,'source_identity_verified':False,
                'verified_assessment':None,'reason_codes':[*verification['reason_codes'],str(error)]}
        verification['verification_identity']=VERSION+':verification:'+content_hash({k:v for k,v in verification.items() if k!='verification_identity'})
        states=[]
        refs=[s['evidence_span_id'] for f in row['identity_fields'] for s in f['source_evidence']]
        # Only the measured protein target gets the owner-approved local state.
        states.append(ScientificEntityIntegrityStateV1(object_id=row['current_proposition_revision'],object_type='bounded_local_HIF_identity',
            entity_integrity_status='entity_integrity_validated_normalization' if verification['local_type_role_verified'] else 'entity_integrity_unresolved',
            affected_field='reported_protein_measurement_target',scientific_role='measurement_target_identity',source_refs=sorted(set(refs))))
        for field,role in [('subject_identity','subject'),('object_target_identity','object'),
                           ('exposure_identity','intervention_identity'),('operational_endpoint_identity','measurement_target_identity')]:
            states.append(ScientificEntityIntegrityStateV1(object_id=row['current_proposition_revision'],object_type='bounded_local_HIF_identity',
                entity_integrity_status='entity_integrity_unresolved',affected_field=field,scientific_role=role,source_refs=sorted(set(refs))))
        gate=ScientificEntityIntegrityGateV1().evaluate(object_id=row['current_proposition_revision'],object_type='bounded_local_HIF_identity',
            consumer='claim_alignment',entity_states=states)
        try:require_scientific_entity_integrity('claim_alignment',[gate]);rejection=None
        except ValueError as error:rejection=str(error)
        entry={**AUTH,'observation_id':row['native_observation_id'],'proposition_key':row['proposition_key'],
            'current_proposition_revision':row['current_proposition_revision'],'current_identity_evidence_revision':row['identity_evidence_revision'],
            'receipt':receipt,'verification':verification,'integrity_states':[s.model_dump(mode='json') for s in states],
            'actual_gate_decision':gate.model_dump(mode='json'),'actual_require_rejection':rejection,
            'original_subject_identity':row['scientific_signature_unchanged']['subject_identity'],
            'original_object_target_identity':row['scientific_signature_unchanged']['object_target_identity']}
        entry['revision_identity']=VERSION+':decision:'+content_hash(entry);result['rows'].append(entry)
    if all(r['verification']['local_type_role_verified'] for r in result['rows']):
        mentions=[EntityMentionEvidenceV1.model_validate(r['verification']['verified_assessment']['mention']) for r in result['rows']]
        pair=decide_local_equivalence_v1(mentions)
        result['correspondence']={**AUTH,'status':'LOCALLY_VERIFIED_BROAD_PROTEIN_TARGET_CORRESPONDENCE' if pair.eligible_for_local_equivalence else 'UNRESOLVED',
            'existing_contract_decision':pair.model_dump(mode='json'),'observation_ids':[r['observation_id'] for r in result['rows']],
            'receipt_revisions':[r['receipt']['revision_identity'] for r in result['rows']],
            'scope':'Same source-reported HIF-1α protein target only; not operational equivalence or regulation direction'}
    result['status']='BOUNDED_VERIFICATION_COMPLETE' if result['correspondence'] else 'BOUNDED_VERIFICATION_BLOCKED'
    result['revision_identity']=VERSION+':'+content_hash(result)
    return result
