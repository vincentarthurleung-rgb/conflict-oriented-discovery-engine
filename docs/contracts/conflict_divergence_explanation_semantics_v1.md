# Conflict Divergence Explanation Semantic Contract v1

Status: **Proposed**

Runtime activation: **false**

This L4b contract asks whether a validated context difference can explain a
validated contradiction signal. It is independent from factor comparability:

`comparability_effect ≠ divergence_explanatory_effect`

No mapping between severity and explanatory effect is authorized.

## Proposed effects

### `not_explanatory`

After an explicit, policy- or adjudication-backed assessment, there is no
evidence that the factor difference sufficiently explains the observed result
divergence. It does not mean the factor is the same, unimportant, or a default.

### `potentially_explanatory`

Auditable mechanistic or experimental-design evidence indicates that the
difference may contribute to the divergence, but it does not independently
resolve the conflict question.

### `sufficiently_explanatory`

Versioned and auditable authority supports classifying the current pair as
context-explained divergence rather than formal conflict.

### `insufficient_information`

Available evidence cannot establish explanatory effect. It must retain a null
effect and must not default to `not_explanatory`.

## Authority

An assessed effect requires an activated versioned explanation policy or
provenance-complete adjudication. Raw Provider pair output, comparability
severity, free text, factor names, and missing-value shape are not authority.

All scientific examples under this contract have:

- `non_normative=true`
- `requires_domain_policy=true`
- `deterministic_derivation_authorized=false`

No example activates semantics or adjudicates an existing pair.
