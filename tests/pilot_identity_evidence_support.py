"""Bounded Work evidence annotations of frozen real records; no identity approval."""
from pathlib import Path
from copy import deepcopy
import hashlib,json
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.orchestration.pilot_identity_evidence import VERSION,POLICY,REGISTRY
from tests.pilot_inclusion_support import R,write,pin
from tests.pilot_projection_interpretation_support import trib_effective
from tests.pilot_semantic_support import ar_semantic,cross_semantic,hif_comparison,null_comparison

RUN=R/'runs/20261029_code_recovery_batch4_10_identity_evidence_offline'
B49=R/'runs/20261029_code_recovery_batch4_9_native_proposition_binding_offline/release_v2'
FROZEN={label:next((B49/label/'cases').glob('B3-*')) for label in ('TRIB3','HIF','AR','HIF_NULL')}


def source_supplement(root,prop):
    # Additional frozen Methods 6/7 are not historical provider-input exposure.
    packet=json.loads(Path(prop['source_packet_pin']['path']).read_text());article=json.loads(Path(packet['source']['article_path']).read_text())
    spans=[]
    for i in (6,7):
        text=article['sections'][i]['text'];h=hashlib.sha256(text.encode()).hexdigest()
        spans.append({'evidence_span_id':'identity_fulltext_supplement:'+content_hash({'source':prop['source_content_sha256'],'section':i,'text':text}),
            'section_index':i,'source_json_pointer':'/sections/'+str(i)+'/text','char_start':0,'char_end':len(text),
            'text':text,'text_hash':h,'source_section_text_sha256':h,
            'coordinate_unit':'Unicode code point; declared source-text representation'})
    packet={**packet,'packet_id':'B4_10_frozen_Methods_identity_supplement','evidence_spans':spans}
    return pin(write(root/'identity_Methods_supplement.json',packet))


