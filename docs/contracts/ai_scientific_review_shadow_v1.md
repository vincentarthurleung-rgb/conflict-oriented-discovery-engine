# AI-assisted scientific review and shadow discovery v1

Development scope is authorized by the project owner's 2026-10-17 instruction.
Human signatures are not required to explore. This contract grants no production
scientific authority and does not activate the future independent-human review
contract in the frozen `Atlas_review_integration_decision.md`.

Implementation: `code_engine.discovery.ai_review_shadow`.

An input binds exact evidence-packet bytes, source bytes, prompt bytes and, when
present, V3/Core file bytes and revision IDs. Original source offsets and text
hashes must match. Evidence references must resolve within that packet.

Each AI review has all nine fields exactly once: experimental scope, factor,
comparator, measurement/endpoint, observed result/direction, evidence linkage,
missing-method limitations, mechanistic overstatement and source support. Each
has SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED or UNCERTAIN, evidence references,
a reasoning summary and explicit uncertainty. There is no global PASS flag.

Reviewer provenance records model family, exact model ID if exposed, identity
basis/limitations, prompt version/hash, timestamp with timezone, input hashes and
canonical output/file hashes in an append-only receipt. The interactive session
does not expose an exact deployment ID; it must be null, not guessed. A review
sharing extraction/session context is not independent. A separately budgeted
model can add a diagnostic, never Human Gold. Hashes prove content identity only.

The namespace is `seen_development_shadow`; every review, alignment, context
comparison, hypothesis and budget artifact bears
`AI_PROVISIONAL_NOT_INDEPENDENTLY_VALIDATED`. Scientific authorization, Human Gold,
Strict Core eligibility and formal graph eligibility are always false. Outputs
are content-addressed under a separate `shadow/` directory with exclusive writes.
There is no formal promotion, Atlas annotation/Gold write or API client here.

Comparison uses explicit reviewed candidate labels and the existing
`evaluate_claim_comparability` weak-comparison policy unchanged as a diagnostic.
Literal labels are not canonical equivalence. Alias/family scores cannot replace
an exact candidate analyte/endpoint/measurement/factor label check. Dose, time,
cell system, baseline and other context remain explicit; matching factor labels
do not establish intervention equivalence. Unknown measurement classification
remains unknown. A partial/uncertain review is exposed field by field.

Opposition requires positive versus negative observed directions; a reported
non-increase, non-significance or unknown result is not negative. A provisional
contradiction also requires supported critical fields, compatible candidate
facets/design and the unchanged weak-comparison diagnostic. Context attribution
lists candidate modifiers; it does not establish explanatory power or mediation.
Only sufficiently supported provisional opposition with a context difference
can produce a provisional, falsifiable modifier hypothesis with both evidence
sets, directional predictions and a rejection test. Zero is a valid result.

Formal input handoff rejects explicitly marked shadow objects before conversion.
The shared direct core gate rejects shadow provenance even inside wrappers and
despite injected authority flags. Existing native authorization checks remain
rejection-only and unchanged for unmarked native records. Tests cover these
entry paths; they do not claim cryptographic authenticity for arbitrarily forged
records with every provenance marker deliberately removed.

No model inference is launched by this module. Call planning reuses the local
token estimator, reports output-token caps, and leaves total cost unpriced unless
both input and output rates are provided. Input-only historical prices cannot
be advertised as total reviewer costs. Model, complete pricing and a separate
execution budget must be approved before any API execution elsewhere.
