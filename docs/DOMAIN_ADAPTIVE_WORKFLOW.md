# Domain-Adaptive Scientific Workflow

## Boundary

`DomainRouter` is a first-class deterministic component. It converts bounded
Chinese or English query cues into a complete `DomainProfile`; it does not use
an LLM and does not decide scientific truth. The supported profiles are
`general_biomedical`, `neuropharmacology`, `drug_target_binding`,
`pathway_biology`, `clinical_outcome`, and `protein_interaction`.

```text
natural-language query
-> DomainProfile
-> domain-specific search plan
-> domain-specific L1 prompt and context contract
-> domain-specific L2 registry/policy selection
-> domain-adaptive validation plan
```

The profile carries search and prompt profile IDs, prompt/schema/policy
versions, an entity registry profile, a resolver policy, a validator profile,
preferred and fallback validators, required and optional contexts, and key
scientific types. `ResearchIntent`, `LiteratureSearchPlan`, L1 claims,
normalization decisions, and validation plans preserve the relevant fields.

## Deterministic Responsibilities

Search templates and L1 prompt compilation are deterministic. An explicitly
enabled LLM may parse or extract structured candidates, but paper-grounded text
is required before a claim can become evidence. User-intent seed triples only
expand search queries; they have `is_evidence=false` and cannot enter L3.

L1 cache identity includes chunk content, domain/subdomain, prompt profile and
version, schema and extraction-policy versions, model identity, and the
compiled prompt hash. Historical L1 records without domain-profile metadata
are incompatible by default.

L2 chooses a local registry and resolver policy from the profile. If a
domain-specific registry is absent, the general local registry is used with an
explicit warning. Ambiguous, unresolved, or low-confidence entities remain
excluded from the high-confidence conflict graph. L3 pair identity continues
to use canonical IDs and its scientific thresholds are unchanged.

## Execution Guards

Planning is dry-run by default. Network acquisition requires `--execute
--network`; DeepSeek extraction requires `--execute --api`. Domain routing,
prompt compilation, normalization, conflict classification, validation status
aggregation, and scoring remain deterministic code boundaries.

See [DOMAIN_ADAPTIVE_VALIDATION.md](DOMAIN_ADAPTIVE_VALIDATION.md) for the
validation plugin contract.
# End-to-end propagation

The recommended `code_engine.cli.run` entry point records DomainProfile identifiers at intake and propagates them through search, L1 planning, ResolverCascade policy, and validator routing. ValidationRouter routes; validators validate. User-intent seed triples remain non-evidence planning objects.
