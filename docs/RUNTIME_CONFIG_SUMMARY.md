# Runtime Config Summary

> **Last verified:** 2026-07-05
> **Branch:** main / HEAD
> **Purpose:** Quick-reference for current CLI arguments, environment variables, provider config, and recommended commands.

---

## 1. Environment Variables

### 1.1 LLM / L1 Provider

| Variable | Status | Used By | Required For | Notes |
|---|---|---|---|---|
| `L1_PROVIDER` | `SET` | `run_case`, `run_case_batch`, `run`, `replay_case_stages`, `check_l1_provider`, `readiness` | All L1 extraction | Currently `deepseek` |
| `MODEL_NAME` | `SET` | Same as above | All L1 extraction | Currently `deepseek-v4-pro` |
| `DEEPSEEK_API_KEY` | `SET` | `client_factory`, `DeepSeekClient` | `--execute --api` | Required for L1 calls |
| `OPENAI_API_KEY` | `MISSING` | `client_factory`, `OpenAIJSONClient` | OpenAI provider | Not needed when using DeepSeek |

### 1.2 NCBI / PubMed

| Variable | Status | Used By | Required For | Notes |
|---|---|---|---|---|
| `NCBI_EMAIL` | `SET` | `external_api_smoke`, `pubmed_post_cutoff_validator`, `case002_plan_review` | PubMed search / validation | Registered user email |
| `NCBI_API_KEY` | `SET` | Same as above | PubMed higher rate limit | Optional but recommended |
| `NCBI_TOOL` | `SET` | Same as above | PubMed API `tool` param | Currently `conflict-oriented-discovery-engine` |

### 1.3 PMC OA (Fulltext)

| Variable | Status | Used By | Notes |
|---|---|---|---|
| `PMC_OA_ENABLED` | `SET` | **NOT_USED in code** | Present in `.env` but never read by Python |
| `PMC_OA_REQUIRE_OPEN_ACCESS` | `SET` | **NOT_USED in code** | Same |
| `PMC_OA_SKIP_NON_OA` | `SET` | **NOT_USED in code** | Same; PMC OA skip logic is hardcoded in `case_factory.py` as `skip_non_oa: True` |

### 1.4 External Data Service Toggles

These `*_ENABLED` variables are **all defined in `.env` but never read by any Python source code**.
They are **NOT_USED**.

| Variable | Status | Notes |
|---|---|---|
| `ENRICHR_ENABLED` | `NOT_USED` | Enrichr is always enabled via validator registry |
| `SPEEDRICHR_ENABLED` | `NOT_USED` | Same |
| `LINCS_L1000_ENABLED` | `NOT_USED` | LINCS is enabled by `--enable-lincs-local-validation` flag |
| `REACTOME_ENABLED` | `NOT_USED` | Reactome is always enabled via validator registry |
| `OPENTARGETS_ENABLED` | `NOT_USED` | OpenTargets is skeleton-only, not production-ready |
| `CHEMBL_ENABLED` | `NOT_USED` | ChEMBL is `local_fixture_only` |
| `UNIPROT_ENABLED` | `NOT_USED` | UniProt is skeleton-only |
| `STRING_ENABLED` | `NOT_USED` | STRING is skeleton-only |
| `PUBCHEM_ENABLED` | `NOT_USED` | PubChem is skeleton-only |
| `CLINICALTRIALS_ENABLED` | `NOT_USED` | ClinicalTrials is skeleton-only |

### 1.5 External Data URLs / Paths

| Variable | Status | Used By | Notes |
|---|---|---|---|
| `ENRICHR_BASE_URL` | `SET` | `enrichr_validator` (hardcoded fallback) | Actually not read from env; hardcoded in `external_api_smoke.py` |
| `SPEEDRICHR_BASE_URL` | `SET` | **NOT_USED in code** | Only in `.env` |
| `LINCS_L1000_ROOT` | `SET` | **NOT_USED in code** | Path is hardcoded as `data/external/lincs_l1000` in `case_routing.py` and `lincs_local.py` |
| `LINCS_L1000_DATASET` | `SET` | **NOT_USED in code** | Dataset `GSE70138` is hardcoded in `readiness.py` |

### 1.6 Other Obsolescent .env Variables

