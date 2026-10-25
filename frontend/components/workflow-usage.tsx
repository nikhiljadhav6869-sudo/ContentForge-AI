"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "./ui/button";

type Usage = {
  day: string;
  resets_at: string;
  generation_attempts: number;
  daily_limit: number;
  remaining: number;
  active_workflows: number;
  concurrency_limit: number;
};

export function WorkflowUsagePanel() {
  const query = useQuery({
    queryKey: ["workflow-usage"],
    queryFn: () => api<Usage>("/usage"),
    retry: false,
    refetchInterval: 30000,
  });
  return (
    <section className="panel workflow-usage-panel" aria-label="Workflow usage">
      <h2>Workflow usage</h2>
      {query.isPending ? (
        <p role="status">Loading workflow usage…</p>
      ) : query.isError ? (
        <>
          <p role="alert">
            Could not load workflow usage. Your allowance is unknown.
          </p>
          <Button
            type="button"
            variant="secondary"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            Retry usage
          </Button>
        </>
      ) : (
        <>
          <p>
            <strong>
              {query.data.generation_attempts} / {query.data.daily_limit}
            </strong>{" "}
            generation attempts today
          </p>
          <p>
            <strong>
              {query.data.active_workflows} / {query.data.concurrency_limit}
            </strong>{" "}
            active workflows
          </p>
          <p role="status">
            {query.data.daily_limit === 0
              ? "New generation is paused by the site operator."
              : query.data.remaining === 0
                ? "Daily allowance reached. You can still edit, review, and download existing content."
                : `${query.data.remaining} generation attempts remaining today.`}
          </p>
          {query.data.active_workflows >= query.data.concurrency_limit && (
            <p>
              All active slots are in use. Wait for a workflow to finish or
              reach review before starting or resuming another.
            </p>
          )}
          <p>
            Starts, retries, and requested revisions count in demo and live
            modes, including failed attempts. Approvals and downloads do not use
            the daily allowance.
          </p>
          <p>
            Daily reset:{" "}
            <time dateTime={query.data.resets_at}>
              {new Date(query.data.resets_at).toLocaleString(undefined, {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </time>{" "}
            (your local time). Limits are managed by the site operator.
          </p>
          <Button
            type="button"
            variant="secondary"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "Refreshing usage…" : "Refresh usage"}
          </Button>
        </>
      )}
    </section>
  );
}
