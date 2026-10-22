import asyncio
import hashlib
import io
import json
import logging
import secrets
import subprocess
import sys
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pypdf import PdfReader
from sqlalchemy import select, update, func, text
from sqlalchemy.exc import IntegrityError
from .config import settings
from .middleware import BodyLimitMiddleware
from .db import (
    Session,
    User,
    Workspace,
    SessionToken,
    Project,
    ContentRequest,
    WorkflowRun,
    WorkflowEvent,
    AgentExecution,
    SourceDocument,
    SourcePassage,
    ContentArtifact,
    ArtifactVersion,
    FactualClaim,
    ClaimEvidence,
    QualityEvaluation,
    ReviewDecision,
    ContentComment,
    PublishingJob,
    serialize,
    now,
)
from .schemas import (
    Credentials,
    ProjectInput,
    Brief,
    TextSource,
    URLSource,
    ReviewInput,
    EditInput,
    CommentInput,
    ScheduleInput,
    Preferences,
    EvidenceInput,
)
from .auth import identity, hash_password, check_password, issue_session
from .sources import store_source, fetch_url, DEMO_SOURCES, MAX_BYTES
from .gateway import availability
from .events import emit
from .workflow import enqueue
from .traceability import latest_versions, evidence_for_run, new_version, verify_version
from .prompts import AGENTS

logger = logging.getLogger("contentforge")


@asynccontextmanager
async def lifespan(app):
    # Local queue processes do not survive a restart. Preserve checkpoints for explicit resume.
    if not settings.redis_url:
        with Session.begin() as db:
            for run in db.scalars(select(WorkflowRun).where(WorkflowRun.status.in_(["running", "queued"]))):
                run.status = "interrupted"
                run.error = "Server restarted. Resume from the saved checkpoint."
    yield


app = FastAPI(title="ContentForge AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)
app.add_middleware(BodyLimitMiddleware)
rate_buckets = defaultdict(deque)
rate_lock = threading.Lock()


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.method in ("POST", "PUT", "DELETE"):
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin != settings.frontend_origin):
            return Response(json.dumps({"detail": "Cross-origin write blocked."}), 403, media_type="application/json")
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return Response(status_code=400)
        if length > MAX_BYTES + 20000:
            return Response(status_code=413)
        address = request.client.host if request.client else "unknown"
        key = (address, "auth" if "/auth/" in request.url.path else "write")
        current = time.monotonic()
        with rate_lock:
            if len(rate_buckets) > 10000:
                for old in list(rate_buckets):
                    if not rate_buckets[old] or rate_buckets[old][-1] < current - 60:
                        del rate_buckets[old]
            bucket = rate_buckets[key]
            while bucket and bucket[0] < current - 60:
                bucket.popleft()
            if len(bucket) >= (30 if key[1] == "auth" else 120):
                return Response(
                    json.dumps({"detail": "Too many requests. Try again in one minute."}),
                    429,
                    media_type="application/json",
                )
            bucket.append(current)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if not response.headers.get("content-type", "").startswith("text/event-stream"):
        response.headers["Cache-Control"] = "no-store"
    return response


def owned_project(db, project_id, who):
    project = db.get(Project, project_id)
    if not project or project.workspace_id != who["workspace_id"]:
        raise HTTPException(404, "Project not found.")
    return project


def owned_run(db, run_id, who):
    run = db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(404, "Workflow not found.")
    owned_project(db, run.project_id, who)
    return run


def dispatch(run_id, action="start"):
    try:
        enqueue(run_id, action)
    except Exception:
        with Session.begin() as db:
            run = db.get(WorkflowRun, run_id)
            run.status, run.error = (
                "interrupted",
                "The task queue is unavailable. Check Redis and worker health, then resume.",
            )
        emit(run_id, "workflow.failed", error="Queue unavailable")
        raise HTTPException(503, "Task queue unavailable. Your workflow was saved and can be resumed.") from None


