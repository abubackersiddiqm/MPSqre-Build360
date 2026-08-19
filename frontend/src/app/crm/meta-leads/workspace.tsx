"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

export type MetaConnector = {
  public_id: string;
  code: string;
  name: string;
  status: string;
  health_status: string;
  page_id: string;
  page_name: string;
  lead_form_ids: string[];
  graph_api_version: string;
  default_owner_membership_public_id: string;
  mapping_code: string;
  verify_token_last_four: string;
  has_secret_reference: boolean;
  webhook_path: string;
  version: number;
  webhook_verify_token?: string;
  verify_token_shown_once?: boolean;
};

type MetaReceipt = {
  public_id: string;
  connector_public_id: string;
  external_lead_id: string;
  page_id: string;
  form_id: string;
  campaign_id: string;
  adset_id: string;
  ad_id: string;
  source_created_at: string | null;
  field_names: string[];
  status: string;
  contact_public_id: string | null;
  lead_public_id: string | null;
  attempt_count: number;
  last_attempt_at: string | null;
  processed_at: string | null;
  error_summary: string;
  created_at: string;
};

type Owner = {
  membership_public_id: string;
  user_public_id: string;
  display_name: string;
  email: string;
};

export type MetaLeadOverview = {
  connectors: MetaConnector[];
  receipts: MetaReceipt[];
  owners: Owner[];
};

type ErrorEnvelope = { message?: string; detail?: string; field_errors?: Record<string, string[]> };

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/integrations/${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as ErrorEnvelope;
    const field = Object.entries(body.field_errors ?? {}).flatMap(([key, values]) => values.map((value) => `${key}: ${value}`)).join(" ");
    throw new Error(field || body.message || body.detail || `Request failed (${response.status})`);
  }
  return await response.json() as T;
}

const statusStyle: Record<string, string> = {
  ACTIVE: "bg-emerald-50 text-emerald-800",
  PROCESSED: "bg-emerald-50 text-emerald-800",
  DUPLICATE: "bg-blue-50 text-blue-800",
  RECEIVED: "bg-amber-50 text-amber-900",
  PROCESSING: "bg-amber-50 text-amber-900",
  FAILED: "bg-red-50 text-red-800",
  SUSPENDED: "bg-slate-100 text-slate-700",
  DRAFT: "bg-slate-100 text-slate-700",
};

