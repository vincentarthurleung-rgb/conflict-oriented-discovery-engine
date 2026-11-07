"""Exact authorized HIF source scope and owner-controlled local test issuance."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import json
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.orchestration.pilot_hif_identity_verification import VERSION,POLICY,PROFILE,issue_local_verification
from code_engine.orchestration.pilot_semantic_grounding import IssuerPermission
from tests.pilot_identity_evidence_support import identity_case,R
from tests.pilot_inclusion_support import write,pin

RUN=R/'runs/20261030_code_b4_11_bounded_hif_identity_verification_offline'
B410=R/'runs/20261029_code_recovery_batch4_10_identity_evidence_offline/release_v2'


def authority(path):
    path=Path(path);now=datetime.now(timezone.utc);issued=now.isoformat();expiry=(now+timedelta(hours=24)).isoformat()
    profile=json.loads(PROFILE.read_text())
    owner={'schema_version':'bounded_hif_owner_authorization_v1','policy':pin(POLICY),'profile':pin(PROFILE),
        'owner_instruction':pin(RUN/'owner_instruction.original.txt'),
        'provenance':{'origin':'direct_owner_request_in_current_chat','original_attachment':'/home/vincent/.codex/attachments/282d7c78-2db5-4ef0-a7e0-e5e6103e9488/已粘贴的文本.txt',
            'record_kind':'Faithful technical binding of explicit owner authorization; no extra approval assumed',
            'signature':None,'independent_expert_review':False},
        'issued_at':issued,'expires_at':expiry,'revoked':False,
        'permitted_observation_ids':[e['observation_id'] for e in profile['entries']],
        'forbidden':['external canonical identity','operational assay equivalence','formal comparator orientation',
            'materializable scientific relations','Human Gold','Strict Core','independent expert validation','formal L4 promotion']}
    owner['authorization_identity_without_permission']='bounded_hif_owner_scope:'+content_hash(owner)
    owner['issuer_permission']=IssuerPermission(issuer_identity=profile['issuer_identity'],issuer_kind='software_provisional_assessor',
        scopes=[profile['permission_scope']],authorization_reference=owner['authorization_identity_without_permission'],enabled=True,
        environment='development_provisional').model_dump(mode='json')
    owner['authorization_identity']='bounded_hif_owner_authorization:'+content_hash(owner)
    owner_pin=pin(write(path/'owner_authorization.json',owner))
    receipts=[issue_local_verification(e['observation_id'],owner_authorization=owner_pin,now=issued) for e in profile['entries']]
    pins=[pin(write(path/('receipt_'+str(i)+'.json'),r)) for i,r in enumerate(receipts)]
    lifecycle={'schema_version':'bounded_hif_identity_lifecycle_v1','owner_authorization':owner_pin,'policy':pin(POLICY),
        'effective_at':issued,'current_receipt_by_observation':{r['observation_id']:r['revision_identity'] for r in receipts},
        'revoked_receipts':[],'supersedes_checkpoint':None,
        'selection_authority':'owner-authorized offline controller; explicitly supplied by caller, not learned from receipt'}
    lifecycle['revision_identity']='bounded_hif_identity_lifecycle:'+content_hash(lifecycle)
    checkpoint=pin(write(path/'current_lifecycle.json',lifecycle))
    cfg={'schema_version':VERSION+':configuration','owner_authorization':owner_pin,'current_lifecycle':checkpoint,
        'receipts':pins,'reason':'Exactly two owner-authorized local protein type/role observations; all broader permissions withheld'}
    return pin(write(path/'verification_configuration.json',cfg))


def verified_case(label,path,authority_config=None):
    b,c,r=identity_case(label,path)
    if label=='HIF':r['bounded_hif_identity_verification']=authority_config or authority(Path(path)/'bounded_authority')
    return b,c,r


def genuine_B410_HIF():
    return json.loads((B410/'HIF/cases/B3-HIF/scientific_identity_evidence.json').read_text())