@app.get("/api/health")
def health():
    with Session() as db:
        db.execute(text("SELECT 1"))
    queue = "local-thread-pool"
    if settings.redis_url:
        from redis import Redis

        try:
            Redis.from_url(settings.redis_url, socket_timeout=2).ping()
            queue = "redis"
        except Exception:
            raise HTTPException(503, "Redis unavailable") from None
    return {
        "status": "ok",
        "database": "postgresql" if settings.database_url.startswith("postgres") else "sqlite",
        "queue": queue,
    }


@app.post("/api/auth/register")
def register(body: Credentials, response: Response):
    try:
        with Session.begin() as db:
            user = User(email=body.email.lower(), name=body.name, password_hash=hash_password(body.password))
            db.add(user)
            db.flush()
            db.add(Workspace(owner_id=user.id, name=body.name + "’s workspace"))
            user_id = user.id
    except IntegrityError:
        raise HTTPException(409, "This email already has an account.") from None
    issue_session(response, user_id)
    return {"ok": True}


@app.post("/api/auth/login")
def login(body: Credentials, response: Response):
    with Session() as db:
        user = db.scalar(select(User).where(User.email == body.email.lower()))
        if not user or not check_password(body.password, user.password_hash):
            raise HTTPException(401, "Email or password is incorrect.")
        issue_session(response, user.id)
    return {"ok": True}


@app.post("/api/auth/demo")
def demo_login(response: Response):
    if not settings.demo_auth:
        raise HTTPException(403, "Guest demo sign-in is disabled.")
    with Session.begin() as db:
        user = User(
            email=f"demo-{secrets.token_hex(8)}@contentforge.local",
            name="Demo creator",
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        db.add(user)
        db.flush()
        db.add(Workspace(owner_id=user.id, name="Demo workspace"))
        user_id = user.id
    issue_session(response, user_id)
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("cf_session")
    if token:
        with Session.begin() as db:
            session = db.scalar(
                select(SessionToken).where(SessionToken.token_hash == hashlib.sha256(token.encode()).hexdigest())
            )
            if session:
                db.delete(session)
    response.delete_cookie("cf_session", path="/")
    return {"ok": True}


@app.get("/api/me")
def me(who=Depends(identity)):
    return who


@app.get("/api/settings")
def get_settings(who=Depends(identity)):
    with Session() as db:
        prefs = db.get(Workspace, who["workspace_id"]).preferences
    return {
        "preferences": Preferences(**prefs).model_dump(),
        "providers": availability(),
        "models": {"openai": settings.openai_model, "gemini": settings.gemini_model, "ollama": settings.ollama_model},
        "source_hosts": settings.source_hosts.split(","),
        "demo_auth": settings.demo_auth,
    }


@app.put("/api/settings")
def save_settings(body: Preferences, who=Depends(identity)):
    with Session.begin() as db:
        db.get(Workspace, who["workspace_id"]).preferences = body.model_dump()
    return {"ok": True}


@app.get("/api/projects")
def projects(who=Depends(identity)):
    with Session() as db:
        return [
            serialize(p)
            for p in db.scalars(
                select(Project).where(Project.workspace_id == who["workspace_id"]).order_by(Project.created_at.desc())
            )
        ]


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectInput, who=Depends(identity)):
    with Session.begin() as db:
        project = Project(workspace_id=who["workspace_id"], **body.model_dump())
        db.add(project)
        db.flush()
        return serialize(project)


@app.get("/api/sources")
def sources(who=Depends(identity)):
    with Session() as db:
        result = []
        for source in db.scalars(
            select(SourceDocument)
            .where(SourceDocument.workspace_id == who["workspace_id"])
            .order_by(SourceDocument.created_at.desc())
        ):
            row = serialize(source)
            row["passages"] = [
                serialize(p)
                for p in db.scalars(
                    select(SourcePassage).where(SourcePassage.source_id == source.id).order_by(SourcePassage.ordinal)
                )
            ]
            result.append(row)
        return result


@app.post("/api/sources/text", status_code=201)
def text_source(body: TextSource, who=Depends(identity)):
    with Session.begin() as db:
        source = store_source(db, who["workspace_id"], body.title, body.text)
        return serialize(source)


