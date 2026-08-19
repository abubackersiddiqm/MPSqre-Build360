"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

export type Company = {
  public_id: string;
  code: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
};
export type CommunicationSummary = {
  policies: number;
  enabled_channels: number;
  active_providers: number;
  published_templates: number;
  queued: number;
  sent: number;
  delivered: number;
  failed: number;
  suppressed: number;
  inbound_review: number;
};
export type NotificationSummary = {
  total: number;
  unread: number;
  critical_unread: number;
  preferences: number;
  active_rules: number;
  delivery_failures: number;
  delivery_suppressed: number;
};
export type ChannelPolicy = {
  public_id: string;
  channel: string;
  is_enabled: boolean;
  consent_required: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  timezone: string;
  retry_limit: number;
  max_daily_per_subject: number;
  version: number;
};
export type Provider = {
  public_id: string;
  channel: string;
  code: string;
  display_name: string;
  adapter_code: string;
  priority: number;
  is_active: boolean;
};
export type Template = {
  public_id: string;
  code: string;
  name: string;
  channel: string;
  locale: string;
  version: number;
  status: string;
  subject_template: string;
  body_template: string;
  variable_names: string[];
  purpose_code: string;
};
export type CommunicationRequest = {
  public_id: string;
  channel: string;
  template: { public_id: string; code: string; name: string; version: number };
  provider: { public_id: string; code: string; display_name: string } | null;
  status: string;
  rendered_subject: string;
  rendered_body: string;
  scheduled_for: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  suppression_reason: string;
  attempt_count: number;
  version: number;
  created_at: string;
};
export type Notification = {
  public_id: string;
  event_code: string;
  title: string;
  body: string;
  severity: string;
  action_path: string;
  read_at: string | null;
  created_at: string;
  deliveries: { channel: string; status: string; failure_code: string; delivered_at: string | null }[];
};
export type Preference = {
  public_id: string;
  event_code: string;
  channel: string;
  enabled: boolean;
  digest_mode: string;
  version: number;
};
export type NotificationRule = {
  public_id: string;
  event_code: string;
  name: string;
  severity: string;
  channels: string[];
  is_active: boolean;
  version: number;
};

type Props = {
  company: Company;
  permissions: string[];
  initialCommunicationSummary: CommunicationSummary | null;
  initialNotificationSummary: NotificationSummary | null;
  initialPolicies: ChannelPolicy[];
  initialProviders: Provider[];
  initialTemplates: Template[];
  initialRequests: CommunicationRequest[];
  initialNotifications: Notification[];
  initialPreferences: Preference[];
  initialRules: NotificationRule[];
};
type ApiError = { message?: string; detail?: string };

