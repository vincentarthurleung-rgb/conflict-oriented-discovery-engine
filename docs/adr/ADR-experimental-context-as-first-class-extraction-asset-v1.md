# ADR: Experimental Context as a First-class Extraction Asset v1

Status: Accepted

Experimental Context is an immutable extraction asset parallel to Observation.
Candidate and Validated Context are separate. Context Asset and Context
Difference are separate. Direct and inherited values are separate, and shared
propagation is deterministic with explicit experiment-scope provenance.

Missing Context is never guessed by an LLM or scientific defaults. Existing
validated Context is not automatically invalidated by missing Raw lineage;
semantic, evidence, provenance, replayability, and downstream authority remain
separate. Historical artifacts migrate through sidecars without modification.

Future extraction should obtain Observation and Context together in one call.
Secondary Context Provider calls are selective remediation only and disabled
for automatic bulk execution.

This ADR does not accept Comparability, Divergence Explanation, Formal Conflict,
automatic Provider execution, automatic re-extraction, ebd5 adjudication, or
any dataset/method-paper contribution claim. The candidate prompt remains
Proposed and Pending Smoke Validation, not Production Accepted.
