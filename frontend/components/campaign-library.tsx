"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Layers,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { api, type CampaignPage } from "@/lib/api";
import { Button } from "./ui/button";
import { Empty, ErrorState, Loading, StatusBadge } from "./shared";

const statuses = [
  ["all", "All statuses"],
  ["active", "Active"],
  ["awaiting_approval", "Awaiting approval"],
  ["completed", "Completed"],
  ["attention", "Needs attention"],
  ["cancelled", "Cancelled"],
  ["rejected", "Rejected"],
];

export default function CampaignLibrary({
  onDemo,
  busy,
}: {
  onDemo: () => void;
  busy: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const q = (params.get("q") || "").trim().slice(0, 180);
  const status = statuses.some(([key]) => key === params.get("status"))
    ? params.get("status")!
    : "all";
  const sort = params.get("sort") === "oldest" ? "oldest" : "newest";
  const pageParam = Number(params.get("page") || 1);
  const page =
    Number.isInteger(pageParam) && pageParam >= 1 && pageParam <= 1_000_000
      ? pageParam
      : 1;
  const [search, setSearch] = useState(q);
  useEffect(() => setSearch(q), [q]);

  const query = useQuery({
    queryKey: ["runs", "library", { q, status, sort, page }],
    queryFn: ({ signal }) =>
      api<CampaignPage>(
        `/campaigns?${new URLSearchParams({ q, status, sort, page: String(page), page_size: "6" })}`,
        { signal },
      ),
    refetchInterval: 15000,
  });
  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    router.push(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  };
  const clear = () => {
    setSearch("");
    update({ q: null, status: null, sort: null, page: null });
  };
  const data = query.data;
  const filtered = !!q || status !== "all";

  return (
    <section
      className="panel recent-runs campaign-library"
      aria-label="Campaign library"
    >
      <div className="section-title">
        <h2>Campaign library</h2>
        {data && <span className="count">{data.total}</span>}
        <button onClick={() => router.push("/workflows/new")}>
          New campaign <Plus size={13} />
        </button>
      </div>
      <form
        className="campaign-filters"
        role="search"
        aria-label="Find campaigns"
        onSubmit={(event) => {
          event.preventDefault();
          update({ q: search.trim() || null, page: null });
        }}
      >
        <div className="campaign-search-row">
          <label>
            Search campaigns
            <input
              type="search"
              maxLength={180}
              placeholder="Search campaign titles…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <Button type="submit" variant="secondary" size="sm">
            <Search size={14} />
            Search
          </Button>
        </div>
        <div className="campaign-filter-row">
          <label>
            Campaign status
            <select
              value={status}
              onChange={(event) =>
                update({
                  status:
                    event.target.value === "all" ? null : event.target.value,
                  q: search.trim() || null,
                  page: null,
                })
              }
            >
              {statuses.map(([key, title]) => (
                <option key={key} value={key}>
                  {title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Campaign order
            <select
              value={sort}
              onChange={(event) =>
                update({
                  sort:
                    event.target.value === "newest" ? null : event.target.value,
                  q: search.trim() || null,
                  page: null,
                })
              }
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
            </select>
          </label>
          <Button type="button" variant="ghost" size="sm" onClick={clear}>
            Clear filters
          </Button>
        </div>
      </form>
      <div className="campaign-results-summary">
        <span role="status" aria-live="polite">
          {query.isPending
            ? "Loading campaigns…"
            : query.isError
              ? "Campaigns unavailable"
              : data?.items.length
                ? `${(page - 1) * 6 + 1}–${(page - 1) * 6 + data.items.length} of ${data.total} campaigns`
                : "No campaigns on this page"}
        </span>
        <button
          className="icon-button"
          aria-label="Refresh campaigns"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          <RefreshCw size={14} className={query.isFetching ? "spin" : ""} />
        </button>
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : data?.items.length ? (
        <>
          <div className="run-table">
            <div className="table-heading">
              <span>CAMPAIGN</span>
              <span>STATUS</span>
              <span>CREATED</span>
              <span />
            </div>
            {data.items.map((run) => (
              <button
                className="run-row"
                key={run.id}
                onClick={() => router.push(`/control/${run.id}`)}
              >
                <span>
                  <span className="run-icon">
                    <Layers size={17} />
                  </span>
                  <span>
                    <strong>{run.title}</strong>
                    <small>
                      {run.mode === "demo"
                        ? "Demo campaign"
                        : `${run.mode} · live model`}
                    </small>
                  </span>
                </span>
                <StatusBadge status={run.status} />
                <time dateTime={run.created_at}>
                  {new Date(run.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                  })}
                </time>
                <ArrowUpRight size={15} />
              </button>
            ))}
          </div>
          <nav className="campaign-pagination" aria-label="Campaign pages">
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1}
              onClick={() =>
                update({ page: page === 2 ? null : String(page - 1) })
              }
            >
              <ChevronLeft size={14} />
              Previous
            </Button>
            <span>
              Page {page} of {data.pages}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= data.pages}
              onClick={() => update({ page: String(page + 1) })}
            >
              Next
              <ChevronRight size={14} />
            </Button>
          </nav>
        </>
      ) : page > 1 ? (
        <Empty
          title="This page has no campaigns"
          description="Return to the first page to see the current results."
          action={
            <Button variant="secondary" onClick={() => update({ page: null })}>
              Go to first page
            </Button>
          }
        />
      ) : filtered ? (
        <Empty
          title="No campaigns match your filters"
          description="Try a different title or status, or clear the filters to see all your campaigns."
          action={
            <Button variant="secondary" onClick={clear}>
              Show all campaigns
            </Button>
          }
        />
      ) : (
        <Empty
          title="Start something worth sharing"
          description="Create your first campaign or run the demonstration to see the full journey."
          action={
            <Button onClick={onDemo} disabled={busy}>
              Explore the demo
            </Button>
          }
        />
      )}
    </section>
  );
}
