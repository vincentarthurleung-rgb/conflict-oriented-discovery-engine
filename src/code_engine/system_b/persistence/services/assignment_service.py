"""Assignment-scoped review queue services."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import datetime
from typing import Iterable

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from code_engine.system_b.annotation_schemas import schema_for_item_type
from code_engine.system_b.persistence.models import Annotation, Assignment, AssignmentBatch, EvaluationProject, EvaluationProtocol, ReviewItem, User, utcnow
from code_engine.system_b.persistence.services.audit_service import write_audit_event
from code_engine.system_b.persistence.services.review_service import review_item_to_dict
from code_engine.system_b.authorization import REVIEW_ASSIGNMENT_ROLES


def _json(value) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _user(session: Session, user_id: str, expected_role: str | None = None) -> User:
    user = session.get(User, user_id)
    if not user or not user.enabled:
        raise ValueError("user_not_found")
    if expected_role and user.role != expected_role:
        raise ValueError(f"user_must_be_{expected_role}")
    return user


def create_project_with_assignments(
    session: Session,
    *,
    owner: dict,
    name: str,
    namespace: str,
    annotation_schema_version: str,
    primary_reviewer_user_id: str,
    secondary_reviewer_user_id: str,
    adjudicator_user_id: str,
    batch_size: int = 50,
    due_at: datetime | None = None,
    case_ids: Iterable[str] | None = None,
    item_ids: Iterable[str] | None = None,
) -> dict:
    if namespace not in {"pilot", "production"}:
        raise ValueError("projects_must_use_pilot_or_production_namespace")
    if primary_reviewer_user_id == secondary_reviewer_user_id:
        raise ValueError("primary_secondary_must_differ")
    primary = _user(session, primary_reviewer_user_id)
    secondary = _user(session, secondary_reviewer_user_id)
    adjudicator = _user(session, adjudicator_user_id)
    if primary.role != "reviewer" or secondary.role != "reviewer":
        raise ValueError("primary_secondary_must_be_reviewers")
    if adjudicator.role not in {"adjudicator", "reviewer"}:
        raise ValueError("adjudicator_role_required")
    if primary.user_id == adjudicator.user_id or secondary.user_id == adjudicator.user_id:
        raise ValueError("adjudicator_must_be_distinct")

    query = select(ReviewItem).where(ReviewItem.namespace == namespace)
    cases = sorted(set(case_ids or []))
    items = sorted(set(item_ids or []))
    if cases:
        query = query.where(ReviewItem.case_id.in_(cases))
    if items:
        query = query.where(ReviewItem.review_item_id.in_(items))
    review_items = session.execute(query.order_by(ReviewItem.case_id, ReviewItem.item_type, ReviewItem.review_item_id)).scalars().all()
    if not review_items:
        raise ValueError("no_review_items_selected")

    project = EvaluationProject(
        name=name,
        description="Owner-created formal production evaluation project.",
        namespace=namespace,
        status="active",
        created_by_user_id=owner.get("user_id"),
    )
    session.add(project)
    session.flush()
    protocol_payload = {
        "annotation_schema_version": annotation_schema_version,
        "case_ids": [item.case_id for item in review_items],
        "item_ids": [item.review_item_id for item in review_items],
    }
    protocol = EvaluationProtocol(
        project_id=project.project_id,
        version=1,
        protocol_json=_json(protocol_payload),
        case_ids_sha256=_sha(protocol_payload["case_ids"]),
        metric_registry_sha256=_sha({"registry": "atlas_metric_registry_v1"}),
        annotation_schema_sha256=_sha({"annotation_schema_version": annotation_schema_version}),
        dataset_split_sha256=_sha(protocol_payload["item_ids"]),
        frozen=True,
        created_by_user_id=owner.get("user_id"),
        frozen_at=utcnow(),
    )
    session.add(protocol)

    created_assignments = []
    for role, reviewer in (("primary", primary), ("secondary", secondary), ("adjudicator", adjudicator)):
        batch = AssignmentBatch(
            project_id=project.project_id,
            reviewer_user_id=reviewer.user_id,
            batch_index=0,
            batch_size=batch_size,
            filter_json=_json({"case_ids": cases, "item_ids": items}),
            status="assigned",
            assigned_by_user_id=owner.get("user_id"),
            due_at=due_at,
        )
        session.add(batch)
        session.flush()
        for item in review_items:
            existing = session.execute(select(Assignment).where(
                Assignment.project_id == project.project_id,
                Assignment.review_item_id == item.review_item_id,
                Assignment.reviewer_user_id == reviewer.user_id,
                Assignment.assignment_role == role,
            )).scalar_one_or_none()
            if existing:
                continue
            assignment = Assignment(
                project_id=project.project_id,
                batch_id=batch.batch_id,
                review_item_id=item.review_item_id,
                reviewer_user_id=reviewer.user_id,
                assignment_role=role,
                status="assigned",
                assigned_by_user_id=owner.get("user_id"),
            )
            session.add(assignment)
            created_assignments.append(assignment)
    session.flush()
    write_audit_event(session, action="assignment_batch_created", object_type="project", object_id=project.project_id, actor=owner, project_id=project.project_id, metadata={"items": len(review_items), "primary": primary.user_id, "secondary": secondary.user_id, "adjudicator": adjudicator.user_id})
    return {
        "project_id": project.project_id,
        "protocol_id": protocol.protocol_id,
        "review_item_count": len(review_items),
        "assignment_count": len(created_assignments),
    }


OPEN_ASSIGNMENT_STATUSES = {"assigned", "in_progress", "revisit"}


def _item_metadata(item: ReviewItem) -> dict:
    try:
        payload = json.loads(item.payload_json or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return {
        "domain": payload.get("domain_id") or (payload.get("domain_snapshot") or {}).get("domain_id") or "unclassified",
        "paper": payload.get("paper_id") or payload.get("pmid") or payload.get("pmcid") or "unknown",
    }


def assignment_batch_preview(
    session: Session,
    *,
    project_id: str,
    item_ids: Iterable[str],
    primary_reviewer_user_id: str,
    secondary_reviewer_user_id: str,
    adjudicator_user_id: str,
    actor_role: str,
    strategy: str = "workload_balance",
    sampling_batch_id: str | None = None,
    expected_frame_hash: str | None = None,
) -> dict:
    """Validate a proposed Pilot assignment batch without writing state."""
    allowed_strategies = {"fixed_pair", "even", "workload_balance", "domain", "case", "paper"}
    if strategy not in allowed_strategies:
        raise ValueError("unsupported_assignment_strategy")
    project = session.get(EvaluationProject, project_id)
    blockers: list[dict] = []
    warnings: list[dict] = []
    if not project:
        blockers.append({"code": "project_not_found", "message": "所选项目不存在。"})
    elif project.status != "active":
        blockers.append({"code": "project_not_active", "message": "项目当前不可继续分配。"})
    elif actor_role == "admin" and project.namespace != "pilot":
        blockers.append({"code": "admin_cannot_create_production", "message": "Admin 只能创建 Pilot 审核批次。"})
    requested = sorted({str(value) for value in item_ids if value})
    rows = session.execute(select(ReviewItem).where(ReviewItem.review_item_id.in_(requested))).scalars().all() if requested else []
    found = {row.review_item_id for row in rows}
    missing = sorted(set(requested) - found)
    if missing:
        blockers.append({"code": "review_items_not_found", "message": f"{len(missing)} 条任务不存在。", "count": len(missing)})
    if project:
        cross_namespace = [row.review_item_id for row in rows if row.namespace != project.namespace]
        if cross_namespace:
            blockers.append({"code": "cross_project_review_items", "message": f"{len(cross_namespace)} 条任务不属于当前项目命名空间。", "count": len(cross_namespace)})
    if not rows:
        blockers.append({"code": "no_assignable_items", "message": "没有可分配的审核任务。"})
    missing_schema_types = sorted({row.item_type for row in rows if not schema_for_item_type(row.item_type)})
    if missing_schema_types:
        blockers.append({
            "code": "schema_missing",
            "message": "部分任务缺少可用审核 Schema。",
            "item_types": missing_schema_types,
        })
    people = [
        ("primary", primary_reviewer_user_id, {"reviewer"}),
        ("secondary", secondary_reviewer_user_id, {"reviewer"}),
        ("adjudicator", adjudicator_user_id, {"reviewer", "adjudicator"}),
    ]
    if primary_reviewer_user_id == secondary_reviewer_user_id:
        blockers.append({"code": "primary_secondary_must_differ", "message": "Primary 与 Secondary 必须是不同用户。"})
    if adjudicator_user_id in {primary_reviewer_user_id, secondary_reviewer_user_id}:
        blockers.append({"code": "adjudicator_must_be_distinct", "message": "Adjudicator 不能与 Reviewer 相同。"})
    workloads = []
    for assignment_role, user_id, allowed_roles in people:
        user = session.get(User, user_id) if user_id else None
        if not user:
            blockers.append({"code": "user_not_found", "role": assignment_role, "message": f"{assignment_role} 用户不存在。"})
            continue
        if not user.enabled:
            blockers.append({"code": "user_disabled", "role": assignment_role, "message": f"{user.display_name} 已禁用。"})
        if user.role not in allowed_roles or user.role == "owner":
            blockers.append({"code": "user_role_incompatible", "role": assignment_role, "message": f"{user.display_name} 的角色不适合该任务。"})
        pending = session.execute(select(func.count()).select_from(Assignment).where(
            Assignment.reviewer_user_id == user.user_id,
            Assignment.status.in_(sorted(OPEN_ASSIGNMENT_STATUSES)),
        )).scalar() or 0
        workloads.append({
            "user_id": user.user_id,
            "display_name": user.display_name,
            "role": assignment_role,
            "current_pending": pending,
            "new_assignments": len(rows),
            "pending_after": pending + len(rows),
        })
    duplicate_count = 0
    if project and rows:
        for assignment_role, user_id, _ in people:
            if not user_id:
                continue
            duplicate_count += session.execute(select(func.count()).select_from(Assignment).where(
                Assignment.project_id == project.project_id,
                Assignment.review_item_id.in_(sorted(found)),
                Assignment.reviewer_user_id == user_id,
                Assignment.assignment_role == assignment_role,
            )).scalar() or 0
    if duplicate_count:
        blockers.append({"code": "duplicate_assignments", "message": f"{duplicate_count} 条相同任务已存在。", "count": duplicate_count})
    existing_roles: dict[str, set[str]] = {}
    if project and rows:
        for review_item_id, assignment_role in session.execute(
            select(Assignment.review_item_id, Assignment.assignment_role).where(
                Assignment.project_id == project.project_id,
                Assignment.review_item_id.in_(sorted(found)),
            )
        ).all():
            existing_roles.setdefault(review_item_id, set()).add(assignment_role)
    partial_secondary = sum("primary" in roles and "secondary" not in roles for roles in existing_roles.values())
    if partial_secondary:
        warnings.append({
            "code": "secondary_review_missing",
            "message": f"{partial_secondary} 条任务已有 Primary，但缺少 Secondary。",
            "count": partial_secondary,
        })
    pending_values = [row["pending_after"] for row in workloads if row["role"] in {"primary", "secondary"}]
    if len(pending_values) == 2 and min(pending_values) and max(pending_values) / min(pending_values) > 1.25:
        imbalance = round((max(pending_values) - min(pending_values)) / min(pending_values) * 100)
        warnings.append({"code": "workload_imbalance", "message": f"分配后两位 Reviewer 的待办差异约 {imbalance}%。"})
    metadata = [_item_metadata(row) for row in rows]
    by_case = dict(Counter(row.case_id for row in rows))
    by_domain = dict(Counter(row["domain"] for row in metadata))
    by_paper = dict(Counter(row["paper"] for row in metadata))
    if by_case and max(by_case.values()) / len(rows) > 0.6:
        warnings.append({"code": "case_distribution_imbalanced", "message": "单个 Case 占比超过 60%。"})
    if by_paper and max(by_paper.values()) / len(rows) > 0.5:
        warnings.append({"code": "paper_concentration_high", "message": "单篇论文占比超过 50%。"})
    return {
        "project": {"project_id": project.project_id, "name": project.name, "namespace": project.namespace, "status": project.status} if project else None,
        "strategy": strategy,
        "sampling_batch_id": sampling_batch_id or "",
        "expected_frame_hash": expected_frame_hash or "",
        "review_item_count": len(rows),
        "primary_assignments": len(rows),
        "secondary_assignments": len(rows),
        "adjudicator_assignments": len(rows),
        "assignment_count": len(rows) * 3,
        "case_distribution": by_case,
        "domain_distribution": by_domain,
        "paper_distribution": by_paper,
        "unique_cases": len(by_case),
        "unique_domains": len(by_domain),
        "unique_papers": len(by_paper),
        "workloads": workloads,
        "duplicate_assignments": duplicate_count,
        "excluded_count": len(missing),
        "unassignable_count": len(missing),
        "partial_secondary_count": partial_secondary,
        "selected_review_item_ids": sorted(found),
        "blockers": blockers,
        "warnings": warnings,
        "blocked": bool(blockers),
        "preview_writes_database": False,
    }


def create_assignment_batch(
    session: Session,
    *,
    actor: dict,
    batch_name: str,
    project_id: str,
    item_ids: Iterable[str],
    primary_reviewer_user_id: str,
    secondary_reviewer_user_id: str,
    adjudicator_user_id: str,
    strategy: str = "workload_balance",
    source: str = "existing_review_items",
    sampling_batch_id: str | None = None,
    expected_frame_hash: str | None = None,
) -> dict:
    """Revalidate and atomically create three role batches for an existing project."""
    preview = assignment_batch_preview(
        session,
        project_id=project_id,
        item_ids=item_ids,
        primary_reviewer_user_id=primary_reviewer_user_id,
        secondary_reviewer_user_id=secondary_reviewer_user_id,
        adjudicator_user_id=adjudicator_user_id,
        actor_role=actor.get("role") or "",
        strategy=strategy,
        sampling_batch_id=sampling_batch_id,
        expected_frame_hash=expected_frame_hash,
    )
    if preview["blocked"]:
        raise ValueError("assignment_batch_blocked:" + ",".join(row["code"] for row in preview["blockers"]))
    project = session.get(EvaluationProject, project_id)
    created: list[Assignment] = []
    batches: list[AssignmentBatch] = []
    operation_id = str(uuid.uuid4())
    filter_payload = {
        "operation_id": operation_id,
        "batch_name": batch_name,
        "source": source,
        "strategy": strategy,
        "sampling_batch_id": sampling_batch_id or "",
        "sampling_frame_hash": expected_frame_hash or "",
        "item_ids": preview["selected_review_item_ids"],
    }
    for assignment_role, user_id in (
        ("primary", primary_reviewer_user_id),
        ("secondary", secondary_reviewer_user_id),
        ("adjudicator", adjudicator_user_id),
    ):
        batch = AssignmentBatch(
            project_id=project.project_id,
            reviewer_user_id=user_id,
            batch_index=(session.execute(select(func.max(AssignmentBatch.batch_index)).where(AssignmentBatch.project_id == project.project_id)).scalar() or 0) + 1,
            batch_size=len(preview["selected_review_item_ids"]),
            filter_json=_json({**filter_payload, "assignment_role": assignment_role}),
            status="assigned",
            assigned_by_user_id=actor.get("user_id"),
        )
        session.add(batch)
        session.flush()
        batches.append(batch)
        for review_item_id in preview["selected_review_item_ids"]:
            row = Assignment(
                project_id=project.project_id,
                batch_id=batch.batch_id,
                review_item_id=review_item_id,
                reviewer_user_id=user_id,
                assignment_role=assignment_role,
                status="assigned",
                assigned_by_user_id=actor.get("user_id"),
            )
            session.add(row)
            created.append(row)
    session.flush()
    write_audit_event(
        session,
        action="operations_assignment_batch_created",
        object_type="assignment_batch",
        object_id=operation_id,
        actor=actor,
        project_id=project.project_id,
        metadata={**filter_payload, "assignment_count": len(created), "batch_ids": [row.batch_id for row in batches]},
    )
    return {
        **preview,
        "batch_id": operation_id,
        "batch_ids": [row.batch_id for row in batches],
        "batch_name": batch_name,
        "source": source,
        "created_at": batches[0].assigned_at.isoformat() if batches[0].assigned_at else "",
        "created_by": actor.get("display_name") or actor.get("username"),
        "creation_status": "created",
    }


def operations_batches(session: Session, *, pilot_only: bool = False) -> dict:
    projects = {row.project_id: row for row in session.execute(select(EvaluationProject)).scalars().all()}
    users = {row.user_id: row for row in session.execute(select(User)).scalars().all()}
    groups: dict[str, dict] = {}
    for batch in session.execute(select(AssignmentBatch).order_by(AssignmentBatch.assigned_at.desc())).scalars().all():
        project = projects.get(batch.project_id)
        if not project or (pilot_only and project.namespace != "pilot"):
            continue
        try:
            config = json.loads(batch.filter_json or "{}")
        except json.JSONDecodeError:
            config = {}
        operation_id = config.get("operation_id") or config.get("sampling_batch_id") or (
            f"{batch.project_id}:{batch.batch_index}:{config.get('batch_name') or 'legacy'}"
        )
        group = groups.setdefault(operation_id, {
            "batch_id": operation_id,
            "batch_name": config.get("batch_name") or f"{project.name} · 批次 {batch.batch_index + 1}",
            "project_id": project.project_id,
            "project_name": project.name,
            "namespace": project.namespace,
            "source": config.get("source") or "existing_review_items",
            "status": batch.status,
            "created_at": batch.assigned_at.isoformat() if batch.assigned_at else "",
            "roles": {},
            "item_ids": set(),
            "config": {key: value for key, value in config.items() if key != "item_ids"},
        })
        role = config.get("assignment_role")
        assignments = session.execute(select(Assignment).where(Assignment.batch_id == batch.batch_id)).scalars().all()
        if role:
            user = users.get(batch.reviewer_user_id)
            group["roles"][role] = {
                "display_name": user.display_name if user else "未知用户",
                "count": len(assignments),
                "completed": sum(row.status in {"submitted", "completed", "skipped"} for row in assignments),
            }
        else:
            for actual_role, count in Counter(row.assignment_role for row in assignments).items():
                user = users.get(batch.reviewer_user_id)
                group["roles"][actual_role] = {
                    "display_name": user.display_name if user else "未知用户",
                    "count": count,
                    "completed": sum(row.assignment_role == actual_role and row.status in {"submitted", "completed", "skipped"} for row in assignments),
                }
        group["item_ids"].update(row.review_item_id for row in assignments)
    items = []
    for group in groups.values():
        assignments = session.execute(select(Assignment).where(
            Assignment.project_id == group["project_id"],
            Assignment.review_item_id.in_(sorted(group["item_ids"])),
        )).scalars().all() if group["item_ids"] else []
        completed = sum(row.status in {"submitted", "completed", "skipped"} for row in assignments)
        group["items"] = len(group.pop("item_ids"))
        group["assignment_count"] = len(assignments)
        group["completed"] = completed
        group["completion_fraction"] = round(completed / len(assignments), 6) if assignments else None
        group["status_distribution"] = dict(Counter(row.status for row in assignments))
        review_items = [
            session.get(ReviewItem, review_item_id)
            for review_item_id in sorted({row.review_item_id for row in assignments})
        ]
        metadata = [_item_metadata(row) for row in review_items if row]
        group["sample_distribution"] = {
            "cases": dict(Counter(row.case_id for row in review_items if row)),
            "domains": dict(Counter(row["domain"] for row in metadata)),
            "papers": dict(Counter(row["paper"] for row in metadata)),
        }
        group["waiting_secondary"] = sum(
            row.assignment_role == "secondary" and row.status in OPEN_ASSIGNMENT_STATUSES
            for row in assignments
        )
        group["waiting_adjudication"] = sum(
            row.assignment_role == "adjudicator" and row.status in OPEN_ASSIGNMENT_STATUSES
            for row in assignments
        )
        group["excluded_count"] = int(group["config"].get("excluded_count") or 0)
        group["duplicate_count"] = int(group["config"].get("duplicate_count") or 0)
        group["audit_reference"] = f"assignment_batch:{group['batch_id']}"
        items.append(group)
    return {"items": items, "total": len(items)}


def assignment_to_dict(row: Assignment) -> dict:
    return {
        "assignment_id": row.assignment_id,
        "project_id": row.project_id,
        "batch_id": row.batch_id,
        "review_item_id": row.review_item_id,
        "reviewer_user_id": row.reviewer_user_id,
        "assignment_role": row.assignment_role,
        "status": row.status,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else "",
        "completed_at": row.completed_at.isoformat() if row.completed_at else "",
    }


def my_assignments(session: Session, *, user_id: str) -> list[dict]:
    rows = session.execute(select(Assignment).where(Assignment.reviewer_user_id == user_id).order_by(Assignment.assigned_at, Assignment.assignment_id)).scalars().all()
    return [assignment_to_dict(row) for row in rows]


def my_batches(session: Session, *, user_id: str) -> list[dict]:
    rows = session.execute(select(AssignmentBatch, EvaluationProject).join(EvaluationProject, AssignmentBatch.project_id == EvaluationProject.project_id).where(AssignmentBatch.reviewer_user_id == user_id).order_by(AssignmentBatch.batch_index, AssignmentBatch.batch_id)).all()
    return [{
        "batch_id": row.batch_id,
        "project_id": row.project_id,
        "project_name": project.name,
        "project_namespace": project.namespace,
        "batch_index": row.batch_index,
        "batch_size": row.batch_size,
        "status": row.status,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else "",
        "due_at": row.due_at.isoformat() if row.due_at else "",
    } for row, project in rows]


def my_review_items(
    session: Session,
    *,
    user_id: str,
    case_id: str | None = None,
    item_type: str | None = None,
    project_id: str | None = None,
) -> list[dict]:
    query = (
        select(Assignment, ReviewItem, EvaluationProject, Annotation)
        .join(ReviewItem, Assignment.review_item_id == ReviewItem.review_item_id)
        .join(EvaluationProject, Assignment.project_id == EvaluationProject.project_id)
        .outerjoin(Annotation, and_(
            Annotation.project_id == Assignment.project_id,
            Annotation.review_item_id == Assignment.review_item_id,
            Annotation.reviewer_user_id == Assignment.reviewer_user_id,
        ))
        .where(Assignment.reviewer_user_id == user_id, Assignment.assignment_role.in_(REVIEW_ASSIGNMENT_ROLES))
        .order_by(Assignment.assigned_at, ReviewItem.case_id, ReviewItem.review_item_id)
    )
    if case_id:
        query = query.where(ReviewItem.case_id == case_id)
    if item_type:
        query = query.where(ReviewItem.item_type == item_type)
    if project_id:
        query = query.where(Assignment.project_id == project_id)
    rows = session.execute(query).all()
    items = []
    for assignment, item, project, annotation in rows:
        payload = review_item_to_dict(item, annotation, assignment=assignment, project=project)
        payload["review_status"] = "reviewed" if assignment.status in {"submitted", "skipped", "revisit", "completed"} else "unreviewed"
        items.append(payload)
    return items


def my_review_workspace(session: Session, *, user_id: str) -> dict:
    items = my_review_items(session, user_id=user_id)
    cases: dict[str, dict] = {}
    for item in items:
        case_id = item.get("case_id") or "unknown"
        item_type = item.get("item_type") or "unknown"
        case = cases.setdefault(case_id, {"case_id": case_id, "total": 0, "reviewed": 0, "unreviewed": 0, "layers": {}})
        layer = case["layers"].setdefault(item_type, {
            "layer_id": item_type,
            "label": item_type.replace("_", " ").title(),
            "total": 0,
            "reviewed": 0,
            "unreviewed": 0,
            "valid": 0,
            "partial": 0,
            "invalid": 0,
            "unclear": 0,
        })
        reviewed = item.get("review_status") == "reviewed"
        case["total"] += 1
        case["reviewed" if reviewed else "unreviewed"] += 1
        layer["total"] += 1
        layer["reviewed" if reviewed else "unreviewed"] += 1
        label = str((item.get("annotation") or {}).get("final_label") or "").lower()
        if label in {"valid", "partial", "invalid", "unclear"}:
            layer[label] += 1
    result = []
    for case in cases.values():
        case["layers"] = sorted(case["layers"].values(), key=lambda row: (row["label"], row["layer_id"]))
        result.append(case)
    return {"cases": sorted(result, key=lambda row: row["case_id"]), "total_items": len(items)}


def my_review_metrics(session: Session, *, user_id: str) -> dict:
    items = my_review_items(session, user_id=user_id)
    reviewed = [item for item in items if item.get("review_status") == "reviewed"]
    labels: dict[str, int] = {}
    dispositions: dict[str, int] = {}
    cases: dict[str, int] = {}
    for item in reviewed:
        annotation = item.get("annotation") or {}
        label = annotation.get("final_label")
        disposition = annotation.get("review_disposition")
        if label:
            labels[label] = labels.get(label, 0) + 1
        if disposition:
            dispositions[disposition] = dispositions.get(disposition, 0) + 1
        case_id = item.get("case_id") or "unknown"
        cases[case_id] = cases.get(case_id, 0) + 1
    total = len(items)
    return {
        "reviewed_count": len(reviewed),
        "unreviewed_count": total - len(reviewed),
        "reviewed_fraction": round(len(reviewed) / total, 6) if total else None,
        "counts_by_final_label": labels,
        "counts_by_disposition": dispositions,
        "counts_by_case": cases,
        "note": "Assignment-scoped live metrics for the current reviewer.",
    }


def my_progress(session: Session, *, user_id: str) -> dict:
    rows = session.execute(select(Assignment.status, func.count()).where(Assignment.reviewer_user_id == user_id, Assignment.assignment_role.in_(REVIEW_ASSIGNMENT_ROLES)).group_by(Assignment.status)).all()
    counts = {status: count for status, count in rows}
    total = sum(counts.values())
    done = sum(counts.get(status, 0) for status in ("submitted", "skipped", "revisit", "completed"))
    return {"total": total, "completed": done, "remaining": max(0, total - done), "counts_by_status": counts, "fraction_complete": round(done / total, 6) if total else None}
