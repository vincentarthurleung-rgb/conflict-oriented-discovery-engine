# C.O.D.E. — Conflict-Oriented Discovery Engine

## 推荐的 System A → Atlas 命令

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas \
  --case-id <case_id> \
  --api \
  --network
```

该命令可断点恢复，并自动完成 frozen case package、base discovery、权威 PMCID 修复、OA Fulltext L1、v5 re-entry、handoff、全局 Atlas 同步和最终安全校验。详见 [One-command System A → Atlas](docs/system_b/one_command_case_to_atlas.md)。

C.O.D.E. 是一个面向生物医学研究的冲突驱动发现引擎。它从自然语言研究问题出发，规划检索、获取文献、抽取并归一化证据，识别机制冲突，生成可追溯假设，并按资源可用性执行外部验证。

项目当前处于 `4.0.0a0` 研究软件阶段。输出用于形成和审计研究假设，不应被视为临床建议或最终科学结论。

## 核心工作流

```text
研究意图
  → 语义检索计划
  → PubMed / PMC 文献获取
  → 摘要优先的 L1 事实抽取
  → L2 实体与关系归一化
  → 证据图与机制图
  → 冲突发现
  → 假设生成与时间推理
  → 外部数据验证
  → 可追溯报告
```

主要设计约束：

- **默认安全执行**：不提供参数时等价于非执行、无 API、无网络；真实运行必须显式传入 `--execute`、`--api` 和/或 `--network`。
- **确定性核心**：归一化、冲突分类、评分和结果聚合不依赖隐式 LLM 判断。
- **无隐式降级**：低置信度意图、确定性检索降级和旧流程均需显式放行。
- **证据可追溯**：用户输入和种子三元组只参与规划，不作为论文证据写入核心图。
- **运行隔离**：每次运行写入独立的 `runs/<run_id>/`，记录配置、产物和来源。
- **摘要优先**：先筛选摘要，仅将满足冲突信号门槛的论文升级到全文处理。

## 环境准备

要求 Python `>=3.10`（以 `pyproject.toml` 为准）。建议使用独立虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

当前 `pyproject.toml` 尚未声明核心运行依赖，`requirements.txt` 又是包含特定机器 Conda 本地路径的开发环境快照，并非可移植的锁文件。因此 `pip install -e .` 只安装项目本身；完整开发运行应复用项目维护的环境，或按实际入口补齐依赖，不要直接在新机器上安装现有 `requirements.txt`。LINCS 可选依赖已单独声明，可通过以下方式安装：

```bash
python -m pip install -e '.[lincs]'
# DuckDB / Arrow 列式索引支持
python -m pip install -e '.[lincs-columnar]'
```

启用 LLM 抽取时，先生成环境变量模板并自行填写密钥：

```bash
python -m code_engine.cli.print_env_template --provider deepseek
# 或
python -m code_engine.cli.print_env_template --provider openai --model YOUR_MODEL
```

常用变量包括 `DEEPSEEK_API_KEY`、`OPENAI_API_KEY`；`NCBI_API_KEY` 非必需，但可提高 PubMed 请求限额。不要提交 `.env` 或任何密钥。

## 快速开始

### 1. 本地安全演练

下面的命令创建运行目录并执行到报告阶段，但不调用 API 或网络：

```bash
python -m code_engine.cli.run \
  --query "metformin -> AMPK -> cancer" \
  --dry-run --no-api --no-network \
  --until report
```

### 2. 获取文献并执行 L1 抽取

真实运行必须明确开放执行、API 和网络：

```bash
python -m code_engine.cli.run \
  --query "metformin -> AMPK -> cancer" \
  --execute --api --network \
  --l1-provider deepseek \
  --max-papers 20 \
  --until l1
```

建议先用较小的 `--max-papers` 和 `--until` 验证配置，再扩大范围。所有可用阶段和预算参数以此命令为准：

```bash
python -m code_engine.cli.run --help
```

### 3. 查询本地产物

`query` 默认只读取本地 C.O.D.E. 产物，不隐式调用 API：

```bash
python -m code_engine.cli.query --query "metformin -> AMPK" --mode coverage --no-api
python -m code_engine.cli.query --query "metformin -> AMPK" --mode answer --no-api
```

## 常用操作

### 自然语言意图解析

```bash
python -m code_engine.cli.intake \
  --query "二甲双胍通过 AMPK 影响肿瘤治疗反应的证据是否一致？" \
  --dry-run --no-api --no-network
```

对于现代 `run_case` 案例包，优先使用 `code_engine.cli.case_factory`；`intake` 主要保留为受保护的自然语言入口。

### 独立抽取与归一化

```bash
python -m code_engine.cli.extract --dry-run --no-api
python -m code_engine.cli.normalize --term "GluA1" --json
python -m code_engine.cli.normalize --term "norketamine" --show-candidates
```

### 固化与重放检索计划

```bash
# 固化本次生成的检索计划
python -m code_engine.cli.run --query "..." --freeze-search-plan

# 使用指定计划重放
python -m code_engine.cli.run \
  --query "..." \
  --search-plan-file path/to/search_plan.json \
  --replay-search-plan
```

### 从已有运行重建图与假设

```bash
python -m code_engine.cli.run \
  --rebuild-from-run runs/<run_id> \
  --rebuild-stages graph,hypothesis,report
