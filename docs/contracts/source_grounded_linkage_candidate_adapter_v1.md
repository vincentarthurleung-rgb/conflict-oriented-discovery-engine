# Source-grounded linkage proposal adapter and component probe (development)

`experimental_core.linkage_candidates` consumes a newly assembled native V3/Core,
exact source block texts and an explicit `LinkProposalResponse`. It does not run
a model or discover links by proximity. `candidate_input` prepares exact endpoint
identities, experiment scope, source identities, source-file and block hashes,
and existing V3 spans. Optional controller-supplied related Results, caption and
Methods spans use `FormalEvidenceSpanV3`, exact block coordinates, text hashes,
and the same source-document identity. They stay in the sidecar, never silently
modify frozen V3. Source block text is controller input, never a model-supplied
replacement. Grouping/co-location does not establish scientific applicability.

The separately versioned `source_grounded_linkage_candidate_prompt_v1` requests
only explicit typed endpoints, evidence references, an explicit-support basis,
explanation and unresolved information. Empty proposals are valid. Provider
output cannot set authority, approvals, canonical identities or derived signs.
Exact references, endpoint types, observation/revision binding and evidence
integrity are checked by `produce_candidates`. This checks representation and
provenance; it cannot establish that a model's explanation is scientifically
correct. Candidate completeness means the proposed row has its required fields,
not that the experiment has complete scientific evidence or authorization.

Factor→measurement and result→comparator reuse the immutable
`SourceGroundedLinkageCandidateV1` contract in `repair_v1`. Every row retains
`authority_state=candidate`, no deterministic semantic grounding version, and is
rejected by the unchanged materializer. `explicit_source_semantics=true` records
the proposal's assertion of explicit support, not verified authority. All five
requested relation types, including result→baseline, measurement→result and
observation→experiment scope, use existing `ExperimentalObservationLinkage`
with `authority_status=candidate_only`. The old candidate enum is not extended.

`candidate_v2_diagnostic` runs the existing V2 metrics on a private hypothetical
candidate graph. It returns metrics only, not a promotable Core envelope. This
does not update original factors, result references, native Core, readiness,
Evidence Projection or production admission. A diagnostic `complete` is
explicitly distinct from original native V2 outcome and materialized authority.
Source-grounded AI judgments are permitted as development candidates; they are
never claimed to be original provider output or independent scientific review.

`fulltext.source_windows.grouped_plan_windows` packs consecutive intervals within
the first two source heading levels, under the existing bounded input size and
unchanged V3 token preflight (6000 estimated input tokens, figure-unit checks,
output/context reservation and observation bound). Planning partitions use exact
source sentence intervals when a region alone fails; unsplittable content stays
accounted and pending. The backend checks this frozen preflight again before
input reservation and provider dispatch. It cannot route an oversized legacy
whole-paper input around the guard.
It keeps original region identities, XML paths, source intervals and exact text.
Results/captions may share a source subsection; Methods protocol paragraphs may
share a parent heading. This asserts no common experiment or method applicability.
Each Construction paragraph preserves its fragment. V3 role prefixes and offsets
have an explicit per-fragment map. Cross-fragment evidence is split into actual
source intersections, retaining the parent block span/hash; inserted role labels
and separators are not presented as source evidence. The native backend verifies
all original source intervals before accepting this plan. Existing prompt,
schema, zero-candidate Quality handling and per-request context/budget gates stay.

The source-view helper also accepts a frozen `pmc-articleset` containing exactly
one article. XML paths keep this wrapper; multiple articles are rejected.
Text accounting remains separate from actual model processing, scientific
extraction completeness, images/external supplements, and scientific admission.

`orchestration.component_probe` only prepares requests. It has no sending or
credential-reading capability. Each V3 request body/file and source input/file
is hashed. Input reservation is canonical UTF-8 request bytes plus 1024 framing
tokens, a conservative engineering ceiling rather than a tokenizer measurement.
Reserve peak cache-miss input price, full output and two attempts per request;
assume no cache/off-peak discount. Existing V3 default output limit stays 32768.

At most one subsequent candidate request has a separate 40000 input / 8192 output
ceiling and two-attempt reservation. Its final endpoints/body/response hash cannot
be known before actual V3 output. After successful hydration, the conditional
binder checks the exact validated observation artifact and pins the provider
response separately, then renders a hash-bound proposed request. The caller must
preserve the hydration audit connecting those artifacts. Nonexperimental,
source-insufficient, empty, invalid or over-limit inputs stop this branch; no
extra anchor, experiment, retry or model output is fabricated to satisfy it.
Scientific support must be assessed from the actual response and frozen source;
structural eligibility alone does not establish it. No third live request is
represented as already frozen. This module never authorizes or sends any request.

An owner-authorized development component test does not require Strict Core,
Human Gold or formal causal authority. It may honestly return zero extraction,
invalid extraction or incomplete linkage; it grants none of those privileges.
