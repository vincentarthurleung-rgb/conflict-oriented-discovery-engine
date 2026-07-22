# Documentation audit

审计日期：2026-07-23。范围包括根 README、`docs/`、`scripts/`、配置、项目元数据、Alembic、相关 CLI 源码/`--help` 和测试。审计未读取 `.env` 内容，也未读取科学 run 内容。

## 已有资料

- 根 `README.md` 已覆盖包化主流程、目录、测试和部分安全开关。
- `docs/` 已有 RunState、artifact、全文 L1、projection、System A → Atlas handoff、Atlas 账号/备份/部署等专题文档。
- `pyproject.toml` 声明包版本 `4.0.0a0` 和 Python `>=3.10`；`environment.yml` 记录维护环境；`package.json` 只声明 Playwright 浏览器测试。
- Alembic migration、Atlas DB CLI、用户 CLI 和 System A/Atlas 同步实现均存在。

## 已修正的差距

- 旧 README 把 `run_case_to_atlas --api --network` 放在首屏推荐位置，首次使用者可能直接触发网络和付费 provider。现在默认路径为离线 help、dry-run、replay 和 staging-only。
- 缺少统一的 WSL2/Linux 环境指南、环境变量清单、端到端 runbook、当前权威架构、综合排错和 Atlas 操作边界。
- Reentry 与 Evidence Projection 的职责散落于多个专题文档，容易把 reentry core count 当成正式 Fulltext Formal Core；现在统一定义 projection 为全文 strict-core 权威层。
- staging、sync、activation 的词义没有在入口文档中严格分离；现在 activation 独立列为高风险操作。
- 旧 `CODE_ATLAS_DATABASE_ARCHITECTURE.md` 写 migration head `0005_metrics_and_audit`，代码常量和 Alembic 文件实际已到 `0010_role_workspaces`。当前值统一记录在 `architecture.md`/`atlas_operations.md`。
- `environment.yml` 是 Linux/CUDA 倾向的已解析维护环境，并带维护机 `prefix`；`requirements.txt` 含 Conda 构建机的 `file://` 引用。两者都不是跨平台最小 lockfile，文档现已明确限制。
- Node 最低版本未在 `package.json` 的 `engines` 或 CI 中声明，因此文档不编造版本范围。

## 已知入口问题

`PYTHONPATH=src python -m code_engine.cli.system_b_sync_system_a --help` 当前会因 `integration`、`system_a_sync` 与 adapters 之间的循环导入失败。源码中的 CLI 参数可以审计，但该入口没有通过真实 `--help` 验证。在修复前，不应把它作为 activation 的复制即运行命令。此项属于代码缺陷，本次文档任务不修改运行逻辑。

## 仍保留的历史资料

未删除旧 Stage/Layer、部署、专题架构或 canary 文档。它们对历史契约和实验背景仍有价值，但当前操作应以根 README 和以下文档为入口：

- `environment_setup.md`
- `environment_variables.md`
- `pipeline_runbook.md`
- `architecture.md`
- `troubleshooting.md`
- `atlas_operations.md`

若专题文档与当前代码或上述入口文档冲突，以代码和可执行 `--help` 为准，并提交文档修正，而不是改写历史 run。
