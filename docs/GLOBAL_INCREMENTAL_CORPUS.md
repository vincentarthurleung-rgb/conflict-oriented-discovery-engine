# Global incremental corpus

The global corpus is an opt-in persistent memory under `data/corpus/` (or `--global-corpus-dir`). Each paper has a stable canonical identity and can be reused across queries, prompts, and batch runs. Run-local manifests and merge plans are always safe to write; global registry, task cache, and KnowledgeStore updates require explicit update flags.

The corpus is offline-first. It never enriches missing metadata through DOI, CrossRef, NCBI, or other remote services. Missing DOI or journal values are warnings, not fatal errors.

The workflow performs paper identity resolution, content fingerprinting, task-family cache lookup, compact bibliographic provenance injection, and an optional KnowledgeStore merge. Coverage precheck is read-only and does not short-circuit execution unless explicitly requested.
