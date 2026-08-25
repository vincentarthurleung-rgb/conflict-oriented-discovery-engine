# L4b Pair Comparability Semantics v1

Status: **Accepted for the V2 pair-requirement sidecars and the L4b v1 result**  
Contract identity: `l4b_pair_comparability_semantics_v1`  
Implementation: `src/code_engine/extraction_assets/context/pair_requirements_v2.py`

## Scientific unit and question

The scientific unit is one already aligned, contradiction-bearing, candidate-qualified
pair of experimental observations. L4b asks:

> For an already aligned and candidate-qualified pair of experimental
> observations, do we have sufficiently resolved decision-relevant context to
> interpret their agreement or divergence?

This is a knowledge-sufficiency judgment. It is not a demand that the two
experiments have identical Context.

## Preconditions

An authoritative L4b evaluation requires all of the following upstream facts:

1. Scientific Entity Integrity is eligible for both endpoints and their
   proposition-critical entities.
2. Claim Alignment is eligible (`aligned`, or an equivalent accepted state).
3. the Contradiction Signal is structurally valid, provenance-complete, and
   validated;
4. Candidate Qualification is eligible (`qualified`, or an equivalent accepted
   state).

The precondition gate runs before Context satisfaction. A failed entity gate,
alignment, contradiction signal, or candidate qualification produces the
corresponding `blocked_upstream_*` state. L4b must not continue as though the
pair passed. Historical and diagnostic Context artifacts remain readable but
cannot substitute for an eligible upstream result or become authoritative L4b
evidence.

## Requirement semantics

`comparison_required` means **required to be resolved**, not **required to
match**. For each pair `p`, let `R(p)` be the dimensions whose primary role is
`comparison_required`. The Context condition for comparability is:

```text
for every d in R(p): resolved_for_comparison(d, p) == true
```

Consequently, known `WT` versus known `KO` can satisfy an activated genotype
requirement and yield `comparable_with_context_divergence`. Known `WT` versus
unknown genotype cannot satisfy that requirement. Neither a Context difference
nor a Context match is itself a complete comparability decision.

Each dimension has exactly one primary decision role for a pair and consumer:

- `comparison_required`: unresolved evidence prevents authoritative positive
  comparability.
- `divergence_explanatory`: does not itself block comparability; a supported,
  resolved difference may be handed to the downstream explanation layer.
- `not_decision_relevant`: the dimension is represented but no validated trigger
  makes it relevant to this pair and consumer.
- `requirement_unresolved`: structured semantics establish a possible decision
  role, but the versioned contract cannot deterministically choose that role.

`comparison_required` may carry `divergence_explanatory` as a secondary role.
The primary role remains unique.

## Pair-level activation

Activation is pair-specific and may use only validated structured facts from
these trigger families:

- `proposition_scope`: the aligned proposition explicitly depends on the
  dimension;
- `experimental_factor_scope`: a validated Factor or Arm structure directly
  relevant to the compared intervention/effect uses the dimension;
- `measurement_result_scope`: measurement or result semantics explicitly depend
  on the dimension;
- `evidence_family_scope`: the validated evidence family structurally requires
  the dimension;
- `source_grounded_pair_difference`: an authoritative difference exists and the
  consumer contract explicitly permits a comparison or explanatory role;
- `comparison_structure`: comparator, reference, group, or baseline structure
  explicitly requires the dimension.

Every activating fact names its consumer, role, source contract, source code or
artifact reference, and a structured evidence payload. A fact that is not
structurally established cannot activate a role. Conflicting established roles
produce `requirement_unresolved`; they are not silently prioritized.

Activation must not use biomedical custom, field presence, field absence,
provider/LLM intuition, free text alone, case names, task IDs, publication IDs,
pair IDs as policy selectors, reference answers, or human adjudication answers.
In particular, missing dose does not make dose relevant: independent structured
semantics must activate intervention/dose first.

The five audited consumers retain separate authority:

- Claim Qualification may consume only a proposition-identity contract; it is
  not a duplicate Context engine.
- L4a is descriptive and does not activate comparability requirements.
- L4b owns comparison requirements.
- Divergence Explanatory Power may consume only dimensions explicitly eligible
  for explanatory consideration.
- Formal Judgment consumes upstream results and does not invent a Context
  requirement without a separately versioned explicit formal contract.

## Dimension registry

V2 reuses the existing authoritative eight-dimension registry and its 19 active
field mappings; registry membership never activates a requirement:

| Dimension | Existing mapped Context fields |
|---|---|
| `biological_model` | `species`, `tissue`, `cell_type`, `cell_line`, `model_system`, `in_vitro_in_vivo_ex_vivo` |
| `intervention` | `intervention`, `dose`, `experimental_arm` |
| `temporal` | `duration`, `timepoint` |
| `genotype` | `genotype` |
| `localization` | `subcellular_localization` |
| `measurement` | `assay`, `measurement_method`, `measured_endpoint` |
| `disease` | `disease` |
| `experimental_design` | `control`, `comparator` |

This implementation does not create a population/cohort dimension alongside
the registry. A future registry version must add and map that semantic family
before it can be activated.

## Dimension states and resolution

One pair/dimension state is selected deterministically:

- `matched`
- `different`
- `unresolved_a`, `unresolved_b`, `unresolved_both`
- `ambiguous_a`, `ambiguous_b`, `ambiguous_both`
- `source_scope_insufficient_a`, `source_scope_insufficient_b`,
  `source_scope_insufficient_both`
