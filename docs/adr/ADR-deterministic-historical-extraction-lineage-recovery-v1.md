# ADR: Deterministic Historical Extraction Lineage Recovery v1

Status: Accepted

Historical lineage may be recovered only through direct evidence or a
deterministic, exact, uniquely recomputable chain. One-to-one matching is a
precondition. Timestamp, filename, directory location, and diagnostic scores
cannot confer authority. Probable matches remain non-authoritative and all ties
fail closed.

Forensic recovery is read-only and zero-API. Parser replay is versioned and
preserves raw bytes. Missing source, raw, or parsed evidence is reported rather
than fabricated. Re-extraction is recalculated only after forensics; the 81 v1
requirements are an upper bound, not an execution plan. No source reingestion,
provider call, prompt activation, scientific adjudication, or dataset-release
claim is authorized by this decision.