export function MetaLeadsWorkspace({ initial, permissions }: Readonly<{ initial: MetaLeadOverview; permissions: string[] }>) {
  const [data, setData] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [oneTimeToken, setOneTimeToken] = useState("");
  const canManage = permissions.includes("integration.meta_leads.manage");
  const canRetry = permissions.includes("integration.meta_leads.retry");

  async function refresh() {
    const next = await api<MetaLeadOverview>("meta-leads");
    setData(next);
  }

  async function createConnector(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setMessage(""); setError(""); setOneTimeToken("");
    const form = new FormData(event.currentTarget);
    try {
      const created = await api<MetaConnector>("meta-leads", {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          name: form.get("name"),
          page_id: form.get("page_id"),
          page_name: form.get("page_name"),
          lead_form_ids: String(form.get("lead_form_ids") || "").split(",").map((value) => value.trim()).filter(Boolean),
          graph_api_version: form.get("graph_api_version"),
          default_owner_membership_public_id: form.get("default_owner_membership_public_id"),
          secret_ref: form.get("secret_ref"),
        }),
      });
      setOneTimeToken(created.webhook_verify_token ?? "");
      setMessage("Meta Lead Ads connector created. Copy the webhook verification token now; Build360 stores only its digest.");
      (event.currentTarget as HTMLFormElement).reset();
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Meta connector could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function status(connector: MetaConnector, target_status: "ACTIVE" | "SUSPENDED") {
    setBusy(true); setMessage(""); setError("");
    try {
      await api(`meta-leads/${connector.public_id}/status`, {
        method: "POST",
        body: JSON.stringify({ expected_version: connector.version, target_status }),
      });
      setMessage(`Connector ${target_status.toLowerCase()}.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Connector status could not be changed.");
    } finally { setBusy(false); }
  }

  async function test(connector: MetaConnector) {
    setBusy(true); setMessage(""); setError("");
    try {
      const result = await api<{ ok: boolean; page_id: string; page_name: string }>(`meta-leads/${connector.public_id}/test`, {
        method: "POST",
        body: JSON.stringify({ expected_version: connector.version }),
      });
      setMessage(`Meta connection succeeded for ${result.page_name || result.page_id}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Meta connection test failed.");
    } finally { setBusy(false); }
  }

  async function rotate(connector: MetaConnector) {
    setBusy(true); setMessage(""); setError(""); setOneTimeToken("");
    try {
      const updated = await api<MetaConnector>(`meta-leads/${connector.public_id}/rotate-verify-token`, {
        method: "POST",
        body: JSON.stringify({ expected_version: connector.version }),
      });
      setOneTimeToken(updated.webhook_verify_token ?? "");
      setMessage("Webhook verification token rotated. Update the Meta webhook subscription with the new token.");
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Verification token could not be rotated.");
    } finally { setBusy(false); }
  }

  async function retry(receipt: MetaReceipt) {
    setBusy(true); setMessage(""); setError("");
    try {
      const result = await api<MetaReceipt>(`meta-leads/receipts/${receipt.public_id}/retry`, { method: "POST", body: "{}" });
      setMessage(`Receipt ${result.external_lead_id} is now ${result.status}.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Receipt retry failed.");
    } finally { setBusy(false); }
  }

  return (
    <main className="min-h-screen bg-[var(--background)] px-4 py-6 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1500px] space-y-6">
        <header className="rounded-[30px] border border-[var(--border)] bg-white p-6 shadow-sm lg:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[.2em] text-[var(--brand)]">CRM · Meta Lead Ads</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">Meta Ads → People → Call next action.</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">
                Facebook and Instagram form submissions are saved into People first. Build360 detects the Meta platform, keeps protected contact details governed, creates a Call next action, and never creates a sales Lead automatically. Raw Meta credentials are never returned to the browser.
              </p>
            </div>
            <Link className="rounded-xl border border-[var(--border)] bg-white px-4 py-2.5 text-sm font-semibold" href="/crm?tab=people">← Back to People</Link>
          </div>
        </header>

        {message ? <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-900">{message}</div> : null}
        {error ? <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-900">{error}</div> : null}
        {oneTimeToken ? <div className="rounded-[24px] border border-amber-300 bg-amber-50 p-5"><p className="text-xs font-bold uppercase tracking-[.14em] text-amber-900">Copy now — shown once</p><code className="mt-3 block break-all rounded-xl bg-white p-4 text-sm">{oneTimeToken}</code><p className="mt-2 text-xs text-amber-900">Use this as the webhook verification token. Build360 stores only its SHA-256 digest.</p></div> : null}

        {canManage ? (
          <section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold">Connect a Meta Page / Lead Form</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">The secret reference must be an <code>env://</code> variable whose backend value is JSON containing <code>page_access_token</code> and <code>app_secret</code>.</p>
            <form className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4" onSubmit={createConnector}>
              <label className="text-sm font-medium">Connector code<input className="mt-1 w-full rounded-xl border border-[var(--border)] p-3" name="code" placeholder="META_LEADS_MAIN" required /></label>
              <label className="text-sm font-medium">Name<input className="mt-1 w-full rounded-xl border border-[var(--border)] p-3" name="name" placeholder="Main Meta Lead Ads" required /></label>
              <label className="text-sm font-medium">Page ID<input className="mt-1 w-full rounded-xl border border-[var(--border)] p-3" name="page_id" required /></label>
              <label className="text-sm font-medium">Page name<input className="mt-1 w-full rounded-xl border border-[var(--border)] p-3" name="page_name" /></label>
              <label className="text-sm font-medium md:col-span-2">Lead Form IDs<input className="mt-1 w-full rounded-xl border border-[var(--border)] p-3" name="lead_form_ids" placeholder="12345, 67890 (blank = accept all forms on configured page)" /></label>
              <label className="text-sm font-medium">Graph API version<input className="mt-1 w-full rounded-xl border border-[var(--border)] p-3" name="graph_api_version" placeholder="vXX.X" required /></label>
              <label className="text-sm font-medium">Default CRM owner<select className="mt-1 w-full rounded-xl border border-[var(--border)] p-3" name="default_owner_membership_public_id" required><option value="">Choose owner</option>{data.owners.map((owner)=><option key={owner.membership_public_id} value={owner.membership_public_id}>{owner.display_name} · {owner.email}</option>)}</select></label>
              <label className="text-sm font-medium md:col-span-2 xl:col-span-4">Governed secret reference<input className="mt-1 w-full rounded-xl border border-[var(--border)] p-3 font-mono text-xs" name="secret_ref" placeholder="env://META_MPSQRE_LEAD_ADS" required /></label>
              <div className="md:col-span-2 xl:col-span-4 flex justify-end"><button className="rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Create Meta connector</button></div>
            </form>
          </section>
        ) : null}

        <section className="grid gap-5 xl:grid-cols-2">
          {data.connectors.map((connector) => (
            <article className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm" key={connector.public_id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="text-xs font-bold uppercase tracking-[.14em] text-[var(--brand)]">{connector.code}</p><h2 className="mt-1 text-xl font-semibold">{connector.name}</h2><p className="mt-1 text-sm text-[var(--muted)]">{connector.page_name || "Meta Page"} · {connector.page_id}</p></div>
                <span className={`rounded-full px-3 py-1 text-xs font-bold ${statusStyle[connector.status] ?? "bg-slate-100"}`}>{connector.status}</span>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-slate-50 p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-[var(--muted)]">Webhook callback</p><code className="mt-2 block break-all text-xs">{connector.webhook_path}</code></div>
                <div className="rounded-2xl bg-slate-50 p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-[var(--muted)]">Verification token</p><p className="mt-2 text-sm font-semibold">••••{connector.verify_token_last_four || "not set"}</p></div>
                <div className="rounded-2xl bg-slate-50 p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-[var(--muted)]">Forms</p><p className="mt-2 text-sm font-semibold">{connector.lead_form_ids.length ? connector.lead_form_ids.join(", ") : "All forms on configured page"}</p></div>
                <div className="rounded-2xl bg-slate-50 p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-[var(--muted)]">Mapping</p><p className="mt-2 text-sm font-semibold">{connector.mapping_code}</p></div>
              </div>
              {canManage ? <div className="mt-5 flex flex-wrap gap-2">
                <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold" disabled={busy} onClick={() => test(connector)} type="button">Test page connection</button>
                <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold" disabled={busy} onClick={() => rotate(connector)} type="button">Rotate verify token</button>
                {connector.status !== "ACTIVE" ? <button className="rounded-lg bg-[var(--brand)] px-3 py-2 text-xs font-semibold text-white" disabled={busy} onClick={() => status(connector, "ACTIVE")} type="button">Activate ingestion</button> : <button className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-800" disabled={busy} onClick={() => status(connector, "SUSPENDED")} type="button">Suspend</button>}
              </div> : null}
            </article>
          ))}
          {!data.connectors.length ? <div className="xl:col-span-2 rounded-[28px] border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-[var(--muted)]">No Meta Lead Ads connector is configured.</div> : null}
        </section>

        <section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Ingestion evidence</p><h2 className="mt-1 text-2xl font-semibold">Recent Meta submissions</h2></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{data.receipts.length}</span></div>
          <div className="mt-5 space-y-3">
            {data.receipts.map((receipt) => <article className="rounded-2xl border border-[var(--border)] p-4" key={receipt.public_id}>
              <div className="flex flex-wrap items-start gap-3"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${statusStyle[receipt.status] ?? "bg-slate-100"}`}>{receipt.status}</span><span className="text-xs font-semibold">Meta ID {receipt.external_lead_id}</span></div><p className="mt-2 text-xs text-[var(--muted)]">Form {receipt.form_id || "—"} · Campaign {receipt.campaign_id || "—"} · Ad Set {receipt.adset_id || "—"} · Ad {receipt.ad_id || "—"}</p>{receipt.error_summary ? <p className="mt-2 text-xs font-semibold text-red-800">{receipt.error_summary}</p> : null}<p className="mt-2 text-[10px] text-[var(--muted)]">Attempts {receipt.attempt_count} · {new Date(receipt.created_at).toLocaleString()}</p></div>
                <div className="flex flex-wrap gap-2">{receipt.contact_public_id ? <Link className="rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold" href={`/crm?tab=people&person=${receipt.contact_public_id}`}>Open person</Link> : null}{canRetry && ["FAILED","RECEIVED"].includes(receipt.status) ? <button className="rounded-lg bg-[var(--brand)] px-3 py-2 text-xs font-semibold text-white" disabled={busy} onClick={() => retry(receipt)} type="button">Retry now</button> : null}</div>
              </div>
            </article>)}
            {!data.receipts.length ? <p className="rounded-2xl bg-slate-50 p-6 text-sm text-[var(--muted)]">No Meta submission has been received yet.</p> : null}
          </div>
        </section>

        <section className="rounded-[28px] border border-amber-200 bg-amber-50 p-6 text-sm text-amber-950">
          <p className="font-semibold">Webhook setup checklist</p>
          <ol className="mt-3 list-decimal space-y-2 pl-5">
            <li>Expose the backend callback path on your production HTTPS API host.</li>
            <li>Use the one-time verification token shown when the connector is created or rotated.</li>
            <li>Configure the backend environment variable referenced by <code>secret_ref</code> as JSON containing <code>page_access_token</code> and <code>app_secret</code>.</li>
            <li>Test the page connection, then activate ingestion.</li>
            <li>Confirm a test submission creates/reuses a Person, shows source <strong>Facebook</strong> or <strong>Instagram</strong>, and schedules a <strong>Call</strong> next action. No CRM Lead should be created automatically.</li>
          </ol>
        </section>
      </div>
    </main>
  );
}
