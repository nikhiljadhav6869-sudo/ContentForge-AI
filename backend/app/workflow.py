import json
import operator
import sqlite3
import threading
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, TypedDict
from sqlalchemy import select, update
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver
from .config import settings
from .db import (
    Session,
    WorkflowRun,
    ContentRequest,
    Project,
    AgentExecution,
    SourceDocument,
    SourcePassage,
    ContentArtifact,
    ArtifactVersion,
    QualityEvaluation,
    UsageAnalytics,
    FactualClaim,
    ReviewDecision,
    now,
)
from .events import emit
from .gateway import complete, ProviderError
from .schemas import AgentOutput, AgentInput, AGENT_DATA_SCHEMAS
from pydantic import ValidationError
from .prompts import AGENTS
from .traceability import latest_versions, new_version, verify_version, SUPPORTED, DISPUTED, UNVERIFIED


def merge(left, right):
    return {**left, **right}


class State(TypedDict):
    run_id: str
    brief: dict
    revision: int
    results: Annotated[dict, merge]
    needs_revision: bool


class Cancelled(Exception):
    pass


def check_cancel(run_id):
    with Session() as db:
        if db.get(WorkflowRun, run_id).cancel_requested:
            raise Cancelled()


def reference_context(run_id):
    with Session() as db:
        run = db.get(WorkflowRun, run_id)
        brief = db.get(ContentRequest, run.request_id).brief
        sources = (
            db.scalars(select(SourceDocument).where(SourceDocument.id.in_(brief["source_ids"]))).all()
            if brief["source_ids"]
            else []
        )
        passages = (
            db.scalars(select(SourcePassage).where(SourcePassage.source_id.in_([s.id for s in sources]))).all()
            if sources
            else []
        )
        return [{"id": p.id, "source_id": p.source_id, "text": p.text} for p in passages][:60]


def drafts(run_id):
    with Session() as db:
        return [
            {"platform": a.platform, "title": a.title, "body": v.body, "version": v.number}
            for a, v in latest_versions(db, run_id)
        ]


def demo_artifacts(brief, revision):
    # Fixtures are explicitly identified in both UI and persisted execution records.
    topic = brief["prompt"].strip().rstrip(".")
    paragraphs = [SUPPORTED]
    if revision == 0:
        paragraphs += [DISPUTED, UNVERIFIED]
    else:
        paragraphs += [
            "Electric vehicles are not emission-free across their entire lifecycle.",
            "Manufacturing and electricity generation contribute to lifecycle emissions.",
        ]
    evidence = "\n\n".join(paragraphs)
    results = []
    for platform in brief["platforms"]:
        if platform == "blog":
            body = f"# Electric vehicles in India: look beyond the headlines\n\n## The evidence\n\n{evidence}\n\n## Make an informed comparison\n\nCompare purchase price, charging access, battery warranty and daily travel needs.\n\nAsk how the electricity is generated and what the manufacturer means by range.\n\n## Your next step\n\nUse the source library to check the statements before sharing this campaign."
        elif platform == "linkedin":
            body = f"Electric vehicles deserve a nuanced conversation.\n\n{evidence}\n\nBefore choosing a vehicle, compare your daily travel needs with charging access.\n\nWhat would you investigate first?\n\n#ElectricVehicles #InformedChoices"
        elif platform == "instagram":
            body = f"A cleaner journey starts with better questions.\n\n{evidence}\n\nSave this checklist: charging • warranty • everyday travel.\n\n#EVIndia #LearnWithEvidence"
        else:
            body = f"# Electric vehicles, explained\n\n[HOOK]\nWhat should college students ask about electric vehicles?\n\n[EXPLAIN]\n{evidence}\n\n[COMPARE]\nCompare charging access, battery warranty and daily travel needs.\n\n[CLOSE]\nExplore the reference notes and keep asking good questions."
        results.append({"platform": platform, "title": "Electric vehicles: an informed perspective", "body": body})
    return results


