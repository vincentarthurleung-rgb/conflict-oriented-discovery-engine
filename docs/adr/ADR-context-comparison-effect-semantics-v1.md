# ADR: Context Comparison Effect Semantics v1

- Status: **Proposed**
- Decision scope: semantic contract and adjudication envelope only

## Context

The runtime v3 comparison factor stores `none`, `minor`, `major`, `blocking`, and `unknown` in one effect enum. The provider prompt does not define the missing-status/effect relationship, while the deterministic validator rejects missing factors marked `none`. This leaves epistemic uncertainty mixed with severity and makes `none` ambiguous.

## Existing inconsistency

Schema membership permits missing + `none`; deterministic validation rejects it. The ebd5 paid payload demonstrates the gap for `measurement_method` and `species`, but this ADR does not resolve those factors.

## Decision drivers

Semantic clarity, separation of epistemic state from severity, deterministic validation, auditability, fail-closed formal-conflict behavior, cross-domain portability, provider neutrality, backward compatibility, and migration risk.

## Model A

Retain the single enum. This maximizes compatibility but cannot distinguish “assessed with no effect” from “not assessed”, and leaves `unknown` as a pseudo-severity.

## Model B

Add an epistemic `effect_assessment_status` (`assessed`, `unknown`, `not_applicable`) and make severity (`none`, `minor`, `major`, `blocking`) nullable. This cleanly expresses assessed/no-effect versus insufficient evidence.

## Model C

Derive effect from comparison status. This incorrectly equates missing values with a scientific effect assessment and shifts scientific authority into unapproved code.

## Recommended architecture

Model B is recommended, subject to human approval. The contract remains Proposed and is not implemented in runtime.

## Why Model B

It is the smallest semantically complete model: `assessed + none` is distinct from `unknown + null`, local invariants are machine-checkable, and unresolved scientific judgment remains visible.

## Backward compatibility

Existing v3 payloads lack assessment status. No legacy `none` is automatically migrated to `unknown`, and legacy `unknown` is not treated as severity in the new model. A future migration needs an explicit versioned adapter and approval.

## Migration risks

Historical `none` may mean either an assessment or a default. Inferring which meaning applies would fabricate scientific provenance. Consumers may also currently treat `unknown` as an enum severity or assume implicit mappings.

## Human adjudication

When no deterministic versioned policy applies, independent reviewers and an adjudicator may produce a provenance-complete factor decision without changing the provider payload.

## Formal conflict safety

Provider suggestions are not formal-conflict authority. Pending, unknown, and blocking states cannot confirm formal conflict. Only validated policy-derived or fully adjudicated effects may reach a future gate.

## Multi-factor aggregation non-decision

`multi_factor_aggregation_decidable=false`. Beyond recording the existing blocking priority behavior, this ADR authorizes no max-severity, voting, weighting, or interaction algorithm.

## Open questions

When is `different + none` scientifically valid? When may `missing_both` support blocking? How should `not_applicable` affect formal eligibility? Which factor-specific thresholds and aggregation policy are defensible?

## Approval requirements

Domain-policy owners, comparison-contract owners, validation owners, and formal-conflict gate owners must approve before acceptance or runtime migration.

## Explicit non-decisions

- Do not adjudicate ebd5.
- Do not automatically migrate legacy `none` to `unknown`.
- Do not map missing values to `unknown`.
- Do not decide that `different + none` is always valid.
- Do not decide that `missing_both` is blocking.
- Do not add factor-specific severity policy.
- Do not implement max-severity aggregation.
- Do not modify runtime.
- Do not create pair attribution, gate, or handoff.
- Do not activate Atlas or change an active pointer.
