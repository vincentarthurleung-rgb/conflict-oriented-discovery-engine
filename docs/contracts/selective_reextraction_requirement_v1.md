# Selective Re-extraction Requirement v1

This is a planning-only artifact, deduplicated by source snapshot/block rather
than candidate, pair, factor, or derived artifact. One block containing several
affected observations has one estimated call.

The required remediation order is raw reparse, parsed migration, deterministic
validation, normalization, derived rebuild, selective provider extraction, then
source reingestion. Automatic execution, provider, network, budget, and
historical-mutation authorizations are always false in v1.
# Historical forensic v2 note

The 81 v1 requirements are preserved as the pre-forensic upper bound.
Selective re-extraction v2 can eliminate a requirement only through an
authoritative offline recovery mode and never executes a provider call.
