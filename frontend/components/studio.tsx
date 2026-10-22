"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { motion, AnimatePresence } from "motion/react";
import {
  LayoutDashboard,
  Workflow,
  Network,
  ScanEye,
  FilePenLine,
  ChartNoAxesCombined,
  ClipboardCheck,
  CalendarDays,
  Settings2,
  ChevronsLeft,
  PanelLeft,
  Plus,
  Command,
  Search,
  ArrowUpRight,
  Bell,
  LogOut,
  X,
  Hexagon,
  ChevronDown,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { api, post, ApiError, type Run, type Settings } from "@/lib/api";
import { useUI } from "@/lib/store";
import { Button } from "./ui/button";
import { Loading, ErrorState } from "./shared";
import Landing from "./landing";
import {
  Dashboard,
  Analytics,
  Calendar,
  SettingsPage,
  Approvals,
} from "./supporting-pages";
import CreateWorkflow from "./create-workflow";
import ControlCenter from "./control-center";
import EvidenceStudio from "./evidence-studio";
import ContentStudio from "./content-studio";
import ServiceStatus from "./service-status";
const nav = [
  { name: "Overview", path: "/dashboard", icon: LayoutDashboard },
  { name: "Workflow studio", path: "/workflows/new", icon: Workflow },
  { name: "Agent control center", path: "/control", icon: Network },
  { name: "Evidence intelligence", path: "/evidence", icon: ScanEye },
  { name: "Content studio", path: "/content", icon: FilePenLine },
  { name: "Agent analytics", path: "/analytics", icon: ChartNoAxesCombined },
  { name: "Human approvals", path: "/approvals", icon: ClipboardCheck },
  { name: "Publishing calendar", path: "/calendar", icon: CalendarDays },
];
export function Logo() {
  return (
    <span className="logo">
      <span className="logo-mark">
        <Hexagon size={26} />
        <span>F</span>
      </span>
      <strong>
        contentforge<span>AI</span>
      </strong>
    </span>
  );
}
export default function Studio() {
  const pathname = usePathname();
  const router = useRouter();
  const client = useQueryClient();
  const [mobile, setMobile] = useState(false);
  const [command, setCommand] = useState(false);
  const [search, setSearch] = useState("");
  const {
    collapsed,
    toggleSidebar,
    runId: storedRunId,
    workspaceId,
    bindWorkspace,
    resetWorkspace,
    setRunId,
  } = useUI();
  const [signingOut, setSigningOut] = useState(false);
  const isLanding = pathname === "/";
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () =>
      api<{ name: string; workspace: string; workspace_id: string }>("/me"),
    enabled: !isLanding,
  });
  const runId = workspaceId === me.data?.workspace_id ? storedRunId : null;
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<Run[]>("/workflows"),
    enabled: !!me.data,
  });
  const preferences = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Settings>("/settings"),
    enabled: !!me.data,
  });
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommand((s) => !s);
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  useEffect(() => {
    if (!me.data?.workspace_id) return;
    bindWorkspace(me.data.workspace_id);
    const parts = pathname.split("/");
    if (["control", "evidence", "content"].includes(parts[1]) && parts[2]) {
      setRunId(parts[2]);
    } else if (
      runs.data &&
      !runs.data.some((run) => run.id === useUI.getState().runId)
    ) {
      setRunId(runs.data[0]?.id ?? null);
    }
  }, [pathname, setRunId, bindWorkspace, me.data?.workspace_id, runs.data]);
  useEffect(() => {
    setMobile(false);
  }, [pathname]);
  useEffect(() => {
    const theme = preferences.data?.preferences.theme || "dark";
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const apply = () =>
      (document.documentElement.dataset.theme =
        theme === "system" ? (media.matches ? "light" : "dark") : theme);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [preferences.data]);
  const pathFor = (path: string) =>
    ["/control", "/evidence", "/content"].includes(path) && runId
      ? `${path}/${runId}`
      : path;
  const page =
    nav.find((n) => pathname.startsWith(n.path.split("/new")[0]))?.name ||
    "Workspace settings";
  const navigate = (path: string) => {
    router.push(pathFor(path));
    setCommand(false);
  };
  if (isLanding) return <Landing />;
  if (me.isLoading)
    return (
      <div className="standalone">
        <Loading />
      </div>
    );
  if (me.error && !(me.error instanceof ApiError && me.error.status === 401))
    return (
      <div className="standalone">
        <ErrorState error={me.error} retry={() => void me.refetch()} />
      </div>
    );
  if (me.error)
    return (
      <div className="auth-needed">
        <Logo />
        <h1>Your creative workspace awaits.</h1>
        <p>Sign in or explore the complete demonstration.</p>
        <Button onClick={() => router.push("/")}>
          Open ContentForge <ArrowUpRight size={16} />
        </Button>
      </div>
    );
  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      {mobile && (
        <button
          aria-label="Dismiss navigation overlay"
          className="mobile-scrim"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <button
          className="mobile-menu-close mobile-toggle icon-button"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        >
          <X size={18} />
        </button>
        <Link href="/" className="sidebar-logo">
          <Logo />
        </Link>
        <button
          className="workspace-switch"
          onClick={() => navigate("/settings")}
        >
          <span className="workspace-avatar">CF</span>
          <span className="nav-label">
            <strong>{me.data?.workspace}</strong>
            <small>Creator workspace</small>
          </span>
          <ChevronDown size={13} />
        </button>
        <div className="sidebar-section-label nav-label">WORKSPACE</div>
        <nav>
          {nav.map((item, i) => {
            const Icon = item.icon;
            const active = pathname.startsWith(item.path.split("/new")[0]);
            return (
              <Link
                key={item.path}
                href={pathFor(item.path)}
                title={item.name}
                className={`nav-item ${active ? "active" : ""}`}
              >
                <Icon size={18} />
                <span className="nav-label">{item.name}</span>
                {i === 3 && <span className="nav-new nav-label">NEW</span>}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-divider" />
        <div className="sidebar-section-label nav-label">
          RECENT CAMPAIGNS{" "}
          <button
            aria-label="New campaign"
            onClick={() => router.push("/workflows/new")}
          >
            <Plus size={14} />
          </button>
        </div>
        <div className="recent-campaigns">
          {runs.data?.slice(0, 3).map((r) => (
            <button
              key={r.id}
              onClick={() => router.push(`/control/${r.id}`)}
              title={r.title}
            >
              <span className={`small-dot ${r.status}`} />
              <span className="nav-label">{r.title}</span>
            </button>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="workspace-tip nav-label">
            <Sparkles size={18} />
            <strong>Ideas deserve evidence.</strong>
            <p>Try the full EV campaign demo with no API key.</p>
            <Link href="/workflows/new">
              Create a campaign <ArrowUpRight size={13} />
            </Link>
          </div>
          <Link
            href="/settings"
            className={`nav-item ${pathname === "/settings" ? "active" : ""}`}
          >
            <Settings2 size={18} />
            <span className="nav-label">Settings</span>
          </Link>
          <button
            className="user-card"
            disabled={signingOut}
            onClick={async () => {
              setSigningOut(true);
              try {
                await post("/auth/logout");
                resetWorkspace();
                client.clear();
                router.push("/");
              } catch (error) {
                toast.error((error as Error).message);
              } finally {
                setSigningOut(false);
              }
            }}
            title="Sign out"
          >
            <span className="user-avatar">{me.data?.name.slice(0, 1)}</span>
            <span className="nav-label">
              <strong>{me.data?.name}</strong>
              <small>Personal workspace</small>
            </span>
            <LogOut size={15} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            aria-label="Toggle navigation"
            className="icon-button desktop-toggle"
            onClick={toggleSidebar}
          >
            <PanelLeft size={18} />
          </button>
          <button
            aria-label="Open navigation"
            className="icon-button mobile-toggle"
            onClick={() => setMobile(true)}
          >
            <PanelLeft size={18} />
          </button>
          <span className="breadcrumb">
            Workspace <span>/</span> <strong>{page}</strong>
          </span>
          <div className="topbar-actions">
            <button
              className="command-trigger"
              onClick={() => setCommand(true)}
            >
              <Search size={14} />
              <span>Quick search</span>
              <kbd>⌘ K</kbd>
            </button>
            <ServiceStatus />
            <button
              className="icon-button"
              aria-label="Open pending approvals"
              onClick={() => router.push("/approvals")}
            >
              <Bell size={17} />
            </button>
            <span className="tiny-avatar">{me.data?.name.slice(0, 1)}</span>
          </div>
        </header>
        <AnimatePresence mode="wait">
          <motion.main
            key={pathname}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className={`page-content ${pathname.startsWith("/control") ? "control-page" : ""}`}
          >
            {pathname === "/dashboard" ? (
              <Dashboard />
            ) : pathname === "/workflows/new" ? (
              <CreateWorkflow />
            ) : pathname.startsWith("/control") ? (
              <ControlCenter id={pathname.split("/")[2] || runId} />
            ) : pathname.startsWith("/evidence") ? (
              <EvidenceStudio id={pathname.split("/")[2] || runId} />
            ) : pathname.startsWith("/content") ? (
              <ContentStudio id={pathname.split("/")[2] || runId} />
            ) : pathname === "/analytics" ? (
              <Analytics />
            ) : pathname === "/approvals" ? (
              <Approvals />
            ) : pathname === "/calendar" ? (
              <Calendar />
            ) : pathname === "/settings" ? (
              <SettingsPage />
            ) : (
              <ErrorState error={new Error("This page does not exist.")} />
            )}
          </motion.main>
        </AnimatePresence>
      </div>
      <Dialog.Root open={command} onOpenChange={setCommand}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="command-dialog">
            <Dialog.Title className="sr-only">
              Navigate the workspace
            </Dialog.Title>
            <Dialog.Description className="sr-only">
              Search pages or campaigns.
            </Dialog.Description>
            <div className="command-search">
              <Search size={20} />
              <input
                autoFocus
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Where would you like to go?"
              />
              <Dialog.Close aria-label="Close">
                <X size={18} />
              </Dialog.Close>
            </div>
            <div className="command-options">
              {nav
                .filter((n) =>
                  n.name.toLowerCase().includes(search.toLowerCase()),
                )
                .map((n) => (
                  <button key={n.path} onClick={() => navigate(n.path)}>
                    <n.icon size={17} />
                    {n.name}
                    <ArrowUpRight size={14} />
                  </button>
                ))}
              {runs.data
                ?.filter((r) =>
                  r.title.toLowerCase().includes(search.toLowerCase()),
                )
                .slice(0, 5)
                .map((r) => (
                  <button
                    key={r.id}
                    onClick={() => {
                      router.push(`/control/${r.id}`);
                      setCommand(false);
                    }}
                  >
                    <Workflow size={17} />
                    {r.title.slice(0, 60)}
                  </button>
                ))}
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
