"use client";


import { PhaseWorkspaceNav } from "@/components/phase-workspace-nav";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { CSSProperties, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  canAccessWorkspace,
  isProtectedWorkspacePath,
  visibleWorkspaces,
  workspaceAccessLevel,
  workspaceForPath,
  type WorkspaceDefinition,
  type WorkspaceAccessLevel,
} from "@/lib/navigation/workspaces";

type ShellContext = {
  company: {
    public_id: string;
    code: string;
    display_name: string;
    locale: string;
    timezone: string;
    currency: string;
    branding?: {
      product_name: string;
      tagline: string;
      logo_url: string;
      compact_logo_url: string;
      favicon_url: string;
      primary_color: string;
      accent_color: string;
      sidebar_style: string;
      powered_by_build360: boolean;
      version: number;
    };
    primary_domain?: string | null;
  };
  permissions: string[];
  features: Record<string, boolean>;
  platform_operator: boolean;
  company_membership_count: number;
  notifications: {
    unread: number;
    critical_unread: number;
  };
  environment: "development" | "testing" | "demo" | "production";
  version: string;
};

type LoadState =
  | { status: "loading" }
  | { status: "ready"; context: ShellContext }
  | { status: "unavailable" };

const RECENT_KEY = "build360-recent-workspaces";

function readRecent(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]") as unknown;
    return Array.isArray(value)
      ? value.filter((item): item is string => typeof item === "string").slice(0, 5)
      : [];
  } catch {
    return [];
  }
}

function rememberWorkspace(href: string) {
  const next = [href, ...readRecent().filter((item) => item !== href)].slice(0, 5);
  localStorage.setItem(RECENT_KEY, JSON.stringify(next));
}

function WorkspaceGlyph({
  workspace,
  className = "h-[18px] w-[18px]",
}: Readonly<{ workspace: WorkspaceDefinition; className?: string }>) {
  const paths: Record<string, string[]> = {
    platform: ["M3 10.5 12 3l9 7.5", "M5.5 9.5V21h13V9.5", "M9 21v-6h6v6"],
    today: ["M7 3v3", "M17 3v3", "M4 8h16", "M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1Z", "m8 15 2 2 4-5"],
    search: ["M20 20l-4.4-4.4", "M10.8 17a6.2 6.2 0 1 0 0-12.4 6.2 6.2 0 0 0 0 12.4Z"],
    crm: ["M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z", "M22 21v-2a4 4 0 0 0-3-3.87", "M16 3.13a4 4 0 0 1 0 7.75"],
    project360: ["M4 21V7l8-4 8 4v14", "M8 10h2", "M14 10h2", "M8 14h2", "M14 14h2", "M10 21v-3h4v3"],
    executive: ["M4 19V9", "M10 19V5", "M16 19v-7", "M22 19H2"],
    approvals: ["M5 12.5 9 16l10-10", "M4 4h16v16H4Z"],
    delivery: ["m12 3 9 5-9 5-9-5 9-5Z", "m3 12 9 5 9-5", "m3 16 9 5 9-5"],
    supply: ["M3 6h11v10H3Z", "M14 10h4l3 3v3h-7Z", "M7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z", "M18 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"],
    field: ["M4 14h16", "M6 14v-2a6 6 0 0 1 12 0v2", "M9 12V7", "M15 12V7", "M8 18h8"],
    finance: ["M12 2v20", "M17 6H9.5a3.5 3.5 0 0 0 0 7H14a3.5 3.5 0 1 1 0 7H6"],
    communications: ["M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z", "M8 9h8", "M8 13h5"],
    operations: ["M4 19V9", "M10 19V5", "M16 19v-7", "M22 19H2"],
    ai: ["m12 3 1.2 3.2L16.5 7.5l-3.3 1.3L12 12l-1.2-3.2-3.3-1.3 3.3-1.3L12 3Z", "m18 13 .8 2.2L21 16l-2.2.8L18 19l-.8-2.2L15 16l2.2-.8L18 13Z"],
    integrations: ["M8 12h8", "M12 8v8", "M5 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z", "M19 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"],
    compliance: ["M12 3 20 7v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V7l8-4Z", "m9 12 2 2 4-5"],
    people: ["M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z", "M17 11h5", "M19.5 8.5v5"],
    brand: ["M12 3a9 9 0 1 0 0 18h1.5a2 2 0 0 0 0-4H15a2 2 0 0 1 0-4h1", "M7.5 10h.01", "M10.5 6.5h.01", "M15 7.5h.01"],
  };
  const selected = paths[workspace.key] ?? ["M4 4h6v6H4Z", "M14 4h6v6h-6Z", "M4 14h6v6H4Z", "M14 14h6v6h-6Z"];

  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
    >
      {selected.map((path) => <path d={path} key={path} />)}
    </svg>
  );
}

