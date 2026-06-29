# Run-scoped hypothesis formation

Hypothesis formation is a deterministic, run-local step. It reads only artifacts in the current run: full-text conflict confirmations, the mechanism graph, abstract conflict candidates/focus set, optional legacy conflict summaries, and L2 observations. It does not call the legacy global Stage6 pipeline, PyG, an LLM, remote APIs, or validation.

Confirmed full-text conflicts form full-text-grounded mechanism-conflict hypotheses. Context-resolved conflicts form context-partition hypotheses. Mechanism paths and unknown mechanism edges form pathway-bridge and mechanism-gap hypotheses. Abstract-only signals form low-confidence follow-ups that require full-text confirmation and manual review. Insufficient coverage forms an evidence-gap follow-up; missing evidence is not contradictory evidence. No usable input produces `no_input`, not workflow failure.

Scoring is deterministic and pre-validation. Validation requirements describe downstream checks and always have `status: not_run`. External validation remains conservative evidence gathering, not proof.

All JSONL inputs and outputs are processed line-by-line. Candidate output is bounded by `max_hypotheses` (default 50).
