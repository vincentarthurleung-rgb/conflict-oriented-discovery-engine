"""Authentic historical acceptance; altered copies are SOFTWARE_FIXTURE controls."""
from copy import deepcopy
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import pytest

from code_engine.discovery.ai_review_shadow import content_hash, file_hash, load_bound_packet
from code_engine.orchestration.pilot_native_representation import (
    recover_native_jsonl,load_native_bound_packet_v1,input_identity,
)
from code_engine.orchestration.pilot_case import PilotCaseExecutor,CaseIntegrity
from code_engine.orchestration.pilot_budget import ModelBudget
from code_engine.orchestration.pilot_dataset import verify_dataset
from tests.pilot_native_representation_support import manifest,trib_native,HIST
from tests.pilot_inclusion_support import pin,write
from tests.test_pilot_scientific_inclusion import seen
from tests.test_pilot_unlimited_integration import offline


def originals():
    return [json.loads(x) for x in (HIST/'artifacts/validated_observations.jsonl').read_text().splitlines()]


@pytest.fixture
def real(tmp_path):
    ref=manifest(tmp_path/'inputs');return ref,recover_native_jsonl(ref)


def test_authentic_six_records_exact_identity_bytes_provenance_and_candidate_assembly(real):
    ref,r=real;c=r['audit']['counts']
    assert [c[k] for k in ('authentic_JSONL_records_present','parsed','formal_V3_valid','verified_source_lineage','native_handoff_accepted','candidate_Core_assembled')]==[6]*6
    assert c['rejected_or_unresolved']==c['formal_materialized_relationships']==c['new_model_extractions']==0
    assert [json.loads(x['core_utf8'])['ExperimentalObservationV3'] for x in r['records']]==originals()
    cfg=json.loads(Path(ref['path']).read_text());raw=Path(cfg['native_jsonl']['path']).read_bytes()
    assert b''.join(raw[x['byte_start']:x['byte_end']] for x in r['audit']['records'])==raw
    assert len({x['original_experiment_identity'] for x in r['audit']['records']})==6
    assert {x['endpoint_as_recorded'] for x in r['audit']['records']}=={'overall survival'}
    for x in r['audit']['records']:
        assert x['original_source_hash']!=x['derived_source_hash']
        assert x['V2']['measurement_result_linkage']=='complete'
        assert x['V2']['full_machine_reuse_linkage'].startswith('blocked_')
        assert not x['scientific_authorization'] and not x['machine_reuse_authorized']
    for item in r['records']:
        core=json.loads(item['core_utf8'])['ExperimentalCore']
        assert all(f['canonical_identity'] is None for f in core['factors'])
        assert all(f['role'] not in ('intervention','treatment','exposure','genetic_manipulation') for f in core['factors'])
        assert all(x['sign'] is None and x['effect_size'] is None for x in core['results'])
        assert all(x['relation_type']=='measurement_produces_result' for x in core['linkages'])


def test_exact_anchor_and_cross_representation_mapping_are_distinct_from_XML_bytes(real):
    ref,r=real;cfg=json.loads(Path(ref['path']).read_text());article=json.loads(Path(cfg['article_json']['path']).read_text())
    xml=ET.parse(cfg['original_xml']['path']).getroot()
    for x in r['audit']['records']:
        for s in x['evidence_mapping']:
            assert article['sections'][s['section_index']]['text'][s['char_start']:s['char_end']]==s['text']
            assert s['xml_byte_offsets'] is None and s['original_anchor_id']!=s['evidence_span_id']
            assert s['original_provider_block_coordinates']['char_start']!=s['char_start']
            node=xml.findall(s['xml_node_selector'])[s['xml_paragraph_index_zero_based']]
            assert ' '.join(''.join(node.itertext()).split())[s['char_start']:s['char_end']]==s['text']
    assert r['audit']['provider_lineage']['model']=='deepseek-v4-pro'


def altered_cfg(tmp_path,real):
    ref,_=real;return deepcopy(json.loads(Path(ref['path']).read_text()))


