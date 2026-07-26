# Source reingestion and core annotation queue refinement v1

This offline workflow reads the immutable v1 source-resolution run and local
full-text assets. It emits local recovery sidecars, source envelopes v2,
core-target retriage, observation annotation bundles, a separate method
enrichment pool, per-ID reconciliations, remediation v4, and readiness v4
candidates.

The workflow is fail-closed. Source recovery only expands auditable scope; it
does not select comparators, factor applications, methods, conflicts,
comparability, differences, or explanations. Current full text authority and
historical Provider-input authority remain separate. No Provider, network,
download, credential, human annotation, gold, publication, or activation path
is present.

The bounded loop has one scan-only baseline and at most five repair rounds.
Every round records evidence, before/after metrics, verification, and its stop
reason. Two consecutive rounds without improvement stop the loop.

