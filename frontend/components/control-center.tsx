"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Clock3,
  Download,
  FileText,
  GitBranch,
  Maximize2,
  Network,
  Play,
  Radio,
  RefreshCw,
  ScanEye,
  ShieldCheck,
  Square,
  Terminal,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { post, label, duration, type Execution } from "@/lib/api";
import { Button } from "./ui/button";
import AgentGraph, { agentMeta } from "./agent-graph";
import {
  useRun,
  NoRun,
  Loading,
  ErrorState,
  StatusBadge,
  RunPicker,
  DemoBanner,
  Download as DownloadButton,
} from "./shared";
export default function ControlCenter({ id }: { id: string | null }) {
  const router = useRouter();
  const client = useQueryClient();
  const query = useRun(id);
  const run = query.data;
  const [selected, setSelected] = useState("supervisor");
  const [tab, setTab] = useState("overview");
  const [logs, setLogs] = useState(true);
  const [busy, setBusy] = useState(false);
  const [inspector, setInspector] = useState(false);
  if (!id) return <NoRun />;
  if (query.isLoading) return <Loading />;
  if (query.error)
    return <ErrorState error={query.error} retry={() => query.refetch()} />;
  if (!run) return null;
  const meta = agentMeta.find((a) => a.id === selected)!;
  const execution = [...run.executions]
    .reverse()
    .find((e) => e.agent === selected);
  const agentEvents = run.events.filter((e) => e.agent === selected);
  const done = new Set(
    run.executions.filter((e) => e.status === "completed").map((e) => e.agent),
  ).size;
  const allTokens = run.executions.reduce(
    (n, e) => n + (e.input_tokens || 0) + (e.output_tokens || 0),
    0,
  );
  const quality = run.quality.at(-1);
  const currentEvents = run.events.slice(-70);
  async function action(name: string) {
    setBusy(true);
    try {
      await post(`/workflows/${id}/${name}`);
      await client.invalidateQueries({ queryKey: ["run", id] });
      toast.success(
        name === "cancel"
          ? "Cancellation requested."
          : "Resuming from checkpoint.",
      );
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="control-heading">
        <div className="control-title">
          <div className="eyebrow">YOUR AGENT TEAM, IN MOTION</div>
          <h1>
            Agent control center{" "}
            <span className="live-badge">
              <span />
              {query.connected ? "Connected" : "Reconnecting"}
            </span>
          </h1>
          <p>Every action. Every decision. One shared mission.</p>
        </div>
        <div className="page-actions">
          <RunPicker
            selected={id}
            onSelect={(next) => router.push(`/control/${next}`)}
          />
          <DownloadButton runId={id} kind="report">
            <Download size={14} />
            Report
          </DownloadButton>
        </div>
      </div>
      <div className="control-toolbar">
        <div className="campaign-title">
          <span className="campaign-icon">
            <Network size={18} />
          </span>
          <div>
            <strong>{run.title}</strong>
            <small>
              {run.brief.platforms.length} content formats ·{" "}
              {run.brief.audience}
            </small>
          </div>
        </div>
        <StatusBadge status={run.status} />
        <div className="workflow-actions">
          {["failed", "interrupted"].includes(run.status) && (
            <Button
              size="sm"
              disabled={busy || run.retry_count >= 3}
              onClick={() => action("retry")}
            >
              <RefreshCw size={13} />
              Resume checkpoint
            </Button>
          )}
          {["running", "queued", "awaiting_approval"].includes(run.status) && (
            <Button
              variant="secondary"
              size="sm"
              disabled={busy}
              onClick={() => action("cancel")}
            >
              <Square size={12} />
              Cancel
            </Button>
          )}
          {run.status === "awaiting_approval" && (
            <Button size="sm" onClick={() => router.push(`/content/${id}`)}>
              <ShieldCheck size={14} />
              Review content
            </Button>
          )}
          {run.status === "completed" && (
            <Button size="sm" onClick={() => router.push(`/content/${id}`)}>
              Open content
              <ArrowRight size={14} />
            </Button>
          )}
        </div>
      </div>
      {run.mode === "demo" && <DemoBanner />}
      {run.error && <div className="warning-banner">{run.error}</div>}
      <div className="control-metrics">
        <div>
          <span className="metric-icon blue">
            <Network size={16} />
          </span>
          <div>
            <small>AGENTS COMPLETED</small>
            <strong>
              {done}
              <span>/ 10</span>
            </strong>
          </div>
        </div>
        <div>
          <span className="metric-icon teal">
            <FileText size={16} />
          </span>
          <div>
            <small>CONTENT ARTIFACTS</small>
            <strong>
              {run.artifacts.length}
              <span>formats</span>
            </strong>
          </div>
        </div>
        <div>
          <span className="metric-icon violet">
            <GitBranch size={16} />
          </span>
          <div>
            <small>REVISION ROUNDS</small>
            <strong>
              {run.revision}
              <span>/ {run.brief.max_revisions} automatic</span>
            </strong>
          </div>
        </div>
        <div>
          <span className="metric-icon amber">
            <Activity size={16} />
          </span>
          <div>
            <small>QUALITY HEURISTIC</small>
            <strong>
              {quality?.score ?? "—"}
              <span>{quality ? " / 100" : "awaiting evaluation"}</span>
            </strong>
          </div>
        </div>
      </div>
      <div className="control-workspace">
        <section className="canvas-panel">
          <div className="canvas-header">
            <div>
              <Network size={14} />
              <strong>Orchestration graph</strong>
              <span className="subtle-pill">LangGraph</span>
            </div>
            <div className="graph-legend">
              <span>
                <i className="legend-waiting" />
                Waiting
              </span>
              <span>
                <i className="legend-running" />
                Running
              </span>
              <span>
                <i className="legend-done" />
                Complete
              </span>
            </div>
          </div>
          <div className="graph-canvas">
            <AgentGraph
              run={run}
              selected={selected}
              onSelect={(agent) => {
                setSelected(agent);
                setInspector(true);
              }}
            />
            <div className="canvas-caption">
              Scroll to zoom · Drag to pan · Select an agent to inspect
            </div>
          </div>
          <div className="terminal-panel">
            <button className="terminal-toggle" onClick={() => setLogs(!logs)}>
              <Terminal size={14} />
              <strong>Execution log</strong>
              <span className="subtle-pill">{run.events.length} events</span>
              <span className="terminal-status">
                <span className="status-dot" />
                {query.connected ? "Stream connected" : "Recovering events"}
              </span>
              {logs ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
            </button>
            {logs && (
              <div className="terminal-body" aria-label="Execution log">
                {currentEvents.map((event) => (
                  <div key={event.id}>
                    <time>
                      {new Date(event.created_at).toLocaleTimeString("en-GB", {
                        hour12: false,
                      })}
                    </time>
                    <span
                      className={`event-type ${event.type.includes("failed") ? "error" : ""}`}
                    >
                      {event.type}
                    </span>
                    <span>
                      {String(
                        event.payload.summary ||
                          event.payload.error ||
                          (event.agent && label(event.agent)) ||
                          "Workflow updated",
                      )}
                    </span>
                    <small>#{event.sequence}</small>
                  </div>
                ))}
                {!run.events.length && <p>Waiting for backend events…</p>}
              </div>
            )}
          </div>
        </section>
        <aside className={`agent-inspector ${inspector ? "mobile-open" : ""}`}>
          <div className="inspector-top">
            <span>AGENT INSPECTOR</span>
            <button
              className="mobile-toggle icon-button"
              aria-label="Close inspector"
              onClick={() => setInspector(false)}
            >
              <X size={16} />
            </button>
            <span className="inspector-id">
              {selected === "human"
                ? "HUMAN"
                : `AGENT ${String(agentMeta.indexOf(meta) + 1).padStart(2, "0")}`}
            </span>
          </div>
          <div className="inspector-identity">
            <span
              className="big-agent-icon"
              style={{ color: meta.color, background: `${meta.color}15` }}
            >
              <meta.icon size={25} />
            </span>
            <h2>{meta.name}</h2>
            <p>{meta.role}</p>
            <StatusBadge
              status={
                execution?.status ||
                (selected === "human" && run.status === "awaiting_approval"
                  ? "awaiting_approval"
                  : "waiting")
              }
            />
          </div>
          <div className="inspector-tabs">
            {["overview", "inputs", "outputs", "trace"].map((t) => (
              <button
                key={t}
                className={tab === t ? "active" : ""}
                onClick={() => setTab(t)}
              >
                {label(t)}
              </button>
            ))}
          </div>
          <div className="inspector-content">
            {tab === "overview" && (
              <>
                <div className="detail-label">CURRENT TASK</div>
                <p>
                  {execution?.decision ||
                    "Ready to execute when workflow dependencies are satisfied."}
                </p>
                <div className="inspector-detail">
                  <span>Model</span>
                  <strong>{execution?.model || "Not started"}</strong>
                </div>
                <div className="inspector-detail">
                  <span>Duration</span>
                  <strong>{duration(execution?.duration_ms ?? null)}</strong>
                </div>
                <div className="inspector-detail">
                  <span>Input tokens</span>
                  <strong>{execution?.input_tokens ?? "Unavailable"}</strong>
                </div>
                <div className="inspector-detail">
                  <span>Output tokens</span>
                  <strong>{execution?.output_tokens ?? "Unavailable"}</strong>
                </div>
                <div className="inspector-detail">
                  <span>Estimated cost</span>
                  <strong>
                    {execution?.estimated_cost != null
                      ? `$${execution.estimated_cost.toFixed(5)}`
                      : "Unavailable"}
                  </strong>
                </div>
                <div className="inspector-detail">
                  <span>Provider retries</span>
                  <strong>{execution?.retries ?? 0}</strong>
                </div>
                <div className="detail-label spaced">RECENT ACTIVITY</div>
                <div className="activity-list">
                  {agentEvents.slice(-5).map((event) => (
                    <div key={event.id}>
                      <span className="activity-dot" />
                      <div>
                        <strong>
                          {label(event.type.split(".")[1] || event.type)}
                        </strong>
                        <small>
                          {String(
                            event.payload.summary ||
                              event.payload.tool ||
                              event.payload.error ||
                              event.type,
                          )}
                        </small>
                        <time>
                          {new Date(event.created_at).toLocaleTimeString()}
                        </time>
                      </div>
                    </div>
                  ))}
                </div>
                {execution?.error && (
                  <div className="warning-banner">{execution.error}</div>
                )}
              </>
            )}
            {tab === "inputs" && (
              <>
                <div className="detail-label">STRUCTURED INPUT</div>
                <pre className="json-preview">
                  {execution
                    ? JSON.stringify(execution.inputs, null, 2)
                    : "No input has been received yet."}
                </pre>
              </>
            )}
            {tab === "outputs" && (
              <>
                <div className="detail-label">SAVED RESULT</div>
                <pre className="json-preview">
                  {execution
                    ? JSON.stringify(execution.outputs, null, 2)
                    : "No output has been produced yet."}
                </pre>
              </>
            )}
            {tab === "trace" && (
              <>
                <p className="help-text">
                  Observable actions and structured summaries. Hidden model
                  reasoning is never collected or shown.
                </p>
                {agentEvents.map((event) => (
                  <div className="trace-entry" key={event.id}>
                    <strong>{event.type}</strong>
                    <small>
                      Event #{event.sequence} ·{" "}
                      {new Date(event.created_at).toLocaleTimeString()}
                    </small>
                    <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                  </div>
                ))}
              </>
            )}
          </div>
          <div className="inspector-footer">
            <ShieldCheck size={14} />
            Every output is persisted and traceable.
          </div>
        </aside>
      </div>
      <div className="control-bottom">
        <span>
          <span className="status-dot" />
          {query.connected
            ? "Event stream synchronized"
            : "Reconnecting with event replay"}
        </span>
        <span>
          {run.events.length} recorded events ·{" "}
          {allTokens
            ? `${allTokens.toLocaleString()} reported tokens`
            : "Token usage unavailable in demo"}
          <button onClick={() => router.push(`/evidence/${id}`)}>
            Explore evidence
            <ArrowUpRightSmall />
          </button>
        </span>
      </div>
    </>
  );
}
function ArrowUpRightSmall() {
  return <ArrowRight size={12} />;
}
