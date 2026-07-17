"""Central role, capability, landing-page and navigation policy for Atlas.

Global roles are only the first authorization layer.  Object services must
also enforce project, assignment and workflow state before returning data.
"""
from __future__ import annotations

from typing import Any


GLOBAL_ROLES = ("owner", "admin", "developer", "reviewer", "adjudicator", "researcher", "pharma")
CREATABLE_ROLES = ("admin", "developer", "reviewer", "adjudicator", "researcher", "pharma")
ADMIN_CREATABLE_ROLES = ("reviewer", "adjudicator", "researcher", "pharma")
REVIEW_ASSIGNMENT_ROLES = ("primary", "secondary", "expert")

ROLE_REGISTRY: dict[str, dict[str, Any]] = {
    "owner": {
        "label": "Owner", "description": "最高治理权限；管理访问、Gold、评估、审计和系统状态。", "landing_path": "/owner",
        "capabilities": ("browse_research", "manage_users", "manage_pilot_projects", "manage_assignments", "manage_governance", "freeze_pilot_gold", "freeze_production_gold", "view_audit", "view_system_state"),
    },
    "admin": {
        "label": "运营管理员", "description": "管理普通用户、Pilot 项目和任务；不能取代 Owner。", "landing_path": "/admin",
        "capabilities": ("browse_research", "manage_users", "manage_pilot_projects", "manage_assignments", "view_operational_quality"),
    },
    "developer": {
        "label": "Developer", "description": "查看同步、投影、Schema、能力状态和技术诊断。", "landing_path": "/console",
        "capabilities": ("browse_research", "view_developer_console"),
    },
    "reviewer": {
        "label": "Reviewer", "description": "完成分配给自己的独立审核任务。", "landing_path": "/review",
        "capabilities": ("browse_research", "review_assigned_items"),
    },
    "adjudicator": {
        "label": "Adjudicator", "description": "在双人审核完成且发生分歧后处理分配给自己的仲裁。", "landing_path": "/adjudication",
        "capabilities": ("browse_research", "adjudicate_assigned_items"),
    },
    "researcher": {
        "label": "科研阅读者", "description": "仅浏览领域、Case、证据、Dossier 和机制图。", "landing_path": "/discover",
        "capabilities": ("browse_research",),
    },
    # Retained for stored users and legacy invites.  It has reader-level
    # authority and is no longer treated as a reviewer or developer role.
    "pharma": {
        "label": "药学阅读者（旧版）", "description": "旧版只读科研角色；权限等同科研阅读者。", "landing_path": "/discover",
        "capabilities": ("browse_research",),
    },
}

NAVIGATION_REGISTRY = (
    {"id": "review", "label": "我的审核", "route": "/review", "allowed_global_roles": ("reviewer",), "required_project_capability": None, "required_assignment_type": "review", "required_feature": "review", "order": 10},
    {"id": "adjudication", "label": "我的仲裁", "route": "/adjudication", "allowed_global_roles": ("adjudicator",), "required_project_capability": None, "required_assignment_type": "adjudication", "required_feature": "adjudication", "order": 10},
    {"id": "console", "label": "Developer Console", "route": "/console", "allowed_global_roles": ("developer",), "required_project_capability": None, "required_assignment_type": None, "required_feature": "technical_console", "order": 10},
    {"id": "admin", "label": "Admin 管理", "route": "/admin", "allowed_global_roles": ("admin",), "required_project_capability": "manage_pilot", "required_assignment_type": None, "required_feature": "admin", "order": 10},
    {"id": "owner", "label": "Owner 总控", "route": "/owner", "allowed_global_roles": ("owner",), "required_project_capability": "governance", "required_assignment_type": None, "required_feature": "owner", "order": 10},
    {"id": "discover", "label": "研究首页", "route": "/discover", "allowed_global_roles": GLOBAL_ROLES, "required_project_capability": None, "required_assignment_type": None, "required_feature": "research", "order": 20},
    {"id": "domains", "label": "领域", "route": "/domains", "allowed_global_roles": GLOBAL_ROLES, "required_project_capability": None, "required_assignment_type": None, "required_feature": "research", "order": 30},
    {"id": "cases", "label": "研究问题", "route": "/cases", "allowed_global_roles": GLOBAL_ROLES, "required_project_capability": None, "required_assignment_type": None, "required_feature": "research", "order": 40},
    {"id": "conflicts", "label": "证据分歧", "route": "/conflicts", "allowed_global_roles": GLOBAL_ROLES, "required_project_capability": None, "required_assignment_type": None, "required_feature": "research", "order": 50},
    {"id": "graph", "label": "机制地图", "route": "/graph", "allowed_global_roles": GLOBAL_ROLES, "required_project_capability": None, "required_assignment_type": None, "required_feature": "research", "order": 60},
    {"id": "library", "label": "资料库", "route": "/library", "allowed_global_roles": GLOBAL_ROLES, "required_project_capability": None, "required_assignment_type": None, "required_feature": "library", "order": 70},
    {"id": "review_progress", "label": "审核进度", "route": "/progress", "allowed_global_roles": ("reviewer",), "required_project_capability": None, "required_assignment_type": "review", "required_feature": "review", "order": 80},
    {"id": "guidelines", "label": "标注指南", "route": "/guidelines/claim_review_v1", "allowed_global_roles": ("reviewer", "adjudicator"), "required_project_capability": None, "required_assignment_type": None, "required_feature": "guidelines", "order": 90},
    {"id": "help", "label": "帮助", "route": "/help", "allowed_global_roles": GLOBAL_ROLES, "required_project_capability": None, "required_assignment_type": None, "required_feature": "help", "order": 100},
)