| Variable | Status | Notes |
|---|---|---|
| `ENRICHR_DEFAULT_LIBRARIES` | `NOT_USED` | Only in `.env`, never read |
| `ENRICHR_API_KEY` | `NOT_USED` | Only in `.env`, never read |
| `REACTOME_API_KEY` | `NOT_USED` | Only in `.env`, never read |
| `OPENTARGETS_API_KEY` | `NOT_USED` | Only in `.env`, never read |
| `CHEMBL_API_KEY` | `NOT_USED` | Only in `.env`, never read |
| `UNIPROT_API_KEY` | `NOT_USED` | Only in `.env`, never read |
| `STRING_API_KEY` | `NOT_USED` | Only in `.env`, never read |
| `PUBCHEM_API_KEY` | `NOT_USED` | Only in `.env`, never read |
| `CLINICALTRIALS_API_KEY` | `NOT_USED` | Only in `.env`, never read |
| `CHEMBL_RATE_LIMIT_PER_SECOND` | `NOT_USED` | Only in `.env`, never read |
| `REACTOME_BASE_URL` | `NOT_USED` | Only in `.env`, never read |
| `OPENTARGETS_BASE_URL` | `NOT_USED` | Only in `.env`, never read |
| `CHEMBL_BASE_URL` | `NOT_USED` | Only in `.env`, never read |
| `UNIPROT_BASE_URL` | `NOT_USED` | Only in `.env`, never read |
| `STRING_BASE_URL` | `NOT_USED` | Only in `.env`, never read |
| `PUBCHEM_BASE_URL` | `NOT_USED` | Only in `.env`, never read |
| `CLINICALTRIALS_BASE_URL` | `NOT_USED` | Only in `.env`, never read |
| `STRING_CALLER_IDENTITY` | `NOT_USED` | Only in `.env`, never read |

---

## 2. CLI Argument Reference

### 2.1 Provider Check

```bash
python -m code_engine.cli.check_l1_provider \
  --scope fulltext \
  --api \
  --network
```

Optional smoke call:

```bash
python -m code_engine.cli.check_l1_provider \
  --scope fulltext \
  --api \
  --network \
  --smoke-call
```

> **Note:** `--smoke-call` currently prints `"smoke_call_not_implemented_use_pipeline_replay"` — it does not actually make a live API call.

### 2.2 Single Case Factory

```bash
python -m code_engine.cli.case_factory \
  --case-id <CASE_ID> \
  --query "<QUERY>" \
  --case-type conflict_enriched \
  --year-from 2000 \
  --year-to 2020 \
  --output-root configs/generated_cases \
  --api \
  --network \
  --freeze-search-plan \
  --run-readiness
```

**Real parameters:**

| Parameter | Default | Required |
|---|---|---|
| `--case-id` | — | Yes |
| `--query` | — | Yes |
| `--case-type` | `conflict_enriched` | No |
| `--year-from` / `--year-to` | None | No |
| `--output-root` | `configs/generated_cases` | No |
| `--api` / `--no-api` | `--no-api` | No |
| `--network` / `--no-network` | `--no-network` | No |
| `--freeze-search-plan` / `--no-freeze-search-plan` | `--freeze-search-plan` | No |
| `--run-readiness` | False | No |
| `--copy-to-configs` | False | No |
| `--overwrite-generated` | False | No |
| `--overwrite-configs` | False | No |
| `--allow-degraded-intake` | False | No |
| `--seed-confidence-threshold` | `0.6` | No |
| `--allow-narrow-discovery-plan` | False | No |
| `--repository-root` | `.` | No |

### 2.3 Batch Case Factory

```bash
python -m code_engine.cli.case_factory_batch \
  --seed-inventory /tmp/code_new_cases.jsonl \
  --output-root configs/generated_cases \
  --api \
  --network \
  --freeze-search-plan \
  --run-readiness
```

**Real parameters:**

| Parameter | Default | Required |
|---|---|---|
| `--seed-inventory` | — | Yes (.jsonl or .csv) |
| `--output-root` | `configs/generated_cases` | No |
| `--api` / `--no-api` | `--no-api` | No |
| `--network` / `--no-network` | `--no-network` | No |
| `--freeze-search-plan` / `--no-freeze-search-plan` | `--freeze-search-plan` | No |
| `--run-readiness` | False | No |
| `--copy-to-configs` | False | No |
| `--overwrite-generated` / `--overwrite-configs` | False | No |
| `--allow-degraded-intake` | False | No |
| `--allow-narrow-discovery-plan` | False | No |
| `--repository-root` | `.` | No |

### 2.4 Single Case Run

```bash
python -m code_engine.cli.run_case \
  --case-profile configs/generated_cases/<CASE_ID>/case_profile.json \
  --search-plan-file configs/generated_cases/<CASE_ID>/search_plan.frozen.json \
  --external-data-root data/external \
  --api \
  --network \
  --enable-fulltext-confirmation
```

> **Fulltext discovery escalation** is **auto-enabled** when:
> - `--enable-fulltext-confirmation` is set, **AND**
> - Case type is `conflict_enriched` (discovery mode)
>
> To **force-disable** even in discovery mode:
> ```bash
> --disable-fulltext-discovery-escalation
> ```

**Real parameters:**

