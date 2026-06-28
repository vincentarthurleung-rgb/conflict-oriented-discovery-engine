# MechanismGraph MVP

C.O.D.E. is incrementally moving from a claim/conflict-centered pipeline toward:

```text
Paper → Evidence → Mechanism → Conflict → Hypothesis → Validation
```

MechanismGraph is a local, JSON-serializable organization layer between normalized evidence and downstream conflict/hypothesis work. Its nodes use canonical IDs when available. Its edges are built only from paper-grounded L2 normalized observations and preserve observation, claim, evidence, and paper provenance. L1 claims and EvidenceRecords enrich links but are optional.

This MVP never asks an LLM to invent mechanism edges. Seed triples, user-intent triples, semantic-intake planning records, unresolved observations, and low-confidence observations are excluded by default. Explicit low-confidence inclusion retains them with `allow_high_confidence_graph_use=false`.

L3 ConflictEngine is unchanged. It still computes Type I/II/III from normalized observations using canonical IDs. The mechanism conflict annotator only maps existing ConflictEdges onto matching canonical subject/object pairs; it never recomputes entropy, thresholds, or conflict type.

Paths are bounded deterministic edge traversals of at most three edges by default. Completeness is the fraction of path edges linked to evidence. This is not causal inference and does not create missing links.

Run-scoped artifacts are `mechanism_graph.json`, `mechanism_graph_summary.json`, `mechanism_conflict_annotations.json`, and `mechanism_graph_report.md`. No Neo4j, Memgraph, PyG, or external graph database is required.
