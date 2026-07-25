# Selective Re-extraction Requirement v1

This is a planning-only artifact, deduplicated by source snapshot/block rather
than candidate, pair, factor, or derived artifact. One block containing several
affected observations has one estimated call.

The required remediation order is raw reparse, parsed migration, deterministic
validation, normalization, derived rebuild, selective provider extraction, then
source reingestion. Automatic execution, provider, network, budget, and
historical-mutation authorizations are always false in v1.
