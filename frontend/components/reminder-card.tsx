"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Clock3, Download, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, label, type Schedule } from "@/lib/api";
import { Button } from "./ui/button";

function localDate(value: string) {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

export default function ReminderCard({
  job,
  onMoved,
}: {
  job: Schedule;
  onMoved: (date: Date) => void;
}) {
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState("");
  const [expected, setExpected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function edit() {
    setDate(localDate(job.scheduled_at));
    setExpected(job.scheduled_at);
    setError("");
    setEditing(true);
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (
      !date ||
      !Number.isFinite(new Date(date).getTime()) ||
      new Date(date).getTime() <= Date.now()
    ) {
      setError("Choose a future date and time.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const updated = await api<Schedule>(`/calendar/${job.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          scheduled_at: new Date(date).toISOString(),
          expected_scheduled_at: expected,
        }),
      });
      await client.invalidateQueries({ queryKey: ["calendar"] });
      setEditing(false);
      onMoved(new Date(updated.scheduled_at));
      toast.success(
        "Reminder rescheduled. The approved content version is unchanged.",
      );
    } catch (error) {
      setError((error as Error).message);
      if (
        error instanceof ApiError &&
        (error.status === 409 || error.status === 404)
      ) {
        await client.invalidateQueries({ queryKey: ["calendar"] });
      }
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setBusy(true);
    setError("");
    try {
      await api(`/calendar/${job.id}`, { method: "DELETE" });
      await client.invalidateQueries({ queryKey: ["calendar"] });
      toast.success("Schedule cancelled.");
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function download() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/calendar/${job.id}/export`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(
          body.detail ||
            "The calendar file could not be downloaded. Try again.",
        );
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `contentforge-reminder-${job.id}.ics`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article
      className="reminder-card"
      aria-label={`${label(job.platform)} reminder: ${job.title}`}
    >
      <div className="reminder-heading">
        <span>
          <strong>{label(job.platform)}</strong>
          <span className="reminder-title">{job.title}</span>
          <small>
            <time dateTime={job.scheduled_at}>
              {new Date(job.scheduled_at).toLocaleString()}
            </time>
          </small>
        </span>
        <Button
          variant="ghost"
          size="icon"
          disabled={busy}
          aria-label={`Cancel ${job.platform} schedule`}
          onClick={remove}
        >
          <Trash2 size={14} />
        </Button>
      </div>
      {editing ? (
        <form onSubmit={save}>
          <label>
            New date and time
            <input
              autoFocus
              aria-label={`Reschedule ${job.platform} date`}
              type="datetime-local"
              value={date}
              required
              disabled={busy}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <p className="help-text">
            Uses your browser’s timezone. Keeps the same approved content
            version.
          </p>
          <div className="reminder-actions">
            <Button size="sm" disabled={busy} type="submit">
              {busy ? "Saving…" : "Save new time"}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              type="button"
              disabled={busy}
              onClick={() => {
                setEditing(false);
                setError("");
              }}
            >
              Discard changes
            </Button>
          </div>
        </form>
      ) : (
        <>
          <div className="reminder-actions">
            <Button
              size="sm"
              variant="secondary"
              onClick={edit}
              disabled={busy}
            >
              <Clock3 size={13} />
              Reschedule
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={download}
              disabled={busy}
            >
              <Download size={13} />
              Download .ics
            </Button>
          </div>
          <p className="help-text">
            Import this snapshot into your calendar app. Later changes do not
            sync automatically.
          </p>
        </>
      )}
      {error && (
        <p className="help-text" role="alert">
          {error}
        </p>
      )}
    </article>
  );
}
