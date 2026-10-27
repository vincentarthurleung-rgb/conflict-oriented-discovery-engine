"""Terminal reporting and portable AI-provisional Atlas packages; no model client."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from code_engine.discovery.ai_review_shadow import (
    BoundPacket, ShadowAuthority, bind_review, compare_shadow_pair,
    content_hash, file_hash, load_bound_packet,
)
from code_engine.fulltext.experimental_projection_handoff import _validate_core
from code_engine.schemas.fulltext_observation import ExperimentalObservationV3

TERMINALS = {'NOT_EVALUABLE', 'INSUFFICIENT_EVIDENCE', 'NOT_SUFFICIENTLY_COMPARABLE',
             'NO_CONTRADICTION_AFTER_COMPARISON', 'PROVISIONAL_CONTRADICTION'}

def terminal_state(pair: dict) -> str:
    status = pair['alignment_status']
    if status in {'NOT_SUPPORTED_BY_REVIEW', 'UNCERTAIN'}:
        return 'INSUFFICIENT_EVIDENCE'
    if status == 'NOT_SUFFICIENTLY_COMPARABLE':
        return status
    if status in {'PROVISIONAL_CONTRADICTION', 'PROVISIONAL_CONTEXT_SPLIT_CONTRADICTION'}:
        if pair.get('provisional_contradiction') is not True:
            raise ValueError('inconsistent_provisional_state')
        return 'PROVISIONAL_CONTRADICTION'
    if status in {'DIRECTIONALLY_CONCORDANT', 'DIRECTIONALLY_CONCORDANT_CONTEXT_DIVERGENT',
                  'DIRECTION_DIFFERENCE_WITHOUT_ESTABLISHED_OPPOSITION'}:
        if pair.get('provisional_contradiction') or pair.get('hypotheses'):
            raise ValueError('inconsistent_negative_terminal')
        return 'NO_CONTRADICTION_AFTER_COMPARISON'
    raise ValueError('unrecognized_shadow_terminal:' + status)


def screen_existing_pair(packets: list[Path], reviews: list[Path], cores: list[Path], prompt: Path) -> dict:
    """Report missing inputs without substituting fixtures or running extraction."""
    result = ShadowAuthority().model_dump(mode='json')
    if len(packets) != 2 or not prompt.is_file() or not all(p.is_file() for p in packets):
        return {**result, 'terminal_state': 'NOT_EVALUABLE', 'reason': 'source_packet_or_prompt_unavailable', 'hypotheses': []}
    if len(reviews) != 2 or len(cores) != 2 or not all(p.is_file() for p in reviews + cores):
        return {**result, 'terminal_state': 'INSUFFICIENT_EVIDENCE', 'reason': 'review_or_experimental_core_unavailable', 'hypotheses': []}
    try:
        bounds = [load_bound_packet(p, prompt, c) for p,c in zip(packets,cores)]
        rs = [bind_review(b,json.loads(p.read_text())) for b,p in zip(bounds,reviews)]
        pair = compare_shadow_pair(*bounds,*rs)
    except (ValueError, KeyError, OSError) as exc:
        return {**result, 'terminal_state': 'NOT_EVALUABLE', 'reason': 'invalid_or_unbound_input:' + str(exc), 'hypotheses': []}
    return {**result, 'terminal_state': terminal_state(pair), 'alignment': pair, 'hypotheses': pair['hypotheses']}


def export_review_package(case_id: str, packets: list[Path], reviews: list[Path],
                          cores: list[Path], prompt: Path) -> dict:
    result = screen_existing_pair(packets,reviews,cores,prompt)
    if 'alignment' not in result:
        raise ValueError('review_package_requires_source_bound_pair:' + result['terminal_state'])
    blobs = []
    def blob(role, path):
        raw=path.read_text(encoding='utf-8')
        item={'role':role,'sha256':hashlib.sha256(raw.encode()).hexdigest(),'utf8':raw}
        blobs.append(item)
        return item['sha256']
    prompt_hash=blob('prompt',prompt)
    members=[]
    for i,(p,r,c) in enumerate(zip(packets,reviews,cores)):
        b=load_bound_packet(p,prompt,c);source=b.packet['source']
        if source.get('format') == 'frozen_jats_paragraph_projection':
            raise ValueError('portable_JATS_projection_package_not_yet_supported')
        roles={'packet':p,'review':r,'core':c,'source':Path(source.get('article_path') or source['article_json_path'])}
        hashes={k:blob(f'{i}:{k}',v) for k,v in roles.items()}
        members.append({'pmcid':source['pmcid'],'pmid':source['pmid'],'hashes':hashes})
    package={**ShadowAuthority().model_dump(mode='json'),'schema_version':'ai_provisional_review_package_v1',
             'case_id':case_id,'evidence_mode':'authentic_seen_development','members':members,
             'prompt_sha256':prompt_hash,'blobs':blobs,'terminal_state':result['terminal_state'],
             'alignment':result['alignment'],'uncertainty':'See every source field review and packet missing-information fields; no global scientific PASS.'}
    package['package_sha256']=content_hash(package)
    validate_review_package(package)
    return package


def validate_review_package(package: dict) -> None:
    ShadowAuthority.model_validate({k:package[k] for k in ShadowAuthority.model_fields})
    if (package.get('schema_version') != 'ai_provisional_review_package_v1'
            or package.get('evidence_mode') != 'authentic_seen_development'
            or not package.get('case_id') or package.get('terminal_state') not in TERMINALS):
        raise ValueError('invalid_review_package_contract')
    expected=package.get('package_sha256')
    if content_hash({k:v for k,v in package.items() if k!='package_sha256'})!=expected:
        raise ValueError('review_package_hash_mismatch')
    blobs={}
    for b in package['blobs']:
        if b['role'] in blobs or hashlib.sha256(b['utf8'].encode()).hexdigest()!=b['sha256']:
            raise ValueError('review_package_blob_hash_or_role_mismatch')
        blobs[b['role']]=b
    if blobs['prompt']['sha256']!=package['prompt_sha256']:
        raise ValueError('review_package_prompt_hash_mismatch')
    bounds=[]; reviews=[]
    if len(package['members'])!=2:
        raise ValueError('two_publications_required')
    for i,member in enumerate(package['members']):
        values={}
        for role in ('packet','review','core','source'):
            b=blobs[f'{i}:{role}']
            if b['sha256']!=member['hashes'][role]:raise ValueError('package_member_hash_mismatch')
            values[role]=json.loads(b['utf8'])
        packet,review,env,source=(values[k] for k in ('packet','review','core','source'))
        if env.get('scientific_authorization') is not False or env.get('human_gold') is not False:
            raise ValueError('review_package_native_authority_must_remain_false')
        if (packet['source']['pmcid']!=member['pmcid'] or str(packet['source']['pmid'])!=str(member['pmid'])
                or source['pmcid']!=member['pmcid'] or str(source['pmid'])!=str(member['pmid'])):
            raise ValueError('package_source_identity_mismatch')
        if packet['source'].get('format')=='frozen_jats_paragraph_projection':raise ValueError('portable_JATS_projection_package_not_yet_supported')
        declared=packet['source'].get('article_sha256') or packet['source'].get('article_json_sha256')
        if declared!=member['hashes']['source']:raise ValueError('package_source_hash_mismatch')
        for s in packet['evidence_spans']:
            t=source['sections'][s['section_index']]['text']
            if (t[s['char_start']:s['char_end']]!=s['text'] or hashlib.sha256(s['text'].encode()).hexdigest()!=s['text_hash']
                    or hashlib.sha256(t.encode()).hexdigest()!=s['source_section_text_sha256']):
                raise ValueError('package_evidence_anchor_mismatch')
        formal=ExperimentalObservationV3.model_validate(env['ExperimentalObservationV3']).model_dump(mode='json')
        _validate_core(env['ExperimentalCore'],formal)
        if (packet.get('V3_observation_id') not in (None,formal['observation_id'])
                or packet.get('Core_revision_id') not in (None,env['ExperimentalCore']['revision']['identity'])):
            raise ValueError('package_packet_revision_mismatch')
        if formal['provenance']['fulltext_source_hash']!=declared or formal['provenance']['pmcid']!=member['pmcid']:
            raise ValueError('package_core_source_mismatch')
        hashes={k:member['hashes'][k] for k in ('packet','source')}
        hashes.update(prompt=package['prompt_sha256'],V3_Core=member['hashes']['core'])
        bound=BoundPacket(packet,hashes,formal['observation_id'],env['ExperimentalCore']['revision']['identity'])
        if str(review.get('model_family','')).startswith('SYNTHETIC'):
            raise ValueError('synthetic_review_forbidden_in_Atlas_package')
        bounds.append(bound);reviews.append(bind_review(bound,review))
    pair=compare_shadow_pair(*bounds,*reviews)
    if pair!=package['alignment'] or terminal_state(pair)!=package['terminal_state']:
        raise ValueError('package_alignment_or_terminal_mismatch')


def review_queue_row(package: dict) -> dict:
    validate_review_package(package)
    return {'review_item_id':'ai_package:'+package['package_sha256'],'case_id':package['case_id'],
            'item_type':'ai_provisional_experimental_package','source_scope':'SEEN_DEVELOPMENT',
            'paper_title':'AI 暂定实验对照评审包','evidence_sentence':package['terminal_state'],
            'review_package':package}