```

`code_engine.tools.rebuild_graph_hypothesis` 是供代码调用的工具模块，不是独立 CLI。

### 外部验证

```bash
python -m code_engine.cli.validation_preflight --help
python -m code_engine.cli.validate --help
python -m code_engine.cli.build_validation_index --help
```

外部验证按本地索引、远程 API、缓存和资源就绪状态路由。没有验证器覆盖的假设标记为 `Unresolved_No_Coverage`，不会被当作验证通过；“没有记录”也不等于反证。

## 运行模式与产物

主入口的三个开关彼此独立：

| 开关 | 含义 |
|---|---|
| `--dry-run` / `--execute` | 是否执行会产生实际研究处理的步骤 |
| `--no-api` / `--api` | 是否允许 LLM/API 调用 |
| `--no-network` / `--network` | 是否允许网络访问 |

默认输出位于 `runs/<run_id>/`。典型运行会包含 RunState、中间 JSON/JSONL、图与假设产物、来源信息以及 `run_report.md`。可用 `--run-dir` 指定目录，或用 `--resume` 继续已有运行。具体产物契约参见 [RunState 与可复现性](docs/RUN_STATE_AND_REPRODUCIBILITY.md) 和 [产物策略](docs/ARTIFACT_POLICY.md)。

## 代码结构

```text
src/code_engine/
  acquisition/       PubMed/PMC 获取与检索清单
  encoder/           研究意图编码与修复
  extraction/        摘要和渐进式全文 L1 抽取
  normalization/     L2 实体解析与审计
  evidence_graph/    证据图、证据包与冲突推理
  mechanism/         机制图、路径与冲突标注
  hypothesis/        假设构建、评分与推理路径
  temporal/          证据时间线与时间窗口比较
  validation/        验证器注册、索引、预检与执行
  corpus/            全局语料、论文身份与任务缓存
  workflow/          端到端编排、RunState 与来源追踪
  cli/               包化命令行入口
configs/              唯一配置根目录
docs/                 架构、流程和产物契约
tests/                单元、集成与回归测试
scripts/              兼容旧 Stage0–8 流程的包装脚本
data/                 原始、中间、处理后和索引数据
runs/                 隔离的运行输出
```

`scripts/` 下的阶段脚本仅用于兼容或调试，不代表当前包化工作流。Stage 编号与 Layer 架构不完全对应，修改前请阅读 [Stage/Layer 映射](docs/STAGE_LAYER_MAPPING.md) 和 [旧代码策略](docs/LEGACY_CODE_POLICY.md)。

## 配置与领域适配

`configs/` 是唯一配置根目录。默认配置不隐式加载 ketamine 等案例专用知识。领域路由支持通用生物医学、神经药理、药物靶点、通路生物学、临床结局和蛋白互作等配置方向；案例特定能力必须通过明确的 profile 或 registry 开启。

```bash
python -m code_engine.cli.run --query "..." --pilot-profile ketamine
python -m code_engine.cli.run --query "..." --case-profile configs/case_profiles/metformin_ampk_cancer.case_profile.json
```

配置目录说明见 [configs/README.md](configs/README.md)。

## 测试

```bash
python -m pytest -q
```

开发时可先运行与修改模块相关的测试，再执行完整测试集。例如：

```bash
python -m pytest -q tests/test_query_answer.py tests/test_config_validation.py
```

测试覆盖离线重放、运行隔离、无网络保护、检索计划、抽取缓存、实体解析、冲突语义、假设来源和外部验证等关键约束。

## 文档导航

- 总体设计：[包架构](docs/PACKAGE_ARCHITECTURE.md) · [端到端工作流](docs/END_TO_END_WORKFLOW.md) · [技术设计手册](docs/TECHNICAL_DESIGN_HANDBOOK.md)
- 运行与复现：[RunState 与可复现性](docs/RUN_STATE_AND_REPRODUCIBILITY.md) · [全新运行指南](docs/FRESH_RUN_GUIDE.md)
- 抽取与归一化：[L1 抽取](docs/L1_EXTRACTION_V2.md) · [渐进式全文](docs/PROGRESSIVE_FULLTEXT_L1.md) · [生物医学实体归一化](docs/BIOMEDICAL_ENTITY_NORMALIZATION.md)
- 图与假设：[机制图](docs/MECHANISM_GRAPH.md) · [运行级假设生成](docs/RUN_SCOPED_HYPOTHESIS_FORMATION.md) · [冲突证据时间线](docs/TRACEABLE_CONFLICT_EVIDENCE_TIMELINE.md)
- 语料与来源：[全局增量语料](docs/GLOBAL_INCREMENTAL_CORPUS.md) · [论文注册与书目来源](docs/PAPER_REGISTRY_AND_BIBLIOGRAPHIC_PROVENANCE.md)
- 外部验证：[领域自适应验证](docs/DOMAIN_ADAPTIVE_VALIDATION.md) · [资源感知验证](docs/RESOURCE_AWARE_EXTERNAL_VALIDATION.md) · [验证预检](docs/VALIDATION_PREFLIGHT.md)
- 工程约束：[代码审查指南](docs/CODE_REVIEW_GUIDE.md) · [清理策略](docs/CLEANUP_POLICY.md) · [旧代码策略](docs/LEGACY_CODE_POLICY.md)

## 关键科学语义

- 信息缺失不是冲突，缓存未命中不是“无覆盖”。
- 外部数据库信号是支持或反驳线索，不是自动证明。
- belief weight 不参与冲突分数或假设科学评分。
- 时间范围由运行参数提供，不使用隐藏的年份默认值。
- 所有进入核心证据图的边都必须能追溯到论文级观察。
