from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, event, ForeignKey, String, Text, JSON, Integer, Float, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


def uid():
    return uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Entity:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class User(Entity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(100))
    email_verified_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Workspace(Entity, Base):
    __tablename__ = "workspaces"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120))
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)


class SessionToken(Entity, Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[str] = mapped_column(String(40))


class PasswordReset(Base):
    __tablename__ = "password_resets"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[str] = mapped_column(String(40))
    requested_at: Mapped[str] = mapped_column(String(40))


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[str] = mapped_column(String(40))
    requested_at: Mapped[str] = mapped_column(String(40))


class Project(Entity, Base):
    __tablename__ = "projects"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")


class ContentRequest(Entity, Base):
    __tablename__ = "content_requests"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    brief: Mapped[dict] = mapped_column(JSON)


class WorkflowRun(Entity, Base):
    __tablename__ = "workflow_runs"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("content_requests.id"))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    mode: Mapped[str] = mapped_column(String(20), default="demo")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    cycle: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_sequence: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class WorkflowEvent(Entity, Base):
    __tablename__ = "workflow_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(60))
    agent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentExecution(Entity, Base):
    __tablename__ = "agent_executions"
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    agent: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(120), default="demo-fixture")
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    outputs: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")


class SourceDocument(Entity, Base):
    __tablename__ = "source_documents"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="available")
    credibility: Mapped[str] = mapped_column(Text, default="User supplied; not independently assessed")
    publication_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)


class SourcePassage(Entity, Base):
    __tablename__ = "source_passages"
    source_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer)


class ContentArtifact(Entity, Base):
    __tablename__ = "content_artifacts"
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    platform: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))


class ArtifactVersion(Entity, Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (UniqueConstraint("artifact_id", "number"),)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("content_artifacts.id"), index=True)
    execution_id: Mapped[str | None] = mapped_column(ForeignKey("agent_executions.id"), nullable=True)
    number: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)


class FactualClaim(Entity, Base):
    __tablename__ = "factual_claims"
    version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.id"), index=True)
    execution_id: Mapped[str | None] = mapped_column(ForeignKey("agent_executions.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(25))
    explanation: Mapped[str] = mapped_column(Text)
    history: Mapped[list] = mapped_column(JSON, default=list)


class ClaimEvidence(Entity, Base):
    __tablename__ = "claim_evidence_links"
    claim_id: Mapped[str] = mapped_column(ForeignKey("factual_claims.id"), index=True)
    passage_id: Mapped[str] = mapped_column(ForeignKey("source_passages.id"))
    relation: Mapped[str] = mapped_column(String(30))
    quote: Mapped[str] = mapped_column(Text)


class QualityEvaluation(Entity, Base):
    __tablename__ = "quality_evaluations"
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("agent_executions.id"))
    score: Mapped[float] = mapped_column(Float)
    dimensions: Mapped[dict] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer)


class ReviewDecision(Entity, Base):
    __tablename__ = "review_decisions"
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str] = mapped_column(Text)
    version_ids: Mapped[list] = mapped_column(JSON)


class ContentComment(Entity, Base):
    __tablename__ = "content_comments"
    version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text, default="")


class PublishingJob(Entity, Base):
    __tablename__ = "publishing_jobs"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    artifact_id: Mapped[str] = mapped_column(ForeignKey("content_artifacts.id"))
    version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.id"))
    scheduled_at: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="scheduled_draft")


class UsageAnalytics(Entity, Base):
    __tablename__ = "usage_analytics"
    execution_id: Mapped[str] = mapped_column(ForeignKey("agent_executions.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(30))
    metrics: Mapped[dict] = mapped_column(JSON)


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False, "timeout": 30} if settings.database_url.startswith("sqlite") else {},
)
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_config(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")


Session = sessionmaker(engine, expire_on_commit=False)


def serialize(obj):
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
