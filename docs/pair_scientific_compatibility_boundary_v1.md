# Pair Scientific Compatibility Boundary v1

Status: Candidate sidecar contract  
Contract identity: `pair_scientific_compatibility_boundary_v1`  
Implementation: `src/code_engine/extraction_assets/context/pair_scientific_compatibility_v1_candidate.py`

## Purpose

This contract separates proposition identity, scientific compatibility, and
explanatory Context for an existing pair of experimental observations. It is
additive and read-only with respect to historical Claim Alignment, Candidate,
L4a, Divergence, and Formal records.

The two governing invariants are:

1. A known contextual difference does not automatically make experiments
   incomparable.
2. A known difference in proposition, measurement, or design semantics does not
   automatically make experiments comparable merely because both values are
   known.

## Definitions

### Proposition Identity

Proposition Identity asks whether two observations assert the same scientific
proposition at a compatible semantic granularity. Claim Alignment and
Qualification own this decision. Canonical subject, relation family, endpoint,
outcome variable, proposition-defining intervention target, measurement target
or endpoint type, and result semantic level may be proposition-critical.

L4b may consume an upstream determination. It must not compare raw strings,
extend a granularity bridge, reinterpret an intervention, or repair Alignment.
When Experimental Core contains a proposition-critical fact that the current
Alignment projection does not consume, the result is an Alignment semantic
coverage gap rather than an L4b Context requirement.

### Scientific Compatibility

Scientific Compatibility asks whether non-identical measurement or experiment
structures permit the observations to support a scientifically meaningful
comparison. Examples include measurement method compatibility, assay
compatibility, evidence-family compatibility, baseline or control compatibility,
and experimental-contrast compatibility.

Known values are not enough. A `compatibility_required` unit is satisfied only
by a versioned deterministic compatibility result. Raw `matched` or `different`
states do not establish compatibility. Incompatibility may be emitted only when
deterministic contract authority establishes it; string inequality alone is
never such authority.

### Explanatory Context

Explanatory Context describes the conditions under which an already aligned,
scientifically compatible observation was made. Examples may include biological
model, disease state, genotype, ordinary temporal context, environmental
localization, population/cohort, and dose or treatment implementation when a
versioned role contract assigns that meaning.

An explanatory Context requirement is a resolution requirement, not an equality
requirement. Supported `matched` and supported `different` values both satisfy
`resolution_only`. For example, known WT versus known KO can remain comparable
and can be retained as a Context Difference. Known WT versus unknown genotype
does not satisfy a required explanatory Context unit.

Dimension membership or field presence alone does not prove that a unit is
explanatory. Endpoint-qualified localization, endpoint-defined time, or a
proposition-defining intervention must instead remain upstream or unresolved.

### Context Difference

Context Difference is L4a's descriptive result that two authoritative Context
values are the same, different, unresolved, or ambiguous. It does not decide
scientific compatibility. A resolved difference can be handed downstream as an
explanation candidate only when a separate role contract makes the dimension
eligible. It does not state that the difference caused the observed divergence.

### Comparability

Comparability is L4b's determination that all upstream proposition gates,
compatibility-critical requirements, and required explanatory Context units are
satisfied. Comparability permits interpretation of agreement or divergence; it
does not require identical experiments.

`comparable_with_context_divergence` is a positive result. It preserves one or
more resolved explanatory Context differences. It cannot be produced from a
resolved proposition-critical or compatibility-critical difference without the
required upstream or compatibility authority.

### Divergence Explanation

Divergence Explanation evaluates whether an eligible Context Difference helps
explain an observed result divergence. It is downstream of L4a and L4b. Neither
Context resolution nor comparability proves explanation. Divergence does not own
proposition alignment, compatibility, or requirement activation.

## Scientific roles and satisfaction policies

Every audited semantic unit has exactly one role and corresponding policy:

