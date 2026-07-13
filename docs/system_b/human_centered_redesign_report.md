# C.O.D.E. Atlas 人本产品重构报告

日期：2026-07-13。范围：System B / Atlas 展示层、确定性投影 API 与临时数据库浏览器测试。未修改 System A 科学计算、L1–L7、claim sign 或 formal conflict eligibility。

## 修改前问题地图

| 分类 | 审计发现 | 影响 |
|---|---|---|
| 信息架构 | 首页、Case、实体、关系、图谱与 Owner 仍按对象/模块组织 | 新用户无法判断从哪里开始 |
| 任务流程 | 所有角色首页近似；Owner 首屏是统计；Evaluation 是硬编码状态 | Reviewer/Owner 需要猜下一步 |
| 内容与术语 | 长 `case_id`、item type、schema id、英文内部字段进入普通视图 | 普通研究者需理解实现细节 |
| 视觉层级 | 首屏统计和同权重卡片过多 | 当前发现与主要行动不突出 |
| 交互 | Context Matrix 默认全部横向字段；Reasoning API 未进入 Dossier 页面 | 科研阅读链断裂 |
| 科学表达 | Case 的全文计数取自旧 case triple 字段，真实 Dossier 有全文而卡片显示 0 | 状态互相矛盾，损害可信度 |
| 权限与角色 | Developer 信息虽有权限门禁，Reviewer 主内容仍展示 schema/item 内部名 | 渐进披露不完整 |
| 空/错状态 | Reasoning 缺失文案不够明确；最近活动无数据缺少行动建议 | 用户误判为加载失败 |
| 响应式/可访问性 | 主体已有断点和 focus 样式，但新科研流程未覆盖真实 11 案例 | 不能证明 1366、平板、200% zoom 可用 |
| 性能 | 11 案例接口会重复遍历证据集合 | 当前规模可用，后续需索引化 |

体验地图的关键断点是：首页没有解释产品 → Case 只给列表 → Dossier 没有推理链 → Context 是超宽表 → Reviewer 暴露内部名 → Owner 统计先于行动 → Evaluation 不解释真实阻塞依赖。

## Persona 与新信息架构

- 科研阅读者：研究问题 → 当前发现 → 关键机制档案 → 论文证据 → 条件差异 → 推理链/矩阵 → 局部图。
- Reviewer：我的任务 → Case/批次 → 原始证据 → 普通语言问题与标签 → 草稿 → 提交/下一条。
- Adjudicator：原始证据 → 审核者 A/B → 差异摘要 → 最终判断 → 指南歧义标记。
- Owner：行动项 → Pilot 概况 → 用户/邀请码 → 项目/任务 → 仲裁 → 金标准 → 评估 → 质量/审计/导出；技术系统独立在 `/owner/system`。

主导航现在按任务排列为 Research、Review、Evaluation、Library、Owner；Developer Console 仅对 developer 出现。图谱从主入口降为研究流程内的辅助入口。

## 核心页面设计与实现

首页用一句准确产品定义和三步起点解释系统用途。11 张真实 Case Card 使用人类可读名称和研究问题，展示证据、文献、正式冲突、人工审核、全文/推理/上下文状态；Reviewer 与 Owner 得到角色化主要行动。

Case 页用“当前发现”回答正式冲突、证据范围、不可比较和弱分歧线索；能力与同步时间单独展示；关键机制按证据量选取；常见实验条件只汇总已报告值；机制图是次要入口。

Dossier 按机制声明、论文证据、为何可能不同、实验推理证据链、Context Matrix、人工审核、局部路径组织。Reasoning 只渲染已有 trace；缺失时明确“该运行未生成全文推理证据链”，不从摘要补齐。Context 默认只展示有信息增益的列，可切换完整矩阵；差异有文字标记，来源层显示为 claim-derived、reasoning-derived、consolidated、conflicting 或 missing，整合值不覆盖原值。

Reviewer 保留已有三栏工作台、自动草稿与提交事务，把任务类型、Case、Subject/Relation/Object/Direction/Context、Evidence、Notes 和保存动作改为普通语言；schema id/version 对非 developer 隐藏。仲裁将 Reviewer A/B 改为审核者 A/B，字段名人类化，并把“指南歧义”写入可追溯说明。

Owner 首屏改为行动项优先，统计降到第二层；Evaluation 调用选中项目的真实 readiness API，逐项解释为什么不能运行，Pilot 与 Production 保持隔离，缺失状态不显示为 0。

Global Evidence Map 保持三级结构：11 个隔离 Case 概览 → 20–40 节点局部图 → 节点/边详情与 Dossier 入口；保留文本列表替代视图、渐进标签和键盘焦点。

## 术语表

| 内部术语 | 普通界面 |
|---|---|
| case | 研究问题 / 案例 |
| claim | 机制声明 |
| triple | 机制关系 |
| conflict | 证据冲突 |
| non-comparable | 实验条件不同，暂不可直接比较 |
| reasoning trace | 实验推理证据链 |
| context consolidation | 实验上下文整合 |
| review item | 审核任务 |
| assignment | 分配任务 |
| adjudication | 仲裁 |
| Gold | 金标准数据 |
| projection / ingestion | 仅技术详情中的投影版本 / 数据同步记录 |

