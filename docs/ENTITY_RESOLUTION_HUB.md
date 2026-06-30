# Entity Resolution Hub

Layer 2 now resolves mentions through `EntityResolutionHub`:

```text
local curated anchors
+ accepted local cache
+ optional external candidate providers
+ optional LLM type/resource proposer
→ deterministic adjudicator
→ auditable NormalizationDecision
```

The former ketamine-depression dictionary is stored only as `configs/normalization/fixtures/ketamine_pilot_registry.json`. It is never loaded by the production default. The domain-neutral default registry is `configs/normalization/entity_registry.json`.

Curated registries are explicit high-confidence anchor sources, not comprehensive biomedical dictionaries. PubChem, ChEMBL, MyGene, and UniProt providers expose guarded candidate interfaces. This patch does not configure or call a real service by default. Network lookup requires all of `--execute --network --entity-network-lookup`.

The LLM proposer emits only ungrounded type and resource suggestions. It cannot emit an accepted canonical decision and requires all of `--execute --api --entity-llm-proposer`. LLM-only candidates cannot enter the high-confidence graph.

The deterministic adjudicator considers exact match, source reliability, external grounding, curated status, type/context compatibility, score threshold, and top-candidate margin. Ambiguous, unresolved, manual-review, and LLM-only results set `allow_high_confidence_graph_use=false`. L3 formulas are unchanged.
# Progressive L1 Usage

The EntityResolutionHub resolves both abstract and full-text claims, but scope
is preserved in every observation. Ambiguous or unresolved candidates are
excluded from abstract entropy and full-text confirmation. Abstract-resolved
observations may contribute to screening statistics; they remain ineligible
for the high-confidence MechanismGraph until linked full-text evidence exists.
