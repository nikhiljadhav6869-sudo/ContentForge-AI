"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { motion } from "motion/react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  GitBranch,
  Hexagon,
  Layers,
  Loader2,
  Network,
  Play,
  ScanEye,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { api, post } from "@/lib/api";
import { useUI } from "@/lib/store";
import { Logo } from "./studio";
import { Button } from "./ui/button";
import { startDemo } from "./shared";
export default function Landing() {
  const router = useRouter();
  const client = useQueryClient();
  const options = useQuery({
    queryKey: ["auth-options"],
    queryFn: () =>
      api<{ registration: boolean; demo: boolean }>("/auth/options"),
    retry: false,
  });
  const registration = options.data?.registration === true;
  const demoEnabled = options.data?.demo === true;
  const [busy, setBusy] = useState(false);
  const [auth, setAuth] = useState<"login" | "register" | null>(null);
  async function demo() {
    setBusy(true);
    try {
      const run = await startDemo();
      client.clear();
      router.push(`/control/${run.id}`);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true);
    try {
      await post(`/auth/${auth}`, data);
      useUI.getState().resetWorkspace();
      client.clear();
      router.push("/dashboard");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="landing">
      <nav className="landing-nav">
        <Logo />
        <div>
          <a href="#features">Platform</a>
          <a href="#evidence">Why evidence?</a>
          <a href="#how">How it works</a>
        </div>
        <div>
          <button className="text-button" onClick={() => setAuth("login")}>
            Sign in
          </button>
          <Button
            size="sm"
            disabled={options.isPending}
            onClick={() => setAuth(registration ? "register" : "login")}
          >
            Start creating <ArrowUpRight size={14} />
          </Button>
        </div>
      </nav>
      <div className="hero-orb" />
      <section className="landing-hero">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="hero-badge">
            <span />
            THE NEXT CHAPTER OF CONTENT CREATION
            <ChevronRight size={13} />
          </div>
          <h1>
            One idea.
            <br />
            Ten AI agents.
            <br />
            <span>Infinite possibilities.</span>
          </h1>
          <p>
            Research, create, verify, and refine content with an intelligent
            <br className="desktop-break" /> team of AI agents working together
            in real time.
          </p>
          <div className="hero-actions">
            {demoEnabled && (
              <Button onClick={demo} disabled={busy}>
                {busy ? (
                  <Loader2 size={17} className="spin" />
                ) : (
                  <Play size={15} fill="currentColor" />
                )}
                Explore the live demo <ArrowRight size={16} />
              </Button>
            )}
            <Button
              variant="secondary"
              disabled={options.isPending}
              onClick={() => setAuth(registration ? "register" : "login")}
            >
              Build your first campaign
            </Button>
          </div>
          {options.isError ? (
            <div role="alert">
              Sign-up options could not load. Existing members can still sign
              in.{" "}
              <button
                className="text-button"
                onClick={() => options.refetch()}
                disabled={options.isFetching}
              >
                Retry sign-up options
              </button>
            </div>
          ) : options.data && !registration ? (
            <p>
              Account registration is closed. Contact the site operator for
              access.
            </p>
          ) : null}
          <div className="hero-notes">
            {demoEnabled && (
              <span>
                <Check size={13} />
                No API key for demo
              </span>
            )}
            <span>
              <Check size={13} />
              Evidence you can inspect
            </span>
            <span>
              <Check size={13} />
              Human approval built in
            </span>
          </div>
        </motion.div>
        <motion.div
          className="hero-visual"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.15, duration: 0.7 }}
        >
          <div className="hero-visual-top">
            <span className="window-dots">
              <i />
              <i />
              <i />
            </span>
            <span>THE CONTENTFORGE NETWORK</span>
            <span className="badge">Architecture preview</span>
          </div>
          <div className="orbital-graph">
            <svg viewBox="0 0 620 390" aria-hidden="true">
              <defs>
                <linearGradient id="edge">
                  <stop stopColor="#68b7ff" />
                  <stop offset="1" stopColor="#a78bfa" />
                </linearGradient>
              </defs>
              <g stroke="url(#edge)" fill="none" opacity=".5">
                <path d="M310 185 Q180 80 100 90M310 185 Q450 70 520 90M310 185 Q200 180 95 240M310 185 Q460 160 525 240M310 185 L310 330" />
                <circle cx="310" cy="185" r="110" strokeDasharray="3 9" />
                <circle cx="310" cy="185" r="155" opacity=".35" />
              </g>
            </svg>
            <div className="core-agent">
              <Hexagon size={45} />
              <strong>ContentForge</strong>
              <small>YOUR AGENT TEAM</small>
            </div>
            <div className="satellite research">
              <span>
                <ScanEye size={20} />
              </span>
              <strong>Research</strong>
              <small>Find the evidence</small>
            </div>
            <div className="satellite write">
              <span>
                <Layers size={20} />
              </span>
              <strong>Create</strong>
              <small>Make ideas resonate</small>
            </div>
            <div className="satellite verify">
              <span>
                <ShieldCheck size={20} />
              </span>
              <strong>Verify</strong>
              <small>Trace every claim</small>
            </div>
            <div className="satellite refine">
              <span>
                <Sparkles size={20} />
              </span>
              <strong>Refine</strong>
              <small>Raise the standard</small>
            </div>
            <div className="human-chip">
              <Check size={13} /> You make the final call
            </div>
          </div>
          <div className="hero-visual-footer">
            <span>
              <Network size={13} />
              10 specialized agents
            </span>
            <span>
              <GitBranch size={13} />
              One shared workflow
            </span>
            <span>
              <ShieldCheck size={13} />
              Full traceability
            </span>
          </div>
        </motion.div>
      </section>
      <div className="landing-strip">
        <span>FROM THE FIRST SPARK TO THE FINAL DRAFT</span>
        <strong>Research.</strong>
        <strong>Collaborate.</strong>
        <strong>Verify.</strong>
        <strong>Create with confidence.</strong>
      </div>
      <section className="landing-section" id="features">
        <div className="eyebrow">BUILT FOR THE WAY IDEAS WORK</div>
        <h2>
          A creative team.
          <br />
          An evidence trail.<span> A better way forward.</span>
        </h2>
        <div className="feature-grid">
          <article className="feature-card large">
            <Network size={28} />
            <span className="feature-number">01 / ORCHESTRATION</span>
            <h3>
              See the thinking
              <br />
              behind the workflow.
            </h3>
            <p>
              Follow observable agent actions, source reads, decisions,
              revisions, and results in a live control center.
            </p>
            <div className="mini-pipeline">
              Research <ArrowRight size={14} /> Write <ArrowRight size={14} />{" "}
              Verify <ArrowRight size={14} /> Review
            </div>
            <Button
              variant="ghost"
              onClick={demoEnabled ? demo : () => setAuth("login")}
              disabled={busy}
            >
              Explore the control center <ArrowUpRight size={15} />
            </Button>
          </article>
          <article className="feature-card large teal" id="evidence">
            <ScanEye size={28} />
            <span className="feature-number">02 / EVIDENCE INTELLIGENCE</span>
            <h3>
              Every claim.
              <br />A story you can trace.
            </h3>
            <p>
              Move from a highlighted sentence to its supporting passages,
              source documents, and complete revision history.
            </p>
            <div className="claim-sample">
              Battery electric vehicles produce no tailpipe emissions.
              <span>
                <ShieldCheck size={12} />
                Linked to source evidence
              </span>
            </div>
          </article>
        </div>
      </section>
      <section className="landing-section how-section" id="how">
        <div>
          <div className="eyebrow">AN IDEA IS ALL IT TAKES</div>
          <h2>
            From a blank page
            <br />
            to a complete campaign.
          </h2>
        </div>
        <div className="how-steps">
          {[
            [
              "01",
              "Set the direction",
              "Add your brief, sources, audience, and brand voice.",
            ],
            [
              "02",
              "Let your team collaborate",
              "Watch specialized agents create and check your content.",
            ],
            [
              "03",
              "Review. Approve. Make it yours.",
              "Inspect the evidence, edit your drafts, and export your campaign.",
            ],
          ].map(([n, t, d]) => (
            <div key={n}>
              <span>{n}</span>
              <div>
                <h3>{t}</h3>
                <p>{d}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
      <footer className="landing-footer">
        <Logo />
        <span>
          From an idea to verified content. Powered by collaborating AI agents.
        </span>
        <span>Human judgment, always.</span>
      </footer>
      {auth && (
        <div className="auth-overlay">
          <div className="auth-card">
            <button
              className="auth-close"
              onClick={() => setAuth(null)}
              aria-label="Close sign-in"
            >
              ×
            </button>
            <Logo />
            <h2>
              {auth === "login"
                ? "Welcome back."
                : "Make room for better ideas."}
            </h2>
            <p>Your projects, evidence, and content in one workspace.</p>
            {auth === "register" && !registration ? (
              <p role="status">
                Registration is unavailable. Contact the site operator for
                access.
              </p>
            ) : (
              <form onSubmit={submit}>
                {auth === "register" && (
                  <label>
                    Your name
                    <input
                      name="name"
                      required
                      maxLength={80}
                      autoComplete="name"
                    />
                  </label>
                )}
                <label>
                  Email
                  <input
                    name="email"
                    type="email"
                    required
                    autoComplete="email"
                  />
                </label>
                <label>
                  Password
                  <input
                    name="password"
                    type="password"
                    minLength={10}
                    maxLength={128}
                    required
                    autoComplete={
                      auth === "login" ? "current-password" : "new-password"
                    }
                  />
                  <small>At least 10 characters</small>
                </label>
                <Button type="submit" disabled={busy}>
                  {busy ? <Loader2 className="spin" size={15} /> : null}
                  {auth === "login" ? "Sign in" : "Create account"}
                  <ArrowRight size={15} />
                </Button>
              </form>
            )}
            {auth === "login" && (
              <Link className="text-button" href="/forgot-password">
                Forgot your password?
              </Link>
            )}
            {(auth === "register" || registration) && (
              <button
                className="text-button"
                onClick={() => setAuth(auth === "login" ? "register" : "login")}
              >
                {auth === "login"
                  ? "New here? Create an account"
                  : "Already have an account? Sign in"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
