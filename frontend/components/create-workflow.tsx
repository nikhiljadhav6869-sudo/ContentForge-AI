"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Check,
  ChevronDown,
  FileText,
  Globe,
  Instagram,
  Linkedin,
  Loader2,
  Paperclip,
  Plus,
  ShieldCheck,
  Sparkles,
  Upload,
  Youtube,
} from "lucide-react";
import { toast } from "sonner";
import { api, post, type Source, type Settings } from "@/lib/api";
import { Button } from "./ui/button";
import { PageHeading } from "./shared";
const platforms = [
  {
    id: "blog",
    name: "Blog article",
    hint: "In-depth, structured narrative",
    icon: FileText,
  },
  {
    id: "linkedin",
    name: "LinkedIn",
    hint: "Professional conversation",
    icon: Linkedin,
  },
  {
    id: "instagram",
    name: "Instagram",
    hint: "Scroll-stopping caption",
    icon: Instagram,
  },
  {
    id: "youtube",
    name: "YouTube",
    hint: "A script worth watching",
    icon: Youtube,
  },
];
export default function CreateWorkflow() {
  const router = useRouter();
  const client = useQueryClient();
  const [selected, setSelected] = useState([
    "blog",
    "linkedin",
    "instagram",
    "youtube",
  ]);
  const [sources, setSources] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [mode, setMode] = useState("demo");
  const [url, setUrl] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Settings>("/settings"),
  });
  const library = useQuery({
    queryKey: ["sources"],
    queryFn: () => api<Source[]>("/sources"),
  });
  const [prompt, setPrompt] = useState(
    "Create a researched content campaign about electric vehicles in India.",
  );
  useEffect(() => {
    if (settings.data) setMode(settings.data.preferences.default_provider);
  }, [settings.data]);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected.length) {
      toast.error("Choose at least one content format.");
      return;
    }
    setBusy(true);
    const form = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await post<{ id: string }>("/workflows", {
        ...form,
        prompt,
        platforms: selected,
        source_ids: sources,
        mode,
        max_revisions: Number(
          form.max_revisions ?? settings.data?.preferences.max_revisions ?? 1,
        ),
        quality_threshold: Number(
          form.quality_threshold ??
            settings.data?.preferences.quality_threshold ??
            80,
        ),
      });
      await client.invalidateQueries({ queryKey: ["runs"] });
      toast.success("Your agent team is getting started.");
      router.push(`/control/${result.id}`);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file: File) {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const source = await api<Source>("/sources/upload", {
        method: "POST",
        body: form,
      });
      setSources((s) => [...s, source.id]);
      await client.invalidateQueries({ queryKey: ["sources"] });
      toast.success("Source added to your library.");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setUploading(false);
    }
  }
  async function addURL() {
    setUploading(true);
    try {
      const source = await post<Source>("/sources/url", { url });
      setSources((s) => [...s, source.id]);
      setUrl("");
      await client.invalidateQueries({ queryKey: ["sources"] });
      toast.success("Source retrieved and stored.");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setUploading(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="WORKFLOW STUDIO"
        title="What will you create today?"
        description="Give your agents a direction. They’ll take it from first draft to final review."
      />
      <form className="creation-layout" onSubmit={submit}>
        <div className="creation-main">
          <section className="panel brief-panel">
            <div className="section-heading">
              <span className="section-icon">
                <Sparkles size={18} />
              </span>
              <div>
                <h2>Start with an idea</h2>
                <p>The best campaigns begin with a clear brief.</p>
              </div>
              <span className="step-label">01</span>
            </div>
            <textarea
              className="prompt-input"
              aria-label="Campaign brief"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              minLength={10}
              maxLength={4000}
              required
              rows={5}
              placeholder="Tell your team what you want to create…"
            />
            <div className="prompt-footer">
              <span>
                <Sparkles size={13} /> Be specific about the outcome you want.
              </span>
              <span>{prompt.length}/4,000</span>
            </div>
            <div className="example-prompts">
              <span>TRY AN IDEA</span>
              {[
                "Electric vehicles in India",
                "AI literacy for students",
                "Sustainable city living",
              ].map((topic) => (
                <button
                  key={topic}
                  type="button"
                  onClick={() =>
                    setPrompt(
                      `Create a researched content campaign about ${topic.toLowerCase()}.`,
                    )
                  }
                >
                  {topic}
                  <ArrowRight size={12} />
                </button>
              ))}
            </div>
          </section>
          <section className="panel">
            <div className="section-heading">
              <span className="section-icon violet">
                <FileText size={18} />
              </span>
              <div>
                <h2>Choose your content formats</h2>
                <p>One campaign, made for every channel.</p>
              </div>
              <span className="step-label">02</span>
            </div>
            <div className="platform-grid">
              {platforms.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  aria-pressed={selected.includes(p.id)}
                  className={`platform-card ${selected.includes(p.id) ? "selected" : ""}`}
                  onClick={() =>
                    setSelected((s) =>
                      s.includes(p.id)
                        ? s.filter((x) => x !== p.id)
                        : [...s, p.id],
                    )
                  }
                >
                  <p.icon size={22} />
                  <strong>{p.name}</strong>
                  <small>{p.hint}</small>
                  <span className="checkbox">
                    {selected.includes(p.id) && <Check size={12} />}
                  </span>
                </button>
              ))}
            </div>
          </section>
          <section className="panel">
            <div className="section-heading">
              <span className="section-icon teal">
                <ShieldCheck size={18} />
              </span>
              <div>
                <h2>Give your ideas a foundation</h2>
                <p>Add source material your agents can actually inspect.</p>
              </div>
              <span className="step-label">03</span>
            </div>
            <label className="upload-area">
              <Upload size={24} />
              <strong>
                {uploading
                  ? "Reading your source…"
                  : "Drop in your reference material"}
              </strong>
              <span>
                Click to upload PDF, TXT, or Markdown · up to 2 MB / 30 PDF
                pages
              </span>
              <input
                type="file"
                accept=".pdf,.txt,.md"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) upload(file);
                  e.target.value = "";
                }}
                disabled={uploading}
              />
            </label>
            <div className="url-input">
              <Globe size={16} />
              <input
                aria-label="Source URL"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://… add a trusted source URL"
              />
              <Button
                variant="secondary"
                size="sm"
                type="button"
                onClick={addURL}
                disabled={!url || uploading}
              >
                <Plus size={14} />
                Add
              </Button>
            </div>
            <p className="help-text">
              Approved domains: {settings.data?.source_hosts.join(", ")}. Demo
              mode uses its own clearly labeled sample references.
            </p>
            <div className="source-checks">
              {library.data?.slice(0, 12).map((s) => (
                <label key={s.id}>
                  <input
                    type="checkbox"
                    checked={sources.includes(s.id)}
                    onChange={(e) =>
                      setSources((v) =>
                        e.target.checked
                          ? [...v, s.id]
                          : v.filter((id) => id !== s.id),
                      )
                    }
                  />
                  <FileText size={14} />
                  <span>{s.title}</span>
                  <small>{s.kind}</small>
                </label>
              ))}
            </div>
          </section>
        </div>
        <aside className="creation-aside">
          <section className="panel">
            <h2>Set the direction</h2>
            <p className="panel-description">
              A few details make all the difference.
            </p>
            <label>
              Who is this for?
              <input
                name="audience"
                defaultValue="Indian college students"
                maxLength={200}
              />
            </label>
            <label>
              Voice & tone
              <select name="tone">
                <option>Clear and educational</option>
                <option>Professional and insightful</option>
                <option>Warm and conversational</option>
                <option>Bold and imaginative</option>
              </select>
            </label>
            <label>
              Campaign goal
              <textarea
                name="goals"
                defaultValue="Educate and inspire informed action"
                rows={2}
                maxLength={1000}
              />
            </label>
            <label>
              Brand voice
              <textarea
                name="brand"
                key={settings.data?.preferences.brand_voice}
                defaultValue={
                  settings.data?.preferences.brand_voice ||
                  "Helpful, evidence-led, inclusive. Avoid hype."
                }
                rows={3}
                maxLength={2000}
              />
            </label>
            <label>
              Execution mode
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                {[
                  ["demo", "Demo · no API key required"],
                  ["openai", "OpenAI-compatible"],
                  ["gemini", "Google Gemini"],
                  ["ollama", "Ollama · local model"],
                ].map(([value, name]) => (
                  <option
                    key={value}
                    value={value}
                    disabled={
                      value !== "demo" && !settings.data?.providers[value]
                    }
                  >
                    {name}
                    {value !== "demo" && !settings.data?.providers[value]
                      ? " · not configured"
                      : ""}
                  </option>
                ))}
              </select>
            </label>
            <div className="info-callout">
              <Sparkles size={15} />
              <p>
                {mode === "demo"
                  ? "Demo runs the full EV example through real orchestration using sample outputs. Other topics require a connected model."
                  : "Live models use your uploaded or retrieved sources. No autonomous web search is performed."}
              </p>
            </div>
            <button
              type="button"
              className="advanced-toggle"
              onClick={() => setAdvanced(!advanced)}
            >
              Advanced workflow settings
              <ChevronDown size={14} />
            </button>
            {advanced && (
              <div className="advanced-fields">
                <label>
                  Quality threshold
                  <input
                    name="quality_threshold"
                    type="number"
                    min={50}
                    max={100}
                    defaultValue={
                      settings.data?.preferences.quality_threshold || 80
                    }
                  />
                </label>
                <label>
                  Maximum automatic revisions
                  <input
                    name="max_revisions"
                    type="number"
                    min={0}
                    max={2}
                    defaultValue={settings.data?.preferences.max_revisions ?? 1}
                  />
                </label>
              </div>
            )}
            <Button
              className="full-button"
              disabled={busy || uploading}
              type="submit"
            >
              {busy ? (
                <Loader2 size={16} className="spin" />
              ) : (
                <Sparkles size={16} />
              )}
              Launch agent team
              <ArrowRight size={16} />
            </Button>
            <p className="center-note">You approve every final draft.</p>
          </section>
          <div className="creation-promise">
            <ShieldCheck size={18} />
            <div>
              <strong>Built for accountable content</strong>
              <p>
                Sources, claims, agent actions, and revisions stay connected
                from start to finish.
              </p>
            </div>
          </div>
        </aside>
      </form>
    </>
  );
}
