"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, post } from "@/lib/api";
import { Logo } from "./studio";
import { Button } from "./ui/button";

type Verification = {
  email: string;
  verified_at: string | null;
  demo_address: boolean;
  delivery_available: boolean;
};

function useVerification() {
  return useQuery({
    queryKey: ["email-verification"],
    queryFn: () => api<Verification>("/auth/email-verification"),
    retry: false,
  });
}

export function EmailVerificationPanel() {
  const query = useVerification();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function request() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await post<{ message: string }>(
        "/auth/email-verification/request",
      );
      setMessage(result.message);
      await query.refetch();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="panel email-verification-panel"
      aria-label="Email verification"
    >
      <h2>Account email</h2>
      {query.isPending ? (
        <p role="status">Checking verification status…</p>
      ) : query.isError ? (
        <>
          <p role="alert">Could not check email verification.</p>
          <Button
            type="button"
            variant="secondary"
            onClick={() => void query.refetch()}
          >
            Retry verification status
          </Button>
        </>
      ) : (
        <>
          <p>{query.data.email}</p>
          <p>
            <strong>
              {query.data.verified_at ? "Verified" : "Not verified"}
            </strong>
          </p>
          {query.data.verified_at ? (
            <p>Your account email has been confirmed.</p>
          ) : query.data.demo_address ? (
            <p>
              This demo address cannot receive email. Create a personal account
              to verify an email address.
            </p>
          ) : !query.data.delivery_available ? (
            <p>Email verification is unavailable. Contact the site operator.</p>
          ) : (
            <>
              <p>
                Request a link, then sign in to this account and confirm your
                email. Links expire after 24 hours.
              </p>
              <Button type="button" onClick={request} disabled={busy}>
                {busy ? "Requesting…" : "Send verification link"}
              </Button>
            </>
          )}
        </>
      )}
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

export default function VerifyEmail() {
  const query = useVerification();
  const client = useQueryClient();
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    const readLink = () => {
      const value = new URLSearchParams(window.location.hash.slice(1)).get(
        "token",
      );
      setToken((current) => value ?? current ?? "");
      if (value) {
        setError("");
        setMessage("");
      }
      window.history.replaceState(
        window.history.state,
        "",
        window.location.pathname,
      );
    };
    readLink();
    window.addEventListener("hashchange", readLink);
    return () => window.removeEventListener("hashchange", readLink);
  }, []);
  async function confirm() {
    setBusy(true);
    setError("");
    try {
      const result = await post<{ message: string }>(
        "/auth/email-verification/confirm",
        { token },
      );
      setToken("");
      setMessage(result.message);
      await client.invalidateQueries({ queryKey: ["email-verification"] });
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const missing = token !== null && !/^[A-Za-z0-9_-]{43}$/.test(token);
  return (
    <main className="recovery-page">
      <div className="auth-card recovery-card">
        <Logo />
        <h1>Verify your email</h1>
        {message ? (
          <p role="status">{message}</p>
        ) : missing ? (
          <p role="alert">
            This link is missing a valid verification token. Reopen the complete
            email link or request a new one in Settings.
          </p>
        ) : query.isPending || token === null ? (
          <p role="status">Checking your account…</p>
        ) : query.error instanceof ApiError && query.error.status === 401 ? (
          <p role="status">
            Sign in to the account that received this link, then reopen the
            complete link from your email.
          </p>
        ) : query.isError ? (
          <>
            <p role="alert">Could not check your account. Please retry.</p>
            <Button onClick={() => void query.refetch()}>Try again</Button>
          </>
        ) : (
          <>
            <p className="verification-email">
              Signed in as {query.data?.email}
            </p>
            {query.data?.verified_at ? (
              <p role="status">This account's email is already verified.</p>
            ) : (
              <>
                <p>
                  Confirm that you own the email address for this account. This
                  link works once and expires after 24 hours.
                </p>
                <Button onClick={confirm} disabled={busy}>
                  {busy ? "Verifying…" : "Verify email"}
                </Button>
              </>
            )}
            {error && <p role="alert">{error}</p>}
          </>
        )}
        <Link href="/settings" className="text-button">
          Open account settings
        </Link>
        <Link href="/" className="text-button">
          Back to sign in
        </Link>
      </div>
    </main>
  );
}
