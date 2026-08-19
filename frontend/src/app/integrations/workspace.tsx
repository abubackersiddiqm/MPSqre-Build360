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

export type IntegrationSummary = {
  published_localization_packs: number;
  active_connectors: number;
  active_api_clients: number;
  active_webhooks: number;
  failed_deliveries: number;
  open_sync_runs: number;
};

export type LocalizationPack = {
  public_id: string;
  code: string;
  version: number;
  name: string;
  country_code: string;
  locale: string;
  currency: string;
  timezone: string;
  unit_system_code: string;
  date_format: string;
  time_format: string;
  status: string;
  is_default: boolean;
  checksum_sha256: string;
};

export type ExchangeRate = {
  public_id: string;
  base_currency: string;
  quote_currency: string;
  rate: string;
  effective_at: string;
  source_code: string;
  checksum_sha256: string;
};

export type Connector = {
  public_id: string;
  code: string;
  name: string;
  connector_type: string;
  provider_code: string;
  direction: string;
  status: string;
  base_url: string;
  has_secret_reference: boolean;
  health_status: string;
  last_health_message: string;
  version: number;
};

export type ApiClient = {
  public_id: string;
  name: string;
  client_key: string;
  scopes: string[];
  status: string;
  expires_at: string | null;
  rotated_at: string | null;
  version: number;
  client_secret?: string;
};

export type Webhook = {
  public_id: string;
  code: string;
  event_code: string;
  target_url: string;
  status: string;
  failure_count: number;
  last_delivery_at: string | null;
  version: number;
};

export type MappingProfile = {
  public_id: string;
  connector_public_id: string;
  connector_code: string;
  code: string;
  version: number;
  name: string;
  source_schema_code: string;
  target_schema_code: string;
  status: string;
  checksum_sha256: string;
};


export type IntegrationProviderCatalogItem = {
  public_id: string;
  code: string;
  name: string;
  category: string;
  connector_type: string;
  provider_code: string;
  adapter_code: string;
  description: string;
  capabilities: string[];
  recommended: boolean;
  connection: { public_id: string; code: string; name: string; status: string; health_status: string } | null;
};

export type SyncRun = {
  public_id: string;
  connector_public_id: string;
  connector_code: string;
  mapping_public_id: string | null;
  direction: string;
  status: string;
  idempotency_key: string;
  records_read: number;
  records_written: number;
  records_rejected: number;
  evidence_checksum_sha256: string;
  version: number;
};

type Props = {
  company: Company;
  permissions: string[];
  features: Record<string, boolean>;
  initialSummary: IntegrationSummary | null;
  initialPacks: LocalizationPack[];
  initialRates: ExchangeRate[];
  initialConnectors: Connector[];
  initialClients: ApiClient[];
  initialWebhooks: Webhook[];
  initialMappings: MappingProfile[];
  initialSyncRuns: SyncRun[];
  initialProviders: IntegrationProviderCatalogItem[];
};

type Tab = "marketplace" | "localization" | "connectors" | "clients" | "webhooks" | "sync";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/integrations/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = (await response.json().catch(() => ({}))) as {
    message?: string;
    detail?: string;
  };
  if (!response.ok) throw new Error(body.message ?? body.detail ?? "Integration request failed.");
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

const inputClass = "w-full rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm";
const panelClass = "rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm";