def demo_output(agent, state):
    if agent == "supervisor":
        data = {
            "plan": list(AGENTS),
            "routing": "Research and strategy run in parallel, then writing and verification. Human approval gates export.",
        }
    elif agent == "research":
        data = {
            "findings": [SUPPORTED, "Lifecycle emissions require qualification."],
            "source_ids": state["brief"]["source_ids"],
            "gaps": ["No official current India statistics are included in this demonstration."],
        }
    elif agent == "strategy":
        data = {
            "angle": "Practical EV literacy for students",
            "outline": ["Understand tailpipe emissions", "Qualify lifecycle claims", "Compare everyday needs"],
            "audience": state["brief"]["audience"],
            "tone": state["brief"]["tone"],
        }
    elif agent == "writer":
        data = {"artifacts": demo_artifacts(state["brief"], state["revision"])}
    elif agent in ("editor", "brand", "seo"):
        data = {
            "notes": [f"{AGENTS[agent][0]} reviewed the sample campaign."],
            "revised_artifacts": drafts(state["run_id"]),
            "metadata": {"keywords": ["electric vehicles", "India", "evidence"], "disclosure": "Demonstration fixture"},
        }
    elif agent == "fact_checker":
        data = {
            "method": "Stored passage comparison; explicit contradiction fixture; unsupported claims remain unverified."
        }
    elif agent == "quality":
        data = {
            "criticism": ["Remove disputed lifecycle claim and unsupported range claim."]
            if state["revision"] == 0
            else [],
            "recommended_agent": "writer",
        }
    else:
        data = {"formats": ["markdown", "json"], "publication": "No external publication performed."}
    return AgentOutput(
        summary=f"{AGENTS[agent][0]} completed a labeled demo step.",
        data=data,
        warnings=["Demonstration uses curated sample references, not live AI or web research."],
    )


def persist_artifacts(run_id, items, execution_id, reason, platforms):
    if (
        not isinstance(items, list)
        or {i.get("platform") for i in items if isinstance(i, dict)} != set(platforms)
        or len(items) != len(platforms)
    ):
        raise ProviderError("Agent did not return exactly the requested content formats.")
    with Session.begin() as db:
        for item in items:
            body = item.get("body")
            if not isinstance(body, str) or not 20 <= len(body) <= 40000:
                raise ProviderError("Agent returned an invalid content document.")
            artifact = db.scalar(
                select(ContentArtifact).where(
                    ContentArtifact.run_id == run_id, ContentArtifact.platform == item["platform"]
                )
            )
            if not artifact:
                artifact = ContentArtifact(
                    run_id=run_id, platform=item["platform"], title=str(item.get("title", item["platform"]))[:300]
                )
                db.add(artifact)
                db.flush()
            previous = db.scalar(
                select(ArtifactVersion)
                .where(ArtifactVersion.artifact_id == artifact.id)
                .order_by(ArtifactVersion.number.desc())
            )
            if not previous or previous.body != body:
                new_version(db, artifact, body, reason, execution_id)


def evaluate_claims(state, execution_id):
    all_claims = []
    with Session.begin() as db:
        for _, version in latest_versions(db, state["run_id"]):
            all_claims += verify_version(
                db, version, state["brief"]["source_ids"], execution_id, state["brief"]["mode"] == "demo"
            )
    counts = {status: sum(c.status == status for c in all_claims) for status in ("supported", "disputed", "unverified")}
    for claim in all_claims:
        emit(state["run_id"], "claim.extracted", "fact_checker", claim_id=claim.id, version_id=claim.version_id)
        emit(
            state["run_id"],
            "claim.verified" if claim.status == "supported" else f"claim.{claim.status}",
            "fact_checker",
            claim_id=claim.id,
            status=claim.status,
        )
    return counts


