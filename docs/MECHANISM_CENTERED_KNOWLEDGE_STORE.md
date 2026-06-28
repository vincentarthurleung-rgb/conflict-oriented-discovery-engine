# Mechanism-Centered Knowledge Store

`code_engine.storage.mechanism_index` loads a run-scoped MechanismGraph JSON artifact and provides local queries for:

- edges involving a canonical entity or node;
- paths between two node IDs;
- conflicted mechanism edges;
- evidence IDs supporting a mechanism edge.

The implementation is deliberately file-backed and dependency-free. It does not merge user-intent seed triples into scientific evidence and does not infer new edges. A future external graph database may implement the same adapter boundary, but Neo4j or another graph service is not part of the current runtime.

Hypothesis search will eventually prioritize conflicted, evidence-grounded mechanism paths. The current run-scoped adapter reports available paths and conflicts but returns planned/blocked because legacy Stage6 remains global-path driven.
