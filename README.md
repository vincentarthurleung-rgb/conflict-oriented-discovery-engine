# C.O.D.E. — Conflict-Oriented Discovery Engine

C.O.D.E. 是一个研究型科学软件系统：从文献中发现相互冲突的证据，归因冲突所处的实验上下文，形成最小可证伪假设，并保留从结论候选到原文证据的可追溯链。外部验证和必要条件筛选用于提高可靠性，但系统输出不等于已证明的科学结论，也不是临床建议。

当前包版本为 `4.0.0a0`，Python 要求为 `>=3.10`。项目仍处于研究和 canary/replay 驱动的成熟阶段。

## 核心设计原则

- 确定性规则、schema 和完整性门优先；LLM 只做受约束的 Draft 抽取，不担任最终科学裁决者。
- 高召回探索层和高精度 Formal Core 分离。`reviewable` 表示需要审阅，不等于 `accepted`。
- Claim 是可审计陈述；Observation 是实验级结果；Evidence Chain 连接干预、比较、测量、结果和锚点；Context 描述这些证据成立的边界。
- Fulltext L1 Formal v3 从全文重新裁决，不继承摘要层的 strict decision。
- Evidence Projection 是全文 Formal Core 的权威裁决层；Reentry 负责 Context Lane、Reviewable、off-seed 等下游消费层。
- Atlas 是 System A 产物的消费、展示与评审平台。它的 SQLite 保存用户和评审状态，不是科学事实真相源。
- 无完整证据不静默降级：`scientific_input_complete=false`、`partial_block_failures=true` 或 `publication_allowed=false` 均阻止正式发布。

## 系统架构与权限边界

```text
Query / Search Plan
        |
        v
Acquisition -> Abstract L1 / L2 -> Conflict Discovery
                                      |
                                      v
                         Fulltext Candidate Bridge
                                      |
                                      v
                         Fulltext L1 Formal v3
                            |                 |
                            v                 v
                  Reentry / Context     Evidence Projection
                       Lanes             / Formal Core
                            \                 /
                             v               v
                              Projection Handoff
                                      |
                                      v
                                Atlas Staging
                                      |
                           explicit high-risk action
                                      v
                              Atlas Activation
```

System A 拥有检索、科学数据管道、归一化、冲突、上下文、假设、projection 和 immutable handoff。System B / C.O.D.E. Atlas 拥有用户、项目、评审、标注、展示、staging 和 active projection 指针。System A 不应绕过 handoff 直接修改 Atlas SQLite；Atlas 也不应改写 System A 的 immutable artifacts。

详细对象模型、权威关系和版本表见 [架构说明](docs/architecture.md)。

## 当前成熟度

摘要检索/L1/L2、冲突与假设管道、PMC OA 全文桥接、Fulltext L1 Formal v3、Reentry、离线 Evidence Projection、projection handoff、Atlas staging、SQLite migration/备份和评审界面均已有代码与测试。Fulltext provider smoke、历史 rehydrate、replay 和 canary 是实验或恢复入口；它们的产物只有通过科学完整性门后才可发布。`fulltext_projection_handoff_replay` 只实现 staging，明确不实现 activation。

Atlas 同步实现会更新 active projection，因此属于高风险路径；当前 `code_engine.cli.system_b_sync_system_a --help` 还存在循环导入错误，不能视为已验证的稳定入口。参见 [Atlas 运维](docs/atlas_operations.md)。

## 快速开始（安全、离线）

推荐 Windows 11 用户在 WSL2 Ubuntu 的 Linux 文件系统中工作；原生 Linux 使用相同步骤。依赖元数据的限制和完整安装方法见 [环境配置](docs/environment_setup.md)。

```bash
git clone <repository-url>
cd conflict-oriented-discovery-engine
conda env create --name code_env -f environment.yml
conda activate code_env
python -m pip install -e .
```

上面的 Conda 求解可能下载包，但不会调用科学数据源或付费 provider。首次验证全部保持离线：

```bash
python --version
python -c "import code_engine; print('code_engine import OK')"
PYTHONPATH=src python -m code_engine.cli.run --help
PYTHONPATH=src python -m code_engine.cli.run_case --help
python -m pytest -q tests/test_config_validation.py tests/test_replay_no_l1_network.py
```

Atlas 本地健康检查（只读数据库检查）：

```bash
PYTHONPATH=src python -m code_engine.cli.atlas_db_check \
  --database-url sqlite:///data/code_atlas.db
```

启动 Atlas 会打开本地服务但不会调用 provider；必须提供已有 projection 路径：

```bash
PYTHONPATH=src python -m code_engine.cli.system_b_serve_knowledge_explorer \
  --projection-registry system_b_outputs/system_a_sync \
  --host 127.0.0.1 --port 8765 \
  --database-url sqlite:///data/code_atlas.db --require-database --require-auth
```

## 常用工作流

默认先查看 plan/help；下列命令不开放网络或 provider：