@app.post("/api/sources/url", status_code=201)
def url_source(body: URLSource, who=Depends(identity)):
    try:
        title, content, url = fetch_url(body.url)
    except Exception as error:
        raise HTTPException(
            400, str(error) if isinstance(error, ValueError) else "Could not retrieve this source securely."
        ) from None
    with Session.begin() as db:
        source = store_source(db, who["workspace_id"], title, content, "url", url)
        return serialize(source)


@app.post("/api/sources/upload", status_code=201)
def upload_source(file: UploadFile = File(...), who=Depends(identity)):
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Files must be 2 MB or smaller.")
    suffix = Path(file.filename or "").suffix.lower()
    try:
        if suffix == ".pdf":
            if not raw.startswith(b"%PDF-"):
                raise ValueError("Invalid PDF signature.")
            result = subprocess.run(
                [sys.executable, "-m", "app.pdf_extract"], input=raw, capture_output=True, timeout=10
            )
            if result.returncode:
                raise ValueError(
                    "PDF extraction failed or exceeded resource limits. Use unencrypted text PDFs with at most 30 pages."
                )
            content = json.loads(result.stdout)["text"]
        elif suffix in (".txt", ".md"):
            content = raw.decode("utf-8")
        else:
            raise ValueError("Upload a PDF, UTF-8 TXT, or Markdown file.")
        with Session.begin() as db:
            source = store_source(
                db, who["workspace_id"], Path(file.filename).name, content, "pdf" if suffix == ".pdf" else "upload"
            )
            return serialize(source)
    except Exception as error:
        raise HTTPException(
            400, str(error) if isinstance(error, ValueError) else "This file could not be safely parsed."
        ) from None


@app.post("/api/workflows", status_code=201)
def create_workflow(body: Brief, who=Depends(identity)):
    if not availability().get(body.mode):
        raise HTTPException(400, "Configure this provider on the server or choose demo mode.")
    with Session.begin() as db:
        # Lock the workspace row to bound simultaneous starts in PostgreSQL.
        db.execute(update(Workspace).where(Workspace.id == who["workspace_id"]).values(name=Workspace.name))
        project_ids = select(Project.id).where(Project.workspace_id == who["workspace_id"])
        active = db.scalar(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.project_id.in_(project_ids), WorkflowRun.status.in_(["queued", "running"]))
        )
        if active >= 2:
            raise HTTPException(429, "Two workflows are already running in this workspace.")
        for source_id in body.source_ids:
            source = db.get(SourceDocument, source_id)
            if not source or source.workspace_id != who["workspace_id"]:
                raise HTTPException(404, "Source not found.")
        if body.project_id:
            project = owned_project(db, body.project_id, who)
        else:
            project = Project(workspace_id=who["workspace_id"], name=body.prompt[:90])
            db.add(project)
            db.flush()
        brief = body.model_dump()
        if body.mode == "demo":
            sample_ids = []
            for title, content in DEMO_SOURCES:
                source = store_source(db, who["workspace_id"], title, content, "demo")
                sample_ids.append(source.id)
            brief["source_ids"] = sample_ids
        request = ContentRequest(project_id=project.id, brief=brief)
        db.add(request)
        db.flush()
        run = WorkflowRun(project_id=project.id, request_id=request.id, mode=body.mode)
        db.add(run)
        db.flush()
        run_id = run.id
    emit(run_id, "workflow.created", summary="Content campaign created", mode=body.mode)
    for agent in AGENTS:
        emit(run_id, "agent.queued", agent)
    dispatch(run_id)
    return {"id": run_id, "project_id": project.id}


@app.get("/api/workflows")
def workflows(who=Depends(identity)):
    with Session() as db:
        runs = db.scalars(
            select(WorkflowRun)
            .join(Project)
            .where(Project.workspace_id == who["workspace_id"])
            .order_by(WorkflowRun.created_at.desc())
            .limit(100)
        ).all()
        return [{**serialize(r), "title": db.get(Project, r.project_id).name} for r in runs]