def rebind_rows(tmp_path,cfg,rows):
    p=tmp_path/'SOFTWARE_FIXTURE_native.jsonl';p.write_text(''.join(json.dumps(x)+'\n' for x in rows));cfg['native_jsonl']=pin(p)
    cfg['record_inventory']=[{'observation_id':f['observation_id'],'formal_sha256':content_hash(f),
        'endpoint_raw':f['measurement']['endpoint_raw'],'design_type_raw':f['experiment']['design_type_raw'],
        'cohort_raw':f['experiment']['cohort_raw']} for f in rows]
    # Preserve explicit membership without conferring scientific truth.
    cfg['cohort_dependency']['native_observation_ids']=[f['observation_id'] for f in rows]


@pytest.mark.parametrize('kind',['malformed','missing','duplicate','conflicting','wrong_observation_identity',
    'wrong_block','wrong_coordinate','missing_span','invalid_cross_mapping','wrong_endpoint','wrong_design'])
def test_SOFTWARE_FIXTURE_record_corruption_fails_closed_without_filling_missing_values(tmp_path,real,kind):
    cfg=altered_cfg(tmp_path,real);rows=originals()
    if kind in ('malformed','missing'):
        p=tmp_path/'SOFTWARE_FIXTURE_malformed.jsonl';lines=Path(cfg['native_jsonl']['path']).read_bytes().splitlines(keepends=True)
        if kind=='malformed':lines[0]=b'{BROKEN\n'
        else:lines.pop(0)
        p.write_bytes(b''.join(lines));cfg['native_jsonl']=pin(p)
    else:
        if kind=='duplicate':rows[1]=deepcopy(rows[0])
        elif kind=='conflicting':rows[1]['observation_id']=rows[0]['observation_id']
        elif kind=='wrong_observation_identity':rows[0]['observation_id']='SOFTWARE_FIXTURE_wrong_identity'
        elif kind=='wrong_block':rows[0]['provenance']['evidence_spans'][0]['block_id']='SOFTWARE_FIXTURE_wrong_block'
        elif kind=='wrong_coordinate':rows[0]['provenance']['evidence_spans'][0]['char_start']+=1
        elif kind=='missing_span':rows[0]['provenance']['evidence_spans'].pop(0)
        elif kind=='invalid_cross_mapping':rows[0]['provenance']['evidence_spans'][0]['anchor_id']=rows[0]['provenance']['evidence_spans'][1]['anchor_id']
        elif kind=='wrong_endpoint':rows[0]['measurement']['endpoint_raw']='event-free survival'
        elif kind=='wrong_design':rows[0]['experiment']['design_type_raw']='assigned randomized TRIB3 intervention'
        rebind_rows(tmp_path,cfg,rows)
    out=recover_native_jsonl(pin(write(tmp_path/'SOFTWARE_FIXTURE_config.json',cfg)))
    assert out['audit']['counts']['candidate_Core_assembled']<6
    assert out['audit']['batch_rejection_reason'] or any(x['reasons'] for x in out['audit']['records'])
    assert all(not x['machine_reuse_authorized'] for x in out['audit']['records'])
    if kind not in ('malformed','missing','duplicate','conflicting'):
        assert out['audit']['counts']['candidate_Core_assembled']==5


@pytest.mark.parametrize('kind',['XML_hash','JSON_hash','representation','coordinates','projection_transform','projection_text','projection_inventory','block_hash','unsupported_payload_framing'])
def test_SOFTWARE_FIXTURE_global_representation_corruption_blocks_all_native_Core(tmp_path,real,kind):
    cfg=altered_cfg(tmp_path,real)
    if kind=='XML_hash':cfg['original_xml']['sha256']='0'*64
    elif kind=='JSON_hash':cfg['article_json']['sha256']='0'*64
    elif kind=='representation':cfg['source_representation']='ArticleJSON_as_original_XML'
    elif kind=='coordinates':cfg['coordinate_mapping']='raw_XML_byte_offsets'
    elif kind=='projection_transform':cfg['projection_transform']='unrecorded_NFKC_and_deleted_text'
    elif kind in ('projection_text','projection_inventory'):
        article=json.loads(Path(cfg['article_json']['path']).read_text())
        if kind=='projection_text':article['sections'][0]['text']+=' SOFTWARE_FIXTURE'
        else:article['sections'].pop()
        cfg['article_json']=pin(write(tmp_path/'SOFTWARE_FIXTURE_article.json',article))
    else:
        m=json.loads(Path(cfg['provider_request_manifest']['path']).read_text())
        if kind=='block_hash':m['block']['chunk_hash']='0'*64
        else:
            p=tmp_path/'SOFTWARE_FIXTURE_payload.txt';p.write_text('UNSUPPORTED\n'+Path(cfg['source_payload']['path']).read_text());cfg['source_payload']=pin(p)
            m['block']['chunk_hash']=m['source_payload_sent_sha256']=cfg['source_payload']['sha256']
        cfg['provider_request_manifest']=pin(write(tmp_path/'SOFTWARE_FIXTURE_manifest.json',m))
    out=recover_native_jsonl(pin(write(tmp_path/'SOFTWARE_FIXTURE_config.json',cfg)))
    assert out['audit']['counts']['formal_V3_valid']==6
    assert out['audit']['counts']['verified_source_lineage']==out['audit']['counts']['candidate_Core_assembled']==0
    assert out['audit']['batch_rejection_reason']


