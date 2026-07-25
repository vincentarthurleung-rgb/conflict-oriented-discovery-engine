# Historical Extraction Lineage Forensics v1

This subsystem performs a read-only, zero-network audit of historical HIF1A
extraction assets. It inventories source, attempt, raw, and parsed sidecars;
replays saved raw bytes through an explicitly identified historical contract;
and resolves lineage only when direct identifiers or deterministic,
content-exact, unique evidence form a closed chain.

Authority is never inferred from timestamps, filenames, directory order, or a
diagnostic score. Those signals may generate review candidates only. Candidate
graphs are resolved under one-to-one constraints; ties and conflicts remain
unbound. Historical source, request, raw, parsed, observation, and v1 planning
artifacts are immutable inputs.

Replayability v2 and selective re-extraction v2 consume the forensic bindings.
They do not execute extraction. The existing 81 requirements remain the
pre-forensic upper bound. Research-readiness tiers are internal lineage audits,
not human-gold labels or dataset-release claims.

