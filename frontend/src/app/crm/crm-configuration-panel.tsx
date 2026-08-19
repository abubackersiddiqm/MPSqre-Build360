"use client";

import { FormEvent, useMemo, useState } from "react";

import { Build360ErrorDialog } from "@/components/build360-dialog";
import { Build360Toast } from "@/components/build360-toast";

export type CrmConfiguration = {
  profile: {
    public_id: string;
    industry_code: string;
    terminology: Record<string, string>;
    settings: Record<string, unknown>;
    version: number;
  };
  industry_packs: Array<{ code: string; name: string; description: string }>;
  pipelines: Array<{
    public_id: string;
    entity_type: "lead" | "opportunity";
    code: string;
    name: string;
    description: string;
    is_default: boolean;
    sort_order: number;
    stage_count: number;
  }>;
  stages: Array<{
    public_id: string;
    pipeline_public_id: string | null;
    entity_type: "lead" | "opportunity";
    code: string;
    name: string;
    outcome: string;
    sort_order: number;
    probability_percent: number;
    allowed_next_codes: string[];
    is_initial: boolean;
    allows_conversion: boolean;
  }>;
  custom_fields: Array<{
    public_id: string;
    entity_type: "customer" | "contact" | "lead" | "opportunity";
    code: string;
    label: string;
    field_type: string;
    help_text: string;
    is_required: boolean;
    options: string[];
    sort_order: number;
    source_pack_code: string;
  }>;
  lead_sources: Array<{
    public_id: string;
    code: string;
    name: string;
    channel_type: string;
    sort_order: number;
    source_pack_code: string;
  }>;
};

type Props = {
  configuration: CrmConfiguration;
  canManage: boolean;
  onChanged: (configuration: CrmConfiguration) => void;
};

type ErrorEnvelope = { message?: string; field_errors?: Record<string, string[]>; details?: string[] };

