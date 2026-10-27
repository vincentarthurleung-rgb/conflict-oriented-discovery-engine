"""No new scientific model responses: authentic records or software-only metadata."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,socket
import pytest
from code_engine.fulltext.source_windows import jats_source_view,plan_windows,construction_window,coverage,mapped_evidence,aggregate_observations,text_hash
from code_engine.extraction_assets.experimental_core.assembly import assemble_v3
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.orchestration.pilot_dataset import verify_dataset
from tests.test_pilot_unlimited_integration import existing_backend,seen,offline
from tests.pilot_offline_support import request
from code_engine.orchestration.pilot_case import PilotCaseExecutor
from code_engine.orchestration.pilot_budget import ModelBudget

AR=Path('runs/20261014_code_first_source_grounded_figure1c_experimental_record_offline/record.json')
TRIB=Path('runs/20260902_single_source_provider_extraction_smoke_pmc10515557_v1/artifacts/validated_observations.jsonl')
def blocks(f):
 if f['provenance']['pmcid']=='PMC13557098':
  r=json.loads(AR.read_text());text=Path(r['source_binding']['BODY_reference']['artifact_path']).read_text()
 else:
  m=json.loads((TRIB.parent/'provider_request_manifest.json').read_text());text=Path(m['source_payload_sent_path']).read_text()
 return {s['block_id']:text for s in f['provenance']['evidence_spans']}
def ar_view():
 r=json.loads(AR.read_text());p=Path(r['source_binding']['normalized_JATS_reference']['artifact_path']);return jats_source_view(p,{'pmid':'42715313','pmcid':'PMC13557098','doi':'10.1126/sciadv.aec8073'})

def test_authentic_long_source_windows_cover_every_projected_character_and_preserve_coordinates():
 article=ar_view();plan=plan_windows(article,content_hash(article),max_chars=1700,overlap_chars=100)
 assert sum(len(s['text']) for s in article['sections'])>60000
 assert len(plan['windows'])>1 and plan==plan_windows(article,content_hash(article),max_chars=1700,overlap_chars=100)
 for w in plan['windows']:
  sec=article['sections'][w['section_index']];assert w['text']==sec['text'][w['source_char_start']:w['source_char_end']]
  construction_window(w,'src_'+'1'*64)
 states={w['window_id']:{k:{'status':'processed'} for k in ('builder_v4','quality_v2','experimental_v3_core')} for w in plan['windows']}
 cov=coverage(plan,states);assert cov['segmented_supported_region_percent']==cov['extraction_processed_percent']==100
 assert not cov['scientific_extraction_complete'] # fabricated coverage states are software-only.
 states[plan['windows'][0]['window_id']]['experimental_v3_core']={'status':'failed','reason':'EXPLICIT SOFTWARE TEST'}
 assert coverage(plan,states)['extraction_processed_percent']<100


def test_two_authentic_designs_automatic_assembly_does_not_create_missing_links():
 forms=[json.loads(AR.read_text())['ExperimentalObservationV3'],*[json.loads(x) for x in TRIB.read_text().splitlines()]]
 assert len({f['provenance']['pmcid'] for f in forms})==2
 for f in forms:
  rebuilt=assemble_v3(f,source_artifact=str(AR if f['provenance']['pmcid']=='PMC13557098' else TRIB),source_blocks=blocks(f))
  assert rebuilt['assembly_mode']=='automatic_V3_field_assembly'
  assert rebuilt['audit']['reference_audit']['valid'] and rebuilt['audit']['linkage']['measurement_result_linkage']=='complete'
  assert rebuilt['audit']['linkage']['full_machine_reuse_linkage'].startswith('blocked_')
  core=rebuilt['envelope']['ExperimentalCore'];assert not any(x['relation_type']=='factor_applies_to_measurement' for x in core['linkages'])
  assert all(x['canonical_identity'] is None for x in core['factors']) and all(x['sign'] is None and x['effect_size'] is None for x in core['results'])
  assert not rebuilt['strict_core_eligible']


def test_unknown_anchor_rejected_and_same_scope_not_experimental_linkage():
 f=json.loads(AR.read_text())['ExperimentalObservationV3'];a=assemble_v3(f,source_artifact=str(AR),source_blocks=blocks(f));assert 'explicit_factor_to_measurement_linkage_missing' in a['missing']
 f['interventions'][0]['evidence_span_ids'].append('NONEXISTENT')
 with pytest.raises(ValueError,match='unknown_component_evidence'):assemble_v3(f,source_artifact=str(AR),source_blocks=blocks(f))


def test_dedup_requires_exact_source_coordinates_and_raw_observation():
 f=json.loads(AR.read_text())['ExperimentalObservationV3'];ev=[{'region_id':'r','char_start':1,'char_end':2,'text_hash':'abc'}];a={'ExperimentalObservationV3':f,'source_evidence':ev,'window_id':'w1'};b=deepcopy(a);b['window_id']='w2'
 assert len(aggregate_observations([a,b]))==1
 b['source_evidence'][0]['char_start']=2;assert len(aggregate_observations([a,b]))==2
 b=deepcopy(a);b['ExperimentalObservationV3']['experiment']['experiment_label_raw']='different explicitly labeled scope';assert len(aggregate_observations([a,b]))==2


def test_blocked_authentic_window_execution_exports_all_pending_windows_and_no_fake_observation(tmp_path,seen):
 backend,cfg=existing_backend(tmp_path);article=ar_view();p=tmp_path/'complete_ar_view.json';p.write_text(json.dumps(article));spec={'identity':{k:article[k] for k in ('pmid','pmcid','doi')},'article_path':str(p),'source_token':'src_'+'1'*64,'binding':{'source_sha256':file_hash(p)},'complete_source_windows':True}
 seen.sources['pmcid'].add('PMC13557098');seen.sources['pmid'].add('42715313')
 backend.catalog.specs=[spec];backend.catalog.select_sources=lambda r:[spec]
 calls=[]
 def no_response(*a,**k):calls.append(1);raise RuntimeError('No frozen response bound to this new window; no output invented')
 backend.transport.send=no_response;b=ModelBudget(tmp_path/'budget.db',cfg,offline=True);r=request('AR-WINDOWS');r.pop('source_count');r['model_stages']={k:'review' if k=='ai_review' else 'batch' for k in r['model_stages']}
 ex=PilotCaseExecutor(tmp_path/'cases',seen,b,backend);out=ex.run(r)
 assert out['terminal_state']=='MODEL_FAILED' and len(calls)==1
 cov=out['run_manifest']['fulltext_coverage']['PMC13557098'];assert cov['extraction_processed_percent']==0 and not cov['source_processing_complete']
 dataset=verify_dataset(tmp_path/'cases/AR-WINDOWS/dataset');assert dataset['scientific_counts']['fulltext_windows']==2 and dataset['scientific_counts']['experimental_core']==0 and not dataset['pipeline_complete']
 again=ex.run(r);assert again['package_sha256']==out['package_sha256'] and len(calls)==1
 assert all(s['stages']['experimental_v3_core']['unprocessed_intervals'] for s in cov['regions'])


def test_existing_explicit_native_links_are_consumed_without_claiming_automatic_recovery():
 base=Path('runs/20261016_code_comparable_evidence_discovery_review_integration_seen_offline/PMC7749157');r=json.loads((base/'v3_core_draft.json').read_text());packet=json.loads((base/'evidence_packet.json').read_text());article=json.loads(Path(packet['source']['article_path']).read_text());f=r['ExperimentalObservationV3'];ctx={f['provenance']['pmcid']+':'+s['section_id']:s['text'] for s in article['sections']}
 out=assemble_v3(f,source_artifact=str(base/'v3_core_draft.json'),source_blocks=ctx,explicit_core=r['ExperimentalCore'])
 assert out['audit']['linkage']['full_machine_reuse_linkage']=='complete' and out['assembly_mode']=='existing_native_core_reuse' and not out['strict_core_eligible']
 broken=deepcopy(r['ExperimentalCore']);broken['linkages'][0]['source_ref']='DANGLING'
 with pytest.raises(ValueError):assemble_v3(f,source_artifact=str(base/'v3_core_draft.json'),source_blocks=ctx,explicit_core=broken)


def test_extreme_overlap_advances_and_local_to_source_mapping_is_exact():
 a={'sections':[{'section_id':'software','section_title':'SOFTWARE FIXTURE ONLY','text':'A sentence. More text. Another sentence. '*5}]};p=plan_windows(a,'1'*64,max_chars=20,overlap_chars=19);assert all(w['source_char_end']>w['source_char_start'] for w in p['windows']) and p['windows'][-1]['source_char_end']==len(a['sections'][0]['text'])
 w=p['windows'][1];span={'evidence_span_id':'fixture','char_start':0,'char_end':3,'text':w['text'][:3],'text_hash':text_hash(w['text'][:3])};mapped=mapped_evidence(w,span);assert a['sections'][0]['text'][mapped['char_start']:mapped['char_end']]==span['text']
 with pytest.raises(ValueError):mapped_evidence(w,{**span,'text':'FAKE'})


def test_existing_results_methods_framing_preserves_source_offsets():
 from code_engine.fulltext.source_windows import extraction_block
 from code_engine.fulltext.evidence_anchors import generate_evidence_anchors
 article=ar_view();plan=plan_windows(article,'1'*64)
 for kind,expected in [('results','current'),('methods','methods')]:
  w=next(w for w in plan['windows'] if kind in w['section_title'].casefold())
  b=extraction_block(w,'PMC13557098','42715313');anchors=generate_evidence_anchors(block_id=b['block_id'],source_document_id='PMC13557098',block_text=b['text'],section=w['section_title'])
  assert anchors and anchors[0].source_role==expected
  mapped=mapped_evidence(w,{**anchors[0].as_dict(),'evidence_span_id':'actual_source_span'},source_prefix_chars=b['source_prefix_chars'])
  assert article['sections'][w['section_index']]['text'][mapped['char_start']:mapped['char_end']]==anchors[0].text


def test_dataset_does_not_double_count_an_assembled_hydrated_observation(tmp_path):
 from code_engine.orchestration.pilot_dataset import export_attempt_dataset
 f=json.loads(AR.read_text())['ExperimentalObservationV3'];a=assemble_v3(f,source_artifact=str(AR),source_blocks=blocks(f));case=tmp_path/'case';case.mkdir();(case/'core.json').write_text(json.dumps(a['envelope']));(case/'one_incomplete_experimental_records.json').write_text(json.dumps({'output':{'incomplete':{'formal_v3':{'experimental_observations':[f]}}}}))
 m={'case_id':'SOFTWARE-EXPORT-CHECK','question':'No new science; duplicate serialization check','input_sha256':'1'*64,'sources':[],'stages':[],'terminal_state':'INSUFFICIENT_EVIDENCE'};v=export_attempt_dataset(m,case,tmp_path/'out')
 assert v['scientific_counts']['experimental_observations']==1 and v['scientific_counts']['extraction_observation_instances']==1
