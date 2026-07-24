# Conflict Comparability Effect Semantic Contract v1

Status: **Proposed**

This document defines a proposed L4b semantic contract. It does not change the
runtime schema, validate a scientific conclusion, or adjudicate any existing
pair. It is outside Observation Context (L2.5) and Context Difference (L4a),
and runtime activation remains false.

## Model B: separate epistemic state from severity

`effect_assessment_status` is one of:

- `assessed`: the effect of this factor on comparability was actually evaluated. `comparability_effect` must be one of `none`, `minor`, `major`, or `blocking`.
- `unknown`: available evidence is insufficient to judge the effect. `comparability_effect` must be `null`, and `formal_conflict_eligible` must be `false`. Unknown is epistemic state, not severity.
- `not_applicable`: the factor does not apply to the comparability question for this pair. `comparability_effect` must be `null`, and a non-empty rationale is required. It is not a placeholder for missing information.

No assessment status or effect may be derived merely from a missing value, a provider confidence, or a comparison status.

## Severity semantics

All severity definitions remain **Proposed** and require human approval before runtime adoption.

### `none`

The factor was actually assessed and explicitly judged not to reduce comparability between the observations.

Required: `effect_assessment_status=assessed`, `comparability_effect=none`, and a non-empty rationale.

Prohibited uses include unassessed state, uncertainty, missing information, absent provider output, a default, or a substitute for `null`. This contract does not assert that `same` always means `none`, nor that `different + none` is invalid.

### `minor`

After explicit assessment, a difference does not prevent direct comparison, but interpretation must retain a caveat.

### `major`

After explicit assessment, a difference means the comparison can only be interpreted conditionally and cannot be treated as an identical experimental context.

### `blocking`

After explicit assessment, a difference or absence of information means the pair cannot currently confirm a formal conflict. `formal_conflict_eligible` must be `false`.

## Legacy `unknown`

Runtime v3 currently includes `unknown` in a single effect enum. In Model B it is represented as `effect_assessment_status=unknown` with `comparability_effect=null`; it is not a severity. Legacy `unknown` is never silently migrated.

## Status and value invariants

The current statuses are `same`, `different`, `missing_a`, `missing_b`, and `missing_both`. Value states are `both_nonempty`, `a_null_b_nonempty`, `a_nonempty_b_null`, `both_null`, and `contains_empty_string`.

The proposed contract preserves current status/value consistency checks and rejects empty strings. Scientific effect is not deterministically derived from status/value shape. In particular, it does not authorize `same → none`, `missing → unknown`, `different → major`, or `missing_both → blocking`.

## Non-normative illustrations

“human vs mouse”, “in vitro vs in vivo”, and “Western blot vs immunoblotting” are illustrations only. For every such example:

- `illustrative_non_normative_example=true`
- `requires_domain_policy=true`
- `deterministic_derivation_authorized=false`

They are not cross-domain rules.

## Candidate comparability mapping

The following is a candidate mapping, not an implemented gate:

| Assessment and effect | Candidate class | Deterministically safe |
|---|---|---|
| assessed + none | comparable | no, pending approval |
| assessed + minor | unresolved candidate | no |
| assessed + major | conditionally_comparable | no |
| assessed + blocking | non_comparable | only the existing blocking gate fact is deterministic |
| unknown + null | insufficient_information | no |
| not_applicable + null | undecided | no |

Existing vocabulary also contains legacy `not_comparable` and internal `blocked`/`reviewable` states. No new aggregation algorithm is authorized. `multi_factor_aggregation_decidable=false`; the existing priority for a registered blocking effect is recorded as a fact, while max-severity aggregation is explicitly prohibited.

## Authority model

### Provider

May suggest status, values, effect, and reasoning. It is not final severity, comparability, or formal-conflict authority.

### Schema

Checks types, enums, status/value local consistency, and assessment/effect local consistency. It does not establish scientific correctness.

### Deterministic Validator

Checks contract consistency, policy identity, source integrity, and registered policy rules. It must not infer severity from free text, repair provider effect, or map missing values to `unknown`.

### Versioned policy

Only explicit, versioned rules supported across cases may deterministically derive an effect.

### Human adjudicator

May make a provenance-complete decision under the adjudication contract. The adjudicator does not modify the provider payload.

### Formal conflict gate

May consume only a validated policy-derived effect or an effect that passed the full human-adjudication gate.

## Formal-conflict safety

Pending, unknown, and blocking decisions cannot confirm formal conflict. A provider suggestion alone is ineligible. `not_applicable` remains unresolved for formal-conflict eligibility until approved policy defines its treatment.

## Open questions and non-decisions

`different + none`, `missing_both + blocking`, factor-specific thresholds, legacy migration, and multi-factor aggregation remain unresolved. This contract does not adjudicate ebd5, change runtime code, create a pair attribution, create a comparability gate or handoff, activate Atlas, change an active pointer, or call variational EM.