async function configRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/crm/${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as ErrorEnvelope;
    const fields = Object.entries(error.field_errors ?? {})
      .flatMap(([field, messages]) => messages.map((message) => `${field}: ${message}`))
      .join(" ");
    throw new Error(fields || error.message || `CRM configuration request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

const TERMINOLOGY_KEYS = ["customer", "contact", "lead", "opportunity", "pipeline", "quote"] as const;

export function CrmConfigurationPanel({ configuration, canManage, onChanged }: Readonly<Props>) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const currentPack = useMemo(
    () => configuration.industry_packs.find((item) => item.code === configuration.profile.industry_code),
    [configuration],
  );

  async function applyPack(packCode: string) {
    setBusy(true); setNotice(""); setError("");
    try {
      const updated = await configRequest<CrmConfiguration>("configuration/apply-pack", {
        method: "POST",
        body: JSON.stringify({ pack_code: packCode }),
      });
      onChanged(updated);
      setNotice(`${updated.industry_packs.find((item) => item.code === packCode)?.name || "Industry"} starter pack applied. Existing CRM records were preserved.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Industry pack could not be applied.");
    } finally { setBusy(false); }
  }

  async function saveTerminology(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setNotice(""); setError("");
    const form = new FormData(event.currentTarget);
    const terminology = Object.fromEntries(
      TERMINOLOGY_KEYS.map((key) => [key, String(form.get(key) || "").trim()]),
    );
    try {
      const updated = await configRequest<CrmConfiguration>("configuration", {
        method: "PATCH",
        body: JSON.stringify({ terminology }),
      });
      onChanged(updated);
      setNotice("CRM terminology updated. Core data model stays stable while your users see business-friendly labels.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Terminology could not be saved.");
    } finally { setBusy(false); }
  }

  async function createStage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setNotice(""); setError("");
    const form = new FormData(event.currentTarget);
    const pipelineId = String(form.get("pipeline_public_id") || "");
    const pipeline = configuration.pipelines.find((item) => item.public_id === pipelineId);
    if (!pipeline) { setBusy(false); setError("Choose a CRM pipeline."); return; }
    try {
      await configRequest("stages", {
        method: "POST",
        body: JSON.stringify({
          pipeline_public_id: pipelineId,
          entity_type: pipeline.entity_type,
          code: form.get("code"),
          name: form.get("name"),
          outcome: form.get("outcome"),
          sort_order: Number(form.get("sort_order") || 100),
          probability_percent: Number(form.get("probability_percent") || 0),
          allowed_next_codes: String(form.get("allowed_next_codes") || "").split(",").map((value) => value.trim()).filter(Boolean),
          is_initial: form.get("is_initial") === "on",
          allows_conversion: form.get("allows_conversion") === "on",
          effective_from: new Date().toISOString(),
        }),
      });
      const updated = await configRequest<CrmConfiguration>("configuration");
      onChanged(updated);
      event.currentTarget.reset();
      setNotice("Pipeline stage added. Transition codes are resolved only inside this pipeline.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Pipeline stage could not be created.");
    } finally { setBusy(false); }
  }

  async function createField(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setNotice(""); setError("");
    const form = new FormData(event.currentTarget);
    try {
      await configRequest("custom-fields", {
        method: "POST",
        body: JSON.stringify({
          entity_type: form.get("entity_type"),
          code: form.get("code"),
          label: form.get("label"),
          field_type: form.get("field_type"),
          help_text: form.get("help_text"),
          is_required: form.get("is_required") === "on",
          options: String(form.get("options") || "").split(",").map((value) => value.trim()).filter(Boolean),
        }),
      });
      const updated = await configRequest<CrmConfiguration>("configuration");
      onChanged(updated);
      event.currentTarget.reset();
      setNotice("Custom field added. New CRM records will validate this definition server-side.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Custom field could not be created.");
    } finally { setBusy(false); }
  }

  async function createSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setNotice(""); setError("");
    const form = new FormData(event.currentTarget);
    try {
      await configRequest("lead-sources", {
        method: "POST",
        body: JSON.stringify({ code: form.get("code"), name: form.get("name"), channel_type: form.get("channel_type") }),
      });
      const updated = await configRequest<CrmConfiguration>("configuration");
      onChanged(updated);
      event.currentTarget.reset();
      setNotice("Lead source added.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lead source could not be created.");
    } finally { setBusy(false); }
  }

  async function createPipeline(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setNotice(""); setError("");
    const form = new FormData(event.currentTarget);
    try {
      await configRequest("pipelines", {
        method: "POST",
        body: JSON.stringify({
          entity_type: form.get("entity_type"),
          code: form.get("code"),
          name: form.get("name"),
          description: form.get("description"),
          is_default: form.get("is_default") === "on",
        }),
      });
      const updated = await configRequest<CrmConfiguration>("configuration");
      onChanged(updated);
      event.currentTarget.reset();
      setNotice("Pipeline created. Add its stages from the existing stage API/workflow before using it for new records.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Pipeline could not be created.");
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Universal CRM</p>
            <h2 className="mt-1 text-xl font-semibold">Industry adaptation</h2>
            <p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">CRM Core stays industry-neutral. Packs only seed labels and custom fields; they do not create construction-only business tables or lock your company to an industry.</p>
          </div>
          <span className="rounded-full bg-[var(--brand-soft)] px-3 py-1.5 text-xs font-bold text-[var(--brand)]">{currentPack?.name || configuration.profile.industry_code}</span>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {configuration.industry_packs.map((pack) => (
            <button
              className={`rounded-xl border p-4 text-left transition ${pack.code === configuration.profile.industry_code ? "border-[var(--brand)] bg-[var(--brand-soft)]" : "border-[var(--border)] hover:border-[var(--brand)]"}`}
              disabled={!canManage || busy}
              key={pack.code}
              onClick={() => applyPack(pack.code)}
              type="button"
            >
              <span className="font-semibold">{pack.name}</span>
              <span className="mt-1 block text-xs leading-5 text-[var(--muted)]">{pack.description}</span>
            </button>
          ))}
        </div>
      </section>


      <section className="grid gap-6 xl:grid-cols-2">
        <form className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={saveTerminology}>
          <h3 className="font-semibold">Business terminology</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">Example: Lead → Applicant, Opportunity → Deal, Customer → Account.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {TERMINOLOGY_KEYS.map((key) => (
              <label className="text-sm font-medium capitalize" key={key}>{key}
                <input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" defaultValue={configuration.profile.terminology[key] || key} disabled={!canManage} name={key} required />
              </label>
            ))}
          </div>
          {canManage ? <div className="mt-4 flex justify-end"><button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" disabled={busy} type="submit">Save labels</button></div> : null}
        </form>

        <form className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createPipeline}>
          <h3 className="font-semibold">Pipelines</h3>
          <div className="mt-3 space-y-2">
            {configuration.pipelines.map((pipeline) => <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm" key={pipeline.public_id}><span>{pipeline.name} <span className="text-[var(--muted)]">· {pipeline.entity_type}</span></span><span className="text-xs font-semibold">{pipeline.stage_count} stages{pipeline.is_default ? " · default" : ""}</span></div>)}
          </div>
          {canManage ? <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">Type<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="entity_type"><option value="lead">Lead</option><option value="opportunity">Opportunity</option></select></label>
            <label className="text-sm font-medium">Code<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="code" placeholder="enterprise_sales" required /></label>
            <label className="text-sm font-medium">Name<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="name" placeholder="Enterprise Sales" required /></label>
            <label className="text-sm font-medium">Description<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="description" /></label>
            <label className="flex items-center gap-2 text-sm font-medium"><input name="is_default" type="checkbox" /> Default for new records</label>
            <div className="flex justify-end"><button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" disabled={busy} type="submit">Add pipeline</button></div>
          </div> : null}
        </form>
      </section>

      <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
        <h3 className="font-semibold">Pipeline stages</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">Each pipeline owns its own stage codes, so two departments can both use New, Won or Lost without colliding.</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {configuration.pipelines.map((pipeline) => (
            <div className="rounded-xl bg-slate-50 p-4" key={pipeline.public_id}>
              <div className="flex items-center justify-between gap-2"><span className="font-semibold">{pipeline.name}</span><span className="text-xs uppercase text-[var(--muted)]">{pipeline.entity_type}</span></div>
              <div className="mt-3 flex flex-wrap gap-2">
                {configuration.stages.filter((stage) => stage.pipeline_public_id === pipeline.public_id).map((stage) => (
                  <span className="rounded-full border border-[var(--border)] bg-white px-2.5 py-1 text-xs" key={stage.public_id}>{stage.name}{stage.is_initial ? " · initial" : ""}</span>
                ))}
                {!configuration.stages.some((stage) => stage.pipeline_public_id === pipeline.public_id) ? <span className="text-xs text-[var(--muted)]">No stages yet</span> : null}
              </div>
            </div>
          ))}
        </div>
        {canManage ? <form className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" onSubmit={createStage}>
          <label className="text-sm font-medium">Pipeline<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="pipeline_public_id" required><option value="">Choose</option>{configuration.pipelines.map((pipeline) => <option key={pipeline.public_id} value={pipeline.public_id}>{pipeline.name} · {pipeline.entity_type}</option>)}</select></label>
          <label className="text-sm font-medium">Stage code<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="code" placeholder="proposal" required /></label>
          <label className="text-sm font-medium">Stage name<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="name" placeholder="Proposal" required /></label>
          <label className="text-sm font-medium">Outcome<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="outcome"><option value="open">Open</option><option value="qualified">Qualified</option><option value="converted">Converted</option><option value="won">Won</option><option value="lost">Lost</option><option value="disqualified">Disqualified</option></select></label>
          <label className="text-sm font-medium">Order<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" defaultValue="100" min="0" name="sort_order" type="number" /></label>
          <label className="text-sm font-medium">Probability %<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" defaultValue="0" max="100" min="0" name="probability_percent" type="number" /></label>
          <label className="text-sm font-medium lg:col-span-2">Allowed next stage codes<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="allowed_next_codes" placeholder="proposal, negotiation, lost" /></label>
          <label className="flex items-center gap-2 text-sm font-medium"><input name="is_initial" type="checkbox" /> Initial stage</label>
          <label className="flex items-center gap-2 text-sm font-medium"><input name="allows_conversion" type="checkbox" /> Allows lead conversion</label>
          <div className="flex items-end justify-end sm:col-span-2"><button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" disabled={busy || !configuration.pipelines.length} type="submit">Add stage</button></div>
        </form> : null}
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
          <h3 className="font-semibold">Custom fields</h3>
          <div className="mt-3 max-h-64 space-y-2 overflow-auto">
            {configuration.custom_fields.length ? configuration.custom_fields.map((field) => <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm" key={field.public_id}><div className="flex items-center justify-between gap-2"><span className="font-medium">{field.label}</span><span className="text-xs uppercase text-[var(--muted)]">{field.entity_type} · {field.field_type}</span></div><p className="mt-1 text-xs text-[var(--muted)]">{field.code}{field.is_required ? " · required" : ""}{field.source_pack_code ? ` · ${field.source_pack_code} pack` : ""}</p></div>) : <p className="text-sm text-[var(--muted)]">No custom fields yet.</p>}
          </div>
          {canManage ? <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={createField}>
            <label className="text-sm font-medium">Record<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="entity_type"><option value="lead">Lead</option><option value="contact">Contact</option><option value="customer">Customer</option><option value="opportunity">Opportunity</option></select></label>
            <label className="text-sm font-medium">Code<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="code" placeholder="vehicle_model" required /></label>
            <label className="text-sm font-medium">Label<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="label" placeholder="Vehicle model" required /></label>
            <label className="text-sm font-medium">Type<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="field_type"><option value="text">Text</option><option value="long_text">Long text</option><option value="number">Number</option><option value="currency">Currency</option><option value="percent">Percentage</option><option value="date">Date</option><option value="datetime">Date & time</option><option value="select">Dropdown</option><option value="multiselect">Multi-select</option><option value="boolean">Yes / no</option><option value="email">Email</option><option value="phone">Phone</option><option value="url">URL</option></select></label>
            <label className="text-sm font-medium sm:col-span-2">Options <span className="font-normal text-[var(--muted)]">(comma separated for dropdown)</span><input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="options" /></label>
            <label className="text-sm font-medium sm:col-span-2">Help text<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="help_text" /></label>
            <label className="flex items-center gap-2 text-sm font-medium"><input name="is_required" type="checkbox" /> Required</label>
            <div className="flex justify-end"><button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" disabled={busy} type="submit">Add field</button></div>
          </form> : null}
        </div>

        <div className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
          <h3 className="font-semibold">Lead sources</h3>
          <div className="mt-3 flex flex-wrap gap-2">{configuration.lead_sources.map((source) => <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold" key={source.public_id}>{source.name} · {source.channel_type}</span>)}</div>
          {canManage ? <form className="mt-5 grid gap-3 sm:grid-cols-2" onSubmit={createSource}>
            <label className="text-sm font-medium">Code<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="code" placeholder="dealer_referral" required /></label>
            <label className="text-sm font-medium">Name<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="name" placeholder="Dealer referral" required /></label>
            <label className="text-sm font-medium">Channel<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="channel_type"><option value="manual">Manual</option><option value="website">Website</option><option value="ads">Ads</option><option value="social">Social</option><option value="phone">Phone</option><option value="whatsapp">WhatsApp</option><option value="email">Email</option><option value="referral">Referral</option><option value="partner">Partner</option><option value="event">Event</option><option value="import">Import</option><option value="api">API</option><option value="other">Other</option></select></label>
            <div className="flex items-end justify-end"><button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" disabled={busy} type="submit">Add source</button></div>
          </form> : null}
        </div>
      </section>
      <Build360ErrorDialog message={error} onClose={() => setError("")} open={Boolean(error)} title="CRM configuration action could not be completed" />
      <Build360Toast message={notice} onDismiss={() => setNotice("")} />
    </div>
  );
}