function WorkspaceMark({ workspace }: Readonly<{ workspace: WorkspaceDefinition }>) {
  return (
    <span
      aria-hidden="true"
      className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[var(--brand)] text-white"
    >
      <WorkspaceGlyph workspace={workspace} />
    </span>
  );
}

function LoadingChrome({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      <div className="fixed inset-x-0 top-0 z-40 h-16 animate-pulse border-b border-[var(--border)] bg-white" />
      <div className="pt-16">{children}</div>
    </div>
  );
}

function CommandPalette({
  open,
  onClose,
  workspaces,
  recent,
}: Readonly<{
  open: boolean;
  onClose: () => void;
  workspaces: WorkspaceDefinition[];
  recent: string[];
}>) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      const recentSet = new Set(recent);
      return [
        ...workspaces.filter((workspace) => recentSet.has(workspace.href)),
        ...workspaces.filter((workspace) => !recentSet.has(workspace.href)),
      ];
    }
    return workspaces.filter((workspace) =>
      `${workspace.title} ${workspace.shortTitle} ${workspace.description}`
        .toLowerCase()
        .includes(normalized),
    );
  }, [query, recent, workspaces]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center px-4 pt-[12vh]">
      <button
        aria-label="Close workspace command palette"
        className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
        onClick={onClose}
        type="button"
      />
      <div
        aria-label="Workspace command palette"
        aria-modal="true"
        className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-white/20 bg-white shadow-2xl"
        role="dialog"
      >
        <div className="border-b border-[var(--border)] p-4">
          <label className="sr-only" htmlFor="workspace-command-search">
            Search workspaces
          </label>
          <input
            className="w-full rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-base"
            id="workspace-command-search"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search CRM, projects, finance, field operations…"
            ref={inputRef}
            value={query}
          />
        </div>
        <div className="max-h-[58vh] overflow-y-auto p-2">
          {results.length ? (
            results.map((workspace) => (
              <Link
                className="flex items-center gap-3 rounded-xl px-3 py-3 hover:bg-[var(--brand-soft)] focus:bg-[var(--brand-soft)]"
                href={workspace.href}
                key={workspace.key}
                onClick={onClose}
              >
                <WorkspaceMark workspace={workspace} />
                <span className="min-w-0">
                  <span className="block font-semibold">{workspace.title}</span>
                  <span className="block truncate text-sm text-[var(--muted)]">
                    {workspace.description}
                  </span>
                </span>
              </Link>
            ))
          ) : (
            <p className="px-4 py-8 text-center text-sm text-[var(--muted)]">
              No authorized workspace matches this search.
            </p>
          )}
        </div>
        <div className="flex items-center justify-between border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
          <span>Permission-aware workspace search</span>
          <span>Esc to close</span>
        </div>
      </div>
    </div>
  );
}

