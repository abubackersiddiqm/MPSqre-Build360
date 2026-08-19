"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

export type Company = {
  public_id: string;
  code: string;
  display_name: string;
  timezone: string;
  currency: string;
};
export type AdminopsSummary = {
  active_environments: number;
  pending_releases: number;
  failed_checks: number;
  active_slos: number;
  open_incidents: number;
  enabled_flags: number;
  planned_maintenance: number;
};
export type RuntimeEnvironment = {
  public_id: string;
  code: string;
  name: string;
  environment_type: string;
  base_url: string;
  region: string;
  data_residency: string;
  production_data_allowed: boolean;
  requires_change_approval: boolean;
  is_active: boolean;
  version: number;
};
type ReleaseCheck = {
  public_id: string;
  code: string;
  name: string;
  category: string;
  status: string;
  is_critical: boolean;
};
export type ReleaseRecord = {
  public_id: string;
  environment: RuntimeEnvironment;
  version_label: string;
  release_name: string;
  source_revision: string;
  artifact_sha256: string;
  status: string;
  readiness: {
    total_checks: number;
    passed_checks: number;
    failed_checks: number;
    blocking_checks: number;
    ready: boolean;
  };
  checks: ReleaseCheck[];
  created_at: string;
  version: number;
};
export type ServiceObjective = {
  public_id: string;
  code: string;
  name: string;
  service_code: string;
  indicator_type: string;
  target_value: string;
  warning_threshold: string;
  critical_threshold: string;
  window_days: number;
  unit_code: string;
};
export type HealthSnapshot = {
  public_id: string;
  environment: { public_id: string; code: string };
  service_code: string;
  status: string;
  latency_ms: number | null;
  checked_at: string;
};
export type Incident = {
  public_id: string;
  environment: { public_id: string; code: string };
  number: string;
  severity: string;
  title: string;
  status: string;
  customer_impact: string;
  postmortem_required: boolean;
  version: number;
};
export type Runbook = {
  public_id: string;
  code: string;
  title: string;
  category: string;
  purpose: string;
  steps: { order?: number; action?: string }[];
  review_due_at: string | null;
  is_active: boolean;
};
export type FeatureFlag = {
  public_id: string;
  code: string;
  name: string;
  description: string;
  is_enabled: boolean;
  rollout_percent: number;
  requires_approval: boolean;
  version: number;
};
export type MaintenanceWindow = {
  public_id: string;
  environment: { public_id: string; code: string };
  reference: string;
  title: string;
  starts_at: string;
  ends_at: string;
  status: string;
  affected_services: string[];
  version: number;
};

type Props = {
  company: Company;
  permissions: string[];
  initialSummary: AdminopsSummary | null;
  initialEnvironments: RuntimeEnvironment[];
  initialReleases: ReleaseRecord[];
  initialObjectives: ServiceObjective[];
  initialHealth: HealthSnapshot[];
  initialIncidents: Incident[];
  initialRunbooks: Runbook[];
  initialFlags: FeatureFlag[];
  initialMaintenance: MaintenanceWindow[];
};
type Tab = "releases" | "reliability" | "incidents" | "controls";
type ApiError = { message?: string; detail?: string };