@app.get("/api/workflows/{run_id}")
def workflow(run_id: str, who=Depends(identity)):
    with Session() as db:
        run = owned_run(db, run_id, who)
        artifacts, versions, claims, links = evidence_for_run(db, run_id)
        brief = db.get(ContentRequest, run.request_id).brief
        documents = (
            db.scalars(select(SourceDocument).where(SourceDocument.id.in_(brief["source_ids"]))).all()
            if brief["source_ids"]
            else []
        )
        passages = (
            db.scalars(select(SourcePassage).where(SourcePassage.source_id.in_([s.id for s in documents]))).all()
            if documents
            else []
        )
        executions = db.scalars(
            select(AgentExecution).where(AgentExecution.run_id == run_id).order_by(AgentExecution.created_at)
        ).all()
        events = db.scalars(
            select(WorkflowEvent).where(WorkflowEvent.run_id == run_id).order_by(WorkflowEvent.sequence)
        ).all()
        quality = db.scalars(
            select(QualityEvaluation).where(QualityEvaluation.run_id == run_id).order_by(QualityEvaluation.created_at)
        ).all()
        reviews = db.scalars(
            select(ReviewDecision).where(ReviewDecision.run_id == run_id).order_by(ReviewDecision.created_at)
        ).all()
        comments = (
            db.scalars(select(ContentComment).where(ContentComment.version_id.in_([v.id for v in versions]))).all()
            if versions
            else []
        )
        data = {**serialize(run), "title": db.get(Project, run.project_id).name, "brief": brief}
        for name, rows in [
            ("artifacts", artifacts),
            ("versions", versions),
            ("claims", claims),
            ("links", links),
            ("sources", documents),
            ("passages", passages),
            ("executions", executions),
            ("events", events),
            ("quality", quality),
            ("reviews", reviews),
            ("comments", comments),
        ]:
            data[name] = [serialize(row) for row in rows]
        return data


@app.get("/api/workflows/{run_id}/events")
async def stream_events(run_id: str, request: Request, after: int = 0, who=Depends(identity)):
    with Session() as db:
        owned_run(db, run_id, who)
    try:
        cursor = max(after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        raise HTTPException(400, "Invalid event cursor.") from None

    async def stream():
        nonlocal cursor
        last_ping = time.monotonic()
        while not await request.is_disconnected():
            with Session() as db:
                rows = db.scalars(
                    select(WorkflowEvent)
                    .where(WorkflowEvent.run_id == run_id, WorkflowEvent.sequence > cursor)
                    .order_by(WorkflowEvent.sequence)
                    .limit(100)
                ).all()
                events = [serialize(row) for row in rows]
            for event in events:
                cursor = event["sequence"]
                yield f"id: {cursor}\nevent: workflow\ndata: {json.dumps(event)}\n\n"
            if time.monotonic() - last_ping > 15:
                yield ": heartbeat\n\n"
                last_ping = time.monotonic()
            await asyncio.sleep(0.4)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache, no-transform", "Content-Encoding": "identity"},
    )


@app.post("/api/workflows/{run_id}/cancel")
def cancel(run_id: str, who=Depends(identity)):
    with Session.begin() as db:
        run = owned_run(db, run_id, who)
        changed = db.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.id == run_id,
                WorkflowRun.status.in_(["queued", "running", "awaiting_approval", "interrupted", "failed"]),
            )
            .values(cancel_requested=1, status="cancelled")
        ).rowcount
        if not changed:
            raise HTTPException(409, "This workflow cannot be cancelled in its current state.")
    emit(
        run_id, "workflow.cancelled", summary="Cancellation requested; in-flight provider calls finish before stopping."
    )
    return {"ok": True}


@app.post("/api/workflows/{run_id}/retry")
def retry(run_id: str, who=Depends(identity)):
    with Session.begin() as db:
        run = owned_run(db, run_id, who)
        changed = db.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.id == run_id, WorkflowRun.status.in_(["failed", "interrupted"]), WorkflowRun.retry_count < 3
            )
            .values(status="queued", retry_count=WorkflowRun.retry_count + 1, cancel_requested=0)
        ).rowcount
        if not changed:
            raise HTTPException(409, "Only failed or interrupted runs can resume, up to three attempts.")
        has_executions = bool(db.scalar(select(AgentExecution.id).where(AgentExecution.run_id == run_id).limit(1)))
    dispatch(run_id, "retry" if has_executions else "start")
    return {"ok": True}


