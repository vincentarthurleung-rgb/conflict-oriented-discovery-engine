"""Explicit Work provisional source annotations, not runtime clinical rules."""
from pathlib import Path
import json
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.orchestration.pilot_native_representation import recover_native_jsonl
from code_engine.fulltext.projection_interpretation import VERSION,POLICY
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import _span_from_anchor
from code_engine.fulltext.evidence_anchors import generate_evidence_anchors
from tests.pilot_native_representation_support import trib_native,manifest,R
from tests.pilot_inclusion_support import pin,write
from tests.pilot_semantic_support import OWNER

RUN=R/'runs/20261029_code_recovery_batch4_8_observational_projection_offline'
BASELINE=R/'runs/20261028_code_recovery_batch4_7_trib3_native_handoff_offline/release_v4/TRIB3/cases/B3-TRIB3/projected_native_observations.json'
# Actual source-bound decisions supplied by this development review and owner
# task; no matching to B4's OVS/EFS proposition array and no P-value classifier.
POSITIVE={'ftl1v3_049285969c578c7df3a74972','ftl1v3_6e04318a5dd1cb6d540643e6'}


def configuration(path,native_pin):
    cfg=json.loads(Path(native_pin['path']).read_text());m=json.loads(Path(cfg['provider_request_manifest']['path']).read_text())
    anchors=generate_evidence_anchors(block_id=m['block']['block_id'],source_document_id='PMC10515557',
        block_text=Path(cfg['source_payload']['path']).read_text(),section='Results')
    setup=next(a for a in anchors if a.anchor_id.endswith(':S0001'))
    methods=next(a for a in anchors if a.anchor_id.endswith(':S0007'))
    setup_ref=_span_from_anchor(setup,'setup').evidence_span_id
    method_ref=_span_from_anchor(methods,'setup').evidence_span_id
    annotations=[]
    for item in recover_native_jsonl(native_pin)['records']:
        env=json.loads(item['core_utf8']);f=env['ExperimentalObservationV3'];c=env['ExperimentalCore'];obsrefs=f['observation']['evidence_span_ids']
        pos=f['observation_id'] in POSITIVE
        annotations.append({'observation_id':f['observation_id'],'Core_revision_id':c['revision']['identity'],
            'formal_sha256':content_hash(f),'core_sha256':content_hash(c),'native_replay_manifest':native_pin,
            'study_design':'observational','factor_semantics':'observational_grouping',
            'association_direction':'positive' if pos else 'unknown',
            'significance':'source_reported_significant' if pos else 'source_reported_nonsignificant',
            'significance_basis':'author_methods_and_reported_statistic' if f['observation']['statistical_support_raw'] else 'source_wording',
            'null_wording':'none_established' if pos else 'reported_absence_of_detection',
            'equivalence_claim':None,'evidence_by_dimension':{
                'study_design':[setup_ref],'factor_semantics':obsrefs,
                'association_direction':obsrefs if pos else [],'significance':[*obsrefs,method_ref],
                'null_wording':obsrefs if not pos else []},
            'additional_anchor_ids':[setup.anchor_id,methods.anchor_id],'conflicts':[],
            'reason':'Frozen clinical cohort Methods, biomarker-group Results and exact OVS subgroup sentence; author statistical statement retained, no engine P threshold, effect size or causal sign',
            'producer':'interactive_Work_B4_8_source_bound_provisional_annotation_not_independent_scientific_review'})
    value={'schema_version':VERSION,'scientific_authorization':False,'B4_6_owner_decision':pin(OWNER),
        'owner_instruction':pin(RUN/'owner_instruction.original.txt'),'policy':pin(POLICY),'annotations':annotations}
    return pin(write(Path(path)/'effective_projection_configuration.json',value))


def trib_effective(path):
    b,c,r=trib_native(path)
    r['projection_interpretations']=configuration(path,r['native_representation_handoffs']['PMC10515557'])
    return b,c,r