## 视觉系统与渐进披露

设计 token 扩展了 4–48px spacing、三档 radius、focus ring、状态色；新增 research hero、Case/Dossier card、能力状态、answer panel、reasoning timeline、readiness/action list。状态同时使用图标、文字和颜色。1366 首屏优先显示产品定义和案例入口；900/520px 断点把 header、timeline、action list 与卡片变为单列。

信息按三层披露：Level 1 是研究问题和当前发现；Level 2 是论文证据、推理链、上下文与局部路径；Level 3 是仅 developer 可见的 ID、原始 JSON、投影和 provenance。Owner 的系统状态在独立页面，不进入总览首屏。

## 可用性任务与点击路径

| Persona / 任务 | 路径 | 关键点击 | 结果 |
|---|---|---:|---|
| 研究者：理解 Wnt 是否有正式冲突 | 登录 → 首页 Wnt 卡 → Case 当前发现 | 1 | 完成；卡片与 Case 均明确“当前未发现正式冲突” |
| 打开全文证据 Dossier | Case → 首个关键机制 → 论文证据 | 1（累计 2） | 完成；显示来源范围、论文标识与证据句 |
| 查看 Reasoning | Dossier → 本页推理链段落 | 0（滚动） | 完成；真实 trace 或明确 unavailable |
| 比较 Context | Dossier → Context → 完整矩阵 | 1 | 完成；简化/完整两层和 provenance |
| 从局部图查看机制 | 研究 → Evidence Map → Wnt 局部图 → 节点/边详情 | 2–3 | 完成；详情提供 Dossier 入口 |
| Reviewer：找到任务并提交 | Review → Case layer → task → label → submit | 3 | 完成；草稿刷新恢复由既有 E2E 覆盖 |
| Owner：邀请码 | Owner → 邀请码 → 创建 | 2 | 完成；明文只显示一次 |
| Owner：进度/仲裁/Gold/Evaluation | Owner 行动项或侧栏 → 对应页 | 1 | 完成；Gold 和 Evaluation 显示阻塞原因 |

浏览任务没有要求查看 raw JSON 或 developer 字段。Wnt 从首页一次点击进入 Case，满足三次点击内到达。

## 修改文件

- `src/code_engine/system_b/explorer/explorer_api.py`
- `src/code_engine/system_b/explorer/dossier_projection.py`
- `src/code_engine/system_b/explorer/static/app.js`
- `src/code_engine/system_b/explorer/static/style.css`
- `src/code_engine/system_b/explorer/static/design_tokens.css`
- `tests/browser/start_atlas_server.py`
- `tests/browser/atlas_pilot.spec.js`
- `tests/browser/human_centered_redesign.spec.js`
- `tests/test_code_atlas_human_centered_redesign.py`
- 本报告

## 验证、截图与边界

浏览器使用真实当前 11-case 投影和临时 SQLite 数据库；写操作只发生在临时库。截图和 trace 位于 gitignored 的 `test-results/human-centered-redesign/` 与 `test-results/browser/`。

关键截图：`01-login.png`、`02-home.png`、`03-case-cards.png`、`04-wnt-case-overview.png`、`05-dossier.png`、`06-reasoning-trace.png`、`07-context-matrix.png`、`08-review-task.png`、`09-owner-dashboard.png`、`10-adjudication.png`、`11-evaluation-readiness.png`、`12-global-case-overview.png`、`13-single-case-map.png`、`14-node-detail.png`、`15-empty-state.png`、`16-error-state.png`。

已确认：认证未关闭；普通 Reviewer 无 Owner/Console 权限；Owner 无 Console 权限；developer 可查看 Console；没有第二个 owner；没有运行 System A 或 LLM；没有写入/重建持久库；没有改变科学符号和冲突 eligibility。

## 剩余问题与真实用户验证

- Case 常见上下文目前按已同步字段频次确定性汇总，尚未做字段级别的科研价值排序。
- Context 的“选择两行”已有可访问选择控件，但专用并排抽屉仍待实现；当前可在表内核对。
- Library 仍是浏览器本地收藏，跨设备同步未实现。
- Export UI 明确显示 `not_implemented`；未伪造导出成功。
- 需要药学生验证人类可读关系词是否足够准确，Reviewer 验证复杂 schema 的说明长度，专家验证“指南歧义”分类是否覆盖真实原因。

## 验收结论

A. 首次接触的药学生可以从首页产品定义、三步起点和研究问题卡理解用途。  
B. 研究者一次点击进入目标 Case。  
C. Dossier 无需 raw JSON 即可理解证据、差异、推理和人工状态。  
D. Reviewer 的核心任务可在没有开发人员解释的情况下完成，但仍需真实学生做措辞验证。  
E. Owner 首屏直接显示下一步行动及可点击入口。  
F. 核心纵向流程已从开发者查看器转为面向人的科研工作台；Library 跨设备、Context 专用双行抽屉与 Export 仍是明确未完成项。
