"""Versioned Pilot adapter for source-bound, explicitly provisional comparison.

Consumes bounded Work scientific assessments, never classifies arbitrary text.
Native Core/Projection and the ordered formal L4 gates remain independent inputs;
missing identity, grounding or policy authority is not manufactured here.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Literal
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code_engine.discovery.ai_review_shadow import ShadowAuthority, content_hash, file_hash
from code_engine.orchestration.pilot_inclusion import question_identity, read_pin
from code_engine.context_attribution.claim_alignment.scientific_proposition_v1_candidate import (
    StructuredSemanticValueV1, DimensionCompatibilityAssessmentV1,
    make_scientific_proposition_signature_v1, InterventionPropositionV1,
    CausalEvidentialModeV1, ExperimentalContrastSemanticsV1,
)
from code_engine.context_attribution.context_difference.models import FactorDifference
from code_engine.hypothesis.validation_requirements import build_validation_requirements_for_hypothesis
from code_engine.hypothesis.hyperedge_builder import build_hypothesis_hyperedge

VERSION = 'pilot_source_bound_scientific_comparison_v1'
AXES = ('biological_entity', 'intervention', 'contrast', 'endpoint', 'assay', 'system', 'conditions', 'source_support')
FACETS = ('entity', 'factor', 'focal_contrast', 'tested_arm', 'reference_arm',
          'shared_conditions', 'system', 'species', 'cell_type', 'tissue',
          'endpoint', 'assay', 'time', 'dose', 'genotype', 'statistical_interpretation')
AUTHORITY = ShadowAuthority().model_dump(mode='json')
FORMAL_BLOCKERS = ['scientific_entity_integrity_and_identity_authority_not_established',
                   'validated_claim_alignment_and_candidate_qualification_not_supplied',
                   'independent_scientific_authorization_not_granted',
                   'activated_comparability_and_explanation_policy_or_adjudication_not_supplied']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class Facet(Strict):
    value: str | None
    evidence_refs: list[str]
    uncertainty: str = Field(min_length=5)

    @model_validator(mode='after')
    def evidenced(self):
        if self.value is not None and (not self.value.strip() or not self.evidence_refs):
            raise ValueError('present_semantic_field_requires_exact_evidence')
        return self


class Result(Strict):
    direction: Literal['increase', 'decrease', 'not_significant', 'unknown']
    description: Facet
    # A P value is a source assertion, never an effect-size substitute.
    effect_size: Facet
    comparator_orientation: Literal['tested_vs_reference', 'unresolved']


class Proposition(ShadowAuthority):
    key: str
    scope_identity: str
    experiment_identity: str | None
    source_packet_pin: dict | None = None
    retained_native_pins: list[dict] = Field(default_factory=list)
    native_observation_id: str | None = None
    facets: dict[str, Facet]
    factor_role: Literal['physical_intervention', 'genetic_manipulation',
                         'observational_biomarker_stratification', 'exposure', 'unresolved']
    result: Result
    # These identifiers describe run-local dependencies, not inferred cohort identity.
    cohort_dependency: str | None = None
    missing_information: list[str]
    provenance: str = Field(min_length=12)

    @model_validator(mode='after')
    def fields_complete(self):
        if set(self.facets) != set(FACETS):
            raise ValueError('all_semantic_facets_required_with_explicit_unknowns')
        return self


class Axis(Strict):
    dimension: Literal['biological_entity', 'intervention', 'contrast', 'endpoint', 'assay', 'system', 'conditions', 'source_support']
    decision: Literal['MATCH', 'COMPATIBLE', 'DIFFERENT', 'INCOMPATIBLE', 'UNKNOWN']
    evidence_refs_a: list[str]
    evidence_refs_b: list[str]
    reason: str = Field(min_length=12)


class ContextAssessment(Strict):
    axis: str
    facet: str
    status: Literal['same', 'different', 'missing_a', 'missing_b', 'missing_both']
    reason: str = Field(min_length=12)
    modifier_support: Literal['NOT_ESTABLISHED', 'SOURCE_SUPPORTED_CANDIDATE'] = 'NOT_ESTABLISHED'
    modifier_evidence_a: list[str] = Field(default_factory=list)
    modifier_evidence_b: list[str] = Field(default_factory=list)
    support_explanation: str | None = None


class HypothesisProposal(Strict):
    modifier_axis: str
    phenomenon: str = Field(min_length=12)
    minimal_assumptions: list[str] = Field(min_length=1)
    unknowns: list[str] = Field(min_length=1)
    falsifiable_prediction: str = Field(min_length=20)
    distinguishing_experiment: str = Field(min_length=20)
    confidence_limitations: list[str] = Field(min_length=1)


class PairAssessment(ShadowAuthority):
    left: str
    right: str
    axes: list[Axis]
    contexts: list[ContextAssessment]
    hypothesis: HypothesisProposal | None = None
    producer: str = Field(min_length=12)

    @model_validator(mode='after')
    def unique(self):
        if self.left == self.right or len(self.axes) != len(AXES) or {x.dimension for x in self.axes} != set(AXES):
            raise ValueError('distinct_observations_and_all_eight_alignment_axes_required')
        if len({c.axis for c in self.contexts}) != len(self.contexts):
            raise ValueError('duplicate_context_axis')
        return self


def input_identity(request):
    """Actual transitive bytes invalidate derivations; never affect raw API cache."""
    pin = request.get('scientific_comparison_assessments')
    found = {}
    inspected = set()
    def visit(value):
        if isinstance(value, dict):
            for name in ('article_path', 'article_json_path', 'original_xml_path'):
                if isinstance(value.get(name), str):
                    source_path = Path(value[name])
                    found[str(source_path.resolve())] = file_hash(source_path) if source_path.is_file() else None
            if isinstance(value.get('path'), str) and 'sha256' in value:
                p = Path(value['path']); key = str(p.resolve())
                found[key] = file_hash(p) if p.is_file() else None
                if p.is_file() and p.suffix == '.json' and key not in inspected:
                    inspected.add(key)
                    try:
                        document = json.loads(p.read_text()); visit(document)
                        source = document.get('source', {}) if isinstance(document, dict) else {}
                        for name in ('article_path', 'article_json_path', 'original_xml_path'):
                            if source.get(name):
                                source_path = Path(source[name])
                                found[str(source_path.resolve())] = file_hash(source_path) if source_path.is_file() else None
                    except (ValueError, OSError): pass
            for v in value.values(): visit(v)
        elif isinstance(value, list):
            for v in value: visit(v)
    visit(pin)
    if isinstance(pin, dict) and Path(pin.get('path', '')).is_file():
        try: visit(json.loads(Path(pin['path']).read_text()))
        except (ValueError, OSError): pass
    return content_hash({'version': VERSION, 'declared': pin, 'actual_files': found})


def _refs(refs, evidence):
    if not set(refs) <= evidence:
        raise ValueError('comparison_unknown_source_evidence_reference')


def _signature(p, obs):
    def value(key):
        f = p.facets[key]
        return StructuredSemanticValueV1(value=f.value, canonical_identity=None,
            authority_state='structured_only' if f.value is not None else 'missing', source_refs=f.evidence_refs)
    observed = p.factor_role == 'observational_biomarker_stratification'
    # Explicit roles are source-bound Work assessments, not causal authorization.
    return make_scientific_proposition_signature_v1(observation_id=obs,
        subject_identity=None, relation_effect_family=None, object_target_identity=None,
        measurement_targets=[value('entity')], measured_properties=[value('endpoint')],
        assay_methods=[value('assay')],
        intervention_proposition=InterventionPropositionV1(intervention_mode='unresolved',
            target_values=[value('factor')], authority_state='unresolved', source_refs=p.facets['factor'].evidence_refs),
        causal_evidential_mode=CausalEvidentialModeV1(observation_type='observational_comparison' if observed else
            'unresolved' if p.factor_role == 'unresolved' else 'interventional_experiment',
            mode_family='observational_association' if observed else None, authority_state='unresolved'),
        experimental_contrast=ExperimentalContrastSemanticsV1(
            contrast_role='unresolved_reference_structure' if p.result.comparator_orientation == 'unresolved' else
                'observational_group_vs_reference' if observed else 'experimental_vs_reference',
            reference_labels=[value('reference_arm')], authority_state='unresolved',
            # No links materialized from provisional facet text.
            comparison_link_count=0, baseline_link_count=0, source_refs=p.facets['focal_contrast'].evidence_refs),
        source_refs=sorted({r for f in p.facets.values() for r in f.evidence_refs})).model_dump(mode='json')


def build_propositions(request, ledger, records, *, bindings):
    pin = request.get('scientific_comparison_assessments')
    if not pin:
        return [], [], {'status': 'NOT_EVALUATED', 'reason': 'No source-bound semantic comparison assessments supplied'}
    raw = read_pin(pin)
    if raw.get('schema_version') != VERSION or raw.get('question_identity') != question_identity(request):
        raise ValueError('comparison_question_or_version_mismatch')
    if raw.get('scientific_authorization') is not False:
        raise ValueError('comparison_cannot_grant_scientific_authority')
    # Verify every supplied dependency, including native XML handoff limitations.
    for dependency in raw.get('dependency_pins', []):
        if file_hash(Path(dependency['path'])) != dependency['sha256']:
            raise ValueError('comparison_dependency_hash_drift')
    inputs = [Proposition.model_validate(p) for p in raw['propositions']]
    if len({p.key for p in inputs}) != len(inputs) or len({p.scope_identity for p in inputs}) != len(inputs):
        raise ValueError('duplicate_proposition_key_or_observation_scope')
    native = {json.loads(r['core'].read_text())['ExperimentalObservationV3']['observation_id']: r for r in records}
    propositions = []
    for p in inputs:
        rows = [r for r in ledger['rows'] if r['scope_level'] == 'observation' and r['scope_identity'] == p.scope_identity]
        if len(rows) != 1 or rows[0]['assessment_state'] != 'ASSESSED':
            raise ValueError('comparison_requires_exact_valid_observation_inclusion_assessment')
        row = rows[0]
        if file_hash(Path(row['source_artifact'])) != row['source_content_sha256']:
            raise ValueError('comparison_source_hash_drift')
        evidence = {s['evidence_span_id'] for s in row['evidence_spans']}
        for f in [*p.facets.values(), p.result.description, p.result.effect_size]: _refs(f.evidence_refs, evidence)
        if p.result.direction != 'unknown' and p.result.description.value is None:
            raise ValueError('observed_direction_requires_source_description')
        if p.result.comparator_orientation == 'tested_vs_reference' and any(
                p.facets[k].value is None for k in ('tested_arm', 'reference_arm', 'focal_contrast')):
            raise ValueError('oriented_result_requires_explicit_arms_and_contrast')
        for pin in p.retained_native_pins:
            if file_hash(Path(pin['path'])) != pin['sha256']: raise ValueError('retained_native_hash_drift')
        if p.source_packet_pin:
            # Existing exact ArticleJSON/JATS packet validator, no new span conversion.
            from code_engine.discovery.ai_review_shadow import load_bound_packet
            bound = load_bound_packet(Path(p.source_packet_pin['path']), Path(p.source_packet_pin['path']))
            if file_hash(Path(p.source_packet_pin['path'])) != p.source_packet_pin['sha256']:
                raise ValueError('comparison_packet_hash_drift')
            source = bound.packet['source']; actual = source.get('article_sha256') or source.get('article_json_sha256')
            if actual != row['source_content_sha256'] or source['pmcid'] != row['source_identity']['pmcid']:
                raise ValueError('comparison_packet_source_mismatch')
        r = native.get(p.native_observation_id); revision = None; readiness = None; native_signature = None
        if p.native_observation_id is not None:
            if r is None: raise ValueError('native_comparison_record_not_retained')
            core = json.loads(r['core'].read_text()); formal = core['ExperimentalObservationV3']
            if p.scope_identity != p.native_observation_id or formal['experiment']['experiment_id'] != p.experiment_identity:
                raise ValueError('comparison_native_scope_or_experiment_mismatch')
            if formal['provenance']['fulltext_source_hash'] != row['source_content_sha256']:
                raise ValueError('comparison_native_source_mismatch')
            revision = core['ExperimentalCore']['revision']['identity']
            readiness = r['prepared']['experimental_core_handoff_audit']['readiness']
            native_signature = {'core_sha256': file_hash(r['core']), 'revision': revision}
        prop = {**p.model_dump(mode='json'), 'schema_version': VERSION + ':proposition',
            'question_identity': question_identity(request), 'publication': row['source_identity'],
            'source_content_sha256': row['source_content_sha256'], 'source_artifact': row['source_artifact'],
            'source_evidence': row['evidence_spans'], 'inclusion_revision_identity': row['revision_identity'],
            'inclusion_decision': row['decision'], 'native_core_revision': revision, 'native_readiness': readiness,
            'native_record_binding': native_signature, 'upstream_bindings': bindings,
            'signature_origin': 'Explicit source-bound semantic facets using existing signature constructor; NOT a newly materialized Core projection',
            'scientific_signature': _signature(p, p.native_observation_id or p.scope_identity),
            'formal_authority_blockers': FORMAL_BLOCKERS,
            'normalization_uncertainty': 'No new canonical identity, assay equivalence, causal edge or grounding authority'}
        prop['proposition_identity'] = 'pilot_proposition:' + content_hash(prop)
        propositions.append(prop)
    pairs = [PairAssessment.model_validate(p) for p in raw.get('pairs', [])]
    if len({frozenset((p.left, p.right)) for p in pairs}) != len(pairs): raise ValueError('duplicate_pair_assessment')
    return propositions, pairs, {'status': 'SOURCE_BOUND_PROVISIONAL', 'input_pin': pin,
                               'producer': raw.get('producer'), 'semantic_assessments_are_not_model_extraction': True}


def compare_pair(a, b, assessment=None):
    """Direction follows alignment and comparator checks, never establishes identity."""
    independent = None
    ia, ib = a['publication'], b['publication']
    if ia.get('pmid') and ib.get('pmid') and ia.get('pmcid') and ib.get('pmcid'):
        independent = ia['pmid'] != ib['pmid'] and ia['pmcid'] != ib['pmcid']
    result = {**AUTHORITY, 'evidence_origin': 'SOFTWARE_FIXTURE' if a.get('provenance') == b.get('provenance') == 'SOFTWARE_FIXTURE' else 'source_bound_Work_provisional', 'pair_id': content_hash([a['proposition_identity'], b['proposition_identity']]),
        'proposition_keys': [a['key'], b['key']], 'proposition_identities': [a['proposition_identity'], b['proposition_identity']],
        'publication_group': sorted({ia.get('pmcid'), ib.get('pmcid')} - {None}),
        'independent_publications': independent, 'shared_experiment': independent is False and
            a['experiment_identity'] is not None and a['experiment_identity'] == b['experiment_identity'],
        'shared_cohort': independent is False and a['cohort_dependency'] is not None and a['cohort_dependency'] == b['cohort_dependency'],
        'cross_publication_cohort_independence': 'UNKNOWN; distinct publications do not prove distinct cohorts',
        'axes': [], 'context_differences': [], 'context_attribution': [], 'hypotheses': [],
        'formal_qualification': {'status': 'NOT_INVOKED_MISSING_PREREQUISITES', 'blockers': FORMAL_BLOCKERS,
          'ordered_contract': ['qualified_candidate', 'L4a_context_difference', 'L4b_comparability',
                               'divergence_explanatory_power', 'L4c_formal_candidate']}}
    if independent is not True:
        result.update(alignment='NOT_COMPARABLE' if independent is False else 'INSUFFICIENT_EVIDENCE',
                      qualification='NOT_EVALUATED', reason='Independent publications not established')
        return result
    if assessment is None:
        result.update(alignment='INSUFFICIENT_EVIDENCE', qualification='INSUFFICIENT_EVIDENCE',
                      reason='No explicit eight-axis source-grounded scientific assessment')
        return result
    if (assessment.left, assessment.right) != (a['key'], b['key']):
        raise ValueError('pair_orientation_mismatch')
    refs = [{s['evidence_span_id'] for s in x['source_evidence']} for x in (a, b)]
    if assessment.producer == 'SOFTWARE_FIXTURE' and any(x.get('provenance') != 'SOFTWARE_FIXTURE' for x in (a, b)):
        raise ValueError('software_pair_cannot_be_authentic_scientific_assessment')
    mapping = {'MATCH': 'compatible_exact', 'COMPATIBLE': 'compatible_with_granularity_qualification',
               'DIFFERENT': 'incompatible', 'INCOMPATIBLE': 'incompatible', 'UNKNOWN': 'unresolved'}
    for axis in assessment.axes:
        _refs(axis.evidence_refs_a, refs[0]); _refs(axis.evidence_refs_b, refs[1])
        if axis.decision != 'UNKNOWN' and (not axis.evidence_refs_a or not axis.evidence_refs_b):
            raise ValueError('known_alignment_decision_requires_two_source_evidence')
        diagnostic = DimensionCompatibilityAssessmentV1(dimension_id=axis.dimension,
            semantic_role='compatibility_qualifier' if axis.dimension in ('system', 'conditions') else 'proposition_critical',
            compatibility_state=mapping[axis.decision], reason=axis.reason).model_dump(mode='json')
        result['axes'].append({**axis.model_dump(mode='json'), 'existing_dimension_contract': diagnostic,
                              'assessment_authority': 'Work_provisional_only_not_formal_identity'})
    byaxis = {x.dimension: x.decision for x in assessment.axes}
    # Exact identity cannot be inferred merely from the presence of common names.
    facet_axis = {'biological_entity': 'entity', 'intervention': 'factor', 'contrast': 'focal_contrast',
                  'endpoint': 'endpoint', 'assay': 'assay', 'system': 'system'}
    unresolved = [axis for axis, facet in facet_axis.items() if any(x['facets'][facet]['value'] is None for x in (a, b))]
    statuses = Counter()
    for c in assessment.contexts:
        if c.facet not in FACETS: raise ValueError('unknown_context_semantic_role')
        fa, fb = a['facets'][c.facet], b['facets'][c.facet]
        d = FactorDifference(factor_id=c.axis, status=c.status, claim_a_value=fa['value'], claim_b_value=fb['value'],
            claim_a_anchor_ids=fa['evidence_refs'], claim_b_anchor_ids=fb['evidence_refs'],
            comparison_rationale=c.reason, provenance={'producer': assessment.producer, **AUTHORITY}).model_dump(mode='json')
        result['context_differences'].append({**d, 'semantic_role': c.facet})
        statuses[c.status] += 1
        _refs(c.modifier_evidence_a, refs[0]); _refs(c.modifier_evidence_b, refs[1])
        supported = c.modifier_support == 'SOURCE_SUPPORTED_CANDIDATE'
        if supported and (c.status != 'different' or not c.support_explanation or not (c.modifier_evidence_a or c.modifier_evidence_b)):
            raise ValueError('modifier_requires_explicit_support_beyond_context_difference')
        result['context_attribution'].append({'axis': c.axis, 'context_difference_present': c.status == 'different',
            'modifier_support': c.modifier_support, 'modifier_evidence_a': c.modifier_evidence_a,
            'modifier_evidence_b': c.modifier_evidence_b, 'support_explanation': c.support_explanation,
            'explanation_sufficiency': 'UNCERTAIN', 'formal_explanatory_effect': None,
            'source_difference_is_not_causal_explanation': True})
    result['context_counts'] = dict(statuses)
    if any(x['inclusion_decision'] != 'INCLUDED' for x in (a, b)):
        alignment = 'INSUFFICIENT_EVIDENCE'
    elif unresolved or 'UNKNOWN' in byaxis.values(): alignment = 'INSUFFICIENT_EVIDENCE'
    elif 'INCOMPATIBLE' in byaxis.values(): alignment = 'NOT_COMPARABLE'
    elif any(byaxis[k] == 'DIFFERENT' for k in ('biological_entity', 'intervention', 'contrast', 'endpoint', 'assay')):
        alignment = 'RELATED_BUT_DIFFERENT_PROPOSITION'
    else: alignment = 'SAME_PROPOSITION_CANDIDATE'
    oriented = all(x['result']['comparator_orientation'] == 'tested_vs_reference' for x in (a, b))
    directions = [x['result']['direction'] for x in (a, b)]
    if alignment == 'RELATED_BUT_DIFFERENT_PROPOSITION': qualification = 'DIFFERENT_SCIENTIFIC_PROPOSITIONS'
    elif alignment == 'NOT_COMPARABLE': qualification = 'NOT_EVALUATED'
    elif alignment != 'SAME_PROPOSITION_CANDIDATE' or not oriented: qualification = 'INSUFFICIENT_EVIDENCE'
    elif 'not_significant' in directions or 'unknown' in directions: qualification = 'INSUFFICIENT_EVIDENCE'
    elif directions[0] == directions[1]: qualification = 'CONSISTENT_FINDINGS'
    elif set(directions) == {'increase', 'decrease'}:
        qualification = 'CONTEXT_DEPENDENT_DISAGREEMENT' if statuses['different'] else 'CANDIDATE_CONTRADICTION'
    else: qualification = 'INSUFFICIENT_EVIDENCE'
    result.update(alignment=alignment, qualification=qualification,
        direction_interpretation='Nonsignificance is not equality, zero effect or opposition',
        scientific_comparability='supports_further_provisional_review' if alignment == 'SAME_PROPOSITION_CANDIDATE' else 'not_established',
        reason='Eight independent semantic axes assessed; explicit arms precede outcome comparison',
        field_uncertainties=unresolved,
        missing_context_axes=[c.axis for c in assessment.contexts if c.status.startswith('missing')])
    # Each relevant context role must be represented, including explicit missing
    # values. A caller cannot omit inconvenient axes to obtain a positive screen.
    required_context = {'system', 'time', 'dose', 'genotype', 'shared_conditions'}
    context_facets = {c.facet for c in assessment.contexts}
    result['context_roles_unassessed'] = sorted(required_context - context_facets)
    # Adequate context is required before interpreting opposing signs as a screen.
    if qualification in ('CANDIDATE_CONTRADICTION', 'CONTEXT_DEPENDENT_DISAGREEMENT') and (
            not assessment.contexts or result['missing_context_axes'] or result['context_roles_unassessed']):
        result['qualification'] = 'INSUFFICIENT_EVIDENCE'
        result['reason'] = 'Opposing directions retained; context incomplete, contradiction screening abstains'
    if assessment.hypothesis:
        result['hypotheses'] = constrained_hypotheses(result, a, b, assessment)
    result['hypothesis_abstention_reason'] = None if result['hypotheses'] else (
        'No adequately aligned opposing observations with an explicitly source-supported modifier and bounded falsifiable proposal')
    return result


def constrained_hypotheses(pair, a, b, assessment):
    if pair['qualification'] not in ('CANDIDATE_CONTRADICTION', 'CONTEXT_DEPENDENT_DISAGREEMENT'):
        return []
    h = assessment.hypothesis
    support = next((c for c in pair['context_attribution'] if c['axis'] == h.modifier_axis and
                    c['modifier_support'] == 'SOURCE_SUPPORTED_CANDIDATE'), None)
    if support is None: return []
    item = {**AUTHORITY, 'hypothesis_id': 'pilot_hypothesis:' + content_hash([pair['pair_id'], h.model_dump()]),
        'hypothesis_type': 'context_partition_hypothesis', 'status': 'provisional_unvalidated',
        'evidence_origin': pair['evidence_origin'], 'source_mode': 'explicit_source_bound_Work_proposal', 'source_scope': 'full_text',
        'evidence_tier': 'AI_provisional', 'phenomenon': h.phenomenon,
        'observations': [a['result'], b['result']], 'context_variables': [h.modifier_axis],
        'source_supported_modifier': support, 'minimal_additional_assumptions': h.minimal_assumptions,
        'unknowns': h.unknowns, 'falsifiable_prediction': h.falsifiable_prediction,
        'distinguishing_experiment': h.distinguishing_experiment,
        'confidence_limitations': h.confidence_limitations, 'hypothesis_text': h.falsifiable_prediction,
        'linked_conflict_ids': [pair['pair_id']], 'linked_observation_ids': [a['scope_identity'], b['scope_identity']],
        'linked_paper_ids': pair['publication_group'], 'linked_evidence_ids': sorted({
            r for c in assessment.contexts if c.axis == h.modifier_axis for r in c.modifier_evidence_a + c.modifier_evidence_b}),
        'requires_manual_review': True, 'requires_external_validation': True,
        'tradeoffs_or_limitations': h.confidence_limitations, 'warnings': ['Run-local proposal; no causal identifiability or independent validation']}
    requirements = build_validation_requirements_for_hypothesis(item)
    item['validation_requirements'] = [r['requirement_type'] for r in requirements]
    item['validation_requirement_records'] = requirements
    # Existing hyperedge schema; no random/beam score or invented mechanism path.
    item['hyperedge'] = build_hypothesis_hyperedge(item).model_dump(mode='json')
    item['ranking'] = {'rank': None, 'score': None, 'basis': 'Unscored pending validation; no causal or Bayesian interpretation'}
    return [item]


def run_comparison(request, ledger, records, *, bindings):
    props, assessments, state = build_propositions(request, ledger, records, bindings=bindings)
    lookup = {p['key']: p for p in props}
    for p in assessments:
        if p.left not in lookup or p.right not in lookup: raise ValueError('pair_proposition_not_present')
    decisions = {frozenset((p.left, p.right)): p for p in assessments}
    pairs = []
    for a, b in combinations(props, 2):
        decision = decisions.get(frozenset((a['key'], b['key'])))
        if decision and decision.left != a['key']: a, b = b, a
        pairs.append(compare_pair(a, b, decision))
    publications = sorted({p['publication']['pmcid'] for p in props})
    groups = {}
    for p in pairs:
        if p['independent_publications']:
            key = '|'.join(p['publication_group']); groups.setdefault(key, []).append(p['pair_id'])
    hypotheses = [h for p in pairs for h in p['hypotheses']]
    counts = {'publications': len(publications),
        'experiments_with_reported_identity': len({(p['publication']['pmcid'], p['experiment_identity']) for p in props if p['experiment_identity']}),
        'experiment_identity_missing': sum(p['experiment_identity'] is None for p in props),
        'observations': len({(p['publication']['pmcid'], p['scope_identity']) for p in props}),
        'candidate_pairs': len(pairs), 'independent_publication_pairs': len(groups),
        'within_publication_pairs_retained_not_replications': sum(p['independent_publications'] is False for p in pairs),
        'comparable_pairs': sum(p['alignment'] == 'SAME_PROPOSITION_CANDIDATE' for p in pairs),
        'provisional_disagreement_pairs': sum(p['qualification'] in ('CANDIDATE_CONTRADICTION', 'CONTEXT_DEPENDENT_DISAGREEMENT') for p in pairs),
        'unresolved_pairs': sum(p['qualification'] in ('INSUFFICIENT_EVIDENCE', 'NOT_EVALUATED') for p in pairs),
        'qualified_hypotheses': 0, 'provisional_hypotheses': len(hypotheses), 'formal_contradictions': 0}
    return {**AUTHORITY, 'schema_version': VERSION, 'input_state': state, 'question_identity': question_identity(request),
        'bindings': bindings, 'propositions': props, 'pairs': pairs, 'publication_dependencies': groups,
        'denominators': counts, 'hypotheses': hypotheses, 'formal_authority_blockers': FORMAL_BLOCKERS,
        'dependence_inventory': [{'publication': pmc,
            'observation_keys': [p['key'] for p in props if p['publication']['pmcid'] == pmc],
            'known_experiment_groups': {exp: [p['key'] for p in props if p['publication']['pmcid'] == pmc and p['experiment_identity'] == exp]
                for exp in sorted({p['experiment_identity'] for p in props if p['publication']['pmcid'] == pmc and p['experiment_identity']})},
            'cohort_groups': {cohort: [p['key'] for p in props if p['publication']['pmcid'] == pmc and p['cohort_dependency'] == cohort]
                for cohort in sorted({p['cohort_dependency'] for p in props if p['publication']['pmcid'] == pmc and p['cohort_dependency']})},
            'unreported_experiment_scope_count': sum(p['experiment_identity'] is None for p in props if p['publication']['pmcid'] == pmc)}
            for pmc in publications],
        'validation_requirements': [r for h in hypotheses for r in h['validation_requirement_records']],
        'coverage': {'semantic_assessments_supplied': len(assessments), 'independent_pair_assessments_executed': sum(
            p['independent_publications'] is True and bool(p['axes']) for p in pairs),
            'not_evaluated_pairs': sum(p['qualification'] == 'NOT_EVALUATED' for p in pairs),
            'full_L0_L6_scientific_execution': False, 'independent_biological_validation': False,
            'source_coverage_is_bounded_packets_not_full_publications': True}}
