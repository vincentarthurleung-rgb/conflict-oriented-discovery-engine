# Architecture

## 权威平面

当前实现可理解为四个职责平面，而不是四套互相复制的数据：

1. **Intake/Acquisition**：研究意图、frozen search plan、PubMed/PMC 获取和 abstract prior。
2. **Scientific processing**：Abstract L1/L2、Fulltext L1 Formal v3、实体重裁决、冲突、上下文和假设。
3. **Publication boundary**：Evidence Projection、immutable Projection Handoff、完整性门和 provenance。
4. **Atlas review**：projection/staging、展示、用户、项目、评审、标注和 active pointer。

System A 拥有前三个平面的科学状态。System B 的 SQLite 只保存交互和评审状态；它不是 System A 科学真相源。

## 科学对象

- **Claim**：可追溯到论文/区块的陈述记录，可能仍需归一化或审阅。
- **Observation**：一个实验/比较下的测量结果。Formal v3 要求一个 observation 对应一个实验 outcome，不能为了方便 fan-out 成多个“确定”关系。
- **Evidence Chain**：把 experimental system、多个 interventions、comparator、measurement、outcome 和 authoritative anchors 串起来。
- **Context**：species、cell line/type、tissue、disease、dose、duration、assay、genotype 等适用条件；缺失保持 unknown/null。
- **Conflict**：可比较的 observations 在相同规范关系族下呈现不一致 polarity；信息缺失或不可比不是冲突。
- **Hypothesis**：对冲突的最小、可证伪解释，必须链接到证据和上下文，不能反向成为证据。

Evidence Chain 负责“证据如何支持 observation”，Context 负责“证据在什么条件下成立”，Claim 负责“系统记录了什么陈述”。三者不能互相替代。

## Abstract 与 Fulltext

Abstract L1/L2 是高召回 prior 和升级全文的导航层。Fulltext L1 从原文 block 与 authoritative anchors 重新建立实验 observation；它不继承 abstract strict decision，也不能因 seed/abstract 先验而确认关系。

当可用且通过完整性门时，Fulltext Evidence Projection 优先。Abstract-only handoff profile 只适用于没有可发布全文 projection、且协议明确允许的路径；不能用 abstract 自动降级覆盖已有 fulltext active projection。

## Fulltext L1 Formal v3

Prompt 只要求 provider 生成 Draft。确定性 hydrator 使用代码产生的 provenance 和 evidence anchor，将 Draft 变为 Formal v3：

- `interventions` 是嵌套/多项结构，rescue、组合、再表达等必须保留；不能静默只取第一个。
- 原文锚点由 pipeline 生成，模型返回 anchor ID，不能自行发明 text/offset/hash。
- normalization/eligibility 状态为 resolved、reviewable/ambiguous 或 rejected 类结果；只有通过 strict eligibility 的记录才可进入 Formal Core。
- lexical direction、observed outcome、intervention sign、derived causal sign 和 final polarity 分离；Formal projection 优先使用 derived sign。
- mixed/unknown、组合方式未知、端点未解析、species 不相容、anchor 缺失等保持 reviewable 或 rejected，不能 fan-out 为多个 core 事实。

## Reentry 与 Evidence Projection

当前权威模型是：

```text
Formal fulltext strict core = Evidence Projection
Context / Reviewable / off-seed = Reentry
```

Reentry 的 `formal_v3_native` adapter 保留 Formal v3 实验结构；`legacy_compatibility` 只为历史输入兼容，不能当成等价的新 Formal v3 证据。Reentry 的 core-like lane 是 Atlas/context 消费和审计输入，不是全文 Formal Core 的最终裁决数。

Evidence Projection 是零网络、零 provider 的 content-addressed 新输出。它重新绑定 context，使用缓存候选做实体 re-adjudication，执行 species gate、derived-sign 关系裁决、strict-core gate 和 conflict bundle 构建。它不修改 source run 或 active pointer。

## Handoff、staging 与 activation

Projection Handoff 把 projection 的 Formal Core 与 reentry 的 context/reviewable lanes 合并为不可变边界，记录文件 hash、schema、来源 run 和完整性。`fulltext_projection_handoff_replay --staging-only` 只生成 handoff/Atlas staging，永不激活。

Atlas projection 目录不可变；staging 是待验证候选。activation 只改变 `current_projection.json` 和按 case 的 `active_projections_by_case.json` 指针，并可能更新 Atlas DB 的 current prediction 状态。它必须是显式、备份后、可回滚的运维操作。

## Run、artifact、cache 与复现

- frozen plan 固定检索身份；run 记录配置、git/provenance、输入和阶段状态。
- 已完成 run 的 artifact 不原地修改；repair/replay 使用新 suffix/新目录。
- schema 和 profile 有显式版本；未知 schema 不静默 fallback。
- cache identity 是输入和执行契约的 hash，不是“同一文件名”。不兼容 cache 应 miss，而不是强制命中。
- projection 和 handoff 使用内容身份与 hash；相同内容可 no-op，不同内容产生新目录。
- incomplete/partial 输入不得发布；手工创建 `ATLAS_READY` 不会使科学输入完整。

## 当前关键版本（单一文档表）

下表来自当前代码；其他入口文档只链接本节，避免重复维护：

| Contract | Current value | Source |
|---|---|---|
| Package | `4.0.0a0` | `pyproject.toml` |
| Fulltext prompt | `fulltext_experimental_observation_prompt_v7_anchor_id_authoritative` | `fulltext/fulltext_l1_v2.py` |
| Draft schema | `fulltext_l1_experimental_observation_draft_schema_v3_anchor_id_authoritative` | `schemas/fulltext_observation_draft.py` |
| Formal schema | `fulltext_l1_experimental_observation_schema_v3` | `fulltext/fulltext_l1_v2.py` |
| Evidence anchor | `fulltext_evidence_anchor_contract_v2` | `fulltext/evidence_anchors.py` |
| Cache identity | `fulltext_l1_v2_cache_identity_v5_authoritative_anchors` | `fulltext/fulltext_l1_v2.py` |
| Reentry native mode | `formal_v3_native` | `fulltext/reentry.py` |
| Reentry legacy mode | `legacy_compatibility` | `fulltext/reentry.py` |
| Evidence projection | `fulltext_evidence_projection_v1.0.8` | `fulltext/evidence_projection.py` |
| Atlas fulltext adapter | `fulltext_reentry_v5_adapter_v5` | `system_b/adapters/fulltext_reentry_v5.py` |
| Atlas projection schema | `atlas_projection_v2` | `system_b/system_a_sync.py` |
| Atlas DB head | `0010_role_workspaces` | `system_b/persistence/database.py` |

安全查询这些值可用 `rg` 读取常量；不要通过运行 provider smoke 来“检查版本”。每个 run 的 summary、cache identity、projection manifest 和 handoff manifest 仍是该次运行的最终来源。
