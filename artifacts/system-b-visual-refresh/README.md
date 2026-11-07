# System B 视觉更新

已将 Atlas 主工作台和旧版 Research Dashboard 统一为低饱和、冷色调的学术科研界面。

## 设计与实现

- 背景 #F6F8FB、冷白导航、纯白卡片、主文字 #243047、次级文字 #64748B、靛蓝主色 #5365CF、导航选中底色 #EEF0FF、边框 #E7EBF2。
- 桌面导航 232px，主内容留白 32px；较窄桌面导航 220px，内容留白 28px。手机采用可横向滚动的导航与单列内容。
- 标题 24–26px，模块标题 16–17px，正文和表格 14px，辅助文字 12px。中文使用现代无衬线字体回退；无需新增在线字体依赖。
- 卡片 8px 圆角与极轻阴影，输入框浅蓝灰底，聚焦边框与焦点环，按钮和状态标签统一；导航使用一致笔画的 SVG 线性图标。
- 统一详情抽屉、登录页面、证据卡、评审选择与表单、用户表格、Owner/Admin 的公共组件。保留成功、提醒、风险等状态的颜色区别。
- 修正窄屏嵌入式侧栏被通用抽屉规则隐藏的问题；评审表单在窄屏顺序展开，选择按钮两列排列，复选框恢复紧凑尺寸。
- 保留业务数据与文案、API、权限、角色导航生成、审核和仲裁流程。Explorer 的 app.js 包含任务开始前已有的业务改动，本次未编辑该文件。

## 修改文件

- `src/code_engine/system_b/explorer/static/design_tokens.css`：共享配色、圆角、阴影和焦点样式。
- `src/code_engine/system_b/explorer/static/style.css`：跨页面视觉覆盖层、布局和窄屏适配；独立登录页面的主题回退值。
- `src/code_engine/system_b/explorer/static/index.html`：顶部工作区路径提示。
- `src/code_engine/system_b/dashboard/static/style.css`：旧版 Dashboard 的浅色主题和响应式布局。
- `src/code_engine/system_b/dashboard/static/index.html`：默认导航选中语义。
- `src/code_engine/system_b/dashboard/static/app.js`：导航选中语义切换、浅色背景下的图谱文字颜色；查询、导出等业务处理保持原样。

## 实际页面截图

以下截图由本地应用实际渲染，非设计稿。研究页面使用现有本地投影的 11 个研究问题；用户和评审截图使用浏览器测试服务器的临时数据库与测试记录。旧版 Dashboard 使用仓库内置样例输出，图谱为空的状态如实呈现。

| 页面 | 截图 |
| --- | --- |
| 研究首页 · 桌面 | [查看](01-home-desktop.png) |
| Case 详情 | [查看](02-case-detail-desktop.png) |
| 机制证据档案 | [查看](03-evidence-detail-desktop.png) |
| 证据地图概览 | [查看](05-graph-desktop.png) |
| 局部证据图 | [查看](06-graph-local-desktop.png) |
| 研究首页 · 390px | [查看](07-home-mobile.png) |
| 证据地图 · 390px | [查看](08-graph-mobile.png) |
| 评审概览 · 桌面 | [查看](09-review-desktop.png) |
| 评审概览 · 390px | [查看](10-review-mobile.png) |
| 用户筛选与表格 | [查看](11-users-table-desktop.png) |
| 用户详情抽屉 | [查看](12-user-drawer-desktop.png) |
| 用户表格 · 768px | [查看](13-users-table-tablet.png) |
| 评审表单 · 桌面 | [查看](14-review-form-desktop.png) |
| 评审证据 · 390px | [查看](15-review-form-mobile.png) |
| 评审选择与字段 · 390px | [查看](16-review-controls-mobile.png) |
| 旧版 Dashboard · 390px | [查看](17-dashboard-mobile.png) |
| 旧版 Dashboard · 桌面 | [查看](18-dashboard-desktop.png) |
| 登录表单 | [查看](19-login-desktop.png) |

## 验证

- 实际检查 1440px 桌面、768px 平板和 390px 窄屏；已记录页面的文档与主内容宽度没有横向溢出，结果见 `browser-checks.json`。
- 额外检查评审表单：390px 视口，表单宽 358px，文档宽 390px；原生字段、审核选择与保存操作保留。
- Python 相关测试共 19 项通过：静态资源、初始化、标签、图谱前端、Dashboard API、集成、默认视图与知识探索。
- Playwright `atlas_pilot.spec.js`：1366px 的 6 项全部通过，覆盖 Owner 页面、局部图谱、双人评审/仲裁/冻结、错误状态、权限与 200% 缩放、用户管理和 Pilot 创建。
- Playwright 1920px 与 768px：6 项通过，6 项按现有测试定义跳过（完整写入流程仅在 1366px 执行一次）。总计 12 项浏览器测试通过。
- 截图检查及业务写入测试使用临时测试数据库，没有修改实际评审数据库。

复查命令：

```sh
PYTHONPATH=src:. pytest -q tests/test_system_b_dashboard_static_assets.py tests/test_atlas_frontend_initialization.py tests/test_system_b_dashboard_no_long_labels.py tests/test_system_b_kg_frontend_assets.py tests/test_system_b_dashboard_api.py tests/test_system_b_dashboard_integration.py tests/test_system_b_knowledge_explorer.py tests/test_system_b_dashboard_default_view.py
npx playwright test atlas_pilot.spec.js
```