export function IntegrationWorkspace({
  company,
  permissions,
  features,
  initialSummary,
  initialPacks,
  initialRates,
  initialConnectors,
  initialClients,
  initialWebhooks,
  initialMappings,
  initialSyncRuns,
  initialProviders,
}: Readonly<Props>) {
  const [tab, setTab] = useState<Tab>("marketplace");
  const [connectorPreset, setConnectorPreset] = useState<IntegrationProviderCatalogItem | null>(null);
  const [packs, setPacks] = useState(initialPacks);
  const [rates, setRates] = useState(initialRates);
  const [connectors, setConnectors] = useState(initialConnectors);
  const [clients, setClients] = useState(initialClients);
  const [webhooks, setWebhooks] = useState(initialWebhooks);
  const [mappings, setMappings] = useState(initialMappings);
  const [syncRuns, setSyncRuns] = useState(initialSyncRuns);
  const [issuedSecret, setIssuedSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const feature = (code: string) => features[code] === true;
  const summary = initialSummary ?? {
    published_localization_packs: packs.filter((item) => item.status === "PUBLISHED").length,
    active_connectors: connectors.filter((item) => item.status === "ACTIVE").length,
    active_api_clients: clients.filter((item) => item.status === "ACTIVE").length,
    active_webhooks: webhooks.filter((item) => item.status === "ACTIVE").length,
    failed_deliveries: 0,
    open_sync_runs: syncRuns.filter((item) => ["QUEUED", "RUNNING"].includes(item.status)).length,
  };

  async function createPack(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    setMessage("");
    try {
      const item = await api<LocalizationPack>("localization-packs", {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          name: form.get("name"),
          country_code: form.get("country_code"),
          locale: form.get("locale"),
          currency: form.get("currency"),
          timezone_code: form.get("timezone_code"),
          unit_system_code: form.get("unit_system_code"),
          date_format: form.get("date_format"),
          time_format: "24h",
          number_format: { decimal: ".", group: ",", grouping: [3] },
          address_schema: { fields: ["line1", "city", "region", "postal_code", "country"] },
          tax_schema: { system: form.get("tax_system"), labels: [form.get("tax_system")] },
          terminology: { postal_code: "Postal code", tax_invoice: "Tax invoice" },
          effective_from: new Date().toISOString(),
          effective_to: null,
          is_default: false,
        }),
      });
      setPacks((current) => [item, ...current]);
      setMessage(`Created ${item.name} v${item.version}.`);
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Localization pack creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function publishPack(item: LocalizationPack) {
    setBusy(true);
    setMessage("");
    try {
      const updated = await api<LocalizationPack>(`localization-packs/${item.public_id}/publish`, {
        method: "POST",
        body: JSON.stringify({ expected_version: item.version }),
      });
      setPacks((current) => current.map((value) => (value.public_id === updated.public_id ? updated : value)));
      setMessage(`${updated.name} is published.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Publishing failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    try {
      const item = await api<ExchangeRate>("exchange-rates", {
        method: "POST",
        body: JSON.stringify({
          base_currency: form.get("base_currency"),
          quote_currency: form.get("quote_currency"),
          rate: form.get("rate"),
          effective_at: new Date().toISOString(),
          source_code: form.get("source_code"),
        }),
      });
      setRates((current) => [item, ...current]);
      setMessage(`Recorded ${item.base_currency}/${item.quote_currency}.`);
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Exchange-rate recording failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createConnectorItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    try {
      const item = await api<Connector>("connectors", {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          name: form.get("name"),
          connector_type: form.get("connector_type"),
          provider_code: form.get("provider_code"),
          direction: form.get("direction"),
          base_url: form.get("base_url"),
          public_config: { external_calls_enabled: false },
          secret_ref: form.get("secret_ref"),
          allowed_data_classes: String(form.get("allowed_data_classes") ?? "")
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
        }),
      });
      setConnectors((current) => [item, ...current]);
      setMessage(`Created connector ${item.code}.`);
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Connector creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function changeConnectorStatus(item: Connector, targetStatus: string) {
    setBusy(true);
    setMessage("");
    try {
      const updated = await api<Connector>(`connectors/${item.public_id}/status`, {
        method: "POST",
        body: JSON.stringify({
          expected_version: item.version,
          target_status: targetStatus,
          reason: "ui.phase14.connector_status",
        }),
      });
      setConnectors((current) =>
        current.map((value) => (value.public_id === updated.public_id ? updated : value)),
      );
      setMessage(`${updated.code} is now ${updated.status}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Connector status change failed.");
    } finally {
      setBusy(false);
    }
  }

  async function checkConnector(item: Connector) {
    setBusy(true);
    try {
      const updated = await api<Connector>(`connectors/${item.public_id}/health`, {
        method: "POST",
        body: JSON.stringify({ expected_version: item.version }),
      });
      setConnectors((current) => current.map((value) => (value.public_id === updated.public_id ? updated : value)));
      setMessage(`${updated.code}: ${updated.health_status}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Connector health evaluation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function issueClient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!feature("platform.api_access")) { setMessage("API Access is disabled for this company subscription."); return; }
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    setIssuedSecret("");
    try {
      const item = await api<ApiClient>("api-clients", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          scopes: String(form.get("scopes") ?? "")
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
          allowed_ip_ranges: [],
          expires_at: null,
        }),
      });
      setClients((current) => [item, ...current]);
      setIssuedSecret(item.client_secret ?? "");
      setMessage("API client issued. Copy the secret now; it will not be shown again.");
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "API client issuance failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createWebhook(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    try {
      const item = await api<Webhook>("webhooks", {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          event_code: form.get("event_code"),
          target_url: form.get("target_url"),
          secret_ref: form.get("secret_ref"),
          headers_public: { "X-Build360-Contract": "v1" },
          allowed_data_classes: ["integration"],
        }),
      });
      setWebhooks((current) => [item, ...current]);
      setMessage(`Created webhook ${item.code} in paused state.`);
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Webhook creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function changeWebhookStatus(item: Webhook, targetStatus: string) {
    setBusy(true);
    setMessage("");
    try {
      const updated = await api<Webhook>(`webhooks/${item.public_id}/status`, {
        method: "POST",
        body: JSON.stringify({
          expected_version: item.version,
          target_status: targetStatus,
          reason: "ui.phase14.webhook_status",
        }),
      });
      setWebhooks((current) =>
        current.map((value) => (value.public_id === updated.public_id ? updated : value)),
      );
      setMessage(`${updated.code} is now ${updated.status}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Webhook status change failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createMapping(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    try {
      const item = await api<MappingProfile>("mappings", {
        method: "POST",
        body: JSON.stringify({
          connector_public_id: form.get("connector_public_id"),
          code: form.get("code"),
          name: form.get("name"),
          source_schema_code: form.get("source_schema_code"),
          target_schema_code: form.get("target_schema_code"),
          mappings: [{ source: "public_id", target: "external_id", required: true }],
          transformations: [],
        }),
      });
      setMappings((current) => [item, ...current]);
      setMessage(`Created mapping ${item.code} v${item.version}.`);
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Mapping creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function publishMapping(item: MappingProfile) {
    setBusy(true);
    try {
      const updated = await api<MappingProfile>(`mappings/${item.public_id}/publish`, {
        method: "POST",
        body: "{}",
      });
      setMappings((current) => current.map((value) => (value.public_id === updated.public_id ? updated : value)));
      setMessage(`${updated.code} is published.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Mapping publication failed.");
    } finally {
      setBusy(false);
    }
  }

  async function startSync(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    try {
      const item = await api<SyncRun>("sync-runs", {
        method: "POST",
        body: JSON.stringify({
          connector_public_id: form.get("connector_public_id"),
          mapping_public_id: form.get("mapping_public_id") || null,
          direction: form.get("direction"),
          idempotency_key: `ui-${crypto.randomUUID()}`,
        }),
      });
      setSyncRuns((current) => [item, ...current]);
      setMessage(`Synchronization run started for ${item.connector_code}.`);
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Synchronization start failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
              MPSqre Build360 · Globalization & Integration Hub
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              Regional rollout and ecosystem connectivity
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {company.display_name} · {company.locale} · {company.currency} · provider-neutral
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <span className="rounded-full bg-emerald-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-emerald-900">
              Phase 14 active
            </span>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/platform">
              Platform
            </Link>
          </div>
        </header>

        <section className="grid gap-4 py-7 sm:grid-cols-2 xl:grid-cols-6">
          <Card label="Published regions" value={summary.published_localization_packs} />
          <Card label="Active connectors" value={summary.active_connectors} />
          {feature("platform.api_access") ? <Card label="API clients" value={summary.active_api_clients} /> : null}
          <Card label="Active webhooks" value={summary.active_webhooks} />
          <Card label="Failed deliveries" value={summary.failed_deliveries} />
          <Card label="Open sync runs" value={summary.open_sync_runs} />
        </section>

        <nav className="flex flex-wrap gap-2 pb-6">
          {(["marketplace", "localization", "connectors", "clients", "webhooks", "sync"] as Tab[]).filter((value) => value !== "clients" || feature("platform.api_access")).map((value) => (
            <button
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-[var(--brand)] text-white" : "border border-[var(--border)] bg-white"}`}
              key={value}
              onClick={() => setTab(value)}
              type="button"
            >
              {value === "marketplace" ? "Marketplace" : value === "localization" ? "Regions & FX" : value === "clients" ? "API clients" : value.charAt(0).toUpperCase() + value.slice(1)}
            </button>
          ))}
        </nav>

        {message ? <p className="mb-5 rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm">{message}</p> : null}


        {tab === "marketplace" ? (
          <section className="space-y-6">
            <article className="overflow-hidden rounded-[28px] border border-[var(--border)] bg-white shadow-sm">
              <div className="grid gap-6 p-6 lg:grid-cols-[1.1fr_.9fr] lg:p-8">
                <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand)]">Integration marketplace</p><h2 className="mt-2 text-3xl font-semibold tracking-tight">Connect the tools each company already trusts.</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--muted)]">The catalogue is global; the actual ConnectorProfile remains company-scoped, provider-neutral and secret-reference based. Choosing a card never stores raw credentials in the browser.</p></div>
                <div className="grid grid-cols-2 gap-3 rounded-3xl bg-slate-50 p-5"><div><p className="text-3xl font-semibold">{initialProviders.length}</p><p className="text-xs text-[var(--muted)]">Available providers</p></div><div><p className="text-3xl font-semibold">{initialProviders.filter((item) => item.connection?.status === "ACTIVE").length}</p><p className="text-xs text-[var(--muted)]">Connected</p></div><div><p className="text-3xl font-semibold">{new Set(initialProviders.map((item) => item.category)).size}</p><p className="text-xs text-[var(--muted)]">Categories</p></div><div><p className="text-3xl font-semibold">{initialProviders.filter((item) => item.recommended).length}</p><p className="text-xs text-[var(--muted)]">Recommended</p></div></div>
              </div>
            </article>
            {[...new Set(initialProviders.map((item) => item.category))].map((category) => (
              <section key={category}>
                <div className="mb-3 flex items-center justify-between"><h3 className="text-lg font-semibold">{category.replaceAll("_", " ")}</h3><span className="text-xs text-[var(--muted)]">{initialProviders.filter((item) => item.category === category).length} providers</span></div>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{initialProviders.filter((item) => item.category === category).map((item) => (
                  <article className="group rounded-[24px] border border-[var(--border)] bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md" key={item.public_id}>
                    <div className="flex items-start justify-between gap-4"><div className="grid h-11 w-11 place-items-center rounded-2xl bg-[var(--brand-soft)] text-xs font-black text-[var(--brand)]">{item.name.split(/\s+/).map((word) => word[0]).join("").slice(0, 3).toUpperCase()}</div><div className="flex gap-2">{item.recommended ? <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-bold uppercase text-emerald-800">Recommended</span> : null}{item.connection ? <Status value={item.connection.status} /> : <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold uppercase text-slate-600">Available</span>}</div></div>
                    <h4 className="mt-4 text-lg font-semibold">{item.name}</h4><p className="mt-2 min-h-10 text-sm leading-5 text-[var(--muted)]">{item.description}</p><div className="mt-4 flex flex-wrap gap-2">{item.capabilities.slice(0, 4).map((capability) => <span className="rounded-lg bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-600" key={capability}>{capability}</span>)}</div>
                    <div className="mt-5 flex items-center justify-between border-t border-[var(--border)] pt-4"><span className="text-xs text-[var(--muted)]">{item.adapter_code || "Adapter slot"}</span>{permissions.includes("integration.connector.manage") ? <button className="rounded-xl bg-[var(--brand)] px-3.5 py-2 text-xs font-semibold text-white" onClick={() => { setConnectorPreset(item); setTab("connectors"); setMessage(`Configure ${item.name}. Add only a governed secret reference—never paste raw secrets into public config.`); }} type="button">{item.connection ? "Manage" : "Configure"}</button> : null}</div>
                  </article>
                ))}</div>
              </section>
            ))}
          </section>
        ) : null}

        {tab === "localization" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            <div className="space-y-6">
              {permissions.includes("integration.localization.manage") ? (
                <form className={panelClass} onSubmit={createPack}>
                  <h2 className="text-xl font-semibold">Create regional pack</h2>
                  <div className="mt-5 space-y-3">
                    <input className={inputClass} name="code" placeholder="Pack code" required />
                    <input className={inputClass} name="name" placeholder="Pack name" required />
                    <div className="grid grid-cols-2 gap-3">
                      <input className={inputClass} maxLength={2} name="country_code" placeholder="Country" required />
                      <input className={inputClass} maxLength={3} name="currency" placeholder="Currency" required />
                    </div>
                    <input className={inputClass} name="locale" placeholder="Locale, e.g. en-AE" required />
                    <input className={inputClass} name="timezone_code" placeholder="Timezone" required />
                    <select className={inputClass} name="unit_system_code" defaultValue="metric">
                      <option value="metric">Metric</option>
                      <option value="imperial">Imperial</option>
                    </select>
                    <input className={inputClass} name="date_format" defaultValue="DD/MM/YYYY" required />
                    <input className={inputClass} name="tax_system" placeholder="Tax system, e.g. VAT" required />
                    <button className="w-full rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white" disabled={busy} type="submit">
                      Create draft pack
                    </button>
                  </div>
                </form>
              ) : null}
              {permissions.includes("integration.currency.manage") ? (
                <form className={panelClass} onSubmit={createRate}>
                  <h2 className="text-xl font-semibold">Record FX evidence</h2>
                  <div className="mt-5 space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <input className={inputClass} defaultValue={company.currency} name="base_currency" required />
                      <input className={inputClass} name="quote_currency" placeholder="USD" required />
                    </div>
                    <input className={inputClass} name="rate" placeholder="Rate" required type="number" min="0.00000001" step="0.00000001" />
                    <input className={inputClass} name="source_code" placeholder="Approved source code" required />
                    <button className="w-full rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white" disabled={busy} type="submit">
                      Record snapshot
                    </button>
                  </div>
                </form>
              ) : null}
            </div>
            <div className="space-y-6">
              <article className={panelClass}>
                <h2 className="text-xl font-semibold">Regional localization catalogue</h2>
                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  {packs.map((item) => (
                    <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold">{item.name}</p>
                          <p className="mt-1 text-sm text-[var(--muted)]">{item.country_code} · {item.locale} · {item.currency}</p>
                        </div>
                        <Status value={item.status} />
                      </div>
                      <p className="mt-3 text-xs text-[var(--muted)]">{item.timezone} · {item.unit_system_code} · {item.date_format}</p>
                      {item.status === "DRAFT" && permissions.includes("integration.localization.publish") ? (
                        <button className="mt-4 rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} onClick={() => publishPack(item)} type="button">
                          Publish
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
              </article>
              <article className={panelClass}>
                <h2 className="text-xl font-semibold">Exchange-rate evidence</h2>
                <div className="mt-5 space-y-3">
                  {rates.length ? rates.map((item) => (
                    <div className="flex items-center justify-between rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                      <div>
                        <p className="font-semibold">{item.base_currency}/{item.quote_currency} · {item.rate}</p>
                        <p className="mt-1 text-xs text-[var(--muted)]">{item.source_code} · {new Date(item.effective_at).toLocaleString()}</p>
                      </div>
                      <span className="text-xs text-[var(--muted)]">{item.checksum_sha256.slice(0, 12)}…</span>
                    </div>
                  )) : <p className="text-sm text-[var(--muted)]">No exchange-rate snapshots recorded.</p>}
                </div>
              </article>
            </div>
          </section>
        ) : null}

        {tab === "connectors" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            {permissions.includes("integration.connector.manage") ? (
              <form className={panelClass} key={connectorPreset?.provider_code ?? "manual"} onSubmit={createConnectorItem}>
                <h2 className="text-xl font-semibold">Register connector</h2>
                <div className="mt-5 space-y-3">
                  <input className={inputClass} defaultValue={connectorPreset ? `${connectorPreset.provider_code}_01` : ""} name="code" placeholder="Connector code" required />
                  <input className={inputClass} defaultValue={connectorPreset?.name ?? ""} name="name" placeholder="Connector name" required />
                  <select className={inputClass} name="connector_type" defaultValue={connectorPreset?.connector_type ?? "CUSTOM"}>
                    <option value="ACCOUNTING">Accounting</option><option value="IDENTITY">Identity</option><option value="STORAGE">Storage</option><option value="COMMUNICATION">Communication</option><option value="ANALYTICS">Analytics</option><option value="CUSTOM">Custom</option>
                  </select>
                  <input className={inputClass} defaultValue={connectorPreset?.provider_code ?? ""} name="provider_code" placeholder="Provider code" required />
                  <select className={inputClass} name="direction" defaultValue="BIDIRECTIONAL">
                    <option value="INBOUND">Inbound</option><option value="OUTBOUND">Outbound</option><option value="BIDIRECTIONAL">Bidirectional</option>
                  </select>
                  <input className={inputClass} name="base_url" placeholder="Base URL (optional)" type="url" />
                  <input className={inputClass} name="secret_ref" placeholder="Secret reference (never raw secret)" />
                  <input className={inputClass} name="allowed_data_classes" placeholder="finance, reporting" />
                  <button className="w-full rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white" disabled={busy} type="submit">Register connector</button>
                </div>
              </form>
            ) : <div />}
            <article className={panelClass}>
              <h2 className="text-xl font-semibold">Connector profiles</h2>
              <div className="mt-5 space-y-3">
                {connectors.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div><p className="font-semibold">{item.name}</p><p className="mt-1 text-sm text-[var(--muted)]">{item.code} · {item.connector_type} · {item.direction}</p></div>
                      <div className="flex gap-2"><Status value={item.status} /><Status value={item.health_status} /></div>
                    </div>
                    <p className="mt-3 text-xs text-[var(--muted)]">Provider: {item.provider_code} · Secret ref: {item.has_secret_reference ? "configured" : "missing"}</p>
                    {item.last_health_message ? <p className="mt-2 text-sm text-[var(--muted)]">{item.last_health_message}</p> : null}
                    <div className="mt-4 flex flex-wrap gap-2">
                      {permissions.includes("integration.connector.health") ? <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} onClick={() => checkConnector(item)} type="button">Evaluate contract</button> : null}
                      {permissions.includes("integration.connector.manage") && item.status !== "ACTIVE" ? <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} onClick={() => changeConnectorStatus(item, "ACTIVE")} type="button">Activate</button> : null}
                      {permissions.includes("integration.connector.manage") && item.status === "ACTIVE" ? <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} onClick={() => changeConnectorStatus(item, "SUSPENDED")} type="button">Suspend</button> : null}
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "clients" && feature("platform.api_access") ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            {permissions.includes("integration.api_client.manage") ? (
              <form className={panelClass} onSubmit={issueClient}>
                <h2 className="text-xl font-semibold">Issue API client</h2>
                <div className="mt-5 space-y-3">
                  <input className={inputClass} name="name" placeholder="Client name" required />
                  <input className={inputClass} name="scopes" placeholder="reporting.read, project.read" required />
                  <button className="w-full rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white" disabled={busy} type="submit">Issue credential</button>
                </div>
                {issuedSecret ? <div className="mt-5 rounded-xl border border-amber-300 bg-amber-50 p-4"><p className="text-sm font-semibold">Copy this secret now</p><code className="mt-2 block break-all text-xs">{issuedSecret}</code></div> : null}
              </form>
            ) : <div />}
            <article className={panelClass}>
              <h2 className="text-xl font-semibold">API client register</h2>
              <div className="mt-5 space-y-3">
                {clients.length ? clients.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{item.name}</p><p className="mt-1 font-mono text-xs text-[var(--muted)]">{item.client_key}</p></div><Status value={item.status} /></div>
                    <p className="mt-3 text-xs text-[var(--muted)]">Scopes: {item.scopes.join(", ")}</p>
                  </div>
                )) : <p className="text-sm text-[var(--muted)]">No API clients issued.</p>}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "webhooks" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            {permissions.includes("integration.webhook.manage") ? (
              <form className={panelClass} onSubmit={createWebhook}>
                <h2 className="text-xl font-semibold">Register webhook</h2>
                <div className="mt-5 space-y-3">
                  <input className={inputClass} name="code" placeholder="Webhook code" required />
                  <input className={inputClass} name="event_code" placeholder="Event code" required />
                  <input className={inputClass} name="target_url" placeholder="HTTPS target URL" required type="url" />
                  <input className={inputClass} name="secret_ref" placeholder="Governed secret reference" required />
                  <button className="w-full rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white" disabled={busy} type="submit">Register paused webhook</button>
                </div>
              </form>
            ) : <div />}
            <article className={panelClass}>
              <h2 className="text-xl font-semibold">Webhook subscriptions</h2>
              <div className="mt-5 space-y-3">
                {webhooks.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{item.code}</p><p className="mt-1 text-sm text-[var(--muted)]">{item.event_code}</p></div><Status value={item.status} /></div>
                    <p className="mt-3 break-all text-xs text-[var(--muted)]">{item.target_url}</p>
                    <p className="mt-2 text-xs text-[var(--muted)]">Failures: {item.failure_count}</p>
                    {permissions.includes("integration.webhook.manage") ? (
                      <div className="mt-4 flex gap-2">
                        {item.status !== "ACTIVE" ? <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} onClick={() => changeWebhookStatus(item, "ACTIVE")} type="button">Activate</button> : <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} onClick={() => changeWebhookStatus(item, "PAUSED")} type="button">Pause</button>}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "sync" ? (
          <section className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              {permissions.includes("integration.mapping.manage") ? (
                <form className={panelClass} onSubmit={createMapping}>
                  <h2 className="text-xl font-semibold">Create mapping profile</h2>
                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    <select className={inputClass} name="connector_public_id" required defaultValue=""><option disabled value="">Select connector</option>{connectors.map((item) => <option key={item.public_id} value={item.public_id}>{item.code}</option>)}</select>
                    <input className={inputClass} name="code" placeholder="Mapping code" required />
                    <input className={inputClass} name="name" placeholder="Mapping name" required />
                    <input className={inputClass} name="source_schema_code" placeholder="Source schema" required />
                    <input className={inputClass} name="target_schema_code" placeholder="Target schema" required />
                    <button className="rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white" disabled={busy} type="submit">Create draft mapping</button>
                  </div>
                </form>
              ) : null}
              {permissions.includes("integration.sync.run") ? (
                <form className={panelClass} onSubmit={startSync}>
                  <h2 className="text-xl font-semibold">Start governed sync</h2>
                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    <select className={inputClass} name="connector_public_id" required defaultValue=""><option disabled value="">Select connector</option>{connectors.map((item) => <option key={item.public_id} value={item.public_id}>{item.code}</option>)}</select>
                    <select className={inputClass} name="mapping_public_id" defaultValue=""><option value="">No mapping</option>{mappings.filter((item) => item.status === "PUBLISHED").map((item) => <option key={item.public_id} value={item.public_id}>{item.code} v{item.version}</option>)}</select>
                    <select className={inputClass} name="direction" defaultValue="OUTBOUND"><option value="INBOUND">Inbound</option><option value="OUTBOUND">Outbound</option><option value="BIDIRECTIONAL">Bidirectional</option></select>
                    <button className="rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white" disabled={busy} type="submit">Start sync evidence</button>
                  </div>
                </form>
              ) : null}
            </div>
            <article className={panelClass}>
              <h2 className="text-xl font-semibold">Mapping profiles</h2>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {mappings.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{item.name}</p><p className="mt-1 text-sm text-[var(--muted)]">{item.connector_code} · {item.code} v{item.version}</p></div><Status value={item.status} /></div>
                    <p className="mt-3 text-xs text-[var(--muted)]">{item.source_schema_code} → {item.target_schema_code}</p>
                    {item.status === "DRAFT" && permissions.includes("integration.mapping.publish") ? <button className="mt-4 rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} onClick={() => publishMapping(item)} type="button">Publish</button> : null}
                  </div>
                ))}
              </div>
            </article>
            <article className={panelClass}>
              <h2 className="text-xl font-semibold">Synchronization evidence</h2>
              <div className="mt-5 space-y-3">
                {syncRuns.length ? syncRuns.map((item) => (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div><p className="font-semibold">{item.connector_code} · {item.direction}</p><p className="mt-1 text-xs text-[var(--muted)]">Read {item.records_read} · Written {item.records_written} · Rejected {item.records_rejected}</p></div><Status value={item.status} />
                  </div>
                )) : <p className="text-sm text-[var(--muted)]">No synchronization runs recorded.</p>}
              </div>
            </article>
          </section>
        ) : null}
      </div>
    </main>
  );
}