@app.post("/api/workflows/{run_id}/review")
def review(run_id: str, body: ReviewInput, who=Depends(identity)):
    action = None
    with Session.begin() as db:
        run = owned_run(db, run_id, who)
        # Claim the transition before reading versions so simultaneous edits/reviews serialize.
        changed = db.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == run_id, WorkflowRun.status == "awaiting_approval")
            .values(status="reviewing")
        ).rowcount
        if not changed:
            raise HTTPException(409, "This workflow is not awaiting review.")
        pairs = latest_versions(db, run_id)
        version_ids = [v.id for _, v in pairs]
        warnings = db.scalars(
            select(FactualClaim).where(FactualClaim.version_id.in_(version_ids), FactualClaim.status != "supported")
        ).all()
        if body.decision == "approve" and warnings and not body.acknowledge_warnings:
            raise HTTPException(409, "Acknowledge the remaining evidence warnings before approving.")
        db.add(
            ReviewDecision(
                run_id=run_id,
                user_id=who["user_id"],
                decision=body.decision,
                comment=body.comment,
                version_ids=version_ids,
            )
        )
        run = db.get(WorkflowRun, run_id, populate_existing=True)
        if body.decision == "approve":
            run.status = "queued"
            action = "approve"
            for claim in db.scalars(select(FactualClaim).where(FactualClaim.version_id.in_(version_ids))):
                claim.history = claim.history + [
                    {"state": "human_approved", "at": now(), "evidence_status": claim.status}
                ]
        elif body.decision == "reject":
            run.status = "rejected"
        else:
            if run.cycle >= 5:
                raise HTTPException(409, "Five human revision rounds reached. Create a new campaign.")
            if not body.comment.strip():
                raise HTTPException(400, "Describe the revision you need.")
            request = db.get(ContentRequest, run.request_id)
            request.brief = {**request.brief, "human_feedback": body.comment}
            run.cycle += 1
            run.status, run.revision = "queued", 0
            action = "start"
    emit(run_id, "review." + body.decision, summary=body.comment or body.decision, reviewer_id=who["user_id"])
    if action:
        dispatch(run_id, action)
    return {"ok": True}


@app.put("/api/artifacts/{artifact_id}")
def edit_artifact(artifact_id: str, body: EditInput, who=Depends(identity)):
    with Session.begin() as db:
        artifact = db.get(ContentArtifact, artifact_id)
        if not artifact:
            raise HTTPException(404, "Artifact not found.")
        run = owned_run(db, artifact.run_id, who)
        changed = db.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == run.id, WorkflowRun.status == "awaiting_approval")
            .values(status="awaiting_approval")
        ).rowcount
        if not changed:
            raise HTTPException(
                409, "Edit content while it is awaiting approval. Request a new campaign for already exported content."
            )
        current = db.scalar(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact.id)
            .order_by(ArtifactVersion.number.desc())
        )
        if current.number != body.base_version:
            raise HTTPException(409, "This document changed in another tab. Reload before saving.")
        version = new_version(db, artifact, body.body, "Human edit; evidence reset")
        verify_version(db, version, [], edited=True)
        data = serialize(version)
    emit(
        run.id,
        "content.edited",
        version_id=data["id"],
        summary="Human edit saved. Evidence status reset for this version.",
    )
    return data


@app.post("/api/versions/{version_id}/comments")
def comment(version_id: str, body: CommentInput, who=Depends(identity)):
    with Session.begin() as db:
        version = db.get(ArtifactVersion, version_id)
        if not version:
            raise HTTPException(404, "Version not found.")
        artifact = db.get(ContentArtifact, version.artifact_id)
        owned_run(db, artifact.run_id, who)
        if body.quote and body.quote not in version.body:
            raise HTTPException(400, "The selected quote is not in this version.")
        record = ContentComment(version_id=version_id, user_id=who["user_id"], **body.model_dump())
        db.add(record)
        db.flush()
        return serialize(record)