| Parameter | Default | Required |
|---|---|---|
| `--case-profile` | — | Yes |
| `--search-plan-file` | — | Yes |
| `--external-data-root` | `data/external` | No |
| `--api` | False | No (but needed for L1) |
| `--network` | False | No |
| `--max-papers` | `60` | No |
| `--temporal-role` | `discovery` | No |
| `--l1-read-timeout-seconds` | `180` | No |
| `--l1-max-retries` | `2` | No |
| `--output-case-bundle-root` | `case_bundles` | No |
| `--output-run-suffix` | None | No |
| `--dry-run` | False | No |
| `--stop-after-readiness` | False | No |
| `--allow-warnings` | False | No |
| `--fail-if-required-validator-unavailable` | False | No |
| `--no-write-audit` | False | No |
| `--enable-fulltext-confirmation` / `--disable-fulltext-confirmation` | mutual exclusive | No |
| `--enable-fulltext-discovery-escalation` / `--disable-fulltext-discovery-escalation` | mutual exclusive | No |
| `--fulltext-source` | `pmc_oa` | No |
| `--fulltext-max-papers` | `20` | No |
| `--fulltext-include-near-conflicts` | False | No |
| `--fulltext-max-sections-per-paper` | `12` | No |
| `--fulltext-max-chunks-per-paper` | `24` | No |
| `--fulltext-max-chars-per-chunk` | `6000` | No |
| `--fulltext-max-total-chunks` | `200` | No |
| `--fulltext-l1-read-timeout-seconds` | `240` | No |
| `--fulltext-l1-max-retries` | `1` | No |

### 2.5 Batch Run Case

```bash
python -m code_engine.cli.run_case_batch \
  --generated-case-root configs/generated_cases \
  --case-ids case_1,case_2,case_3 \
  --external-data-root data/external \
  --api \
  --network \
  --enable-fulltext-confirmation \
  --max-workers 3 \
  --l1-concurrency 8 \
  --pubmed-concurrency 3 \
  --validator-concurrency 3 \
  --case-start-stagger-seconds 10 \
  --max-retries 2 \
  --retry-backoff-seconds 30 \
  --resume \
  --output-root batch_runs/my_batch
```

**Real parameters:**

| Parameter | Default | Required |
|---|---|---|
| `--generated-case-root` | `configs/generated_cases` | No |
| `--case-ids` | None | Yes (or `--case-inventory`) |
| `--case-inventory` | None | No (JSONL/CSV alternative) |
| `--external-data-root` | `data/external` | No |
| `--api` / `--no-api` | `--no-api` | No |
| `--network` / `--no-network` | `--no-network` | No |
| `--enable-fulltext-confirmation` | False | No |
| `--max-workers` | `1` | No |
| `--l1-concurrency` | `1` | No |
| `--pubmed-concurrency` | `1` | No |
| `--validator-concurrency` | `1` | No |
| `--case-start-stagger-seconds` | `0` | No |
| `--max-retries` | `0` | No |
| `--retry-backoff-seconds` | `30` | No |
| `--resume` | False | No |
| `--overwrite-bundles` | False | No |
| `--allow-degraded-intake` | False | No |
| `--allow-narrow-discovery-plan` | False | No |
| `--fail-fast` | False | No |
| `--dry-run` | False | No |
| **`--output-root`** | — | **Yes** |

### 2.6 Fulltext L1 Cached Replay

```bash
python -m code_engine.cli.replay_case_stages \
  --case-id <CASE_ID> \
  --source-bundle case_bundles/<SOURCE_BUNDLE> \
  --from-stage fulltext_l1 \
  --to-stage bundle \
  --case-version <VERSION> \
  --output-bundle case_bundles/<OUTPUT_BUNDLE> \
  --api \
  --network
```

### 2.7 Weak Conflict Replay (Offline, no LLM)

```bash
python -m code_engine.cli.replay_case_stages \
  --case-id <CASE_ID> \
  --source-bundle case_bundles/<SOURCE_BUNDLE> \
  --from-stage weak_conflict \
  --to-stage bundle \
  --case-version <VERSION> \
  --output-bundle case_bundles/<OUTPUT_BUNDLE> \
  --no-llm \
  --no-network
```

**Replay stages available:** `l2`, `l3`, `l6`, `bundle`, `fulltext_discovery`, `fulltext_l1`, `weak_conflict`

### 2.8 System B Commands

```bash
# Ingest bundles
python -m code_engine.cli.system_b_ingest_batch \
  --bundle-root case_bundles \
  --output-root system_b_output \
  --registry configs/validation/validator_registry.json

# Build KG
python -m code_engine.cli.system_b_build_kg \
  --bundle-root system_b_output \
  --output-root system_b_kg

# Serve dashboard
python -m code_engine.cli.system_b_serve_dashboard \
  --system-b-root system_b_output \
  --kg-root system_b_kg
```