def normalize_role(role: str | None) -> str:
    return role if role in ROLE_REGISTRY else "researcher"


def role_capabilities(role: str | None) -> dict[str, bool]:
    current = normalize_role(role)
    granted = set(ROLE_REGISTRY[current]["capabilities"])
    names = {name for spec in ROLE_REGISTRY.values() for name in spec["capabilities"]}
    return {name: name in granted for name in sorted(names)}


def has_capability(identity_or_role: dict | str | None, capability: str) -> bool:
    role = identity_or_role.get("role") if isinstance(identity_or_role, dict) else identity_or_role
    return role_capabilities(role).get(capability, False)


def can_view_research(identity: dict) -> bool:
    return bool(identity.get("authenticated")) and has_capability(identity, "browse_research")


def can_review_item(identity: dict, *, assignment_owned: bool, assignment_role: str | None, assignment_open: bool, project_active: bool) -> bool:
    return bool(identity.get("authenticated")) and has_capability(identity, "review_assigned_items") and assignment_owned and assignment_role in REVIEW_ASSIGNMENT_ROLES and assignment_open and project_active


def can_adjudicate_item(identity: dict, *, assignment_owned: bool, double_submitted: bool, disagreement: bool) -> bool:
    legacy_assigned_reviewer = identity.get("role") == "reviewer" and assignment_owned
    return bool(identity.get("authenticated")) and (has_capability(identity, "adjudicate_assigned_items") or legacy_assigned_reviewer) and assignment_owned and double_submitted and disagreement


def can_manage_pilot(identity: dict, *, namespace: str) -> bool:
    return bool(identity.get("authenticated")) and namespace == "pilot" and has_capability(identity, "manage_pilot_projects")


def can_manage_users(identity: dict) -> bool:
    return bool(identity.get("authenticated")) and has_capability(identity, "manage_users")


def can_view_console(identity: dict) -> bool:
    return bool(identity.get("authenticated")) and has_capability(identity, "view_developer_console")


def can_freeze_gold(identity: dict, *, namespace: str) -> bool:
    capability = "freeze_production_gold" if namespace == "production" else "freeze_pilot_gold"
    return bool(identity.get("authenticated")) and has_capability(identity, capability)


def landing_path(role: str | None, *, must_change_password: bool = False) -> str:
    if must_change_password:
        return "/account/security"
    return str(ROLE_REGISTRY[normalize_role(role)]["landing_path"])


def navigation_for(role: str | None, task_summary: dict[str, int] | None = None) -> list[dict[str, Any]]:
    current = normalize_role(role)
    tasks = task_summary or {}
    items = []
    for spec in NAVIGATION_REGISTRY:
        legacy_adjudication_assignment = (
            spec["id"] == "adjudication"
            and current == "reviewer"
            and tasks.get("adjudication_assigned", 0) > 0
        )
        if current not in spec["allowed_global_roles"] and not legacy_adjudication_assignment:
            continue
        # A role's own empty workspace remains visible so it can explain that
        # no work is assigned.  Assignment scope is enforced by its APIs.
        item = dict(spec)
        item["task_count"] = tasks.get("review_pending", 0) if spec["id"] == "review" else tasks.get("adjudication_pending", 0) if spec["id"] == "adjudication" else None
        items.append(item)
    return sorted(items, key=lambda item: (item["order"], item["id"]))


def page_capability(path: str) -> str | None:
    clean = "/" + str(path or "").strip("/")
    if clean in {"/login", "/register", "/password-reset"}:
        return None
    if clean.startswith("/owner") or clean.startswith("/evaluation"):
        return "manage_governance"
    if clean.startswith("/admin"):
        return "manage_pilot_projects"
    if clean in {"/console", "/dev", "/entities", "/triples", "/chains"} or clean.startswith(("/entity/", "/triple/", "/chain/")):
        return "view_developer_console"
    if clean in {"/review", "/metrics", "/progress"}:
        return "review_assigned_items"
    if clean == "/adjudication" or clean.startswith("/adjudication/"):
        return "adjudicate_assigned_items"
    return "browse_research"


def page_allowed(role: str | None, path: str) -> bool:
    clean = "/" + str(path or "").strip("/")
    if clean.startswith("/admin"):
        return normalize_role(role) == "admin"
    if clean.startswith("/owner") or clean.startswith("/evaluation"):
        return normalize_role(role) == "owner"
    required = page_capability(path)
    return required is None or has_capability(role, required)
