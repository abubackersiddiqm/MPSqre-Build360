"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import styles from "./digital-twin-operations.module.css";

type Scalar = string | number | boolean | null;
type Row = Record<string, Scalar | Record<string, unknown> | unknown[]>;
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: { status: string; version: number; coordinate_system: string; retention_days: number };
  metrics: Record<string, string | number>;
  models: Row[];
  revisions: Row[];
  federations: Row[];
  clashes: Row[];
  issues: Row[];
  devices: Row[];
  telemetry: Row[];
  alerts: Row[];
  assets: Row[];
};

type Tab = "summary" | "models" | "coordination" | "smart-site" | "handover";
type InputEvent = ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>;

const emptyModel = { code: "", name: "", discipline_code: "ARCHITECTURE", model_type_code: "AUTHORING", file_format_code: "IFC", authoring_tool: "", site_reference: "", storage_reference: "", checksum_sha256: "" };
const emptyRevision = { model_public_id: "", revision_code: "", issue_purpose_code: "COORDINATION", file_reference: "", checksum_sha256: "", notes: "" };
const emptyFederation = { code: "", name: "", model_public_ids: "", coordination_date: "" };
const emptyClash = { federation_public_id: "", clash_number: "", clash_type_code: "HARD", severity_code: "MEDIUM", discipline_a_code: "ARCHITECTURE", discipline_b_code: "STRUCTURE", title: "", description: "", location_reference: "", due_date: "" };
const emptyIssue = { issue_code: "", category_code: "COORDINATION", priority_code: "NORMAL", title: "", description: "", site_reference: "", model_public_id: "", revision_public_id: "", due_date: "" };
const emptyDevice = { code: "", name: "", device_type_code: "TEMPERATURE_SENSOR", provider_code: "GENERIC", protocol_code: "HTTP", metric_code: "TEMPERATURE", unit_code: "CELSIUS", site_reference: "", threshold_min: "", threshold_max: "", threshold_severity: "HIGH" };
const emptyTelemetry = { device_public_id: "", observed_at: "", numeric_value: "", text_value: "", quality_code: "GOOD", source_reference: "" };
const emptyAsset = { asset_tag: "", asset_name: "", classification_code: "MECHANICAL", site_reference: "", model_public_id: "", model_element_reference: "", serial_number: "", manufacturer: "", location_reference: "", commissioned_on: "", warranty_end_on: "", maintainable: true, document_references: "" };

function value(input: unknown): string {
  if (input === null || input === undefined) return "";
  return String(input);
}

function dateValue(input: unknown): string {
  const raw = value(input);
  if (!raw) return "—";
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? raw : parsed.toLocaleString();
}

function messageFrom(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const record = payload as Record<string, unknown>;
  if (typeof record.message === "string") return record.message;
  if (typeof record.detail === "string") return record.detail;
  const first = Object.values(record).find((item) => typeof item === "string" || Array.isArray(item));
  if (typeof first === "string") return first;
  if (Array.isArray(first)) return first.map(String).join(" ");
  return fallback;
}

function Metric({ label, value: metricValue, note }: { label: string; value: string | number; note: string }) {
  return <article className={styles.metric}><span>{label}</span><strong>{metricValue}</strong><small>{note}</small></article>;
}

function Status({ label }: { label: string }) {
  return <span className={styles.pill}>{label || "—"}</span>;
}

function Field({ label, children, wide = false }: { label: string; children?: ReactNode; wide?: boolean }) {
  return <label className={wide ? styles.full : undefined}><span>{label}</span>{children}</label>;
}

function nextRevision(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "PUBLISHED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextClash(status: string): string {
  if (status === "OPEN") return "IN_PROGRESS";
  if (status === "IN_PROGRESS") return "RESOLVED";
  if (status === "RESOLVED") return "VERIFIED";
  if (status === "VERIFIED") return "CLOSED";
  if (status === "BLOCKED") return "IN_PROGRESS";
  return "";
}

function nextIssue(status: string): string {
  if (status === "OPEN") return "IN_PROGRESS";
  if (status === "IN_PROGRESS") return "RESOLVED";
  if (status === "RESOLVED") return "CLOSED";
  if (status === "BLOCKED") return "IN_PROGRESS";
  return "";
}