async function api<T>(scope: "communications" | "notifications", path: string, init?: RequestInit) {
  const response = await fetch(`/api/${scope}/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = (await response.json().catch(() => ({}))) as T & ApiError;
  if (!response.ok) {
    throw new Error(body.message ?? body.detail ?? "The communication operation could not be completed.");
  }
  return body as T;
}

function Card({ label, value }: { label: string; value: string | number }) {
  return (
    <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
      <p className="text-sm text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
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

export function CommunicationWorkspace(props: Readonly<Props>) {
  const { company, permissions } = props;
  const [tab, setTab] = useState<"inbox" | "requests" | "templates" | "controls">("inbox");
  const [communicationSummary, setCommunicationSummary] = useState(
    props.initialCommunicationSummary ?? {
      policies: 0,
      enabled_channels: 0,
      active_providers: 0,
      published_templates: 0,
      queued: 0,
      sent: 0,
      delivered: 0,
      failed: 0,
      suppressed: 0,
      inbound_review: 0,
    },
  );
  const [notificationSummary, setNotificationSummary] = useState(
    props.initialNotificationSummary ?? {
      total: 0,
      unread: 0,
      critical_unread: 0,
      preferences: 0,
      active_rules: 0,
      delivery_failures: 0,
      delivery_suppressed: 0,
    },
  );
  const [policies, setPolicies] = useState(props.initialPolicies);
  const [providers, setProviders] = useState(props.initialProviders);
  const [templates, setTemplates] = useState(props.initialTemplates);
  const [requests, setRequests] = useState(props.initialRequests);
  const [notifications, setNotifications] = useState(props.initialNotifications);
  const [preferences, setPreferences] = useState(props.initialPreferences);
  const [rules, setRules] = useState(props.initialRules);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refresh() {
    const [cs, ns, p, pr, t, r, n, pref, rule] = await Promise.all([
      api<CommunicationSummary>("communications", "summary"),
      api<NotificationSummary>("notifications", "summary"),
      api<{ items: ChannelPolicy[] }>("communications", "policies"),
      api<{ items: Provider[] }>("communications", "providers"),
      api<{ items: Template[] }>("communications", "templates"),
      api<{ items: CommunicationRequest[] }>("communications", "requests"),
      api<{ items: Notification[] }>("notifications", "items"),
      api<{ items: Preference[] }>("notifications", "preferences"),
      api<{ items: NotificationRule[] }>("notifications", "rules"),
    ]);
    setCommunicationSummary(cs);
    setNotificationSummary(ns);
    setPolicies(p.items);
    setProviders(pr.items);
    setTemplates(t.items);
    setRequests(r.items);
    setNotifications(n.items);
    setPreferences(pref.items);
    setRules(rule.items);
  }

  async function run(action: () => Promise<void>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh();
      setNotice(message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The communication operation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createNotification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api("notifications", "items", {
        method: "POST",
        body: JSON.stringify({
          event_code: form.get("event_code"),
          title: form.get("title"),
          body: form.get("body"),
          severity: form.get("severity"),
          action_path: form.get("action_path"),
          route_external: form.get("route_external") === "on",
        }),
      });
      event.currentTarget.reset();
    }, "Notification created through the governed routing layer.");
  }

  async function markRead(publicId: string) {
    await run(
      async () => {
        await api("notifications", `items/${publicId}/read`, { method: "POST", body: "{}" });
      },
      "Notification marked as read.",
    );
  }

  async function markAllRead() {
    await run(
      async () => {
        await api("notifications", "items/read-all", { method: "POST", body: "{}" });
      },
      "All visible notifications marked as read.",
    );
  }

  async function createTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api("communications", "templates", {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          name: form.get("name"),
          channel: form.get("channel"),
          locale: company.locale,
          subject_template: form.get("subject_template"),
          body_template: form.get("body_template"),
          variable_names: String(form.get("variable_names") ?? "")
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
          purpose_code: form.get("purpose_code"),
        }),
      });
      event.currentTarget.reset();
    }, "Draft communication template created.");
  }

  async function publishTemplate(publicId: string) {
    await run(
      async () => {
        await api("communications", `templates/${publicId}/publish`, { method: "POST", body: "{}" });
      },
      "Template published as an immutable active version.",
    );
  }

  async function createRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api("communications", "requests", {
        method: "POST",
        body: JSON.stringify({
          template_public_id: form.get("template_public_id"),
          template_variables: {
            title: form.get("title"),
            body: form.get("body"),
            company_name: company.display_name,
          },
          idempotency_key: crypto.randomUUID(),
        }),
      });
      event.currentTarget.reset();
    }, "Communication request created with consent and policy evaluation.");
  }

  async function dispatchRequest(publicId: string) {
    await run(
      async () => {
        await api("communications", `requests/${publicId}/dispatch`, { method: "POST", body: "{}" });
      },
      "Communication request dispatched through its provider adapter.",
    );
  }

  async function updatePolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const current = policies.find((item) => item.channel === form.get("channel"));
    await run(async () => {
      await api("communications", "policies", {
        method: "PATCH",
        body: JSON.stringify({
          channel: form.get("channel"),
          is_enabled: form.get("is_enabled") === "on",
          consent_required: form.get("consent_required") === "on",
          timezone: company.timezone,
          expected_version: current?.version,
        }),
      });
    }, "Channel policy updated with optimistic concurrency.");
  }

  async function updatePreference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const eventCode = String(form.get("event_code") ?? "").trim();
    const channel = String(form.get("channel") ?? "in_app");
    const current = preferences.find((item) => item.event_code === eventCode && item.channel === channel);
    await run(async () => {
      await api("notifications", "preferences", {
        method: "PATCH",
        body: JSON.stringify({
          event_code: eventCode,
          channel,
          enabled: form.get("enabled") === "on",
          digest_mode: form.get("digest_mode"),
          expected_version: current?.version,
        }),
      });
    }, "Notification preference updated.");
  }

  const input = "rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm";
  const publishedTemplates = templates.filter((item) => item.status === "published");

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">MPSqre Build360</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Communications and notifications</h1>
            <p className="mt-2 text-sm text-[var(--muted)]">{company.display_name} · consent-aware · provider-neutral · auditable</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <span className="rounded-full bg-emerald-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-emerald-900">Phase 9 active</span>
            <Link href="/platform" className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold">Platform</Link>
          </div>
        </header>

        <section className="grid gap-4 py-7 sm:grid-cols-2 xl:grid-cols-4">
          <Card label="Unread notifications" value={notificationSummary.unread} />
          <Card label="Published templates" value={communicationSummary.published_templates} />
          <Card label="Delivered communications" value={communicationSummary.delivered} />
          <Card label="Suppressed by policy" value={communicationSummary.suppressed} />
        </section>

        <nav className="mb-6 flex flex-wrap gap-2" aria-label="Communication workspace tabs">
          {(["inbox", "requests", "templates", "controls"] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setTab(item)}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === item ? "bg-[var(--brand)] text-white" : "border border-[var(--border)] bg-white"}`}
            >
              {item.charAt(0).toUpperCase() + item.slice(1)}
            </button>
          ))}
        </nav>

        {error ? <p className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</p> : null}
        {notice ? <p className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</p> : null}

        {tab === "inbox" ? (
          <section className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-xl font-semibold">Notification inbox</h2>
                {permissions.includes("notification.mark_read") ? (
                  <button disabled={busy} onClick={markAllRead} className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold">Mark all read</button>
                ) : null}
              </div>
              <div className="mt-5 grid gap-3">
                {notifications.length ? notifications.map((item) => (
                  <article key={item.public_id} className={`rounded-xl border p-4 ${item.read_at ? "border-[var(--border)]" : "border-emerald-300 bg-emerald-50/40"}`}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">{item.title}</p>
                        <p className="mt-1 text-xs uppercase tracking-wide text-[var(--muted)]">{item.event_code} · {item.severity}</p>
                      </div>
                      {!item.read_at && permissions.includes("notification.mark_read") ? (
                        <button disabled={busy} onClick={() => markRead(item.public_id)} className="text-sm font-semibold text-[var(--brand)]">Mark read</button>
                      ) : <Status value={item.read_at ? "read" : "unread"} />}
                    </div>
                    <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{item.body}</p>
                    <div className="mt-3 flex flex-wrap gap-2">{item.deliveries.map((delivery) => <span key={delivery.channel} className="text-xs text-[var(--muted)]">{delivery.channel}: {delivery.status}</span>)}</div>
                  </article>
                )) : <p className="text-sm text-[var(--muted)]">No notifications are visible to this user.</p>}
              </div>
            </article>

            {permissions.includes("notification.create") ? (
              <form onSubmit={createNotification} className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold">Create notification</h2>
                <div className="mt-5 grid gap-3">
                  <input className={input} name="event_code" placeholder="event.code" required />
                  <input className={input} name="title" placeholder="Title" required />
                  <textarea className={input} name="body" placeholder="Notification body" rows={5} required />
                  <select className={input} name="severity" defaultValue="info"><option value="info">Information</option><option value="success">Success</option><option value="warning">Warning</option><option value="critical">Critical</option></select>
                  <input className={input} name="action_path" placeholder="/optional-action" />
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="route_external" /> Route configured external channels</label>
                  <button disabled={busy} className="rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white">Create notification</button>
                </div>
              </form>
            ) : null}
          </section>
        ) : null}

        {tab === "requests" ? (
          <section className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Communication requests</h2>
              <div className="mt-5 grid gap-3">
                {requests.length ? requests.map((item) => (
                  <article key={item.public_id} className="rounded-xl border border-[var(--border)] p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold">{item.rendered_subject || item.template.name}</p><p className="mt-1 text-xs text-[var(--muted)]">{item.template.code} v{item.template.version} · {item.channel} · attempts {item.attempt_count}</p></div><Status value={item.status} /></div>
                    <p className="mt-3 line-clamp-3 text-sm text-[var(--muted)]">{item.rendered_body}</p>
                    {item.suppression_reason ? <p className="mt-2 text-xs text-amber-700">Policy result: {item.suppression_reason}</p> : null}
                    {["queued", "failed"].includes(item.status) && permissions.includes("communication.request.dispatch") ? <button disabled={busy} onClick={() => dispatchRequest(item.public_id)} className="mt-3 text-sm font-semibold text-[var(--brand)]">Dispatch</button> : null}
                  </article>
                )) : <p className="text-sm text-[var(--muted)]">No communication requests have been created.</p>}
              </div>
            </article>

            {permissions.includes("communication.request.create") ? (
              <form onSubmit={createRequest} className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold">Create request</h2>
                <div className="mt-5 grid gap-3">
                  <select className={input} name="template_public_id" required defaultValue=""><option value="" disabled>Select published template</option>{publishedTemplates.map((item) => <option key={item.public_id} value={item.public_id}>{item.name} · {item.channel}</option>)}</select>
                  <input className={input} name="title" placeholder="Rendered title" required />
                  <textarea className={input} name="body" placeholder="Rendered body" rows={5} required />
                  <button disabled={busy || !publishedTemplates.length} className="rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white">Evaluate and queue</button>
                </div>
              </form>
            ) : null}
          </section>
        ) : null}

        {tab === "templates" ? (
          <section className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Versioned templates</h2>
              <div className="mt-5 grid gap-3">
                {templates.map((item) => (
                  <article key={item.public_id} className="rounded-xl border border-[var(--border)] p-4">
                    <div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{item.name}</p><p className="mt-1 text-xs text-[var(--muted)]">{item.code} · {item.channel} · {item.locale} · v{item.version}</p></div><Status value={item.status} /></div>
                    <p className="mt-3 text-sm text-[var(--muted)]">{item.body_template}</p>
                    {item.status === "draft" && permissions.includes("communication.template.publish") ? <button disabled={busy} onClick={() => publishTemplate(item.public_id)} className="mt-3 text-sm font-semibold text-[var(--brand)]">Publish version</button> : null}
                  </article>
                ))}
              </div>
            </article>

            {permissions.includes("communication.template.manage") ? (
              <form onSubmit={createTemplate} className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold">Create template version</h2>
                <div className="mt-5 grid gap-3">
                  <input className={input} name="code" placeholder="SYSTEM.ALERT" required />
                  <input className={input} name="name" placeholder="Template name" required />
                  <select className={input} name="channel" defaultValue="in_app"><option value="in_app">In-app</option><option value="email">Email</option><option value="sms">SMS</option><option value="whatsapp">WhatsApp</option><option value="voice">Voice</option></select>
                  <input className={input} name="subject_template" placeholder="{title}" defaultValue="{title}" />
                  <textarea className={input} name="body_template" placeholder="{body}" defaultValue="{body}" rows={4} required />
                  <input className={input} name="variable_names" placeholder="title, body, company_name" defaultValue="title, body, company_name" />
                  <input className={input} name="purpose_code" placeholder="service_alert" required />
                  <button disabled={busy} className="rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white">Create draft</button>
                </div>
              </form>
            ) : null}
          </section>
        ) : null}

        {tab === "controls" ? (
          <section className="grid gap-6 lg:grid-cols-2">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Channel governance</h2>
              <div className="mt-5 grid gap-4">
                {policies.map((item) => (
                  <form key={item.public_id} onSubmit={updatePolicy} className="rounded-xl border border-[var(--border)] p-4">
                    <input type="hidden" name="channel" value={item.channel} />
                    <div className="flex items-center justify-between"><div><p className="font-semibold">{item.channel.replaceAll("_", " ")}</p><p className="text-xs text-[var(--muted)]">{item.timezone} · retry {item.retry_limit} · limit {item.max_daily_per_subject}/day</p></div><span className="text-xs">v{item.version}</span></div>
                    <div className="mt-3 flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><input type="checkbox" name="is_enabled" defaultChecked={item.is_enabled} /> Enabled</label><label className="flex items-center gap-2"><input type="checkbox" name="consent_required" defaultChecked={item.consent_required} /> Consent required</label></div>
                    {permissions.includes("communication.policy.manage") ? <button disabled={busy} className="mt-3 text-sm font-semibold text-[var(--brand)]">Save policy</button> : null}
                  </form>
                ))}
              </div>
              <h3 className="mt-7 font-semibold">Provider configurations</h3>
              <ul className="mt-3 grid gap-2">{providers.map((item) => <li key={item.public_id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"><span>{item.display_name} · {item.channel}</span><Status value={item.is_active ? "active" : "inactive"} /></li>)}</ul>
            </article>

            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Notification preferences</h2>
              {permissions.includes("notification.preference.manage") ? (
                <form onSubmit={updatePreference} className="mt-5 grid gap-3">
                  <input className={input} name="event_code" placeholder="event.code" required />
                  <select className={input} name="channel" defaultValue="in_app"><option value="in_app">In-app</option><option value="email">Email</option><option value="sms">SMS</option><option value="whatsapp">WhatsApp</option><option value="voice">Voice</option></select>
                  <select className={input} name="digest_mode" defaultValue="immediate"><option value="immediate">Immediate</option><option value="daily">Daily digest</option><option value="weekly">Weekly digest</option><option value="muted">Muted</option></select>
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="enabled" defaultChecked /> Enabled</label>
                  <button disabled={busy} className="rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white">Save preference</button>
                </form>
              ) : null}
              <div className="mt-6 grid gap-2">{preferences.map((item) => <div key={item.public_id} className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-2 text-sm"><span>{item.event_code} · {item.channel}</span><Status value={item.enabled ? item.digest_mode : "disabled"} /></div>)}</div>
              <h3 className="mt-7 font-semibold">Active routing rules</h3>
              <div className="mt-3 grid gap-2">{rules.map((item) => <div key={item.public_id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm"><p className="font-medium">{item.name}</p><p className="text-xs text-[var(--muted)]">{item.event_code} · {item.channels.join(", ")} · {item.severity}</p></div>)}</div>
            </article>
          </section>
        ) : null}
      </div>
    </main>
  );
}
