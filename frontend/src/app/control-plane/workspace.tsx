"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

export type OperatorProfile = {
  is_operator: boolean;
  user: { public_id: string; email: string; display_name: string };
  roles: { public_id: string; code: string; name: string }[];
  permissions: string[];
};

export type Plan = {
  public_id: string;
  code: string;
  version: number;
  name: string;
  status: string;
  entitlements: Record<string, boolean>;
  limits: Record<string, number | null>;
  effective_from: string;
  effective_to: string | null;
  published_at: string | null;
};

export type Subscription = {
  public_id: string;
  company_public_id: string;
  plan: Plan;
  status: string;
  starts_at: string;
  ends_at: string | null;
  grace_until: string | null;
};

export type UsageSnapshot = {
  public_id: string;
  tenant_public_id: string;
  company: { code: string; display_name: string };
  period_start: string;
  period_end: string;
  metrics: Record<string, number>;
  quota_status: Record<
    string,
    { used: number; limit: number | null; exceeded: boolean; utilization_percent: number | null }
  >;
  checksum_sha256: string;
  collected_at: string;
};

export type TenantAccount = {
  public_id: string;
  company: {
    public_id: string;
    code: string;
    legal_name: string;
    display_name: string;
    locale: string;
    timezone: string;
    currency: string;
    is_active: boolean;
  };
  lifecycle_status: string;
  onboarding_status: string;
  segment_code: string;
  deployment_region: string;
  data_residency: string;
  pilot_started_at: string | null;
  activated_at: string | null;
  grace_until: string | null;
  suspended_at: string | null;
  closed_at: string | null;
  lifecycle_reason: string;
  subscription: Subscription | null;
  latest_usage: UsageSnapshot | null;
  version: number;
};

export type SupportRequest = {
  public_id: string;
  tenant: { public_id: string; company_code: string; company_name: string };
  operator: { assignment_public_id: string; email: string; display_name: string };
  reason: string;
  scope_codes: string[];
  status: string;
  requested_at: string;
  expires_at: string;
  decided_at: string | null;
  decision_reason: string;
  version: number;
  access_token_issued: boolean;
};

export type ControlPlaneSummary = {
  total_tenants: number;
  active_tenants: number;
  suspended_tenants: number;
  active_subscriptions: number;
  quota_breaches: number;
  open_support_requests: number;
};

type Props = {
  operator: OperatorProfile;
  initialSummary: ControlPlaneSummary | null;
  initialTenants: TenantAccount[];
  initialPlans: Plan[];
  initialSubscriptions: Subscription[];
  initialUsage: UsageSnapshot[];
  initialSupportRequests: SupportRequest[];
};

type Tab = "tenants" | "plans" | "usage" | "support";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/control-plane/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = (await response.json().catch(() => ({}))) as {
    message?: string;
    detail?: string;
  };
  if (!response.ok) {
    throw new Error(body.message ?? body.detail ?? "Control-plane request failed.");
  }
  return body as T;
}

