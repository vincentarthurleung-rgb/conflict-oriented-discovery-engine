# AI-provisional Atlas review package v1

`code_engine.discovery.pilot_acceptance` exports portable, hash-bound original
packet/source/Core/review/prompt bytes and a recomputed Shadow alignment. The
case identity, two publication identities, source anchors, revisions, field
judgments, missing information, model provenance, native alignment state and
reported terminal state remain available. Hashes establish content identity,
not scientific truth. The portable v1 supports frozen article JSON sources;
JATS paragraph projections are rejected until their XML chain is packaged.

`tools/export_ai_provisional_review_package.py` requires `--case-id`, two
`--packet`, `--review` and `--core` paths, `--prompt`, and a new `--output-root`.
It writes a package and `manual_review_queue.jsonl`; it never publishes or calls
a model. Current v1 requires two bound source records. A missing-review/Core
attempt may be screened and retained as a terminal report, but cannot yet be
exported as this two-source Atlas item.

Atlas maps `ai_provisional_experimental_package` to the dedicated field-review
schema. Import verifies the complete package and queue identity. Production
namespace import is disabled. Existing roles, assignments, guideline
acknowledgements, annotation revisions and audit events are reused. Every save
revalidates stored package identity and binds the exact package SHA-256 on the
server; reviewers cannot replace that binding. Fields have `gold_field=false`.
A submitted response grants no scientific authorization, Strict Core or Gold.
Closed assignments retain existing write-rejection behavior.

The UI shows exact source text, experimental scope, AI field judgments,
uncertainty, context differences, model provenance and hypotheses separately
from the human response form. Staging test identities and responses are software
fixtures, never independent scientific review. Live activation requires owner
authorization under the existing Atlas process.

The terminal adapter preserves the native Shadow state and reports exactly:
NOT_EVALUABLE, INSUFFICIENT_EVIDENCE, NOT_SUFFICIENTLY_COMPARABLE,
NO_CONTRADICTION_AFTER_COMPARISON, or PROVISIONAL_CONTRADICTION.
Unknown/inconsistent native states raise; no production scientific gate or
threshold is changed. Synthetic software branch controls cannot be imported as
real review evidence.
