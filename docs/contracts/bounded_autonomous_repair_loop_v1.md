# Bounded autonomous repair loop v1

The loop permits deterministic engineering repairs supported by local assets.
Iteration 0 is scan-only; the total limit is six. Each record includes issue
IDs, evidence, root cause, files changed, repair, tests, before/after metrics,
limitations, and a stop/continue reason.

Scientific ambiguity is always `autonomous_repair_allowed=false`. The loop
stops after two stagnant rounds, at the iteration cap, or when all in-scope
high-severity engineering issues are fixed or explicitly blocked.

