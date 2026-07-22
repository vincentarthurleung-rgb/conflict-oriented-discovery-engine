# Atlas operations

## 数据与边界

Atlas 默认数据库 URL 是 `sqlite:///data/code_atlas.db`，当前 migration head 为 `0010_role_workspaces`。SQLite 保存用户、邀请、项目、review items、assignments、annotations、audit、adjudication、Gold、metrics 和 ingestion metadata；System A JSON/JSONL/projection 才是科学产物。System A 必须通过校验 handoff/sync 边界，不得任意 SQL 写 Atlas DB。

以下命令不会访问 provider 或外网。任何 init/migrate/restore/user/import 操作都会写 DB 或用户文件，先确认目标 URL。

## 只读检查

```bash
PYTHONPATH=src python -m code_engine.cli.atlas_db_check \
  --database-url sqlite:///data/code_atlas.db

PYTHONPATH=src python -m code_engine.cli.atlas_user_admin list-users \
  --users-file configs/atlas_users.json

PYTHONPATH=src python -m code_engine.cli.atlas_user_admin list-invites \
  --users-file configs/atlas_users.json
```

DB check 报告 `PRAGMA integrity_check`、foreign key check、journal mode 和 schema version。不要用文本编辑器打开并保存正在运行的 SQLite/WAL 文件。

## 初始化与 migration

仅对全新或已备份的明确目标执行：

```bash
# DB write: yes
PYTHONPATH=src python -m code_engine.cli.atlas_db_init \
  --database-url sqlite:///data/code_atlas.db

# DB write: yes; default revision is head
PYTHONPATH=src python -m code_engine.cli.atlas_db_migrate \
  --database-url sqlite:///data/code_atlas.db --revision head
```

Migration rehearsal 使用临时 SQLite URL，先 init/migrate/check，再对生产文件操作。不要对 migration 中途失败的 DB 反复手工改表；保留日志并从备份或可重现副本排查。

## Backup / restore

```bash
# Creates backup + hash manifest; source DB remains online
PYTHONPATH=src python -m code_engine.cli.atlas_db_backup \
  --database-url sqlite:///data/code_atlas.db \
  --output-dir data/backups

# HIGH RISK: overwrites target DB; explicit confirmation required
PYTHONPATH=src python -m code_engine.cli.atlas_db_restore \
  --database-url sqlite:///data/code_atlas.db \
  --backup-file data/backups/<verified-backup>.db \
  --confirm-restore
```

Restore 会先备份现有目标（若存在），但仍应停止写入服务、验证 manifest SHA-256，并在恢复后运行 `atlas_db_check`。回滚 migration/activation 优先恢复经验证备份或 active registry 副本，不手工拼接 WAL。

## 用户、owner、邀请与密码

密码通过操作员自选的临时环境变量传入；CLI 不应提供读取明文密码的能力，文档也不建议查看 password hash。

```bash
# Example only: set a fresh secret in the current shell without committing it
read -s ATLAS_ADMIN_PASSWORD && export ATLAS_ADMIN_PASSWORD

PYTHONPATH=src python -m code_engine.cli.atlas_user_admin create-owner \
  --database-url sqlite:///data/code_atlas.db \
  --username <owner> --display-name "<Owner>" \
  --password-env ATLAS_ADMIN_PASSWORD

PYTHONPATH=src python -m code_engine.cli.atlas_user_admin reset-password \
  --users-file configs/atlas_users.json --username <user> \
  --password-env ATLAS_ADMIN_PASSWORD

unset ATLAS_ADMIN_PASSWORD
```

`create-user`、`disable-user` 修改 legacy users file；`create-owner` 修改 DB。先确认部署使用哪种 auth backend，不要双写。邀请命令：

```bash
PYTHONPATH=src python -m code_engine.cli.atlas_user_admin create-invite \
  --users-file configs/atlas_users.json --label <one-time-label> \
  --role reviewer --max-uses 1 --expires-in-days 7
```

`must_change_password` 等状态由账号/auth 实现管理；不要在 JSON/DB 中直接翻位。真实凭据不得记录到 run、文档、issue 或 shell transcript。

## 启动与 auth

```bash
PYTHONPATH=src python -m code_engine.cli.system_b_serve_knowledge_explorer \
  --projection-registry system_b_outputs/system_a_sync \
  --review-root system_b_outputs/three_case_review \
  --host 127.0.0.1 --port 8765 \
  --database-url sqlite:///data/code_atlas.db \
  --require-database --require-auth
```

生产/共享环境必须配置稳定的 `ATLAS_SECRET_KEY`，使用 auth，并通过受控反向代理提供 TLS。`--public-preview` 强制 loopback；`--allow-registration` 会改变注册面，只有明确需要时开启。`--no-auth` 只适合不含敏感数据的本地隔离调试。

## Staging

Projection handoff staging 是文件级、无 DB、无 activation 操作，见 [pipeline runbook](pipeline_runbook.md#6-projection-handoff--atlas-staging)。Evaluation staging import 默认 plan；只有 `--apply` 才写评审数据库。两种 staging 都不应改变 active projection。

## Activation（高风险变更）

System A sync 实现会创建 immutable Atlas projection，并在非 dry-run 时更新 `active_projections_by_case.json`；默认还更新 `current_projection.json`。这就是 activation，不是普通 staging。

执行前必须全部满足：

1. 用户明确授权本次 case/projection activation。
2. L1 `scientific_input_complete=true`、`partial_block_failures=false`、`publication_allowed=true`。
3. handoff hash、projection validation report 和 staging counts 已审阅。
4. `atlas_db_backup` 成功；`current_projection.json`、`active_projections_by_case.json` 另存副本并记录 SHA-256。
5. dry-run 输出与目标 case/manifest hash 一致，没有 evidence-scope downgrade。
6. 明确维护窗口和回滚目标 projection ID。

当前 `code_engine.cli.system_b_sync_system_a --help` 会循环导入失败，未通过 CLI 验证。本次文档不提供 execute activation 命令；在修复及测试该入口前，禁止用手工 JSON 编辑或直接调用内部函数绕过。源码参数中虽有 `--dry-run`、`--no-database-write` 和 `--no-refresh-current-projection`，但“no refresh current”仍不阻止按 case registry activation，因此不能误当 staging-only。

## Rollback

Rollback 也是 active pointer 变更，需同级授权。停止 Atlas 写入，确认目标旧 projection 目录和 manifest hash 未变，恢复 registry/DB 的匹配备份，重启后检查 `/api/active-projections`、DB integrity 和 case 展示。不要仅把 `current_projection.json` 指向旧目录而忽略 per-case registry 和 DB current prediction 状态。