def test_compatibility_reader_reverifies_proof_and_rejects_authority_or_Core_tampering(tmp_path,real):
    _,r=real;item=r['records'][0]
    paths=[tmp_path/'packet.json',tmp_path/'prompt.txt',tmp_path/'core.json']
    for p,k in zip(paths,('packet_utf8','review_prompt_utf8','core_utf8')):p.write_text(item[k])
    bound=load_native_bound_packet_v1(*paths,item['native_representation_binding'])
    assert bound.observation_id==originals()[0]['observation_id']
    assert bound.input_hashes['source']!=bound.input_hashes['original_xml']
    with pytest.raises(ValueError,match='record_source_mismatch'):load_bound_packet(*paths)
    core=json.loads(paths[2].read_text());core['scientific_authorization']=True;paths[2].write_text(json.dumps(core))
    with pytest.raises(ValueError,match='Core_changed'):load_native_bound_packet_v1(*paths,item['native_representation_binding'])
    cfg=json.loads(Path(item['native_representation_binding']['configuration_pin']['path']).read_text());cfg['scientific_authorization']=True
    with pytest.raises(ValueError,match='authority_must_be_false'):recover_native_jsonl(pin(write(tmp_path/'SOFTWARE_FIXTURE_authority.json',cfg)))


def test_real_unified_Pilot_keeps_native_availability_separate_from_B4_propositions(tmp_path):
    b,c,r=trib_native(tmp_path/'inputs');p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.db',c,offline=True),b).run(r)
    assert p['terminal_state']=='NOT_EVALUABLE',p['reason']
    d=verify_dataset(tmp_path/'cases'/r['case_id']/'dataset')['scientific_counts']
    assert d['experimental_observations']==d['experimental_core']==d['native_representation_lineage']==6
    assert d['scientific_propositions']==6 and d['hypotheses']==d['human_reviews']==0
    availability=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role']=='native_representation_availability.json'))
    assert availability['native_Core_records_retained']==6 and availability['B4_propositions_available_independently']==6
    assert availability['native_records_permitted_downstream']==6
    # Existing B3 permits uncertain records for processing/review, never turns
    # that permission into INCLUDED or supported semantic/scientific authority.
    assert p['run_manifest']['scientific_inclusion_summary']['observation_decisions']=={'INCLUDED':3,'EXCLUDED':3,'UNCERTAIN':6}
    assert all(x['logical_id'].split(':',1)[0] in ('builder_v4','quality_v2') for x in p['costs']['requests'])
    outcomes=[json.loads(a['utf8']) for a in p['artifacts'] if a['role'].endswith('_linkage_outcome.json')]
    assert len(outcomes)==6 and all(x['status']=='prepared_NOT_AUTHORIZED' for x in outcomes)
    assert d['evidence_projection']==6


def test_actual_transitive_native_bytes_invalidate_completed_package_without_resending(tmp_path):
    b,c,r=trib_native(tmp_path/'inputs');ex=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.db',c,offline=True),b)
    old=ex.run(r);assert old['terminal_state']=='NOT_EVALUABLE',old['reason'];calls=len(b.transport.calls)
    ref=r['native_representation_handoffs']['PMC10515557'];cfg=json.loads(Path(ref['path']).read_text())
    cfg['coordinate_mapping']='SOFTWARE_FIXTURE_INVALID_CHANGED_MAPPING';old_identity=input_identity(r)
    Path(ref['path']).write_text(json.dumps(cfg));assert input_identity(r)!=old_identity
    with pytest.raises(CaseIntegrity,match='input_drift'):ex.run(r)
    assert len(b.transport.calls)==calls
