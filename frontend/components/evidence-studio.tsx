"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  ExternalLink,
  FileText,
  GitBranch,
  Link2,
  ScanEye,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import {
  post,
  latest,
  currentClaims,
  label,
  type Claim,
  type Detail,
  type Version,
} from "@/lib/api";
import { Button } from "./ui/button";
import {
  useRun,
  NoRun,
  Loading,
  ErrorState,
  PageHeading,
  RunPicker,
  DemoBanner,
  Empty,
  StatusBadge,
} from "./shared";
export function HighlightedDocument({
  body,
  claims,
  selected,
  onSelect,
}: {
  body: string;
  claims: Claim[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const ordered = [...claims].sort((a, b) => a.start - b.start);
  // Persisted offsets count Unicode code points (Python), not UTF-16 units.
  const points = Array.from(body);
  const slice = (start: number, end?: number) =>
    points.slice(start, end).join("");
  const pieces: React.ReactNode[] = [];
  let cursor = 0;
  for (const claim of ordered) {
    if (claim.start < cursor || slice(claim.start, claim.end) !== claim.text)
      continue;
    pieces.push(slice(cursor, claim.start));
    pieces.push(
      <button
        key={claim.id}
        className={`claim-highlight ${claim.status} ${selected === claim.id ? "selected" : ""}`}
        onClick={() => onSelect(claim.id)}
        title={`${label(claim.status)} — inspect evidence`}
        data-testid="claim-highlight"
      >
        {claim.text}
        <sup>{ordered.indexOf(claim) + 1}</sup>
      </button>,
    );
    cursor = claim.end;
  }
  pieces.push(slice(cursor));
  return <div className="document-body">{pieces}</div>;
}
export default function EvidenceStudio({ id }: { id: string | null }) {
  const router = useRouter();
  const query = useRun(id);
  const [artifactId, setArtifactId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [claimId, setClaimId] = useState<string | null>(null);
  const [sourceId, setSourceId] = useState<string | null>(null);
  const run = query.data;
  if (!id) return <NoRun />;
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  if (!run) return null;
  const artifact =
    run.artifacts.find((a) => a.id === artifactId) || run.artifacts[0];
  const versions = artifact ? latest(run, artifact.id) : [];
  const version = versions.find((v) => v.id === versionId) || versions[0];
  const claims = run.claims.filter((c) => c.version_id === version?.id);
  const selected = claims.find((c) => c.id === claimId) || claims[0];
  const links = run.links.filter((l) => l.claim_id === selected?.id);
  const linkedSources = new Set(
    links.map(
      (l) => run.passages.find((p) => p.id === l.passage_id)?.source_id,
    ),
  );
  const source = run.sources.find((s) => s.id === sourceId);
  const covered = claims.filter((c) => c.status === "supported").length;
  return (
    <>
      <PageHeading
        eyebrow="EVIDENCE INTELLIGENCE"
        title="Great content stands up to questions."
        description="Follow every significant claim back to its evidence, source, and revision history."
        actions={
          <RunPicker
            selected={id}
            onSelect={(next) => router.push(`/evidence/${next}`)}
          />
        }
      />
      {run.mode === "demo" && <DemoBanner />}
      <div className="evidence-summary">
        <span>
          <ShieldCheck size={15} />
          <strong>{covered}</strong> supported
        </span>
        <span>
          <TriangleAlert size={15} />
          <strong>
            {claims.filter((c) => c.status === "disputed").length}
          </strong>{" "}
          disputed
        </span>
        <span>
          <ScanEye size={15} />
          <strong>
            {claims.filter((c) => c.status === "unverified").length}
          </strong>{" "}
          unverified
        </span>
        <div />
        <small>Support measures source agreement, not independent truth.</small>
      </div>
      <div className="evidence-layout">
        <aside className="panel source-library">
          <div className="section-title">
            <BookOpen size={16} />
            <h2>Source library</h2>
            <span className="count">{run.sources.length}</span>
          </div>
          <p className="help-text">
            Select a source to inspect the stored material.
          </p>
          {run.sources.map((s, i) => (
            <button
              key={s.id}
              className={`source-card ${sourceId === s.id ? "selected" : ""} ${linkedSources.has(s.id) ? "linked" : ""}`}
              onClick={() => setSourceId(s.id)}
            >
              <div>
                <span className="source-icon">
                  <FileText size={17} />
                </span>
                <span className="source-number">
                  SOURCE {String(i + 1).padStart(2, "0")}
                </span>
                {linkedSources.has(s.id) && <Link2 size={13} />}
              </div>
              <strong>{s.title}</strong>
              <small>
                {s.kind === "demo" ? "SAMPLE REFERENCE" : s.kind.toUpperCase()}
              </small>
              <span className="source-status">
                <span />
                Stored & accessible
              </span>
            </button>
          ))}
          {!run.sources.length && (
            <p className="help-text">
              No sources were supplied. Claims will remain unverified.
            </p>
          )}
          {source && (
            <div className="source-detail">
              <h3>{source.title}</h3>
              <p>{source.credibility}</p>
              <small>
                Publication date: {source.publication_date || "Not supplied"}
              </small>
              {source.url && (
                <a href={source.url} target="_blank" rel="noreferrer">
                  Open source <ExternalLink size={12} />
                </a>
              )}
              <pre>{source.text}</pre>
              <small>SHA-256: {source.content_hash.slice(0, 16)}…</small>
            </div>
          )}
        </aside>
        <section className="panel evidence-document">
          <div className="document-toolbar">
            <div className="format-tabs">
              {run.artifacts.map((a) => (
                <button
                  key={a.id}
                  className={artifact?.id === a.id ? "active" : ""}
                  onClick={() => {
                    setArtifactId(a.id);
                    setVersionId("");
                    setClaimId(null);
                  }}
                >
                  {label(a.platform)}
                </button>
              ))}
            </div>
            {versions.length > 0 && (
              <select
                aria-label="Evidence version"
                value={version?.id}
                onChange={(e) => {
                  setVersionId(e.target.value);
                  setClaimId(null);
                }}
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    Version {v.number}
                    {v.id === versions[0].id ? " · Latest" : ""}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div className="document-meta">
            <span>
              CONTENT / {artifact?.platform.toUpperCase() || "AWAITING DRAFT"}
            </span>
            <span>{version?.body.split(/\s+/).length || 0} words</span>
          </div>
          {version ? (
            <HighlightedDocument
              body={version.body}
              claims={claims}
              selected={selected?.id || null}
              onSelect={setClaimId}
            />
          ) : (
            <Empty
              title="The evidence trail is taking shape"
              description="Content and extracted claims will appear as your agents complete their work."
            />
          )}
          <div className="document-legend">
            <span className="supported">Supported</span>
            <span className="disputed">Disputed</span>
            <span className="unverified">Unverified</span>
            <small>Click an underlined claim to inspect it.</small>
          </div>
        </section>
        <aside className="panel evidence-inspector">
          <div className="section-title">
            <ScanEye size={17} />
            <h2>Evidence inspector</h2>
          </div>
          {selected ? (
            <>
              <div className="detail-label spaced">SELECTED CLAIM</div>
              <blockquote>{selected.text}</blockquote>
              <StatusBadge status={selected.status} />
              <p className="verification-explanation">{selected.explanation}</p>
              <div className="inspector-detail">
                <span>Responsible stage</span>
                <strong>
                  {run.executions
                    .find((e) => e.id === selected.execution_id)
                    ?.agent.replace("_", " ") || "Human edit"}
                </strong>
              </div>
              <div className="inspector-detail">
                <span>Content version</span>
                <strong>v{version?.number}</strong>
              </div>
              <div className="detail-label spaced">EVIDENCE RELATIONSHIPS</div>
              {links.length ? (
                <div className="relation-map">
                  <div className={`relation-claim ${selected.status}`}>
                    <ScanEye size={14} />
                    Selected claim
                  </div>
                  {links.map((link) => {
                    const passage = run.passages.find(
                      (p) => p.id === link.passage_id,
                    );
                    const doc = run.sources.find(
                      (s) => s.id === passage?.source_id,
                    );
                    return (
                      <div className="relation-branch" key={link.id}>
                        <span className={`relation-line ${link.relation}`} />
                        <div>
                          <span className={`relation-label ${link.relation}`}>
                            {label(link.relation)}
                          </span>
                          <button onClick={() => setSourceId(doc?.id || null)}>
                            <FileText size={13} />
                            {doc?.title}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="warning-banner">
                  No sufficient supporting evidence is linked.
                </div>
              )}
              {links.map((link) => (
                <div
                  className={`evidence-passage ${link.relation}`}
                  key={link.id}
                >
                  <span>
                    <Link2 size={12} />
                    {label(link.relation)}
                  </span>
                  <p>“{link.quote}”</p>
                  <small>Exact passage stored in the source library</small>
                </div>
              ))}
              <EvidenceAssessment
                key={selected.id}
                run={run}
                claim={selected}
                enabled={
                  run.status === "awaiting_approval" &&
                  version?.id === versions[0]?.id
                }
              />
              <div className="detail-label spaced">CLAIM LIFECYCLE</div>
              <div className="claim-lifecycle">
                {selected.history.map((entry, i) => (
                  <div key={i}>
                    <span className="activity-dot" />
                    <div>
                      <strong>{label(entry.state)}</strong>
                      <small>{new Date(entry.at).toLocaleString()}</small>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <Empty
              title="Choose a claim"
              description="Select an underlined sentence to inspect its evidence."
            />
          )}
        </aside>
      </div>
    </>
  );
}

function EvidenceAssessment({
  run,
  claim,
  enabled,
}: {
  run: Detail;
  claim: Claim;
  enabled: boolean;
}) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [passageId, setPassageId] = useState(run.passages[0]?.id || "");
  const [quote, setQuote] = useState("");
  const [relation, setRelation] = useState("mentions");
  const [explanation, setExplanation] = useState("");
  const [busy, setBusy] = useState(false);
  const passage = run.passages.find((p) => p.id === passageId);
  async function save() {
    setBusy(true);
    try {
      await post(`/claims/${claim.id}/evidence`, {
        passage_id: passageId,
        relation,
        quote,
        explanation,
      });
      await client.invalidateQueries({ queryKey: ["run", run.id] });
      setOpen(false);
      toast.success("Human evidence assessment recorded.");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!enabled || !run.passages.length) return null;
  return (
    <div className="evidence-assessment">
      <Button variant="secondary" size="sm" onClick={() => setOpen(!open)}>
        <Link2 size={13} />
        {open ? "Close assessment" : "Assess source evidence"}
      </Button>
      {open && (
        <div>
          <label>
            Stored passage
            <select
              value={passageId}
              onChange={(e) => {
                setPassageId(e.target.value);
                setQuote("");
              }}
            >
              {run.passages.map((p) => (
                <option key={p.id} value={p.id}>
                  {run.sources.find((s) => s.id === p.source_id)?.title} ·
                  passage {p.ordinal + 1}
                </option>
              ))}
            </select>
          </label>
          <pre>{passage?.text}</pre>
          <label>
            Evidence relation
            <select
              value={relation}
              onChange={(e) => setRelation(e.target.value)}
            >
              {[
                "supports",
                "contradicts",
                "partially_supports",
                "mentions",
                "insufficient_evidence",
              ].map((r) => (
                <option key={r} value={r}>
                  {label(r)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Exact quote
            <textarea
              value={quote}
              onChange={(e) => setQuote(e.target.value)}
              rows={3}
              minLength={10}
              maxLength={1200}
              placeholder="Copy a relevant passage exactly."
            />
          </label>
          <label>
            Your assessment
            <textarea
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              rows={3}
              minLength={10}
              maxLength={2000}
              placeholder="Explain how this passage relates to the claim."
            />
          </label>
          <Button
            size="sm"
            disabled={busy || quote.length < 10 || explanation.length < 10}
            onClick={save}
          >
            Record assessment
          </Button>
        </div>
      )}
    </div>
  );
}
