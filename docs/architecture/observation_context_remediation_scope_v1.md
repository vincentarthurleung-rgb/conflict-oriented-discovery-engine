# Observation Context Remediation Scope v1

Status: Active

Remediation debt belongs to an Observation, not to every Candidate that
references it. One immutable Observation-level need is indexed by the global
registry and may fan out to zero or more Candidate dependencies.

Only a qualified Candidate whose L4 Entry is blocked by that Observation can
receive an active blocking dependency. Policy coverage failures use a separate
review requirement and are never ordinary extraction or network retries.
Neither needs, reviews, dependencies, nor the registry authorize execution.

