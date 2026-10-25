"""Database-backed workflow admission. Call within the workflow's transaction."""

import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update

from .config import settings
from .db import Project, Workspace, WorkspaceUsage, WorkflowRun


def utc_now():
    return datetime.now(timezone.utc)


def window():
    current = utc_now()
    reset = current.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return current.date().isoformat(), reset, current


def lock_workspace(db, workspace_id):
    # All queue-entry endpoints take this lock before reading/changing run state.
    # A no-op UPDATE serializes PostgreSQL replicas and SQLite writers alike.
    if not db.execute(update(Workspace).where(Workspace.id == workspace_id).values(name=Workspace.name)).rowcount:
        raise HTTPException(404, "Workspace not found.")


def active_count(db, workspace_id):
    projects = select(Project.id).where(Project.workspace_id == workspace_id)
    return db.scalar(
        select(func.count())
        .select_from(WorkflowRun)
        .where(WorkflowRun.project_id.in_(projects), WorkflowRun.status.in_(["queued", "running"]))
    )


def admit(db, workspace_id, *, generation=True):
    """Reserve capacity under lock_workspace; rollback also rolls back the charge."""
    if active_count(db, workspace_id) >= settings.workflow_concurrency_limit:
        raise HTTPException(
            429,
            "This workspace has reached its active workflow limit. Wait for a workflow to finish or reach review, then retry.",
            headers={"Retry-After": "5"},
        )
    if not generation:
        return
    day, reset, current = window()
    row = db.get(WorkspaceUsage, (workspace_id, day))
    used = row.generation_attempts if row else 0
    if used >= settings.workflow_daily_limit:
        raise HTTPException(
            429,
            f"Daily generation allowance reached. It resets at {reset.isoformat()}. Check Settings → Workflow usage or contact the site operator.",
            headers={"Retry-After": str(max(1, math.ceil((reset - current).total_seconds())))},
        )
    if row is None:
        db.add(WorkspaceUsage(workspace_id=workspace_id, day=day, generation_attempts=1))
    else:
        row.generation_attempts += 1


def snapshot(db, workspace_id):
    day, reset, _ = window()
    row = db.get(WorkspaceUsage, (workspace_id, day))
    used = row.generation_attempts if row else 0
    return {
        "day": day,
        "resets_at": reset.isoformat(),
        "generation_attempts": used,
        "daily_limit": settings.workflow_daily_limit,
        "remaining": max(0, settings.workflow_daily_limit - used),
        "active_workflows": active_count(db, workspace_id),
        "concurrency_limit": settings.workflow_concurrency_limit,
    }
