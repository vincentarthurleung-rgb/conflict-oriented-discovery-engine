# Coverage precheck

The optional read-only precheck estimates paper, entity/claim, conflict, mechanism, hypothesis, and validation coverage for a query. It recommends reuse, incremental search, abstract-only work, full-text escalation, or validation-only work.

Recommendations do not silently skip workflow stages. Short-circuiting requires `--allow-coverage-short-circuit`; the current mainline records the recommendation and continues. Empty stores return `insufficient_global_store`.
