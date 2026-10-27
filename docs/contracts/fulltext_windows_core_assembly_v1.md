# Complete-source windows and automatic V3 component assembly (development)

This supplements the existing pilot integration. Frozen JATS/BODY, Builder V4,
Quality V2, V3 prompts/schemas, Core schemas, linkage/readiness and scientific
admission policies are not edited. A new immutable derived source view records
XML paths and exact normalized Unicode coordinates. It is not a replacement for
raw JATS or the historical 60k canonical BODY.

`fulltext.source_windows.jats_source_view` traverses BODY and article abstracts;
existing excluded-section rules and structural-heading rules are named in its
dispositions. Figure/table text includes labels, captions and textual cells.
Unsupported text remains pending. Images, external supplements and OCR are not
acquired or interpreted. Each region retains XML/section/paragraph identity.
Normalization is the existing NFKC/whitespace rule; coordinates do not claim to
be byte offsets in the raw XML.

`plan_windows` creates stable bounded windows, prefers source text boundaries,
records exact overlap and does not delete separators or infer shared experiments.
The source view and historical BODY remain unchanged. `construction_window`
wraps each window in the existing validated ConstructionEvidenceDocumentV1.
V3 framing uses the existing CURRENT_RESULTS/LINKED_METHODS conventions; its
controller-added prefix is explicitly removed only in the source-coordinate
mapping. No frozen prompt or evidence text is edited.

The concrete backend and unified executor process multiple windows per source
and multiple V3 observations per response. Window request/result identities use
source/window keys; biological PMID/PMCID remain the actual paper identities.
Provider bodies, including prompt/schema overhead, are bounded before dispatch.
Existing budget/cache machinery owns reservation, retry and exact result reuse.
Completed window states persist before the next window; pending/failed ranges
remain visible on interruption. An unresolved dispatch cannot be charged again
by restart. Explicit continuation preserves the old terminal package.

Quality is not called for a zero-candidate window because its frozen input
cardinality is 1–3. This is not a fabricated Quality PASS. Source coverage treats
that stage as explicitly not applicable; missing extraction is still pending.
Malformed/rejected provider output and usage remain recorded. Byte/text coverage,
completed processing, accepted V3, complete Core and scientific authorization
are separate results. No coverage count proves complete scientific extraction.

`experimental_core.assembly.assemble_v3(formal, source_artifact=..., source_blocks=...)`
requires genuine structured V3 and actual block texts. It checks evidence hashes,
coordinates and references; reuses existing component models, type policy,
scalar measurement/result linkage, integrity, V2 linkage and readiness. It copies
raw information, preserves missing values, creates record identities only, and
sets no biological canonical IDs, effect sizes, units, causal signs or approvals.
V3 arm strings lacking their own anchors remain unanchored. No factor→measurement
or comparator edge follows from proximity, a shared scope or a unique candidate.

An explicitly supplied existing native Core can be validated/reused as such.
That mode is reported as reuse, never automatic recovery of absent links. Current
frozen V3 drafts cannot express all required explicit factor/comparator links.
A future model linkage candidate needs the existing source-grounded resolution
contract and its verification; the model must not assert validated authority.
Unknown registry types remain unresolved pending a separately authorized
scientific policy decision.

Reviewable incomplete native records remain exportable/projectable. Existing
machine-reuse readiness gates entry into Shadow pair alignment; an AI review
cannot substitute for the missing Core linkage. Gold, Strict Core and scientific
authorization stay false. The native per-window instances and exact dedup aliases
are retained in the existing dataset exporter; final observations are not counted
twice because they also occur in incomplete-output diagnostics. Atlas uses its
existing whole-attempt package for pending windows and component-only records;
no new UX or scientific review identity system is introduced.