function nextAlert(status: string): string {
  if (status === "OPEN") return "ACKNOWLEDGED";
  if (status === "ACKNOWLEDGED") return "RESOLVED";
  if (status === "RESOLVED") return "CLOSED";
  return "";
}

function nextAsset(status: string): string {
  if (status === "DRAFT") return "VERIFIED";
  if (status === "VERIFIED") return "HANDED_OVER";
  if (status === "HANDED_OVER") return "IN_SERVICE";
  if (status === "OUT_OF_SERVICE") return "IN_SERVICE";
  return "";
}

export function DigitalTwinOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [modelForm, setModelForm] = useState(emptyModel);
  const [revisionForm, setRevisionForm] = useState(emptyRevision);
  const [federationForm, setFederationForm] = useState(emptyFederation);
  const [clashForm, setClashForm] = useState(emptyClash);
  const [issueForm, setIssueForm] = useState(emptyIssue);
  const [deviceForm, setDeviceForm] = useState(emptyDevice);
  const [telemetryForm, setTelemetryForm] = useState(emptyTelemetry);
  const [assetForm, setAssetForm] = useState(emptyAsset);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/platform/digital-twin-operations/overview", { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(payload, "Digital twin operations could not be loaded."));
      setOverview(payload as Overview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Digital twin operations could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void refresh();
    });
    return () => controller.abort();
  }, [refresh]);

  async function post(path: string, body: Record<string, unknown>, success = "Digital twin record saved successfully.") {
    setWorking(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/platform/digital-twin-operations/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(payload, "The request could not be completed."));
      setNotice(success);
      await refresh();
      return payload as Record<string, unknown>;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The request could not be completed.");
      return null;
    } finally {
      setWorking(false);
    }
  }

  const modelOptions = overview?.models ?? [];
  const revisionOptions = overview?.revisions ?? [];
  const federationOptions = overview?.federations ?? [];
  const deviceOptions = overview?.devices ?? [];
  const latestTelemetry = useMemo(() => (overview?.telemetry ?? []).slice(0, 12), [overview]);

  if (loading && !overview) {
    return <main className={styles.shell}><section className={styles.state}><p className={styles.kicker}>DIGITAL TWIN CONTROL ROOM</p><h1>Preparing BIM and smart-site intelligence…</h1></section></main>;
  }

  if (!overview) {
    return <main className={styles.shell}><section className={styles.state}><p className={styles.kicker}>DIGITAL TWIN CONTROL UNAVAILABLE</p><h1>BIM, digital twin and smart-site operations could not be opened.</h1><p>{error}</p><button type="button" onClick={() => void refresh()}>Retry workspace</button></section></main>;
  }

  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 39</p>
          <h1>BIM, digital twin & smart site</h1>
          <p className={styles.lead}>Govern models, revisions, coordination clashes, digital issues, IoT telemetry, alerts and handover assets from one tenant-safe construction intelligence cockpit.</p>
          <div className={styles.badges}><span>{overview.company.name}</span><span>{overview.policy.coordinate_system}</span><span>Policy {overview.policy.status}</span><span>{overview.policy.retention_days} day telemetry retention</span></div>
        </div>
        <div className={styles.heroAction}><span>PHASE 39 DIGITAL TWIN OPERATIONS ACTIVE</span><button type="button" onClick={() => void refresh()} disabled={loading}>Refresh twin cockpit</button></div>
      </header>

      {error ? <div className={styles.error}>{error}</div> : null}
      {notice ? <div className={styles.notice}>{notice}</div> : null}

      <section className={styles.metrics}>
        <Metric label="Published models" value={overview.metrics.published_models ?? 0} note={`${overview.metrics.pending_model_reviews ?? 0} pending reviews`} />
        <Metric label="Open clashes" value={overview.metrics.open_clashes ?? 0} note={`${overview.metrics.critical_clashes ?? 0} critical`} />
        <Metric label="Open BIM issues" value={overview.metrics.open_issues ?? 0} note="Coordination through closure" />
        <Metric label="Online devices" value={overview.metrics.online_devices ?? 0} note={`${overview.metrics.stale_devices ?? 0} stale or unseen`} />
        <Metric label="Open alerts" value={overview.metrics.open_alerts ?? 0} note={`${overview.metrics.critical_alerts ?? 0} critical`} />
        <Metric label="Handover assets" value={overview.metrics.handover_assets ?? 0} note={`${overview.metrics.handed_over_assets ?? 0} operationally handed over`} />
      </section>

      <nav className={styles.tabs} aria-label="Digital twin operations tabs">
        {(["summary", "models", "coordination", "smart-site", "handover"] as Tab[]).map((item) => (
          <button key={item} type="button" className={tab === item ? styles.activeTab : ""} onClick={() => setTab(item)}>{item.replace("-", " ")}</button>
        ))}
      </nav>

      {tab === "summary" ? (
        <section className={styles.grid}>
          <article className={styles.card}><p className={styles.kicker}>MODEL GOVERNANCE</p><h2>Information readiness</h2><div className={styles.summaryList}><div><span>Registered models</span><strong>{overview.models.length}</strong></div><div><span>Recent revisions</span><strong>{overview.revisions.length}</strong></div><div><span>Federations</span><strong>{overview.federations.length}</strong></div><div><span>Pending reviews</span><strong>{overview.metrics.pending_model_reviews ?? 0}</strong></div></div></article>
          <article className={styles.card}><p className={styles.kicker}>SMART SITE ASSURANCE</p><h2>Operational signal</h2><div className={styles.summaryList}><div><span>Devices</span><strong>{overview.devices.length}</strong></div><div><span>Readings in 24h</span><strong>{overview.metrics.telemetry_readings_24h ?? 0}</strong></div><div><span>Open alerts</span><strong>{overview.metrics.open_alerts ?? 0}</strong></div><div><span>Critical alerts</span><strong>{overview.metrics.critical_alerts ?? 0}</strong></div></div></article>
          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>EXECUTION EXPOSURE</p><h2>Priority coordination and alert queue</h2><div className={styles.tableWrap}><table><thead><tr><th>Record</th><th>Type</th><th>Severity / priority</th><th>Status</th><th>Due / triggered</th></tr></thead><tbody>{overview.clashes.slice(0, 8).map((item) => <tr key={`summary-clash-${value(item.public_id)}`}><td><strong>{value(item.clash_number)}</strong><small>{value(item.title)}</small></td><td>Clash · {value(item.federation__code)}</td><td>{value(item.severity_code)}</td><td><Status label={value(item.status_code)} /></td><td>{dateValue(item.due_date)}</td></tr>)}{overview.alerts.slice(0, 8).map((item) => <tr key={`summary-alert-${value(item.public_id)}`}><td><strong>{value(item.alert_code)}</strong><small>{value(item.message)}</small></td><td>Smart alert · {value(item.device__code)}</td><td>{value(item.severity_code)}</td><td><Status label={value(item.status_code)} /></td><td>{dateValue(item.triggered_at)}</td></tr>)}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "models" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("models", modelForm, "BIM model registered."); setModelForm(emptyModel); }}>
            <p className={styles.kicker}>MODEL REGISTER</p><h2>Register BIM model</h2>
            <div className={styles.formGrid}>
              <Field label="Model code"><input required value={modelForm.code} onChange={(event: InputEvent) => setModelForm({ ...modelForm, code: event.target.value })} /></Field>
              <Field label="Discipline"><select value={modelForm.discipline_code} onChange={(event: InputEvent) => setModelForm({ ...modelForm, discipline_code: event.target.value })}><option>ARCHITECTURE</option><option>STRUCTURE</option><option>MEP</option><option>CIVIL</option><option>LANDSCAPE</option><option>INTERIORS</option></select></Field>
              <Field label="Model name" wide><input required value={modelForm.name} onChange={(event: InputEvent) => setModelForm({ ...modelForm, name: event.target.value })} /></Field>
              <Field label="Model type"><select value={modelForm.model_type_code} onChange={(event: InputEvent) => setModelForm({ ...modelForm, model_type_code: event.target.value })}><option>AUTHORING</option><option>FEDERATED</option><option>AS_BUILT</option><option>FABRICATION</option></select></Field>
              <Field label="File format"><select value={modelForm.file_format_code} onChange={(event: InputEvent) => setModelForm({ ...modelForm, file_format_code: event.target.value })}><option>IFC</option><option>RVT</option><option>NWD</option><option>DWG</option><option>BCF</option><option>OTHER</option></select></Field>
              <Field label="Authoring tool"><input value={modelForm.authoring_tool} onChange={(event: InputEvent) => setModelForm({ ...modelForm, authoring_tool: event.target.value })} /></Field>
              <Field label="Site reference"><input value={modelForm.site_reference} onChange={(event: InputEvent) => setModelForm({ ...modelForm, site_reference: event.target.value })} /></Field>
              <Field label="Storage reference" wide><input value={modelForm.storage_reference} onChange={(event: InputEvent) => setModelForm({ ...modelForm, storage_reference: event.target.value })} placeholder="Provider-neutral file or document reference" /></Field>
              <Field label="SHA-256 checksum" wide><input minLength={64} maxLength={64} value={modelForm.checksum_sha256} onChange={(event: InputEvent) => setModelForm({ ...modelForm, checksum_sha256: event.target.value })} /></Field>
            </div><button disabled={working}>Register model</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("revisions", revisionForm, "BIM revision created."); setRevisionForm(emptyRevision); }}>
            <p className={styles.kicker}>REVISION CONTROL</p><h2>Create model revision</h2>
            <div className={styles.formGrid}>
              <Field label="Model" wide><select required value={revisionForm.model_public_id} onChange={(event: InputEvent) => setRevisionForm({ ...revisionForm, model_public_id: event.target.value })}><option value="">Select model</option>{modelOptions.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field>
              <Field label="Revision"><input required value={revisionForm.revision_code} onChange={(event: InputEvent) => setRevisionForm({ ...revisionForm, revision_code: event.target.value })} /></Field>
              <Field label="Issue purpose"><select value={revisionForm.issue_purpose_code} onChange={(event: InputEvent) => setRevisionForm({ ...revisionForm, issue_purpose_code: event.target.value })}><option>COORDINATION</option><option>REVIEW</option><option>CONSTRUCTION</option><option>AS_BUILT</option><option>HANDOVER</option></select></Field>
              <Field label="File reference" wide><input required value={revisionForm.file_reference} onChange={(event: InputEvent) => setRevisionForm({ ...revisionForm, file_reference: event.target.value })} /></Field>
              <Field label="SHA-256 checksum" wide><input minLength={64} maxLength={64} value={revisionForm.checksum_sha256} onChange={(event: InputEvent) => setRevisionForm({ ...revisionForm, checksum_sha256: event.target.value })} /></Field>
              <Field label="Notes" wide><textarea value={revisionForm.notes} onChange={(event: InputEvent) => setRevisionForm({ ...revisionForm, notes: event.target.value })} /></Field>
            </div><button disabled={working}>Create revision</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>MODEL INFORMATION</p><h2>Models and revision approvals</h2><div className={styles.tableWrap}><table><thead><tr><th>Model / revision</th><th>Discipline / purpose</th><th>Format</th><th>Status</th><th>Published</th><th>Control</th></tr></thead><tbody>{overview.models.map((item) => <tr key={`model-${value(item.public_id)}`}><td><strong>{value(item.code)}</strong><small>{value(item.name)}</small></td><td>{value(item.discipline_code)}</td><td>{value(item.file_format_code)}</td><td><Status label={value(item.status_code)} /></td><td>{value(item.current_revision_code) || "—"}</td><td>v{value(item.version)}</td></tr>)}{overview.revisions.map((item) => { const status = value(item.status_code); const next = nextRevision(status); return <tr key={`revision-${value(item.public_id)}`}><td><strong>{value(item.model__code)} · {value(item.revision_code)}</strong><small>Revision record</small></td><td>{value(item.issue_purpose_code)}</td><td>Controlled file</td><td><Status label={status} /></td><td>{dateValue(item.approved_at)}</td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`revisions/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version) }, `Revision moved to ${next}.`)}>{next.replace("_", " ")}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "coordination" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const model_public_ids = federationForm.model_public_ids.split(",").map((item) => item.trim()).filter(Boolean); void post("federations", { ...federationForm, model_public_ids }, "Model federation created."); setFederationForm(emptyFederation); }}>
            <p className={styles.kicker}>MODEL FEDERATION</p><h2>Create coordination set</h2><div className={styles.formGrid}>
              <Field label="Federation code"><input required value={federationForm.code} onChange={(event: InputEvent) => setFederationForm({ ...federationForm, code: event.target.value })} /></Field>
              <Field label="Coordination date"><input type="date" value={federationForm.coordination_date} onChange={(event: InputEvent) => setFederationForm({ ...federationForm, coordination_date: event.target.value })} /></Field>
              <Field label="Name" wide><input required value={federationForm.name} onChange={(event: InputEvent) => setFederationForm({ ...federationForm, name: event.target.value })} /></Field>
              <Field label="Model public IDs" wide><textarea value={federationForm.model_public_ids} onChange={(event: InputEvent) => setFederationForm({ ...federationForm, model_public_ids: event.target.value })} placeholder="Comma-separated model public IDs" /></Field>
            </div><button disabled={working}>Create federation</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("clashes", clashForm, "Coordination clash registered."); setClashForm(emptyClash); }}>
            <p className={styles.kicker}>CLASH CONTROL</p><h2>Register coordination clash</h2><div className={styles.formGrid}>
              <Field label="Federation" wide><select required value={clashForm.federation_public_id} onChange={(event: InputEvent) => setClashForm({ ...clashForm, federation_public_id: event.target.value })}><option value="">Select federation</option>{federationOptions.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field>
              <Field label="Clash number"><input required value={clashForm.clash_number} onChange={(event: InputEvent) => setClashForm({ ...clashForm, clash_number: event.target.value })} /></Field>
              <Field label="Severity"><select value={clashForm.severity_code} onChange={(event: InputEvent) => setClashForm({ ...clashForm, severity_code: event.target.value })}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></Field>
              <Field label="Discipline A"><input required value={clashForm.discipline_a_code} onChange={(event: InputEvent) => setClashForm({ ...clashForm, discipline_a_code: event.target.value })} /></Field>
              <Field label="Discipline B"><input required value={clashForm.discipline_b_code} onChange={(event: InputEvent) => setClashForm({ ...clashForm, discipline_b_code: event.target.value })} /></Field>
              <Field label="Title" wide><input required value={clashForm.title} onChange={(event: InputEvent) => setClashForm({ ...clashForm, title: event.target.value })} /></Field>
              <Field label="Location"><input value={clashForm.location_reference} onChange={(event: InputEvent) => setClashForm({ ...clashForm, location_reference: event.target.value })} /></Field>
              <Field label="Due date"><input type="date" value={clashForm.due_date} onChange={(event: InputEvent) => setClashForm({ ...clashForm, due_date: event.target.value })} /></Field>
              <Field label="Description" wide><textarea value={clashForm.description} onChange={(event: InputEvent) => setClashForm({ ...clashForm, description: event.target.value })} /></Field>
            </div><button disabled={working}>Register clash</button>
          </form>

          <form className={`${styles.card} ${styles.wide}`} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const payload = { ...issueForm, model_public_id: issueForm.model_public_id || null, revision_public_id: issueForm.revision_public_id || null }; void post("issues", payload, "BIM issue created."); setIssueForm(emptyIssue); }}>
            <p className={styles.kicker}>ISSUE GOVERNANCE</p><h2>Create BIM issue</h2><div className={styles.formGrid}>
              <Field label="Issue code"><input required value={issueForm.issue_code} onChange={(event: InputEvent) => setIssueForm({ ...issueForm, issue_code: event.target.value })} /></Field>
              <Field label="Priority"><select value={issueForm.priority_code} onChange={(event: InputEvent) => setIssueForm({ ...issueForm, priority_code: event.target.value })}><option>LOW</option><option>NORMAL</option><option>HIGH</option><option>CRITICAL</option></select></Field>
              <Field label="Category"><select value={issueForm.category_code} onChange={(event: InputEvent) => setIssueForm({ ...issueForm, category_code: event.target.value })}><option>COORDINATION</option><option>DESIGN</option><option>CONSTRUCTABILITY</option><option>INFORMATION</option><option>FIELD_CHANGE</option><option>HANDOVER</option></select></Field>
              <Field label="Due date"><input type="date" value={issueForm.due_date} onChange={(event: InputEvent) => setIssueForm({ ...issueForm, due_date: event.target.value })} /></Field>
              <Field label="Model"><select value={issueForm.model_public_id} onChange={(event: InputEvent) => setIssueForm({ ...issueForm, model_public_id: event.target.value })}><option value="">No model</option>{modelOptions.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)}</option>)}</select></Field>
              <Field label="Revision"><select value={issueForm.revision_public_id} onChange={(event: InputEvent) => setIssueForm({ ...issueForm, revision_public_id: event.target.value })}><option value="">No revision</option>{revisionOptions.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.model__code)} · {value(item.revision_code)}</option>)}</select></Field>
              <Field label="Title" wide><input required value={issueForm.title} onChange={(event: InputEvent) => setIssueForm({ ...issueForm, title: event.target.value })} /></Field>
              <Field label="Description" wide><textarea value={issueForm.description} onChange={(event: InputEvent) => setIssueForm({ ...issueForm, description: event.target.value })} /></Field>
            </div><button disabled={working}>Create issue</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>COORDINATION QUEUE</p><h2>Clashes and BIM issues</h2><div className={styles.tableWrap}><table><thead><tr><th>Record</th><th>Category</th><th>Severity / priority</th><th>Status</th><th>Due</th><th>Control</th></tr></thead><tbody>{overview.clashes.map((item) => { const status = value(item.status_code); const next = nextClash(status); return <tr key={`clash-${value(item.public_id)}`}><td><strong>{value(item.clash_number)}</strong><small>{value(item.title)}</small></td><td>{value(item.discipline_a_code)} / {value(item.discipline_b_code)}</td><td>{value(item.severity_code)}</td><td><Status label={status} /></td><td>{dateValue(item.due_date)}</td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`clashes/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), resolution_note: next === "RESOLVED" ? "Resolved through coordination workflow." : "" }, `Clash moved to ${next}.`)}>{next.replace("_", " ")}</button> : "—"}</td></tr>; })}{overview.issues.map((item) => { const status = value(item.status_code); const next = nextIssue(status); return <tr key={`issue-${value(item.public_id)}`}><td><strong>{value(item.issue_code)}</strong><small>{value(item.title)}</small></td><td>{value(item.category_code)}</td><td>{value(item.priority_code)}</td><td><Status label={status} /></td><td>{dateValue(item.due_date)}</td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`issues/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version) }, `Issue moved to ${next}.`)}>{next.replace("_", " ")}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "smart-site" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const threshold_configuration: Record<string, unknown> = { severity: deviceForm.threshold_severity }; if (deviceForm.threshold_min !== "") threshold_configuration.min = Number(deviceForm.threshold_min); if (deviceForm.threshold_max !== "") threshold_configuration.max = Number(deviceForm.threshold_max); const payload = { ...deviceForm, threshold_configuration }; delete (payload as Partial<typeof deviceForm>).threshold_min; delete (payload as Partial<typeof deviceForm>).threshold_max; delete (payload as Partial<typeof deviceForm>).threshold_severity; void post("devices", payload, "Smart-site device registered."); setDeviceForm(emptyDevice); }}>
            <p className={styles.kicker}>DEVICE REGISTRY</p><h2>Register IoT device</h2><div className={styles.formGrid}>
              <Field label="Device code"><input required value={deviceForm.code} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, code: event.target.value })} /></Field>
              <Field label="Device type"><input required value={deviceForm.device_type_code} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, device_type_code: event.target.value })} /></Field>
              <Field label="Device name" wide><input required value={deviceForm.name} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, name: event.target.value })} /></Field>
              <Field label="Metric"><input required value={deviceForm.metric_code} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, metric_code: event.target.value })} /></Field>
              <Field label="Unit"><input required value={deviceForm.unit_code} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, unit_code: event.target.value })} /></Field>
              <Field label="Provider"><input value={deviceForm.provider_code} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, provider_code: event.target.value })} /></Field>
              <Field label="Protocol"><select value={deviceForm.protocol_code} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, protocol_code: event.target.value })}><option>HTTP</option><option>MQTT</option><option>MODBUS</option><option>LORAWAN</option><option>OPC_UA</option></select></Field>
              <Field label="Minimum threshold"><input type="number" step="any" value={deviceForm.threshold_min} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, threshold_min: event.target.value })} /></Field>
              <Field label="Maximum threshold"><input type="number" step="any" value={deviceForm.threshold_max} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, threshold_max: event.target.value })} /></Field>
              <Field label="Alert severity"><select value={deviceForm.threshold_severity} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, threshold_severity: event.target.value })}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></Field>
              <Field label="Site reference"><input value={deviceForm.site_reference} onChange={(event: InputEvent) => setDeviceForm({ ...deviceForm, site_reference: event.target.value })} /></Field>
            </div><button disabled={working}>Register device</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const payload = { ...telemetryForm, numeric_value: telemetryForm.numeric_value === "" ? null : telemetryForm.numeric_value, observed_at: telemetryForm.observed_at ? new Date(telemetryForm.observed_at).toISOString() : new Date().toISOString() }; void post("telemetry", payload, "Telemetry recorded and thresholds evaluated."); setTelemetryForm(emptyTelemetry); }}>
            <p className={styles.kicker}>TELEMETRY INGESTION</p><h2>Record smart-site reading</h2><div className={styles.formGrid}>
              <Field label="Device" wide><select required value={telemetryForm.device_public_id} onChange={(event: InputEvent) => setTelemetryForm({ ...telemetryForm, device_public_id: event.target.value })}><option value="">Select device</option>{deviceOptions.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.metric_code)} ({value(item.unit_code)})</option>)}</select></Field>
              <Field label="Observed at"><input type="datetime-local" value={telemetryForm.observed_at} onChange={(event: InputEvent) => setTelemetryForm({ ...telemetryForm, observed_at: event.target.value })} /></Field>
              <Field label="Quality"><select value={telemetryForm.quality_code} onChange={(event: InputEvent) => setTelemetryForm({ ...telemetryForm, quality_code: event.target.value })}><option>GOOD</option><option>UNCERTAIN</option><option>BAD</option></select></Field>
              <Field label="Numeric value"><input type="number" step="any" value={telemetryForm.numeric_value} onChange={(event: InputEvent) => setTelemetryForm({ ...telemetryForm, numeric_value: event.target.value })} /></Field>
              <Field label="Text value"><input value={telemetryForm.text_value} onChange={(event: InputEvent) => setTelemetryForm({ ...telemetryForm, text_value: event.target.value })} /></Field>
              <Field label="Source reference" wide><input value={telemetryForm.source_reference} onChange={(event: InputEvent) => setTelemetryForm({ ...telemetryForm, source_reference: event.target.value })} /></Field>
            </div><button disabled={working}>Record telemetry</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>SMART SITE MONITORING</p><h2>Devices, readings and alerts</h2><div className={styles.tableWrap}><table><thead><tr><th>Device / alert</th><th>Metric</th><th>Value / message</th><th>Status / quality</th><th>Observed</th><th>Control</th></tr></thead><tbody>{overview.devices.map((item) => <tr key={`device-${value(item.public_id)}`}><td><strong>{value(item.code)}</strong><small>{value(item.name)}</small></td><td>{value(item.metric_code)} · {value(item.unit_code)}</td><td>{JSON.stringify(item.threshold_configuration ?? {})}</td><td><Status label={value(item.status_code)} /></td><td>{dateValue(item.last_seen_at)}</td><td>v{value(item.version)}</td></tr>)}{latestTelemetry.map((item) => <tr key={`telemetry-${value(item.public_id)}`}><td><strong>{value(item.device__code)}</strong><small>Telemetry reading</small></td><td>{value(item.metric_code)} · {value(item.unit_code)}</td><td>{value(item.numeric_value) || value(item.text_value)}</td><td><Status label={value(item.quality_code)} /></td><td>{dateValue(item.observed_at)}</td><td>Recorded</td></tr>)}{overview.alerts.map((item) => { const status = value(item.status_code); const next = nextAlert(status); return <tr key={`alert-${value(item.public_id)}`}><td><strong>{value(item.alert_code)}</strong><small>{value(item.device__code)}</small></td><td>{value(item.alert_type_code)}</td><td>{value(item.message)}</td><td><Status label={`${value(item.severity_code)} · ${status}`} /></td><td>{dateValue(item.triggered_at)}</td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`alerts/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version) }, `Alert moved to ${next}.`)}>{next.replace("_", " ")}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "handover" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const payload = { ...assetForm, model_public_id: assetForm.model_public_id || null, document_references: assetForm.document_references.split(",").map((item) => item.trim()).filter(Boolean) }; void post("assets", payload, "Digital handover asset registered."); setAssetForm(emptyAsset); }}>
            <p className={styles.kicker}>DIGITAL HANDOVER</p><h2>Register maintainable asset</h2><div className={styles.formGrid}>
              <Field label="Asset tag"><input required value={assetForm.asset_tag} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, asset_tag: event.target.value })} /></Field>
              <Field label="Classification"><input required value={assetForm.classification_code} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, classification_code: event.target.value })} /></Field>
              <Field label="Asset name" wide><input required value={assetForm.asset_name} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, asset_name: event.target.value })} /></Field>
              <Field label="BIM model"><select value={assetForm.model_public_id} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, model_public_id: event.target.value })}><option value="">No model</option>{modelOptions.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)}</option>)}</select></Field>
              <Field label="Element reference"><input value={assetForm.model_element_reference} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, model_element_reference: event.target.value })} /></Field>
              <Field label="Manufacturer"><input value={assetForm.manufacturer} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, manufacturer: event.target.value })} /></Field>
              <Field label="Serial number"><input value={assetForm.serial_number} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, serial_number: event.target.value })} /></Field>
              <Field label="Site reference"><input value={assetForm.site_reference} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, site_reference: event.target.value })} /></Field>
              <Field label="Location"><input value={assetForm.location_reference} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, location_reference: event.target.value })} /></Field>
              <Field label="Commissioned on"><input type="date" value={assetForm.commissioned_on} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, commissioned_on: event.target.value })} /></Field>
              <Field label="Warranty end"><input type="date" value={assetForm.warranty_end_on} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, warranty_end_on: event.target.value })} /></Field>
              <Field label="Document references" wide><textarea value={assetForm.document_references} onChange={(event: InputEvent) => setAssetForm({ ...assetForm, document_references: event.target.value })} placeholder="Comma-separated O&M manuals, warranties and certificates" /></Field>
              <label className={styles.check}><input type="checkbox" checked={assetForm.maintainable} onChange={(event: ChangeEvent<HTMLInputElement>) => setAssetForm({ ...assetForm, maintainable: event.target.checked })} /> Maintainable asset</label>
            </div><button disabled={working}>Register handover asset</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>ASSET INFORMATION MODEL</p><h2>Handover and operational asset register</h2><div className={styles.tableWrap}><table><thead><tr><th>Asset</th><th>Classification</th><th>Model / location</th><th>Commissioned / warranty</th><th>Status</th><th>Control</th></tr></thead><tbody>{overview.assets.map((item) => { const status = value(item.operation_status_code); const next = nextAsset(status); return <tr key={`asset-${value(item.public_id)}`}><td><strong>{value(item.asset_tag)}</strong><small>{value(item.asset_name)}</small></td><td>{value(item.classification_code)}{item.maintainable ? " · Maintainable" : ""}</td><td>{value(item.model_element_reference) || "—"}<small>{value(item.site_reference)}</small></td><td>{dateValue(item.commissioned_on)}<small>Warranty: {dateValue(item.warranty_end_on)}</small></td><td><Status label={status} /></td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`assets/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version) }, `Asset moved to ${next}.`)}>{next.replace("_", " ")}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}
    </main>
  );
}