def quality_score(state, execution_id):
    with Session() as db:
        pairs = latest_versions(db, state["run_id"])
        claims = db.scalars(select(FactualClaim).where(FactualClaim.version_id.in_([v.id for _, v in pairs]))).all()
    support = sum(c.status == "supported" for c in claims) / max(len(claims), 1) * 100
    bodies = [v.body for _, v in pairs]
    # Explainable deterministic rubric: these are heuristics, never model confidence.
    dimensions = {
        "factual_support": {
            "weight": 25,
            "score": round(support),
            "basis": "Verbatim-supported claims / extracted claims; source truth is not certified.",
        },
        "relevance": {
            "weight": 20,
            "score": 100
            if all(any(w.lower() in b.lower() for w in state["brief"]["prompt"].split() if len(w) > 4) for b in bodies)
            else 50,
            "basis": "Topic word overlap.",
        },
        "clarity": {
            "weight": 15,
            "score": 90 if all(len(b.split()) / max(b.count("."), 1) < 35 for b in bodies) else 60,
            "basis": "Average words per sentence below 35.",
        },
        "structure": {
            "weight": 15,
            "score": 100 if all("\n\n" in b for b in bodies) else 50,
            "basis": "Paragraph separation.",
        },
        "brand_consistency": {
            "weight": 10,
            "score": 80 if state["brief"]["brand"] else 50,
            "basis": "Brand instructions supplied to guardian; heuristic, not semantic certification.",
        },
        "platform_suitability": {
            "weight": 10,
            "score": 100 if len(pairs) == len(state["brief"]["platforms"]) else 0,
            "basis": "All requested channel artifacts exist.",
        },
        "engagement": {
            "weight": 5,
            "score": 80 if any("?" in b or "Compare" in b for b in bodies) else 50,
            "basis": "Question or comparison prompt present.",
        },
    }
    score = round(sum(d["score"] * d["weight"] / 100 for d in dimensions.values()), 1)
    warnings = []
    if any(c.status != "supported" for c in claims):
        warnings.append("Factual support is incomplete. Review disputed and unverified claims before approval.")
    if not claims:
        warnings.append("No factual claims were extracted. This does not establish factual accuracy.")
    if state["brief"]["mode"] == "demo":
        warnings.append("Sample references only; verify against authoritative sources before publication.")
    with Session.begin() as db:
        db.add(
            QualityEvaluation(
                run_id=state["run_id"],
                execution_id=execution_id,
                score=score,
                dimensions=dimensions,
                warnings=warnings,
                revision=state["revision"],
            )
        )
    return {
        "score": score,
        "dimensions": dimensions,
        "warnings": warnings,
        "needs_revision": score < state["brief"]["quality_threshold"] or any(c.status != "supported" for c in claims),
    }


