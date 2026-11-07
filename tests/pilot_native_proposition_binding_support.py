"""Explicit B4.9 Work source assessments; software transport is not evidence.

No clinical matching rules live in the runtime adapter. Each annotation below
is tied to the exact frozen record and source spans reviewed for this task.
"""
from pathlib import Path
import json
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.orchestration.pilot_native_representation import NativeReplayManifest, _lineage, _spans, recover_native_jsonl
from code_engine.fulltext.evidence_anchors import resolve_anchor
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import _span_from_anchor
from code_engine.orchestration.pilot_native_proposition_binding import VERSION, POLICY
from tests.pilot_projection_interpretation_support import trib_effective
from tests.pilot_inclusion_support import R, pin, write

RUN=R/'runs/20261029_code_recovery_batch4_9_native_proposition_binding_offline'
FROZEN=R/'runs/20261029_code_recovery_batch4_8_observational_projection_offline/release_v3/TRIB3/cases/B3-TRIB3'
B47=R/'runs/20261028_code_recovery_batch4_7_trib3_native_handoff_offline/release_v4/TRIB3/cases/B3-TRIB3'


def configuration(path):
    projections=json.loads((FROZEN/'projected_native_observations.json').read_text())
    props=json.loads((FROZEN/'scientific_comparison.json').read_text())['propositions']
    ledger=json.loads((FROZEN/'scientific_inclusion_final.json').read_text())['rows']
    native_pin=pin(FROZEN.parents[1]/'inputs/native_representation_manifest.json')
    cfg=NativeReplayManifest.model_validate(json.loads(Path(native_pin['path']).read_text()))
    article,m,text,anchors,fragments,_,_,_=_lineage(cfg)
    # Exact original sentences establishing Stage IV subgroup and clinical setup;
    # the Stage IV result sentence alone does not identify this subgroup.
    extra=[a for a in anchors if a.text.startswith('In this study, archival formalin-fixed') or
           a.text.startswith('Finally, we analyzed')]
    stage=[a for a in anchors if 'Stage IV' in a.text]
    extra+=stage
    extra=list({a.anchor_id:a for a in extra}.values())
    additional=[_span_from_anchor(a,'setup').model_dump(mode='json') for a in extra]
    native_rows={r['original_V3_identity']:r for r in json.loads((FROZEN/'PMC10515557_native_representation_handoff.json').read_text())['records']}
    producer='interactive_Work_B4_9_explicit_source_scope_assessment_not_independent_scientific_review'
    def assessment(value,pointer,record,refs,limitation='Source-bound local descriptor only; not canonical or independently approved'):
        raw=record
        for token in pointer[1:].split('/'):raw=raw[token]
        return {'value':value,'record_pointer':pointer,'record_value':raw,'evidence_refs':list(refs),'limitation':limitation}
    def inclusion(scope):return next(r['revision_identity'] for r in ledger if r['scope_level']=='observation' and r['scope_identity']==scope)
    native_profiles=[]
    # Explicit source phrases, not inferred risk-stage equivalence or array order.
    labels={'56 neuroblastoma patients':('entire patient group','overall_cohort'),
            'low-risk neuroblastoma patients':('low-risk','risk'),
            'high-risk neuroblastoma patients':('high-risk','risk'),
            'low-stage neuroblastoma patients':('low-stage','stage'),
            'high-stage neuroblastoma patients':('high-stage','stage'),
            'Stage IV neuroblastoma patients':('Stage IV','stage')}
    for view in projections:
        f=view['formal_v3_native_payload'];c=view['ExperimentalCore'];oid=f['observation_id'];env={'ExperimentalObservationV3':f,'ExperimentalCore':c}
        # Exact envelope including retained original fields, via existing adapter.
        rec=next(json.loads(r['core_utf8']) for r in recover_native_jsonl(native_pin)['records'] if json.loads(r['core_utf8'])['ExperimentalObservationV3']['observation_id']==oid)
        mapped=native_rows[oid]['evidence_mapping']+_spans({**f,'provenance':{**f['provenance'],'evidence_spans':additional}},cfg,article,m,text,anchors,fragments)
        refs=f['observation']['evidence_span_ids'];methods=f['measurement']['evidence_span_ids']
        scope,kind=labels[f['experiment']['cohort_raw']]
        scope_refs=refs if scope!='Stage IV' else [s['evidence_span_id'] for s in mapped if 'Stage IV' in s['text']]
        setup_refs=[s['evidence_span_id'] for s in mapped if s['text'].startswith('In this study, archival')]
        positive=view['effective_interpretation']['reported_association_direction']=='positive'
        root='/ExperimentalObservationV3/'
        fields={
            'endpoint':assessment(f['measurement']['endpoint_raw'],root+'measurement/endpoint_raw',rec,methods+refs),
            'subgroup':assessment(scope,root+'experiment/cohort_raw',rec,scope_refs),
            'scope_kind':assessment(kind,root+'experiment/experimental_design_raw',rec,scope_refs),
            'study_design':assessment('observational',root+'experiment/design_type_raw',rec,setup_refs),
            'measurement':assessment('Kaplan-Meier / log-rank',root+'measurement/assay_or_readout_raw',rec,methods),
            'reported_result':assessment('positive_association' if positive else 'no_significant_association_reported',root+'observation/observed_result',rec,refs),
            'reported_statistic':assessment(f['observation']['statistical_support_raw'],root+'observation/statistical_support_raw',rec,refs),
            'result_group':assessment('TRIB3-positive',root+'experiment/comparison_arm_raw',rec,refs),
            'reference_group':assessment('TRIB3-negative',root+'experiment/control_arm_raw',rec,refs),
            'time':assessment(None,root+'observation/uncertainty_raw',rec,[], 'Follow-up duration/time origin not established in these frozen evidence records')}
        native_profiles.append({'key':oid,'record_sha256':content_hash(rec),'revision_identity':c['revision']['identity'],
            'inclusion_revision_identity':inclusion(oid),'effective_interpretation_identity':view['effective_interpretation']['identity'],
            'fields':fields,'producer':producer})
    prop_profiles=[]
    for p in props:
        group=p['facets']['system']['value'];scope,kind={
            'low-risk neuroblastoma patients':('low-risk','risk'),
            'high-risk neuroblastoma patients':('high-risk','risk'),
            'all-patient neuroblastoma patients':('entire patient group','overall_cohort')}[group]
        # Narrow result-bearing paragraph, rather than all source packet spans.
        section=14 if kind=='overall_cohort' else 16
        refs=[s['evidence_span_id'] for s in p['source_evidence'] if s['section_index']==section]
        setup=[s['evidence_span_id'] for s in p['source_evidence'] if s['section_index']==3]
        methods=[s['evidence_span_id'] for s in p['source_evidence'] if s['section_index']==8]
        positive=p['effective_interpretation']['reported_association_direction']=='positive'
        # Exact source-reported statistical strings are read from the retained
        # source facet, not compared to a threshold or used as effect size.
        raw=p['facets']['statistical_interpretation']['value'];stat='P = '+raw.split('P = ')[1] if 'P = ' in raw else None
        fields={
            'endpoint':assessment(p['facets']['endpoint']['value'],'/facets/endpoint/value',p,methods+refs),
            'subgroup':assessment(scope,'/facets/system/value',p,refs),
            'scope_kind':assessment(kind,'/facets/focal_contrast/value',p,refs),
            'study_design':assessment('observational','/factor_role',p,setup),
            'measurement':assessment('Kaplan-Meier / log-rank','/facets/assay/value',p,methods),
            'reported_result':assessment('positive_association' if positive else 'no_significant_association_reported','/result/description/value',p,refs),
            'reported_statistic':assessment(stat,'/facets/statistical_interpretation/value',p,refs),
            'result_group':assessment('TRIB3-positive','/facets/tested_arm/value',p,refs),
            'reference_group':assessment('TRIB3-negative','/facets/reference_arm/value',p,refs),
            'time':assessment(None,'/facets/time/value',p,[], 'Follow-up duration/time origin not established in these frozen evidence records')}
        prop_profiles.append({'key':p['key'],'record_sha256':content_hash(p),'revision_identity':p['proposition_identity'],
            'inclusion_revision_identity':p['inclusion_revision_identity'],
            'effective_interpretation_identity':'source_proposition_interpretation:'+content_hash(p['effective_interpretation']),
            'fields':fields,'producer':producer})
    source={'publication':cfg.source_identity,'native_replay_manifest':native_pin,
        'B4_7_native_lineage':pin(B47/'PMC10515557_native_representation_handoff.json'),
        'B4_8_projected_observations':pin(FROZEN/'projected_native_observations.json'),
        'B4_propositions':pin(FROZEN/'scientific_comparison.json'),
        'B3_inclusion_ledger':pin(FROZEN/'scientific_inclusion_final.json'),
        'additional_anchor_ids':[a.anchor_id for a in extra]}
    value={'schema_version':VERSION,'policy':pin(POLICY),'owner_instruction':pin(RUN/'owner_instruction.original.txt'),
        'sources':[source],'native_profiles':native_profiles,'proposition_profiles':prop_profiles,'producer':producer}
    return pin(write(Path(path)/'native_proposition_binding_configuration.json',value))


def trib_binding(path):
    b,c,r=trib_effective(path)
    r['native_proposition_binding']=configuration(path)
    return b,c,r