- `not_reported_a`, `not_reported_b`, `not_reported_both`
- `not_applicable`
- `no_supported_value`

`matched` and `different` are `resolved_for_comparison` only when both values
are supported by one of these authorities:

- validated, source-grounded evidence;
- deterministic inheritance whose source and target scopes were validated as
  safe under the field propagation policy;
- an authorized deterministic derived value with its versioned rule identity.

All `unresolved_*`, `ambiguous_*`, and `source_scope_insufficient_*` states are
unresolved. `no_supported_value` is unresolved. `not_applicable` satisfies no
activated requirement unless the activating contract itself explicitly defines
non-applicability; v1 has no such rule.

`not_reported_*` is valid only when the relevant source scope was adequately
inspected. It is still an unresolved required Context gap in v1. Inadequate
scope must use `source_scope_insufficient_*`, never `not_reported_*`.

## Source adequacy and exact failure policy

For an activated `comparison_required` dimension:

- adequate source scope plus `not_reported_*` ->
  `reviewable_required_context_gap`;
- extraction or normalization unresolved ->
  `reviewable_required_context_gap`;
- competing source-supported values (`ambiguous_*`) ->
  `blocked_required_context_ambiguous`;
- inadequate or wrong source scope (`source_scope_insufficient_*`) ->
  `blocked_source_scope`.

Wrong-scope inheritance cannot satisfy a requirement. In particular, Context
cannot cross unrelated arms, experiments, cohorts, timepoints, or doses.

## L4b result states

After upstream eligibility succeeds:

- no activated Context-sensitive role ->
  `comparable_no_context_sensitive_requirement`;
- all comparison-required dimensions resolved and no decision-relevant
  difference -> `comparable_all_required_context_resolved`;
- all comparison-required dimensions resolved and at least one resolved,
  decision-relevant difference -> `comparable_with_context_divergence`;
- unresolved role semantics -> `reviewable_requirement_semantics_unresolved`;
- unresolved or adequately-not-reported required Context ->
  `reviewable_required_context_gap`;
- ambiguous required Context -> `blocked_required_context_ambiguous`;
- inadequate required source scope -> `blocked_source_scope`.

The upstream states are `blocked_upstream_entity_integrity`,
`blocked_upstream_alignment`, `blocked_upstream_contradiction_signal`, and
`blocked_upstream_candidate_qualification`. `not_applicable` is reserved for an
explicitly out-of-scope L4b request, not for an upstream failure.

`comparable_with_context_divergence` is positive comparability. It means the
observations can be compared while interpretation retains a resolved Context
difference.

## Layer separation

### L4a Context Difference

L4a asks what is matched, different, unresolved, or ambiguous. It is descriptive
and does not block merely because a dimension is absent. Its output may supply
the evidence facts consumed by L4b. L4a does not decide comparability.

### Divergence Explanatory Power

L4b may emit `resolved_context_difference_candidates`. Each candidate contains
the dimension, both values and provenances, `difference_status`, requirement
role, and deterministic eligibility for downstream explanation. Only a
source-grounded, resolved `different` dimension whose role permits explanatory
consideration is eligible. This handoff never states or implies that the
difference explains the result divergence. Unresolved evidence and provider/LLM
claims cannot enter the handoff.

### L4c Formal Judgment

L4c asks whether residual unresolved conflict remains after alignment,
contradiction, comparability, and any validated Context explanation. L4b neither
creates a formal conflict nor confirms residual conflict. Formal Judgment must
consume L4b and must not derive new Context requirements on its own.

## Fail-closed behavior

Unknown upstream eligibility, unsupported values, unresolved normalization,
ambiguous values, inadequate source scope, conflicting trigger roles, missing
contract identity, invalid inheritance, or provider-only/LLM-only activation
cannot silently produce authoritative comparability. Invalid contract payloads
are rejected; scientifically unresolved valid payloads receive the reviewable or
blocked state defined above.

## Examples and counterexamples

- Required genotype, `WT` vs `WT`: resolved matched; comparable.
- Required genotype, `WT` vs `KO`: resolved different;
  `comparable_with_context_divergence`.
- Required genotype, `WT` vs unknown: unresolved required gap; not
  authoritatively comparable.
- Genotype differs but has role `not_decision_relevant`: it does not block.
- Missing timepoint without a temporal trigger: no temporal requirement.
- Required timepoint with one unresolved side: required Context gap.
- Localization-specific proposition with supported different compartments:
  resolved difference.
- Different localization without a localization-sensitive trigger: no automatic
  requirement and no automatic explanation.
- Context from an unrelated cohort cannot satisfy a population/cohort contract;
  the current registry additionally cannot activate an unmapped cohort
  dimension.
- A control from an unrelated arm cannot satisfy an experimental-design
  requirement.

Counterexamples prohibited by this contract include: all Context present
therefore comparable; one field missing therefore incomparable; any difference
therefore incomparable; any match therefore comparable; a missing field
therefore required; explanatory eligibility therefore comparison-required; a
required difference therefore causal explanation; L4a or L4b therefore Formal
conflict; and an LLM assertion therefore activation.

## Non-goals

This contract does not define generic biomedical requirements, rename the
registry, establish proposition alignment, re-adjudicate intervention identity,
infer causal explanation, aggregate explanatory factors, create scientific
bridges, resolve entity identities, modify Candidate/Alignment/Formal objects,
or adjudicate manual scientific-review boundaries.