```bash
# 创建 generated case；不会覆盖已有同名目录
PYTHONPATH=src python -m code_engine.cli.case_factory \
  --case-id <new_case_id> --query "<research question>" \
  --no-api --no-network --freeze-search-plan

# base case 安全预演
PYTHONPATH=src python -m code_engine.cli.run_case \
  --case-profile configs/generated_cases/<case_id>/case_profile.json \
  --search-plan-file configs/generated_cases/<case_id>/search_plan.frozen.json \
  --dry-run --stop-after-readiness

# 只读、零网络的 Evidence Projection；输出为新的 content-addressed projection
PYTHONPATH=src python -m code_engine.cli.fulltext_offline_reproject \
  runs/<completed_reentry_run>

# projection-authoritative handoff + Atlas staging；不会激活
PYTHONPATH=src python -m code_engine.cli.fulltext_projection_handoff_replay \
  --fulltext-run runs/<fulltext_run> \
  --reentry-run runs/<reentry_run> \
  --projection-run runs/<projection_run> \
  --staging-only
```

PMCID repair、Fulltext bridge/L1、Reentry、Projection、Handoff 和恢复流程的真实参数、产物与成功判据见 [Pipeline 运行手册](docs/pipeline_runbook.md)。数据库 migration、用户、邀请码、staging 与 activation 隔离见 [Atlas 运维](docs/atlas_operations.md)。

## 目录与可复现性

```text
src/code_engine/       当前包化实现和 CLI
configs/               配置、profile、registry 与 generated cases
runs/                  隔离的科学 run；不要原地编辑
data/                  本地数据、索引与默认 Atlas SQLite
docs/                  架构、契约、运行和运维文档
tests/                 单元、集成、回归和浏览器测试
scripts/               兼容/维护脚本，不是默认主入口
system_b_outputs/      Atlas projection、staging 与 active registry
alembic/               Atlas SQLite migration
```

- generated case 是 `case_factory` 生成的 profile、语义意图和 frozen search plan 集合。
- frozen config/plan 固定一次运行的检索身份；改变它应产生新 run，而不是改历史产物。
- run directory 保存本次运行的状态、`artifacts/`、报告和来源。
- artifact 是可审计输出；已完成 run 中的 artifact 视为 immutable。
- cache 位于运行或全局语料路径中，其身份包含输入、provider/model、Prompt/Draft/Formal schema 等；不同版本不得混用。
- handoff 是 System A 到 Atlas 的校验过的不可变文件边界。
- staging 是候选 projection，active projection 是 Atlas 当前读取的显式指针；两者不等价。

已有契约详见 [RunState 与可复现性](docs/RUN_STATE_AND_REPRODUCIBILITY.md)、[产物策略](docs/ARTIFACT_POLICY.md) 和 [Handoff 协议](docs/system_b/system_a_atlas_handoff_protocol.md)。

## 安全警告

> **默认不要添加 `--api`、`--network`、`--overwrite`、`--entity-network-lookup`、`--entity-llm-cleaner` 或任何 activation 操作。**

- `.env`、API key、session secret、密码和 token 不得提交；模板见 [.env.example](.env.example)。
- `--api` 允许 provider 调用，可能付费；`--network` 允许 PubMed/PMC 或 provider 网络访问。两者含义不同。
- `--overwrite` 可删除同名目标 run 后重建；默认使用新的 `--output-suffix`，不要覆盖历史 run。
- `--entity-network-lookup` 使用网络；`--entity-llm-cleaner` 还可能调用付费 API。
- incomplete run 不得 handoff/发布。不要直接改 `publication_allowed` 或 `ATLAS_READY`。
- Atlas staging 不等于 activation。修改 `current_projection.json` 或 `active_projections_by_case.json` 是高风险操作，只能在明确授权、备份、hash 对比和 staging 验证后执行。
- 正式 SQLite migration/restore/用户管理前先备份。密码只能 reset，不能读取明文。
- 不直接编辑 immutable artifacts，不把不同 Prompt/Draft/Formal/anchor 版本的 cache 拼接复用。

## 测试与质量保证

```bash
# focused offline tests
python -m pytest -q \
  tests/test_fulltext_evidence_projection.py \
  tests/test_fulltext_bridge_replay_cli.py \
  tests/test_atlas_db_auth.py

# full suite（耗时；浏览器测试单独运行）
python -m pytest -q

# import / compile / whitespace
python -m compileall -q src
git diff --check

# SQLite integrity + FK + migration head
PYTHONPATH=src python -m code_engine.cli.atlas_db_check --database-url sqlite:///data/code_atlas.db
PYTHONPATH=src python -m code_engine.cli.atlas_db_migrate --help

# browser tests；需先 npm ci 和安装 Playwright 浏览器
npm run test:browser
```

测试命令本身可能创建临时文件；完整测试中也有模拟 provider/network 的用例。当前已知的 CLI 导入失败见上文和 [故障排查](docs/troubleshooting.md)，不应隐藏为“全部入口正常”。

## 文档索引

- [文档差距审计](docs/documentation_audit.md)
- [环境配置：WSL2 / Linux / Python / Node](docs/environment_setup.md)
- [环境变量](docs/environment_variables.md)
- [Pipeline 运行手册](docs/pipeline_runbook.md)
- [架构、对象与版本表](docs/architecture.md)
- [故障排查](docs/troubleshooting.md)
- [Atlas 数据库与运维](docs/atlas_operations.md)
- [现有专题文档索引](docs/TECHNICAL_DESIGN_HANDBOOK.md)

## 科学语义底线

- 信息缺失不是冲突；缓存未命中不是“无覆盖”。
- 外部数据库信号是支持或反驳线索，不是自动证明。
- abstract prior 帮助定位全文，但不决定 Fulltext Formal Core。
- `reviewable`、`context`、`off-seed` 都不能被静默提升为 Formal Core。
- 所有核心边必须回溯到论文、实验 observation 和 authoritative evidence anchors。
