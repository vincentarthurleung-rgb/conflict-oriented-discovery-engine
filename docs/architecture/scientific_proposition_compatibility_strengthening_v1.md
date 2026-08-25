# Scientific Proposition Compatibility Strengthening v1

Status: candidate-only additive Claim Alignment contract
Implementation: `src/code_engine/context_attribution/claim_alignment/scientific_proposition_v1_candidate.py`

## Scientific proposition

A scientific proposition is the validated subject–relation–object claim plus
the proposition-defining measurement target, measured property or endpoint,
result semantic level, intervention proposition, causal/evidential mode,
scientific contrast role, and explicit granularity qualifiers. Compatibility
asks whether two observations make claims about the same effect at a compatible
semantic level. It is evaluated before Context comparability.

Direction, sign, polarity, and negation are excluded from proposition identity.
They remain inputs to Contradiction Signal. Opposite results can therefore be
aligned when every proposition-defining semantic is compatible.

## Structured authority and failure policy

`ScientificPropositionSignatureV1` is projected only from validated Claim
Alignment v2 proposition-core fields and immutable Experimental Core revision,
factor, measurement, and result records. The projector uses controlled enum
maps for measurement property, result representation, causal/evidential mode,
intervention role, and contrast role.

Canonical identity equality may establish an exact match. Distinct validated
canonical identities may establish a mismatch. Extracted-only text, lexical
overlap, topic similarity, publication identity, and pathway relatedness cannot
establish identity or incompatibility. Unknown controlled values remain
unresolved. There is no fuzzy ontology matching, free-text scientific
inference, LLM use, or case-specific rule.

## Target, endpoint, assay, and result semantics

`MeasurementPropositionCompatibilityV1` separates:

- measurement target;
- measured property or endpoint;
- result semantic family and representation;
- assay or method; and
- unit or representation.

Target, endpoint, and result semantic level are proposition-critical. Assay and
unit are compatibility qualifiers unless separate structured authority states
that they change the measured property. Consequently, different methods do not
by themselves create a proposition mismatch. Distinct result families are not
collapsed merely because they concern the same entity.

## Intervention, causal mode, and contrast

Intervention mode distinguishes none, single intervention, combination, and
unresolved structure. Factor roles project only narrow controlled families.
A generic intervention role and a more specific role require review rather
than being declared incompatible without granularity authority.

Observation type deterministically distinguishes descriptive observation,
observational association, interventional effect, and non-experimental
evidence. Cross-family claims are not silently treated as the same proposition.

Contrast compatibility uses semantic roles derived from validated comparison
and baseline links. Reference labels and exact Arm IDs are not proposition
identity, so different labels can remain compatible when their contrast roles
match.

## Semantic roles and layer ownership

Every audited unit is assigned one of:

- `proposition_critical`;
- `compatibility_qualifier`;
- `context_only`;
- `not_applicable`; or
- `semantic_role_unresolved`.

Species, genotype, time, localization, disease state, dose, and cohort remain
ordinary explanatory Context unless a validated Claim qualifier explicitly
scopes the proposition to that dimension. Endpoint compartment is one such
explicit scope. A generic Context difference cannot be promoted upstream.

Layer ownership remains:

```text
Claim Alignment -> proposition and scientific semantic compatibility
L4a             -> descriptive Context Difference
L4b             -> sufficiency of resolved decision-relevant Context
Divergence      -> explanatory power of eligible Context differences
Formal          -> residual conflict adjudication
```

L4b may consume an aligned V3 candidate state but cannot repair measurement,
endpoint, result, intervention, causal-mode, contrast, or granularity gaps.

## Candidate decision policy

Exact and versioned semantic-family compatibility can yield `aligned_exact`,
`aligned_compatible`, or `aligned_with_granularity_qualification`. Missing or
unresolved proposition authority yields `partial_reviewable`. A blocked state
requires structured deterministic mismatch authority. Historical Alignment v2,
Candidate Qualification, L4, Divergence, and Formal records remain immutable;
all V3 outputs are sidecars and read-only eligibility replays.
