"""Authentic frozen records plus explicit software failure tests, no provider calls."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from code_engine.discovery.ai_review_shadow import content_hash, file_hash
from code_engine.extraction_assets.experimental_core.assembly import assemble_v3
from code_engine.extraction_assets.experimental_core.linkage_candidates import (
    candidate_input, produce_candidates, candidate_v2_diagnostic, render_candidate_prompt,
)
from code_engine.fulltext.source_windows import (
    grouped_plan_windows, verify_plan_accounting, construction_window,
    extraction_block, mapped_evidence_segments, coverage, text_hash,
)
from code_engine.fulltext.evidence_anchors import generate_evidence_anchors
from code_engine.orchestration.component_probe import request_proposal, conditional_linkage_request
from code_engine.orchestration.pilot_backend import PilotProviderTransport
from tests.test_fulltext_window_core_integration import AR, TRIB, blocks, ar_view
from tests.test_pilot_unlimited_integration import offline


def authentic(which):
    f = json.loads(AR.read_text())['ExperimentalObservationV3'] if which == 'ar' else json.loads(TRIB.read_text().splitlines()[0])
    p = AR if which == 'ar' else TRIB
    a = assemble_v3(f, source_artifact=str(p), source_blocks=blocks(f))
    c = a['envelope']['ExperimentalCore']
    return a, p, blocks(f), c


def response(a, c):
    # Test payload only: source semantics are NOT scientifically verified here.
    return {'schema_version': 'source_grounded_linkage_proposals_v1',
            'observation_identity': a['envelope']['ExperimentalObservationV3']['observation_id'],
            'core_revision_identity': c['revision']['identity'], 'proposals': [], 'unresolved_information': []}


@pytest.mark.parametrize('which', ['ar', 'trib'])
def test_source_bound_candidate_round_trip_does_not_promote_or_modify_core(which):
    a, p, b, c = authentic(which); before = content_hash(a)
    packet = candidate_input(a, source_artifact=str(p), source_blocks=b)
    assert packet['source_artifact_sha256'] == file_hash(p)
    spans = packet['evidence_spans']; r = response(a, c)
    for typ, s, t, basis in [
        ('factor_applies_to_measurement', c['factors'][0]['identity'], c['measurements'][0]['identity'], 'explicit_group_endpoint_statement'),
        ('measurement_produces_result', c['measurements'][0]['identity'], c['results'][0]['identity'], 'explicit_measurement_result_statement'),
        ('result_compared_against_factor', c['results'][0]['identity'], c['factors'][1]['identity'], 'explicit_comparison_statement'),
        ('observation_belongs_to_experiment_scope', c['revision']['identity'], c['revision']['experiment_scope_identity'], 'explicit_scope_statement')]:
        r['proposals'].append(dict(relation_type=typ, source_ref=s, target_ref=t, source_basis=basis,
                                  evidence_refs=[x['evidence_span_id'] for x in spans],
                                  support_explanation='SOFTWARE STRUCTURAL ROUND TRIP ONLY; not scientific validation'))
    out = produce_candidates(a, r, source_artifact=str(p), source_blocks=b, proposal_origin='software_test_only')
    assert len(out['native_candidate_linkages']) == 4
    assert all(x['authority_state'] == 'candidate' for x in out['source_grounded_candidates'])
    assert all(x['status'] == 'rejected' for x in out['materialization_decisions'])
    diag = candidate_v2_diagnostic(a, out)
    assert diag['linkage_v2']['factor_measurement_application_linkage'] == 'complete'
    assert diag['linkage_v2']['comparative_reference_linkage'] == 'complete'
    assert diag['original_linkage_v2']['full_machine_reuse_linkage'].startswith('blocked_')
    assert not diag['scientific_authorization'] and content_hash(a) == before
    assert 'paragraph' in render_candidate_prompt(packet)


@pytest.mark.parametrize('fault', ['endpoint', 'anchor', 'authority', 'binding', 'proximity', 'duplicate', 'source'])
def test_candidate_rejects_invalid_interfaces(fault):
    a, p, b, c = authentic('ar'); r = response(a, c)
    prop = dict(relation_type='factor_applies_to_measurement', source_ref=c['factors'][0]['identity'], target_ref=c['measurements'][0]['identity'],
                evidence_refs=[a['envelope']['ExperimentalObservationV3']['evidence_span_ids'][0]], source_basis='explicit_group_endpoint_statement', support_explanation='software rejection fixture')
    r['proposals'] = [prop]
    if fault == 'endpoint': prop['target_ref'] = c['results'][0]['identity']
    elif fault == 'anchor': prop['evidence_refs'] = ['UNKNOWN']
    elif fault == 'authority': prop['authority_state'] = 'validated_source_grounded'
    elif fault == 'binding': r['core_revision_identity'] = 'DIFFERENT'
    elif fault == 'proximity': prop['source_basis'] = 'paragraph_proximity'
    elif fault == 'duplicate': r['proposals'].append(deepcopy(prop))
    elif fault == 'source': b = {k: 'WRONG SOURCE' for k in b}
    with pytest.raises(ValueError): produce_candidates(a, r, source_artifact=str(p), source_blocks=b, proposal_origin='software_test')


def test_grouped_authentic_source_full_accounting_native_contracts_and_all_anchor_coordinates():
    article = ar_view(); plan = grouped_plan_windows(article, content_hash(article))
    assert len(plan['regions']) == 83 and len(plan['windows']) == 46
    accounted = verify_plan_accounting(article, plan)
    assert accounted['accounting_percent'] == 100 and accounted['source_characters'] == 96327
    for w in plan['windows']:
        construction_window(w, 'src_' + '1' * 64)
        assert len(w['text']) <= 16000
        assert w['v3_dispatch_eligible'] and w['v3_preflight']['input_token_estimate'] <= 6000
        block = extraction_block(w, article['pmcid'], article['pmid'])
        anchors = generate_evidence_anchors(block_id=w['window_id'], source_document_id=article['pmcid'], block_text=block['text'], section=w['section_title'])
        for anchor in anchors:
            ev = {**anchor.as_dict(), 'evidence_span_id': anchor.anchor_id}
            for mapped in mapped_evidence_segments(w, ev, block=block):
                assert article['sections'][mapped['section_index']]['text'][mapped['char_start']:mapped['char_end']] == mapped['text']
    cov = coverage(plan, {})
    assert cov['extraction_processed_percent'] == 0 and not cov['source_processing_complete']
    states = {w['window_id']: {k: {'status': 'processed'} for k in ('builder_v4', 'quality_v2', 'experimental_v3_core')} for w in plan['windows']}
    assert coverage(plan, states)['extraction_processed_percent'] == 100 # software coverage states only
    broken = deepcopy(plan); broken['windows'][0]['fragments'][0]['text'] = 'REPLACED'
    with pytest.raises(ValueError): verify_plan_accounting(article, broken)


def test_grouped_cross_region_evidence_keeps_each_source_intersection_and_rejects_prefix_only():
    article = ar_view(); plan = grouped_plan_windows(article, '1' * 64)
    w = next(w for w in plan['windows'] if len(w['fragments']) > 1); b = extraction_block(w, '', '')
    left, right = b['source_fragment_map'][:2]; a, end = left['block_char_end'] - 3, right['block_char_start'] + 4
    raw = b['text'][a:end]; ev = dict(evidence_span_id='SOFTWARE_JOIN_TEST',char_start=a,char_end=end,text=raw,text_hash=text_hash(raw))
    mapped = mapped_evidence_segments(w,ev,block=b)
    assert len(mapped)==2 and len(mapped[0]['text'])==3 and len(mapped[1]['text'])==4
    raw=b['text'][:4]
    with pytest.raises(ValueError): mapped_evidence_segments(w,dict(evidence_span_id='PREFIX',char_start=0,char_end=4,text=raw,text_hash=text_hash(raw)),block=b)


PRICING = dict(model='deepseek-flash', input_usd_per_million='0.30', output_usd_per_million='1.20', context_tokens=1000000, max_output_tokens=32768)

def retained_provider_v3(tmp_path):
    """Replay authentic historical provider text; no synthesized model evidence."""
    from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import TrustedDraftContextV3, hydrate_draft_response_v3
    from code_engine.fulltext.fulltext_l1_v2 import parse_draft_response
    base=Path('runs/20260902_single_source_provider_extraction_smoke_pmc10515557_v1/artifacts')
    m=json.loads((base/'provider_request_manifest.json').read_text())
    raw=base/'raw_provider_response.txt'; text=Path(m['source_payload_sent_path']).read_text()
    ctx=TrustedDraftContextV3(run_id='offline_retained_provider_replay',block_id=m['block']['block_id'],parent_block_id=m['block']['parent_block_id'],child_block_id=m['block']['child_block_id'],block_text=text,source_block_hash=m['source_payload_sent_sha256'],source_document_id=m['paper_identity']['pmcid'],paper_id=m['paper_identity']['paper_id'],pmid=m['paper_identity']['pmid'],pmcid=m['paper_identity']['pmcid'],fulltext_source_hash=m['source_fulltext_sha256'],source_artifact=m['source_fulltext_path'],section='Results')
    hydrated=hydrate_draft_response_v3(parse_draft_response(json.loads(raw.read_text())),ctx)
    assert not hydrated.rejected
    f=hydrated.formal_response['experimental_observations'][0];b={ctx.block_id:text}
    a=assemble_v3(f,source_artifact=ctx.source_artifact,source_blocks=b)
    validated=tmp_path/'retained_provider_rehydrated.json';validated.write_text(json.dumps(hydrated.formal_response))
    return a,ctx.source_artifact,b,raw,validated,ctx


def test_probe_reserves_full_retries_binds_files_and_has_no_implicit_execution(tmp_path):
    a,p,b,raw,validated,ctx=retained_provider_v3(tmp_path)
    kwargs=dict(source_artifact=str(p),source_blocks=b,actual_v3_response_file=raw,validated_v3_file=validated,hydration_context=ctx)
    prepared=conditional_linkage_request(a,**kwargs)
    body=prepared['body']; proposal=request_proposal(body,source_identity=a['envelope']['ExperimentalObservationV3']['provenance']['pmcid'], source_files=[p],pricing=PRICING)
    from decimal import Decimal
    assert Decimal(proposal['full_retry_reservation_usd']) == 2 * Decimal(proposal['per_attempt_reservation_usd'])
    assert not proposal['execution_authorized'] and not prepared['execution_authorized']
    with pytest.raises(RuntimeError,match='not_authorized'): PilotProviderTransport().send('deepseek',body)
    with pytest.raises(ValueError,match='exceeds_reserved'): conditional_linkage_request(a,**kwargs,input_token_ceiling=1)
    with pytest.raises(ValueError,match='required'): conditional_linkage_request(a,**{**kwargs,'actual_v3_response_file':tmp_path/'MISSING'})
    with pytest.raises(ValueError,match='binding_mismatch'): conditional_linkage_request(a,**{**kwargs,'validated_v3_file':AR})


def test_related_methods_anchor_is_exact_sidecar_evidence_never_silent_v3_mutation():
    a,p,b,c=authentic('ar');before=content_hash(a);article=ar_view()
    sec=next(s for s in article['sections'] if s['section_title'].endswith('fiber csa measurements'))
    raw=sec['text']; block_id='source-region:'+sec['source_region_id'];b[block_id]=raw
    span=dict(evidence_span_id='supplemental_'+text_hash(raw),anchor_id=None,anchor_version='exact_source_region_sidecar_v1',source_document_id='PMC13557098',block_id=block_id,text=raw,text_hash=text_hash(raw),source_role='methods',span_type='setup',section=sec['section_title'],char_start=0,char_end=len(raw))
    packet=candidate_input(a,source_artifact=str(p),source_blocks=b,additional_evidence=[span])
    assert len(packet['evidence_spans'])==9 and content_hash(a)==before
    bad={**span,'source_document_id':'DIFFERENT_PAPER'}
    with pytest.raises(ValueError,match='cross_source'):candidate_input(a,source_artifact=str(p),source_blocks=b,additional_evidence=[bad])
    with pytest.raises(ValueError,match='coordinate'):candidate_input(a,source_artifact=str(p),source_blocks=b,additional_evidence=[{**span,'char_end':len(raw)+1}])


def test_actual_wrapped_trib_source_uses_original_xml_paths_and_complete_accounting():
    from code_engine.fulltext.source_windows import jats_source_view
    manifest=json.loads((TRIB.parent/'provider_request_manifest.json').read_text());path=Path(manifest['source_fulltext_path'])
    view=jats_source_view(path,manifest['paper_identity']);plan=grouped_plan_windows(view,file_hash(path))
    assert len(plan['regions'])==26 and len(plan['windows'])==20
    assert all(s['source_xpath'].startswith('/pmc-articleset/article[1]/') for s in view['sections'])
    assert view['original_xml_sha256']==manifest['source_fulltext_sha256']
    assert verify_plan_accounting(view,plan)['source_characters']==21479


def test_jats_multiple_articles_are_not_silently_collapsed(tmp_path):
    from code_engine.fulltext.source_windows import jats_source_view
    p=tmp_path/'SOFTWARE_WRAPPER.xml';p.write_text('<pmc-articleset><article/><article/></pmc-articleset>')
    with pytest.raises(ValueError,match='single_JATS_article'):jats_source_view(p,{})


def test_frozen_v3_preflight_is_enforced_before_transport(tmp_path):
    from tests.test_pilot_unlimited_integration import existing_backend
    from code_engine.fulltext.source_windows import plan_windows
    backend,_=existing_backend(tmp_path);article=ar_view()
    # Authentic oversized Results region, not a fabricated scientific response.
    w=next(w for w in plan_windows(article,'1'*64)['windows'] if w['section_index']==8)
    payload={'article':article,'window':w,'source_sha256':'1'*64,'source_artifact':str(AR)}
    with pytest.raises(ValueError,match='frozen_V3_preflight'):backend.input_upper_bound('experimental_v3_core',payload)
    with pytest.raises(ValueError,match='frozen_V3_preflight'):backend.complete('experimental_v3_core','PMC13557098',payload,provider='deepseek',model='deepseek-flash',max_output_tokens=32768)
    assert backend.transport.calls==[]


def test_multifigure_sentence_remains_accounted_when_frozen_preflight_blocks_it():
    # Software-only text tests planning disposition, not biological evidence.
    a={'pmcid':'TEST_ONLY','sections':[{'section_id':'software','section_title':'Results','text':'Software fixture compares Figure 1 and Figure 2 in one sentence.'}]}
    p=grouped_plan_windows(a,'1'*64)
    assert len(p['windows'])==1 and not p['windows'][0]['v3_dispatch_eligible']
    assert p['blocked_window_ids'] and verify_plan_accounting(a,p)['accounting_percent']==100
    assert coverage(p,{})['extraction_processed_percent']==0


def test_unsplittable_long_token_with_trailing_space_stays_pending_without_recursive_loop():
    # A source-shape regression only; no synthetic biological evidence.
    a={'pmcid':'TEST_ONLY','sections':[{'section_id':'software','section_title':'Results','text':'X'*10000+' '}]}
    plan=grouped_plan_windows(a,'1'*64)
    assert len(plan['windows'])==1 and not plan['windows'][0]['v3_dispatch_eligible']
    assert verify_plan_accounting(a,plan)['accounting_percent']==100
