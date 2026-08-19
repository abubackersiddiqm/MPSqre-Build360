"use client";


import { PhaseWorkspaceNav } from "@/components/phase-workspace-nav";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { CSSProperties, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  isProtectedWorkspacePath,
  visibleWorkspaces,
  workspaceForPath,
  type WorkspaceDefinition,
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

function WorkspaceMark({ workspace }: Readonly<{ workspace: WorkspaceDefinition }>) {
  return (
    <span
      aria-hidden="true"
      className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[var(--brand)] text-xs font-bold tracking-wide text-white"
    >
      {workspace.badge}
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
}: Readonly<{
  currentPath: string;
  workspaces: WorkspaceDefinition[];
  companyName: string;
  branding: ShellContext["company"]["branding"];
  version: string;
  onSearch: () => void;
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
      className={`fixed inset-y-0 left-0 z-50 hidden w-72 flex-col border-r lg:flex ${
        darkSidebar ? "border-white/10 bg-slate-950 text-white" : "border-[var(--border)] bg-white"
      }`}
      style={asideStyle}
    >
      <div className={`border-b px-5 py-5 ${darkSidebar ? "border-white/10" : "border-[var(--border)]"}`}>
        <Link className="block" href="/project360">
          <span className="flex items-center gap-3">
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
            <span className="min-w-0">
              <span className={`block truncate text-xs font-bold uppercase tracking-[0.2em] ${darkSidebar ? "text-white/75" : "text-[var(--brand)]"}`}>
                {branding?.product_name && branding.product_name !== companyName
                  ? branding.product_name
                  : (branding?.tagline || "Company workspace")}
              </span>
              <span className="mt-1 block truncate text-lg font-semibold">{companyName}</span>
            </span>
          </span>
        </Link>
      </div>
      <div className="px-4 py-4">
        <button
          className={`flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left text-sm transition ${
            darkSidebar
              ? "border-white/15 bg-white/10 text-white/70 hover:border-white/30"
              : "border-[var(--border)] bg-[var(--background)] text-[var(--muted)] hover:border-[var(--brand)]"
          }`}
          onClick={onSearch}
          type="button"
        >
          <span>Search workspaces</span>
          <kbd className={`rounded border px-1.5 py-0.5 text-[10px] ${darkSidebar ? "border-white/15 bg-white/10 text-white/70" : "border-[var(--border)] bg-white"}`}>
            Ctrl K
          </kbd>
        </button>
      </div>
      <nav aria-label="Build360 workspaces" className="min-h-0 flex-1 overflow-y-auto px-3 pb-5">
        <ul className="space-y-1">
          {workspaces.filter((workspace) => workspace.key !== "brand").map((workspace) => {
            const active =
              currentPath === workspace.href ||
              currentPath.startsWith(`${workspace.href}/`);
            return (
              <li key={workspace.key}>
                <Link
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${
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
                    className={`grid h-8 w-8 place-items-center rounded-lg text-[10px] font-bold ${
                      active
                        ? darkSidebar ? "bg-[var(--brand-soft)]" : "bg-white/15"
                        : darkSidebar ? "bg-white/10 text-white" : "bg-[var(--brand-soft)] text-[var(--brand)]"
                    }`}
                  >
                    {workspace.badge}
                  </span>
                  <span className="truncate">{workspace.shortTitle}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      
        <PhaseWorkspaceNav />
</nav>
      <div className={`border-t px-5 py-4 text-xs ${darkSidebar ? "border-white/10 text-white/60" : "border-[var(--border)] text-[var(--muted)]"}`}>
        <span className="block">{branding?.tagline || "Construction Operating System"} · v{version}</span>
        {branding?.powered_by_build360 === false ? null : <span className="mt-1 block text-[10px]">Powered by MPSqre Build360</span>}
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

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  const router = useRouter();
  const protectedRoute = isProtectedWorkspacePath(pathname);
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);

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
  const workspaces = visibleWorkspaces({
    permissions: context.permissions,
    features: context.features,
    platformOperator: context.platform_operator,
  });
  const currentWorkspace = workspaceForPath(pathname);
  const unread = context.notifications.unread;
  const branding = context.company.branding;
  const primaryColor = branding?.primary_color || "#174d3c";
  const brandStyle = {
    "--brand": primaryColor,
    "--brand-strong": branding?.accent_color || "#0f382b",
    "--brand-soft": /^#[0-9a-f]{6}$/i.test(primaryColor) ? `${primaryColor}14` : "#e8f2ee",
  } as CSSProperties;

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
        onSearch={openPalette}
        version={context.version}
        workspaces={workspaces}
      />

      <header className="fixed inset-x-0 top-0 z-40 flex h-16 items-center justify-between border-b border-[var(--border)] bg-white/95 px-4 backdrop-blur lg:left-72 lg:px-6">
        <div className="min-w-0">
          <p className="truncate text-xs font-bold uppercase tracking-[0.15em] text-[var(--brand)] lg:hidden">
            {branding?.product_name || "MPSqre Build360"}
          </p>
          <p className="truncate text-sm font-semibold sm:text-base">
            {currentWorkspace?.title ?? "Authorized workspace"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            aria-label="Search authorized workspaces"
            className="hidden rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm text-[var(--muted)] sm:block lg:hidden"
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

      <div className="min-h-screen pt-16 pb-20 lg:ml-72 lg:pb-0">
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
