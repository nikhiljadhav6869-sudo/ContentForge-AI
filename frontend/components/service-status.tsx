"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function ServiceStatus() {
  const [offline, setOffline] = useState(false);
  const health = useQuery({
    queryKey: ["service-health"],
    queryFn: ({ signal }) =>
      api<{ status: string }>("/health", {
        signal: AbortSignal.any([signal, AbortSignal.timeout(5000)]),
      }),
    refetchInterval: 30000,
    refetchOnWindowFocus: true,
    retry: false,
  });

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  const state = offline
    ? "offline"
    : health.isFetching || health.isPending
      ? "checking"
      : health.isError || health.data?.status !== "ok"
        ? "unavailable"
        : "available";
  const labels = {
    offline: "You’re offline",
    checking: "Checking connection",
    unavailable: "Connection unavailable",
    available: "API available",
  };
  const description =
    state === "available"
      ? "API, database, and configured queue responded. Worker and AI provider availability are checked when a campaign runs."
      : state === "offline"
        ? "Reconnect to the internet to continue."
        : state === "checking"
          ? "Checking the API connection."
          : "Could not confirm service availability. Click to check again.";

  return (
    <button
      className="system-status"
      data-state={state}
      aria-label="Check service connection"
      title={description}
      disabled={health.isFetching}
      onClick={() => void health.refetch()}
    >
      <i aria-hidden="true" />
      <span role="status" aria-live="polite">
        {labels[state]}
      </span>
    </button>
  );
}
