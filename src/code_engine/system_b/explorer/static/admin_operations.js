(function () {
  "use strict";

  const ROLE_LABELS = {
    researcher: "科研阅读者", reviewer: "Reviewer", adjudicator: "Adjudicator",
    developer: "开发者", admin: "管理员", owner: "Owner", pharma: "药学阅读者"
  };
  const STATUS_LABELS = {
    active: "正常", pending_first_login: "待完成注册", disabled: "已禁用", locked: "已锁定",
    assigned: "进行中", completed: "已完成", draft: "草稿", temporary_password: "临时密码",
    never_logged_in: "从未登录", complete: "已完成注册"
  };
  const operationState = {
    actor: "admin", userData: null, selectedUsers: new Set(),
    userSummaryFilter: "",
    assignment: { step: 1, source: "existing_review_items", strategy: "workload_balance", itemIds: [], preview: null },
    sampling: { step: 1, purpose: "", preview: null, frame: null }
  };

  function prefix() { return operationState.actor === "owner" ? "/api/owner/operations" : "/api/admin"; }
  function samplingPrefix() { return operationState.actor === "owner" ? "/api/owner/sampling" : "/api/admin/sampling"; }
  function roleLabel(value) { return ROLE_LABELS[value] || value || "未设置"; }
  function statusLabel(value) { return STATUS_LABELS[value] || value || "未知"; }
  function fmtDate(value) {
    if (!value) return "从未";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "未知" : date.toLocaleDateString("zh-CN", { year: "numeric", month: "short", day: "numeric" });
  }
  function percent(value) { return value === null || value === undefined ? "尚无进度" : Math.round(value * 100) + "%"; }
  function emptyState(titleText, detail, action) {
    return '<div class="operations-empty"><h3>' + esc(titleText) + '</h3><p>' + esc(detail) + '</p>' + (action || "") + "</div>";
  }
  function alertList(rows, kind) {
    if (!rows || !rows.length) return "";
    return '<div class="validation-list ' + kind + '">' + rows.map(function (row) {
      return '<div><strong>' + (kind === "blockers" ? "阻断" : "提醒") + '</strong><span>' + esc(row.message || row.code) + "</span></div>";
    }).join("") + "</div>";
  }
  function loading(host, message) {
    host.innerHTML = '<div class="operations-loading" role="status"><span class="loading-dot"></span><p>' + esc(message || "正在读取运营数据…") + "</p></div>";
  }
  function shell(actor, active, body) {
    operationState.actor = actor;
    const common = [
      ["overview", "运营总览"], ["users", "用户与访问"], ["projects", "项目"],
      ["assignments", "任务与批次"], ["sampling", "抽样与数据集"], ["progress", "进度"], ["invites", "邀请与注册"]
    ];
    const ownerOnly = [
      ["gold", "Gold"], ["evaluation", "Evaluation"], ["quality", "Quality"],
      ["audit", "Audit"], ["exports", "Export"], ["system", "System State"]
    ];
    const base = actor === "owner" ? "/owner/" : "/admin/";
    const nav = common.concat(actor === "owner" ? ownerOnly : []);
    return '<div class="owner-shell operations-shell"><aside class="owner-side" aria-label="' + (actor === "owner" ? "Owner" : "Admin") + ' 运营导航">' +
      nav.map(function (row) { return '<a class="' + (active === row[0] ? "active" : "") + '" href="' + base + row[0] + '">' + esc(row[1]) + "</a>"; }).join("") +
      '</aside><main class="owner-main operations-main">' + (actor === "owner" ? '<div id="owner-page-body"><div id="operations-page">' : '<div id="operations-page">') + (body || "") + (actor === "owner" ? "</div></div>" : "</div>") + "</main></div>";
  }

  async function renderOverview(host) {
    loading(host);
    const endpoint = operationState.actor === "owner" ? "/api/owner/overview" : "/api/admin/overview";
    const raw = await api(endpoint);
    const data = operationState.actor === "owner" ? (raw.operations || {}) : raw;
    const cards = [
      ["pending_registration", "待完成注册", "users?onboarding=never_logged_in"],
      ["temporary_password_pending", "尚未修改临时密码", "users?onboarding=temporary_password"],
      ["never_logged_in", "从未登录", "users?onboarding=never_logged_in"],
      ["active_reviewer_count", "当前活跃 Reviewer", "users?role=reviewer&enabled=true"],
      ["active_adjudicator_count", "当前活跃 Adjudicator", "users?role=adjudicator&enabled=true"],
      ["reviewers_without_assignments", "没有任务的 Reviewer", "users?role=reviewer&has_tasks=false"],
      ["users_with_unstarted_tasks", "任务未开始用户", "users?has_tasks=true"],
      ["second_review_backlog", "等待第二审核", "progress?status=secondary"],
      ["waiting_adjudication", "等待仲裁", "progress?status=adjudication"],
      ["pilot_project_count", "当前 Pilot 数", "projects"],
      ["draft_sampling_batches", "抽样批次草稿", "sampling"],
      ["blocked_batch_count", "存在阻断的批次", "assignments?status=blocked"]
    ];
    const actions = [];
    if (data.never_logged_in) actions.push([data.never_logged_in + " 位用户从未登录", "users?onboarding=never_logged_in"]);
    if (data.reviewers_without_assignments) actions.push([data.reviewers_without_assignments + " 位 Reviewer 有 0 个任务", "users?role=reviewer&has_tasks=false"]);
    if (data.second_review_backlog) actions.push([data.second_review_backlog + " 条任务等待 Secondary", "progress?status=secondary"]);
    if (data.waiting_adjudication) actions.push([data.waiting_adjudication + " 条分歧等待仲裁", "progress?status=adjudication"]);
    if (data.sampling_frame_status === "missing") actions.push(["Sampling Frame 当前不可用", "sampling"]);
    const base = operationState.actor === "owner" ? "/owner/" : "/admin/";
    host.innerHTML = (operationState.actor === "owner" ? '<h2 class="workspace-identity">Owner 工作台</h2>' : "") +
      '<section class="operations-hero owner-action-hero"><div><span class="eyebrow">运营总览</span><h2>今天需要处理什么？</h2><p>从用户、抽样到双人审核，按阻断优先级推进 Pilot。</p></div><a class="button light" href="' + base + 'assignments">创建审核批次</a></section>' +
      '<section aria-labelledby="action-title"><div class="section-heading"><div><h2 id="action-title">需要处理</h2><p>点击行动项进入已过滤页面。</p></div><span class="freshness">刚刚更新 · <button class="link-button" onclick="route()">刷新</button></span></div>' +
      (actions.length ? '<div class="action-list">' + actions.map(function (row) { return '<a href="' + base + row[1] + '"><span>' + esc(row[0]) + '</span><b>处理 →</b></a>'; }).join("") + "</div>" :
        emptyState("当前没有紧急行动项", "可以继续设计抽样方案或检查项目覆盖。", '<a class="button-sm" href="' + base + 'sampling">查看抽样与数据集</a>')) + "</section>" +
      '<section><div class="section-heading"><div><h2>运营状态</h2><p>只显示行动所需的计数，不展示数据库内部字段。</p></div></div><div class="operations-metric-grid">' +
      cards.map(function (row) {
        return '<a class="ops-metric-card" href="' + base + row[2] + '"><strong>' + esc(data[row[0]] || 0) + '</strong><span>' + esc(row[1]) + '</span><small>查看详情 →</small></a>';
      }).join("") + "</div></section>";
  }

  function userSummary(summary) {
    const cards = [
      ["all", "全部用户"], ["enabled", "已启用"], ["pending_registration", "待完成注册"],
      ["never_logged_in", "从未登录"], ["with_tasks", "当前有任务"],
      ["reviewers_without_tasks", "无任务 Reviewer"], ["adjudication_pending", "待仲裁任务用户"], ["disabled", "已禁用"]
    ];
    return '<div class="user-summary">' + cards.map(function (row) {
      return '<button type="button" data-user-summary="' + row[0] + '"><strong>' + esc(summary[row[0]] || 0) + '</strong><span>' + row[1] + "</span></button>";
    }).join("") + "</div>";
  }
  function userRows(items) {
    if (!items.length) return '<tr><td colspan="10">' + emptyState("没有符合条件的用户", "调整搜索或筛选条件后重试。", '<button class="button-sm" type="button" data-clear-user-filters>清除筛选</button>') + "</td></tr>";
    return items.map(function (user) {
      const warning = user.account_warning ? '<span class="account-warning">' + esc(user.account_warning) + "</span>" : "";
      const initials = (user.display_name || user.username || "?").trim().slice(0, 1).toUpperCase();
      return '<tr data-user-row="' + esc(user.user_id) + '"><td><input class="user-check" type="checkbox" aria-label="选择 ' + esc(user.display_name) + '" value="' + esc(user.user_id) + '" ' + (user.role === "owner" ? "disabled" : "") + "></td>" +
        '<td><button class="person-link" type="button" data-open-user="' + esc(user.user_id) + '"><span class="person-avatar" aria-hidden="true">' + esc(initials) + '</span><span><strong>' + esc(user.display_name) + '</strong><small>@' + esc(user.username) + " · " + esc(statusLabel(user.onboarding_status)) + "</small></span></button></td>" +
        '<td><span class="role-chip role-' + esc(user.role) + '">' + esc(roleLabel(user.role)) + "</span></td>" +
        '<td><span class="status-pill status-' + esc(user.status) + '">' + esc(statusLabel(user.status)) + "</span>" + warning + "</td>" +
        "<td>" + esc(user.pending_assignment_count || 0) + "</td><td>" + esc(user.completed_assignment_count || 0) + "</td>" +
        "<td>" + esc(user.adjudication_pending || 0) + "</td><td>" + esc((user.current_project_names || []).join("、") || "—") + "</td><td>" + esc(fmtDate(user.last_activity_at || user.last_login_at)) + "</td>" +
        '<td><button class="button-sm" type="button" data-open-user="' + esc(user.user_id) + '">查看</button></td></tr>';
    }).join("");
  }
  function clearUserFilters() {
    operationState.userSummaryFilter = "";
    ["#user-search", "#user-role-filter", "#user-status-filter", "#user-onboarding-filter", "#user-task-filter", "#user-project-filter", "#user-activity-filter"].forEach(function (selector) {
      const field = document.querySelector(selector);
      if (field) field.value = "";
    });
    const sort = document.querySelector("#user-sort");
    if (sort) sort.value = "username";
    applyUserFilters();
  }
  function applyUserFilters() {
    const data = operationState.userData;
    if (!data) return;
    const search = (document.querySelector("#user-search").value || "").toLowerCase();
    const role = document.querySelector("#user-role-filter").value;
    const status = document.querySelector("#user-status-filter").value;
    const onboarding = document.querySelector("#user-onboarding-filter").value;
    const tasks = document.querySelector("#user-task-filter").value;
    const project = document.querySelector("#user-project-filter").value;
    const activity = document.querySelector("#user-activity-filter").value;
    const sort = document.querySelector("#user-sort").value;
    const summary = operationState.userSummaryFilter;
    const cutoff = activity ? Date.now() - Number(activity) * 86400000 : 0;
    const filtered = data.items.filter(function (user) {
      const haystack = [user.username, user.display_name, roleLabel(user.role)].concat(user.current_project_names || []).join(" ").toLowerCase();
      const summaryMatch = !summary || summary === "all" ||
        (summary === "enabled" && user.enabled) ||
        (summary === "pending_registration" && user.onboarding_status !== "complete") ||
        (summary === "never_logged_in" && !user.last_login_at) ||
        (summary === "with_tasks" && user.pending_assignment_count > 0) ||
        (summary === "reviewers_without_tasks" && user.role === "reviewer" && user.enabled && !user.pending_assignment_count) ||
        (summary === "adjudication_pending" && user.adjudication_pending > 0) ||
        (summary === "disabled" && !user.enabled);
      const activityTime = new Date(user.last_activity_at || user.last_login_at || 0).getTime();
      return summaryMatch && (!search || haystack.includes(search)) && (!role || user.role === role) &&
        (!status || String(user.enabled) === status) && (!onboarding || user.onboarding_status === onboarding) &&
        (!tasks || String(Boolean(user.pending_assignment_count)) === tasks) &&
        (!project || (user.active_projects || []).some(function (row) { return row.project_id === project; })) &&
        (!activity || (activity === "never" ? !user.last_activity_at && !user.last_login_at : activityTime >= cutoff));
    });
    const sorters = {
      pending_desc: function (a, b) { return b.pending_assignment_count - a.pending_assignment_count; },
      completed_desc: function (a, b) { return b.completed_assignment_count - a.completed_assignment_count; },
      recent_desc: function (a, b) { return String(b.last_activity_at || "").localeCompare(String(a.last_activity_at || "")); },
      created_desc: function (a, b) { return String(b.created_at || "").localeCompare(String(a.created_at || "")); },
      username: function (a, b) { return a.username.localeCompare(b.username); }
    };
    filtered.sort(sorters[sort] || sorters.username);
    document.querySelector("#user-table-body").innerHTML = userRows(filtered);
    document.querySelectorAll("[data-user-summary]").forEach(function (button) {
      button.classList.toggle("active", button.dataset.userSummary === (summary || "all"));
    });
  }
  async function renderUsers(host) {
    loading(host, "正在汇总用户身份、任务和最近活动…");
    const endpoint = operationState.actor === "owner" ? "/api/owner/operations/users" : "/api/admin/users";
    const data = await api(endpoint);
    operationState.userData = data;
    const projects = [];
    (data.items || []).forEach(function (user) {
      (user.active_projects || []).forEach(function (project) {
        if (!projects.some(function (row) { return row.project_id === project.project_id; })) projects.push(project);
      });
    });
    const quickRoles = ["researcher", "reviewer", "adjudicator"].concat(operationState.actor === "owner" ? ["developer", "admin"] : []);
    host.innerHTML = '<section class="operations-page-head"><div><span class="eyebrow">用户与访问</span><h2>用户总览</h2><p>快速识别未登录、无任务和负载异常用户。</p></div><div class="quick-create"><h2>创建普通账号</h2><label>角色<select id="admin-role">' + quickRoles.map(function (role) { return '<option value="' + role + '">' + roleLabel(role) + "</option>"; }).join("") + '</select></label><button class="button" type="button" id="open-create-user">创建用户</button></div></section>' +
      userSummary(data.summary || {}) +
      '<section class="filter-card" aria-label="用户筛选"><label class="search-field">搜索用户或项目<input id="user-search" placeholder="用户名、显示名称、角色或项目"></label>' +
      '<label>角色<select id="user-role-filter"><option value="">全部角色</option><option value="reviewer">审核员</option><option value="adjudicator">仲裁员</option><option value="researcher">科研阅读者</option><option value="admin">管理员</option></select></label>' +
      '<label>启用状态<select id="user-status-filter"><option value="">全部状态</option><option value="true">已启用</option><option value="false">已禁用</option></select></label>' +
      '<label>Onboarding<select id="user-onboarding-filter"><option value="">全部</option><option value="temporary_password">尚未修改临时密码</option><option value="never_logged_in">从未登录</option><option value="complete">已完成</option></select></label>' +
      '<label>任务<select id="user-task-filter"><option value="">全部</option><option value="true">有任务</option><option value="false">无任务</option></select></label></section>' +
      '<section class="filter-card secondary-filters" aria-label="更多用户筛选"><label>当前项目<select id="user-project-filter"><option value="">全部项目</option>' + projects.map(function (project) { return '<option value="' + esc(project.project_id) + '">' + esc(project.name) + "</option>"; }).join("") + '</select></label><label>最近活动<select id="user-activity-filter"><option value="">不限</option><option value="7">最近 7 天</option><option value="30">最近 30 天</option><option value="never">从未活动</option></select></label><label>排序<select id="user-sort"><option value="username">用户名</option><option value="pending_desc">待办最多</option><option value="completed_desc">完成最多</option><option value="recent_desc">最近活动</option><option value="created_desc">创建时间</option></select></label><button class="button-sm" type="button" data-clear-user-filters>清除筛选</button></section>' +
      '<div class="bulk-bar" id="bulk-bar"><span><b id="selected-user-count">0</b> 位用户已选择</span><a class="button-sm" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'invites">批量邀请</a><button class="button-sm" type="button" data-bulk-to-pilot>批量加入 Pilot</button><button class="button-sm" type="button" data-bulk-action="enable">批量启用</button><button class="button-sm danger-outline" type="button" data-bulk-action="disable">批量禁用</button><button class="button-sm" type="button" onclick="window.print()">批量导出进度</button></div>' +
      '<div class="table-scroll operations-table"><table><thead><tr><th><span class="sr-only">选择</span></th><th>用户</th><th>角色</th><th>账号状态</th><th>当前待办</th><th>已完成</th><th>待仲裁</th><th>当前项目</th><th>最近活动</th><th>操作</th></tr></thead><tbody id="user-table-body">' + userRows(data.items || []) + "</tbody></table></div>" +
      '<div id="user-drawer-backdrop" class="drawer-backdrop" hidden></div><aside id="user-drawer" class="user-drawer" aria-label="用户详情" aria-hidden="true"></aside>';
    ["#user-search", "#user-role-filter", "#user-status-filter", "#user-onboarding-filter", "#user-task-filter", "#user-project-filter", "#user-activity-filter", "#user-sort"].forEach(function (selector) {
      document.querySelector(selector).addEventListener(selector === "#user-search" ? "input" : "change", applyUserFilters);
    });
    const params = new URLSearchParams(location.search);
    if (params.get("role")) document.querySelector("#user-role-filter").value = params.get("role");
    if (params.get("enabled")) document.querySelector("#user-status-filter").value = params.get("enabled");
    if (params.get("onboarding")) document.querySelector("#user-onboarding-filter").value = params.get("onboarding");
    if (params.get("has_tasks")) document.querySelector("#user-task-filter").value = params.get("has_tasks");
    applyUserFilters();
  }
  function closeUserDrawer() {
    const drawer = document.querySelector("#user-drawer"), backdrop = document.querySelector("#user-drawer-backdrop");
    if (!drawer) return;
    drawer.classList.remove("open"); drawer.setAttribute("aria-hidden", "true"); backdrop.hidden = true;
  }
  async function openUserDrawer(userId) {
    const user = (operationState.userData.items || []).find(function (row) { return row.user_id === userId; });
    if (!user) return;
    const workloadEndpoint = operationState.actor === "owner"
      ? "/api/owner/operations/users/" + encodeURIComponent(userId) + "/workload"
      : "/api/admin/users/" + encodeURIComponent(userId) + "/workload";
    let workload = {
      pending: user.pending_assignment_count || 0,
      completed: user.completed_assignment_count || 0,
      revisit: user.revisit_assignment_count || 0,
      adjudication_pending: user.adjudication_pending || 0,
      recent_7_days_completed: user.recent_7_days_completed || 0,
      assignment_role_distribution: user.assignment_role_distribution || {},
      domain_distribution: user.domain_distribution || {},
      case_distribution: user.case_distribution || {},
      projects: user.active_projects || []
    };
    try { workload = await api(workloadEndpoint); } catch (_) { /* Keep the safe list summary as a degraded state. */ }
    const mutable = Boolean(user.admin_mutable);
    const roleOptions = ["researcher", "reviewer", "adjudicator"].concat(operationState.actor === "owner" ? ["developer", "admin"] : []);
    const drawer = document.querySelector("#user-drawer");
    drawer.innerHTML = '<header><div><span class="eyebrow">用户详情</span><h2>' + esc(user.display_name) + '</h2><p>@' + esc(user.username) + '</p></div><button class="close-drawer" type="button" aria-label="关闭用户详情">×</button></header>' +
      '<div class="drawer-sections"><section><h3>基本资料</h3><dl><div><dt>角色</dt><dd>' + esc(roleLabel(user.role)) + '</dd></div><div><dt>账号状态</dt><dd>' + esc(statusLabel(user.status)) + '</dd></div><div><dt>Onboarding</dt><dd>' + esc(statusLabel(user.onboarding_status)) + '</dd></div><div><dt>最近登录</dt><dd>' + esc(fmtDate(user.last_login_at)) + "</dd></div></dl></section>" +
      '<section><h3>当前项目与任务负载</h3><div class="drawer-metrics"><div><strong>' + esc(workload.pending || 0) + '</strong>待审核</div><div><strong>' + esc(workload.completed || 0) + '</strong>已提交</div><div><strong>' + esc(workload.revisit || 0) + '</strong>稍后处理</div><div><strong>' + esc(workload.adjudication_pending || 0) + '</strong>待仲裁</div><div><strong>' + esc((workload.projects || []).length) + '</strong>参与项目</div><div><strong>' + esc(workload.recent_7_days_completed || 0) + '</strong>最近 7 天完成</div></div><p>' + esc((user.current_project_names || []).join("、") || "尚未加入项目") + "</p></section>" +
      '<section><h3>任务来源分布</h3><div class="distribution-chips">' + ["primary", "secondary", "adjudicator"].map(function (role) { return '<span><b>' + esc((workload.assignment_role_distribution || {})[role] || 0) + "</b>" + esc(role === "primary" ? "Primary" : role === "secondary" ? "Secondary" : "Adjudicator") + "</span>"; }).join("") + '</div><details><summary>按 Domain / Case 查看</summary><p><b>Domain：</b>' + esc(Object.entries(workload.domain_distribution || {}).map(function (row) { return row[0] + " " + row[1]; }).join("、") || "暂无") + '</p><p><b>Case：</b>' + esc(Object.entries(workload.case_distribution || {}).map(function (row) { return row[0] + " " + row[1]; }).join("、") || "暂无") + "</p></details></section>" +
      '<section><h3>角色与权限</h3>' + (mutable ? '<label>修改普通角色<select id="drawer-role" data-current-role="' + esc(user.role) + '">' + roleOptions.map(function (role) { return '<option value="' + role + '" ' + (role === user.role ? "selected" : "") + ">" + roleLabel(role) + "</option>"; }).join("") + '</select></label><div id="role-impact" class="impact-box"><strong id="role-change-title">' + esc(roleLabel(user.role)) + ' → ' + esc(roleLabel(user.role)) + '</strong><ul><li>当前登录 Session 将失效</li><li id="role-workspace-impact">下次登录进入对应角色工作台</li><li>现有 Assignment 不会自动删除</li><li>新角色不会自动获得其他项目权限</li></ul></div><button class="button-sm" data-change-role="' + esc(user.user_id) + '">确认修改角色</button>' : '<div class="protected-note">该账号受保护，当前运营角色不能修改。</div>') + "</section>" +
      '<section><h3>运营操作</h3><div class="drawer-actions"><a class="button-sm" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'assignments?assignee=' + encodeURIComponent(user.user_id) + '">给该用户分配任务</a><a class="button-sm" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'progress?user=' + encodeURIComponent(user.user_id) + '">查看该用户任务</a></div></section>' +
      '<section><h3>账号安全</h3><div class="drawer-actions">' + (mutable ? '<button class="button-sm" data-user-action="revoke-sessions" data-user-id="' + esc(user.user_id) + '">撤销所有 Session</button><button class="button-sm" data-user-action="issue-password-reset" data-user-id="' + esc(user.user_id) + '">生成密码重置链接</button><a class="button-sm" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'invites?role=' + encodeURIComponent(user.role) + '">重新发送邀请</a><button class="button-sm danger-outline" data-user-action="' + (user.enabled ? "disable" : "enable") + '" data-user-id="' + esc(user.user_id) + '">' + (user.enabled ? "禁用账号" : "启用账号") + "</button>" : "") + "</div></section>" +
      '<details><summary>高级信息</summary><dl><div><dt>User ID</dt><dd><code>' + esc(user.user_id) + '</code></dd></div><div><dt>创建时间</dt><dd>' + esc(fmtDate(user.created_at)) + "</dd></div><div><dt>内部角色</dt><dd>" + esc(user.role) + "</dd></div><div><dt>Audit reference</dt><dd><code>" + esc(user.audit_reference || "—") + "</code></dd></div></dl></details></div>";
    document.querySelector("#user-drawer-backdrop").hidden = false;
    drawer.classList.add("open"); drawer.setAttribute("aria-hidden", "false"); drawer.querySelector(".close-drawer").focus();
  }

  async function userAction(userId, action, body) {
    const base = operationState.actor === "owner" ? "/api/owner/user/" : "/api/admin/user/";
    if (action === "disable" && !confirm("确认禁用该用户？其现有 Session 将失效，开放任务不会自动转移。")) return;
    try {
      const result = await apiPost(base + encodeURIComponent(userId) + "/" + action, body || {});
      if (result.reset_link) {
        const box = document.createElement("div"); box.className = "credential-box"; box.innerHTML = '<strong>重置链接仅本次显示</strong><code>' + esc(result.reset_link) + "</code>";
        document.querySelector(".user-drawer .drawer-sections").prepend(box);
      } else {
        showToast("用户账号已更新", "success"); await renderUsers(document.querySelector("#operations-page"));
      }
    } catch (error) { showToast("操作未完成：" + error.message, "error"); }
  }
  function openCreateUser() {
    const drawer = document.querySelector("#user-drawer");
    const roles = ["researcher", "reviewer", "adjudicator"].concat(operationState.actor === "owner" ? ["developer", "admin"] : []);
    drawer.innerHTML = '<header><div><span class="eyebrow">用户与访问</span><h2>创建用户</h2><p>临时密码只显示一次。</p></div><button class="close-drawer" type="button" aria-label="关闭用户详情">×</button></header><div class="drawer-sections"><section><label>用户名<input id="create-user-username" autocomplete="off"></label><label>显示名称<input id="create-user-display"></label><label>普通角色<select id="create-user-role">' + roles.map(function (role) { return '<option value="' + role + '">' + roleLabel(role) + "</option>"; }).join("") + '</select></label><p class="scientific-boundary">Admin 不能创建 Owner、Admin 或 Developer；后端会再次校验角色。</p><button class="button" type="button" data-create-user-submit>创建用户</button><div id="create-user-result"></div></section></div>';
    document.querySelector("#user-drawer-backdrop").hidden = false;
    drawer.classList.add("open"); drawer.setAttribute("aria-hidden", "false");
    const quickRole = document.querySelector("#admin-role");
    if (quickRole && drawer.querySelector("#create-user-role option[value='" + quickRole.value + "']")) {
      drawer.querySelector("#create-user-role").value = quickRole.value;
    }
    drawer.querySelector("#create-user-username").focus();
  }
  async function createUser() {
    const endpoint = operationState.actor === "owner" ? "/api/owner/users" : "/api/admin/users";
    try {
      const result = await apiPost(endpoint, {
        username: document.querySelector("#create-user-username").value,
        display_name: document.querySelector("#create-user-display").value,
        role: document.querySelector("#create-user-role").value
      });
      document.querySelector("#create-user-result").innerHTML = '<div class="credential-box"><strong>临时密码仅本次显示</strong><code>' + esc(result.temporary_password) + "</code></div>";
    } catch (error) {
      document.querySelector("#create-user-result").innerHTML = '<div class="error">' + esc(error.message) + "</div>";
    }
  }
  async function changeRole(userId) {
    const role = document.querySelector("#drawer-role").value;
    if (!confirm("确认修改角色？当前 Session 将失效，现有 Assignment 不会自动删除。")) return;
    await userAction(userId, "change-role", { role: role });
  }
  async function bulkAction(action) {
    const ids = Array.from(operationState.selectedUsers);
    if (!ids.length) return showToast("请先选择用户", "error");
    const verb = action === "disable" ? "禁用" : "启用";
    if (!confirm("确认批量" + verb + " " + ids.length + " 位用户？将重新校验权限并使 " + ids.length + " 个 Session 版本失效。")) return;
    const endpoint = operationState.actor === "owner" ? "/api/owner/operations/users/bulk" : "/api/admin/users/bulk";
    try { await apiPost(endpoint, { user_ids: ids, action: action }); operationState.selectedUsers.clear(); showToast("批量操作已完成", "success"); await renderUsers(document.querySelector("#operations-page")); }
    catch (error) { showToast("批量操作未完成：" + error.message, "error"); }
  }

  async function renderProjects(host) {
    loading(host);
    const endpoint = operationState.actor === "owner" ? "/api/owner/projects" : "/api/admin/projects";
    const data = await api(endpoint);
    const compatibilityPreview = operationState.actor === "owner"
      ? '<section class="card pilot-count-explainer"><h2>Pilot Setup Preview</h2><p>在创建批次前核对 Case 与 Review Item 两种不同口径。</p><button class="button-sm" type="button" id="preview-pilot-counts">Preview assignments</button><div id="pilot-preview" aria-live="polite"></div></section>'
      : "";
    host.innerHTML = '<section class="operations-page-head"><div><span class="eyebrow">项目</span><h2>' + (operationState.actor === "admin" ? "创建 Pilot 与双人任务" : "选择要运营的项目") + '</h2><p>Admin 仅能继续 Pilot；Owner 可查看 Production 治理状态。</p></div><a class="button" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'assignments">创建审核批次</a></section>' +
      compatibilityPreview +
      ((data.items || []).length ? '<div class="project-card-grid">' + data.items.map(function (project) {
        const canContinue = project.can_create_batch !== false && project.status === "active" && (operationState.actor === "owner" || project.namespace === "pilot");
        return '<article class="project-card"><header><span class="namespace-pill ' + esc(project.namespace) + '">' + (project.namespace === "pilot" ? "Pilot" : "Production") + '</span><span class="status-pill">' + esc(statusLabel(project.status)) + '</span></header><h3>' + esc(project.name) + '</h3><div class="project-stats"><span><b>' + esc(project.unique_review_items || 0) + '</b> Review Items</span><span><b>' + esc(project.assignment_count || 0) + '</b> Assignments</span><span><b>' + esc(project.unique_cases || 0) + '</b> Cases</span></div><p>' + (canContinue ? "可以继续分配任务" : "当前项目不可继续分配") + '</p><a class="button-sm ' + (canContinue ? "" : "disabled") + '" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'assignments?project=' + encodeURIComponent(project.project_id) + '">创建审核批次</a></article>';
      }).join("") + "</div>" : emptyState("还没有项目", "请先由有权限的用户建立 Pilot 项目。"));
  }

  function wizardSteps(current, labels) {
    return '<ol class="wizard-steps">' + labels.map(function (label, index) {
      const step = index + 1;
      return '<li class="' + (step === current ? "current" : step < current ? "done" : "") + '"><span>' + step + "</span><b>" + esc(label) + "</b></li>";
    }).join("") + "</ol>";
  }
  function assignmentBody(data) {
    const state = operationState.assignment, projects = data.projects || [], users = data.users || [];
    const reviewers = users.filter(function (row) { return row.enabled && row.role === "reviewer"; });
    const adjudicators = users.filter(function (row) { return row.enabled && ["reviewer", "adjudicator"].includes(row.role); });
    const project = projects.find(function (row) { return row.project_id === state.projectId; });
    let content = "";
    if (state.step === 1) {
      content = '<h3>选择项目</h3><p>选择一个状态正常、具有 Review Items 的项目。</p><div class="project-choice-grid">' + projects.map(function (row) {
        const disabled = row.status !== "active" || row.can_create_batch === false || (operationState.actor === "admin" && row.namespace !== "pilot");
        return '<button class="choice-card ' + (state.projectId === row.project_id ? "selected" : "") + '" type="button" data-assignment-project="' + esc(row.project_id) + '" ' + (disabled ? "disabled" : "") + '><span class="namespace-pill ' + esc(row.namespace) + '">' + esc(row.namespace === "pilot" ? "Pilot" : "Production") + '</span><strong>' + esc(row.name) + '</strong><small>' + esc(row.available_review_items || row.unique_review_items || 0) + ' Review Items · 已分配 ' + esc(row.assignment_count || 0) + ' · 完成 ' + esc(percent(row.completion_fraction)) + '</small><small>Schema：' + esc((row.schema_ids || []).join("、") || "缺失") + '</small><em>' + (disabled ? "阻断：" + esc((row.batch_creation_blockers || ["当前角色无权限"]).join("、")) : "可以继续分配") + "</em></button>";
      }).join("") + "</div>";
    } else if (state.step === 2) {
      const sources = [
        ["existing_review_items", "使用已有 Review Items", "适合对当前项目现有审核对象继续分配。"],
        ["sampling_batch", "使用已保存的抽样批次", "保留评估目的、Frame 与分布配置。"],
        ["source_units", "从 Source-unit Frame 创建", "用于穷尽标注 Gold，可支持 Precision / Recall / F1。"],
        ["predicted_claims", "从 Predicted Claims 创建", "用于 Claim Precision、字段正确性和 Evidence Grounding；不能单独评估 Recall / F1。"],
        ["case_manual", "按 Case 手动选择", "按研究 Case 组织任务。"],
        ["id_import", "导入 Review Item ID 列表", "仅用于已审核过的内部清单。"]
      ];
      const cases = Array.from(new Set((state.reviewItems || []).map(function (row) { return row.case_id; }))).sort();
      let sourceConfiguration = "";
      if (state.source === "case_manual") {
        sourceConfiguration = '<fieldset class="exclusion-grid"><legend>选择 Case</legend>' + cases.map(function (caseId) { return '<label><input type="checkbox" data-assignment-case value="' + esc(caseId) + '"> ' + esc(caseId) + "</label>"; }).join("") + "</fieldset>";
      } else if (state.source === "id_import") {
        sourceConfiguration = '<label class="id-import">导入 Review Item ID 列表<textarea id="assignment-id-import" rows="5" placeholder="每行一个 Review Item ID；只接受当前项目已有任务"></textarea></label>';
      } else if (state.source === "sampling_batch") {
        sourceConfiguration = state.samplingBatchId ? '<div class="seed-note"><strong>已载入抽样批次</strong><p>' + esc((state.itemIds || []).length) + ' 个 Review Items；无需复制 Batch ID。</p></div>' : '<div class="validation-list blockers"><div><strong>阻断</strong><span>请从“抽样与数据集”创建或复用抽样批次后进入。</span></div></div>';
      } else if (state.source === "source_units" || state.source === "predicted_claims") {
        sourceConfiguration = '<div class="seed-note"><strong>下一步：设计科学抽样</strong><p>继续后进入对应 Sampling Wizard；创建完成会自动返回并携带样本与 Frame 信息。</p></div>';
      }
      content = '<h3>选择任务来源</h3><div class="choice-grid">' + sources.map(function (row) {
        return '<button class="choice-card ' + (state.source === row[0] ? "selected" : "") + '" type="button" data-assignment-source="' + row[0] + '"><strong>' + row[1] + '</strong><span>' + row[2] + "</span></button>";
      }).join("") + '</div>' + sourceConfiguration + '<div class="scientific-boundary callout">Source-unit 抽样框为 <b>selected_for_l1_extraction</b>，不代表完整论文端到端 Recall。</div>';
    } else if (state.step === 3) {
      const options = function (rows, selected) { return '<option value="">请选择</option>' + rows.map(function (row) { return '<option value="' + esc(row.user_id) + '" ' + (selected === row.user_id ? "selected" : "") + ">" + esc(row.display_name) + " · 当前待办 " + esc(row.pending_assignment_count || 0) + "</option>"; }).join(""); };
      content = '<h3>选择人员和分配策略</h3><div class="assignment-people-grid"><label>Primary Reviewer<select id="assignment-primary">' + options(reviewers, state.primary) + '</select></label><label>Secondary Reviewer<select id="assignment-secondary">' + options(reviewers, state.secondary) + '</select></label><label>Adjudicator<select id="assignment-adjudicator">' + options(adjudicators, state.adjudicator) + '</select></label><label>分配策略<select id="assignment-strategy"><option value="workload_balance">按当前工作量平衡（推荐）</option><option value="even">均匀分配</option><option value="fixed_pair">固定双人组</option><option value="domain">按领域分组</option><option value="case">按 Case 分组</option><option value="paper">按 Paper 分组</option></select></label></div><div class="workload-hint">预览时会重新读取每位用户的当前待办，显示新增和分配后负载。</div>';
    } else if (state.step === 4) {
      if (!state.preview) content = '<div class="operations-loading"><span class="loading-dot"></span><p>正在重新校验项目、人员、重复任务和负载…</p></div>';
      else {
        const p = state.preview;
        content = '<h3>预览与校验</h3>' + alertList(p.blockers, "blockers") + alertList(p.warnings, "warnings") +
          '<div class="preview-metrics"><div><strong>' + esc(p.review_item_count) + '</strong>Review Items</div><div><strong>' + esc(p.assignment_count) + '</strong>Assignments</div><div><strong>' + esc(p.unique_domains) + '</strong>Domains</div><div><strong>' + esc(p.unique_cases) + '</strong>Cases</div><div><strong>' + esc(p.unique_papers) + '</strong>Papers</div><div><strong>' + esc(p.duplicate_assignments) + '</strong>重复任务</div></div>' +
          '<div class="table-scroll"><table><thead><tr><th>用户</th><th>职责</th><th>当前待办</th><th>新增</th><th>分配后待办</th></tr></thead><tbody>' + (p.workloads || []).map(function (row) { return "<tr><td>" + esc(row.display_name) + "</td><td>" + esc(row.role) + "</td><td>" + row.current_pending + "</td><td>+" + row.new_assignments + "</td><td><strong>" + row.pending_after + "</strong></td></tr>"; }).join("") + "</tbody></table></div>";
      }
    } else {
      const result = state.result;
      content = result ? '<div class="creation-result"><span class="success-mark">✓</span><h3>审核批次已创建</h3><p>' + esc(result.batch_name) + ' · ' + esc(result.project ? result.project.name : "") + '</p><div class="preview-metrics"><div><strong>' + esc(result.review_item_count) + '</strong>Review Items</div><div><strong>' + esc(result.assignment_count) + '</strong>Assignments</div><div><strong>' + esc(result.unique_domains) + '</strong>Domains</div><div><strong>' + esc(result.unique_cases) + '</strong>Cases</div><div><strong>' + esc(result.unique_papers) + '</strong>Papers</div><div><strong>' + esc(result.duplicate_assignments || 0) + '</strong>跳过重复</div></div><dl class="result-summary"><div><dt>任务来源</dt><dd>' + esc(result.source) + '</dd></div><div><dt>Primary / Secondary / Adjudicator</dt><dd>' + esc((result.workloads || []).map(function (row) { return row.display_name; }).join(" / ")) + '</dd></div><div><dt>创建时间</dt><dd>' + esc(fmtDate(result.created_at)) + '</dd></div><div><dt>创建者</dt><dd>' + esc(result.created_by || "—") + '</dd></div></dl><p>三个角色批次与全部 Assignments 已在同一事务中提交。</p><div class="toolbar"><a class="button" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'batches?batch=' + encodeURIComponent(result.batch_id) + '">查看批次</a><a class="button-sm" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'users">查看用户负载</a><a class="button-sm" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'progress">查看项目进度</a><button class="button-sm" data-copy-text="' + esc(result.batch_name + "：" + result.review_item_count + " Items，" + result.assignment_count + " Assignments") + '">复制批次摘要</button></div></div>' : '<div class="error">创建结果不可用，请返回预览重试。</div>';
    }
    return '<section class="wizard-card">' + wizardSteps(state.step, ["选择项目", "任务来源", "人员与策略", "预览校验", "创建结果"]) + '<div class="wizard-content">' + content + '</div><footer class="wizard-footer">' + (state.step > 1 && state.step < 5 ? '<button class="button-sm" type="button" data-assignment-back>上一步</button>' : "<span></span>") + (state.step < 4 ? '<button class="button" type="button" data-assignment-next ' + (state.step === 1 && !project ? "disabled" : "") + '>继续</button>' : state.step === 4 ? '<button class="button" type="button" data-assignment-create ' + ((!state.preview || state.preview.blocked) ? "disabled" : "") + '>确认创建审核批次</button>' : "") + "</footer></section>";
  }
  async function renderAssignments(host) {
    loading(host);
    const projectEndpoint = operationState.actor === "owner" ? "/api/owner/projects" : "/api/admin/projects";
    const userEndpoint = operationState.actor === "owner" ? "/api/owner/operations/users" : "/api/admin/users";
    const values = await Promise.all([api(projectEndpoint), api(userEndpoint)]);
    const state = operationState.assignment;
    try {
      const handoff = JSON.parse(sessionStorage.getItem("atlas_assignment_handoff") || "null");
      if (handoff) {
        Object.assign(state, handoff);
        sessionStorage.removeItem("atlas_assignment_handoff");
      }
    } catch (error) {}
    if (!state.projectId) state.projectId = new URLSearchParams(location.search).get("project") || "";
    state.data = { projects: values[0].items || [], users: values[1].items || [] };
    if (!state.projectId && state.source === "sampling_batch") {
      const recommended = state.data.projects.find(function (row) { return row.can_create_batch !== false && row.status === "active" && (operationState.actor === "owner" || row.namespace === "pilot"); });
      if (recommended) state.projectId = recommended.project_id;
    }
    host.innerHTML = '<section class="operations-page-head"><div><span class="eyebrow">任务与批次</span><h2>创建审核批次</h2><p>按运营任务完成选择、人员平衡和创建前校验，无需理解 Assignment 数据表。</p></div><a class="button-sm" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'batches">查看全部批次</a></section><div id="assignment-wizard">' + assignmentBody(state.data) + "</div>";
  }
  async function assignmentNext() {
    const state = operationState.assignment;
    if (state.step === 1) {
      if (!state.projectId) return;
      if (state.source !== "sampling_batch" || !(state.itemIds || []).length) {
        const endpoint = operationState.actor === "owner" ? "/api/owner/operations/review-items" : "/api/admin/review-items";
        const data = await api(endpoint + "?project_id=" + encodeURIComponent(state.projectId));
        state.reviewItems = data.items || [];
        state.itemIds = (data.items || []).map(function (row) { return row.review_item_id; });
      }
    }
    if (state.step === 2) {
      if (state.source === "source_units" || state.source === "predicted_claims") {
        sessionStorage.setItem("atlas_sampling_start_purpose", state.source === "predicted_claims" ? "predicted_claim_precision" : "source_unit_exhaustive_gold");
        sessionStorage.setItem("atlas_sampling_project", state.projectId);
        location.href = (operationState.actor === "owner" ? "/owner/" : "/admin/") + "sampling";
        return;
      }
      if (state.source === "sampling_batch" && !state.samplingBatchId) return showToast("请先创建或复用抽样批次", "error");
      if (state.source === "case_manual") {
        const selectedCases = Array.from(document.querySelectorAll("[data-assignment-case]:checked")).map(function (input) { return input.value; });
        if (!selectedCases.length) return showToast("请至少选择一个 Case", "error");
        state.itemIds = (state.reviewItems || []).filter(function (row) { return selectedCases.includes(row.case_id); }).map(function (row) { return row.review_item_id; });
      }
      if (state.source === "id_import") {
        const allowed = new Set((state.reviewItems || []).map(function (row) { return row.review_item_id; }));
        state.itemIds = (document.querySelector("#assignment-id-import").value || "").split(/\r?\n|,/).map(function (value) { return value.trim(); }).filter(function (value) { return value && allowed.has(value); });
        if (!state.itemIds.length) return showToast("没有可用于当前项目的 Review Item ID", "error");
      }
    }
    if (state.step === 3) {
      state.primary = document.querySelector("#assignment-primary").value;
      state.secondary = document.querySelector("#assignment-secondary").value;
      state.adjudicator = document.querySelector("#assignment-adjudicator").value;
      state.strategy = document.querySelector("#assignment-strategy").value;
      state.step = 4; state.preview = null;
      document.querySelector("#assignment-wizard").innerHTML = assignmentBody(state.data);
      const endpoint = operationState.actor === "owner" ? "/api/owner/operations/batches/preview" : "/api/admin/batches/preview";
      try {
        state.preview = await apiPost(endpoint, {
          project_id: state.projectId, item_ids: state.itemIds, primary_reviewer_user_id: state.primary,
          secondary_reviewer_user_id: state.secondary, adjudicator_user_id: state.adjudicator,
          strategy: state.strategy, source: state.source, sampling_batch_id: state.samplingBatchId || "",
          expected_frame_hash: state.expectedFrameHash || ""
        });
      } catch (error) { state.preview = { blocked: true, blockers: [{ message: error.message }], warnings: [] }; }
      document.querySelector("#assignment-wizard").innerHTML = assignmentBody(state.data); return;
    }
    state.step += 1;
    document.querySelector("#assignment-wizard").innerHTML = assignmentBody(state.data);
  }
  async function createAssignment() {
    const state = operationState.assignment, endpoint = operationState.actor === "owner" ? "/api/owner/operations/batches" : "/api/admin/batches";
    const project = state.data.projects.find(function (row) { return row.project_id === state.projectId; });
    try {
      state.result = await apiPost(endpoint, {
        batch_name: (project ? project.name : "Pilot") + " · 审核批次",
        project_id: state.projectId, item_ids: state.itemIds, primary_reviewer_user_id: state.primary,
        secondary_reviewer_user_id: state.secondary, adjudicator_user_id: state.adjudicator,
        strategy: state.strategy, source: state.source, sampling_batch_id: state.samplingBatchId || "",
        expected_frame_hash: state.expectedFrameHash || ""
      });
      state.step = 5; document.querySelector("#assignment-wizard").innerHTML = assignmentBody(state.data);
    } catch (error) {
      state.preview = { blocked: true, blockers: [{ message: "创建失败，未写入任何任务：" + error.message }], warnings: [] };
      document.querySelector("#assignment-wizard").innerHTML = assignmentBody(state.data);
    }
  }

  function purposeCards(selected) {
    const purposes = [
      ["predicted_claim_precision", "预测 Claim 精度审核", "从系统已预测的 Claims 中抽样。", ["Claim Precision", "字段正确性", "Evidence Grounding", "Entity Linking Precision"], "不能单独评估 Recall / 完整 F1"],
      ["source_unit_exhaustive_gold", "Source-unit 穷尽 Gold", "从源文本单元中抽样，Reviewer 标注所有符合规则的 Claims。", ["Precision", "Recall", "F1"], "当前抽样框是 selected_for_l1_extraction，不代表全文端到端 Recall"]
    ];
    return '<div class="purpose-grid">' + purposes.map(function (row) {
      return '<button type="button" class="purpose-card ' + (selected === row[0] ? "selected" : "") + '" data-sampling-purpose="' + row[0] + '"><span class="purpose-icon">' + (row[0] === "predicted_claim_precision" ? "P" : "G") + '</span><strong>' + row[1] + '</strong><p>' + row[2] + '</p><div class="can-measure"><b>可以评估</b>' + row[3].map(function (item) { return "<span>✓ " + item + "</span>"; }).join("") + '</div><div class="cannot-measure">' + row[4] + "</div></button>";
    }).join("") + "</div>";
  }
  function distributionTable(population, sample) {
    const keys = Array.from(new Set(Object.keys(population || {}).concat(Object.keys(sample || {})))).sort();
    return '<div class="table-scroll"><table><thead><tr><th>Domain</th><th>总体</th><th>抽中</th><th>抽样比例</th></tr></thead><tbody>' + keys.map(function (key) {
      const total = population[key] || 0, selected = sample[key] || 0;
      return "<tr><td>" + esc(key) + "</td><td>" + total + "</td><td><strong>" + selected + "</strong></td><td>" + (total ? Math.round(selected / total * 100) : 0) + "%</td></tr>";
    }).join("") + "</tbody></table></div>";
  }
  function samplingBody() {
    const state = operationState.sampling, frame = state.frame || {};
    let content = "";
    if (state.step === 1) content = '<h3>选择评估目的</h3><p>先明确要回答的科学评估问题，再配置抽样参数。</p>' + purposeCards(state.purpose);
    if (state.step === 2) content = '<h3>选择 Sampling Frame</h3>' + (frame.supported ?
      '<button type="button" class="frame-card selected"><header><span class="status-pill status-active">' + esc(frame.status) + '</span><strong>' + (state.purpose === "predicted_claim_precision" ? "预测 Claim 的 Source-unit Cluster Frame" : "Source-unit Exhaustive Gold Frame") + '</strong></header><div class="preview-metrics"><div><strong>' + frame.source_unit_count + '</strong>Source Units</div><div><strong>' + frame.predicted_claim_count + '</strong>Predicted Claims</div><div><strong>' + frame.paper_count + '</strong>Papers</div><div><strong>' + frame.case_count + '</strong>Cases</div><div><strong>' + frame.domain_count + '</strong>Domains</div><div><strong>' + esc((frame.source_scope_distribution || {}).abstract || 0) + '</strong>Abstract</div><div><strong>' + esc((frame.source_scope_distribution || {}).fulltext || 0) + '</strong>Fulltext</div></div><p>Section Types：' + esc(Object.entries(frame.section_type_distribution || {}).map(function (row) { return row[0] + " " + row[1]; }).join("、") || "未提供") + '</p><p>' + esc(frame.notice) + '</p><details><summary>高级信息</summary><dl><div><dt>Frame Version</dt><dd>' + esc(frame.frame_version) + '</dd></div><div><dt>Frame Hash</dt><dd><code>' + esc(frame.frame_hash) + '</code></dd></div><div><dt>Projection ID</dt><dd>' + esc(frame.projection_id || "未提供") + '</dd></div><div><dt>Adapter Version</dt><dd>' + esc(frame.adapter_version || "未提供") + '</dd></div><div><dt>Artifact Hash</dt><dd><code>' + esc(frame.artifact_hash || "未提供") + '</code></dd></div><div><dt>Generated from</dt><dd>' + esc(frame.generated_from || "current projection") + "</dd></div></dl></details></button>" :
      '<div class="readiness-hero is-blocked"><h3>Sampling Frame 不可用</h3><p>当前投影没有可用源文本单元，不能把 0 显示为评估指标，也不能创建 F1 Pilot。</p><button class="button-sm" type="button" onclick="route()">重试</button></div>');
    if (state.step === 3) content = '<h3>选择分层与覆盖规则</h3><div class="preset-row"><button class="preset selected" data-sampling-preset="proportional" type="button">按总体比例</button><button class="preset" data-sampling-preset="domain" type="button">领域均衡</button><button class="preset" data-sampling-preset="case" type="button">Case 最低覆盖</button><button class="preset" data-sampling-preset="scope" type="button">Abstract / Fulltext 分层</button><button class="preset" data-sampling-preset="custom" type="button">自定义</button></div><div class="sampling-form-grid"><label>每个 Domain 最少<input id="sample-min-domain" type="number" min="0" value="' + esc(state.minDomain || 0) + '"><small>避免领域完全缺席。</small></label><label>每个 Case 最少<input id="sample-min-case" type="number" min="0" value="' + esc(state.minCase || 0) + '"><small>保证关键 Case 的最低覆盖。</small></label><label>每个 Case 最多<input id="sample-case-cap" type="number" min="0" value="' + esc(state.caseCap || 0) + '"><small>0 表示不设上限。</small></label><label>每篇 Paper 最多<input id="sample-paper-cap" type="number" min="0" value="' + esc(state.paperCap || 3) + '"><small>防止单篇论文支配样本。</small></label><label>Abstract 最低比例<input id="sample-abstract-ratio" type="number" min="0" max="100" value="' + esc(state.abstractRatio || 0) + '"><small>百分比，无法满足时阻断。</small></label><label>Fulltext 最低比例<input id="sample-fulltext-ratio" type="number" min="0" max="100" value="' + esc(state.fulltextRatio || 0) + '"><small>百分比，无法满足时阻断。</small></label></div><details><summary>高级分层变量</summary><p>当前后端还支持 Source Scope、Section Type、Relation Type 与 Confidence Band 过滤；未选择时保持总体范围。</p></details>';
    if (state.step === 4) content = '<h3>样本量、排除与随机种子</h3><div class="sampling-form-grid"><label>总样本量<input id="sample-size" type="number" min="1" value="' + esc(state.sampleSize || Math.min(50, frame.source_unit_count || 50)) + '"></label><label>随机种子<input id="sample-seed" type="number" value="' + esc(state.seed || 20260731) + '"></label></div><fieldset class="exclusion-grid"><legend>排除项</legend><label><input type="checkbox" data-exclusion="exclude_annotated" checked> 已标注单元</label><label><input type="checkbox" data-exclusion="exclude_duplicate_source_unit" checked> 重复 source_unit_id</label><label><input type="checkbox" data-exclusion="exclude_duplicate_text_hash" checked> 重复 text_hash</label><label><input type="checkbox" data-exclusion="exclude_no_text" checked> 无文本</label><label><input type="checkbox" data-exclusion="exclude_unsupported_schema" checked> unsupported schema</label><label><input type="checkbox" data-exclusion="exclude_inactive_case" checked> inactive Case</label><label><input type="checkbox" data-exclusion="exclude_legacy_invalid" checked> legacy-invalid source</label></fieldset><div class="seed-note"><strong>为什么保留 Seed？</strong><p>相同 Sampling Frame、配置和 Seed 会生成相同结果；Frame Hash 改变时，即使 Seed 相同，结果也可能变化。</p></div>';
    if (state.step === 5) {
      const p = state.preview;
      content = p ? '<h3>抽样预览</h3>' + alertList(p.blockers, "blockers") + alertList(p.warnings, "warnings") +
        '<div class="preview-metrics"><div><strong>' + p.sample_size + '</strong>抽中样本</div><div><strong>' + p.coverage.papers + '</strong>覆盖 Papers</div><div><strong>' + p.coverage.cases + '</strong>覆盖 Cases</div><div><strong>' + p.coverage.domains + '</strong>覆盖 Domains</div><div><strong>' + p.coverage.abstract + '</strong>Abstract</div><div><strong>' + p.coverage.fulltext + '</strong>Fulltext</div><div><strong>' + p.coverage.duplicate_source_unit_ids + '</strong>重复 Source Unit</div><div><strong>' + p.coverage.duplicate_text_hashes + '</strong>重复 Text Hash</div><div><strong>' + (p.coverage.max_paper_share === null ? "—" : Math.round(p.coverage.max_paper_share * 100) + "%") + '</strong>最大单 Paper</div><div><strong>' + (p.coverage.max_case_share === null ? "—" : Math.round(p.coverage.max_case_share * 100) + "%") + '</strong>最大单 Case</div></div>' +
        distributionTable(p.population_distribution.domains, p.sample_distribution.domains) +
        '<section class="excluded-breakdown"><h4>未覆盖 Case</h4><span>' + esc((p.coverage.uncovered_cases || []).join("、") || "全部已覆盖") + '</span><h4>排除明细</h4>' + (Object.keys(p.excluded_breakdown || {}).length ? Object.entries(p.excluded_breakdown).map(function (row) { return "<span>" + esc(row[0]) + "：<b>" + row[1] + "</b></span>"; }).join("") : "<span>没有被排除的记录</span>") + '</section><details><summary>查看抽中样本</summary><div class="table-scroll"><table><thead><tr><th>样本</th><th>Case</th><th>Domain</th><th>Paper</th><th>Scope</th><th>Section</th></tr></thead><tbody>' + p.units.slice(0, 100).map(function (row, index) { return "<tr><td>样本 " + (index + 1) + "<small>" + esc(row.text_excerpt || "") + "</small></td><td>" + esc(row.case_id) + "</td><td>" + esc(row.domain_id) + "</td><td>" + esc(row.paper_id) + "</td><td>" + esc(row.source_scope) + "</td><td>" + esc(row.section_type) + '</td></tr>'; }).join("") + '</tbody></table></div></details><div class="toolbar"><button class="button-sm" type="button" data-sampling-back>修改配置</button><button class="button-sm" type="button" data-sampling-new-seed>更换 Seed 并重新预览</button></div>' : '<div class="operations-loading"><span class="loading-dot"></span><p>正在确定性生成样本并计算分布…</p></div>';
    }
    if (state.step === 6) {
      const result = state.result;
      content = result ? '<div class="creation-result"><span class="success-mark">✓</span><h3>' + (result.reused ? "已复用相同抽样批次" : "抽样批次已创建") + '</h3><p>' + (result.purpose === "predicted_claim_precision" ? "预测 Claim 精度审核" : "Source-unit 穷尽 Gold") + ' · ' + esc(result.creation_status) + '</p><div class="preview-metrics"><div><strong>' + result.sample_size + '</strong>样本量</div><div><strong>' + result.coverage.domains + '</strong>Domains</div><div><strong>' + result.coverage.cases + '</strong>Cases</div><div><strong>' + result.coverage.papers + '</strong>Papers</div></div><div class="metric-readiness"><p>Claim Precision <span class="status">' + esc(result.metric_readiness.claim_precision.status) + ' · null</span></p><p>Claim Recall <span class="status status-needs_exhaustive_gold">' + esc(result.metric_readiness.claim_recall.status) + ' · null</span></p><p>Claim F1 <span class="status status-needs_exhaustive_gold">' + esc(result.metric_readiness.claim_f1.status) + ' · null</span></p></div><details><summary>高级信息</summary><p>Sampling Batch：<code>' + esc(result.batch_id) + '</code></p><p>Sampling unit：' + esc(result.sampling_unit) + '</p><p>Seed：' + result.random_seed + '</p><p>Frame Hash：<code>' + esc(result.frame_hash) + '</code></p><p>Configuration Hash：<code>' + esc(result.configuration_hash) + '</code></p></details><div class="toolbar"><button class="button" type="button" data-sampling-to-assignment>立即分配审核人员</button><button class="button-sm" data-copy-text="' + esc("抽样批次 " + result.batch_id + "，样本 " + result.sample_size) + '">复制批次摘要</button></div></div>' : '<div class="error">创建结果不可用。</div>';
    }
    return '<section class="wizard-card sampling-wizard">' + wizardSteps(state.step, ["评估目的", "Sampling Frame", "分层覆盖", "样本量与 Seed", "预览", "创建 Pilot"]) + '<div class="wizard-content">' + content + '</div><p class="draft-note">配置仅保存在当前浏览器会话；尚未创建前不会写数据库。</p><footer class="wizard-footer">' + (state.step > 1 && state.step < 6 ? '<button class="button-sm" type="button" data-sampling-back>上一步</button>' : "<span></span>") + (state.step < 5 ? '<button class="button" type="button" data-sampling-next ' + ((state.step === 1 && !state.purpose) || (state.step === 2 && !frame.supported) ? "disabled" : "") + '>继续</button>' : state.step === 5 ? '<button class="button" type="button" data-sampling-create ' + ((!state.preview || state.preview.blocked) ? "disabled" : "") + '>确认创建抽样批次</button>' : "") + "</footer></section>";
  }
  async function renderSampling(host) {
    loading(host);
    const data = await api(samplingPrefix() + "/frames");
    operationState.sampling.frame = data.current || {};
    const startingPurpose = sessionStorage.getItem("atlas_sampling_start_purpose");
    if (startingPurpose) {
      operationState.sampling.purpose = startingPurpose;
      sessionStorage.removeItem("atlas_sampling_start_purpose");
    }
    host.innerHTML = '<section class="operations-page-head"><div><span class="eyebrow">抽样与数据集</span><h2>设计随机抽样方案</h2><p>先选择评估目的，再查看总体、分层、排除和确定性预览。</p></div></section><div id="sampling-wizard">' + samplingBody() + "</div>";
  }
  async function samplingNext() {
    const state = operationState.sampling;
    if (state.step === 3) {
      state.minDomain = Number(document.querySelector("#sample-min-domain").value) || 0;
      state.minCase = Number(document.querySelector("#sample-min-case").value) || 0;
      state.caseCap = Number(document.querySelector("#sample-case-cap").value) || 0;
      state.paperCap = Number(document.querySelector("#sample-paper-cap").value) || 0;
      state.abstractRatio = Number(document.querySelector("#sample-abstract-ratio").value) || 0;
      state.fulltextRatio = Number(document.querySelector("#sample-fulltext-ratio").value) || 0;
    }
    if (state.step === 4) {
      state.sampleSize = Number(document.querySelector("#sample-size").value) || 0;
      state.seed = Number(document.querySelector("#sample-seed").value) || 0;
      state.exclusions = {};
      document.querySelectorAll("[data-exclusion]").forEach(function (input) { state.exclusions[input.dataset.exclusion] = input.checked; });
      state.step = 5; state.preview = null; document.querySelector("#sampling-wizard").innerHTML = samplingBody();
      try {
        state.preview = await apiPost(samplingPrefix() + "/preview", {
          purpose: state.purpose, sample_size: state.sampleSize, random_seed: state.seed,
          min_per_domain: state.minDomain, min_per_case: state.minCase, max_per_case: state.caseCap,
          max_per_paper: state.paperCap, min_abstract_ratio: state.abstractRatio / 100,
          min_fulltext_ratio: state.fulltextRatio / 100,
          exclusions: state.exclusions
        });
      } catch (error) { state.preview = { blocked: true, blockers: [{ message: error.message }], warnings: [] }; }
      document.querySelector("#sampling-wizard").innerHTML = samplingBody(); return;
    }
    state.step += 1; document.querySelector("#sampling-wizard").innerHTML = samplingBody();
  }
  async function createSampling() {
    const state = operationState.sampling;
    try {
      state.result = await apiPost(samplingPrefix() + "/create", {
        purpose: state.purpose, sample_size: state.sampleSize, random_seed: state.seed,
        min_per_domain: state.minDomain, min_per_case: state.minCase, max_per_case: state.caseCap,
        max_per_paper: state.paperCap, min_abstract_ratio: state.abstractRatio / 100,
        min_fulltext_ratio: state.fulltextRatio / 100,
        exclusions: state.exclusions
      });
      state.step = 6; document.querySelector("#sampling-wizard").innerHTML = samplingBody();
    } catch (error) { showToast("抽样创建失败：" + error.message, "error"); }
  }
  function samplingToAssignment() {
    const sample = operationState.sampling.result;
    operationState.assignment = {
      step: 1, source: "sampling_batch", strategy: "workload_balance",
      itemIds: (sample.units || []).map(function (row) { return row.review_item_id; }),
      samplingBatchId: sample.batch_id, expectedFrameHash: sample.frame_hash, preview: null,
      samplingPurpose: sample.purpose, samplingSchema: sample.schema_version,
      sampleDistribution: sample.sample_distribution,
      projectId: sessionStorage.getItem("atlas_sampling_project") || ""
    };
    sessionStorage.removeItem("atlas_sampling_project");
    sessionStorage.setItem("atlas_assignment_handoff", JSON.stringify(operationState.assignment));
    location.href = (operationState.actor === "owner" ? "/owner/" : "/admin/") + "assignments?sampling_batch=" + encodeURIComponent(sample.batch_id);
  }

  async function renderBatches(host) {
    loading(host);
    const endpoint = operationState.actor === "owner" ? "/api/owner/operations/batches" : "/api/admin/batches";
    const data = await api(endpoint), selected = new URLSearchParams(location.search).get("batch");
    const rows = data.items || [];
    host.innerHTML = '<section class="operations-page-head"><div><span class="eyebrow">任务与批次</span><h2>审核批次</h2><p>查看进度、人员职责和创建配置。</p></div><a class="button" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'assignments">创建审核批次</a></section>' +
      (rows.length ? '<div class="table-scroll operations-table"><table><thead><tr><th>批次</th><th>项目</th><th>来源</th><th>Items</th><th>完成度</th><th>Primary</th><th>Secondary</th><th>Adjudicator</th><th>状态</th></tr></thead><tbody>' + rows.map(function (row) {
        return '<tr class="' + (selected === row.batch_id ? "selected-row" : "") + '" data-batch-row="' + esc(row.batch_id) + '"><td><button class="person-link" type="button" data-open-batch="' + esc(row.batch_id) + '"><strong>' + esc(row.batch_name) + '</strong><span>' + esc(fmtDate(row.created_at)) + '</span></button></td><td>' + esc(row.project_name) + '</td><td>' + esc(row.source) + '</td><td>' + row.items + '</td><td>' + percent(row.completion_fraction) + '</td><td>' + esc((row.roles.primary || {}).count || 0) + '</td><td>' + esc((row.roles.secondary || {}).count || 0) + '</td><td>' + esc((row.roles.adjudicator || {}).count || 0) + '</td><td><span class="status-pill">' + esc(statusLabel(row.status)) + "</span></td></tr>";
      }).join("") + "</tbody></table></div><div id=\"batch-detail\"></div>" : emptyState("还没有审核批次", "创建后会在这里显示人员、进度和抽样来源。", '<a class="button" href="' + (operationState.actor === "owner" ? "/owner/" : "/admin/") + 'assignments">创建审核批次</a>'));
    operationState.batchData = rows;
    if (selected) openBatch(selected);
  }
  function openBatch(batchId) {
    const row = (operationState.batchData || []).find(function (item) { return item.batch_id === batchId; });
    if (!row) return;
    operationState.openBatch = row;
    document.querySelector("#batch-detail").innerHTML = '<section class="batch-detail card"><div class="section-heading"><div><span class="eyebrow">批次详情</span><h2>' + esc(row.batch_name) + '</h2><p>' + esc(row.project_name) + " · " + esc(fmtDate(row.created_at)) + '</p></div><span class="status-pill">' + esc(statusLabel(row.status)) + '</span></div><nav class="detail-tabs"><button class="active" data-batch-tab="summary">批次摘要</button><button data-batch-tab="sampling">抽样配置</button><button data-batch-tab="distribution">样本分布</button><button data-batch-tab="workload">用户负载</button><button data-batch-tab="status">任务状态</button><button data-batch-tab="disagreement">分歧状态</button><button data-batch-tab="excluded">被排除项目</button><button data-batch-tab="audit">Audit</button></nav><div id="batch-tab-body">' + batchTabBody(row, "summary") + "</div></section>";
    document.querySelector("#batch-detail").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function keyValueRows(values, empty) {
    const rows = Object.entries(values || {});
    return rows.length ? '<div class="distribution-chips">' + rows.map(function (row) { return '<span><b>' + esc(row[1]) + '</b>' + esc(row[0]) + "</span>"; }).join("") + "</div>" : '<p class="muted">' + esc(empty || "暂无数据") + "</p>";
  }
  function batchTabBody(row, tab) {
    if (tab === "sampling") return '<h3>抽样配置</h3><dl class="result-summary"><div><dt>来源</dt><dd>' + esc(row.source) + '</dd></div><div><dt>策略</dt><dd>' + esc((row.config || {}).strategy || "fixed_pair") + '</dd></div><div><dt>Sampling Batch</dt><dd>' + esc((row.config || {}).sampling_batch_id ? "已关联" : "未关联") + '</dd></div></dl><details><summary>高级创建配置</summary><pre>' + esc(JSON.stringify(row.config || {}, null, 2)) + "</pre></details>";
    if (tab === "distribution") return '<h3>样本分布</h3><h4>Domain</h4>' + keyValueRows((row.sample_distribution || {}).domains) + '<h4>Case</h4>' + keyValueRows((row.sample_distribution || {}).cases) + '<h4>Paper</h4>' + keyValueRows((row.sample_distribution || {}).papers);
    if (tab === "workload") return '<h3>用户负载</h3><div class="workload-cards">' + Object.entries(row.roles || {}).map(function (entry) { const role = entry[0], value = entry[1]; return '<article><span>' + esc(role) + '</span><strong>' + esc(value.display_name || "未知用户") + '</strong><p>' + esc(value.completed || 0) + " / " + esc(value.count || 0) + " 已完成</p><progress max=\"" + esc(value.count || 1) + '" value="' + esc(value.completed || 0) + '"></progress></article>'; }).join("") + "</div>";
    if (tab === "status") return '<h3>任务状态</h3>' + keyValueRows(row.status_distribution) + '<div class="preview-metrics"><div><strong>' + esc(row.waiting_secondary || 0) + '</strong>等待第二审核</div><div><strong>' + esc(row.waiting_adjudication || 0) + "</strong>仲裁角色待办</div></div>";
    if (tab === "disagreement") return '<h3>分歧状态</h3><p>此运营页面只显示安全计数，不返回 Primary/Secondary 的具体答案。</p><div class="preview-metrics"><div><strong>' + esc(row.waiting_adjudication || 0) + '</strong>仲裁角色待办</div></div>';
    if (tab === "excluded") return '<h3>排除与重复</h3><div class="preview-metrics"><div><strong>' + esc(row.excluded_count || 0) + '</strong>被排除</div><div><strong>' + esc(row.duplicate_count || 0) + "</strong>重复项目</div></div>";
    if (tab === "audit") return '<h3>Audit</h3><p>创建时间：' + esc(fmtDate(row.created_at)) + '</p><details><summary>高级引用</summary><code>' + esc(row.audit_reference) + "</code></details>";
    return '<div class="preview-metrics"><div><strong>' + row.items + '</strong>Review Items</div><div><strong>' + row.assignment_count + '</strong>Assignments</div><div><strong>' + row.completed + '</strong>已完成</div><div><strong>' + percent(row.completion_fraction) + '</strong>完成度</div></div><p>来源：' + esc(row.source) + "。默认隐藏 UUID 与内部 hash。</p>";
  }
  async function renderProgress(host) {
    const endpoint = operationState.actor === "owner" ? "/api/owner/operations/batches" : "/api/admin/batches";
    const data = await api(endpoint), rows = data.items || [];
    const total = rows.reduce(function (sum, row) { return sum + row.assignment_count; }, 0);
    const completed = rows.reduce(function (sum, row) { return sum + row.completed; }, 0);
    host.innerHTML = '<section class="operations-page-head"><div><span class="eyebrow">进度</span><h2>Pilot 完成与仲裁进度</h2><p>只展示状态和统计，不返回 Reviewer 的具体答案。</p></div></section><div class="preview-metrics"><div><strong>' + total + '</strong>全部任务</div><div><strong>' + completed + '</strong>已完成</div><div><strong>' + Math.max(0, total - completed) + '</strong>待完成</div><div><strong>' + percent(total ? completed / total : null) + '</strong>总体进度</div></div>' + (rows.length ? rows.map(function (row) { return '<section class="progress-row"><div><strong>' + esc(row.batch_name) + '</strong><span>' + esc(row.project_name) + '</span></div><progress max="' + row.assignment_count + '" value="' + row.completed + '"></progress><b>' + percent(row.completion_fraction) + "</b></section>"; }).join("") : emptyState("暂无进度", "创建审核批次后会在这里汇总。"));
  }

  const legacyOwnerWorkspace = ownerWorkspace;
  const legacyAdminWorkspace = adminWorkspace;
  async function operationsWorkspace(actor) {
    operationState.actor = actor;
    let page = location.pathname.replace(new RegExp("^/" + actor + "/?"), "") || "overview";
    if (page === "people") page = "users";
    if (page === "batches") page = "batches";
    const operationsPages = ["overview", "users", "projects", "assignments", "batches", "sampling", "progress"];
    if (actor === "owner" && !operationsPages.includes(page)) return legacyOwnerWorkspace();
    if (actor === "admin" && page === "invites") return legacyAdminWorkspace();
    title(actor === "owner" ? "Owner 运营工作台" : "Admin 运营工作台", actor === "owner" ? "运营工作流与治理能力分层呈现。" : "管理普通用户、Pilot、抽样和任务；不包含 Gold、Metrics 或技术 Console。");
    W.innerHTML += shell(actor, page === "batches" ? "assignments" : page);
    const host = document.querySelector("#operations-page");
    try {
      if (page === "users") return await renderUsers(host);
      if (page === "projects") return await renderProjects(host);
      if (page === "assignments") return await renderAssignments(host);
      if (page === "batches") return await renderBatches(host);
      if (page === "sampling") return await renderSampling(host);
      if (page === "progress") return await renderProgress(host);
      return await renderOverview(host);
    } catch (error) {
      host.innerHTML = '<div class="operations-error" role="alert"><h2>运营数据暂时无法读取</h2><p>' + esc(error.message) + '</p><button class="button" type="button" onclick="route()">重试</button></div>';
    }
  }
  adminWorkspace = function () { return operationsWorkspace("admin"); };
  ownerWorkspace = function () { return operationsWorkspace("owner"); };

  document.addEventListener("click", function (event) {
    const target = event.target.closest("button,[data-open-user],[data-open-batch]");
    if (!target) return;
    if (target.dataset.openUser) return openUserDrawer(target.dataset.openUser);
    if (target.dataset.userSummary) {
      operationState.userSummaryFilter = target.dataset.userSummary;
      applyUserFilters();
      return;
    }
    if (target.hasAttribute("data-clear-user-filters")) return clearUserFilters();
    if (target.id === "open-create-user") return openCreateUser();
    if (target.hasAttribute("data-create-user-submit")) return createUser();
    if (target.classList.contains("close-drawer") || target.id === "user-drawer-backdrop") return closeUserDrawer();
    if (target.dataset.userAction) return userAction(target.dataset.userId, target.dataset.userAction);
    if (target.dataset.changeRole) return changeRole(target.dataset.changeRole);
    if (target.dataset.bulkAction) return bulkAction(target.dataset.bulkAction);
    if (target.hasAttribute("data-bulk-to-pilot")) {
      const ids = Array.from(operationState.selectedUsers);
      if (!ids.length) return showToast("请先选择用户", "error");
      sessionStorage.setItem("atlas_assignment_assignees", JSON.stringify(ids));
      location.href = (operationState.actor === "owner" ? "/owner/" : "/admin/") + "assignments";
      return;
    }
    if (target.dataset.assignmentProject) { operationState.assignment.projectId = target.dataset.assignmentProject; document.querySelector("#assignment-wizard").innerHTML = assignmentBody(operationState.assignment.data); return; }
    if (target.dataset.assignmentSource) { operationState.assignment.source = target.dataset.assignmentSource; document.querySelector("#assignment-wizard").innerHTML = assignmentBody(operationState.assignment.data); return; }
    if (target.hasAttribute("data-assignment-next")) return assignmentNext();
    if (target.hasAttribute("data-assignment-back")) { operationState.assignment.step -= 1; operationState.assignment.preview = null; document.querySelector("#assignment-wizard").innerHTML = assignmentBody(operationState.assignment.data); return; }
    if (target.hasAttribute("data-assignment-create")) return createAssignment();
    if (target.dataset.samplingPurpose) { operationState.sampling.purpose = target.dataset.samplingPurpose; document.querySelector("#sampling-wizard").innerHTML = samplingBody(); return; }
    if (target.hasAttribute("data-sampling-next")) return samplingNext();
    if (target.hasAttribute("data-sampling-back")) { operationState.sampling.step -= 1; operationState.sampling.preview = null; document.querySelector("#sampling-wizard").innerHTML = samplingBody(); return; }
    if (target.hasAttribute("data-sampling-create")) return createSampling();
    if (target.hasAttribute("data-sampling-to-assignment")) return samplingToAssignment();
    if (target.dataset.samplingPreset) {
      const presets = {
        proportional: [0, 0, 0, 0],
        domain: [1, 0, 0, 0],
        case: [0, 1, 0, 0],
        scope: [0, 0, 20, 20],
        custom: null
      };
      const values = presets[target.dataset.samplingPreset];
      if (values) {
        document.querySelector("#sample-min-domain").value = values[0];
        document.querySelector("#sample-min-case").value = values[1];
        document.querySelector("#sample-abstract-ratio").value = values[2];
        document.querySelector("#sample-fulltext-ratio").value = values[3];
      }
      document.querySelectorAll("[data-sampling-preset]").forEach(function (button) { button.classList.toggle("selected", button === target); });
      return;
    }
    if (target.hasAttribute("data-sampling-new-seed")) {
      operationState.sampling.seed = Number(operationState.sampling.seed || 0) + 1;
      operationState.sampling.step = 4;
      operationState.sampling.preview = null;
      document.querySelector("#sampling-wizard").innerHTML = samplingBody();
      document.querySelector("#sample-seed").focus();
      return;
    }
    if (target.dataset.copyText && target.closest("#assignment-wizard, #sampling-wizard")) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        Promise.resolve(navigator.clipboard.writeText(target.dataset.copyText))
          .then(function () { showToast("批次摘要已复制", "success"); })
          .catch(function () { showToast("无法访问剪贴板，请手动复制", "error"); });
      } else {
        showToast("无法访问剪贴板，请手动复制", "error");
      }
      return;
    }
    if (target.dataset.openBatch) return openBatch(target.dataset.openBatch);
    if (target.dataset.batchTab && operationState.openBatch) {
      document.querySelectorAll("[data-batch-tab]").forEach(function (button) { button.classList.toggle("active", button === target); });
      document.querySelector("#batch-tab-body").innerHTML = batchTabBody(operationState.openBatch, target.dataset.batchTab);
      return;
    }
    if (target.id === "preview-pilot-counts") {
      const box = document.querySelector("#pilot-preview");
      box.innerHTML = '<div class="scientific-boundary"><strong>Review Item count is not Case count.</strong><div class="preview-metrics"><div><strong>Case</strong>unique cases</div><div><strong>Review Item</strong>unique review items</div></div><p>实际分配和计费口径使用 Review Items；Cases 只表示研究分组。</p></div>';
      return;
    }
  });
  document.addEventListener("change", function (event) {
    if (event.target.id === "drawer-role") {
      const current = event.target.dataset.currentRole;
      document.querySelector("#role-change-title").textContent = roleLabel(current) + " → " + roleLabel(event.target.value);
      const workspaces = { reviewer: "审核工作台", adjudicator: "仲裁工作台", researcher: "科研阅读工作台", developer: "开发工作台", admin: "Admin 运营工作台" };
      document.querySelector("#role-workspace-impact").textContent = "下次登录进入" + (workspaces[event.target.value] || "对应角色工作台");
      return;
    }
    if (!event.target.classList.contains("user-check")) return;
    if (event.target.checked) operationState.selectedUsers.add(event.target.value); else operationState.selectedUsers.delete(event.target.value);
    const count = document.querySelector("#selected-user-count"); if (count) count.textContent = operationState.selectedUsers.size;
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeUserDrawer();
  });
}());
