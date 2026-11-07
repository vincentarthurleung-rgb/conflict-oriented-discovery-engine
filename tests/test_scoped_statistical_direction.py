"""SOFTWARE_FIXTURE scope controls and immutable authentic D19 regression."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import pytest

from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.discovery.directional_discovery import native_direction_record, discover_directions, LEVELS
from tests.test_deterministic_initial_discovery import frozen_records, run_initial_discovery

R=Path(__file__).resolve().parents[1]


def SOFTWARE_FIXTURE_native(text, *, sign='negative', selected='Figure 1A', section='fig', reference='control'):
    span={'evidence_span_id':'SOFTWARE_FIXTURE:span', 'anchor_id':'SOFTWARE_FIXTURE:anchor',
          'source_document_id':'SOFTWARE_FIXTURE:source', 'block_id':'SOFTWARE_FIXTURE:block',
          'section':section, 'char_start':17, 'char_end':17+len(text), 'text':text,
          'text_hash':hashlib.sha256(text.encode()).hexdigest()}
    refs=[span['evidence_span_id']]
    return {'observation_id':'SOFTWARE_FIXTURE:observation',
        'provenance':{'source_document_id':span['source_document_id'],'evidence_spans':[span]},
        'experiment':{'experiment_id':'SOFTWARE_FIXTURE:experiment','experiment_label_raw':selected,
            'design_type':'in_vitro', 'comparison_arm_raw':'treated','control_arm_raw':reference},
        'candidate_relation':{'lexical_direction':sign,'lexical_direction_raw':sign},
        'measurement':{'measured_entity_mention':'SOFTWARE_FIXTURE_PROTEIN','endpoint_raw':'protein abundance',
            'measurement_dimension_raw':'abundance_expression','assay_or_readout_raw':'SOFTWARE_FIXTURE_ASSAY',
            'evidence_span_ids':refs},
        'observation':{'observed_result':text,'evidence_span_ids':refs,'negation':False},
        'interventions':[{'role':'primary','target_mention':'SOFTWARE_FIXTURE_FACTOR','intervention_type_raw':'exposure'}]}


def row(formal, paper='1'):
    return native_direction_record(formal, publication={'pmcid':'SOFTWARE_FIXTURE:'+paper,'pmid':paper})


@pytest.mark.parametrize('text,selected,status',[
    ('(A) treated versus control: protein abundance decreased. NS, not significant.', 'Figure 1A','UNKNOWN'),
    ('(A) treated versus control: protein abundance decreased, NS, not significant.', 'Figure 1A','UNKNOWN'),
    ('(A) treated versus control: protein abundance decreased, not significant.', 'Figure 1A','NONSIGNIFICANT'),
    ('(B) treated versus control: protein abundance decreased, not significant.', 'Figure 1A','UNKNOWN'),
    ('(A) treated versus control: protein abundance significantly decreased. (B) treated versus control: protein abundance decreased, not significant.', 'Figure 1A','SIGNIFICANT'),
    ('(A) treated versus control: protein abundance significantly decreased. (B) treated versus control: protein abundance decreased, not significant.', 'Figure 1B','NONSIGNIFICANT'),
    ('(A) treated versus control: protein abundance decreased, not significant.', None,'UNKNOWN'),
    ('(A) treated versus other_control: protein abundance decreased, not significant.', 'Figure 1A','UNKNOWN'),
    ('(A) untreated versus control: protein abundance decreased, not significant.', 'Figure 1A','UNKNOWN'),
    ('(A) treated versus control: SOFTWARE_FIXTURE_PROTEIN mRNA decreased, not significant.', 'Figure 1A','UNKNOWN'),
    ('(A) protein abundance decreased in treated and control, not significant.', 'Figure 1A','UNKNOWN'),
    ('(A) treated versus control: protein abundance decreased; other versus control: protein abundance was not significant.', 'Figure 1A','UNKNOWN'),
    ('(A) treated versus control increased protein abundance, whereas other versus control was not significant.', 'Figure 1A','UNKNOWN'),
])
def test_SOFTWARE_FIXTURE_scoped_statistics_and_preserved_direction(text,selected,status):
    f=SOFTWARE_FIXTURE_native(text,selected=selected);before=deepcopy(f);r=row(f)
    assert f==before
    assert r['source_reported_direction']=='negative' and r['effective_direction']==-1
    assert r['statistical_significance_status']==status
    assert r['conflict_screen_eligibility']['eligible']==(status!='NONSIGNIFICANT')
    scope=r['applicable_result_evidence_scope']
    assert scope['native_revision_sha256']==content_hash(f)
    assert not scope['significance_assumed_from_absence'] and scope['P_value_inferred'] is None
    for statement in scope['accepted_statements']+scope['ignored_statements']:
        assert text[statement['char_start']-17:statement['char_end']-17]==statement['text']
        assert statement['evidence_span_id']=='SOFTWARE_FIXTURE:span'
        assert statement['native_revision_sha256']==content_hash(f)


def test_SOFTWARE_FIXTURE_direction_unknown_and_missing_comparator():
    text='(A) treated versus control: protein abundance showed no significant difference.'
    r=row(SOFTWARE_FIXTURE_native(text,sign='unknown'))
    assert r['effective_direction'] is None and r['source_reported_sign'] is None and not r['zero_effect_asserted']
    assert r['statistical_significance_status']=='NONSIGNIFICANT'
    r=row(SOFTWARE_FIXTURE_native(text,reference=None))
    assert r['effective_direction']==-1 and r['statistical_significance_status']=='UNKNOWN'
    assert r['orientation']=='unverified'


def test_SOFTWARE_FIXTURE_legacy_unbound_statistics_not_observation_status():
    from code_engine.extraction.direction_semantics import effective_legacy_direction
    r=effective_legacy_direction({'relation_sign':-1,'evidence_sentence':'SOFTWARE_FIXTURE: NS, not significant'})
    assert r['effective_sign']==-1 and r['statistical_significance_status']=='UNKNOWN'
    assert r['nonsignificance_reported'] is None and r['nonsignificance_wording_present']
    assert not r['conflict_screen_eligible'] and not r['zero_effect_asserted']


def test_SOFTWARE_FIXTURE_conflicting_scoped_statements_unknown():
    text='(A) treated versus control: protein abundance significantly decreased. Treated versus control: protein abundance decreased, not significant.'
    r=row(SOFTWARE_FIXTURE_native(text))
    assert r['effective_direction']==-1 and r['statistical_significance_status']=='UNKNOWN'
    assert 'CONFLICTING_SCOPED_STATISTICAL_STATEMENTS' in r['uncertainty_reasons']


def test_SOFTWARE_FIXTURE_raw_effective_screen_and_relation_partition():
    plus=SOFTWARE_FIXTURE_native('(A) treated versus control: protein abundance increased.',sign='positive')
    minus=SOFTWARE_FIXTURE_native('(A) treated versus control: protein abundance decreased, not significant.')
    d=discover_directions([row(plus),row(minus,'2')]);p=d['pairs'][0]
    assert 'raw_signs' not in p and d['schema_version'].endswith('_v2')
    assert p['raw_extracted_signs']==['positive','negative']
    assert p['source_reported_signs']==p['effective_signs']==[1,-1]
    assert p['screening_signs']==[1,None] and all(v==0 for v in d['counts'].values())
    minus=SOFTWARE_FIXTURE_native('(A) treated versus control: protein abundance decreased.')
    d=discover_directions([row(plus),row(minus,'2')])
    assert d['counts']==dict(zip(LEVELS,[1,1,0,0]))
    minus['interventions'][0]['target_mention']='SOFTWARE_FIXTURE_OTHER_FACTOR'
    d=discover_directions([row(plus),row(minus,'2')])
    assert not d['pairs'] and all(v==0 for v in d['counts'].values())
    assert d['source_opposing_direction_pairs']==1 and not d['relation_partition_diagnostics'][0]['relation_keys_align']


@pytest.mark.parametrize('corruption',['ref','source','hash','coordinates'])
def test_SOFTWARE_FIXTURE_wrong_source_span_rejected(corruption):
    f=SOFTWARE_FIXTURE_native('(A) treated versus control: protein abundance decreased.')
    span=f['provenance']['evidence_spans'][0]
    if corruption=='ref':f['observation']['evidence_span_ids']=['SOFTWARE_FIXTURE:wrong']
    if corruption=='source':span['source_document_id']='SOFTWARE_FIXTURE:unrelated'
    if corruption=='hash':span['text_hash']='0'*64
    if corruption=='coordinates':span['char_end']+=1
    with pytest.raises(ValueError):row(f)


def test_genuine_wrong_packet_revision_abstains(tmp_path):
    record=deepcopy(frozen_records('HIF')[0]);packet=json.loads(record['packet'].read_text())
    packet['Core_revision_id']='SOFTWARE_FIXTURE:wrong_revision'
    dest=tmp_path/'wrong_revision_packet.json';dest.write_text(json.dumps(packet));record['packet']=dest
    d=run_initial_discovery([record],dependencies='SOFTWARE_FIXTURE')
    assert d['retained_observations']==0 and 'record_revision_mismatch' in d['rejected'][0]['reason']


def test_genuine_D19_preserves_opposition_without_claiming_same_relation():
    rows=[]
    for pmc in ('PMC6787500','PMC7744182'):
        path=R/'runs/20261017_code_real_contradiction_candidate_discovery_seen_offline/reconstructions/D19'/pmc/'v3_core_draft.json'
        f=json.loads(path.read_text())['ExperimentalObservationV3']
        rows.append(native_direction_record(f,publication={k:f['provenance'][k] for k in ('pmcid','pmid')}))
    assert [r['effective_direction'] for r in rows]==[-1,1]
    assert [r['source_reported_direction'] for r in rows]==['negative','positive']
    assert rows[0]['statistical_significance_status']=='UNKNOWN'
    ignored=rows[0]['applicable_result_evidence_scope']['ignored_statements']
    assert any('NS, not significant' in i['text'] and i['reason']=='GENERIC_STATISTICAL_LEGEND_NOT_OBSERVATION_EVIDENCE' for i in ignored)
    d=discover_directions(rows)
    assert all(v==0 for v in d['counts'].values()) and not d['pairs']
    assert d['source_opposing_direction_pairs']==1 and len(d['relation_partition_diagnostics'])==1
