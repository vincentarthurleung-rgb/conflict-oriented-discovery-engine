# Biomedical Entity Normalization

`ResolverCascade` remains the public Layer 2 entry point, but delegates candidate collection and selection to `EntityResolutionHub`. The hub combines explicitly configured curated anchors, previously accepted local-cache mappings, optional external candidate providers, and an optional LLM proposer.

The ketamine-depression dictionary is a pilot fixture, not a production general registry. Curated anchors provide high-confidence identities where explicitly configured; they are not the only possible source and are not intended to cover every domain. DomainProfile `entity_registry_profile` values select provider/resolver policies, not hand-written domain dictionaries.

Entity typing prioritizes L1 hints and grounded provider candidates. Universal lexical rules emit weak type candidates only; there is no ketamine-specific `TYPE_RULES`. Weak hints cannot establish canonical identity.

PubChem, ChEMBL, MyGene, and UniProt providers are optional guarded skeletons. Network access requires execute, global network permission, and entity-network permission. The LLM proposer similarly requires execute, global API permission, and entity-LLM permission. It proposes type/resource candidates only and is always ungrounded.

The deterministic adjudicator selects curated, external-grounded, or accepted-cache candidates only when score and margin policies pass. Ambiguous, unresolved, low-confidence, manual-review, and LLM-only suggestions remain excluded from high-confidence ConflictGraph use. Resolver decisions preserve legacy fields while adding provider names, candidate count, selected candidate ID, external IDs, status, manual-review state, and audit reference.

Every run writes candidate JSONL, decision JSONL, and an aggregate audit. Accepted cache mappings are written only for explicit high-confidence execution. L3 continues to group by canonical IDs and its conflict formulas are unchanged.
