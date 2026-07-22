# Troubleshooting

每项按“症状 → 检查 → 安全修复 → 不要做”组织。默认检查均离线，标注网络的除外。

## Python 与环境

### `ModuleNotFoundError: code_engine`

检查 `python -c 'import sys; print(sys.executable); print(sys.path)'` 和 `python -m pip show conflict-oriented-discovery-engine`。激活正确环境后运行 `python -m pip install -e .`；临时源码验证可用 `PYTHONPATH=src python -m ...`。不要把绝对个人路径写进源码或全局 `PYTHONPATH`。

### Conda 环境未激活 / 版本错误

检查 `conda info --envs`、`python --version`、`which python`。激活 `code_env`，确认 Python `>=3.10`。不要把当前机器的 3.11 误写成项目最低要求。

### `.env` 未加载 / provider key missing

检查入口是否调用项目 `load_dotenv`，以及只打印存在性：`python -c "import os; print(bool(os.getenv('OPENAI_API_KEY')))"`。从 `.env.example` 复制后在本机填写。不要打印 key、提交 `.env` 或把 key 放在命令行参数中。

### API 被意外调用

立即停止进程，保存 execution/accounting audit，检查命令是否含 `--api`、`--network`、`--entity-llm-cleaner`，以及环境中的 provider/model。恢复时使用 `--no-api --no-network` 或 replay-only CLI。不要删除付费 accounting 记录来“清零”。

## 网络、PMC 与 XML

### PubMed/PMC 网络失败 / WSL DNS 或代理

网络检查：`getent hosts eutils.ncbi.nlm.nih.gov`、`curl -I https://eutils.ncbi.nlm.nih.gov/`、`env | grep -E '^(HTTP|HTTPS|NO)_PROXY='`。修复组织代理或 WSL DNS 后重试单个请求；离线 replay 不需要修。不要覆盖已有 `/etc/resolv.conf`/`wsl.conf` 或关闭证书验证。

### XML 已下载但解析失败

检查 retrieval record、文件大小/hash、parser error 和是否收到 HTML/错误页；对单个已缓存文件做离线 parser 测试。重新下载要用新 run/cache record。不要手工编辑 XML 后沿用原 hash。

### PMCID 不存在

检查 `pmcid_repair_summary.json` 与 `pmcid_enrichment_audit.jsonl`，确认 PMID 和 reverse verification。将其记录为 coverage gap；需要联网时仅运行 repair 的 `--network` 路径。不要猜 PMCID 或把 PMID 政名为 PMCID。

## Fulltext L1 与完整性

### `scientific_input_complete=false` / `partial_block_failures=true` / `publication_allowed=false`

检查 `fulltext_l1_v2_summary.json` 的 `still_failed`、execution records 和 consistency report。只恢复失败 block，复用身份匹配的成功 cache；完成后重新生成 summary。不要手工改布尔值、创建 `ATLAS_READY` 或发布 partial run。

### Draft schema drift

症状是 `draft_schema_failure`、未知/缺失字段或连续失败。检查 raw response 对应的 prompt/schema/hash 与 execution record。对兼容 raw response 使用离线 reparse/rehydrate；系统性 drift 应停止 provider run。不要用宽松 JSON 修补把缺字段变成“resolved”。

### Output truncation / split blocks

检查 finish reason、raw response 长度、`output_truncated`、child block IDs 和 `max_tokens`。保留成功块并只恢复失败/oversized 块；必要时调整显式 token budget（范围见环境变量文档）。不要无上限提高 tokens 或重新支付全部 blocks。

### Thinking mode 未禁用

当前 Fulltext L1 默认 `disabled`。检查 request audit/thinking-mode audit；若 provider 不遵守，停止并修正 provider 配置。不要把 reasoning text 当作 Draft JSON 或 scientific evidence。

### Evidence anchor mismatch / missing / cross-block anchor

检查 authoritative anchor registry、block ID、offset/hash 和 parser normalization audit。重新以同一原始 block 生成 anchor/rehydrate；失败项保持 reviewable/rejected。不要用相似文本替换 anchor ID，也不要跨 block 借锚点。

## Reentry 与 Projection

### Reentry adapter mode 不符合预期

检查 `fulltext_formal_v3_reentry_summary.json` 的 native/legacy counts 和 audit 的 `adapter_mode`。确认源 claim schema；旧输入保留 `legacy_compatibility`，需要 native 结果时重新走当前 Formal v3。不要改 schema_version 强制 native。

### Projection Formal Core 与 reentry core count 不同

这是可能的设计结果。检查 projection 的 entity/species/sign/core-gate audits 和 reentry lane reasons。正式 Fulltext Core 以 Evidence Projection 为准；Reentry core-like lane 用于上下文/探索消费。不要为了对齐计数把 reviewable 提升为 core。

### Entity lookup/cleaner 意外联网

检查 reentry manifest 的 `network_used`/`api_used` 和 flags。离线重跑时不加 `--entity-network-lookup`、`--entity-llm-cleaner`、`--api`、`--network`。不要假设“replay”天然禁止这些显式开关。

## Atlas

### Staging 已生成但 Atlas 未激活 / active projection 未变化

这是 staging-only 的正常结果。检查 staging manifest、`current_projection.json` 和 `active_projections_by_case.json` 的 hash/ID。只有走获授权 activation 才应变化。不要手工编辑 pointer 来“修复”。

### SQLite migration / foreign key violations

运行 `atlas_db_check`，比较 `schema_version` 与 `0010_role_workspaces`，先备份再 migrate。FK 失败时查 orphan repair/audit 流程并在副本演练。不要关闭 `PRAGMA foreign_keys`、删 migration 记录或直接改生产表。

### Atlas auth、`must_change_password` 或密码问题

用 `atlas_user_admin list-users` 查看非敏感状态；密码只能 `reset-password`，owner 使用 DB CLI。确认服务实际使用 users file 还是 database。不要读取/复制 hash、查询明文或把临时密码写入文档。

### `static/app.js` / 前端无法启动

Atlas UI 静态资源在 Python package 下，先运行 `system_b_serve_knowledge_explorer --help`，再检查启动日志中的 projection root 和静态文件路径。不要从 `tests/` 或历史输出随意复制 `app.js` 覆盖当前包。

### Playwright 缺系统依赖

运行 `npx playwright install` 后按错误安装精确依赖；获准修改系统时才用 `npx playwright install --with-deps`。普通 Atlas 服务无需 Playwright。不要为一次 server smoke 默认安装整套浏览器。

### 端口被占用

检查 `ss -ltnp | grep ':8765'`，停止确认过的旧进程或改用 `--port <free-port>`。不要用宽泛 `killall`。

### `system_b_sync_system_a --help` 循环导入

症状是 partially initialized module / `ADAPTER_VERSION` ImportError。该入口当前未验证，见 [文档审计](documentation_audit.md)。使用 staging-only handoff 继续安全检查；activation 保持暂停，等待代码修复和 focused tests。不要直接调用 `_activate_cases` 或手改 registry。

## 磁盘与 run 安全

### WSL/磁盘空间不足

检查 `df -h .` 和 `du -sh runs data system_b_outputs`。暂停新全文下载，按项目清理策略逐项归档测试输出。不要递归删除 runs、cache、SQLite/WAL、handoff 或 active projection；cache 是否可删取决于是否需要恢复和避免重复付费。