def agent_node(agent):
    def node(state):
        run_id = state["run_id"]
        check_cancel(run_id)
        instruction = AGENTS[agent][1]
        context = {"prior_results": state.get("results", {}), "revision": state["revision"]}
        if agent in ("research", "writer", "fact_checker", "quality"):
            context["passages"] = reference_context(run_id)
        if agent in ("fact_checker", "editor", "brand", "seo", "quality", "export"):
            context["artifacts"] = drafts(run_id)
        inputs = AgentInput(brief=state["brief"], context=context, instruction=instruction).model_dump()
        with Session.begin() as db:
            execution = AgentExecution(run_id=run_id, agent=agent, status="running", inputs=inputs)
            db.add(execution)
            db.flush()
            execution_id = execution.id
        emit(
            run_id,
            "agent.started",
            agent,
            execution_id=execution_id,
            summary=f"{AGENTS[agent][0]} started",
            revision=state["revision"],
        )
        start = time.monotonic()
        metrics = {
            "model": "demo-fixture",
            "input_tokens": None,
            "output_tokens": None,
            "estimated_cost": None,
            "retries": 0,
        }
        try:
            if agent in ("research", "fact_checker", "export"):
                emit(
                    run_id,
                    "agent.tool_started",
                    agent,
                    tool={
                        "research": "stored_source_reader",
                        "fact_checker": "passage_matcher",
                        "export": "approved_artifact_packager",
                    }[agent],
                )
            if state["brief"]["mode"] == "demo":
                time.sleep(settings.demo_step_delay)
                output = demo_output(agent, state)
            elif agent in ("fact_checker", "export"):
                output = AgentOutput(summary=f"{AGENTS[agent][0]} applied deterministic integrity rules.", data={})
                metrics["model"] = "deterministic-tool"
            else:
                output, metrics = complete(
                    state["brief"]["mode"],
                    instruction,
                    inputs,
                    on_retry=lambda attempt, reason: emit(run_id, "agent.retry", agent, attempt=attempt, reason=reason),
                )
            if state["brief"]["mode"] != "demo" and agent in AGENT_DATA_SCHEMAS:
                try:
                    output.data = AGENT_DATA_SCHEMAS[agent].model_validate(output.data).model_dump()
                except ValidationError:
                    raise ProviderError(f"{AGENTS[agent][0]} returned data outside its output schema.") from None
            check_cancel(run_id)
            if agent == "writer":
                persist_artifacts(
                    run_id,
                    output.data.get("artifacts"),
                    execution_id,
                    "Writer revision" if state["revision"] else "Initial draft",
                    state["brief"]["platforms"],
                )
            if agent in ("editor", "brand", "seo"):
                persist_artifacts(
                    run_id,
                    output.data.get("revised_artifacts"),
                    execution_id,
                    AGENTS[agent][0] + " revision",
                    state["brief"]["platforms"],
                )
            if agent == "fact_checker":
                output.data["claims"] = evaluate_claims(state, execution_id)
            if agent == "quality":
                # Recheck after every agent allowed to change text; no inherited verification.
                evaluate_claims(state, execution_id)
                output.data.update(quality_score(state, execution_id))
            if agent == "export":
                with Session() as db:
                    approval = db.scalar(
                        select(ReviewDecision)
                        .where(ReviewDecision.run_id == run_id, ReviewDecision.decision == "approve")
                        .order_by(ReviewDecision.created_at.desc())
                    )
                    current_ids = {v.id for _, v in latest_versions(db, run_id)}
                    if not approval or set(approval.version_ids) != current_ids:
                        raise ProviderError("Export requires approval of the current versions.")
                output.data = {
                    "artifact_count": len(current_ids),
                    "download_ready": True,
                    "publication": "No external publication performed.",
                }
            if agent in ("research", "fact_checker", "export"):
                emit(run_id, "agent.tool_completed", agent, result_summary=output.summary)
            with Session.begin() as db:
                record = db.get(AgentExecution, execution_id)
                record.status = "completed"
                record.outputs = output.model_dump()
                record.decision = output.summary
                record.duration_ms = round((time.monotonic() - start) * 1000, 2)
                for key, value in metrics.items():
                    setattr(record, key, value)
                db.add(UsageAnalytics(execution_id=execution_id, provider=state["brief"]["mode"], metrics=metrics))
            emit(run_id, "agent.output_created", agent, execution_id=execution_id, summary=output.summary)
            emit(
                run_id,
                "agent.completed",
                agent,
                execution_id=execution_id,
                duration_ms=round((time.monotonic() - start) * 1000, 2),
            )
            update_state = {"results": {agent: output.model_dump()}}
            if agent == "quality":
                update_state["needs_revision"] = output.data["needs_revision"]
            return update_state
        except Exception as error:
            safe_error = (
                str(error)
                if isinstance(error, ProviderError)
                else "Stage cancelled."
                if isinstance(error, Cancelled)
                else f"{type(error).__name__}: stage failed; inspect server diagnostics."
            )
            with Session.begin() as db:
                record = db.get(AgentExecution, execution_id)
                record.status = "cancelled" if isinstance(error, Cancelled) else "failed"
                record.error = safe_error
                record.duration_ms = round((time.monotonic() - start) * 1000, 2)
            emit(run_id, "agent.failed", agent, execution_id=execution_id, error=safe_error)
            raise

    return node


def revision_node(state):
    revision = state["revision"] + 1
    with Session.begin() as db:
        db.get(WorkflowRun, state["run_id"]).revision = revision
    emit(
        state["run_id"],
        "revision.requested",
        "quality",
        target="writer",
        revision=revision,
        summary="Revise unsupported claims and address the quality rubric.",
    )
    return {"revision": revision}


def human_node(state):
    answer = interrupt(
        {"reason": "Review the current content, source evidence, and warnings.", "action": "human_approval"}
    )
    if answer != "approve":
        raise ProviderError("A human approval is required to continue.")
    return {}


