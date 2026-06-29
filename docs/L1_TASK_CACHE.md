# L1 task cache

An L1 cache key combines task family, source scope, canonical paper, content hash, schema version, prompt profile/fingerprint, model, domain, and L1 mode. Task family distinguishes abstract claim screening from full-text evidence extraction and legacy/refinement work.

Exact signatures are reusable. A different prompt fingerprint with the same compatible task family is reported as `compatible_task_family_hit`, but is not reused unless `--allow-compatible-l1-task-reuse` is explicit. Schema or content changes invalidate reuse. A hit rewrites cached records into the current run with cache key, original run, and original artifact reference, without calling the LLM.

Dry runs report hits and misses but do not populate the global cache unless global corpus update is explicitly enabled.
