# Conflict Comparability Effect Adjudication Contract v1

Status: **Proposed**

Schema version: `conflict_comparability_effect_adjudication_v1`

The machine-readable authority is
`conflict_comparability_effect_adjudication_v1.schema.json`. Each decision is
factor-scoped and retains immutable source provenance. Provider payloads are
evidence, never edited adjudication records.

## Workflow

1. Packet construction verifies pair, endpoints, extraction identities, request identity, provider-execution identity, canonical payload hash, adapter hash, anchors, and factor values.
2. Two reviewers receive independent pending forms with no recommended or preselected answer.
3. Each reviewer selects an assessment state and, only for `assessed`, a severity. They provide rationale and identity.
4. An adjudicator acts only after the two review decisions are available. Disagreement fields and decision hashes are recorded without rewriting reviewer records.
5. A superseding decision links the earlier adjudication. A superseded record cannot remain active.

## State requirements

- `pending`: assessment, effect, class, and eligibility are `null`; rationale is empty. Blank reviewer identity is allowed.
- `adjudicated + assessed`: effect is `none`, `minor`, `major`, or `blocking`; rationale and reviewer identity are non-empty; eligibility is boolean.
- `adjudicated + unknown`: effect is `null`; eligibility is `false`; rationale and reviewer identity are non-empty.
- `adjudicated + not_applicable`: effect is `null`; rationale and reviewer identity are non-empty. Scientific eligibility treatment remains a policy question.
- `blocking`: eligibility is `false`.

Every record asserts `source_artifacts_verified=true`, `source_payload_modified=false`, `provider_called=false`, and `credential_read=false`.

## Independence and scientific neutrality

Reviewer forms do not display the other reviewer’s answer, a gold answer, a system expectation, an option ranking, or a recommendation. Contract-representable options are not claims of scientific correctness.

## Authority and activation

An adjudication does not itself create a formal pair attribution, gate, handoff, or Atlas activation. Downstream use requires a separate approved policy and explicit activation workflow.