@app.get("/api/workflows/{run_id}/export")
def export(run_id: str, format: str = "markdown", who=Depends(identity)):
    with Session() as db:
        run = owned_run(db, run_id, who)
        if run.status != "completed":
            raise HTTPException(409, "Approve the current content and wait for export preparation first.")
        pairs = latest_versions(db, run_id)
        approval = db.scalar(
            select(ReviewDecision)
            .where(ReviewDecision.run_id == run_id, ReviewDecision.decision == "approve")
            .order_by(ReviewDecision.created_at.desc())
        )
        if not approval or set(approval.version_ids) != {v.id for _, v in pairs}:
            raise HTTPException(409, "Current versions are not approved.")
        claims = db.scalars(select(FactualClaim).where(FactualClaim.version_id.in_([v.id for _, v in pairs]))).all()
        disclaimer = (
            "DEMO: generated from labeled sample fixtures. Not live AI research.\n\n" if run.mode == "demo" else ""
        )
        if format == "json":
            payload = {
                "mode": run.mode,
                "artifacts": [{**serialize(a), "version": serialize(v)} for a, v in pairs],
                "claims": [serialize(c) for c in claims],
                "approval": serialize(approval),
            }
            data, mime, filename = json.dumps(payload, indent=2), "application/json", "contentforge-campaign.json"
        elif format == "markdown":
            data = disclaimer + "\n\n---\n\n".join(
                f"# {a.platform.upper()} · v{v.number}\n\n{v.body}" for a, v in pairs
            )
            data += "\n\n## Evidence audit\n\n" + "\n".join(f"- [{c.status}] {c.text}" for c in claims)
            data += "\n\nHuman approval is an editorial decision, not a factual guarantee. See the execution report for source passages and relationships."
            mime, filename = "text/markdown", "contentforge-campaign.md"
        else:
            raise HTTPException(400, "Choose markdown or json.")
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/workflows/{run_id}/report")
def report(run_id: str, who=Depends(identity)):
    return Response(
        json.dumps(workflow(run_id, who), indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="contentforge-execution.json"'},
    )


@app.get("/api/analytics")
def analytics(who=Depends(identity)):
    with Session() as db:
        projects = db.scalars(select(Project).where(Project.workspace_id == who["workspace_id"])).all()
        runs = db.scalars(select(WorkflowRun).where(WorkflowRun.project_id.in_([p.id for p in projects]))).all()
        run_ids = [r.id for r in runs]
        executions = db.scalars(select(AgentExecution).where(AgentExecution.run_id.in_(run_ids))).all()
        quality = db.scalars(
            select(QualityEvaluation)
            .where(QualityEvaluation.run_id.in_(run_ids))
            .order_by(QualityEvaluation.created_at)
        ).all()
        pairs = [pair for run in runs for pair in latest_versions(db, run.id)]
        claims = db.scalars(select(FactualClaim).where(FactualClaim.version_id.in_([v.id for _, v in pairs]))).all()
        agents = []
        for agent in AGENTS:
            rows = [e for e in executions if e.agent == agent]
            completed = [e for e in rows if e.status == "completed"]
            agents.append(
                {
                    "agent": agent,
                    "name": AGENTS[agent][0],
                    "executions": len(rows),
                    "success_rate": round(len(completed) / len(rows) * 100, 1) if rows else None,
                    "average_ms": round(sum(e.duration_ms or 0 for e in completed) / len(completed), 1)
                    if completed
                    else None,
                    "retries": sum(e.retries for e in rows),
                    "estimated_cost": sum(e.estimated_cost or 0 for e in rows)
                    if any(e.estimated_cost is not None for e in rows)
                    else None,
                }
            )
        return {
            "projects": len(projects),
            "runs": len(runs),
            "active": sum(r.status in ("running", "queued") for r in runs),
            "artifacts": len(pairs),
            "pending": sum(r.status == "awaiting_approval" for r in runs),
            "claim_count": len(claims),
            "supported_claims": sum(c.status == "supported" for c in claims),
            "coverage": round(sum(c.status == "supported" for c in claims) / len(claims) * 100) if claims else None,
            "agents": agents,
            "quality": [serialize(q) for q in quality],
            "models": list(dict.fromkeys(e.model for e in executions)),
        }


@app.get("/api/calendar")
def calendar(who=Depends(identity)):
    with Session() as db:
        result = []
        for job in db.scalars(
            select(PublishingJob)
            .where(PublishingJob.workspace_id == who["workspace_id"])
            .order_by(PublishingJob.scheduled_at)
        ):
            artifact = db.get(ContentArtifact, job.artifact_id)
            result.append({**serialize(job), "title": artifact.title, "platform": artifact.platform})
        return result


@app.post("/api/calendar", status_code=201)
def schedule(body: ScheduleInput, who=Depends(identity)):
    try:
        date = datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
        if date.tzinfo is None or date < datetime.now(timezone.utc):
            raise ValueError()
    except ValueError:
        raise HTTPException(400, "Choose a future date with a timezone.") from None
    with Session.begin() as db:
        artifact = db.get(ContentArtifact, body.artifact_id)
        if not artifact:
            raise HTTPException(404, "Artifact not found.")
        run = owned_run(db, artifact.run_id, who)
        if run.status != "completed":
            raise HTTPException(409, "Schedule approved content after export preparation.")
        version = db.scalar(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact.id)
            .order_by(ArtifactVersion.number.desc())
        )
        job = PublishingJob(
            workspace_id=who["workspace_id"],
            artifact_id=artifact.id,
            version_id=version.id,
            scheduled_at=date.astimezone(timezone.utc).isoformat(),
        )
        db.add(job)
        db.flush()
        return serialize(job)