def build_graph(checkpointer):
    graph = StateGraph(State)
    for name in AGENTS:
        graph.add_node(name, agent_node(name))
    graph.add_node("revision", revision_node)
    graph.add_node("human", human_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "research")
    graph.add_edge("supervisor", "strategy")
    graph.add_edge(["research", "strategy"], "writer")
    for a, b in [
        ("writer", "fact_checker"),
        ("fact_checker", "editor"),
        ("editor", "brand"),
        ("brand", "seo"),
        ("seo", "quality"),
    ]:
        graph.add_edge(a, b)
    graph.add_conditional_edges(
        "quality",
        lambda s: "revision" if s["needs_revision"] and s["revision"] < s["brief"]["max_revisions"] else "human",
        {"revision": "revision", "human": "human"},
    )
    graph.add_edge("revision", "writer")
    graph.add_edge("human", "export")
    graph.add_edge("export", END)
    return graph.compile(checkpointer=checkpointer)


@contextmanager
def checkpoint_store():
    if settings.checkpoint_url:
        from langgraph.checkpoint.postgres import PostgresSaver

        with PostgresSaver.from_conn_string(settings.checkpoint_url) as saver:
            yield saver
    else:
        connection = sqlite3.connect(
            str(Path(settings.data_dir) / "checkpoints.sqlite3"), check_same_thread=False, timeout=30
        )
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield SqliteSaver(connection)
        finally:
            connection.close()


def execute(run_id, action="start"):
    with Session.begin() as db:
        run = db.get(WorkflowRun, run_id)
        if not run or run.cancel_requested:
            return
        brief = db.get(ContentRequest, run.request_id).brief
        run.status = "running"
        run.error = ""
        cycle = run.cycle
    emit(run_id, "workflow.started", action=action, mode=brief["mode"])
    config = {"configurable": {"thread_id": f"{run_id}:{cycle}"}, "recursion_limit": 50}
    try:
        with checkpoint_store() as saver:
            graph = build_graph(saver)
            value = (
                Command(resume="approve")
                if action == "approve"
                else None
                if action == "retry"
                else {"run_id": run_id, "brief": brief, "revision": 0, "results": {}, "needs_revision": False}
            )
            result = graph.invoke(value, config)
            snapshot = graph.get_state(config)
        check_cancel(run_id)
        status = "awaiting_approval" if snapshot.next else "completed"
        with Session.begin() as db:
            run = db.get(WorkflowRun, run_id)
            run.status = status
            if status == "completed":
                run.finished_at = now()
        emit(
            run_id,
            "approval.required" if status == "awaiting_approval" else "workflow.completed",
            summary="Current versions need human approval."
            if snapshot.next
            else "Approved content is ready to export.",
        )
        if result.get("revision", 0):
            emit(run_id, "revision.completed", revision=result["revision"])
    except Exception as error:
        status = "cancelled" if isinstance(error, Cancelled) else "failed"
        safe = (
            str(error)
            if isinstance(error, ProviderError)
            else "Cancelled by user."
            if status == "cancelled"
            else f"{type(error).__name__}: workflow interrupted. Retry from the saved checkpoint."
        )
        with Session.begin() as db:
            run = db.get(WorkflowRun, run_id)
            run.status, run.error = status, safe
        emit(run_id, "workflow.cancelled" if status == "cancelled" else "workflow.failed", error=safe)


pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="contentforge")


def enqueue(run_id, action="start"):
    if settings.redis_url:
        from redis import Redis
        from rq import Queue

        Queue("contentforge", connection=Redis.from_url(settings.redis_url)).enqueue(
            execute, run_id, action, job_timeout=1800, result_ttl=3600, on_failure=queue_failure
        )
    else:
        pool.submit(execute, run_id, action)


def queue_failure(job, connection, error_type, error_value, traceback):
    run_id = job.args[0]
    with Session.begin() as db:
        run = db.get(WorkflowRun, run_id)
        if run and run.status in ("running", "queued"):
            run.status = "interrupted"
            run.error = "Worker interrupted or exceeded its time limit. Resume from the saved checkpoint."
    emit(run_id, "workflow.failed", error="Worker interrupted; checkpoint retained.")