async function api<T>(path: string, init?: RequestInit) {
  const response = await fetch(`/api/adminops/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = (await response.json().catch(() => ({}))) as T & ApiError;
  if (!response.ok) {
    throw new Error(body.message ?? body.detail ?? "Enterprise administration request failed.");
  }
  return body as T;
}

function Card({ label, value, note }: { label: string; value: number | string; note?: string }) {
  return (
    <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
      <p className="text-sm text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
      {note ? <p className="mt-2 text-xs text-[var(--muted)]">{note}</p> : null}
    </article>
  );
}

function Status({ value }: { value: string }) {
  return (
    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-slate-700">
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function EnterpriseAdminWorkspace({
  company,
  permissions,
  initialSummary,
  initialEnvironments,
  initialReleases,
  initialObjectives,
  initialHealth,
  initialIncidents,
  initialRunbooks,
  initialFlags,
  initialMaintenance,
}: Readonly<Props>) {
  const [tab, setTab] = useState<Tab>("releases");
  const [releases, setReleases] = useState(initialReleases);
  const [incidents, setIncidents] = useState(initialIncidents);
  const [flags, setFlags] = useState(initialFlags);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const summary = initialSummary ?? {
    active_environments: initialEnvironments.filter((item) => item.is_active).length,
    pending_releases: releases.filter((item) => ["draft", "validated", "approved"].includes(item.status)).length,
    failed_checks: releases.reduce((total, item) => total + item.readiness.failed_checks, 0),
    active_slos: initialObjectives.length,
    open_incidents: incidents.filter((item) => item.status !== "closed").length,
    enabled_flags: flags.filter((item) => item.is_enabled).length,
    planned_maintenance: initialMaintenance.filter((item) => ["planned", "approved"].includes(item.status)).length,
  };
  const latestHealth = useMemo(() => initialHealth.slice(0, 12), [initialHealth]);

  async function createRelease(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      const item = await api<ReleaseRecord>("releases", {
        method: "POST",
        body: JSON.stringify({
          environment_public_id: form.get("environment_public_id"),
          version_label: form.get("version_label"),
          release_name: form.get("release_name"),
          source_revision: form.get("source_revision"),
          artifact_sha256: form.get("artifact_sha256"),
          change_summary: form.get("change_summary"),
        }),
      });
      setReleases((current) => [item, ...current]);
      event.currentTarget.reset();
      setMessage("Release record created. Add critical checks before validation.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Release creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      const item = await api<Incident>("incidents", {
        method: "POST",
        body: JSON.stringify({
          environment_public_id: form.get("environment_public_id"),
          number: form.get("number"),
          severity: form.get("severity"),
          title: form.get("title"),
          summary: form.get("summary"),
          customer_impact: form.get("customer_impact"),
          postmortem_required: form.get("postmortem_required") === "on",
        }),
      });
      setIncidents((current) => [item, ...current]);
      event.currentTarget.reset();
      setMessage("Incident registered with audit and outbox evidence.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Incident creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleFlag(flag: FeatureFlag) {
    setBusy(true);
    setMessage("");
    try {
      const nextEnabled = !flag.is_enabled;
      const item = await api<FeatureFlag>(`flags/${flag.public_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          is_enabled: nextEnabled,
          rollout_percent: nextEnabled ? 100 : 0,
          expected_version: flag.version,
        }),
      });
      setFlags((current) => current.map((value) => (value.public_id === item.public_id ? item : value)));
      setMessage(`${item.name} is now ${item.is_enabled ? "enabled" : "disabled"}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Feature flag update failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
              MPSqre Build360 · Enterprise administration
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              Production readiness and reliability
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {company.display_name} · {company.code} · governed releases · SLOs · incidents
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <span className="rounded-full bg-emerald-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-emerald-900">
              Phase 12 active
            </span>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/platform">
              Platform
            </Link>
          </div>
        </header>

        <section className="grid gap-4 py-7 sm:grid-cols-2 lg:grid-cols-4">
          <Card label="Active environments" value={summary.active_environments} />
          <Card label="Pending releases" value={summary.pending_releases} note={`${summary.failed_checks} failed checks`} />
          <Card label="Open incidents" value={summary.open_incidents} />
          <Card label="Enabled flags" value={summary.enabled_flags} note={`${summary.planned_maintenance} maintenance windows`} />
        </section>

        <nav className="mb-6 flex flex-wrap gap-2">
          {(["releases", "reliability", "incidents", "controls"] as Tab[]).map((value) => (
            <button
              className={
                tab === value
                  ? "rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white"
                  : "rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold"
              }
              key={value}
              onClick={() => setTab(value)}
              type="button"
            >
              {value.charAt(0).toUpperCase() + value.slice(1)}
            </button>
          ))}
        </nav>

        {message ? <p className="mb-5 rounded-xl border border-[var(--border)] bg-white p-4 text-sm">{message}</p> : null}

        {tab === "releases" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            {permissions.includes("adminops.release.create") ? (
              <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createRelease}>
                <h2 className="text-xl font-semibold">Register release</h2>
                <div className="mt-5 grid gap-3">
                  <select className="rounded-lg border border-[var(--border)] p-3" name="environment_public_id" required>
                    <option value="">Select environment</option>
                    {initialEnvironments.filter((item) => item.is_active).map((item) => (
                      <option key={item.public_id} value={item.public_id}>{item.code} · {item.name}</option>
                    ))}
                  </select>
                  <input className="rounded-lg border border-[var(--border)] p-3" name="version_label" placeholder="Version, e.g. 0.12.1" required />
                  <input className="rounded-lg border border-[var(--border)] p-3" name="release_name" placeholder="Release name" required />
                  <input className="rounded-lg border border-[var(--border)] p-3" name="source_revision" placeholder="Git revision or build ID" required />
                  <input className="rounded-lg border border-[var(--border)] p-3" minLength={64} maxLength={64} name="artifact_sha256" placeholder="Artifact SHA-256" required />
                  <textarea className="rounded-lg border border-[var(--border)] p-3" name="change_summary" placeholder="Change summary" rows={4} />
                  <button className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">
                    Create governed release
                  </button>
                </div>
              </form>
            ) : null}
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Release register</h2>
              <div className="mt-5 grid gap-4">
                {releases.length ? releases.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">{item.version_label} · {item.release_name}</p>
                        <p className="mt-1 text-sm text-[var(--muted)]">{item.environment.code} · {item.source_revision}</p>
                      </div>
                      <Status value={item.status} />
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                      <div><p className="text-[var(--muted)]">Checks</p><p className="font-semibold">{item.readiness.total_checks}</p></div>
                      <div><p className="text-[var(--muted)]">Blocking</p><p className="font-semibold">{item.readiness.blocking_checks}</p></div>
                      <div><p className="text-[var(--muted)]">Readiness</p><p className="font-semibold">{item.readiness.ready ? "Ready" : "Not ready"}</p></div>
                    </div>
                  </div>
                )) : <p className="text-sm text-[var(--muted)]">No release records created.</p>}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "reliability" ? (
          <section className="grid gap-6 lg:grid-cols-2">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Service objectives</h2>
              <div className="mt-5 grid gap-3">
                {initialObjectives.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <p className="font-semibold">{item.name}</p>
                    <p className="mt-1 text-sm text-[var(--muted)]">{item.service_code} · {item.indicator_type}</p>
                    <p className="mt-2 text-sm">Target: <strong>{item.target_value} {item.unit_code}</strong> over {item.window_days} days</p>
                  </div>
                ))}
              </div>
            </article>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Latest health evidence</h2>
              <div className="mt-5 grid gap-3">
                {latestHealth.map((item) => (
                  <div className="flex items-center justify-between rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div><p className="font-semibold">{item.service_code}</p><p className="text-sm text-[var(--muted)]">{item.environment.code}</p></div>
                    <Status value={item.status} />
                  </div>
                ))}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "incidents" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            {permissions.includes("adminops.incident.create") ? (
              <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createIncident}>
                <h2 className="text-xl font-semibold">Register incident</h2>
                <div className="mt-5 grid gap-3">
                  <select className="rounded-lg border border-[var(--border)] p-3" name="environment_public_id" required>
                    <option value="">Select environment</option>
                    {initialEnvironments.map((item) => <option key={item.public_id} value={item.public_id}>{item.code}</option>)}
                  </select>
                  <input className="rounded-lg border border-[var(--border)] p-3" name="number" placeholder="Incident number" required />
                  <select className="rounded-lg border border-[var(--border)] p-3" name="severity" defaultValue="sev3">
                    <option value="sev1">SEV1 · Critical</option><option value="sev2">SEV2 · High</option><option value="sev3">SEV3 · Medium</option><option value="sev4">SEV4 · Low</option>
                  </select>
                  <input className="rounded-lg border border-[var(--border)] p-3" name="title" placeholder="Incident title" required />
                  <textarea className="rounded-lg border border-[var(--border)] p-3" name="summary" placeholder="Summary" rows={3} />
                  <textarea className="rounded-lg border border-[var(--border)] p-3" name="customer_impact" placeholder="Customer impact" rows={3} />
                  <label className="flex items-center gap-2 text-sm"><input name="postmortem_required" type="checkbox" /> Postmortem required</label>
                  <button className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Create incident</button>
                </div>
              </form>
            ) : null}
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Incident register</h2>
              <div className="mt-5 grid gap-3">
                {incidents.length ? incidents.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div className="flex flex-wrap justify-between gap-3"><div><p className="font-semibold">{item.number} · {item.title}</p><p className="mt-1 text-sm text-[var(--muted)]">{item.environment.code} · {item.severity.toUpperCase()}</p></div><Status value={item.status} /></div>
                    {item.customer_impact ? <p className="mt-3 text-sm">Impact: {item.customer_impact}</p> : null}
                  </div>
                )) : <p className="text-sm text-[var(--muted)]">No operational incidents recorded.</p>}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "controls" ? (
          <section className="grid gap-6 lg:grid-cols-2">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Feature flags</h2>
              <div className="mt-5 grid gap-3">
                {flags.map((item) => (
                  <div className="flex items-center justify-between gap-4 rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div><p className="font-semibold">{item.name}</p><p className="text-sm text-[var(--muted)]">{item.code} · {item.rollout_percent}% rollout</p></div>
                    {permissions.includes(item.is_enabled ? "adminops.feature_flag.manage" : "adminops.feature_flag.approve") ? (
                      <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} onClick={() => toggleFlag(item)} type="button">{item.is_enabled ? "Disable" : "Enable"}</button>
                    ) : <Status value={item.is_enabled ? "enabled" : "disabled"} />}
                  </div>
                ))}
              </div>
            </article>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Operational runbooks</h2>
              <div className="mt-5 grid gap-3">
                {initialRunbooks.map((item) => (
                  <details className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <summary className="cursor-pointer font-semibold">{item.code} · {item.title}</summary>
                    <p className="mt-3 text-sm text-[var(--muted)]">{item.purpose}</p>
                    <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm">{item.steps.map((step, index) => <li key={`${item.public_id}-${index}`}>{step.action ?? "Controlled step"}</li>)}</ol>
                  </details>
                ))}
              </div>
            </article>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm lg:col-span-2">
              <h2 className="text-xl font-semibold">Maintenance windows</h2>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {initialMaintenance.length ? initialMaintenance.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div className="flex justify-between gap-3"><div><p className="font-semibold">{item.reference} · {item.title}</p><p className="text-sm text-[var(--muted)]">{item.environment.code} · {item.affected_services.join(", ")}</p></div><Status value={item.status} /></div>
                  </div>
                )) : <p className="text-sm text-[var(--muted)]">No maintenance windows planned.</p>}
              </div>
            </article>
          </section>
        ) : null}
      </div>
    </main>
  );
}
