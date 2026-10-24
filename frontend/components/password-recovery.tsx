"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api, post } from "@/lib/api";
import { useUI } from "@/lib/store";
import { Logo } from "./studio";
import { Button } from "./ui/button";

export default function PasswordRecovery({ reset }: { reset: boolean }) {
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const client = useQueryClient();
  const options = useQuery({
    queryKey: ["auth-options"],
    queryFn: () => api<{ password_reset: boolean }>("/auth/options"),
    enabled: !reset,
    retry: false,
  });

  useEffect(() => {
    if (!reset) return;
    const readLink = () => {
      const value = new URLSearchParams(window.location.hash.slice(1)).get(
        "token",
      );
      setToken((current) => value ?? current ?? "");
      if (value) {
        setMessage("");
        setError("");
      }
      // Keep the token only in this component's memory, outside history/requests.
      window.history.replaceState(
        window.history.state,
        "",
        window.location.pathname,
      );
    };
    readLink();
    window.addEventListener("hashchange", readLink);
    return () => window.removeEventListener("hashchange", readLink);
  }, [reset]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setError("");
    if (reset && data.get("password") !== data.get("confirmation")) {
      setError("The passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const result = await post<{ message: string }>(
        reset ? "/auth/reset-password" : "/auth/forgot-password",
        reset
          ? { token, password: data.get("password") }
          : { email: data.get("email") },
      );
      if (reset) {
        setToken("");
        useUI.getState().resetWorkspace();
        client.clear();
      }
      form.reset();
      setMessage(result.message);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const missing = reset && token !== null && !/^[A-Za-z0-9_-]{43}$/.test(token);
  return (
    <main className="recovery-page">
      <div className="auth-card recovery-card">
        <Logo />
        <h1>{reset ? "Choose a new password" : "Forgot your password?"}</h1>
        <p>
          {reset
            ? "Updating your password signs out all existing sessions."
            : "Enter your account email to request a reset link."}
        </p>
        {message ? (
          <p role="status" className="recovery-message">
            {message}
          </p>
        ) : (
          <>
            {missing ? (
              <p role="alert">
                This link is missing a valid reset token. Open the complete link
                from your email, or request a new one.
              </p>
            ) : reset && token === null ? (
              <p role="status">Opening reset link…</p>
            ) : !reset && options.isPending ? (
              <p role="status">Checking password recovery…</p>
            ) : !reset && options.isError ? (
              <div role="alert">
                <p>Could not check password recovery. Please try again.</p>
                <Button
                  variant="secondary"
                  onClick={() => void options.refetch()}
                >
                  Try again
                </Button>
              </div>
            ) : !reset && !options.data?.password_reset ? (
              <p role="status">
                Password recovery is unavailable. Contact the site operator.
              </p>
            ) : (
              <form onSubmit={submit}>
                {reset ? (
                  <>
                    <label>
                      New password
                      <input
                        name="password"
                        type="password"
                        autoComplete="new-password"
                        minLength={10}
                        maxLength={128}
                        required
                        disabled={busy}
                      />
                    </label>
                    <label>
                      Confirm new password
                      <input
                        name="confirmation"
                        type="password"
                        autoComplete="new-password"
                        minLength={10}
                        maxLength={128}
                        required
                        disabled={busy}
                      />
                    </label>
                    <small>
                      Use 10–128 characters. Reset links expire after 30
                      minutes.
                    </small>
                  </>
                ) : (
                  <label>
                    Email
                    <input
                      name="email"
                      type="email"
                      autoComplete="email"
                      maxLength={254}
                      required
                      disabled={busy}
                    />
                  </label>
                )}
                {error && <p role="alert">{error}</p>}
                <Button type="submit" disabled={busy}>
                  {busy && <Loader2 className="spin" size={15} />}
                  {reset ? "Update password" : "Request reset link"}
                </Button>
              </form>
            )}
          </>
        )}
        {reset && !message && (
          <Link className="text-button" href="/forgot-password">
            Request a new link
          </Link>
        )}
        <Link className="text-button" href="/">
          Back to sign in
        </Link>
      </div>
    </main>
  );
}
