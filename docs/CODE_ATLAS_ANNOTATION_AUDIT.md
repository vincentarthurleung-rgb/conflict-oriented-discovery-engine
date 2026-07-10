# C.O.D.E. Atlas Annotation Audit

Formal annotation writes ignore frontend `reviewer_id`, username, and role. The backend binds annotations to the authenticated session identity. In `--no-auth` local development, writes are forced to the `test` namespace with the local developer identity.

Each create/update writes an append-only `annotation_events` row with previous revision, new revision, changed fields, a full snapshot, request id, salted IP hash, and salted session hash.

Optimistic locking uses `expected_revision`; stale writes return `409 Conflict`. Duplicate `client_submission_id` returns the original annotation result.

Legacy unattributed annotations are imported into `test` by default and marked with `legacy_unattributed`; they are not production Gold.