function Sidebar({
  currentPath,
  workspaces,
  companyName,
  branding,
  version,
  onSearch,
  expanded,
  onToggle,
  onHoverChange,
}: Readonly<{
  currentPath: string;
  workspaces: WorkspaceDefinition[];
  companyName: string;
  branding: ShellContext["company"]["branding"];
  version: string;
  onSearch: () => void;
  expanded: boolean;
  onToggle: () => void;
  onHoverChange: (hovered: boolean) => void;
}>) {
  const sidebarStyle = branding?.sidebar_style ?? "LIGHT";
  const darkSidebar = sidebarStyle === "DARK" || sidebarStyle === "BRAND";
  const asideStyle =
    sidebarStyle === "BRAND"
      ? { background: "linear-gradient(180deg, var(--brand-strong), var(--brand))" }
      : undefined;
  const logoUrl = branding?.compact_logo_url || branding?.logo_url || "";
  return (
    <aside
      className={`build360-sidebar fixed inset-y-0 left-0 z-50 hidden w-[88px] flex-col border-r lg:flex ${
        darkSidebar ? "border-white/10 bg-slate-950 text-white" : "border-[var(--border)] bg-white"
      }`}
      data-expanded={expanded ? "true" : "false"}
      onMouseEnter={() => onHoverChange(true)}
      onMouseLeave={() => onHoverChange(false)}
      style={asideStyle}
    >
      <div className={`grid min-h-16 place-items-center border-b px-3 ${darkSidebar ? "border-white/10" : "border-[var(--border)]"}`}>
        <Link className="build360-brand-link flex min-w-0 items-center gap-3" href="/project360" title={branding?.product_name || companyName}>
          <span className="flex min-w-0 items-center gap-3">
            {logoUrl ? (
              <span
                aria-label={`${branding?.product_name || companyName} logo`}
                className="h-9 w-9 shrink-0 rounded-xl bg-white bg-contain bg-center bg-no-repeat shadow-sm"
                role="img"
                style={{ backgroundImage: `url(${logoUrl})` }}
              />
            ) : (
              <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl text-[10px] font-black ${darkSidebar ? "bg-white/15 text-white" : "bg-[var(--brand-soft)] text-[var(--brand)]"}`}>
                {companyName.slice(0, 2).toUpperCase()}
              </span>
            )}
            <span className="build360-sidebar-label min-w-0">
              <span className={`block truncate text-xs font-bold uppercase tracking-[0.2em] ${darkSidebar ? "text-white/75" : "text-[var(--brand)]"}`}>
                {branding?.product_name && branding.product_name !== companyName
                  ? branding.product_name
                  : (branding?.tagline || "Company workspace")}
              </span>
              <span className="mt-1 block truncate text-lg font-semibold">{companyName}</span>
            </span>
          </span>
        </Link>
        <button
          aria-label={expanded ? "Collapse navigation" : "Expand navigation"}
          className="build360-sidebar-toggle"
          onClick={onToggle}
          title={expanded ? "Collapse navigation" : "Expand navigation"}
          type="button"
        >
          <svg aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2">
            <path d={expanded ? "m15 18-6-6 6-6" : "m9 18 6-6-6-6"} />
          </svg>
        </button>
      </div>
      <div className="px-3 py-3">
        <button
          className={`flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left text-sm transition ${
            darkSidebar
              ? "border-white/15 bg-white/10 text-white/70 hover:border-white/30"
              : "border-[var(--border)] bg-[var(--background)] text-[var(--muted)] hover:border-[var(--brand)]"
          }`}
          onClick={onSearch}
          type="button"
        >
          <svg aria-hidden="true" className="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">
            <path d="M20 20l-4.4-4.4" />
            <circle cx="10.8" cy="10.8" r="6.2" />
          </svg>
          <span className="build360-sidebar-label min-w-0 flex-1 truncate">Search</span>
          <kbd className="build360-sidebar-label rounded-md border border-current/15 px-1.5 py-0.5 text-[9px] opacity-60">Ctrl K</kbd>
        </button>
      </div>
      <nav aria-label="Build360 workspaces" className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-3 pb-5">
        <ul className="space-y-1">
          {workspaces.filter((workspace) => workspace.key !== "brand").map((workspace) => {
            const active =
              currentPath === workspace.href ||
              currentPath.startsWith(`${workspace.href}/`);
            return (
              <li key={workspace.key}>
                <Link
                  aria-current={active ? "page" : undefined}
                  title={workspace.title}
                  className={`build360-nav-link grid h-12 w-full place-items-center rounded-2xl text-sm font-semibold transition ${
                    active
                      ? darkSidebar
                        ? "bg-white text-[var(--brand)]"
                        : "bg-[var(--brand)] text-white"
                      : darkSidebar
                        ? "text-white/75 hover:bg-white/10 hover:text-white"
                        : "text-slate-700 hover:bg-[var(--brand-soft)] hover:text-[var(--brand)]"
                  }`}
                  href={workspace.href}
                >
                  <span
                    aria-hidden="true"
                    className={`build360-nav-icon grid h-9 w-9 shrink-0 place-items-center rounded-xl ${
                      active
                        ? darkSidebar ? "bg-[var(--brand-soft)]" : "bg-white/15"
                        : darkSidebar ? "bg-white/10 text-white" : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    <WorkspaceGlyph workspace={workspace} />
                  </span>
                  <span className="build360-sidebar-label min-w-0 truncate">{workspace.shortTitle}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      
        <PhaseWorkspaceNav />
</nav>
      <div className={`build360-sidebar-footer border-t px-3 py-3 text-xs ${darkSidebar ? "border-white/10 text-white/60" : "border-[var(--border)] text-[var(--muted)]"}`}>
        <span
          aria-hidden="true"
          className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${darkSidebar ? "bg-white/10 text-white" : "bg-slate-100 text-slate-600"}`}
        >
          <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">
            <path d="M4 21V7l8-4 8 4v14" />
            <path d="M8 10h2M14 10h2M8 14h2M14 14h2M10 21v-3h4v3" />
          </svg>
        </span>
        <span className="build360-sidebar-label min-w-0">
          <span className="block truncate font-semibold">{companyName}</span>
          <span className="mt-1 block truncate text-[10px]">{branding?.tagline || "Construction Operating System"} · v{version}</span>
          {branding?.powered_by_build360 === false ? null : <span className="mt-1 block truncate text-[10px]">Powered by MPSqre Build360</span>}
        </span>
      </div>
    </aside>
  );
}

function MobileNavigation({
  currentPath,
  workspaces,
  onMore,
  onSearch,
}: Readonly<{
  currentPath: string;
  workspaces: WorkspaceDefinition[];
  onMore: () => void;
  onSearch: () => void;
}>) {
  const primary = workspaces.filter((workspace) => workspace.mobilePrimary).slice(0, 3);
  return (
    <nav
      aria-label="Mobile workspace navigation"
      className="fixed inset-x-0 bottom-0 z-50 grid grid-cols-5 border-t border-[var(--border)] bg-white/95 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-10px_30px_rgba(15,23,42,0.08)] backdrop-blur lg:hidden"
    >
      {primary.map((workspace) => {
        const active =
          currentPath === workspace.href || currentPath.startsWith(`${workspace.href}/`);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={`flex min-w-0 flex-col items-center gap-1 rounded-lg px-1 py-1 text-[11px] font-semibold ${
              active ? "text-[var(--brand)]" : "text-[var(--muted)]"
            }`}
            href={workspace.href}
            key={workspace.key}
          >
            <span
              aria-hidden="true"
              className={`grid h-7 w-7 place-items-center rounded-lg text-[9px] font-bold ${
                active ? "bg-[var(--brand)] text-white" : "bg-slate-100"
              }`}
            >
              {workspace.badge}
            </span>
            <span className="truncate">{workspace.shortTitle}</span>
          </Link>
        );
      })}
      <button
        className="flex flex-col items-center gap-1 rounded-lg px-1 py-1 text-[11px] font-semibold text-[var(--muted)]"
        onClick={onSearch}
        type="button"
      >
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-slate-100 text-base" aria-hidden="true">
          ⌕
        </span>
        Search
      </button>
      <button
        className="flex flex-col items-center gap-1 rounded-lg px-1 py-1 text-[11px] font-semibold text-[var(--muted)]"
        onClick={onMore}
        type="button"
      >
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-slate-100 text-base" aria-hidden="true">
          ⋯
        </span>
        More
      </button>
    </nav>
  );
}

function UnauthorizedWorkspaceRedirect({
  workspaceKey,
  workspaceTitle,
}: Readonly<{
  workspaceKey: string;
  workspaceTitle: string;
}>) {
  const router = useRouter();

  useEffect(() => {
    const params = new URLSearchParams({
      access: "denied",
      workspace: workspaceKey,
    });
    router.replace(`/platform?${params.toString()}`);
  }, [router, workspaceKey]);

  return (
    <LoadingChrome>
      <div className="grid min-h-[55vh] place-items-center px-6">
        <div className="max-w-md rounded-2xl border border-[var(--border)] bg-white p-6 text-center shadow-sm">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--brand)]">
            Access restricted
          </p>
          <h1 className="mt-2 text-lg font-semibold">{workspaceTitle}</h1>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Your current company package or role does not authorize this workspace.
            Redirecting to an authorized workspace…
          </p>
        </div>
      </div>
    </LoadingChrome>
  );
}

function WorkspaceAccessBadge({
  level,
}: Readonly<{
  level: WorkspaceAccessLevel;
}>) {
  if (level === "NONE") return null;
  const label =
    level === "FULL" ? "Full access" : level === "EDIT" ? "Read + edit" : "View only";
  const className =
    level === "FULL"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : level === "EDIT"
        ? "border-[var(--brand)]/20 bg-[var(--brand-soft)] text-[var(--brand)]"
        : "border-slate-200 bg-slate-50 text-slate-600";
  return (
    <span
      aria-label={`Workspace access: ${label}`}
      className={`hidden rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-wide sm:inline-flex ${className}`}
    >
      {label}
    </span>
  );
}

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  const router = useRouter();
  const protectedRoute = isProtectedWorkspacePath(pathname);
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [sidebarHovered, setSidebarHovered] = useState(false);

  const loadContext = useCallback(async () => {
    const response = await fetch("/api/app-shell/context", {
      cache: "no-store",
      credentials: "same-origin",
    }).catch(() => null);
    if (!response?.ok) {
      setLoadState({ status: "unavailable" });
      return;
    }
    setLoadState({ status: "ready", context: (await response.json()) as ShellContext });
  }, []);

  useEffect(() => {
    if (!protectedRoute) return;
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void loadContext();
    });
    return () => controller.abort();
  }, [loadContext, protectedRoute]);

  useEffect(() => {
    if (!protectedRoute) return;
    const refresh = () => {
      void fetch("/api/auth/refresh", { method: "POST" }).finally(() => {
        void loadContext();
      });
    };
    const timer = window.setInterval(refresh, 8 * 60 * 1000);
    window.addEventListener("focus", refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, [loadContext, protectedRoute]);

  useEffect(() => {
    if (!protectedRoute) return;
    const workspace = workspaceForPath(pathname);
    if (workspace) rememberWorkspace(workspace.href);
  }, [pathname, protectedRoute]);

  useEffect(() => {
    if (!protectedRoute) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [protectedRoute]);

  useEffect(() => {
    if (!protectedRoute || loadState.status !== "ready") return;
    const brand = loadState.context.company.branding;
    const productName = brand?.product_name || "MPSqre Build360";
    const workspaceTitle = workspaceForPath(pathname)?.title || "Workspace";
    document.title = `${workspaceTitle} · ${productName}`;

    if (brand?.favicon_url) {
      let icon = document.querySelector<HTMLLinkElement>('link[data-build360-favicon="tenant"]');
      if (!icon) {
        icon = document.createElement("link");
        icon.rel = "icon";
        icon.dataset.build360Favicon = "tenant";
        document.head.appendChild(icon);
      }
      icon.href = brand.favicon_url;
    }

    let theme = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    if (!theme) {
      theme = document.createElement("meta");
      theme.name = "theme-color";
      document.head.appendChild(theme);
    }
    theme.content = brand?.primary_color || "#174D3C";
  }, [loadState, pathname, protectedRoute]);

  function openPalette() {
    setRecent(readRecent());
    setPaletteOpen(true);
  }

  if (!protectedRoute) return <>{children}</>;
  if (loadState.status === "loading") return <LoadingChrome>{children}</LoadingChrome>;
  if (loadState.status === "unavailable") {
    return (
      <div className="grid min-h-screen place-items-center px-6">
        <div className="max-w-md rounded-2xl border border-[var(--border)] bg-white p-7 text-center shadow-sm">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--brand)]">
            Build360 workspace
          </p>
          <h1 className="mt-3 text-2xl font-semibold">Navigation context is unavailable</h1>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            Confirm the backend is running and your company session is still active.
          </p>
          <button
            className="mt-6 rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white"
            onClick={() => void loadContext()}
            type="button"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { context } = loadState;
  const workspaceAccessContext = {
    permissions: context.permissions,
    features: context.features,
    platformOperator: context.platform_operator,
  };
  const workspaces = visibleWorkspaces(workspaceAccessContext);
  const currentWorkspace = workspaceForPath(pathname);
  const currentWorkspaceAuthorized = currentWorkspace
    ? canAccessWorkspace(currentWorkspace, workspaceAccessContext)
    : true;
  const currentWorkspaceAccessLevel = currentWorkspace
    ? workspaceAccessLevel(currentWorkspace, workspaceAccessContext)
    : "FULL";
  const unread = context.notifications.unread;
  const branding = context.company.branding;
  const primaryColor = branding?.primary_color || "#174d3c";
  const brandStyle = {
    "--brand": primaryColor,
    "--brand-strong": branding?.accent_color || "#0f382b",
    "--brand-soft": /^#[0-9a-f]{6}$/i.test(primaryColor) ? `${primaryColor}14` : "#e8f2ee",
  } as CSSProperties;
  const sidebarOpen = sidebarExpanded || sidebarHovered;

  if (currentWorkspace && !currentWorkspaceAuthorized) {
    return (
      <UnauthorizedWorkspaceRedirect
        workspaceKey={currentWorkspace.key}
        workspaceTitle={currentWorkspace.title}
      />
    );
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => null);
    router.replace("/sign-in");
    router.refresh();
  }

  return (
    <div className="min-h-screen bg-[var(--background)]" style={brandStyle}>
      <a
        className="fixed left-3 top-3 z-[100] -translate-y-24 rounded-lg bg-white px-4 py-2 font-semibold shadow focus:translate-y-0"
        href="#build360-main-content"
      >
        Skip to content
      </a>
      <Sidebar
        branding={branding}
        companyName={context.company.display_name}
        currentPath={pathname}
        expanded={sidebarExpanded}
        onHoverChange={setSidebarHovered}
        onSearch={openPalette}
        onToggle={() => setSidebarExpanded((value) => !value)}
        version={context.version}
        workspaces={workspaces}
      />

      <header className={`fixed inset-x-0 top-0 z-40 flex h-16 items-center justify-between border-b border-[var(--border)] bg-white/95 px-4 backdrop-blur lg:px-6 ${sidebarOpen ? "lg:left-72" : "lg:left-[88px]"}`}>
        <div className="min-w-0">
          <p className="truncate text-xs font-bold uppercase tracking-[0.15em] text-[var(--brand)] lg:hidden">
            {branding?.product_name || "MPSqre Build360"}
          </p>
          <div className="flex min-w-0 items-center gap-2">
            <p className="truncate text-sm font-semibold sm:text-base">
              {currentWorkspace?.title ?? "Authorized workspace"}
            </p>
            {currentWorkspace ? <WorkspaceAccessBadge level={currentWorkspaceAccessLevel} /> : null}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            aria-label="Search authorized workspaces"
            className="hidden h-9 items-center rounded-xl border border-[var(--border)] bg-[var(--surface-subtle)] px-3 text-sm text-[var(--muted)] transition hover:border-[var(--border-strong)] hover:bg-white sm:flex"
            onClick={openPalette}
            type="button"
          >
            Search
          </button>
          {context.permissions.includes("notification.read") ? (
            <Link
              aria-label={`${unread} unread notifications`}
              className="relative grid h-10 w-10 place-items-center rounded-xl border border-[var(--border)] bg-white font-bold"
              href="/communications"
            >
              <span aria-hidden="true">N</span>
              {unread > 0 ? (
                <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-red-600 px-1.5 py-0.5 text-center text-[10px] text-white">
                  {unread > 99 ? "99+" : unread}
                </span>
              ) : null}
            </Link>
          ) : null}
          <div className="relative">
            <button
              aria-expanded={profileOpen}
              aria-label="Open account menu"
              className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--brand)] text-sm font-bold text-white"
              onClick={() => setProfileOpen((value) => !value)}
              type="button"
            >
              {context.company.code.slice(0, 2).toUpperCase()}
            </button>
            {profileOpen ? (
              <div className="absolute right-0 top-12 w-64 rounded-2xl border border-[var(--border)] bg-white p-2 shadow-xl">
                <div className="border-b border-[var(--border)] px-3 py-3">
                  <p className="truncate font-semibold">{context.company.display_name}</p>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    {context.company.code} · {context.company.timezone}
                  </p>
                </div>
                <Link
                  className="mt-2 block rounded-xl px-3 py-2 text-sm font-semibold hover:bg-[var(--brand-soft)]"
                  href="/workspaces"
                  onClick={() => setProfileOpen(false)}
                >
                  All workspaces
                </Link>
                {context.company_membership_count > 1 ? (
                  <Link
                    className="block rounded-xl px-3 py-2 text-sm font-semibold hover:bg-[var(--brand-soft)]"
                    href="/select-company"
                    onClick={() => setProfileOpen(false)}
                  >
                    Switch company
                  </Link>
                ) : null}
                <button
                  className="block w-full rounded-xl px-3 py-2 text-left text-sm font-semibold text-red-700 hover:bg-red-50"
                  onClick={() => void logout()}
                  type="button"
                >
                  Sign out
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </header>

      <div className={`min-h-screen bg-[var(--background)] pb-20 pt-16 transition-[margin] duration-200 lg:pb-0 ${sidebarOpen ? "lg:ml-72" : "lg:ml-[88px]"}`}>
        <div id="build360-main-content">{children}</div>
      </div>

      <MobileNavigation
        currentPath={pathname}
        onMore={() => setMobileOpen(true)}
        onSearch={openPalette}
        workspaces={workspaces}
      />

      {mobileOpen ? (
        <div className="fixed inset-0 z-[70] lg:hidden">
          <button
            aria-label="Close workspace menu"
            className="absolute inset-0 bg-slate-950/45"
            onClick={() => setMobileOpen(false)}
            type="button"
          />
          <div className="absolute inset-x-0 bottom-0 max-h-[78vh] overflow-y-auto rounded-t-3xl bg-white px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-3 shadow-2xl">
            <div className="mx-auto mb-4 h-1.5 w-12 rounded-full bg-slate-300" />
            <div className="flex items-center justify-between px-1 pb-3">
              <h2 className="text-lg font-semibold">All workspaces</h2>
              <button className="rounded-lg px-3 py-2 text-sm font-semibold" onClick={() => setMobileOpen(false)} type="button">
                Close
              </button>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {workspaces.map((workspace) => (
                <Link
                  className="flex items-center gap-3 rounded-2xl border border-[var(--border)] p-3"
                  href={workspace.href}
                  key={workspace.key}
                  onClick={() => setMobileOpen(false)}
                >
                  <WorkspaceMark workspace={workspace} />
                  <span className="min-w-0">
                    <span className="block font-semibold">{workspace.shortTitle}</span>
                    <span className="block truncate text-xs text-[var(--muted)]">
                      {workspace.description}
                    </span>
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      <CommandPalette
        onClose={() => setPaletteOpen(false)}
        open={paletteOpen}
        recent={recent}
        workspaces={workspaces}
      />
    </div>
  );
}
