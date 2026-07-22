# Environment variables

本表只列代码直接读取的环境变量。部分 CLI 会调用项目的简易 `.env` loader；它按行读取 `KEY=VALUE`，不会做完整 shell 展开。不要把真实 secret 写入文档、命令历史或版本库。

## Provider / LLM

| Variable | Required | Default | Used by | Sensitive | Network/API impact | Description |
|---|---:|---|---|---:|---|---|
| `L1_PROVIDER` | provider 模式需要 | 空 | L1、Fulltext、readiness | 否 | 与 `--api`/网络许可组合后可付费 | Canonical provider：代码支持 `deepseek` 或 `openai`。 |
| `MODEL_NAME` | provider 模式需要 | 空 | L1、planner、Fulltext | 否 | 选择计费模型；也是 cache identity 的一部分 | 模型名。 |
| `DEEPSEEK_API_KEY` | DeepSeek 时需要 | 空 | provider client | 是 | 存在本身不触发调用；显式 API 运行会付费 | DeepSeek credential。 |
| `OPENAI_API_KEY` | OpenAI 时需要 | 空 | provider client | 是 | 同上 | OpenAI credential。 |
| `L1_CONNECT_TIMEOUT_SECONDS` | 否 | client 内建值 | provider client | 否 | 不触发调用 | 连接超时；CLI 显式参数优先。 |
| `L1_READ_TIMEOUT_SECONDS` | 否 | 回退到 `L1_TIMEOUT_SECONDS`/内建值 | provider client | 否 | 不触发调用 | 读取超时，canonical 名称。 |
| `L1_TIMEOUT_SECONDS` | 否 | 空 | provider client | 否 | 不触发调用 | `L1_READ_TIMEOUT_SECONDS` 的兼容别名；新配置优先用 canonical 名称。 |
| `L1_MAX_RETRIES` | 否 | client 内建值 | provider client | 否 | 重试会增加实际请求/潜在费用 | 最大重试次数；CLI 参数优先。 |
| `FULLTEXT_L1_V2_MAX_TOKENS` | 否 | `32768` | Fulltext L1 Formal v3 实现 | 否 | 影响输出预算和 cache identity | 合法范围 `1024..131072`；历史模块名仍含 v2。 |
| `L2_ENTITY_CLEANER_PROVIDER` | 否 | 回退 `L1_PROVIDER` | entity cleaner | 否 | 仅显式启用 cleaner 后可能付费 | L2 cleaner provider。 |
| `L2_ENTITY_CLEANER_MODEL` | 否 | 回退 `MODEL_NAME` | entity cleaner | 否 | 同上；影响结果身份 | L2 cleaner model。 |

密钥永远不是启用开关：只有 CLI 同时允许 API/网络时才应发出请求。`--entity-llm-cleaner` 是独立的高风险许可。

## PubMed / PMC

| Variable | Required | Default | Used by | Sensitive | Network/API impact | Description |
|---|---:|---|---|---:|---|---|
| `NCBI_TOOL` | 否 | `conflict_oriented_discovery_engine` | NCBI requests | 否 | 仅网络命令使用 | NCBI tool 标识。 |
| `NCBI_EMAIL` | 否 | 空 | NCBI requests | 低敏感 | 仅网络命令使用 | NCBI 联系邮箱。 |
| `NCBI_API_KEY` | 否 | 空 | NCBI requests | 是 | 允许认证后的 NCBI 配额；不产生 provider 费用 | 可选 NCBI key。 |

## Atlas / database / authentication

| Variable | Required | Default | Used by | Sensitive | Network/API impact | Description |
|---|---:|---|---|---:|---|---|
| `ATLAS_DATABASE_URL` | 否 | `sqlite:///data/code_atlas.db` | Alembic、Atlas persistence | 凭据型 URL 是 | 无 provider 调用；会选择被读写的 DB | CLI `--database-url` 通常优先。 |
| `ATLAS_SECRET_KEY` | authenticated server 需要稳定值 | 空 | Atlas server sessions | 是 | 无外网影响 | Flask/session secret；生产必须随机、稳定且不提交。 |

`atlas_user_admin --password-env <NAME>` 会动态读取由操作员指定的变量名；这不是一个固定 canonical 环境变量。密码变量仅在当前 shell 临时设置，不能放入 `.env.example` 的真实值。

## Paths / local build / tests

| Variable | Required | Default | Used by | Sensitive | Network/API impact | Description |
|---|---:|---|---|---:|---|---|
| `CODE_OMICS_TARGETS` | 否 | 空 | `scripts/build_lincs_index.py` | 否 | 无 | 逗号分隔的目标基因 flight log。 |
| `ATLAS_BASE_URL` | 否 | `http://localhost:18765` | Playwright config | 否 | 只访问指定测试服务 | 浏览器测试 base URL。 |
| `ATLAS_TRACE` | 否 | 非 `1` | Playwright config | 否 | 无 | `1` 时始终保留 trace。 |
| `FONTCONFIG_FILE` | 否 | 测试配置自动设置 | Playwright/font rendering | 否 | 无 | 通常无需用户设置。 |
| `ATLAS_DISPLAY_ROOT` | 否 | `system_b_outputs/system_a_sync` | browser test server only | 否 | 无 | E2E fixture 的 projection 根。 |
| `ATLAS_E2E_PORT` | 否 | `18765` | browser test server only | 否 | 仅本机监听 | E2E fixture 端口。 |
| `ATLAS_OWNER_USERNAME` | 否 | `owner` | browser test only | 否 | 无 | E2E owner 用户名。 |
| `ATLAS_OWNER_PASSWORD` | 否 | 测试 fallback | browser test only | 是 | 无 | 只用于测试；生产不得使用测试默认值。 |

## Cache 与环境差异

Fulltext L1 cache identity 显式包含 Prompt/Draft/Formal schema、anchor contract、hydrator/registry/completeness 版本、provider/model、输入 block 和配置。不要仅靠复制目录强制复用 cache。超时和重试主要影响传输，不应被当作科学 schema；token budget 会进入 Fulltext L1 配置身份。

本地开发可使用 SQLite 相对路径；部署时用受保护的绝对路径或受管数据库 URL，并独立管理 secret。生产不应依赖 browser-test 变量、测试密码或 `--no-auth`。

模板见仓库根目录 `.env.example`。检查变量是否存在时只打印变量名/布尔状态，绝不打印值。
