# Pilot completion dependencies and raw-response reuse v1

Scope: Recovery Batch 1. No scientific gate, frozen Builder/Quality prompt,
canonical identity, review approval or historical package is changed.

## Completion identity

`pilot_dependencies.effective_dependencies` maintains a bounded, explicit file
list grouped by the current executor's scientific processing stages. It covers
prompt compilation/routing, source windows, V3 schemas/parser/hydration, native
Core and linkage contracts, semantic registries, projection/admission, AI review
binding, Shadow comparison/context and dataset/package implementations. Runtime
versions, provider/model configuration, effective review-prompt **content**, frozen
construction contracts, catalog identity and checked annotation pins are bound.
Versions embedded in those files are content-bound even if a version string was
not manually incremented. Missing dependencies fail rather than hash as empty.

Each new case writes `effective_dependencies.json`; its digest participates in
the completion fingerprint and run manifest. Reusing an old case directory after
dependency drift raises `case_identity_input_drift` before a completed package is
returned. Use a new immutable revision/output directory, retaining the old
package, and explicitly share the same model-cache directory. `resume_partial`
does not override dependency drift. There is no automatic historical rewrite.

This manifest is an explicit maintenance contract, not a claim to hash every
repository file or external service. A newly connected scientific stage must add
its effective dependencies. Dormant L4/L5 paths are not activated by listing
current Shadow dependencies. Model aliases remain aliases; future execution must
record and verify the actual returned model.

## Two cache layers

The concrete backend separates `prepare_model_request`, `dispatch_raw`,
`response_usage` and `derive_response`. `complete` remains their compatibility
wrapper. Pilot raw cache entries (`raw_v1_*`) bind the provider endpoint, exact
canonical UTF-8 body digest and fixture namespace. They preserve the raw provider
JSON, exact request, original usage and request identity. Parser, assembler,
projection, review binding, dependency manifest and prices are not raw request
identity. A cache hit re-runs current derivation and records zero new charge.

Raw responses are durably captured before settlement or derivation. Only verified
settlement creates a reusable entry. Unverifiable usage retains both captured
response and pending dispatch. A changed scientific dependency can therefore
invalidate a completed package while reusing an unchanged, settled request.
Historical derived-only entries are not silently relabeled as raw responses.
Importing them would need exact request/response/receipt verification; this batch
does not perform such a migration.

## Unknown dispatches and retries

Timeouts and uncertain transport failures stop after one dispatch and retain the
full reservation and pending marker. They do not automatically retry. An explicit
HTTP 429 rejection can use the second reserved attempt; 5xx responses are treated
as uncertain. The budget still conservatively retains the first reservation.
Legacy pending markers without recoverable exact request identity block new raw
dispatch until explicit reconciliation. No reconciliation or spend authority is
granted by this contract. The maximum allowed attempts remains two.

## Component preparation

The existing routed V3 helper and concrete backend compile the same body. Probe
files contain canonical bytes without a final newline, so the body-file SHA-256
equals the transport-byte SHA-256. A local injected callback tests the actual
transport serializer without any socket or model request.

Conditional linkage preparation now requires the original `TrustedDraftContextV3`
and replays the existing parser/hydrator against the retained response. It checks
source/block hashes and an exact formal-observation match, then the existing
native schema, reference and source-anchor validators. A manual completed Core
file cannot substitute for a model response. This check is provenance/structure,
not independent scientific approval or cryptographic provider-origin attestation.

The future linkage request has no body/hash until genuine eligible V3 output
exists. Full retry ceilings are reserved; actual dispatch still requires owner
authorization and a new pricing check. All scientific authority remains false.