def configuration(label,path):
    frozen=FROZEN[label];bundle=json.loads((frozen/'scientific_comparison.json').read_text());props=bundle['propositions']
    retained=pin(FROZEN['TRIB3']/'native_proposition_bindings.json') if label=='TRIB3' else None
    matches=[r for r in json.loads(Path(retained['path']).read_text())['rows'] if r['decision']=='SOURCE_BOUND_PROVISIONAL_MATCH'] if retained else []
    chosen={r['proposition_key'] for r in matches} if label=='TRIB3' else {'AR-2'} if label=='AR' else {p['key'] for p in props}
    items=[]
    for p in props:
        if p['key'] not in chosen:continue
        spans=p['source_evidence'];facets=p['facets'];group=facets['system']['value'];supp=None
        if label=='TRIB3':supp=source_supplement(Path(path),p)
        def mention(pointer,term,why,unresolved,refs=None):
            raw=p
            for token in pointer[1:].split('/'):raw=raw[token]
            candidates=[s['evidence_span_id'] for s in spans if term is not None and term in s['text']] if refs is None else refs
            return {'facet_pointer':pointer,'facet_value':raw,'raw_mention':term,'evidence_refs':candidates,
                'candidate_interpretation':why,'unresolved':list(unresolved)}
        common=['No approved proposition-role identity verification, validated entity type or canonical mapping',
                'Operational measurement equivalence and comparator orientation not independently verified']
        if label=='TRIB3':
            rawgroup='entire patient group' if group.startswith('all-patient') else 'low-risk' if group.startswith('low-risk') else 'high-risk'
            terms={'subject':'TRIB3','object':'OVS','biological_entity':'TRIB3','measured_entity':'TRIB3',
                   'intervention_or_grouping':'TRIB3-positive','endpoint':'overall survival (OVS)',
                   'cohort':rawgroup,'comparison':'TRIB3-positive','reported_result':None}
            interpretations={'subject':'Candidate observed TRIB3 protein biomarker role; not an assigned gene intervention',
                'object':'Overall-survival clinical endpoint; not EFS or a canonical biological entity',
                'biological_entity':'TRIB3 protein expression by IHC; gene/protein external identity not verified',
                'measured_entity':'IHC TRIB3 protein positivity and clinical survival are separate operational measurements',
                'intervention_or_grouping':'TRIB3-positive/negative observational strata, not treatment/exposure assignment',
                'endpoint':'Source explicitly expands OVS as overall survival; no cross-study endpoint equivalence',
                'cohort':'Source-specific '+rawgroup+' NB analysis; risk is not stage and parent N=56 is not subgroup n',
                'comparison':'Recorded positive/negative strata; no validated result-reference orientation link',
                'reported_result':'Positive or nonsignificant association retained in original result, not identity or causal sign'}
            limitations=common+['IHC percent-positive scoring and DF7844 antibody are reported, but positivity threshold is not established',
                'Follow-up origin/duration, HR/CI, adjusted effects and analysis/subgroup n not established']
        elif label=='HIF':
            terms={'subject':'5%' if p['key']=='PMC4024011' else 'hypoxia (1%', 'object':'HIF-1α','biological_entity':'HIF-1α',
                'measured_entity':'HIF-1α','intervention_or_grouping':'5%' if p['key']=='PMC4024011' else 'hypoxia (1%',
                'endpoint':'HIF-1α','cohort':'HCT116' if p['key']=='PMC4024011' else 'A549','comparison':'20%' if p['key']=='PMC4024011' else 'normoxia','reported_result':None}
            interpretations={k:'Source-described '+k+' for broad oxygen-exposure/HIF-1α protein abundance proposition; not gene, mRNA or transcriptional activity identity' for k in terms}
            limitations=common+['Distinct HCT116/A549 cells, 5%/1% oxygen, 72h/24h and own reference conditions',
                'Broad provisional protein proposition only; antibody/assay calibration and full operational equivalence not verified']
        elif label=='AR':
            terms={'subject':'Ar','object':'myofiber cross-sectional area','biological_entity':'Ar',
                'measured_entity':'myofiber cross-sectional area','intervention_or_grouping':'AR ablation',
                'endpoint':'Myofiber CSA','cohort':'MuSC','comparison':'Pax7-CreERT2','reported_result':None}
            interpretations={k:'Source-described '+k+' within conditional Ar deletion/MuSC experiment; CTX shared injury and TAM Cre-negative reference preserved' for k in terms}
            limitations=common+['D6 Option A: histological single-myofiber CSA stays reviewable_unknown',
                'Single-myofiber area is distinct from whole-muscle geometric CSA; no molecular mediation established']
        else:
            terms={'subject':'5%','object':'VEGF','biological_entity':'VEGF','measured_entity':'VEGF',
                'intervention_or_grouping':'5%','endpoint':'VEGF','cohort':'HCT116','comparison':'20%','reported_result':None}
            interpretations={k:'Source-described '+k+' for VEGF mRNA qRT-PCR oxygen comparison, not protein abundance; VEGFA alias not verified' for k in terms}
            limitations=common+['VEGF transcript identity is not an approved VEGFA mapping or isoform identity',
                'P=0.7 nonsignificance is not zero effect, equivalence or opposite-direction evidence; no VEGF native Core exists']
        pointers={'subject':'/facets/factor/value','object':'/facets/endpoint/value','biological_entity':'/facets/entity/value',
                  'measured_entity':'/facets/entity/value','intervention_or_grouping':'/facets/factor/value',
                  'endpoint':'/facets/endpoint/value','cohort':'/facets/system/value','comparison':'/facets/reference_arm/value',
                  'reported_result':'/result/description/value'}
        annotations={k:mention(pointers[k],t,interpretations[k],limitations if k in ('endpoint','measured_entity') else common) for k,t in terms.items()}
        # Keep source-reported Results as an auxiliary exact full sentence, not
        # a source of scientific identity or canonical alias authority.
        rr=next((s for s in spans if s['evidence_span_id'] in p['result']['description']['evidence_refs']),None)
        if rr:annotations['reported_result']=mention('/result/description/value',rr['text'],interpretations['reported_result'],common,[rr['evidence_span_id']])
        if supp:
            supplemental=json.loads(Path(supp['path']).read_text())['evidence_spans']
            for role in ('biological_entity','measured_entity'):
                annotations[role]['evidence_refs'] += [s['evidence_span_id'] for s in supplemental]
        binding=next((r for r in matches if r['proposition_key']==p['key']),None)
        oid=binding['observation_id'] if binding else p['native_observation_id']
        cores=[x for x in frozen.rglob('core.json') if json.loads(x.read_text())['ExperimentalObservationV3']['observation_id']==oid] if oid else []
        items.append({'proposition_key':p['key'],'frozen_comparison':pin(frozen/'scientific_comparison.json'),
            'frozen_inclusion':pin(frozen/'scientific_inclusion_final.json'),'proposition_revision':p['proposition_identity'],
            'native_core':pin(cores[0]) if cores else None,'native_observation_id':oid,
            'frozen_effective_projections':pin(frozen/'projected_native_observations.json') if cores else None,
            'B4_9_binding_revision':binding['binding_revision'] if binding else None,
            'supplemental_packet':supp,'mentions':annotations,'limitations':limitations})
    decisions={
        'TRIB3':'Decide separately whether source IHC TRIB3 biomarker, positivity strata, OVS endpoint and each exact patient subgroup can receive a specified local scientific identity; identify required cutoff/time/contrast limits without causal promotion.',
        'HIF':'Decide whether the two explicit Western-blot HIF-1α protein observations support a stated broad provisional protein proposition, while retaining cell/oxygen/time/reference differences and withholding complete operational equivalence.',
        'AR':'Decide the permissible identity/role scope for conditional Ar deletion versus histological single-myofiber CSA at 7 dpi, retaining MuSC, CTX shared injury and TAM Cre-negative reference; D6 remains unknown.',
        'HIF_NULL':'Decide whether frozen VEGF mRNA evidence supports any specified transcript identity beyond the source label, and what evidence would verify a VEGFA/isoform mapping; preserve P=0.7 nonsignificance.'}
    value={'schema_version':VERSION,'policy':pin(POLICY),'owner_instruction':pin(RUN/'owner_instruction.original.txt'),
        'registry':pin(REGISTRY),'retained_B4_9_bindings':retained,'items':items,'review_decision':decisions[label],
        'alternatives':{
            'TRIB3':['TRIB3 IHC positivity is an operational protein-biomarker stratum, not a verified gene-perturbation identity', 'OVS/risk-subgroup analysis may be source-local only; assay positivity cutoff or clinical endpoint authority may require clarification; risk cannot be stage'],
            'HIF':['Source captions name the same HIF-1α protein and support only a broad provisional protein-abundance question', 'The differing oxygen dose, time, cell line and assay context may preclude full operational equivalence even if biological protein identity is later verified'],
            'AR':['Conditional Ar deletion is the intervention target while histological single-myofiber CSA is a distinct measurement; both require role-specific identity evidence', 'Whole-muscle geometric CSA or a molecular mediation identity would exceed this evidence; retain D6 Option A unknown'],
            'HIF_NULL':['Retain only the source VEGF mRNA label without a verified VEGFA or isoform identifier', 'A more specific transcript identity requires additional trusted frozen mapping evidence or clarification; nonsignificance cannot determine identity or prove equivalence']}[label],
        'minimal_reviewer_issuer_requirement':'An explicitly authorized scientific reviewer or approved deterministic identity procedure with role/type, source/revision and scope verification; Atlas authentication alone and B4.6 provenance receipts do not supply this authority.',
        'producer':'interactive_Work_B4_10_source_evidence_preparation_not_identity_verification_or_independent_review'}
    return pin(write(Path(path)/'scientific_identity_evidence_configuration.json',value))


def identity_case(label,path):
    factory={'TRIB3':trib_effective,'AR':ar_semantic,'HIF':lambda p:cross_semantic(hif_comparison,p),
             'HIF_NULL':lambda p:cross_semantic(null_comparison,p)}[label]
    b,c,r=factory(path)
    r.pop('native_proposition_binding',None)
    r['scientific_identity_evidence']=configuration(label,path)
    return b,c,r
