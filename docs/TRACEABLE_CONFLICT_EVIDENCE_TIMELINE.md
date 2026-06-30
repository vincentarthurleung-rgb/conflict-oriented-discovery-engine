# Traceable Conflict Evidence Timeline

This module does not decide whether a scientific conflict is resolved. It creates a paper-level, time-ordered evidence chain and leaves the decision to a researcher. A deterministic implementation is used because an LLM verdict would add an untraceable semantic adjudication step.

## Windows

The conflict source window is the highest-entropy qualifying sliding window (then highest paper count, then earliest). Directions are deduplicated per paper. The later evidence window contains evidence for the same conflict key after that window, capped at five years by default. Sparse later literature indicates insufficient activity, never resolution.

## Statuses

Statuses are `persistent_conflict`, `emerging_conflict`, `conflict_with_later_explanation_evidence`, `recent_consensus_signal`, `context_partition_supported`, `stale_unresolved_conflict`, `abandoned_or_understudied_conflict`, `insufficient_later_evidence`, and `uncertain_temporal_evidence_status`. None is a scientific resolution verdict; every timeline has `system_judgment = non_decisive` and `human_review_required = true`.

## Outputs and comparison

Each evidence row includes year, role, direction, paper/DOI/title/journal provenance, context or mechanism links, and its evidence span. Retained system hypotheses are displayed beside later evidence and classified deterministically as covered, partially covered, extending, diverging, unavailable, or uncertain. Hypotheses are never deleted or marked invalid.

## Time-gated analysis

With `timeline_cutoff_year`, evidence after the cutoff is excluded and reported in `excluded_future_evidence_count` and `excluded_future_paper_ids`. Timeline construction runs after hypothesis formation and never feeds back into it. External validation artifacts are not inputs.

## Limitations

- A recent consensus signal is not proof.
- Lack of recent literature is not resolution.
- Human review is always required.
- External validation signals are not used.
- No LLM-based semantic resolution judgment is made.
