"""Deliver every attempted case through existing Atlas review infrastructure."""
from __future__ import annotations
from code_engine.discovery.ai_review_shadow import ShadowAuthority,content_hash
from code_engine.discovery.pilot_acceptance import validate_review_package,TERMINALS

CASE_TERMINALS=TERMINALS|{'MODEL_FAILED','ACQUISITION_FAILED','INTEGRITY_FAILED','BUDGET_STOP','ATLAS_EXPORT_FAILED','PARTIAL_RESOURCE_STOP'}
STAGE_STATES={'executed','skipped','blocked','failed'}
STAGES_V1=('intake','source_selection_acquisition','immutable_handoff','builder_v4','quality_v2',
        'experimental_v3_core','ai_review','normalization_projection','shadow_alignment',
        'context_analysis','contradiction_classification','hypothesis','atlas_export')
STAGES_V2=STAGES_V1[:-1]+('dataset_export','atlas_export')
STAGES_V3=STAGES_V2[:6]+('source_grounded_linkage',)+STAGES_V2[6:]
STAGES=STAGES_V3[:3]+('scientific_inclusion',)+STAGES_V3[3:]

def make_case_package(manifest:dict,*,pairs:list[dict],artifacts:list[dict],costs:dict)->dict:
    package={**ShadowAuthority().model_dump(mode='json'),'schema_version':'ai_provisional_case_attempt_v1',
             'case_id':manifest['case_id'],'evidence_mode':manifest['evidence_mode'],
             'question':manifest['question'],'terminal_state':manifest['terminal_state'],
             'reason':manifest['terminal_reason'],'sources':manifest.get('sources',[]),
             'run_manifest':manifest,'pair_packages':pairs,'artifacts':artifacts,'costs':costs,
             'uncertainty':'Missing evidence, failed stages and unresolved scientific judgments are retained; a terminal report is not a scientific finding.'}
    package['package_sha256']=content_hash(package);validate_case_package(package);return package


def validate_case_package(p):
    if p.get('schema_version')=='ai_provisional_review_package_v1':return validate_review_package(p)
    ShadowAuthority.model_validate({k:p[k] for k in ShadowAuthority.model_fields})
    if p.get('schema_version')!='ai_provisional_case_attempt_v1' or p.get('terminal_state') not in CASE_TERMINALS:raise ValueError('invalid_case_attempt_terminal')
    if p.get('evidence_mode') not in ('authentic_seen_replay','authorized_new_pilot'):raise ValueError('synthetic_or_unknown_case_mode')
    if content_hash({k:v for k,v in p.items() if k!='package_sha256'})!=p.get('package_sha256'):raise ValueError('case_package_hash_mismatch')
    m=p['run_manifest']
    if m['case_id']!=p['case_id'] or m['terminal_state']!=p['terminal_state'] or m['sources']!=p['sources'] or m['question']!=p['question'] or m['terminal_reason']!=p['reason']:raise ValueError('case_manifest_binding_mismatch')
    previous=m['input_sha256'];stage_names=[]
    for s in m['stages']:
        if s['case_id']!=p['case_id'] or s['status'] not in STAGE_STATES or not s['reason'] or s['previous_sha256']!=previous:raise ValueError('case_stage_lineage_invalid')
        if content_hash({k:v for k,v in s.items() if k!='stage_sha256'})!=s['stage_sha256']:raise ValueError('case_stage_hash_mismatch')
        previous=s['stage_sha256'];stage_names.append(s['stage'])
    expected={'case_stages_v4':STAGES,'case_stages_v3':STAGES_V3,'case_stages_v2':STAGES_V2}.get(m.get('stage_contract_version'),STAGES_V1)
    if tuple(stage_names)!=expected or previous!=m['stage_chain_tip']:raise ValueError('case_stage_chain_invalid')
    for a in p['artifacts']:
        import hashlib
        if hashlib.sha256(a['utf8'].encode()).hexdigest()!=a['sha256']:raise ValueError('case_artifact_bytes_mismatch')
        if a['case_id']!=p['case_id']:raise ValueError('case_artifact_identity_mismatch')
    for pair in p['pair_packages']:
        validate_review_package(pair)
        if pair['case_id']!=p['case_id']:raise ValueError('case_pair_identity_mismatch')
        for member in pair['members']:
            if not any(s['identity']['pmcid']==member['pmcid'] and str(s['identity']['pmid'])==str(member['pmid']) and s['source_sha256']==member['hashes']['source'] for s in p['sources']):raise ValueError('case_pair_source_not_selected')
    if p['terminal_state']=='PROVISIONAL_CONTRADICTION' and not any(x['terminal_state']=='PROVISIONAL_CONTRADICTION' for x in p['pair_packages']):raise ValueError('case_cannot_invent_provisional_contradiction')
    if p['terminal_state']=='NO_CONTRADICTION_AFTER_COMPARISON' and not p['pair_packages']:raise ValueError('no_comparison_cannot_be_negative_finding')
    if not p['sources'] and p['pair_packages']:raise ValueError('zero_source_case_cannot_have_pair')
    if p['costs'].get('case_id') not in (None,p['case_id']):raise ValueError('cost_case_identity_mismatch')
    if any(r['case_id']!=p['case_id'] for r in p['costs']['requests']):raise ValueError('request_cost_case_identity_mismatch')
    if sum(r['charged'] if r['charged'] is not None else r['reserved'] for r in p['costs']['requests'])!=p['costs']['accounted_nusd']:raise ValueError('case_cost_total_mismatch')


def case_queue_row(p):
    validate_case_package(p)
    return {'review_item_id':'ai_case:'+p['package_sha256'],'case_id':p['case_id'],
            'item_type':'ai_provisional_case_review' if p['run_manifest'].get('stage_contract_version') in ('case_stages_v2','case_stages_v3','case_stages_v4') else 'ai_provisional_case_attempt','source_scope':p['evidence_mode'],
            'paper_title':p['question'],'evidence_sentence':p['terminal_state']+': '+p['reason'],
            'review_package':p}


def case_review_rows(package):
    """One attempt denominator plus independently assignable pair review units."""
    rows=[case_queue_row(package)]
    if package['run_manifest'].get('stage_contract_version') in ('case_stages_v2','case_stages_v3','case_stages_v4'):
        from code_engine.discovery.pilot_acceptance import review_queue_row
        for pair in package['pair_packages']:
            row=review_queue_row(pair);row['item_type']='ai_provisional_pair_review';rows.append(row)
    return rows
