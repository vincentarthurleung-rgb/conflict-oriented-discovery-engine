"""Exact frozen evidence and instrumented software transports, never fresh science."""
from copy import deepcopy
from pathlib import Path
import json
import hashlib
import socket
import pytest
from code_engine.domain.models import default_domain_profiles
from code_engine.domain.prompt_registry import default_prompt_registry
from code_engine.domain.extraction_routing import (
    block_design,design_from_spans,paper_design,routing_decision,prepare_v3_prompt,
    prepare_linkage_prompt,routed_v3_preflight,V3_PROFILE,LINKAGE_PROFILE,
)
from code_engine.discovery.ai_review_shadow import content_hash,file_hash
from code_engine.fulltext.source_windows import grouped_plan_windows,extraction_block,verify_plan_accounting
from code_engine.fulltext.fulltext_l1_v2 import build_prompt,FulltextTokenBudget,token_budget_preflight
from code_engine.fulltext.evidence_anchors import generate_evidence_anchors
from code_engine.orchestration.component_probe import prepare_v3_component_request
from code_engine.query.intake import parse_research_intake
from tests.test_fulltext_window_core_integration import AR,TRIB,ar_view
from tests.test_pilot_unlimited_integration import existing_backend,offline,seen

HIF=Path('runs/20261016_code_comparable_evidence_discovery_review_integration_seen_offline/PMC7749157')

def native(which):
    if which=='ar':return json.loads(AR.read_text())['ExperimentalObservationV3']
    if which=='trib':return json.loads(TRIB.read_text().splitlines()[0])
    return json.loads((HIF/'v3_core_draft.json').read_text())['ExperimentalObservationV3']


def fixture_block(text):
    return {'block_id':'SOFTWARE_ROUTING_TEST','text':'CURRENT_RESULTS: '+text,'section':{'section_title':'Results'},'paper_metadata':{'pmcid':'SOFTWARE_TEST'}}


def test_six_existing_profiles_and_actual_legacy_versions_are_preserved():
    profiles=default_domain_profiles();assert len(profiles)==6
    assert {p.domain_id for p in profiles}=={'general_biomedical','neuropharmacology','drug_target_binding','pathway_biology','clinical_outcome','protein_interaction'}
    for domain in profiles:
        legacy=default_prompt_registry().get_profile(domain.prompt_profile_id)
        assert legacy.version=='2.1' and '{chunk_text}' in legacy.template
        assert legacy.output_schema_version=='l1_v2_evidence_mechanism_schema'


@pytest.mark.parametrize('which,expected',[('ar','in_vivo'),('trib','observational_clinical'),('hif','in_vitro')])
def test_authentic_observation_designs_use_exact_source_spans_not_v3_type_labels(which,expected):
    f=native(which);result=design_from_spans(f['provenance']['evidence_spans'],scope='native_observation')
    assert result['designs']==[expected] and not result['scientific_authorization']
    assert result['evidence_hits']
    # Mislabeling a model raw design does not change evidence-cue routing.
    f['experiment']['design_type_raw']='interventional clinical trial'
    assert design_from_spans(f['provenance']['evidence_spans'],scope='native_observation')['designs']==[expected]


@pytest.mark.parametrize('text,expected',[
    ('Patients were randomized to drug or placebo in this clinical trial.',['interventional_clinical']),
    ('In this retrospective cohort study, patient data were collected.',['observational_clinical']),
    ('Cultured cells were incubated with drug. Mice were injected with the drug.',['in_vitro','in_vivo']),
    ('RNA-seq measured transcript abundance. Molecular docking predicted affinity.',['computational','omics']),
    ('A biomarker was associated with outcome.',['unknown']),
    ('Patients received standard care; treatment assignment was not reported.',['unknown']),
    ('No in vivo experiments were performed.',['unknown']),
    ('Patients were not randomized to treatment.',['unknown']),
    ('We propose that future experiments might use cultured cells.',['unknown']),
])
def test_mixed_ambiguous_negated_and_nonassigned_designs_are_not_forced(text,expected):
    actual=block_design(fixture_block(text));assert actual['designs']==expected
    assert actual['mixed_design']==(len(expected)>1)


def test_paper_scope_is_mixed_but_ar_observation_scope_is_in_vivo():
    article=ar_view();paper=paper_design(article)
    assert {'in_vitro','in_vivo','omics'}<=set(paper['designs']) and paper['mixed_design']
    assert paper['paper_domain_semantic_classification'].startswith('not_established')
    assert design_from_spans(native('ar')['provenance']['evidence_spans'],scope='observation')['designs']==['in_vivo']


def test_question_domain_is_separate_and_invalid_domain_falls_back():
    d=block_design(fixture_block('Cells were incubated in hypoxia.'))
    assert routing_decision(d,question_domain='neuropharmacology')['selected_domain']=='neuropharmacology'
    assert routing_decision(d,question_domain='NONEXISTENT')['question_domain_state']=='general_fallback'
    clinical=block_design(fixture_block('Survival differed between biomarker-positive and -negative patients.'))
    route=routing_decision(clinical,question_domain='pathway_biology')
    assert route['question_domain']=='pathway_biology' and route['selected_domain']=='clinical_outcome'
    assert route['semantics_normalization_profile']=='generic_experimental'


