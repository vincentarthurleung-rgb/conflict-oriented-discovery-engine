# LLM-First Semantic Intake

Natural-language understanding in C.O.D.E. is LLM-first. The Scientific Encoder receives the raw query and dynamically generated DomainProfile summaries, then emits a structured research intent, domain-routing decision, search concepts, non-evidence seed triples, and recommended search queries.

The encoder performs semantic encoding only. It does not determine scientific truth, conflict type, validation status, or final score. User intent and seed triples are planning inputs, never EvidenceRecords. Search queries are planning artifacts, not evidence.

The deterministic verifier is deliberately non-semantic. It validates the output schema and allowed domain IDs, sanitizes search queries, clamps legal values, enforces `is_evidence=false`, and marks low-confidence results for review. DomainRouter retrieves and validates registered DomainProfiles; it is not the primary semantic classifier.

Real LLM access requires both `--execute` and `--api`. Without both permissions, intake uses `deterministic_degraded`: language detection, an explicit `A -> B` relation, an explicit `domain:` flag, and coarse lexical chunks only. It contains no biomedical entity-to-domain mappings. Unresolved domains fall back to `general_biomedical` with confidence at most 0.5 and manual review required.

Execute mode blocks uncertain intake by default at the configured threshold (default `0.6`). Override deliberately with `--allow-uncertain-intake`, or change the threshold with `--semantic-confidence-threshold`. Dry-run continues through search planning and clearly records the degraded mode.

Legacy deterministic intent/query parsers remain available for compatibility and debugging. They are not called by the workflow semantic main path. Legacy keyword domain routing is configuration-backed and exposed only as `route_deterministic_fallback()`.
