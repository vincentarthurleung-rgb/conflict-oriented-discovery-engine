"""Authentic frozen regressions and explicitly SOFTWARE_FIXTURE controls."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import pytest

from code_engine.discovery.directional_discovery import (
    native_direction_record, discover_directions, run_initial_discovery, LEVELS,
)
from code_engine.extraction.direction_semantics import effective_legacy_direction
from code_engine.extraction.polarity import normalize_directional_relation
from code_engine.extraction.converters import legacy_tuple_to_l1_claim,l1_claim_to_legacy_tuple
from code_engine.graph.conflict_discovery import build_conflict_graph
from code_engine.graph.probabilistic_conflict import binary_direction_summary
from code_engine.discovery.ai_review_shadow import content_hash

R=Path(__file__).resolve().parents[1]
FROZEN=R/'runs/20261030_code_b4_11_bounded_hif_identity_verification_offline/release_v2'


def software_record(sign, paper='1', *, endpoint='protein abundance', tested='treated', reference='control',
                    text=None, kind='in_vitro', observation='software'):
    """No biological experiment, model success or real canonical ID is asserted."""
    text=text or ('protein abundance increased' if sign=='positive' else 'protein abundance decreased' if sign=='negative' else 'direction unresolved')
    text='SOFTWARE_FIXTURE: '+text+'. treated and control; assay of protein abundance.'
    span={'evidence_span_id':'SOFTWARE_FIXTURE:'+paper,'source_document_id':'SOFTWARE_FIXTURE:'+paper,
          'block_id':'SOFTWARE_FIXTURE:block','char_start':0,'char_end':len(text),'text':text,
          'text_hash':hashlib.sha256(text.encode()).hexdigest()}
    refs=[span['evidence_span_id']]
    f={'observation_id':'SOFTWARE_FIXTURE:'+observation,'provenance':{'evidence_spans':[span]},
       'experiment':{'design_type':kind,'experimental_design_raw':'retrospective cohort study' if kind=='observational' else 'assigned experiment',
                     'comparison_arm_raw':tested,'control_arm_raw':reference,'model_system_raw':'SOFTWARE_FIXTURE'},
       'candidate_relation':{'lexical_direction':sign,'lexical_direction_raw':sign,'relation_raw':'observed contrast'},
       'interventions':[{'role':'primary','target_mention':'SOFTWARE_FIXTURE_FACTOR','intervention_type_raw':'exposure'}],
       'measurement':{'measured_entity_mention':'SOFTWARE_FIXTURE_PROTEIN','endpoint_raw':endpoint,
                      'assay_or_readout_raw':'SOFTWARE_FIXTURE_ASSAY','measurement_dimension_raw':'abundance_expression','evidence_span_ids':refs},
       'observation':{'observed_result':text,'evidence_span_ids':refs},'extraction_warnings':['SOFTWARE_FIXTURE']}
    return native_direction_record(f,publication={'pmcid':'SOFTWARE_FIXTURE:PMC'+paper,'pmid':paper})


@pytest.mark.parametrize('signs,entropy,collision,status',[
    ([1,-1],1.0,True,'opposed'),([1,1],0.0,False,'no_polarity_collision'),
    ([1,0],0.0,False,'no_polarity_collision'),([0,0],None,False,'insufficient_evidence'),
    ([None],None,False,'insufficient_evidence'),([True,-1],0.0,False,'no_polarity_collision')])
def test_SOFTWARE_FIXTURE_binary_controls(signs,entropy,collision,status):
    s=binary_direction_summary(signs)
    assert s['entropy']==entropy and s['directional_discordance']==collision and s['direction_status']==status


def test_SOFTWARE_FIXTURE_old_graph_plus_zero_no_longer_conflict_and_preserves_input():
    rows=[{'subject':'SOFTWARE_FIXTURE_A','object':'SOFTWARE_FIXTURE_B','relation_sign':s,
           'evidence_id':str(i),'source_asset':'same_publication','triple_id':str(i),'context':{},'confidence':1,
           'doi':'','article_title':'SOFTWARE_FIXTURE','evidence_sentence':'SOFTWARE_FIXTURE'}
          for i,s in enumerate([1,0])]
    before=deepcopy(rows);edge=build_conflict_graph(rows,latent_pool=[])[1][0]
    assert rows==before and edge['entropy']==0 and edge['negative_count']==0
    assert edge['conflict_status']=='uncontested' and not edge['formal_conflict']
    rows[0]['relation_sign']=0
    edge=build_conflict_graph(rows,latent_pool=[])[1][0]
    assert edge['conflict_status']=='insufficient_evidence'
    assert edge['probabilistic_state']['classification']=='insufficient_evidence'


def test_SOFTWARE_FIXTURE_missing_sign_roundtrip_and_nonsignificant_positive_estimate():
    claim=legacy_tuple_to_l1_claim({'subject':'SOFTWARE_FIXTURE_A','object':'B','evidence_sentence':'SOFTWARE_FIXTURE'}, {'paper_id':'SOFTWARE_FIXTURE'})
    assert claim.direct_relation_sign=='unknown'
    out=l1_claim_to_legacy_tuple(claim)
    assert out['relation_sign'] is None and out['direction_semantics']['zero_effect_asserted'] is False
    claim.direct_relation_sign='positive';claim.evidence_sentence='SOFTWARE_FIXTURE: positive estimate but not significant'
    out=l1_claim_to_legacy_tuple(claim)
    assert out['relation_sign']==1 and out['raw_relation_sign']=='positive'
    assert legacy_tuple_to_l1_claim(out,{'paper_id':'SOFTWARE_FIXTURE'}).direct_relation_sign=='positive'
    audit=effective_legacy_direction({'relation_sign':1,'observed_result':'positive estimate but not significant'})
    assert audit['effective_sign']==1 and not audit['conflict_screen_eligible']
    assert normalize_directional_relation('no significant effect').direction=='not_significant'


def test_SOFTWARE_FIXTURE_actual_L2_missing_sign_and_association_partition(tmp_path):
    from code_engine.graph.ontology_alignment import extract_normalized_observations
    values=[{'subject':'SOFTWARE_FIXTURE_A','object':'SOFTWARE_FIXTURE_B','evidence_sentence':'SOFTWARE_FIXTURE missing direction'},
            {'subject':'SOFTWARE_FIXTURE_A','object':'SOFTWARE_FIXTURE_B','relation_sign':1,'relation_raw':'positively associated',
             'evidence_sentence':'SOFTWARE_FIXTURE observational association'},
            {'subject':'SOFTWARE_FIXTURE_A','object':'SOFTWARE_FIXTURE_B','relation_sign':-1,'relation_raw':'observed decrease',
             'evidence_sentence':'SOFTWARE_FIXTURE intervention outcome'}]
    p=tmp_path/'SOFTWARE_FIXTURE_refined.json'
    p.write_text(json.dumps({'asset_id':'SOFTWARE_FIXTURE','pmcid':'SOFTWARE_FIXTURE_PMC','pmid':'SOFTWARE_FIXTURE_PMID',
        'chunks_extracted':[{'raw_samples':[{'causal_tuples':values}]}]}))
    rows,_=extract_normalized_observations(str(tmp_path),synonym_map={},forbidden_keywords=[],
                                         resolver_cascade=False,legacy_synonym_only=True)
    missing=next(r for r in rows if r['evidence_sentence']==values[0]['evidence_sentence'])
    assert missing['relation_sign'] is None and missing['raw_relation_sign'] is None
    _,edges,_,_=build_conflict_graph(rows,latent_pool=[],include_low_confidence=True)
    assert all(e['conflict_status']!='conflicting' for e in edges)
    assert all(e['independent_publications_count']==1 and e['independent_labs_count']==0 for e in edges)


def test_SOFTWARE_FIXTURE_initial_lane_without_Work_or_formal_authority():
    d=discover_directions([software_record('positive'),software_record('negative','2')])
    assert d['counts']==dict(zip(LEVELS,[1,1,0,0]))
    assert not d['Work_assessments_consumed'] and not d['formal_L4_invoked']
    assert all(not x['scientific_authorization'] and not x['qualified_for_l4'] for x in d['pairs'])


def test_SOFTWARE_FIXTURE_orientation_unverified_and_reversed():
    a=software_record('positive');b=software_record('negative','2',tested=None,reference=None)
    d=discover_directions([a,b]);assert d['counts'][LEVELS[0]]==1 and d['counts'][LEVELS[1]]==0
    b=software_record('negative','2',tested='control',reference='treated')
    d=discover_directions([a,b]);p=d['pairs'][0]
    assert p['orientation']=='reversed_tested_reference' and p['oriented_signs']==[1,1]
    assert d['counts'][LEVELS[1]]==0
    b=software_record('positive','2',tested='control',reference='treated')
    d=discover_directions([a,b])
    assert d['counts'][LEVELS[0]]==0 and d['counts'][LEVELS[1]]==1


def test_SOFTWARE_FIXTURE_different_endpoint_association_and_duplicate_independence():
    a=software_record('positive');b=software_record('negative','2',endpoint='different endpoint')
    assert discover_directions([a,b])['counts'][LEVELS[0]]==0
    b=software_record('negative','2',kind='observational')
    assert discover_directions([a,b])['counts'][LEVELS[0]]==0
    duplicate=deepcopy(a);duplicate['observation_id']='SOFTWARE_FIXTURE:duplicate';duplicate['record_identity']=content_hash(duplicate)
    d=discover_directions([a,duplicate]);assert d['retained_observations']==1 and len(d['duplicates'])==1
    b=software_record('negative',observation='other endpoint occurrence')
    d=discover_directions([a,b]);assert d['independent_publication_pairs']==0 and d['counts'][LEVELS[1]]==0


def test_SOFTWARE_FIXTURE_nonsignificance_cannot_supply_opposition():
    d=discover_directions([software_record('positive'),software_record('negative','2',text='treated versus control decreased protein abundance, not significant')])
    assert all(n==0 for n in d['counts'].values())
    assert d['observations'][1]['raw_extracted_sign']=='negative'
    assert d['observations'][1]['effective_direction']==-1 and not d['observations'][1]['zero_effect_asserted']
    assert d['observations'][1]['statistical_significance_status']=='NONSIGNIFICANT'
    assert not d['observations'][1]['conflict_screen_eligibility']['eligible']


def frozen_records(case):
    root=FROZEN/case/'cases'
    sources=json.loads(next(root.rglob('final_manifest.json')).read_text())['sources']
    records=[]
    for core in sorted(root.rglob('core.json')):
        f=json.loads(core.read_text())['ExperimentalObservationV3'];pmc=f['provenance']['pmcid']
        source=deepcopy(next(s for s in sources if s['identity']['pmcid']==pmc))
        source['binding']={'source_sha256':source['source_sha256']}
        records.append({'source':source,'core':core,'packet':core.with_name('packet.json'),'prompt':core.with_name('review_prompt.txt')})
    return records


@pytest.mark.parametrize('case,count',[('AR',5),('HIF',2)])
def test_genuine_frozen_native_AR_HIF_source_binding_and_no_unsupported_conflict(case,count):
    records=frozen_records(case);before={str(r['core']):r['core'].read_bytes() for r in records}
    d=run_initial_discovery(records,dependencies='SOFTWARE_TEST_CURRENT_DEPENDENCIES')
    assert not d['rejected'] and d['retained_observations']==count
    assert all(n==0 for n in d['counts'].values())
    assert all(r['core'].read_bytes()==before[str(r['core'])] for r in records)
    if case=='HIF':
        assert [r['effective_direction'] for r in d['observations']]==[1,1]
        assert len({r['experiment_context']['model_system_raw'] for r in d['observations']})==2
        assert len({r['tested_arm'] for r in d['observations']})==2
    else:
        assert any('myofiber cross-sectional area' in json.dumps(r['measurement']) for r in d['observations'])
        assert any('28 dpi' in json.dumps(r['measurement']) for r in d['observations'])
        assert all(any('cardiotoxin' in str(i).lower() for i in r['all_interventions']) for r in d['observations'])


def test_genuine_TRIB3_six_associations_four_nulls_not_zero_or_effect_conflicts(tmp_path):
    from tests.pilot_projection_interpretation_support import configuration,BASELINE
    from tests.pilot_native_representation_support import manifest
    from code_engine.fulltext.projection_interpretation import interpret_projection
    pin=configuration(tmp_path,manifest(tmp_path));raw=json.loads(BASELINE.read_text())
    rows=[native_direction_record(r['formal_v3_native_payload'],publication={'pmcid':'PMC10515557','pmid':'37744426'}) for r in raw]
    d=discover_directions(rows)
    assert len(rows)==6
    # Null wording is retained; it does not bind statistics to an endpoint/contrast.
    assert all(r['statistical_significance_status']=='UNKNOWN' for r in rows)
    assert sum(bool(r['reported_absence_wording']) for r in rows)==4
    assert all(r['relationship_kind']=='association' and r['causal_sign'] is None for r in rows)
    assert all(not r['zero_effect_asserted'] for r in rows)
    assert sum(r['effective_direction'] is None for r in rows)==4 and all(n==0 for n in d['counts'].values())
    assert all(interpret_projection(r,pin)['causal_direction']['sign'] is None for r in raw)


def test_genuine_VEGF_retains_P_point7_without_fake_native_extraction():
    p=R/'runs/20261017_code_ai_first_scientific_review_shadow_seen_offline/E1/left/evidence_packet.json'
    packet=json.loads(p.read_text());spans=packet['evidence_spans']
    assert packet['V3_observation_id'] is None and not packet['new_V3_Core_reconstruction']
    assert any('0.7' in s['text'] and '(ns)' in s['text'] for s in spans)
    for s in spans:
        assert hashlib.sha256(s['text'].encode()).hexdigest()==s['text_hash']
    result=next(s['text'] for s in spans if '0.7' in s['text'] and '(ns)' in s['text'])
    audit=effective_legacy_direction({'relation_sign':0,'evidence_sentence':result})
    assert audit['effective_sign'] is None and not audit['zero_effect_asserted']


def test_genuine_unified_Pilot_missing_Work_and_formal_authority_runs_initial_stage(tmp_path,monkeypatch):
    from tests.pilot_inclusion_support import hif_case
    from tests.test_pilot_scientific_inclusion import seen
    from tests.test_pilot_unlimited_integration import offline
    from code_engine.orchestration.pilot_case import PilotCaseExecutor
    from code_engine.orchestration.pilot_budget import ModelBudget
    from code_engine.orchestration.pilot_dataset import verify_dataset
    from code_engine.system_b.persistence.services.pilot_review_display import case_display
    offline.__wrapped__(monkeypatch)
    b,c,r=hif_case(tmp_path/'inputs');r.pop('development_stop_after',None);r['model_stages'].pop('ai_review',None)
    assert 'scientific_comparison_assessments' not in r
    p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'budget.sqlite',c,offline=True),b).run(r)
    stage=next(s for s in p['run_manifest']['stages'] if s['stage']=='initial_sign_discordance')
    assert stage['status']=='executed',p['reason']
    d=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role']=='initial_sign_discordance.json'))
    assert d['retained_observations']==2 and not d['rejected'] and not d['Work_assessments_consumed']
    assert p['run_manifest']['stage_contract_version']=='case_stages_v5' and not p['scientific_authorization']
    assert verify_dataset(tmp_path/'cases'/r['case_id']/'dataset')['scientific_counts']['initial_sign_discordance']==1
    assert case_display(p)['initial_discovery_artifacts']


def test_genuine_bad_packet_evidence_rejects_instead_of_creating_signal(tmp_path):
    r=deepcopy(frozen_records('HIF')[0]);core=json.loads(r['core'].read_text())
    s=core['ExperimentalObservationV3']['provenance']['evidence_spans'][0]
    s['char_start']+=1;s['char_end']+=1
    # Self-consistent span length/hash does not verify source-local coordinates.
    dest=tmp_path/'core.json';dest.write_text(json.dumps(core));r['core']=dest
    lineage={'source_blocks':{s['block_id']:s['text']}}
    r['v3_lineage']=lineage
    d=run_initial_discovery([r],dependencies='SOFTWARE_FIXTURE')
    assert d['rejected'] and d['retained_observations']==0 and all(n==0 for n in d['counts'].values())


def test_genuine_projection_counts_never_alias_candidates_to_formal(tmp_path,monkeypatch):
    from tests.pilot_inclusion_support import hif_case
    from tests.test_pilot_scientific_inclusion import seen
    from tests.test_pilot_unlimited_integration import offline
    from code_engine.orchestration.pilot_case import PilotCaseExecutor
    from code_engine.orchestration.pilot_budget import ModelBudget
    offline.__wrapped__(monkeypatch)
    b,c,r=hif_case(tmp_path/'inputs');r.pop('development_stop_after',None);r['model_stages'].pop('ai_review',None)
    p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.sqlite',c,offline=True),b).run(r)
    summary=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role']=='projection_summary.json'))
    assert 'true_conflicts_after' not in summary
    assert summary['formally_authorized_conflicts_after']==summary['qualified_candidates_after']==0
    assert set(summary['conflict_signal_counts'])==set(LEVELS)
