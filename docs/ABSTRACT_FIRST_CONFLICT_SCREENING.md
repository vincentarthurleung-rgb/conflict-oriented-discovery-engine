# Abstract-First Conflict Screening

## Candidate Semantics

Abstract claims are normalized by L2 and grouped by canonical subject/object,
`relation_family`, and `polarity_type`. Shannon entropy is computed over the
normalized direction distribution. Unknown directions are counted separately;
`no_effect` is configurable. Each paper contributes at most one directional
vote per group, preventing duplicate claims from overweighting one paper.

Ambiguous, unresolved, and low-confidence L2 observations are excluded from
the candidate set and reported as excluded counts. Abstract entropy therefore
produces `abstract_conflict_signal`, not a final L3 conflict.

## Three Entropy Levels

1. Abstract entropy screens broad claim-level disagreement.
2. Full-text entropy uses only selected, traceable full-text evidence.
3. Context-conditioned entropy groups full-text evidence by available context
   slots. A substantial entropy drop after conditioning is labeled
   `context_resolved_conflict`.

Insufficient full-text coverage remains `insufficient_fulltext_coverage`.
Absence of full text does not make an abstract signal false. The original L3
conflict formula and thresholds remain unchanged; this confirmation layer is a
separate upstream/downstream evidence-quality boundary.