function Card({ label, value, note }: { label: string; value: number; note?: string }) {
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

export function ControlPlaneWorkspace({
  operator,
  initialSummary,
  initialTenants,
  initialPlans,
  initialSubscriptions,
  initialUsage,
  initialSupportRequests,
}: Readonly<Props>) {
  const [tab, setTab] = useState<Tab>("tenants");
  const [tenants, setTenants] = useState(initialTenants);
  const [subscriptions, setSubscriptions] = useState(initialSubscriptions);
  const [usage, setUsage] = useState(initialUsage);
  const [supportRequests, setSupportRequests] = useState(initialSupportRequests);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const publishedPlans = useMemo(
    () => initialPlans.filter((item) => item.status === "PUBLISHED"),
    [initialPlans],
  );
  const summary = initialSummary ?? {
    total_tenants: tenants.length,
    active_tenants: tenants.filter((item) => ["pilot", "active", "grace"].includes(item.lifecycle_status)).length,
    suspended_tenants: tenants.filter((item) => item.lifecycle_status === "suspended").length,
    active_subscriptions: subscriptions.filter((item) => ["TRIAL", "ACTIVE", "GRACE"].includes(item.status)).length,
    quota_breaches: usage.filter((item) => Object.values(item.quota_status).some((value) => value.exceeded)).length,
    open_support_requests: supportRequests.filter((item) => ["requested", "approved"].includes(item.status)).length,
  };

  async function transitionTenant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    setMessage("");
    const form = new FormData(formElement);
    const tenantPublicId = String(form.get("tenant_public_id"));
    const tenant = tenants.find((item) => item.public_id === tenantPublicId);
    if (!tenant) {
      setBusy(false);
      setMessage("Tenant was not found.");
      return;
    }
    const targetStatus = String(form.get("target_status"));
    try {
      const item = await api<TenantAccount>(`tenants/${tenantPublicId}/lifecycle`, {
        method: "POST",
        body: JSON.stringify({
          target_status: targetStatus,
          expected_version: tenant.version,
          reason: form.get("reason"),
          grace_until: targetStatus === "grace" ? form.get("grace_until") : null,
        }),
      });
      setTenants((current) => current.map((value) => (value.public_id === item.public_id ? item : value)));
      setMessage(`${item.company.display_name} is now ${item.lifecycle_status}.`);
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Tenant transition failed.");
    } finally {
      setBusy(false);
    }
  }

  async function assignPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    setMessage("");
    const form = new FormData(formElement);
    const tenantPublicId = String(form.get("tenant_public_id"));
    try {
      const item = await api<Subscription>(`tenants/${tenantPublicId}/subscription`, {
        method: "POST",
        body: JSON.stringify({
          plan_public_id: form.get("plan_public_id"),
          status: form.get("status"),
          starts_at: new Date().toISOString(),
          ends_at: null,
          grace_until: null,
          reason: form.get("reason"),
        }),
      });
      setSubscriptions((current) => [item, ...current]);
      setTenants((current) =>
        current.map((value) =>
          value.public_id === tenantPublicId ? { ...value, subscription: item } : value,
        ),
      );
      setMessage(`Assigned ${item.plan.code} v${item.plan.version}.`);
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Subscription assignment failed.");
    } finally {
      setBusy(false);
    }
  }

  async function collectUsage(tenant: TenantAccount) {
    setBusy(true);
    setMessage("");
    try {
      const item = await api<UsageSnapshot>(`tenants/${tenant.public_id}/usage/collect`, {
        method: "POST",
        body: "{}",
      });
      setUsage((current) => [item, ...current.filter((value) => value.public_id !== item.public_id)]);
      setTenants((current) =>
        current.map((value) =>
          value.public_id === tenant.public_id ? { ...value, latest_usage: item } : value,
        ),
      );
      setMessage(`Usage evidence collected for ${tenant.company.display_name}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Usage collection failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createSupportRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    setMessage("");
    const form = new FormData(formElement);
    try {
      const item = await api<SupportRequest>("support-requests", {
        method: "POST",
        body: JSON.stringify({
          tenant_public_id: form.get("tenant_public_id"),
          reason: form.get("reason"),
          scope_codes: form.getAll("scope_codes"),
          duration_hours: Number(form.get("duration_hours")),
        }),
      });
      setSupportRequests((current) => [item, ...current]);
      setMessage("Support access request created. Tenant approval remains mandatory.");
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Support request failed.");
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
              MPSqre Build360 · SaaS control plane
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              Tenant lifecycle and subscription operations
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {operator.user.display_name} · platform operator · cross-tenant governance
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <span className="rounded-full bg-emerald-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-emerald-900">
              Phase 13 active
            </span>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/platform">
              Platform
            </Link>
          </div>
        </header>

        <section className="grid gap-4 py-7 sm:grid-cols-2 xl:grid-cols-4">
          <Card label="Tenant accounts" value={summary.total_tenants} note={`${summary.active_tenants} active`} />
          <Card label="Active subscriptions" value={summary.active_subscriptions} />
          <Card label="Quota breaches" value={summary.quota_breaches} note="Latest evidence" />
          <Card label="Support requests" value={summary.open_support_requests} note={`${summary.suspended_tenants} suspended tenants`} />
        </section>

        <nav className="mb-6 flex flex-wrap gap-2">
          {(["tenants", "plans", "usage", "support"] as Tab[]).map((value) => (
            <button
              className={tab === value ? "rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" : "rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold"}
              key={value}
              onClick={() => setTab(value)}
              type="button"
            >
              {value.charAt(0).toUpperCase() + value.slice(1)}
            </button>
          ))}
        </nav>

        {message ? <p className="mb-5 rounded-xl border border-[var(--border)] bg-white p-4 text-sm">{message}</p> : null}

        {tab === "tenants" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            {operator.permissions.includes("controlplane.tenant.manage") ? (
              <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={transitionTenant}>
                <h2 className="text-xl font-semibold">Change tenant lifecycle</h2>
                <div className="mt-5 grid gap-3">
                  <select className="rounded-lg border border-[var(--border)] p-3" name="tenant_public_id" required>
                    <option value="">Select tenant</option>
                    {tenants.map((item) => <option key={item.public_id} value={item.public_id}>{item.company.code} · {item.company.display_name}</option>)}
                  </select>
                  <select className="rounded-lg border border-[var(--border)] p-3" name="target_status" required>
                    <option value="active">Active</option>
                    <option value="grace">Grace</option>
                    <option value="suspended">Suspended</option>
                    <option value="closed">Closed</option>
                  </select>
                  <input className="rounded-lg border border-[var(--border)] p-3" name="grace_until" type="datetime-local" />
                  <textarea className="rounded-lg border border-[var(--border)] p-3" name="reason" placeholder="Governance reason" required rows={4} />
                  <button className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Apply controlled transition</button>
                </div>
              </form>
            ) : null}
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Tenant register</h2>
              <div className="mt-5 grid gap-4">
                {tenants.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">{item.company.display_name}</p>
                        <p className="mt-1 text-sm text-[var(--muted)]">{item.company.code} · {item.deployment_region || "region pending"} · {item.company.currency}</p>
                      </div>
                      <Status value={item.lifecycle_status} />
                    </div>
                    <p className="mt-3 text-sm">Plan: <strong>{item.subscription ? `${item.subscription.plan.code} v${item.subscription.plan.version}` : "No active plan"}</strong></p>
                    <p className="mt-1 text-xs text-[var(--muted)]">Onboarding: {item.onboarding_status.replaceAll("_", " ")} · record v{item.version}</p>
                  </div>
                ))}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "plans" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            {operator.permissions.includes("controlplane.subscription.manage") ? (
              <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={assignPlan}>
                <h2 className="text-xl font-semibold">Assign subscription</h2>
                <div className="mt-5 grid gap-3">
                  <select className="rounded-lg border border-[var(--border)] p-3" name="tenant_public_id" required>
                    <option value="">Select tenant</option>
                    {tenants.map((item) => <option key={item.public_id} value={item.public_id}>{item.company.code} · {item.company.display_name}</option>)}
                  </select>
                  <select className="rounded-lg border border-[var(--border)] p-3" name="plan_public_id" required>
                    <option value="">Select published plan</option>
                    {publishedPlans.map((item) => <option key={item.public_id} value={item.public_id}>{item.code} v{item.version} · {item.name}</option>)}
                  </select>
                  <select className="rounded-lg border border-[var(--border)] p-3" defaultValue="ACTIVE" name="status">
                    <option value="TRIAL">Trial</option>
                    <option value="ACTIVE">Active</option>
                  </select>
                  <textarea className="rounded-lg border border-[var(--border)] p-3" name="reason" placeholder="Commercial or pilot reason" required rows={4} />
                  <button className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Assign plan</button>
                </div>
              </form>
            ) : null}
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Published plan catalogue</h2>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                {initialPlans.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div className="flex items-start justify-between gap-3"><p className="font-semibold">{item.name}</p><Status value={item.status} /></div>
                    <p className="mt-1 text-sm text-[var(--muted)]">{item.code} v{item.version}</p>
                    <p className="mt-3 text-sm">{Object.values(item.entitlements).filter(Boolean).length} enabled entitlements</p>
                    <p className="mt-1 text-xs text-[var(--muted)]">Limits: {Object.keys(item.limits).length}</p>
                  </div>
                ))}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "usage" ? (
          <section className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">Usage and quota evidence</h2><span className="text-sm text-[var(--muted)]">Checksummed monthly snapshots</span></div>
            <div className="mt-5 grid gap-4">
              {tenants.map((tenant) => {
                const snapshot = usage.find((item) => item.tenant_public_id === tenant.public_id) ?? tenant.latest_usage;
                return (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={tenant.public_id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div><p className="font-semibold">{tenant.company.display_name}</p><p className="mt-1 text-sm text-[var(--muted)]">{snapshot ? `${snapshot.period_start} → ${snapshot.period_end}` : "No usage evidence"}</p></div>
                      {operator.permissions.includes("controlplane.usage.collect") ? <button className="rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm font-semibold disabled:opacity-50" disabled={busy} onClick={() => collectUsage(tenant)} type="button">Collect now</button> : null}
                    </div>
                    {snapshot ? <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(snapshot.quota_status).map(([code, value]) => <div className={value.exceeded ? "rounded-lg border border-red-200 bg-red-50 p-3" : "rounded-lg bg-slate-50 p-3"} key={code}><p className="text-xs uppercase tracking-wide text-[var(--muted)]">{code.replaceAll("_", " ")}</p><p className="mt-1 font-semibold">{value.used}{value.limit === null ? " / unlimited" : ` / ${value.limit}`}</p></div>)}</div> : null}
                  </div>
                );
              })}
            </div>
          </section>
        ) : null}

        {tab === "support" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            {operator.permissions.includes("controlplane.support.request") ? (
              <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createSupportRequest}>
                <h2 className="text-xl font-semibold">Request support access</h2>
                <p className="mt-2 text-sm text-[var(--muted)]">Creates approval evidence only. Build360 does not mint an impersonation token.</p>
                <div className="mt-5 grid gap-3">
                  <select className="rounded-lg border border-[var(--border)] p-3" name="tenant_public_id" required><option value="">Select tenant</option>{tenants.map((item) => <option key={item.public_id} value={item.public_id}>{item.company.code} · {item.company.display_name}</option>)}</select>
                  <label className="flex gap-2 text-sm"><input name="scope_codes" type="checkbox" value="tenant.diagnostics" />Diagnostics</label>
                  <label className="flex gap-2 text-sm"><input name="scope_codes" type="checkbox" value="tenant.audit" />Audit evidence</label>
                  <label className="flex gap-2 text-sm"><input name="scope_codes" type="checkbox" value="tenant.read_only" />Read-only records</label>
                  <input className="rounded-lg border border-[var(--border)] p-3" defaultValue={4} max={24} min={1} name="duration_hours" type="number" />
                  <textarea className="rounded-lg border border-[var(--border)] p-3" name="reason" placeholder="Specific diagnostic reason" required rows={4} />
                  <button className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Create approval request</button>
                </div>
              </form>
            ) : null}
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Support-access register</h2>
              <div className="mt-5 grid gap-4">
                {supportRequests.length ? supportRequests.map((item) => <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold">{item.tenant.company_name}</p><p className="mt-1 text-sm text-[var(--muted)]">{item.operator.email} · expires {new Date(item.expires_at).toLocaleString()}</p></div><Status value={item.status} /></div><p className="mt-3 text-sm">{item.reason}</p><p className="mt-2 text-xs text-[var(--muted)]">{item.scope_codes.join(" · ")} · token issued: {String(item.access_token_issued)}</p></div>) : <p className="text-sm text-[var(--muted)]">No governed support requests.</p>}
              </div>
            </article>
          </section>
        ) : null}
      </div>
    </main>
  );
}
