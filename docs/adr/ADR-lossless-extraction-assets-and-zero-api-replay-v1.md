# ADR: Lossless extraction assets and zero-API replay v1

Status: Accepted

## Decision

Source snapshots and provider raw bytes are immutable. Raw bytes are persisted
before parsing, and parsed candidates are separate immutable revisions. Parser,
schema, validation, or normalization failure does not authorize a provider
retry. New parsers create new revisions against the same raw response.

Field evidence preserves raw, extracted, and canonical values separately.
Value state is explicit; old nulls remain `legacy_null_unresolved`. Coverage and
replayability sidecars record losses without fabricating lineage. Re-extraction
is planning-only, block-deduplicated, selective, and has all execution
authorizations false.

## Consequences

Parser/schema/registry and derived-reasoning changes can preferentially replay
offline. Historical incompleteness remains visible. The facility serves
reproducibility, auditability, and billing safety only; it does not establish a
public dataset release, data-paper contribution, or any conflict-science rule.
# Historical forensic v2 note

The v1 decision remains unchanged. The accepted deterministic historical
lineage ADR adds fail-closed, one-to-one recovery and treats all v1
re-extraction requirements as a pre-forensic upper bound.