def test_v3_prompt_is_versioned_different_by_design_and_retains_frozen_schema():
    article={'pmcid':'SOFTWARE_TEST','pmid':'TEST','sections':[]};b=fixture_block('Cells were incubated in hypoxia.')
    frozen=build_prompt({'pmcid':article['pmcid'],'pmid':article['pmid']},b)
    text,route=prepare_v3_prompt(article,b,question_domain='general_biomedical')
    assert text.startswith(frozen) and route['prompt_profile']==V3_PROFILE
    assert not route['legacy_schema_compatible_with_V3'] and 'Root object: {"claims"' not in text
    changed,other=prepare_v3_prompt(article,b,question_domain='protein_interaction')
    assert changed!=text and content_hash(other)!=content_hash(route)
    assert route['schema_sha256'] and route['input_hashes']['block']
    base=token_budget_preflight(article,b,FulltextTokenBudget());routed=routed_v3_preflight(article,b)
    assert routed['input_token_estimate']>base['input_token_estimate']
    assert routed['input_token_estimate']<=6000 and routed['model_context_limit']==131072


def test_routed_windows_account_for_source_and_budget_routing_overhead():
    a=ar_view();p=grouped_plan_windows(a,content_hash(a),routing_domain='general_biomedical')
    assert verify_plan_accounting(a,p)['accounting_percent']==100
    assert all(w['v3_preflight']['routing_overhead_token_estimate']>0 for w in p['windows'])
    assert all(w['v3_preflight']['input_token_estimate']<=6000 for w in p['windows'] if w['v3_dispatch_eligible'])


def test_actual_backend_send_matches_prepared_routed_body_and_input_bound(tmp_path):
    backend,_=existing_backend(tmp_path);backend.annotations={};backend.pricing['experimental_v3_core']['max_output_tokens']=32768
    backend.bind_question_profile(parse_research_intake('domain: general_biomedical; compare experimental evidence',execute=False,use_api=False).model_dump(mode='json'))
    a=ar_view();plan=grouped_plan_windows(a,content_hash(a),routing_domain='general_biomedical')
    w=next(w for w in plan['windows'] if any(f['section_index']==5 for f in w['fragments']))
    payload={'article':a,'window':w,'source_sha256':content_hash(a),'source_artifact':str(AR)}
    body,block,route=backend.prepare_v3_request(payload,model='deepseek-flash',max_output_tokens=32768)
    observed=[]
    def software_empty(provider,actual):
        observed.append(actual)
        from code_engine.schemas.fulltext_observation_draft import fulltext_l1_draft_prompt_examples
        empty,_=fulltext_l1_draft_prompt_examples()
        return {'model':actual['model'],'usage':{'prompt_tokens':100,'completion_tokens':50},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(empty)}}]}
    backend.transport.send=software_empty
    out,_=backend.complete('experimental_v3_core',a['pmcid'],payload,provider='deepseek',model='deepseek-flash',max_output_tokens=32768)
    from code_engine.system_b.annotation_schemas.registry import canonical_json
    assert observed==[body] and backend.input_upper_bound('experimental_v3_core',payload)==len(canonical_json(body).encode())
    assert out['records']==[] and out['incomplete']['prompt_routing']['provider_body_sha256']==content_hash(body)
    assert route['study_design']['designs']==['in_vivo']
    prepared=prepare_v3_component_request(a,block,question_domain='general_biomedical')
    assert prepared['body']==body and not prepared['execution_authorized']


def test_linkage_candidate_preparation_routes_native_evidence_without_new_authority():
    p=Path('runs/20261019_code_source_grounded_linkage_component_probe_offline/final_run/candidate_packets/PMC10515557/input.json')
    packet=json.loads(p.read_text())
    from code_engine.extraction_assets.experimental_core.linkage_candidates import render_candidate_prompt
    base=render_candidate_prompt(packet);text,route=prepare_linkage_prompt(packet,base)
    assert text.startswith(base) and route['prompt_profile']==LINKAGE_PROFILE
    assert route['selected_domain']=='clinical_outcome' and route['study_design']['designs']==['observational_clinical']
    assert not route['scientific_authorization']


def test_executor_records_intake_and_source_routing_before_reusing_native_records(tmp_path,seen):
    from code_engine.orchestration.pilot_budget import ModelBudget
    from code_engine.orchestration.pilot_case import PilotCaseExecutor
    from tests.pilot_offline_support import request
    backend,cfg=existing_backend(tmp_path);req=request('ROUTING-INTEGRATION');req.pop('source_count')
    req['question']='domain: protein_interaction; bounded offline routing integration'
    req['model_stages']={k:'review' if k=='ai_review' else 'batch' for k in req['model_stages']}
    p=PilotCaseExecutor(tmp_path/'cases',seen,ModelBudget(tmp_path/'budget.db',cfg,offline=True),backend).run(req)
    dest=tmp_path/'cases/ROUTING-INTEGRATION'
    assert p['run_manifest']['question_domain_routing']['domain_id']=='protein_interaction'
    assert list(dest.glob('*_paper_design_routing.json'))
    receipts=[json.loads(x.read_text()) for x in dest.glob('builder_v4_*_prompt_routing.json')]
    assert receipts and all(x['question_domain']=='protein_interaction' and x['prompt_selection']=='fixed_frozen_prompt' for x in receipts)
    v3=[json.loads(x.read_text()) for x in dest.glob('experimental_v3_core_*_prompt_routing.json')]
    assert v3 and all(x['prompt_selection']=='pinned_native_annotation_reuse_no_model_request' for x in v3)
