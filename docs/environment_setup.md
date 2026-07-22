# Environment setup

## 支持范围

项目元数据要求 Python `>=3.10`，维护环境固定在 Python 3.11。推荐 Windows 11 + WSL2 Ubuntu 或原生 Ubuntu/Linux。macOS 可能支持不依赖 CUDA/Linux 路径的包化与离线功能，但仓库没有声明或 CI 证明完整支持。纯 Windows 原生命令行没有验证，路径、shell 脚本和 Linux 依赖使其不推荐。

Node 只用于 Atlas 的 Playwright 浏览器测试；Atlas 服务本身是 Python/Flask。仓库未声明 Node `engines` 或 CI 版本，所以不能给出受支持的最低 Node 版本；以能完成 `npm ci` 的当前 LTS 为操作前提并在本机记录 `node --version`。

## Windows 11 + WSL2

在管理员 PowerShell 中安装（会修改 Windows 功能并下载 Ubuntu）：

```powershell
wsl --install -d Ubuntu
wsl --status
wsl --list --verbose
```

目标发行版应显示 version 2。若项目需要 systemd，先查看现有 `/etc/wsl.conf`，再合并而不是覆盖：

```ini
[boot]
systemd=true
```

执行 `wsl --shutdown` 后重启发行版，用 `systemctl is-system-running` 检查。项目应克隆到如 `/home/<user>/project/...`，不要放在 `/mnt/c/...`：Linux 文件系统通常具有更合适的权限语义、文件监听和大量小文件 I/O。Windows 的 `C:\Users\...` 在 WSL 中对应 `/mnt/c/Users/...`；不要把两种路径直接传给同一个 CLI。

VS Code 使用 Remote - WSL 扩展，并从 WSL shell 在仓库中运行 `code .`。Python、Conda、Node 和 Git 都应在 WSL 内安装/选择，不要混用 Windows 可执行文件和 WSL 路径。

## Python 主安装路径

`environment.yml` 是当前维护环境快照，包含 Linux/CUDA 依赖且末尾有维护机 prefix。用 `--name` 明确覆盖环境名：

```bash
conda env create --name code_env -f environment.yml
conda activate code_env
python -m pip install -e .
python -c "import code_engine; print('OK')"
python -m pytest -q tests/test_config_validation.py
```

网络影响：Conda/pip 安装会访问包源；不会访问 PubMed/PMC 或 provider。不要在未审计的机器上直接用 `requirements.txt` 重建：其中若干 `file://` wheel 指向 Conda 构建机，不可移植。

轻量备选是 Python 3.10+ venv，但 `pyproject.toml` 尚未声明核心运行依赖，必须按所用入口自行安装依赖，不能声称 `pip install -e .` 可得到完整环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

可选本地验证依赖由项目声明：

```bash
python -m pip install -e '.[lincs]'
python -m pip install -e '.[lincs-columnar]'
```

## Node 与 Atlas 前端测试

```bash
node --version
npm --version
npm ci
npx playwright install
npm run test:browser
```

`npm ci` 和 `playwright install` 使用网络；浏览器安装还占用较多磁盘。某些 Linux 环境需要 Playwright 的系统依赖，`npx playwright install --with-deps` 会下载软件并可能要求 sudo，只在明确允许修改系统时运行。普通 Atlas 服务不需要 Node：

```bash
PYTHONPATH=src python -m code_engine.cli.system_b_serve_knowledge_explorer --help
```

## 系统依赖

代码/元数据能确认的基础工具是 Git、Python、SQLite（运维检查也可由 Python CLI 完成）和 Node/npm（仅浏览器测试）。Graphviz 只在需要图形渲染的工作流中使用；Playwright 浏览器/系统库仅测试需要。XML 解析使用 Python/Biopython 路径，仓库没有独立声明必须安装某个 apt XML 开发包。

不要复制一份未经项目验证的长 apt 列表。遇到 wheel 编译失败时，先记录具体包和错误，再安装对应编译工具；不要默认安装 CUDA 或全套浏览器依赖。

## 数据目录与磁盘

`runs/`、`batch_runs/`、`data/`、全文 XML/解析结果和 cache 会快速增长；仓库没有可据以承诺的统一容量。执行前用以下只读命令估算：

```bash
df -h .
du -sh runs data system_b_outputs 2>/dev/null
```

WSL 可在 PowerShell 用 `wsl --status` 检查发行版，再按 Windows 官方流程管理虚拟磁盘。不要用递归删除命令清理 `runs/`、`data/` 或 `system_b_outputs/`。测试缓存（如 `.pytest_cache`、`test-results`）通常可重建，但删除前仍要确认不包含需要保留的调试证据。历史 run、handoff、active registry 和 SQLite/WAL 文件不能直接删除。

## 网络、DNS 与代理

离线 replay、projection 和本地测试不需要网络。PubMed/PMC 获取需要 NCBI 网络；provider 抽取同时需要网络、provider 配置和显式 CLI 许可。

```bash
getent hosts eutils.ncbi.nlm.nih.gov
curl -I https://eutils.ncbi.nlm.nih.gov/
env | grep -E '^(HTTP|HTTPS|NO)_PROXY='
```

这些检查会访问网络。代理只使用组织提供的通用环境变量，不把个人地址写入仓库。WSL 中 `localhost` 通常指 WSL 自身；Windows 服务是否可由 WSL 的 localhost 访问取决于 WSL 网络模式。DNS 异常先比较 `getent hosts`、`/etc/resolv.conf` 和 Windows 侧连通性；不要在不理解现有配置时覆盖 `/etc/resolv.conf` 或 `/etc/wsl.conf`。

## 离线验收

```bash
python --version
python -c "import code_engine"
PYTHONPATH=src python -m code_engine.cli.run --help
PYTHONPATH=src python -m code_engine.cli.fulltext_offline_reproject --help
PYTHONPATH=src python -m code_engine.cli.atlas_db_check --help
git status --short
```
