export type Status =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled"
  | "rejected"
  | "interrupted";
export type Run = {
  id: string;
  title: string;
  project_id: string;
  status: Status;
  mode: string;
  revision: number;
  cycle: number;
  retry_count: number;
  created_at: string;
  error: string;
};
export type Artifact = {
  id: string;
  run_id: string;
  title: string;
  platform: string;
};
export type Version = {
  id: string;
  artifact_id: string;
  number: number;
  body: string;
  reason: string;
  execution_id: string | null;
  created_at: string;
};
export type Claim = {
  id: string;
  version_id: string;
  text: string;
  start: number;
  end: number;
  status: "supported" | "disputed" | "unverified";
  explanation: string;
  execution_id: string | null;
  history: { state: string; at: string; evidence_status?: string }[];
};
export type Source = {
  id: string;
  title: string;
  url: string;
  kind: string;
  status: string;
  credibility: string;
  publication_date: string | null;
  text: string;
  content_hash: string;
};
export type Passage = {
  id: string;
  source_id: string;
  text: string;
  ordinal: number;
};
export type EvidenceLink = {
  id: string;
  claim_id: string;
  passage_id: string;
  relation: string;
  quote: string;
};
export type Execution = {
  id: string;
  agent: string;
  status: string;
  model: string;
  inputs: Record<string, unknown>;
  outputs: {
    summary?: string;
    data?: Record<string, unknown>;
    warnings?: string[];
  };
  decision: string;
  duration_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost: number | null;
  retries: number;
  error: string;
  created_at: string;
};
export type Event = {
  id: string;
  run_id: string;
  sequence: number;
  type: string;
  agent: string | null;
  created_at: string;
  payload: Record<string, unknown>;
};
export type Quality = {
  id: string;
  run_id: string;
  score: number;
  revision: number;
  created_at: string;
  dimensions: Record<string, { weight: number; score: number; basis: string }>;
  warnings: string[];
};
export type Review = {
  id: string;
  decision: string;
  comment: string;
  created_at: string;
  version_ids: string[];
};
export type Comment = {
  id: string;
  version_id: string;
  text: string;
  quote: string;
  created_at: string;
};
export type Detail = Run & {
  brief: {
    prompt: string;
    audience: string;
    tone: string;
    goals: string;
    brand: string;
    platforms: string[];
    source_ids: string[];
    mode: string;
    quality_threshold: number;
    max_revisions: number;
  };
  artifacts: Artifact[];
  versions: Version[];
  claims: Claim[];
  links: EvidenceLink[];
  sources: Source[];
  passages: Passage[];
  executions: Execution[];
  events: Event[];
  quality: Quality[];
  reviews: Review[];
  comments: Comment[];
};
export type AgentMetric = {
  agent: string;
  name: string;
  executions: number;
  success_rate: number | null;
  average_ms: number | null;
  retries: number;
  estimated_cost: number | null;
};
export type Analytics = {
  projects: number;
  runs: number;
  active: number;
  artifacts: number;
  pending: number;
  claim_count: number;
  supported_claims: number;
  coverage: number | null;
  agents: AgentMetric[];
  quality: Quality[];
  models: string[];
};
export type Preferences = {
  brand_name: string;
  brand_voice: string;
  default_provider: string;
  theme: string;
  export_format: string;
  quality_threshold: number;
  max_revisions: number;
};
export type Settings = {
  preferences: Preferences;
  providers: Record<string, boolean>;
  models: Record<string, string>;
  source_hosts: string[];
};
export type Schedule = {
  id: string;
  artifact_id: string;
  version_id: string;
  title: string;
  platform: string;
  scheduled_at: string;
  status: string;
};
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: "include",
    ...options,
    headers:
      options.body instanceof FormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "Request failed." }));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Check the form fields and try again.",
    );
  }
  return response.json();
}
export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export function latest(run: Detail, artifactId?: string) {
  return run.versions
    .filter((v) => !artifactId || v.artifact_id === artifactId)
    .sort((a, b) => b.number - a.number);
}
export function currentClaims(run: Detail) {
  const ids = new Set(run.artifacts.map((a) => latest(run, a.id)[0]?.id));
  return run.claims.filter((c) => ids.has(c.version_id));
}
export const label = (text: string) =>
  text.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
export const duration = (ms: number | null) =>
  ms == null
    ? "Unavailable"
    : ms < 1000
      ? `${Math.round(ms)} ms`
      : `${(ms / 1000).toFixed(1)} s`;
