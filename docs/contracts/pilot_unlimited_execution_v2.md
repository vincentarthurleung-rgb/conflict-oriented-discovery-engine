# Unlimited pilot integration V2 (development, not scientific authorization)

This version supplements `pilot_case_executor_v1.md`; it does not mutate any frozen scientific contract or historical run. V1 reports the earlier replay-only boundary. The current concrete backend is `ExistingStagesBackend`, composed with `CorpusStageCatalog`, the existing prospective acquisition journal and verified handoff adapter, existing frozen Builder V4/Quality V2 request preparation, existing V3 hydration and native Core adapters, and the existing Projection/Shadow functions. Native scientific schemas and gates remain unchanged.

The executor records fourteen stages (V1's thirteen remain readable): intake, acquisition, immutable handoff, Builder, Quality, experimental V3/Core, AI review, normalization/projection, alignment, context, contradiction, hypothesis, dataset export, Atlas export. A terminal package may legitimately contain blocked or skipped stages. A negative result requires an actual valid pair; no new positive scientific fixture is invented.

## Reproduction and execution boundaries

`tools/replay_unlimited_pilot.py --manifest <pinned offline manifest> --output <new directory>` blocks external sockets/DNS and replays only old SEEN sources. Deterministic Builder/Quality responses and usage are software fixtures; native packets/Core and historical AI judgments are exact pinned reuse, not fresh extraction or independent review.

`tools/run_unlimited_pilot.py --manifest <owner-bound manifest> --output <pilot directory>` checks an explicit owner artifact before credentials, metadata or provider calls. `execution_phase=metadata_access_inventory` runs metadata/access only, without constructing a model budget; later processing requires a separately bound manifest and spending approval. This interface has not been exercised against live providers in this development run. Both execution and financial authorization are absent.

## Corpus and resources

Every scientific question, inclusion/exclusion criteria and compiled query is frozen before acquisition. There is no per-case paper quota. Page size is a transport batch. Search predicates above the service pagination ceiling are partitioned into disjoint exhaustive date/complement predicates; count drift or an unsplittable partition pauses rather than truncates. Query results, duplicates, failed/unresolved identities, unavailable sources and case membership remain in a persistent SQLite ledger. One writer lease bounds acquisition concurrency to one and prevents duplicate full-text downloads across cases. Source-byte and model-input caches use exact hashes and preserve original provenance and costs. No outcome-direction filter is applied.

A query candidate is not scientific eligibility or proposition equivalence. Full-text scope review and complete access beyond the existing PMID+PMCID+DOI/OA-JATS route remain limitations. Metadata-failure reconciliation is explicit, not automatic scientific completion. Failed downloads require an explicit retry; failed/uncertain model dispatch requires reconciliation before any duplicate request.

The frozen constructor has a 60,000-character body/10,000-character abstract window. The adapter detects a saturated window and pauses with full-source references retained. It does not silently interpret the window as complete full-text processing. A complete source-window extraction/aggregation strategy is still required.

## Budget, restart, dataset and review

All model dispatches reserve worst-case configured input/output usage in a shared persistent SQLite budget before dispatch. At most two attempts are allowed; timeouts retain uncertain reservations. Exact completed requests can be reused across cases without a second charge. A durable pending marker blocks duplicate unresolved dispatch after interruption. Config/pricing/owner-approval hashes are required in live mode. Cap additions are explicit immutable tranches; they do not reset cumulative spend. `resume_partial=true` preserves the old terminal package and creates a bound continuation of the same case ID.

`tools/export_pilot_scientific_dataset.py --case-dir <attempt> --output <new directory> [--atlas-review-export <owner export>]` reuses `case_bundle_manifest_v1` and preserves native scientific objects. JSONL tables and a dictionary have content hashes and a content-derived version. Negative/incomplete/failed attempts are exported as well. Software-account responses marked SYNTHETIC go to `workflow_fixture_reviews`, never `human_reviews`. Authenticated Atlas identities and hashes do not confer scientific qualification, independent validation, Human Gold or Strict Core.

Atlas v2 review items distinguish whole attempts from individually assignable publication pairs. Lists and original-evidence pages are bounded; full immutable source packages remain server-side. Existing assignment/role/onboarding/audit controls still apply. Completed assignments retain their existing revision restrictions; a reviewer cannot bypass them by resubmitting from an old page.

## Explicit remaining boundary

Generic draft hydration can produce source-bound V3 material but does not automatically supply complete source-grounded factors/measurements/results and V2 linkage. Missing Core stays incomplete and is exported. Exact GPT review model/rates, full-text scope/window handling, broader accessible-source coverage, and owner approval must be resolved before a complete new ten-case pilot is ready. There is no scientific-authority promotion in this development path.
