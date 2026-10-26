"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  plainDocument,
  documentText,
  RichDocumentView,
  type RichDocument,
} from "@/lib/rich-text";
import {
  ArrowLeftRight,
  Bold,
  Check,
  ClipboardCheck,
  Download,
  FilePenLine,
  History,
  Italic,
  List,
  Loader2,
  MessageSquare,
  PenLine,
  Save,
  ShieldCheck,
  Undo2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import {
  api,
  post,
  latest,
  currentClaims,
  label,
  type Detail,
  type Version,
  type Settings,
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
  Download as DownloadButton,
  CopyButton,
  Empty,
} from "./shared";
export function ReviewPanel({
  run,
  onDone,
}: {
  run: Detail;
  onDone: () => void;
}) {
  const [comment, setComment] = useState("");
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const warnings = currentClaims(run).filter((c) => c.status !== "supported");
  async function decide(decision: string) {
    setBusy(true);
    try {
      await post(`/workflows/${run.id}/review`, {
        decision,
        comment,
        acknowledge_warnings: ack,
      });
      toast.success(
        decision === "approve"
          ? "Approval recorded. Preparing your exports."
          : decision === "revise"
            ? "Revision requested. Your team is back at work."
            : "Draft rejected.",
      );
      onDone();
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel review-panel">
      <div className="section-title">
        <ClipboardCheck size={18} />
        <h2>Your editorial decision</h2>
      </div>
      <p>Review the current versions and their evidence before approving.</p>
      {warnings.length > 0 && (
        <div className="warning-banner">
          {warnings.length} claim{warnings.length !== 1 ? "s" : ""} still need
          evidence review. Approval does not change their verification status.
        </div>
      )}
      {run.mode === "demo" && (
        <p className="help-text">
          This campaign uses demonstration references. Human approval here is
          part of the sample journey.
        </p>
      )}
      <label>
        Review notes or revision request
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
          maxLength={2000}
          placeholder="What works? What should change?"
        />
      </label>
      {warnings.length > 0 && (
        <label className="check-label">
          <input
            type="checkbox"
            checked={ack}
            onChange={(e) => setAck(e.target.checked)}
          />
          I reviewed the remaining evidence warnings.
        </label>
      )}
      <div className="review-actions">
        <Button
          disabled={
            busy ||
            run.status !== "awaiting_approval" ||
            (warnings.length > 0 && !ack)
          }
          onClick={() => decide("approve")}
        >
          <Check size={15} />
          Approve current versions
        </Button>
        <Button
          variant="secondary"
          disabled={
            busy || run.status !== "awaiting_approval" || !comment.trim()
          }
          onClick={() => decide("revise")}
        >
          <Undo2 size={14} />
          Request revision
        </Button>
        <Button
          variant="ghost"
          disabled={busy || run.status !== "awaiting_approval"}
          onClick={() => decide("reject")}
        >
          Reject
        </Button>
      </div>
    </section>
  );
}
function RichEditor({
  version,
  onChange,
}: {
  version: Version;
  onChange: (document: RichDocument) => void;
}) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        blockquote: false,
        code: false,
        codeBlock: false,
        heading: false,
        horizontalRule: false,
        orderedList: false,
        strike: false,
        link: false,
        underline: false,
      }),
    ],
    immediatelyRender: false,
    content: version.document || plainDocument(version.body),
    onUpdate: ({ editor }) => onChange(editor.getJSON() as RichDocument),
    editorProps: {
      attributes: {
        "aria-label": "Content editor",
        role: "textbox",
        "aria-multiline": "true",
        class: "rich-editor",
      },
    },
  });
  return (
    <div className="editor-wrap">
      <div className="editor-toolbar">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Bold"
          aria-pressed={editor?.isActive("bold") || false}
          onClick={() => editor?.chain().focus().toggleBold().run()}
        >
          <Bold size={15} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Italic"
          aria-pressed={editor?.isActive("italic") || false}
          onClick={() => editor?.chain().focus().toggleItalic().run()}
        >
          <Italic size={15} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Bullet list"
          aria-pressed={editor?.isActive("bulletList") || false}
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
        >
          <List size={15} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Undo"
          onClick={() => editor?.chain().focus().undo().run()}
        >
          <Undo2 size={15} />
        </Button>
        <small>
          Formatting is saved. Each new version needs its own evidence review.
        </small>
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}
export default function ContentStudio({ id }: { id: string | null }) {
  const router = useRouter();
  const client = useQueryClient();
  const query = useRun(id);
  const preferences = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Settings>("/settings"),
  });
  const [artifactId, setArtifactId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<RichDocument | null>(null);
  const [editBase, setEditBase] = useState<Version | null>(null);
  const [compare, setCompare] = useState(false);
  const [comment, setComment] = useState("");
  const [quote, setQuote] = useState("");
  const [busy, setBusy] = useState(false);
  const run = query.data;
  if (!id) return <NoRun />;
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  if (!run) return null;
  const artifact =
    run.artifacts.find((a) => a.id === artifactId) || run.artifacts[0];
  const versions = artifact ? latest(run, artifact.id) : [];
  const version = versions.find((v) => v.id === versionId) || versions[0];
  const previous = versions.find((v) => v.number < (version?.number || 0));
  const comments = run.comments.filter((c) => c.version_id === version?.id);
  async function refresh() {
    await client.invalidateQueries({ queryKey: ["run", id] });
    await client.invalidateQueries({ queryKey: ["runs"] });
  }
  async function save() {
    if (!version || !artifact || !draft || !editBase) return;
    setBusy(true);
    try {
      await api(`/artifacts/${artifact.id}`, {
        method: "PUT",
        body: JSON.stringify({
          body: documentText(draft),
          document: draft,
          base_version: editBase.number,
        }),
      });
      setEditing(false);
      setVersionId("");
      await refresh();
      toast.success("New version saved. Evidence status reset for review.");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function addComment() {
    if (!version) return;
    try {
      await post(`/versions/${version.id}/comments`, { text: comment, quote });
      setComment("");
      setQuote("");
      await refresh();
      toast.success("Comment recorded.");
    } catch (error) {
      toast.error((error as Error).message);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="CONTENT STUDIO"
        title="Make every word count."
        description="Refine your campaign, compare revisions, and make the final editorial call."
        actions={
          <>
            <RunPicker
              selected={id}
              onSelect={(next) => router.push(`/content/${next}`)}
            />
            {run.status === "completed" && (
              <DownloadButton
                runId={id}
                format={
                  preferences.data?.preferences.export_format || "markdown"
                }
              >
                <Download size={14} />
                Export campaign
              </DownloadButton>
            )}
          </>
        }
      />
      {run.mode === "demo" && <DemoBanner />}
      {!version ? (
        <Empty
          title="Your drafts are on their way"
          description="The writing agent will create your requested content formats here."
        />
      ) : (
        <div className="content-layout">
          <div>
            <section className="panel content-document">
              <div className="document-toolbar">
                <div className="format-tabs">
                  {run.artifacts.map((a) => (
                    <button
                      key={a.id}
                      className={a.id === artifact.id ? "active" : ""}
                      onClick={() => {
                        setArtifactId(a.id);
                        setVersionId("");
                        setEditing(false);
                        setCompare(false);
                      }}
                    >
                      {label(a.platform)}
                    </button>
                  ))}
                </div>
                <CopyButton text={version.body} />
              </div>
              <div className="content-actionbar">
                <div>
                  <span className="subtle-pill">Version {version.number}</span>
                  <span>{version.body.split(/\s+/).length} words</span>
                </div>
                <div>
                  {previous && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setCompare(!compare);
                        setEditing(false);
                      }}
                    >
                      <ArrowLeftRight size={14} />
                      {compare ? "Single view" : "Compare"}
                    </Button>
                  )}
                  {run.status === "awaiting_approval" &&
                    version.id === versions[0].id && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setEditing(!editing);
                          setDraft(
                            version.document || plainDocument(version.body),
                          );
                          setEditBase(version);
                          setCompare(false);
                        }}
                      >
                        {editing ? <X size={14} /> : <PenLine size={14} />}{" "}
                        {editing ? "Cancel edit" : "Edit document"}
                      </Button>
                    )}
                  {editing && (
                    <Button size="sm" disabled={busy} onClick={save}>
                      <Save size={14} />
                      Save version
                    </Button>
                  )}
                </div>
              </div>
              {editing ? (
                <RichEditor
                  key={editBase?.id || version.id}
                  version={editBase || version}
                  onChange={setDraft}
                />
              ) : compare && previous ? (
                <div className="compare-view">
                  <div>
                    <h3>Version {previous.number} · Previous</h3>
                    {previous.document ? (
                      <RichDocumentView document={previous.document} />
                    ) : (
                      <pre>{previous.body}</pre>
                    )}
                  </div>
                  <div>
                    <h3>Version {version.number} · Selected</h3>
                    {version.document ? (
                      <RichDocumentView document={version.document} />
                    ) : (
                      <pre>{version.body}</pre>
                    )}
                  </div>
                </div>
              ) : (
                <div
                  className="document-body"
                  onMouseUp={() => {
                    const selected = window.getSelection()?.toString() || "";
                    if (
                      selected.length <= 500 &&
                      version.body.includes(selected)
                    )
                      setQuote(selected);
                  }}
                >
                  {version.document ? (
                    <RichDocumentView document={version.document} />
                  ) : (
                    version.body
                  )}
                </div>
              )}
              <div className="document-bottom">
                <ShieldCheck size={14} />
                <span>
                  Evidence is tracked separately for every saved version.
                </span>
                <button onClick={() => router.push(`/evidence/${id}`)}>
                  Inspect claims →
                </button>
              </div>
            </section>
            {run.status === "awaiting_approval" && (
              <ReviewPanel run={run} onDone={refresh} />
            )}{" "}
            {run.status === "completed" && (
              <section className="approved-banner">
                <span>
                  <ShieldCheck size={25} />
                </span>
                <div>
                  <h3>Approved and ready for your next step.</h3>
                  <p>
                    Download approved drafts and their evidence as a ZIP
                    package, or schedule them in your editorial calendar.
                  </p>
                </div>
                <DownloadButton runId={id} format="zip">
                  Download ZIP package
                </DownloadButton>
                <DownloadButton runId={id} format="json">
                  Export JSON
                </DownloadButton>
                <Button
                  variant="secondary"
                  onClick={() => router.push("/calendar")}
                >
                  Open calendar
                </Button>
              </section>
            )}
          </div>
          <aside>
            <section className="panel version-panel">
              <div className="section-title">
                <History size={17} />
                <h2>Version history</h2>
              </div>
              {versions.map((v) => (
                <button
                  key={v.id}
                  className={`version-item ${v.id === version.id ? "selected" : ""}`}
                  onClick={() => {
                    setVersionId(v.id);
                    setEditing(false);
                  }}
                >
                  <span className="version-dot" />
                  <div>
                    <strong>
                      Version {v.number}
                      {v.id === versions[0].id && <small>Latest</small>}
                    </strong>
                    <p>{v.reason}</p>
                    <time>{new Date(v.created_at).toLocaleString()}</time>
                  </div>
                </button>
              ))}
            </section>
            <section className="panel comments-panel">
              <div className="section-title">
                <MessageSquare size={17} />
                <h2>Document comments</h2>
                <span className="count">{comments.length}</span>
              </div>
              {comments.map((c) => (
                <div className="comment" key={c.id}>
                  {c.quote && <blockquote>{c.quote}</blockquote>}
                  <p>{c.text}</p>
                  <small>{new Date(c.created_at).toLocaleString()}</small>
                </div>
              ))}
              {quote && (
                <div className="selected-quote">
                  <small>COMMENT ON SELECTION</small>
                  <p>“{quote}”</p>
                  <button onClick={() => setQuote("")}>Clear selection</button>
                </div>
              )}
              <label className="sr-only" htmlFor="comment">
                Add a comment
              </label>
              <textarea
                id="comment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                maxLength={2000}
                rows={3}
                placeholder="Add a comment, or select text in the document first…"
              />
              <Button
                variant="secondary"
                size="sm"
                disabled={!comment.trim()}
                onClick={addComment}
              >
                <PlusSmall />
                Add comment
              </Button>
            </section>
            {run.reviews.length > 0 && (
              <section className="panel review-history">
                <h2>Review history</h2>
                {run.reviews.map((r) => (
                  <div key={r.id}>
                    <strong>{label(r.decision)}</strong>
                    <p>{r.comment || "No additional notes."}</p>
                    <small>{new Date(r.created_at).toLocaleString()}</small>
                  </div>
                ))}
              </section>
            )}
          </aside>
        </div>
      )}
    </>
  );
}
function PlusSmall() {
  return <MessageSquare size={13} />;
}