@app.delete("/api/calendar/{job_id}")
def unschedule(job_id: str, who=Depends(identity)):
    with Session.begin() as db:
        job = db.get(PublishingJob, job_id)
        if not job or job.workspace_id != who["workspace_id"]:
            raise HTTPException(404, "Schedule not found.")
        job.status = "cancelled"
    return {"ok": True}


@app.post("/api/claims/{claim_id}/evidence", status_code=201)
def assess_evidence(claim_id: str, body: EvidenceInput, who=Depends(identity)):
    with Session.begin() as db:
        claim = db.get(FactualClaim, claim_id)
        if not claim:
            raise HTTPException(404, "Claim not found.")
        version = db.get(ArtifactVersion, claim.version_id)
        artifact = db.get(ContentArtifact, version.artifact_id)
        run = owned_run(db, artifact.run_id, who)
        changed = db.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == run.id, WorkflowRun.status == "awaiting_approval")
            .values(status="awaiting_approval")
        ).rowcount
        if not changed:
            raise HTTPException(409, "Evidence assessment is available while the campaign awaits approval.")
        if version.id not in {v.id for _, v in latest_versions(db, run.id)}:
            raise HTTPException(409, "Assess the latest content version.")
        passage = db.get(SourcePassage, body.passage_id)
        brief = db.get(ContentRequest, run.request_id).brief
        if not passage or passage.source_id not in brief["source_ids"]:
            raise HTTPException(404, "Passage not found in this campaign.")
        if body.quote not in passage.text:
            raise HTTPException(400, "The quote must appear exactly in the stored passage.")
        link = ClaimEvidence(claim_id=claim.id, passage_id=passage.id, relation=body.relation, quote=body.quote)
        db.add(link)
        db.flush()
        relations = db.scalars(select(ClaimEvidence.relation).where(ClaimEvidence.claim_id == claim.id)).all()
        claim.status = (
            "disputed" if "contradicts" in relations else "supported" if "supports" in relations else "unverified"
        )
        claim.explanation = (
            "Human evidence assessment: "
            + body.explanation
            + " Source agreement is not an independent truth guarantee."
        )
        claim.history = claim.history + [
            {"state": "re_evaluated", "at": now(), "reviewer_id": who["user_id"], "relation": body.relation},
            {"state": claim.status, "at": now()},
        ]
        result = serialize(claim)
    emit(run.id, "claim.assessed", claim_id=claim_id, relation=body.relation, reviewer_id=who["user_id"])
    return result
