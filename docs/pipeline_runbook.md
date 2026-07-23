# Pipeline runbook

本手册先给离线/plan 路径，再说明会联网或付费的 execute 路径。所有 `<...>` 都必须替换；不要对已有目录使用 `--overwrite`。当前契约版本见 [architecture.md](architecture.md#当前关键版本单一文档表)。

## 影响标记

| 标记 | 含义 |
|---|---|
| Network | PubMed/PMC/provider/实体查询等外部访问 |
| Paid API | LLM/provider 潜在费用 |
| DB write | Atlas SQLite 写入 |
| New run | 新建或复制 run/projection 目录 |
| Activation | 改 Atlas active pointer |

## 1. Generated case 与 Base run

用途：固化 case profile/search plan，并在执行科学任务前验证 readiness。

```bash
# Network: no | Paid API: no | DB write: no | New run: generated case | Activation: no
PYTHONPATH=src python -m code_engine.cli.case_factory \
  --case-id <new_case_id> --query "<question>" \
  --no-api --no-network --freeze-search-plan

# Network: no | Paid API: no | DB write: no | New run: audit/bundle possible | Activation: no
PYTHONPATH=src python -m code_engine.cli.run_case \
  --case-profile configs/generated_cases/<case_id>/case_profile.json \
  --search-plan-file configs/generated_cases/<case_id>/search_plan.frozen.json \
  --dry-run --stop-after-readiness
```

`case_factory` 遇到已存在输出会阻止覆盖；`--overwrite-generated`/`--overwrite-configs` 是高风险例外。正式 base run 需要 `--api --network`，会同时访问 PubMed和 provider，可能付费：

```bash
# HIGH RISK: Network yes | Paid API yes | DB write no | New run yes | Activation no
PYTHONPATH=src python -m code_engine.cli.run_case \
  --case-profile <case_profile.json> --search-plan-file <search_plan.frozen.json> \
  --api --network --output-run-suffix <unique_suffix>
```

成功判据：退出码 0，run/bundle 记录 frozen plan、readiness 与阶段 summary；不能只看有无目录。失败时保留目录和 audit，修正配置后使用新 suffix，不原地改 artifact。

## 2. PMCID repair

用途：从已有 candidate PMID 权威重解析 PMCID；不执行 L1。

```bash
PYTHONPATH=src python -m code_engine.cli.repair_fulltext_candidate_pmcids --help

# Network: no (cache only) | Paid API: no | DB write: no | New run: yes | Activation: no
PYTHONPATH=src python -m code_engine.cli.repair_fulltext_candidate_pmcids \
  --source-run runs/<base_run> --output-suffix pmcid_repair_<unique>
```

添加 `--network` 会访问 NCBI；`--refresh-cache` 也要求重新查询。关键产物为 `artifacts/pmcid_enrichment_audit.jsonl`、`pmcid_repair_summary.json` 和 repaired/verified candidate 文件。PMCID 不存在应保留为覆盖缺口，不可伪造。默认禁止覆盖；不要添加 `--overwrite`。

## 3. Fulltext bridge replay / Fulltext L1

用途：从已有 run 运行 candidate bridge、PMC OA retrieval 和 Fulltext L1。

```bash
PYTHONPATH=src python -m code_engine.cli.fulltext_bridge_replay --help

# Plan/skeleton: no flags permit network or API; creates a separate replay run
PYTHONPATH=src python -m code_engine.cli.fulltext_bridge_replay \
  --case-id <case_id> --source-run runs/<pmcid_repair_run> \
  --output-suffix fulltext_<unique> --open-access-required
```

无 cache 时，上述离线路径会记录 blocked/planned 状态而不是偷偷联网。真正获取与抽取：

```bash
# HIGH RISK: Network yes | Paid API yes | DB write no | New run yes | Activation no
PYTHONPATH=src python -m code_engine.cli.fulltext_bridge_replay \
  --case-id <case_id> --source-run runs/<pmcid_repair_run> \
  --output-suffix fulltext_<unique> --open-access-required --network --api
```

关键产物：`fulltext_bridge_replay_manifest.json`、`l35_fulltext_retrieval_results.jsonl`、`fulltext_experiment_observations.jsonl`、`l35_fulltext_l1_claims.jsonl`、`fulltext_l1_v2_execution_records.jsonl`、`fulltext_l1_v2_summary.json`、`fulltext_l1_schema_coverage.json`。

Formal v3 使用 Prompt/Draft/Formal/anchor 版本共同定义 cache identity。执行是 block 级 patient/resumable：execution records 标识 hit、success、provider error、parse/schema error和 split 子块。输出截断/局部 parse failure 可触发有限 split；不能把未完成块当成空证据。

发布前必须同时满足：

```text
scientific_input_complete == true
partial_block_failures == false
consistency_report.publication_allowed == true
```

目录存在、claim count 非零或 canary 成功都不能替代该门。

## 4. Fulltext Reentry

用途：从已有 Fulltext L1 claims 重跑下游实体/上下文/图层，不重跑全文 L1。

```bash
# Network no | Paid API no | DB write no | New run yes | Activation no
PYTHONPATH=src python -m code_engine.cli.fulltext_reentry_replay \
  --case-id <case_id> --base-run runs/<base_run> \
  --fulltext-run runs/<fulltext_run> \
  --output-suffix reentry_<unique>
```

Formal v3 输入走 `formal_v3_native`；旧 schema 走 `legacy_compatibility`，audit 会分别计数。Reentry 保留多个 interventions，并产生 core-seed、seed-neighborhood、reviewable-context、off-seed lanes。其职责是 context/reviewable 消费层；正式 Fulltext Formal Core 由 Evidence Projection 决定。

`--entity-network-lookup` 会联网；`--entity-llm-cleaner` 加上 `--api` 可能付费。`--publish-atlas-handoff` 会尝试发布验证过的 handoff，默认不加。不要加 `--overwrite`；该实现会删除既有目标再复制。

关键产物：`fulltext_reentry_summary.json`、`fulltext_formal_v3_reentry_audit.jsonl`、`fulltext_reviewable_relations.jsonl`、`fulltext_off_seed_relations.jsonl` 及 context/evidence-chain artifacts。

## 5. Evidence Projection

用途：零网络、零 provider 地从 immutable reentry run 生成 content-addressed Formal Core projection。

```bash
# Network no | Paid API no | DB write no | New projection yes | Activation no
PYTHONPATH=src python -m code_engine.cli.fulltext_offline_reproject \
  runs/<completed_reentry_run> --output-root runs
```

它重做 context binding、cached candidate entity re-adjudication、species gate、derived sign、strict-core/reviewable 分流和 conflict bundle。关键产物包括 `fulltext_projected_observations.jsonl`、`canonical_edge_evidence_families.jsonl`、`fulltext_entity_upgrade_audit.jsonl`、`fulltext_species_compatibility_audit.jsonl`、`fulltext_core_projection_summary.json`、`offline_call_accounting.json` 和 `projection_manifest.json`。成功时 offline accounting 的 network/API/provider calls 必须为 0。

## 6. Projection Handoff + Atlas Staging

用途：Formal Core 取自 projection，context/reviewable 取自 reentry，生成 non-activating staging。

```bash
# Network no | Paid API no | DB write no | New staging yes | Activation no
PYTHONPATH=src python -m code_engine.cli.fulltext_projection_handoff_replay \
  --fulltext-run runs/<fulltext_run> \
  --reentry-run runs/<reentry_run> \
  --projection-run runs/<projection_run> \
  --base-abstract-run runs/<base_run> \
  --output-root runs --staging-only
```

`--staging-only` 必填，CLI 中没有 activation 实现。检查 `fulltext_projection_handoff_manifest.json`、`fulltext_projection_handoff_summary.json`、`atlas_fulltext_projection_staging_manifest.json`；incomplete L1 仍会令 `publication_allowed=false`，staging 文件存在不表示可激活。

## 7. Atlas evaluation staging import

默认命令是计划，不写 DB：

```bash
# Network no | Paid API no | DB write no | New run no | Activation no
PYTHONPATH=src python -m code_engine.cli.system_b_import_evaluation_staging \
  --staging-root <projection>/evaluation_staging --project-id <project_id> \
  --database-url sqlite:///data/code_atlas.db
```

`--apply` 才写数据库；`--allow-production` 是额外高风险许可。导入评审 staging 不等于激活 scientific projection。

## 8. Atlas Activation（高风险、默认不执行）

只有用户明确授权后才能执行。先按 [Atlas 运维](atlas_operations.md#activation高风险变更) 备份 DB 和 registry、验证 scientific completeness、记录当前 registry hash、dry-run 同步并比较 staging。当前同步 CLI 的 `--help` 有循环导入错误，因此本手册不提供“复制即激活”的 execute 命令。修复并验证入口前，不得绕过它手工编辑 active JSON。

## 9. Resume / recovery

1. 查看 `fulltext_l1_v2_execution_records.jsonl` 和 summary 的 `still_failed`/`newly_failed`，按 block ID 区分失败。
2. provider/auth/timeout 是传输失败；Draft schema drift 是响应契约失败；missing/cross-block anchor 是证据身份失败；reviewable 是科学 gate，不是传输错误。
3. 保留成功 block cache；相同 input/provider/model/Prompt/Draft/Formal/anchor/config identity 才能复用，避免重新支付全部 blocks。
4. offline raw-response reparse/rehydrate 只适合兼容的历史输出；先运行对应 CLI `--help`，不得把 Prompt v6/v7 cache 冒充 Prompt v8 native output。
5. 修复后重新检查三项 completeness gate。不要手改 summary、删掉 failed execution record 或把 reviewable 改成 core。

`run_case_to_atlas --dry-run --reuse-only --offline` 可审计已有 case 的一键编排计划；不要把 README 旧式 `--api --network` 示例作为默认恢复命令。
