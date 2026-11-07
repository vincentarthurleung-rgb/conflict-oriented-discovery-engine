"""Frozen real observations; modified copies are SOFTWARE_FIXTURE controls."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.fulltext.projection_interpretation import (
    interpret_projection,consumer_guard,raw_projection,interpret_proposition,VERSION,
)
from code_engine.fulltext.evidence_projection import aggregate_canonical_edges,project_fulltext_run
from code_engine.orchestration.pilot_case import PilotCaseExecutor,CaseIntegrity
from code_engine.orchestration.pilot_budget import ModelBudget
from code_engine.orchestration.pilot_dataset import verify_dataset
from code_engine.orchestration.pilot_comparison import compare_pair,constrained_hypotheses
from code_engine.orchestration.pilot_comparison import PairAssessment
from tests.pilot_projection_interpretation_support import configuration,BASELINE,trib_effective,RUN
from tests.pilot_native_representation_support import manifest
from tests.pilot_inclusion_support import write,pin,R
from tests.test_pilot_scientific_inclusion import seen
from tests.test_pilot_unlimited_integration import offline


@pytest.fixture
def real(tmp_path):
    ref=configuration(tmp_path/'inputs',manifest(tmp_path/'inputs'))
    return ref,json.loads(BASELINE.read_text())


def test_genuine_six_keep_raw_outcomes_and_separate_association_significance_null_and_causality(real):
    ref,rows=real;before=deepcopy(rows);effective=[interpret_projection(x,ref) for x in rows]
    assert rows==before
    assert [e['reported_association_direction'] for e in effective]==['unknown','positive','unknown','positive','unknown','unknown']
    assert [e['statistical_significance']['assessment'] for e in effective]==['source_reported_nonsignificant','source_reported_significant','source_reported_nonsignificant','source_reported_significant','source_reported_nonsignificant','source_reported_nonsignificant']
    assert all(e['status']=='SOURCE_BOUND_PROVISIONAL' and e['effective_layer']=='association' for e in effective)
    for raw,e in zip(rows,effective):
        assert e['effective_outcome_sign'] is e['causal_direction']['sign'] is e['effect_magnitude'] is None
        assert not e['zero_effect_asserted'] and not e['equivalence']['established'] and not e['causal_direction']['causal_increases']
        assert not e['factor_semantics']['assigned_intervention_established']
        assert e['statistical_significance']['raw_support']==raw['formal_v3_native_payload']['observation']['statistical_support_raw']
        assert e['null_or_absence_of_detection']['raw_outcome_language']==raw['formal_v3_native_payload']['observation']['observed_result']
        assert e['binding']['Core_revision_id']==raw['ExperimentalCore']['revision']['identity']
        assert e['statistical_significance']['engine_P_threshold_applied'] is False
    assert effective[-1]['statistical_significance']['raw_support'] is None


def test_all_direct_consumer_authority_guards_abstain_but_associations_remain_reviewable(real):
    ref,rows=real
    for row in rows:
        row['effective_interpretation']=interpret_projection(row,ref)
        assert consumer_guard(row,'review')['allowed_by_effective_layer']
        for purpose in ('causal_graph','V2_readiness_authority','effect_contradiction','equality','formal_mediation','machine_reuse','hypothesis'):
            guard=consumer_guard(row,purpose)
            assert guard['status']=='ABSTAIN' and guard['raw_evidence_retained'] and not guard['allowed_by_effective_layer']


@pytest.mark.parametrize('case',['missing','duplicate','wrong_Core','wrong_formal','wrong_policy','P_only','direction_P_only','manipulation','conflict'])
def test_SOFTWARE_FIXTURE_invalid_source_annotation_abstains_without_heuristic_fallback(real,tmp_path,case):
    ref,rows=real;cfg=json.loads(Path(ref['path']).read_text());a=cfg['annotations'][1]
    if case=='missing':cfg['annotations']=[]
    elif case=='duplicate':cfg['annotations'].append(deepcopy(a))
    elif case=='wrong_Core':a['Core_revision_id']='SOFTWARE_FIXTURE_wrong_core'
    elif case=='wrong_formal':a['formal_sha256']='0'*64
    elif case=='wrong_policy':cfg['policy']['sha256']='0'*64
    elif case=='P_only':a['significance_basis']='unknown'
    elif case=='direction_P_only':a['evidence_by_dimension']['association_direction']=a['evidence_by_dimension']['study_design']
    elif case=='manipulation':a['factor_semantics']='assigned_manipulation'
    elif case=='conflict':a['conflicts']=['SOFTWARE_FIXTURE contradictory source interpretation']
    new=pin(write(tmp_path/'SOFTWARE_FIXTURE_config.json',cfg));e=interpret_projection(rows[1],new)
    assert e['status']=='ABSTAIN' and e['reported_association_direction']=='unknown' and e['abstention_reasons']
    assert not e['scientific_authorization'] and e['effective_outcome_sign'] is None


def test_P_support_does_not_generate_a_missing_direction(real,tmp_path):
    ref,rows=real;cfg=json.loads(Path(ref['path']).read_text());cfg['annotations'][1]['association_direction']='unknown'
    cfg['annotations'][1]['evidence_by_dimension']['association_direction']=[]
    e=interpret_projection(rows[1],pin(write(tmp_path/'SOFTWARE_FIXTURE_unknown_direction.json',cfg)))
    assert e['statistical_significance']['raw_support']=='P = .034'
    assert e['reported_association_direction']=='unknown' and e['effective_outcome_sign'] is None


@pytest.mark.parametrize('case',['missing_sidecar','stale','raw_sign_changed','rehash_science_promotion','rehash_causal_sign'])
def test_SOFTWARE_FIXTURE_forged_legacy_projection_cannot_enter_graph(real,case):
    ref,rows=real;row=deepcopy(rows[1]);row['effective_interpretation']=interpret_projection(row,ref)
    if case=='missing_sidecar':row.pop('effective_interpretation')
    elif case=='stale':row['effective_interpretation']['implementation']['sha256']='0'*64
    elif case=='raw_sign_changed':row['observed_outcome_sign']=-1
    else:
        e=row['effective_interpretation']
        if case=='rehash_science_promotion':e['formal_admission']['eligible']=True
        else:e['causal_direction']['sign']=1
        e['identity']=VERSION+':'+content_hash({k:v for k,v in e.items() if k!='identity'})
    assert not consumer_guard(row,'review')['allowed_by_effective_layer']
    row.update(formal_core_graph_eligible=True,conflict_eligible=True,derived_causal_sign=1,
               subject_canonical_id='SOFTWARE_FIXTURE:S',object_canonical_id='SOFTWARE_FIXTURE:O',
               formal_relation='increases',formal_relation_family='positive_regulation',final_formal_polarity='positive')
    edges,merged=aggregate_canonical_edges([row]);assert edges==[]
    assert row['effective_consumer_guards']['causal_graph']['status']=='ABSTAIN'


def test_unbound_equivalence_claim_rejected_without_fabricating_a_source_assertion(real,tmp_path):
    ref,rows=real;cfg=json.loads(Path(ref['path']).read_text())
    cfg['annotations'][0]['equivalence_claim']='SOFTWARE_FIXTURE equivalence claim is unverified; not genuine biomedical evidence'
    e=interpret_projection(rows[0],pin(write(tmp_path/'SOFTWARE_FIXTURE_equivalence.json',cfg)))
    assert e['status']=='ABSTAIN' and e['equivalence']['established'] is False and e['equivalence']['source_claim'] is None
    assert any('NOT_APPROVED' in reason for reason in e['abstention_reasons'])


def test_old_projection_without_versioned_interpretation_is_not_scientific_authority(real):
    _,rows=real
    for row in rows:
        assert consumer_guard(row,'effect_contradiction')['reason_codes']==['EFFECTIVE_INTERPRETATION_MISSING','PROVISIONAL_INTERPRETATION_IS_NOT_EFFECT_CONTRADICTION_AUTHORITY']
        assert raw_projection(row)==row


@pytest.mark.parametrize('kind',['unknown_intervention','association'])
def test_SOFTWARE_FIXTURE_legacy_unknown_or_association_does_not_gain_a_graph_edge(kind):
    legacy={'observation_id':'SOFTWARE_FIXTURE_LEGACY_UNKNOWN','formal_core_graph_eligible':True,
        'intervention_type':'unknown','observed_outcome_sign':1,'scientific_edge_layer':'strict_causal_core',
        'formal_relation':'increases','subject_canonical_id':'SOFTWARE_FIXTURE:S','object_canonical_id':'SOFTWARE_FIXTURE:O'}
    if kind=='association':legacy.update(intervention_type='observational_no_intervention',scientific_edge_layer='association')
    assert aggregate_canonical_edges([legacy])[0]==[]
    assert legacy['effective_consumer_guards']['causal_graph']['status']=='ABSTAIN'


def test_real_Pilot_dataset_raw_native_Core_V2_and_linkage_preserved_with_effective_sidecars(tmp_path):
    b,c,r=trib_effective(tmp_path/'inputs');p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'budget.db',c,offline=True),b).run(r)
    assert p['terminal_state']=='NOT_EVALUABLE',p['reason']
    byrole={a['role']:a for a in p['artifacts']}
    effective=json.loads(byrole['effective_projection_interpretations.json']['utf8'])['rows']
    raw=json.loads(byrole['raw_projected_native_observations.json']['utf8'])
    assert len(effective)==len(raw)==6 and all(e['status']=='SOURCE_BOUND_PROVISIONAL' for e in effective)
    d=verify_dataset(tmp_path/'cases'/r['case_id']/'dataset')['scientific_counts']
    assert d['experimental_core']==d['raw_evidence_projection']==d['effective_projection_interpretation']==d['effective_projection_consumer_guards']==6
    old=BASELINE.parent
    oldcores={content_hash(json.loads(x.read_text())) for x in old.rglob('core.json')}
    newcores={content_hash(json.loads(a['utf8'])) for a in p['artifacts'] if a['role'].endswith('/core.json')}
    assert oldcores==newcores
    for oldrow,newrow in zip(json.loads(BASELINE.read_text()),sorted(raw,key=lambda x:next(i for i,e in enumerate(json.loads(BASELINE.read_text())) if e['observation_id']==x['observation_id']))):
        for k in ('observed_outcome_sign','formal_relation','scientific_edge_layer','ExperimentalObservationV3','ExperimentalCore'):
            assert oldrow[k]==newrow[k]
    assert d['hypotheses']==d['human_reviews']==0


def test_B4_source_packet_null_and_association_are_not_positional_native_mappings():
    prior=R/'runs/20261028_code_recovery_batch4_7_trib3_native_handoff_offline/release_v4'
    null=json.loads((prior/'HIF_NULL/cases/B3-HIF-NULL/scientific_comparison.json').read_text())['propositions'][0]
    e=interpret_proposition(null);assert e['statistical_null_as_recorded'] and e['effective_outcome_sign'] is None
    assert not e['effect_contradiction_screening_permitted'] and not e['equivalence_established']
    t=json.loads((prior/'TRIB3/cases/B3-TRIB3/scientific_comparison.json').read_text())['propositions']
    assert len(t)==6 and {p['facets']['endpoint']['value'] for p in t}=={'overall survival','event-free survival'}
    assert all(interpret_proposition(p)['effective_relation_kind']=='association' for p in t)


def test_effective_input_drift_invalidates_completed_Pilot_without_resending(tmp_path):
    b,c,r=trib_effective(tmp_path/'inputs');ex=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'budget.db',c,offline=True),b)
    p=ex.run(r);assert p['terminal_state']=='NOT_EVALUABLE',p['reason'];calls=len(b.transport.calls)
    ref=r['projection_interpretations'];cfg=json.loads(Path(ref['path']).read_text());cfg['annotations'][0]['reason']+='; changed provisional interpretation commentary'
    Path(ref['path']).write_text(json.dumps(cfg))
    with pytest.raises(CaseIntegrity,match='input_drift'):ex.run(r)
    assert len(b.transport.calls)==calls


@pytest.mark.parametrize('case',['legacy_zero','association_opposition','null_opposition','missing_role'])
def test_SOFTWARE_FIXTURE_old_signs_or_association_cannot_become_effect_conflict_or_hypothesis(case):
    base=R/'runs/20261028_code_recovery_batch4_7_trib3_native_handoff_offline/release_v4/HIF'
    bundle=json.loads((base/'cases/B3-HIF/scientific_comparison.json').read_text())
    req=json.loads((base/'request.json').read_text());annotation=json.loads(Path(req['scientific_comparison_assessments']['path']).read_text())
    a,b=deepcopy(bundle['propositions']);a['provenance']=b['provenance']='SOFTWARE_FIXTURE'
    assessment=PairAssessment.model_validate({**annotation['pairs'][0],'producer':'SOFTWARE_FIXTURE'})
    a['result']['direction']='increase';b['result']['direction']='decrease'
    if case=='legacy_zero':a['observed_outcome_sign']=0
    elif case=='association_opposition':a['factor_role']=b['factor_role']='observational_biomarker_stratification'
    elif case=='null_opposition':a['result']['direction']='not_significant'
    else:a.pop('factor_role')
    result=compare_pair(a,b,assessment)
    assert result['qualification']=='INSUFFICIENT_EVIDENCE' and not result['hypotheses']
    forged={**result,'qualification':'CANDIDATE_CONTRADICTION'}
    assert constrained_hypotheses(forged,a,b,assessment)==[]
