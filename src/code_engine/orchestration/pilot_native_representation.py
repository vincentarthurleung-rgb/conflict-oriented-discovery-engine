"""Explicit historical V3 JSONL compatibility path; no extraction or authority.

XML bytes, paragraph projection text and provider-block Unicode coordinates are
different representations. A successful parse never substitutes for their proof.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

from pydantic import Field
from code_engine.discovery.ai_review_shadow import (
    ShadowAuthority, BoundPacket, content_hash, file_hash, load_bound_packet,
)
from code_engine.schemas.fulltext_observation import ExperimentalObservationV3
from code_engine.fulltext.evidence_anchors import generate_evidence_anchors, resolve_anchor, EVIDENCE_ANCHOR_VERSION
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import TrustedDraftContextV3, hydrate_draft_response_v3
from code_engine.fulltext.fulltext_l1_v2 import parse_draft_response
from code_engine.extraction_assets.experimental_core.assembly import assemble_v3
from code_engine.orchestration.pilot_inclusion import read_pin

VERSION = 'historical_native_v3_jsonl_handoff_v1'
COORDINATES = 'provider_block_unicode_to_projected_paragraph_unicode_v1'
AUTHORITY = {**ShadowAuthority().model_dump(mode='json'), 'machine_reuse_authorized': False,
             'formal_conflict_confirmed': False, 'causal_qualification': False}


class NativeReplayManifest(ShadowAuthority):
    schema_version: str
    original_xml: dict
    article_json: dict
    native_jsonl: dict
    provider_request_manifest: dict
    source_payload: dict
    rendered_prompt: dict
    raw_provider_response: dict
    projection_producer: dict
    block_producer: dict
    native_producer: dict
    source_representation: str
    projection_representation: str
    projection_transform: str
    coordinate_mapping: str
    historical_run_id: str
    source_identity: dict
    record_inventory: list[dict] = Field(min_length=1)
    cohort_dependency: dict | None = None


def input_identity(request):
    from code_engine.orchestration.pilot_comparison import input_identity as transitive
    return content_hash({'version': VERSION, 'inputs': transitive({
        'scientific_comparison_assessments': request.get('native_representation_handoffs')})})


def _bytes(pin):
    p = Path(pin['path'])
    if file_hash(p) != pin['sha256']:
        raise ValueError('native_representation_artifact_hash_mismatch:' + p.name)
    return p.read_bytes()


def _lineage(cfg):
    if (cfg.source_representation != 'JATS_XML'
            or cfg.projection_representation != 'frozen_jats_paragraph_projection'
            or cfg.projection_transform != 'itertext_whitespace_collapse_v1'
            or cfg.coordinate_mapping != COORDINATES):
        raise ValueError('unsupported_source_representation_or_coordinate_mapping')
    pins = {k: getattr(cfg, k) for k in ('original_xml', 'article_json', 'provider_request_manifest',
            'source_payload', 'rendered_prompt', 'raw_provider_response', 'projection_producer',
            'block_producer', 'native_producer')}
    data = {k: _bytes(p) for k, p in pins.items()}
    xml = ET.fromstring(data['original_xml']); article = json.loads(data['article_json'])
    m = json.loads(data['provider_request_manifest']); text = data['source_payload'].decode('utf-8')
    ids = {n.get('pub-id-type'): n.text for n in xml.findall('.//front/article-meta/article-id')}
    for key in ('pmcid', 'pmid'):
        if str(ids.get(key)) != str(cfg.source_identity.get(key)) or str(article.get(key)) != str(ids.get(key)):
            raise ValueError('native_original_source_identity_mismatch')
    if (m['paper_identity']['pmcid'] != article['pmcid'] or str(m['paper_identity']['pmid']) != str(article['pmid'])
            or m['source_fulltext_sha256'] != cfg.original_xml['sha256']
            or m['source_payload_sent_sha256'] != cfg.source_payload['sha256']
            or m['block']['chunk_hash'] != cfg.source_payload['sha256']
            or m['rendered_prompt_sha256'] != cfg.rendered_prompt['sha256']):
        raise ValueError('historical_request_source_or_block_hash_mismatch')
    paragraphs = xml.findall('.//body//p'); sections = article['sections']
    if len(paragraphs) != len(sections):
        raise ValueError('unsupported_projection_lineage_paragraph_inventory')
    projected = {}
    for i, (node, section) in enumerate(zip(paragraphs, sections)):
        # Exactly the frozen converter/reader's itertext + whitespace-collapse
        # contract; no NFKC, dropped citations or XML-byte-coordinate claim.
        if (section.get('source_xml_paragraph_index') != i or section['section_id'] != 'JATS_body_p_' + str(i)
                or section['text'] != ' '.join(''.join(node.itertext()).split())):
            raise ValueError('unsupported_projection_lineage_paragraph_mismatch:' + str(i))
        projected.setdefault(section['text'], []).append(i)
    if cfg.cohort_dependency:
        c=cfg.cohort_dependency
        if (c.get('authority')!='source_bound_Work_provisional_not_independent'
                or hashlib.sha256(sections[c['section_index']]['text'].encode()).hexdigest()!=c['source_section_text_sha256']
                or set(c['native_observation_ids'])!={r['observation_id'] for r in cfg.record_inventory}):
            raise ValueError('cohort_dependency_source_or_native_membership_unverified')
    fragments = []; offset = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip('\r\n'); prefix = re.match(r'^(?:CURRENT_[A-Z_]+|PRECEDING_SETUP|LINKED_METHODS):\s*', body)
        if prefix is None: raise ValueError('unsupported_provider_block_framing')
        quote = body[prefix.end():]; matches = projected.get(quote, [])
        # Exact whole-paragraph matches only. Repeated text is unresolved rather
        # than chosen by order, topic, approximate text or proximity.
        if len(matches) != 1: raise ValueError('UNRESOLVED_SOURCE_LINEAGE:block_paragraph_not_unique')
        i = matches[0]
        fragments.append({'block_char_start': offset + prefix.end(), 'block_char_end': offset + len(body),
            'section_index': i, 'source_json_pointer': '/sections/' + str(i) + '/text',
            'xml_node_selector': './/body//p', 'xml_paragraph_index_zero_based': i,
            'xml_node_selection_contract': 'ElementTree.findall(selector)[zero_based_index]; not XPath per-parent sibling position',
            'projected_char_start': 0, 'projected_char_end': len(quote), 'text_hash': hashlib.sha256(quote.encode()).hexdigest(),
            'coordinate_system': COORDINATES, 'xml_byte_offsets': None,
            'mapping_basis': 'Exact full paragraph text after replaying the frozen projection transformation'})
        offset += len(line)
    anchors = generate_evidence_anchors(block_id=m['block']['block_id'], source_document_id=article['pmcid'],
                                        block_text=text, section=m['block']['section']['section_title'])
    prompt = data['rendered_prompt'].decode('utf-8')
    if any(a.text not in prompt or a.anchor_id not in prompt for a in anchors):
        raise ValueError('original_provider_input_exposure_unverified')
    ctx = TrustedDraftContextV3(run_id=cfg.historical_run_id, block_id=m['block']['block_id'],
        parent_block_id=m['block']['parent_block_id'], child_block_id=m['block']['child_block_id'],
        block_text=text, source_block_hash=cfg.source_payload['sha256'], source_document_id=article['pmcid'],
        paper_id=m['paper_identity']['paper_id'], pmid=str(article['pmid']), pmcid=article['pmcid'],
        fulltext_source_hash=cfg.original_xml['sha256'], source_artifact=cfg.original_xml['path'],
        section=m['block']['section']['section_title'])
    hydrated = hydrate_draft_response_v3(parse_draft_response(json.loads(data['raw_provider_response'])), ctx)
    formal_by_id = {f['observation_id']: f for f in hydrated.formal_response['experimental_observations']}
    if len(formal_by_id) != len(hydrated.formal_response['experimental_observations']):
        raise ValueError('historical_provider_hydration_duplicate_identity')
    return article, m, text, anchors, fragments, ctx, formal_by_id, hydrated


def _spans(formal, cfg, article, m, text, anchors, fragments):
    p = formal['provenance']
    if (p['fulltext_source_hash'] != cfg.original_xml['sha256'] or p['pmcid'] != article['pmcid']
            or str(p['pmid']) != str(article['pmid']) or p['source_document_id'] != article['pmcid']
            or p['child_block_id'] != m['block']['block_id']):
        raise ValueError('native_V3_original_source_or_block_mismatch')
    mapped = []
    for span in p['evidence_spans']:
        if span['anchor_version'] != EVIDENCE_ANCHOR_VERSION:
            raise ValueError('native_anchor_contract_unsupported')
        anchor = resolve_anchor(span['anchor_id'], anchors, expected_block_id=m['block']['block_id'],
            source_text=text, expected_source_document_id=article['pmcid'])
        if any(span[k] != getattr(anchor, k) for k in ('block_id','source_document_id','char_start','char_end','text','text_hash','source_role','section')):
            raise ValueError('native_evidence_span_anchor_or_coordinate_mismatch')
        candidates = [f for f in fragments if f['block_char_start'] <= span['char_start'] < span['char_end'] <= f['block_char_end']]
        if len(candidates) != 1: raise ValueError('UNRESOLVED_SOURCE_LINEAGE:span_crosses_unmapped_regions')
        f = candidates[0]; section = article['sections'][f['section_index']]
        start = span['char_start'] - f['block_char_start']; end = span['char_end'] - f['block_char_start']
        if section['text'][start:end] != span['text']: raise ValueError('cross_representation_evidence_mapping_mismatch')
        mapped.append({'evidence_span_id':span['evidence_span_id'], 'original_anchor_id':span['anchor_id'],
            'section_index':f['section_index'],'source_json_pointer':f['source_json_pointer'],
            'char_start':start,'char_end':end,'text':span['text'],'text_hash':span['text_hash'],
            'source_section_text_sha256':hashlib.sha256(section['text'].encode()).hexdigest(),
            'original_provider_block_coordinates':{'block_id':span['block_id'],'char_start':span['char_start'],'char_end':span['char_end']},
            'xml_node_selector':f['xml_node_selector'],'xml_paragraph_index_zero_based':f['xml_paragraph_index_zero_based'],
            'xml_node_selection_contract':f['xml_node_selection_contract'],'xml_byte_offsets':None,
            'mapping_status':'VERIFIED_EXACT_PROJECTED_TEXT','coordinate_system':COORDINATES})
    return mapped


def recover_native_jsonl(manifest_pin, *, source=None, review_prompt=''):
    cfg = NativeReplayManifest.model_validate(read_pin(manifest_pin))
    if cfg.schema_version != VERSION: raise ValueError('native_representation_version_not_selected')
    raw = _bytes(cfg.native_jsonl); rows = []; forms = []; offset = 0
    for index, line in enumerate(raw.splitlines(keepends=True)):
        row = {**AUTHORITY,'original_index':index,'byte_start':offset,'byte_end':offset+len(line),
            'original_line_sha256':hashlib.sha256(line).hexdigest(),'native_jsonl':cfg.native_jsonl,
            'parsed':False,'formal_v3_valid':False,'source_lineage_status':'UNRESOLVED_SOURCE_LINEAGE',
            'native_handoff_accepted':False,'candidate_Core_assembled':False,'reasons':[]}
        offset += len(line); formal = None
        try:
            value = json.loads(line); row['parsed'] = True; row['original_V3_identity'] = value.get('observation_id')
            ExperimentalObservationV3.model_validate(value); formal=value; row['formal_v3_valid']=True
            row['original_formal_v3']=value
        except (ValueError,TypeError,AttributeError) as e:row['reasons'].append('MALFORMED_OR_INVALID_V3:'+str(e))
        rows.append(row); forms.append(formal)
    ids = Counter(f['observation_id'] for f in forms if f is not None)
    global_reason = None; lineage = None
    try:
        lineage = _lineage(cfg)
        if len(rows) != len(cfg.record_inventory): raise ValueError('native_record_inventory_missing_or_extra')
        if source and (source['binding']['source_sha256'] != cfg.article_json['sha256'] or source['identity'] != cfg.source_identity
                       or file_hash(Path(source['article_path'])) != cfg.article_json['sha256']
                       or Path(source.get('origin_article_path',source['article_path'])).resolve() != Path(cfg.article_json['path']).resolve()):
            raise ValueError('Pilot_source_projection_binding_mismatch')
    except (ValueError,KeyError,IndexError,TypeError,OSError,ET.ParseError) as e:global_reason=str(e)
    records=[]
    for row, formal in zip(rows, forms):
        if global_reason:row['reasons'].append(global_reason)
        if formal is None or global_reason:continue
        try:
            article,m,text,anchors,fragments,ctx,hydrated,hydration=lineage
            oid=formal['observation_id']; inv=cfg.record_inventory[row['original_index']]
            if ids[oid] != 1:raise ValueError('duplicate_or_conflicting_V3_record:'+oid)
            if inv != {'observation_id':oid,'formal_sha256':content_hash(formal),
                'endpoint_raw':formal['measurement']['endpoint_raw'],'design_type_raw':formal['experiment']['design_type_raw'],
                'cohort_raw':formal['experiment']['cohort_raw']}:
                raise ValueError('native_record_identity_order_endpoint_or_design_binding_mismatch')
            mapped=_spans(formal,cfg,article,m,text,anchors,fragments)
            if hydrated.get(oid) != formal:raise ValueError('native_record_not_exact_historical_provider_hydration')
            row.update(source_lineage_status='VERIFIED_SOURCE_LINEAGE',coordinate_mapping_status='VERIFIED_EXACT_PROJECTED_TEXT',
                evidence_mapping=mapped,original_source_hash=cfg.original_xml['sha256'],derived_source_hash=cfg.article_json['sha256'],
                source_representation_identity=cfg.original_xml,projection_identity=cfg.article_json,
                original_experiment_identity=formal['experiment']['experiment_id'],endpoint_as_recorded=formal['measurement']['endpoint_raw'],
                cohort_as_recorded=formal['experiment']['cohort_raw'],design_as_recorded=formal['experiment'],
                publication_dependency_group='publication:'+article['pmcid'],
                cohort_dependency=cfg.cohort_dependency,
                interpretation_limitations=['Historical neutral/nonsignificant direction is preserved, not proof of zero effect or equality',
                    'Source-lineage verification is not independent scientific validation of endpoint, subgroup or mechanistic interpretation'])
            assembled=assemble_v3(formal,source_artifact=cfg.original_xml['path'],source_blocks={m['block']['block_id']:text})
            envelope=assembled['envelope']; core=envelope['ExperimentalCore']; revision=core['revision']['identity']
            if envelope['ExperimentalObservationV3']!=formal:raise ValueError('native_V3_changed_during_existing_assembly')
            packet={'packet_id':'derived_native_packet:'+content_hash({'config':manifest_pin,'index':row['original_index'],'formal':formal}),
                'source':{**cfg.source_identity,'title':article['title'],'article_path':cfg.article_json['path'],
                'article_sha256':cfg.article_json['sha256'],'format':cfg.projection_representation,
                'original_xml_path':cfg.original_xml['path'],'original_xml_sha256':cfg.original_xml['sha256']},
                'V3_observation_id':oid,'Core_revision_id':revision,'evidence_spans':mapped}
            row.update(native_handoff_accepted=True,candidate_Core_assembled=True,
                derived_revision_identity=revision,assembly_mode=assembled['assembly_mode'],
                assembly_missing=assembled['missing'],V2=assembled['audit']['linkage'],readiness=assembled['audit']['readiness'],
                original_source_hash_preserved_in_native_V3=True)
            binding={'schema_version':VERSION,'configuration_pin':manifest_pin,'original_index':row['original_index'],
                'original_line_sha256':row['original_line_sha256'],'original_V3_identity':oid,
                'formal_sha256':content_hash(formal),'derived_envelope_sha256':content_hash(envelope),
                'derived_packet_sha256':content_hash(packet),'original_source_hash':cfg.original_xml['sha256'],
                'derived_source_hash':cfg.article_json['sha256'],'coordinate_mapping':COORDINATES,**AUTHORITY}
            binding['derived_handoff_revision']='native_representation_revision:'+content_hash(binding)
            row['handoff_binding']=binding
            records.append({'packet_utf8':json.dumps(packet,ensure_ascii=False),'core_utf8':json.dumps(envelope,ensure_ascii=False),
                'review_prompt_utf8':review_prompt,'native_representation_binding':binding,
                'native_source_lineage':row,'v3_lineage_material':{
                    'raw_provider_response':json.loads(_bytes(cfg.raw_provider_response)),
                    'validated_formal_v3':hydration.formal_response,
                    'hydration_context':asdict(ctx),'source_blocks':{ctx.block_id:text},'window':None,
                    'representation_note':'Decoded JSON copy for existing linkage interface; original provider bytes remain pinned by configuration',
                    'original_response_bytes':cfg.raw_provider_response}})
        except (ValueError,KeyError,IndexError,TypeError,OSError) as e:row['reasons'].append(str(e))
    audit={**AUTHORITY,'schema_version':VERSION,'configuration_pin':manifest_pin,'source_representations':{
        'original_xml':cfg.original_xml,'paragraph_projection':cfg.article_json,'provider_block':cfg.source_payload,
        'native_jsonl':cfg.native_jsonl},'transformation_provenance':{
        'projection_producer':cfg.projection_producer,'block_producer':cfg.block_producer,'native_producer':cfg.native_producer,
        'projection_transform':cfg.projection_transform,'coordinate_system':COORDINATES,
        'historical_transformation_signature':'NOT_AVAILABLE; frozen bytes and deterministic exact-text replay, no invented attestation'},
        'provider_lineage':None if lineage is None else {k:lineage[1][k] for k in ('provider','model','request_identity')},
        'original_provider_response':cfg.raw_provider_response,'batch_rejection_reason':global_reason,
        'missing_expected_record_count':max(len(cfg.record_inventory)-len(rows),0),'fragments':lineage[4] if lineage else [],
        'hydration_rejections':lineage[7].rejected if lineage else None,'records':rows,
        'counts':{'authentic_JSONL_records_present':len(rows),'parsed':sum(r['parsed'] for r in rows),
            'formal_V3_valid':sum(r['formal_v3_valid'] for r in rows),
            'verified_source_lineage':sum(r['source_lineage_status']=='VERIFIED_SOURCE_LINEAGE' for r in rows),
            'native_handoff_accepted':sum(r['native_handoff_accepted'] for r in rows),
            'candidate_Core_assembled':len(records),'rejected_or_unresolved':sum(not r['candidate_Core_assembled'] for r in rows),
            'formal_materialized_relationships':0,'new_model_extractions':0},
        'availability_axes_independent':True,'B4_source_packet_propositions_not_matched_to_JSONL_by_count':True}
    return {'records':records,'audit':audit}


def load_native_bound_packet_v1(packet_path,prompt_path,core_path,binding):
    """Selected compatibility reader. Legacy load_bound_packet is unchanged.

    Recompute the proof from frozen inputs and the current existing assembler;
    a caller-supplied valid-looking wrapper or verification boolean is not proof.
    """
    expected=recover_native_jsonl(binding['configuration_pin'],review_prompt=Path(prompt_path).read_text())
    matches=[r for r in expected['records'] if r['native_representation_binding']==binding]
    if len(matches)!=1:raise ValueError('native_handoff_binding_not_reverified')
    r=matches[0]
    if json.loads(Path(packet_path).read_text())!=json.loads(r['packet_utf8']) or json.loads(Path(core_path).read_text())!=json.loads(r['core_utf8']):
        raise ValueError('native_derived_packet_or_Core_changed')
    bound=load_bound_packet(Path(packet_path),Path(prompt_path))
    hashes={**bound.input_hashes,'V3_Core':file_hash(Path(core_path)),
        'native_representation_config':binding['configuration_pin']['sha256']}
    return BoundPacket(bound.packet,hashes,binding['original_V3_identity'],
                       json.loads(r['core_utf8'])['ExperimentalCore']['revision']['identity'])
