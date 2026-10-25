"use client";
import { EmailVerificationPanel } from "./email-verification";
import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FileText,
  FolderOpen,
  GitBranch,
  Globe,
  Layers,
  Loader2,
  Network,
  Plus,
  Save,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import {
  api,
  post,
  currentClaims,
  label,
  duration,
  type Analytics as AnalyticsData,
  type Run,
  type Detail,
  type Settings,
  type Preferences,
  type Schedule,
} from "@/lib/api";
import { Button } from "./ui/button";
import {
  PageHeading,
  Loading,
  ErrorState,
  Empty,
  StatusBadge,
  startDemo,
  useRun,
} from "./shared";
import { ReviewPanel } from "./content-studio";
import CampaignLibrary from "./campaign-library";
import ReminderCard from "./reminder-card";
const chartTheme = {
  background: "#192235",
  border: "1px solid #2b3850",
  borderRadius: 10,
  color: "#f5f7ff",
};
function useAnalytics() {
  return useQuery({
    queryKey: ["analytics"],
    queryFn: () => api<AnalyticsData>("/analytics"),
  });
}
function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => api<Run[]>("/workflows"),
  });
}
export function Dashboard() {
  const router = useRouter();
  const query = useAnalytics();
  const [busy, setBusy] = useState(false);
  if (query.isLoading) return <Loading />;
  if (query.error)
    return <ErrorState error={query.error} retry={() => query.refetch()} />;
  const a = query.data!;
  async function demo() {
    setBusy(true);
    try {
      const r = await startDemo();
      router.push(`/control/${r.id}`);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="YOUR CONTENT, CONNECTED"
        title="A little inspiration. A lot of possibility."
        description="Your campaigns, collaborating agents, and evidence — all in one place."
        actions={
          <Button onClick={() => router.push("/workflows/new")}>
            <Plus size={16} />
            New workflow
          </Button>
        }
      />
      <div className="dashboard-banner">
        <div>
          <span className="eyebrow">MEET YOUR NEW CREATIVE TEAM</span>
          <h2>One brief. A whole new perspective.</h2>
          <p>
            Give ten specialized agents an idea. Follow it from research to a
            reviewed, multi-format campaign.
          </p>
          <Button variant="secondary" onClick={demo} disabled={busy}>
            {busy ? (
              <Loader2 size={14} className="spin" />
            ) : (
              <Sparkles size={15} />
            )}
            Run the EV demo
            <ArrowUpRight size={14} />
          </Button>
        </div>
        <div className="banner-art">
          <div className="banner-core">
            <Network size={40} />
          </div>
          <span className="art-dot one">
            <ShieldCheck size={20} />
          </span>
          <span className="art-dot two">
            <FileText size={20} />
          </span>
          <span className="art-dot three">
            <Sparkles size={20} />
          </span>
        </div>
      </div>
      <div className="stats-grid">
        {[
          {
            title: "Total projects",
            value: a.projects,
            icon: FolderOpen,
            hint: "Campaigns in your workspace",
            color: "blue",
          },
          {
            title: "Active workflows",
            value: a.active,
            icon: Network,
            hint: "Your agents at work",
            color: "violet",
          },
          {
            title: "Content created",
            value: a.artifacts,
            icon: FileText,
            hint: "Across every channel",
            color: "teal",
          },
          {
            title: "Evidence coverage",
            value: a.coverage == null ? "—" : a.coverage + "%",
            icon: ShieldCheck,
            hint: `${a.supported_claims} of ${a.claim_count} current claims supported`,
            color: "amber",
          },
        ].map((m) => (
          <section className="stat-card" key={m.title}>
            <div>
              <span>{m.title}</span>
              <span className={`metric-icon ${m.color}`}>
                <m.icon size={17} />
              </span>
            </div>
            <strong>{m.value}</strong>
            <small>{m.hint}</small>
          </section>
        ))}
      </div>
      <div className="dashboard-columns">
        <Suspense fallback={<Loading />}>
          <CampaignLibrary onDemo={demo} busy={busy} />
        </Suspense>
        <section className="panel approval-summary">
          <span className="metric-icon amber">
            <ShieldCheck size={22} />
          </span>
          <h2>The final say is yours.</h2>
          <strong>{a.pending}</strong>
          <p>
            {a.pending === 1 ? "campaign is" : "campaigns are"} waiting for your
            review.
          </p>
          <Button variant="secondary" onClick={() => router.push("/approvals")}>
            Open approval center
            <ArrowRight size={14} />
          </Button>
          <div className="approval-note">
            <ShieldCheck size={14} />
            Nothing is published automatically.
          </div>
        </section>
      </div>
      <section className="panel">
        <div className="section-title">
          <h2>Your agent team</h2>
          <span className="subtle-pill">10 SPECIALISTS</span>
          <button onClick={() => router.push("/analytics")}>
            View analytics
            <ArrowUpRight size={13} />
          </button>
        </div>
        <div className="agent-overview">
          {a.agents.map((agent, i) => (
            <div key={agent.agent}>
              <span className={`agent-avatar color-${i % 4}`}>
                {agent.name.slice(0, 1)}
              </span>
              <strong>{agent.name}</strong>
              <span>{agent.executions} executions</span>
              <small>
                {agent.success_rate == null
                  ? "Ready to collaborate"
                  : `${agent.success_rate}% completion`}
              </small>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
export function Analytics() {
  const query = useAnalytics();
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const a = query.data!;
  const chart = a.quality.map((q, i) => ({
    name: `Eval ${i + 1}`,
    score: q.score,
    revision: q.revision,
  }));
  return (
    <>
      <PageHeading
        eyebrow="AGENT ANALYTICS"
        title="Understand how your team performs."
        description="Measured execution, transparent usage, and explainable quality — from your stored runs."
      />
      <div className="stats-grid">
        <div className="stat-card">
          <span>Agent executions</span>
          <strong>{a.agents.reduce((n, x) => n + x.executions, 0)}</strong>
          <small>Recorded stage attempts</small>
        </div>
        <div className="stat-card">
          <span>Provider retries</span>
          <strong>{a.agents.reduce((n, x) => n + x.retries, 0)}</strong>
          <small>Transport and rate-limit retries</small>
        </div>
        <div className="stat-card">
          <span>Models used</span>
          <strong>{a.models.length}</strong>
          <small>{a.models.join(", ") || "No executions yet"}</small>
        </div>
        <div className="stat-card">
          <span>Estimated model cost</span>
          <strong>
            {a.agents.some((x) => x.estimated_cost != null)
              ? "$" +
                a.agents
                  .reduce((n, x) => n + (x.estimated_cost || 0), 0)
                  .toFixed(4)
              : "Unavailable"}
          </strong>
          <small>Requires reported tokens and configured rates</small>
        </div>
      </div>
      <div className="analytics-charts">
        <section className="panel">
          <div className="section-title">
            <h2>Quality over time</h2>
            <span className="subtle-pill">HEURISTIC / 100</span>
          </div>
          {chart.length ? (
            <div className="chart">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chart}>
                  <defs>
                    <linearGradient
                      id="qualityFill"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="0%"
                        stopColor="#a78bfa"
                        stopOpacity={0.25}
                      />
                      <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    stroke="#253047"
                    strokeDasharray="3 5"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="name"
                    stroke="#73829e"
                    tickLine={false}
                    axisLine={false}
                    fontSize={10}
                  />
                  <YAxis
                    domain={[0, 100]}
                    stroke="#73829e"
                    tickLine={false}
                    axisLine={false}
                    fontSize={10}
                  />
                  <Tooltip contentStyle={chartTheme} />
                  <Area
                    type="monotone"
                    dataKey="score"
                    stroke="#a78bfa"
                    fill="url(#qualityFill)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <Empty
              title="Quality has a story to tell"
              description="Run a campaign to see its evaluations here."
            />
          )}
        </section>
        <section className="panel">
          <div className="section-title">
            <h2>Average agent duration</h2>
            <span className="subtle-pill">MILLISECONDS</span>
          </div>
          {a.agents.some((x) => x.executions) ? (
            <div className="chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={a.agents}>
                  <CartesianGrid
                    stroke="#253047"
                    strokeDasharray="3 5"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="name"
                    stroke="#73829e"
                    tickLine={false}
                    axisLine={false}
                    fontSize={9}
                    interval={0}
                    angle={-30}
                    height={55}
                    textAnchor="end"
                  />
                  <YAxis stroke="#73829e" fontSize={10} />
                  <Tooltip contentStyle={chartTheme} />
                  <Bar
                    dataKey="average_ms"
                    fill="#68b7ff"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <Empty
              title="Actual timings, when available"
              description="Each completed agent records its measured duration."
            />
          )}
        </section>
      </div>
      <section className="panel">
        <div className="section-title">
          <h2>Execution performance</h2>
        </div>
        <div className="data-table">
          <table>
            <thead>
              <tr>
                <th>Agent</th>
                <th>Executions</th>
                <th>Completion rate</th>
                <th>Average duration</th>
                <th>Provider retries</th>
                <th>Estimated cost</th>
              </tr>
            </thead>
            <tbody>
              {a.agents.map((x) => (
                <tr key={x.agent}>
                  <td>{x.name}</td>
                  <td>{x.executions}</td>
                  <td>{x.success_rate == null ? "—" : x.success_rate + "%"}</td>
                  <td>{duration(x.average_ms)}</td>
                  <td>{x.retries}</td>
                  <td>
                    {x.estimated_cost == null
                      ? "Unavailable"
                      : "$" + x.estimated_cost.toFixed(5)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {a.quality.at(-1) && (
        <section className="panel quality-rubric">
          <div className="section-title">
            <h2>Latest quality rubric</h2>
            <span className="subtle-pill">EXPLAINABLE HEURISTICS</span>
          </div>
          <div className="rubric-grid">
            {Object.entries(a.quality.at(-1)!.dimensions).map(([name, d]) => (
              <div key={name}>
                <div>
                  <strong>{label(name)}</strong>
                  <span>
                    {d.score}/100 · {d.weight}% weight
                  </span>
                </div>
                <div className="progress-track">
                  <span style={{ width: `${d.score}%` }} />
                </div>
                <p>{d.basis}</p>
              </div>
            ))}
          </div>
          <p className="help-text">
            This score is a configurable heuristic, not a guarantee. Evidence
            warnings remain regardless of the total score.
          </p>
        </section>
      )}
    </>
  );
}
export function Approvals() {
  const router = useRouter();
  const client = useQueryClient();
  const runs = useRuns();
  const [selected, setSelected] = useState<string | null>(null);
  const pending =
    runs.data?.filter((r) => r.status === "awaiting_approval") || [];
  const active =
    selected && pending.some((r) => r.id === selected)
      ? selected
      : pending[0]?.id || null;
  const detail = useRun(active);
  return (
    <>
      <PageHeading
        eyebrow="HUMAN APPROVAL CENTER"
        title="Good judgment is the final step."
        description="Inspect the drafts, question the evidence, and decide what’s ready to leave the workspace."
      />
      {runs.isLoading ? (
        <Loading />
      ) : runs.error ? (
        <ErrorState error={runs.error} />
      ) : pending.length ? (
        <div className="approval-layout">
          <aside className="panel">
            <div className="section-title">
              <h2>Awaiting your review</h2>
              <span className="count">{pending.length}</span>
            </div>
            {pending.map((r) => (
              <button
                className={`approval-run ${active === r.id ? "selected" : ""}`}
                key={r.id}
                onClick={() => setSelected(r.id)}
              >
                <span className="metric-icon amber">
                  <ShieldCheck size={18} />
                </span>
                <strong>{r.title}</strong>
                <small>{new Date(r.created_at).toLocaleString()}</small>
                <StatusBadge status={r.status} />
              </button>
            ))}
          </aside>
          <div>
            {detail.data ? (
              <>
                <section className="panel">
                  <div className="section-title">
                    <h2>{detail.data.title}</h2>
                  </div>
                  <p>
                    {detail.data.artifacts.length} formats ·{" "}
                    {currentClaims(detail.data).length} current claims ·{" "}
                    {detail.data.revision} automatic revisions
                  </p>
                  <div className="review-links">
                    <Button
                      variant="secondary"
                      onClick={() => router.push(`/content/${active}`)}
                    >
                      Read all content
                      <ArrowUpRight size={14} />
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => router.push(`/evidence/${active}`)}
                    >
                      Inspect evidence
                      <ShieldCheck size={14} />
                    </Button>
                  </div>
                  <div className="approval-preview">
                    {
                      detail.data.versions
                        .filter(
                          (v) =>
                            v.artifact_id === detail.data?.artifacts[0]?.id,
                        )
                        .sort((a, b) => b.number - a.number)[0]?.body
                    }
                  </div>
                </section>
                <ReviewPanel
                  run={detail.data}
                  onDone={() => {
                    client.invalidateQueries({ queryKey: ["runs"] });
                    client.invalidateQueries({ queryKey: ["run", active] });
                  }}
                />
              </>
            ) : (
              <Loading />
            )}
          </div>
        </div>
      ) : (
        <Empty
          title="You’re all caught up."
          description="Campaigns will appear here once your agent team finishes its work."
          action={
            <Button onClick={() => router.push("/workflows/new")}>
              Create a campaign
              <Plus size={14} />
            </Button>
          }
        />
      )}
    </>
  );
}
export function Calendar() {
  const client = useQueryClient();
  const [month, setMonth] = useState(() => new Date());
  const [mode, setMode] = useState("month");
  const [runId, setRunId] = useState("");
  const [artifact, setArtifact] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const runs = useRuns();
  const detail = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api<Detail>(`/workflows/${runId}`),
    enabled: !!runId,
  });
  const schedule = useQuery({
    queryKey: ["calendar"],
    queryFn: () => api<Schedule[]>("/calendar"),
  });
  const jobs = schedule.data || [];
  const start = new Date(month.getFullYear(), month.getMonth(), 1);
  const offset = (start.getDay() + 6) % 7;
  const dates = Array.from({ length: mode === "week" ? 7 : 42 }, (_, i) =>
    mode === "week"
      ? new Date(
          month.getFullYear(),
          month.getMonth(),
          month.getDate() - ((month.getDay() + 6) % 7) + i,
        )
      : new Date(month.getFullYear(), month.getMonth(), i - offset + 1),
  );
  async function add() {
    setBusy(true);
    try {
      await post("/calendar", {
        artifact_id: artifact,
        scheduled_at: new Date(date).toISOString(),
      });
      await client.invalidateQueries({ queryKey: ["calendar"] });
      toast.success(
        "Editorial reminder scheduled. No external publication will occur.",
      );
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="PUBLISHING CALENDAR"
        title="Give your content a place in the week."
        description="Plan approved content with an editorial schedule. External publishing is not connected."
      />
      <div className="calendar-layout">
        <section className="panel calendar-panel">
          <div className="calendar-header">
            <h2>
              {month.toLocaleDateString(undefined, {
                month: "long",
                year: "numeric",
              })}
            </h2>
            <div>
              <div className="segmented">
                {["month", "week"].map((m) => (
                  <button
                    key={m}
                    className={mode === m ? "active" : ""}
                    onClick={() => setMode(m)}
                  >
                    {label(m)}
                  </button>
                ))}
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Previous period"
                onClick={() =>
                  setMonth(
                    mode === "month"
                      ? new Date(month.getFullYear(), month.getMonth() - 1, 1)
                      : new Date(
                          month.getFullYear(),
                          month.getMonth(),
                          month.getDate() - 7,
                        ),
                  )
                }
              >
                <ChevronLeft size={16} />
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setMonth(new Date())}
              >
                Today
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Next period"
                onClick={() =>
                  setMonth(
                    mode === "month"
                      ? new Date(month.getFullYear(), month.getMonth() + 1, 1)
                      : new Date(
                          month.getFullYear(),
                          month.getMonth(),
                          month.getDate() + 7,
                        ),
                  )
                }
              >
                <ChevronRight size={16} />
              </Button>
            </div>
          </div>
          <div className="calendar-grid">
            {["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"].map((d) => (
              <div className="calendar-day-label" key={d}>
                {d}
              </div>
            ))}
            {dates.map((day) => (
              <div
                className={`calendar-cell ${day.getMonth() !== month.getMonth() ? "outside" : ""} ${day.toDateString() === new Date().toDateString() ? "today" : ""}`}
                key={day.toISOString()}
              >
                <span>{day.getDate()}</span>
                {jobs
                  .filter(
                    (j) =>
                      j.status !== "cancelled" &&
                      new Date(j.scheduled_at).toDateString() ===
                        day.toDateString(),
                  )
                  .map((j) => (
                    <button
                      key={j.id}
                      className="calendar-event"
                      title={`${j.title} · ${label(j.status)}`}
                      onClick={() =>
                        toast.info(
                          `${j.title} — ${new Date(j.scheduled_at).toLocaleString()} (${label(j.status)}; not published)`,
                        )
                      }
                    >
                      <span>{label(j.platform)}</span>
                      {j.title}
                    </button>
                  ))}
              </div>
            ))}
          </div>
        </section>
        <aside>
          <section className="panel">
            <div className="section-title">
              <CalendarDays size={17} />
              <h2>Schedule a draft</h2>
            </div>
            <label>
              Approved campaign
              <select
                value={runId}
                onChange={(e) => {
                  setRunId(e.target.value);
                  setArtifact("");
                }}
              >
                <option value="">Choose a campaign</option>
                {runs.data
                  ?.filter((r) => r.status === "completed")
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.title}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Content format
              <select
                value={artifact}
                onChange={(e) => setArtifact(e.target.value)}
              >
                <option value="">Choose a format</option>
                {detail.data?.artifacts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {label(a.platform)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Date and time
              <input
                aria-label="Schedule date"
                type="datetime-local"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </label>
            <Button
              className="full-button"
              onClick={add}
              disabled={busy || !artifact || !date}
            >
              <Plus size={15} />
              Add to calendar
            </Button>
            <p className="help-text">
              Uses your browser’s timezone. Scheduling stores an editorial
              reminder; it does not post to social platforms.
            </p>
          </section>
          <section className="panel schedule-list">
            <h2>Upcoming drafts</h2>
            {schedule.isLoading && (
              <p className="help-text">Loading reminders…</p>
            )}
            {schedule.error && (
              <ErrorState
                error={schedule.error}
                retry={() => schedule.refetch()}
              />
            )}
            {jobs
              .filter((j) => j.status !== "cancelled")
              .map((j) => (
                <ReminderCard key={j.id} job={j} onMoved={setMonth} />
              ))}
            {schedule.isSuccess &&
              !jobs.some((j) => j.status !== "cancelled") && (
                <p className="help-text">
                  Approved content can be scheduled here.
                </p>
              )}
          </section>
        </aside>
      </div>
    </>
  );
}
export function SettingsPage() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Settings>("/settings"),
  });
  const [busy, setBusy] = useState(false);
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const settings = query.data!;
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api("/settings", {
        method: "PUT",
        body: JSON.stringify({
          ...data,
          quality_threshold: Number(data.quality_threshold),
          max_revisions: Number(data.max_revisions),
        }),
      });
      await client.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Workspace preferences saved.");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE SETTINGS"
        title="A workspace that sounds like you."
        description="Shape your brand, configure workflow defaults, and understand your connected models."
      />
      <EmailVerificationPanel />
      <form onSubmit={save} className="settings-layout">
        <div>
          <section className="panel">
            <div className="section-title">
              <Globe size={18} />
              <h2>Model providers</h2>
              <span className="subtle-pill">SERVER CONFIGURATION</span>
            </div>
            <p className="panel-description">
              API credentials stay on the server. No secret values are sent to
              or stored by this browser.
            </p>
            <div className="provider-list">
              {[
                ["demo", "Demo engine", "Built-in fixture runner"],
                ["openai", "OpenAI-compatible", settings.models.openai],
                ["gemini", "Google Gemini", settings.models.gemini],
                ["ollama", "Ollama", settings.models.ollama],
              ].map(([id, name, model]) => (
                <div className="provider-card" key={id}>
                  <span className={`provider-logo ${id}`}>
                    {name.slice(0, 1)}
                  </span>
                  <div>
                    <strong>{name}</strong>
                    <small>{model}</small>
                  </div>
                  <span
                    className={`badge ${settings.providers[id] ? "supported" : "waiting"}`}
                  >
                    {id === "ollama"
                      ? "Server URL configured"
                      : settings.providers[id]
                        ? "Configured"
                        : "Not configured"}
                  </span>
                </div>
              ))}
            </div>
            <details className="configuration-help">
              <summary>How to connect a model</summary>
              <p>
                Set server environment variables, then restart the backend and
                worker.
              </p>
              <code>
                OPENAI_API_KEY · OPENAI_BASE_URL · OPENAI_MODEL
                <br />
                GEMINI_API_KEY · GEMINI_MODEL
                <br />
                OLLAMA_BASE_URL · OLLAMA_MODEL
              </code>
              <p>
                Ollama needs a running server with the selected model installed.
                “Configured” indicates configuration presence; a workflow tests
                actual connectivity.
              </p>
            </details>
            <label>
              Default provider
              <select
                name="default_provider"
                defaultValue={settings.preferences.default_provider}
              >
                {Object.keys(settings.providers).map((p) => (
                  <option key={p} value={p} disabled={!settings.providers[p]}>
                    {label(p)}
                  </option>
                ))}
              </select>
            </label>
          </section>
          <section className="panel">
            <div className="section-title">
              <FileText size={18} />
              <h2>Brand profile</h2>
            </div>
            <label>
              Brand name
              <input
                name="brand_name"
                defaultValue={settings.preferences.brand_name}
                maxLength={100}
                required
              />
            </label>
            <label>
              Voice and guidelines
              <textarea
                name="brand_voice"
                defaultValue={settings.preferences.brand_voice}
                maxLength={2000}
                rows={5}
              />
            </label>
            <p className="help-text">
              These instructions are passed to the writer and Brand Guardian in
              new campaigns.
            </p>
          </section>
        </div>
        <div>
          <section className="panel">
            <div className="section-title">
              <GitBranch size={18} />
              <h2>Workflow defaults</h2>
            </div>
            <label>
              Quality threshold
              <input
                name="quality_threshold"
                type="number"
                min={50}
                max={100}
                defaultValue={settings.preferences.quality_threshold}
              />
            </label>
            <label>
              Maximum automatic revisions
              <input
                name="max_revisions"
                type="number"
                min={0}
                max={2}
                defaultValue={settings.preferences.max_revisions}
              />
            </label>
            <p className="help-text">
              Quality is an explainable heuristic. Evidence warnings are
              preserved even if a campaign meets the threshold.
            </p>
          </section>
          <section className="panel">
            <div className="section-title">
              <Layers size={18} />
              <h2>Appearance & exports</h2>
            </div>
            <label>
              Theme
              <select name="theme" defaultValue={settings.preferences.theme}>
                <option value="dark">Dark</option>
                <option value="light">Light</option>
                <option value="system">Follow system</option>
              </select>
            </label>
            <label>
              Preferred export format
              <select
                name="export_format"
                defaultValue={settings.preferences.export_format}
              >
                <option value="markdown">Markdown</option>
                <option value="json">JSON with audit metadata</option>
                <option value="zip">ZIP package with evidence</option>
              </select>
            </label>
          </section>
          <Button className="full-button" type="submit" disabled={busy}>
            {busy ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
            Save preferences
          </Button>
        </div>
      </form>
    </>
  );
}
