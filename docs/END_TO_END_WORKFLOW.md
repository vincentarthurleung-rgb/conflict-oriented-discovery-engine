# End-to-End Workflow

`python -m code_engine.cli.run` is the recommended package entry point for this research MVP. Stage scripts remain available as legacy and debugging entry points.

The default is a local dry run with API and network access disabled:

```bash
python -m code_engine.cli.run \
  --query "我想了解一下当前氯胺酮在抑郁症中的作用" \
  --dry-run --no-api --no-network --until report
```

This no-API mode is fully operational but semantically degraded. The Scientific Encoder is the primary natural-language path when `--execute --api` is explicit. Low-confidence execute runs stop after intake unless `--allow-uncertain-intake` is supplied; dry-runs continue to a sanitized search plan.

Execution and external access are independent permissions. `--execute` never enables API or network access. Use `--execute --api` for configured LLM extraction or `--execute --network` for configured literature acquisition. Resume is also deny-by-default:

```bash
python -m code_engine.cli.run --resume runs/<run_id> --execute --until report
```

Progressive steps are `abstract_l1`, `l2_abstract`,
`abstract_conflict_screening`, `fulltext_escalation`, `fulltext_l1`,
`l2_fulltext`, and `fulltext_conflict_confirmation`. The compatibility steps
`l1`, `l1_5`, `l2`, and the original `conflict` remain available. DomainProfile
metadata is carried from intake into search, L1 planning, normalization policy,
MechanismGraph, and validation planning. User-intent seed triples are
search-planning inputs with `is_evidence=false`; they are never EvidenceRecords,
mechanism edges, or conflict-graph observations.

The mechanism step builds a run-scoped evidence-grounded graph when L2 observations exist. Conflict discovery continues to run independently with its existing formulas, then maps its already-adjudicated ConflictEdges onto mechanism edges. The current Stage6 adapter consumes only run metadata and honestly remains planned/blocked until a safe run-scoped search callable exists.

The L2 step runs EntityResolutionHub and writes candidate, decision, and aggregate audit artifacts. External lookup and LLM proposing have separate opt-in flags beneath the global execute/network/API guards. No external entity service is called by default.

LLMs and scientific encoders encode candidate structure. Deterministic modules adjudicate normalization, conflicts, ranking, and coverage. ValidationRouter selects validators; validators produce validation results. A partial report with blocked steps is a normal reproducibility artifact, not necessarily a failed run.
# Progressive Evidence Path

The preferred large-scale path is `abstract_l1 -> l2_abstract ->
abstract_conflict_screening`. With explicit full-text escalation it continues
through conflict-focused paper selection, deterministic section/span ranking,
`fulltext_l1`, `l2_fulltext`, and full-text conflict confirmation. Abstract
signals cannot enter the high-confidence MechanismGraph. Legacy L1/L1.5/L2/L3
steps remain available with `--l1-mode legacy`.

All L1 work is cache- and budget-guarded. Full-text extraction is targeted, and
no full text is represented as a coverage gap rather than negative evidence.

The validation step internally performs anchor building, semantic question
building, capability routing, query planning, resource checks, streaming
evidence retrieval, signal construction, and conservative aggregation. Remote
validation is off by default and requires execute, network, and external
validation gates together.
# Run-scoped hypothesis formation

The mainline is `Conflict / Mechanism / Evidence → HypothesisCandidate → HypothesisHyperedge → ReasoningRecord → ValidationRequirements → Validation`. Hypothesis formation reads only current-run artifacts and never reads validation signals. It does not invoke legacy global Stage6. Abstract-only conflicts produce low-confidence follow-ups; confirmed full-text conflicts and mechanism paths can produce full-text- and mechanism-grounded hypotheses. No hypothesis input is a non-failing `no_input` outcome. See [the artifact contract](HYPOTHESIS_ARTIFACT_CONTRACT.md).