---

## 3. Obsolete / Unsupported Arguments

The following arguments do NOT exist in the current CLI code (checked via `--help` and source code):

| Argument | Expected In | Status |
|---|---|---|
| `--input` | `run_case_batch` | **NOT SUPPORTED** — use `--generated-case-root` + `--case-ids` |
| `--api-concurrency` | any CLI | **NOT SUPPORTED** — use `--l1-concurrency` instead |
| `--retries` (generic) | `run_case_batch` | **NOT SUPPORTED** — use `--max-retries` |
| `--case-dir` | `run_case_batch` | **NOT SUPPORTED** — use `--generated-case-root` |
| `--case-id` in `run_case_batch` | `run_case_batch` | **SUPPORTED** (plural: `--case-ids`) |
| `--concurrency` | any CLI | **NOT SUPPORTED** — split into `--max-workers`, `--l1-concurrency`, etc. |
| `--skip-readiness` | `run_case` | **NOT SUPPORTED** |
| `--skip-fulltext` | `run_case` | **NOT SUPPORTED** |
| `--l1-timeout` | `run_case` | **NOT SUPPORTED** — use `--l1-read-timeout-seconds` |
| `--fulltext-l1-timeout` | `run_case` | **NOT SUPPORTED** — use `--fulltext-l1-read-timeout-seconds` |

---

## 4. Current Provider Configuration

| Field | Value |
|---|---|
| Provider | `deepseek` |
| Model | `deepseek-v4-pro` |
| API Key (`DEEPSEEK_API_KEY`) | `SET` |
| API Key (`OPENAI_API_KEY`) | `MISSING` |
| Provider available | `true` (verified via `check_l1_provider`) |
| Endpoint | `https://api.deepseek.com/v1/chat/completions` |
| Default timeout (connect) | 20s |
| Default timeout (read) | 120s |
| Default max retries | 2 |

---

## 5. Recommended Concurrency

```json
{
  "case_level_max_workers": 3,
  "l1_concurrency": 8,
  "pubmed_concurrency": 3,
  "validator_concurrency": 3,
  "case_start_stagger_seconds": 10,
  "max_retries": 2,
  "retry_backoff_seconds": 30
}
```

**Rationale:**

- **LLM provider theoretical concurrency ≠ pipeline concurrency.** DeepSeek API has rate limits that are not documented; start low.
- **PubMed/NCBI** rate-limits to ~180 requests/min (with API key) or ~10/min (without). `pubmed_concurrency: 3` is safe.
- **Disk I/O** (downloading PMC OA articles, writing bundles) adds contention. `l1_concurrency: 8` balances throughput vs. timeout risk.
- **`max-workers: 3`** means up to 3 cases in parallel, each using its own concurrency pool. This can quickly overload if all 3 are doing L1 simultaneously — stagger with `--case-start-stagger-seconds 10`.
- **Start small**: test with 1 case / l1-concurrency 8 first, then increase max-workers.

---

## 6. Must-Set Variables

| Variable | Reason |
|---|---|
| `L1_PROVIDER` | Required by readiness check and all L1 paths |
| `MODEL_NAME` | Same |
| `DEEPSEEK_API_KEY` (or `OPENAI_API_KEY`) | Required for `--execute --api` |
| `NCBI_EMAIL` | Required by PubMed/E-utilities API |
| `NCBI_API_KEY` | Strongly recommended for higher rate limits |

**Variables that look required but are NOT actually read:**
`ENRICHR_ENABLED`, `SPEEDRICHR_ENABLED`, `LINCS_L1000_ENABLED`, `REACTOME_ENABLED`, `OPENTARGETS_ENABLED`, `CHEMBL_ENABLED`, `UNIPROT_ENABLED`, `STRING_ENABLED`, `PUBCHEM_ENABLED`, `CLINICALTRIALS_ENABLED` — all are safe to leave empty / remove.

---

## 7. Fulltext Confirmation Auto-Enable Logic

Fulltext confirmation is **auto-enabled** when (from `run_case.py` source):

```python
fulltext_enabled = not a.disable_fulltext_confirmation and (
    a.enable_fulltext_confirmation
    or bool(policy.get("enabled"))
    or "full_text_conflict_confirmation" in profile.validation_needs
    or profile.case_type == "conflict_enriched"
)
```

So for `conflict_enriched` case types, fulltext is enabled **by default**. Use `--disable-fulltext-confirmation` to override.

Discovery escalation is auto-enabled when:

```python
discovery_requested = not a.disable_fulltext_discovery_escalation and (
    a.enable_fulltext_discovery_escalation
    or (fulltext_enabled and discovery_mode)
)
```

Where `discovery_mode = (case_type == "conflict_enriched" or planning_mode == "neutral_discovery")`.