| Scientific role | Satisfaction policy | Satisfying authority |
|---|---|---|
| `proposition_alignment_critical` | `upstream_alignment_required` | validated upstream Alignment/Qualification result |
| `comparison_compatibility_critical` | `compatibility_required` | versioned deterministic compatibility result |
| `context_explanatory` | `resolution_only` | supported two-sided `matched` or `different` Context |
| `explicitly_not_decision_relevant` | `not_decision_relevant` | explicit versioned consumer contract |
| `semantic_role_unresolved` | `semantic_role_unresolved` | none; review is required |

`upstream_alignment_partial_but_reviewable` and
`alignment_semantic_coverage_gap` do not satisfy
`upstream_alignment_required`. L4b records the blocker or review state and
leaves the upstream object unchanged.

## Context difference or failed alignment?

A difference is explanatory Context only when all of the following hold:

1. a versioned contract assigns the unit `context_explanatory` for the relevant
   semantics;
2. the compared values come from validated structured authority with safe
   scope;
3. the difference does not change proposition identity, endpoint meaning,
   result meaning, intervention proposition, or experimental contrast; and
4. all upstream proposition and compatibility gates are independently
   satisfied.

A difference instead means the observations should not yet have been aligned
when it changes or leaves unresolved the asserted subject/relation/endpoint,
measurement target or endpoint type, result semantic level, proposition-defining
intervention, or another identity-affecting qualifier. If the current Alignment
contract does not consume an available Experimental Core fact, the deterministic
outcome is `alignment_semantic_coverage_gap`. If a versioned policy proves
incompatibility, the outcome may be
`scientifically_incompatible_under_current_contract`. Without such policy the
outcome remains reviewable; it is not inferred from differing strings.

Differences in design, control structure, assay, or evidence family that do not
alter proposition identity still require scientific compatibility when their
role is `comparison_compatibility_critical`. A descriptive no-arm observation
and an interventional arm contrast therefore cannot pass simply because both
designs are resolved.

## Alignment and Experimental Core coverage audit

Claim Alignment v2 currently consumes canonical subject identity, canonical
relation family, canonical endpoint identity, optional outcome-variable
identity, and bridge assessments for legacy measurement semantic level and
endpoint compartment. Its taxonomy names additional conditional semantics, but
the pairwise Alignment implementation does not consume Experimental Core's
measurement target, measurement endpoint type, result semantic level,
intervention proposition, evidence family, observation type, or experimental
contrast.

When those facts are available in Experimental Core, this candidate contract
records an Alignment semantic coverage gap. It does not expand Alignment's
historical signature and does not transfer proposition authority to L4b.

## Layer ownership

The preferred authority flow is:

```text
Claim Alignment / Qualification -> proposition compatibility
L4a                            -> descriptive Context Difference
L4b                            -> compatibility and Context sufficiency
Divergence                     -> explanation eligibility/evaluation
Formal                         -> consumes upstream results
```

The legacy five-consumer-by-eight-dimension matrix remains compatible for this
candidate iteration, but it is not treated as five independent scientific
requirement engines. L4a does not activate comparison requirements, Divergence
does not decide compatibility, and Formal does not invent requirements.

## Deterministic trigger projection

`PairSemanticTriggerProjectionV1` may materialize only an already validated,
two-sided structured fact whose role is `context_explanatory` and whose state is
`matched` or `different`. It uses no free text, fuzzy scientific inference, LLM,
or missingness inference.

Proposition-critical units are `not_required_after_role_audit` for L4b trigger
projection because their authority remains upstream. Compatibility-critical
units cannot be projected from raw values without a deterministic compatibility
result. Partial, ambiguous, or role-unresolved units remain explicitly
unprojected.

## Formal separation and non-goals

Scientific incompatibility is not Formal conflict. L4b may block comparison but
does not create, confirm, or modify a Formal Judgment. This contract does not
adjudicate f389/PI3K, create scientific bridges, repair entities, alter active
pointers, invoke providers, or modify any historical pair object.
