"""B4 authentic negative/null regression and visibly separate software controls."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from code_engine.orchestration.pilot_comparison import (run_comparison, compare_pair, PairAssessment,
    Proposition, AXES, input_identity, VERSION)
from code_engine.orchestration.pilot_case import PilotCaseExecutor, CaseIntegrity
from code_engine.orchestration.pilot_budget import ModelBudget
from code_engine.orchestration.pilot_dataset import verify_dataset
from code_engine.orchestration.pilot_inclusion import InclusionLedger
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.system_b.persistence.services.pilot_review_display import case_display
from tests.test_pilot_scientific_inclusion import seen
from tests.pilot_comparison_support import (ar_comparison,hif_comparison,trib_comparison,
    null_comparison,facet,bind,source_dependencies)
from tests.test_pilot_unlimited_integration import offline


def execute(tmp_path, factory):
 b,c,r=factory(tmp_path/'inputs');budget=ModelBudget(tmp_path/'budget.sqlite',c,offline=True)
 executor=PilotCaseExecutor(tmp_path/'cases',seen(),budget,b)
 p=executor.run(r)
 assert p['terminal_state']=='NOT_EVALUABLE',p['reason']
 comparison=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role']=='scientific_comparison.json'))
 return b,r,p,comparison,executor


@pytest.mark.parametrize('factory,props,pairs',[ (ar_comparison,5,10),(hif_comparison,2,1),(trib_comparison,6,15),(null_comparison,1,0)])
def test_authentic_unified_executor_delivery(tmp_path,factory,props,pairs):
 b,r,p,d,executor=execute(tmp_path,factory)
 assert len(d['propositions'])==props and len(d['pairs'])==pairs
 assert d['denominators']['qualified_hypotheses']==d['denominators']['provisional_hypotheses']==d['denominators']['formal_contradictions']==0
 assert all(not x['scientific_authorization'] for x in d['propositions'])
 assert all(x['formal_qualification']['status']=='NOT_INVOKED_MISSING_PREREQUISITES' for x in d['pairs'])
 data=verify_dataset(tmp_path/'cases'/r['case_id']/'dataset')
 assert data['scientific_counts']['scientific_propositions']==props and not data['pipeline_complete']
 assert data['scientific_counts']['scientific_comparison']==1 and data['scientific_counts']['ai_scientific_reviews']==0
 assert case_display(p)['scientific_comparison_artifacts']
 stages={x['stage']:x for x in p['run_manifest']['stages']}
 for stage in ('shadow_alignment','context_analysis','contradiction_classification'):
  assert stages[stage]['status']=='executed'
 assert p['run_manifest']['scientific_inclusion_summary']['real_model_dispatches_this_attempt']==0
 if factory==ar_comparison:
  assert d['denominators']['publications']==1 and d['denominators']['experiments_with_reported_identity']==1
  assert d['denominators']['within_publication_pairs_retained_not_replications']==10
  assert {x['inclusion_decision'] for x in d['propositions']}=={'INCLUDED','EXCLUDED','UNCERTAIN'}
  csa=d['propositions'][2];force=d['propositions'][3]
  assert csa['facets']['time']['value']=='7 dpi' and '28 dpi' in force['facets']['time']['value']
  assert csa['factor_role']=='genetic_manipulation' and 'CTX' in csa['facets']['shared_conditions']['value']
  assert csa['native_core_revision'] and 'machine_reusable' not in csa['native_readiness']['status']
 elif factory==trib_comparison:
  assert data['scientific_counts']['experimental_core']==0 and d['denominators']['publications']==1
  assert all(x['factor_role']=='observational_biomarker_stratification' for x in d['propositions'])
  assert all(x['shared_cohort'] for x in d['pairs'])
  assert {x['facets']['endpoint']['value'] for x in d['propositions']}=={'overall survival','event-free survival'}
 elif factory==hif_comparison:
  pair=d['pairs'][0];assert pair['alignment']=='SAME_PROPOSITION_CANDIDATE' and pair['qualification']=='CONSISTENT_FINDINGS'
  assert pair['context_counts']['different']>=3
  assert all(x['explanation_sufficiency']=='UNCERTAIN' for x in pair['context_attribution'])
 else:
  p=d['propositions'][0];assert p['result']['direction']=='not_significant' and '0.7' in p['result']['description']['value']
  assert p['native_core_revision'] is None and p['experiment_identity'] is None


def software_pair():
 # No biomedical paper, no authentic source and no publication accuracy estimate.
 def prop(side,direction):
  fs={k:facet('SOFTWARE_'+k,['S'+side]) for k in ('entity','factor','focal_contrast','endpoint','assay','system','time','dose','species','genotype','shared_conditions')}
  return {'proposition_identity':'SOFTWARE:'+side,'key':side,'publication':{'pmid':'SOFTWARE_'+side,'pmcid':'SOFTWARE_'+side},
   'experiment_identity':'SOFTWARE_EXP_'+side,'cohort_dependency':None,'scope_identity':side,'provenance':'SOFTWARE_FIXTURE',
   'source_evidence':[{'evidence_span_id':'S'+side}],'facets':fs,'inclusion_decision':'INCLUDED',
   'result':{'direction':direction,'comparator_orientation':'tested_vs_reference'}}
 a,b=prop('A','increase'),prop('B','decrease')
 axes=[{'dimension':key,'decision':'MATCH','evidence_refs_a':['SA'],'evidence_refs_b':['SB'],
        'reason':'SOFTWARE_FIXTURE explicit same semantic role and endpoint'} for key in AXES]
 ctx=[{'axis':'time','facet':'time','status':'different','reason':'SOFTWARE_FIXTURE source states time modification affects response',
       'modifier_support':'SOURCE_SUPPORTED_CANDIDATE','modifier_evidence_a':['SA'],'modifier_evidence_b':['SB'],
       'support_explanation':'SOFTWARE_FIXTURE explicit factorial time perturbation support'}]
 ctx += [{'axis':f,'facet':f,'status':'same','reason':'SOFTWARE_FIXTURE explicit matching or justified nonapplicable context role'} for f in ('system','dose','genotype','shared_conditions')]
 h={'modifier_axis':'time','phenomenon':'SOFTWARE_FIXTURE opposed endpoint responses',
    'minimal_assumptions':['SOFTWARE_FIXTURE the modifier generalizes to this held-out comparison'],
    'unknowns':['SOFTWARE_FIXTURE modifier sufficiency remains untested'],
    'falsifiable_prediction':'SOFTWARE_FIXTURE switching the measured duration reverses endpoint response sign in a crossed design',
    'distinguishing_experiment':'SOFTWARE_FIXTURE cross both source systems with both exposure durations and matched controls',
    'confidence_limitations':['SOFTWARE_FIXTURE validates program paths only, no biological validation']}
 d={'left':'A','right':'B','axes':axes,'contexts':ctx,'hypothesis':h,'producer':'SOFTWARE_FIXTURE'}
 return a,b,d


def test_SOFTWARE_FIXTURE_positive_context_disagreement_and_constrained_hypothesis():
 a,b,d=software_pair();out=compare_pair(a,b,PairAssessment.model_validate(d))
 assert out['qualification']=='CONTEXT_DEPENDENT_DISAGREEMENT' and len(out['hypotheses'])==1
 h=out['hypotheses'][0];assert h['hyperedge']['mechanism_path']==[]
 assert all(x['status']=='not_run' for x in h['validation_requirement_records'])
 assert h['ranking']['score'] is None and not h['scientific_authorization']
 assert all(x['explanation_sufficiency']=='UNCERTAIN' for x in out['context_attribution'])


def test_SOFTWARE_FIXTURE_opposition_without_context_difference():
 a,b,d=software_pair();d['contexts'][0].update(status='same',modifier_support='NOT_ESTABLISHED',modifier_evidence_a=[],modifier_evidence_b=[],support_explanation=None)
 out=compare_pair(a,b,PairAssessment.model_validate(d))
 assert out['qualification']=='CANDIDATE_CONTRADICTION' and out['hypotheses']==[]


@pytest.mark.parametrize('variant',['unknown_identity','endpoint_mismatch','intervention_mismatch','assay_incompatible','null','unoriented','missing_context','excluded','uncertain','absent_assessment','no_modifier_support'])
def test_SOFTWARE_FIXTURE_abstains_or_distinguishes_propositions(variant):
 a,b,d=software_pair()
 if variant=='unknown_identity':a['facets']['entity']=facet()
 if variant in ('endpoint_mismatch','intervention_mismatch','assay_incompatible'):
  key={'endpoint_mismatch':'endpoint','intervention_mismatch':'intervention','assay_incompatible':'assay'}[variant]
  next(x for x in d['axes'] if x['dimension']==key)['decision']='INCOMPATIBLE' if variant=='assay_incompatible' else 'DIFFERENT'
 if variant=='null':b['result']['direction']='not_significant'
 if variant=='unoriented':a['result']['comparator_orientation']='unresolved'
 if variant=='missing_context':a['facets']['time']=facet();d['contexts'][0]['status']='missing_a';d['contexts'][0]['modifier_support']='NOT_ESTABLISHED'
 if variant in ('excluded','uncertain'):a['inclusion_decision']=variant.upper()
 if variant=='no_modifier_support':d['contexts'][0]['modifier_support']='NOT_ESTABLISHED'
 out=compare_pair(a,b,None if variant=='absent_assessment' else PairAssessment.model_validate(d))
 assert out['hypotheses']==[]
 if variant not in ('no_modifier_support',):assert out['qualification'] not in ('CANDIDATE_CONTRADICTION','CONTEXT_DEPENDENT_DISAGREEMENT')


@pytest.mark.parametrize('mutation',['authority','anchor','packet_hash','orientation','native','question'])
def test_authentic_input_corruption_controlled_failure(tmp_path,mutation):
 b,c,req=hif_comparison(tmp_path/'inputs');pin=req['scientific_comparison_assessments'];raw=json.loads(Path(pin['path']).read_text())
 if mutation=='authority':raw['propositions'][0]['scientific_authorization']=True
 elif mutation=='anchor':raw['propositions'][0]['facets']['entity']['evidence_refs']=['NONEXISTENT']
 elif mutation=='packet_hash':raw['propositions'][0]['source_packet_pin']['sha256']='0'*64
 elif mutation=='orientation':raw['propositions'][0]['facets']['reference_arm']=facet()
 elif mutation=='native':raw['propositions'][0]['native_observation_id']='FAKE'
 elif mutation=='question':raw['question_identity']='other'
 from tests.pilot_inclusion_support import write,pin as mkpin
 write(pin['path'],raw);req['scientific_comparison_assessments']=mkpin(pin['path'])
 p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.sqlite',c,offline=True),b).run(req)
 assert p['terminal_state']=='INTEGRITY_FAILED' and ('ValueError' in p['reason'] or 'ValidationError' in p['reason']),p['reason']
 assert not any(a['role']=='scientific_comparison.json' for a in p['artifacts'])


def test_derived_assessment_dependency_drift_rejects_completed_reuse_without_dispatch(tmp_path):
 b,req,p,d,executor=execute(tmp_path,hif_comparison);calls=len(b.transport.calls)
 pin=req['scientific_comparison_assessments'];path=Path(pin['path']);raw=json.loads(path.read_text());old=input_identity(req)
 raw['producer']+=' revised semantic assessment';path.write_text(json.dumps(raw))
 assert input_identity(req)!=old
 with pytest.raises(CaseIntegrity,match='input_drift'):executor.run(req)
 assert len(b.transport.calls)==calls


def test_absent_b4_input_is_explicit_not_evaluated():
 out=run_comparison({'case_id':'EMPTY','question':'Unknown','scope':{}},{'rows':[]},[],bindings={})
 assert out['input_state']['status']=='NOT_EVALUATED' and out['denominators']['publications']==0


def test_current_default_no_inputs_abstains_without_legacy_lexical_substitution(tmp_path):
 b,c,req=hif_comparison(tmp_path/'inputs');req.pop('scientific_comparison_assessments')
 p=PilotCaseExecutor(tmp_path/'cases',seen(),ModelBudget(tmp_path/'b.sqlite',c,offline=True),b).run(req)
 assert p['terminal_state']=='NOT_EVALUABLE' and 'B4_SEMANTIC_INPUT_UNAVAILABLE' in p['reason']
 assert p['pair_packages']==[]
 d=json.loads(next(a['utf8'] for a in p['artifacts'] if a['role']=='scientific_comparison.json'))
 assert d['input_state']['status']=='NOT_EVALUATED' and not d['hypotheses']


def test_changed_valid_semantics_new_revision_reuses_exact_raw_requests(tmp_path):
 b,req,p,d,executor=execute(tmp_path,hif_comparison);calls=len(b.transport.calls)
 from code_engine.orchestration.pilot_inclusion import question_identity
 from tests.pilot_inclusion_support import write,pin
 req['case_id']+='-B4-REVISION'
 for key in ('scientific_inclusion_assessments','scientific_comparison_assessments'):
  data=json.loads(Path(req[key]['path']).read_text());data['question_identity']=question_identity(req)
  if key=='scientific_comparison_assessments':data['producer']+='; explicitly revised commentary without provider request changes'
  path=tmp_path/(key+'_revision.json');write(path,data);req[key]=pin(path)
 new=executor.run(req)
 assert new['terminal_state']=='NOT_EVALUABLE' and len(b.transport.calls)==calls
 assert new['costs']['accounted_nusd']==0
 assert new['run_manifest']['derived_execution_dependencies_sha256']!=p['run_manifest']['derived_execution_dependencies_sha256']
