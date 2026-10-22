"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  Copy,
  FileText,
  Loader2,
  Plus,
  Radio,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { api, post, label, ApiError, type Detail, type Run } from "@/lib/api";
import { useUI } from "@/lib/store";
import { Button } from "./ui/button";
export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${status}`}>
      <span className="status-dot" />
      {label(status)}
    </span>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <Sparkles size={30} />
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading">
      <div className="skeleton wide" />
      <div className="skeleton tall" />
      <div className="skeleton wide" />
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry?: () => void;
}) {
  return (
    <div className="error-state">
      <AlertTriangle size={24} />
      <h3>We couldn’t load this view.</h3>
      <p>{error.message}</p>
      {retry && (
        <Button variant="secondary" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="page-actions">{actions}</div>
    </div>
  );
}
export function useRun(id: string | null) {
  const client = useQueryClient();
  const [connected, setConnected] = useState(false);
  const query = useQuery({
    queryKey: ["run", id],
    queryFn: () => api<Detail>(`/workflows/${id}`),
    enabled: !!id,
  });
  useEffect(() => {
    if (!id) return;
    const stream = new EventSource(`/api/workflows/${id}/events`, {
      withCredentials: true,
    });
    stream.onopen = () => setConnected(true);
    stream.onerror = () => setConnected(false);
    stream.addEventListener("workflow", () => {
      client.invalidateQueries({ queryKey: ["run", id] });
      client.invalidateQueries({ queryKey: ["runs"] });
      client.invalidateQueries({ queryKey: ["analytics"] });
    });
    return () => {
      stream.close();
      setConnected(false);
    };
  }, [id, client]);
  return { ...query, connected };
}
export function RunPicker({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { data = [] } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<Run[]>("/workflows"),
  });
  return (
    <select
      aria-label="Choose campaign"
      className="run-picker"
      value={selected || ""}
      onChange={(e) => onSelect(e.target.value)}
    >
      <option value="" disabled>
        Select a campaign
      </option>
      {data.map((r) => (
        <option key={r.id} value={r.id}>
          {r.title.slice(0, 55)} · {label(r.status)}
        </option>
      ))}
    </select>
  );
}
export function NoRun() {
  const router = useRouter();
  return (
    <Empty
      title="Your next campaign starts here"
      description="Create a workflow to explore its agents, evidence, and content."
      action={
        <Button onClick={() => router.push("/workflows/new")}>
          <Plus size={15} />
          Create workflow
        </Button>
      }
    />
  );
}
export function DemoBanner() {
  return (
    <div className="demo-banner">
      <Sparkles size={14} />
      <span>
        <strong>Demonstration mode</strong> · Real orchestration, curated sample
        outputs. No live AI or web research.
      </span>
    </div>
  );
}
export function Download({
  runId,
  kind = "export",
  format = "markdown",
  children,
}: {
  runId: string;
  kind?: string;
  format?: string;
  children: React.ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  async function download() {
    setBusy(true);
    try {
      const response = await fetch(
        `/api/workflows/${runId}/${kind}?format=${format}`,
      );
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail);
      }
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download =
        kind === "report"
          ? "contentforge-execution.json"
          : format === "json"
            ? "contentforge-campaign.json"
            : format === "zip"
              ? "contentforge-campaign.zip"
              : "contentforge-campaign.md";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Button variant="secondary" size="sm" disabled={busy} onClick={download}>
      {busy ? <Loader2 size={14} className="spin" /> : null}
      {children}
    </Button>
  );
}
export async function startDemo() {
  try {
    await api("/me");
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
    await post("/auth/demo");
    useUI.getState().resetWorkspace();
  }
  return post<{ id: string }>("/workflows", {
    prompt:
      "Create a researched content campaign about electric vehicles in India.",
    mode: "demo",
    platforms: ["blog", "linkedin", "instagram", "youtube"],
  });
}
export function CopyButton({ text }: { text: string }) {
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() =>
        navigator.clipboard
          .writeText(text)
          .then(() => toast.success("Copied to clipboard"))
          .catch(() =>
            toast.error("Clipboard unavailable. Use export instead."),
          )
      }
    >
      <Copy size={13} />
      Copy
    </Button>
  );
}
