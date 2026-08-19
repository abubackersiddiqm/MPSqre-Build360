"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import styles from "./facilities-operations.module.css";

type Row = Record<string, unknown>;
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: { status: string; version: number; preventive_horizon_days: number; warranty_alert_days: number };
  metrics: Record<string, string | number>;
  facilities: Row[];
  spaces: Row[];
  assets: Row[];
  maintenance_plans: Row[];
  work_orders: Row[];
  service_requests: Row[];
  warranty_claims: Row[];
  inspections: Row[];
  lifecycle_events: Row[];
};

type Tab = "summary" | "facilities" | "assets" | "maintenance" | "service" | "warranty";
type InputEvent = ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>;

const emptyFacility = { code: "", name: "", facility_type_code: "BUILDING", site_reference: "", timezone: "", gross_area: "", area_unit_code: "SQ_M", occupancy_capacity: "", operational_from: "" };
const emptySpace = { facility_public_id: "", parent_public_id: "", code: "", name: "", space_type_code: "ROOM", floor_reference: "", area: "", area_unit_code: "SQ_M", criticality_code: "NORMAL" };
const emptyAsset = { facility_public_id: "", space_public_id: "", asset_tag: "", asset_name: "", classification_code: "HVAC", source_handover_public_id: "", model_element_reference: "", manufacturer: "", model_number: "", serial_number: "", commissioned_on: "", warranty_start_on: "", warranty_end_on: "", criticality_code: "NORMAL", condition_code: "GOOD", maintainable: true, service_interval_days: "", next_service_on: "", document_references: "" };
const emptyPlan = { asset_public_id: "", code: "", name: "", plan_type_code: "PREVENTIVE", frequency_days: "90", lead_time_days: "7", next_due_date: "", estimated_duration_minutes: "60", checklist: "" };
const emptyWorkOrder = { asset_public_id: "", plan_public_id: "", service_request_public_id: "", work_order_number: "", work_type_code: "CORRECTIVE", priority_code: "NORMAL", title: "", description: "", vendor_reference: "", due_date: "", estimated_cost: "" };
const emptyRequest = { facility_public_id: "", space_public_id: "", asset_public_id: "", request_number: "", category_code: "GENERAL", priority_code: "NORMAL", channel_code: "PORTAL", requester_reference: "", title: "", description: "" };
const emptyClaim = { asset_public_id: "", work_order_public_id: "", claim_number: "", supplier_reference: "", warranty_reference: "", reported_on: "", failure_date: "", issue_description: "", claimed_amount: "" };
const emptyInspection = { facility_public_id: "", space_public_id: "", asset_public_id: "", inspection_number: "", inspection_type_code: "CONDITION", scheduled_on: "", inspected_on: "", condition_code: "GOOD", score: "", findings: "", actions_required: "" };

function value(input: unknown): string {
  if (input === null || input === undefined) return "";
  return String(input);
}

function displayDate(input: unknown): string {
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

function nullable(input: string): string | null {
  return input.trim() ? input.trim() : null;
}

function numberOrNull(input: string): string | null {
  return input.trim() ? input : null;
}

function Metric({ label, metric, note }: { label: string; metric: string | number; note: string }) {
  return <article className={styles.metric}><span>{label}</span><strong>{metric}</strong><small>{note}</small></article>;
}

function Status({ label }: { label: string }) {
  return <span className={styles.pill}>{label || "—"}</span>;
}

function Field({ label, children, wide = false }: { label: string; children?: ReactNode; wide?: boolean }) {
  return <label className={wide ? styles.full : undefined}><span>{label}</span>{children}</label>;
}

function nextAsset(status: string): string {
  if (status === "DRAFT") return "VERIFIED";
  if (status === "VERIFIED") return "IN_SERVICE";
  if (status === "IN_SERVICE") return "OUT_OF_SERVICE";
  if (status === "OUT_OF_SERVICE") return "IN_SERVICE";
  if (status === "DECOMMISSIONED") return "RETIRED";
  return "";
}

function nextRequest(status: string): string {
  if (status === "NEW") return "ACKNOWLEDGED";
  if (status === "ACKNOWLEDGED") return "ASSIGNED";
  if (status === "ASSIGNED") return "IN_PROGRESS";
  if (status === "IN_PROGRESS") return "RESOLVED";
  if (status === "RESOLVED") return "CLOSED";
  if (status === "REOPENED") return "IN_PROGRESS";
  if (status === "ON_HOLD") return "IN_PROGRESS";
  return "";
}

function nextWorkOrder(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "IN_PROGRESS";
  if (status === "SCHEDULED") return "IN_PROGRESS";
  if (status === "IN_PROGRESS") return "COMPLETED";
  if (status === "COMPLETED") return "VERIFIED";
  if (status === "VERIFIED") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  if (status === "ON_HOLD") return "IN_PROGRESS";
  return "";
}

function nextClaim(status: string): string {
  if (status === "DRAFT") return "FILED";
  if (status === "FILED") return "UNDER_REVIEW";
  if (status === "UNDER_REVIEW") return "APPROVED";
  if (status === "INFO_REQUIRED") return "UNDER_REVIEW";
  if (status === "APPROVED") return "SETTLED";
  if (status === "SETTLED" || status === "REJECTED") return "CLOSED";
  return "";
}

function nextInspection(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "VERIFIED";
  if (status === "VERIFIED") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

export function FacilitiesOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [facilityForm, setFacilityForm] = useState(emptyFacility);
  const [spaceForm, setSpaceForm] = useState(emptySpace);
  const [assetForm, setAssetForm] = useState(emptyAsset);
  const [planForm, setPlanForm] = useState(emptyPlan);
  const [workOrderForm, setWorkOrderForm] = useState(emptyWorkOrder);
  const [requestForm, setRequestForm] = useState(emptyRequest);
  const [claimForm, setClaimForm] = useState(emptyClaim);
  const [inspectionForm, setInspectionForm] = useState(emptyInspection);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/platform/facilities-operations/overview", { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(payload, "Facilities operations could not be loaded."));
      setOverview(payload as Overview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Facilities operations could not be loaded.");
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

  async function post(path: string, body: Record<string, unknown>, success: string) {
    setWorking(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/platform/facilities-operations/${path}`, {
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

  const facilities = overview?.facilities ?? [];
  const spaces = overview?.spaces ?? [];
  const assets = overview?.assets ?? [];
  const plans = overview?.maintenance_plans ?? [];
  const requests = overview?.service_requests ?? [];
  const workOrders = overview?.work_orders ?? [];
  const recentEvents = useMemo(() => (overview?.lifecycle_events ?? []).slice(0, 12), [overview]);

  if (loading && !overview) {
    return <main className={styles.shell}><section className={styles.loading}>Preparing the facilities operations cockpit…</section></main>;
  }

  if (!overview) {
    return <main className={styles.shell}><section className={styles.errorCard}><p className={styles.kicker}>FACILITIES CONTROL UNAVAILABLE</p><h2>Facilities, maintenance and warranty operations could not be opened.</h2><p>{error || "The request could not be completed."}</p><button type="button" onClick={() => void refresh()}>Retry workspace</button></section></main>;
  }

  const metrics = overview.metrics;

  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 40</p>
          <h1>Facilities, asset lifecycle & warranty</h1>
          <p className={styles.lead}>Operate buildings and spaces, maintain handed-over assets, resolve service requests, recover warranty value and preserve condition evidence from one tenant-safe control room.</p>
          <div className={styles.tags}><span>{overview.company.name}</span><span>{overview.company.currency}</span><span>{overview.company.timezone}</span><span>Policy {overview.policy.status}</span></div>
        </div>
        <div className={styles.heroActions}><span className={styles.activeLabel}>PHASE 40 FACILITIES OPERATIONS ACTIVE</span><button type="button" onClick={() => void refresh()} disabled={loading}>Refresh facility cockpit</button></div>
      </header>

      {error ? <div className={styles.alert}>{error}</div> : null}
      {notice ? <div className={styles.notice}>{notice}</div> : null}

      <section className={styles.metrics}>
        <Metric label="Active facilities" metric={metrics.active_facilities ?? 0} note={`${metrics.managed_spaces ?? 0} governed spaces`} />
        <Metric label="Operational assets" metric={metrics.operational_assets ?? 0} note={`${metrics.asset_availability ?? "0.00"}% in service`} />
        <Metric label="Maintenance exposure" metric={metrics.service_due ?? 0} note={`${metrics.overdue_work_orders ?? 0} overdue work orders`} />
        <Metric label="Service requests" metric={metrics.open_service_requests ?? 0} note={`${metrics.sla_breaches ?? 0} SLA breaches`} />
        <Metric label="Warranty watch" metric={metrics.active_warranty_claims ?? 0} note={`${metrics.warranties_expiring ?? 0} expiring soon`} />
        <Metric label="Condition risk" metric={metrics.critical_condition ?? 0} note={`${metrics.pending_inspections ?? 0} inspections pending`} />
      </section>

      <nav className={styles.tabs} aria-label="Facilities operations sections">
        {(["summary", "facilities", "assets", "maintenance", "service", "warranty"] as Tab[]).map((item) => (
          <button key={item} type="button" className={tab === item ? styles.selected : ""} onClick={() => setTab(item)}>{item === "service" ? "Service requests" : item === "warranty" ? "Warranty & inspections" : item.charAt(0).toUpperCase() + item.slice(1)}</button>
        ))}
      </nav>

      {tab === "summary" ? (
        <section className={styles.grid}>
          <article className={styles.card}><p className={styles.kicker}>OPERATING POSTURE</p><h2>Lifecycle assurance</h2><dl className={styles.definition}><div><dt>Preventive horizon</dt><dd>{overview.policy.preventive_horizon_days} days</dd></div><div><dt>Warranty alert</dt><dd>{overview.policy.warranty_alert_days} days</dd></div><div><dt>Asset availability</dt><dd>{metrics.asset_availability ?? "0.00"}%</dd></div><div><dt>Critical condition</dt><dd>{metrics.critical_condition ?? 0}</dd></div></dl></article>
          <article className={styles.card}><p className={styles.kicker}>EXECUTION FOCUS</p><h2>Operational exposure</h2><dl className={styles.definition}><div><dt>Service due</dt><dd>{metrics.service_due ?? 0}</dd></div><div><dt>Overdue work orders</dt><dd>{metrics.overdue_work_orders ?? 0}</dd></div><div><dt>Open requests</dt><dd>{metrics.open_service_requests ?? 0}</dd></div><div><dt>SLA breaches</dt><dd>{metrics.sla_breaches ?? 0}</dd></div></dl></article>
          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>ASSET HISTORY</p><h2>Recent lifecycle events</h2><div className={styles.tableWrap}><table><thead><tr><th>Asset</th><th>Event</th><th>Summary</th><th>Transition</th><th>Occurred</th></tr></thead><tbody>{recentEvents.length ? recentEvents.map((item) => <tr key={value(item.public_id)}><td><strong>{value(item.asset__asset_tag)}</strong></td><td><Status label={value(item.event_type_code)} /></td><td>{value(item.summary)}</td><td>{value(item.from_status_code) || "—"} → {value(item.to_status_code) || "—"}</td><td>{displayDate(item.occurred_at)}</td></tr>) : <tr><td colSpan={5}>No lifecycle evidence has been recorded.</td></tr>}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "facilities" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("facilities", { ...facilityForm, gross_area: numberOrNull(facilityForm.gross_area), occupancy_capacity: numberOrNull(facilityForm.occupancy_capacity), operational_from: nullable(facilityForm.operational_from) }, "Facility registered."); setFacilityForm(emptyFacility); }}>
            <p className={styles.kicker}>FACILITY MASTER</p><h2>Register operational facility</h2><div className={styles.formGrid}>
              <Field label="Facility code"><input required value={facilityForm.code} onChange={(e: InputEvent) => setFacilityForm({ ...facilityForm, code: e.target.value })} /></Field>
              <Field label="Type"><select value={facilityForm.facility_type_code} onChange={(e: InputEvent) => setFacilityForm({ ...facilityForm, facility_type_code: e.target.value })}><option>BUILDING</option><option>WAREHOUSE</option><option>PLANT</option><option>CAMPUS</option><option>INFRASTRUCTURE</option></select></Field>
              <Field label="Facility name" wide><input required value={facilityForm.name} onChange={(e: InputEvent) => setFacilityForm({ ...facilityForm, name: e.target.value })} /></Field>
              <Field label="Site reference"><input value={facilityForm.site_reference} onChange={(e: InputEvent) => setFacilityForm({ ...facilityForm, site_reference: e.target.value })} /></Field>
              <Field label="Timezone"><input value={facilityForm.timezone} onChange={(e: InputEvent) => setFacilityForm({ ...facilityForm, timezone: e.target.value })} placeholder={overview.company.timezone} /></Field>
              <Field label="Gross area"><input type="number" min="0" step="0.001" value={facilityForm.gross_area} onChange={(e: InputEvent) => setFacilityForm({ ...facilityForm, gross_area: e.target.value })} /></Field>
              <Field label="Area unit"><select value={facilityForm.area_unit_code} onChange={(e: InputEvent) => setFacilityForm({ ...facilityForm, area_unit_code: e.target.value })}><option>SQ_M</option><option>SQ_FT</option></select></Field>
              <Field label="Occupancy capacity"><input type="number" min="0" value={facilityForm.occupancy_capacity} onChange={(e: InputEvent) => setFacilityForm({ ...facilityForm, occupancy_capacity: e.target.value })} /></Field>
              <Field label="Operational from"><input type="date" value={facilityForm.operational_from} onChange={(e: InputEvent) => setFacilityForm({ ...facilityForm, operational_from: e.target.value })} /></Field>
            </div><button disabled={working}>Register facility</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("spaces", { ...spaceForm, parent_public_id: nullable(spaceForm.parent_public_id), area: numberOrNull(spaceForm.area) }, "Facility space registered."); setSpaceForm(emptySpace); }}>
            <p className={styles.kicker}>SPACE HIERARCHY</p><h2>Create governed space</h2><div className={styles.formGrid}>
              <Field label="Facility" wide><select required value={spaceForm.facility_public_id} onChange={(e: InputEvent) => setSpaceForm({ ...spaceForm, facility_public_id: e.target.value, parent_public_id: "" })}><option value="">Select facility</option>{facilities.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field>
              <Field label="Parent space"><select value={spaceForm.parent_public_id} onChange={(e: InputEvent) => setSpaceForm({ ...spaceForm, parent_public_id: e.target.value })}><option value="">No parent</option>{spaces.filter((item) => value(item.facility__public_id) === spaceForm.facility_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field>
              <Field label="Space type"><select value={spaceForm.space_type_code} onChange={(e: InputEvent) => setSpaceForm({ ...spaceForm, space_type_code: e.target.value })}><option>ROOM</option><option>FLOOR</option><option>ZONE</option><option>PLANT_ROOM</option><option>EXTERNAL_AREA</option></select></Field>
              <Field label="Space code"><input required value={spaceForm.code} onChange={(e: InputEvent) => setSpaceForm({ ...spaceForm, code: e.target.value })} /></Field>
              <Field label="Floor reference"><input value={spaceForm.floor_reference} onChange={(e: InputEvent) => setSpaceForm({ ...spaceForm, floor_reference: e.target.value })} /></Field>
              <Field label="Space name" wide><input required value={spaceForm.name} onChange={(e: InputEvent) => setSpaceForm({ ...spaceForm, name: e.target.value })} /></Field>
              <Field label="Area"><input type="number" min="0" step="0.001" value={spaceForm.area} onChange={(e: InputEvent) => setSpaceForm({ ...spaceForm, area: e.target.value })} /></Field>
              <Field label="Criticality"><select value={spaceForm.criticality_code} onChange={(e: InputEvent) => setSpaceForm({ ...spaceForm, criticality_code: e.target.value })}><option>LOW</option><option>NORMAL</option><option>HIGH</option><option>CRITICAL</option></select></Field>
            </div><button disabled={working}>Create space</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>FACILITY PORTFOLIO</p><h2>Facilities and spaces</h2><div className={styles.tableWrap}><table><thead><tr><th>Facility / space</th><th>Type</th><th>Location</th><th>Area / capacity</th><th>Status</th></tr></thead><tbody>{facilities.map((item) => <tr key={`f-${value(item.public_id)}`}><td><strong>{value(item.code)}</strong><small>{value(item.name)}</small></td><td>{value(item.facility_type_code)}</td><td>{value(item.site_reference) || "—"}<small>{value(item.timezone)}</small></td><td>{value(item.gross_area) || "—"} {value(item.area_unit_code)}<small>Capacity: {value(item.occupancy_capacity) || "—"}</small></td><td><Status label={value(item.status_code)} /></td></tr>)}{spaces.map((item) => <tr key={`s-${value(item.public_id)}`}><td><strong>{value(item.facility__code)} / {value(item.code)}</strong><small>{value(item.name)}</small></td><td>{value(item.space_type_code)}</td><td>{value(item.floor_reference) || "—"}<small>Parent: {value(item.parent__code) || "—"}</small></td><td>{value(item.area) || "—"} {value(item.area_unit_code)}</td><td><Status label={`${value(item.status_code)} · ${value(item.criticality_code)}`} /></td></tr>)}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "assets" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("assets", { ...assetForm, space_public_id: nullable(assetForm.space_public_id), source_handover_public_id: nullable(assetForm.source_handover_public_id), commissioned_on: nullable(assetForm.commissioned_on), warranty_start_on: nullable(assetForm.warranty_start_on), warranty_end_on: nullable(assetForm.warranty_end_on), service_interval_days: numberOrNull(assetForm.service_interval_days), next_service_on: nullable(assetForm.next_service_on), document_references: assetForm.document_references.split(",").map((item) => item.trim()).filter(Boolean) }, "Operational asset registered."); setAssetForm(emptyAsset); }}>
            <p className={styles.kicker}>ASSET INFORMATION MODEL</p><h2>Register operational asset</h2><div className={styles.formGrid}>
              <Field label="Facility" wide><select required value={assetForm.facility_public_id} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, facility_public_id: e.target.value, space_public_id: "" })}><option value="">Select facility</option>{facilities.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field>
              <Field label="Space"><select value={assetForm.space_public_id} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, space_public_id: e.target.value })}><option value="">No space</option>{spaces.filter((item) => value(item.facility__public_id) === assetForm.facility_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field>
              <Field label="Asset tag"><input required value={assetForm.asset_tag} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, asset_tag: e.target.value })} /></Field>
              <Field label="Asset name" wide><input required value={assetForm.asset_name} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, asset_name: e.target.value })} /></Field>
              <Field label="Classification"><input required value={assetForm.classification_code} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, classification_code: e.target.value })} /></Field>
              <Field label="Handover public ID"><input value={assetForm.source_handover_public_id} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, source_handover_public_id: e.target.value })} /></Field>
              <Field label="Manufacturer"><input value={assetForm.manufacturer} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, manufacturer: e.target.value })} /></Field>
              <Field label="Model number"><input value={assetForm.model_number} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, model_number: e.target.value })} /></Field>
              <Field label="Serial number"><input value={assetForm.serial_number} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, serial_number: e.target.value })} /></Field>
              <Field label="Criticality"><select value={assetForm.criticality_code} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, criticality_code: e.target.value })}><option>LOW</option><option>NORMAL</option><option>HIGH</option><option>CRITICAL</option></select></Field>
              <Field label="Commissioned"><input type="date" value={assetForm.commissioned_on} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, commissioned_on: e.target.value })} /></Field>
              <Field label="Warranty start"><input type="date" value={assetForm.warranty_start_on} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, warranty_start_on: e.target.value })} /></Field>
              <Field label="Warranty end"><input type="date" value={assetForm.warranty_end_on} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, warranty_end_on: e.target.value })} /></Field>
              <Field label="Service interval days"><input type="number" min="1" value={assetForm.service_interval_days} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, service_interval_days: e.target.value })} /></Field>
              <Field label="Next service"><input type="date" value={assetForm.next_service_on} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, next_service_on: e.target.value })} /></Field>
              <Field label="Document references" wide><textarea value={assetForm.document_references} onChange={(e: InputEvent) => setAssetForm({ ...assetForm, document_references: e.target.value })} placeholder="Comma-separated O&M manuals, certificates and warranties" /></Field>
              <label className={styles.check}><input type="checkbox" checked={assetForm.maintainable} onChange={(e: ChangeEvent<HTMLInputElement>) => setAssetForm({ ...assetForm, maintainable: e.target.checked })} /> Maintainable asset</label>
            </div><button disabled={working}>Register asset</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>OPERATIONAL ASSET REGISTER</p><h2>Asset condition and lifecycle</h2><div className={styles.tableWrap}><table><thead><tr><th>Asset</th><th>Facility / space</th><th>Condition</th><th>Service / warranty</th><th>Status</th><th>Control</th></tr></thead><tbody>{assets.map((item) => { const status = value(item.operation_status_code); const next = nextAsset(status); return <tr key={value(item.public_id)}><td><strong>{value(item.asset_tag)}</strong><small>{value(item.asset_name)} · {value(item.classification_code)}</small></td><td>{value(item.facility__code)}<small>{value(item.space__code) || "No space"}</small></td><td><Status label={`${value(item.condition_code)} · ${value(item.criticality_code)}`} /></td><td>Next: {displayDate(item.next_service_on)}<small>Warranty: {displayDate(item.warranty_end_on)}</small></td><td><Status label={status} /></td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`assets/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version) }, `Asset moved to ${next}.`)}>{next.replaceAll("_", " ")}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "maintenance" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("maintenance-plans", { ...planForm, frequency_days: Number(planForm.frequency_days), lead_time_days: Number(planForm.lead_time_days), estimated_duration_minutes: Number(planForm.estimated_duration_minutes), checklist: planForm.checklist.split(",").map((item) => item.trim()).filter(Boolean) }, "Maintenance plan created."); setPlanForm(emptyPlan); }}>
            <p className={styles.kicker}>PREVENTIVE MAINTENANCE</p><h2>Create maintenance plan</h2><div className={styles.formGrid}>
              <Field label="Asset" wide><select required value={planForm.asset_public_id} onChange={(e: InputEvent) => setPlanForm({ ...planForm, asset_public_id: e.target.value })}><option value="">Select asset</option>{assets.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.asset_tag)} · {value(item.asset_name)}</option>)}</select></Field>
              <Field label="Plan code"><input required value={planForm.code} onChange={(e: InputEvent) => setPlanForm({ ...planForm, code: e.target.value })} /></Field>
              <Field label="Plan type"><select value={planForm.plan_type_code} onChange={(e: InputEvent) => setPlanForm({ ...planForm, plan_type_code: e.target.value })}><option>PREVENTIVE</option><option>PREDICTIVE</option><option>STATUTORY</option><option>CONDITION_BASED</option></select></Field>
              <Field label="Plan name" wide><input required value={planForm.name} onChange={(e: InputEvent) => setPlanForm({ ...planForm, name: e.target.value })} /></Field>
              <Field label="Frequency days"><input required type="number" min="1" value={planForm.frequency_days} onChange={(e: InputEvent) => setPlanForm({ ...planForm, frequency_days: e.target.value })} /></Field>
              <Field label="Lead time days"><input type="number" min="0" value={planForm.lead_time_days} onChange={(e: InputEvent) => setPlanForm({ ...planForm, lead_time_days: e.target.value })} /></Field>
              <Field label="Next due date"><input required type="date" value={planForm.next_due_date} onChange={(e: InputEvent) => setPlanForm({ ...planForm, next_due_date: e.target.value })} /></Field>
              <Field label="Estimated minutes"><input type="number" min="1" value={planForm.estimated_duration_minutes} onChange={(e: InputEvent) => setPlanForm({ ...planForm, estimated_duration_minutes: e.target.value })} /></Field>
              <Field label="Checklist" wide><textarea value={planForm.checklist} onChange={(e: InputEvent) => setPlanForm({ ...planForm, checklist: e.target.value })} placeholder="Comma-separated maintenance controls" /></Field>
            </div><button disabled={working}>Create plan</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("work-orders", { ...workOrderForm, plan_public_id: nullable(workOrderForm.plan_public_id), service_request_public_id: nullable(workOrderForm.service_request_public_id), due_date: nullable(workOrderForm.due_date), estimated_cost: numberOrNull(workOrderForm.estimated_cost), currency_code: overview.company.currency }, "Facility work order created."); setWorkOrderForm(emptyWorkOrder); }}>
            <p className={styles.kicker}>WORK EXECUTION</p><h2>Create facility work order</h2><div className={styles.formGrid}>
              <Field label="Asset" wide><select required value={workOrderForm.asset_public_id} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, asset_public_id: e.target.value, plan_public_id: "" })}><option value="">Select asset</option>{assets.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.asset_tag)} · {value(item.asset_name)}</option>)}</select></Field>
              <Field label="Maintenance plan"><select value={workOrderForm.plan_public_id} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, plan_public_id: e.target.value })}><option value="">No plan</option>{plans.filter((item) => value(item.asset__public_id) === workOrderForm.asset_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)}</option>)}</select></Field>
              <Field label="Service request"><select value={workOrderForm.service_request_public_id} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, service_request_public_id: e.target.value })}><option value="">No request</option>{requests.filter((item) => !workOrderForm.asset_public_id || value(item.asset__asset_tag) === value(assets.find((asset) => value(asset.public_id) === workOrderForm.asset_public_id)?.asset_tag)).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.request_number)}</option>)}</select></Field>
              <Field label="Work-order number"><input required value={workOrderForm.work_order_number} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, work_order_number: e.target.value })} /></Field>
              <Field label="Work type"><select value={workOrderForm.work_type_code} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, work_type_code: e.target.value })}><option>CORRECTIVE</option><option>PREVENTIVE</option><option>PREDICTIVE</option><option>WARRANTY</option><option>INSPECTION</option></select></Field>
              <Field label="Priority"><select value={workOrderForm.priority_code} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, priority_code: e.target.value })}><option>LOW</option><option>NORMAL</option><option>HIGH</option><option>CRITICAL</option></select></Field>
              <Field label="Title" wide><input required value={workOrderForm.title} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, title: e.target.value })} /></Field>
              <Field label="Due date"><input type="date" value={workOrderForm.due_date} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, due_date: e.target.value })} /></Field>
              <Field label="Estimated cost"><input type="number" min="0" step="0.01" value={workOrderForm.estimated_cost} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, estimated_cost: e.target.value })} /></Field>
              <Field label="Vendor reference" wide><input value={workOrderForm.vendor_reference} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, vendor_reference: e.target.value })} /></Field>
              <Field label="Description" wide><textarea value={workOrderForm.description} onChange={(e: InputEvent) => setWorkOrderForm({ ...workOrderForm, description: e.target.value })} /></Field>
            </div><button disabled={working}>Create work order</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>MAINTENANCE CONTROL</p><h2>Plans and work orders</h2><div className={styles.tableWrap}><table><thead><tr><th>Plan / work order</th><th>Asset</th><th>Type / priority</th><th>Due</th><th>Status</th><th>Control</th></tr></thead><tbody>{plans.map((item) => <tr key={`p-${value(item.public_id)}`}><td><strong>{value(item.code)}</strong><small>{value(item.name)}</small></td><td>{value(item.asset__asset_tag)}</td><td>{value(item.plan_type_code)}<small>Every {value(item.frequency_days)} days</small></td><td>{displayDate(item.next_due_date)}</td><td><Status label={value(item.status_code)} /></td><td>v{value(item.version)}</td></tr>)}{workOrders.map((item) => { const status = value(item.status_code); const next = nextWorkOrder(status); return <tr key={`w-${value(item.public_id)}`}><td><strong>{value(item.work_order_number)}</strong><small>{value(item.title)}</small></td><td>{value(item.asset__asset_tag)}</td><td>{value(item.work_type_code)} · {value(item.priority_code)}</td><td>{displayDate(item.due_date)}</td><td><Status label={status} /></td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`work-orders/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), completion_evidence: next === "COMPLETED" ? { source: "FACILITY_PORTAL" } : {} }, `Work order moved to ${next}.`)}>{next.replaceAll("_", " ")}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "service" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("service-requests", { ...requestForm, space_public_id: nullable(requestForm.space_public_id), asset_public_id: nullable(requestForm.asset_public_id) }, "Service request created and SLA deadlines calculated."); setRequestForm(emptyRequest); }}>
            <p className={styles.kicker}>SERVICE INTAKE</p><h2>Create facility request</h2><div className={styles.formGrid}>
              <Field label="Facility" wide><select required value={requestForm.facility_public_id} onChange={(e: InputEvent) => setRequestForm({ ...requestForm, facility_public_id: e.target.value, space_public_id: "", asset_public_id: "" })}><option value="">Select facility</option>{facilities.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field>
              <Field label="Space"><select value={requestForm.space_public_id} onChange={(e: InputEvent) => setRequestForm({ ...requestForm, space_public_id: e.target.value })}><option value="">No space</option>{spaces.filter((item) => value(item.facility__public_id) === requestForm.facility_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)}</option>)}</select></Field>
              <Field label="Asset"><select value={requestForm.asset_public_id} onChange={(e: InputEvent) => setRequestForm({ ...requestForm, asset_public_id: e.target.value })}><option value="">No asset</option>{assets.filter((item) => value(item.facility__public_id) === requestForm.facility_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.asset_tag)}</option>)}</select></Field>
              <Field label="Request number"><input required value={requestForm.request_number} onChange={(e: InputEvent) => setRequestForm({ ...requestForm, request_number: e.target.value })} /></Field>
              <Field label="Category"><input value={requestForm.category_code} onChange={(e: InputEvent) => setRequestForm({ ...requestForm, category_code: e.target.value })} /></Field>
              <Field label="Priority"><select value={requestForm.priority_code} onChange={(e: InputEvent) => setRequestForm({ ...requestForm, priority_code: e.target.value })}><option>LOW</option><option>NORMAL</option><option>HIGH</option><option>CRITICAL</option></select></Field>
              <Field label="Channel"><select value={requestForm.channel_code} onChange={(e: InputEvent) => setRequestForm({ ...requestForm, channel_code: e.target.value })}><option>PORTAL</option><option>PHONE</option><option>EMAIL</option><option>WHATSAPP</option><option>SENSOR</option></select></Field>
              <Field label="Requester reference"><input value={requestForm.requester_reference} onChange={(e: InputEvent) => setRequestForm({ ...requestForm, requester_reference: e.target.value })} /></Field>
              <Field label="Title" wide><input required value={requestForm.title} onChange={(e: InputEvent) => setRequestForm({ ...requestForm, title: e.target.value })} /></Field>
              <Field label="Description" wide><textarea value={requestForm.description} onChange={(e: InputEvent) => setRequestForm({ ...requestForm, description: e.target.value })} /></Field>
            </div><button disabled={working}>Create service request</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>SLA EXECUTION</p><h2>Service request queue</h2><div className={styles.tableWrap}><table><thead><tr><th>Request</th><th>Facility / asset</th><th>Priority</th><th>Response / resolution SLA</th><th>Status</th><th>Control</th></tr></thead><tbody>{requests.map((item) => { const status = value(item.status_code); const next = nextRequest(status); return <tr key={value(item.public_id)}><td><strong>{value(item.request_number)}</strong><small>{value(item.title)}</small></td><td>{value(item.facility__code)}<small>{value(item.asset__asset_tag) || value(item.space__code) || "General"}</small></td><td><Status label={`${value(item.priority_code)} · ${value(item.channel_code)}`} /></td><td>{displayDate(item.response_due_at)}<small>{displayDate(item.resolution_due_at)}</small></td><td><Status label={status} /></td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`service-requests/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version) }, `Request moved to ${next}.`)}>{next.replaceAll("_", " ")}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "warranty" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("warranty-claims", { ...claimForm, work_order_public_id: nullable(claimForm.work_order_public_id), failure_date: nullable(claimForm.failure_date), claimed_amount: numberOrNull(claimForm.claimed_amount), currency_code: overview.company.currency }, "Warranty claim created."); setClaimForm(emptyClaim); }}>
            <p className={styles.kicker}>WARRANTY RECOVERY</p><h2>Register warranty claim</h2><div className={styles.formGrid}>
              <Field label="Asset" wide><select required value={claimForm.asset_public_id} onChange={(e: InputEvent) => setClaimForm({ ...claimForm, asset_public_id: e.target.value, work_order_public_id: "" })}><option value="">Select asset</option>{assets.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.asset_tag)} · {value(item.asset_name)}</option>)}</select></Field>
              <Field label="Work order"><select value={claimForm.work_order_public_id} onChange={(e: InputEvent) => setClaimForm({ ...claimForm, work_order_public_id: e.target.value })}><option value="">No work order</option>{workOrders.filter((item) => value(item.asset__public_id) === claimForm.asset_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.work_order_number)}</option>)}</select></Field>
              <Field label="Claim number"><input required value={claimForm.claim_number} onChange={(e: InputEvent) => setClaimForm({ ...claimForm, claim_number: e.target.value })} /></Field>
              <Field label="Supplier reference"><input value={claimForm.supplier_reference} onChange={(e: InputEvent) => setClaimForm({ ...claimForm, supplier_reference: e.target.value })} /></Field>
              <Field label="Warranty reference"><input value={claimForm.warranty_reference} onChange={(e: InputEvent) => setClaimForm({ ...claimForm, warranty_reference: e.target.value })} /></Field>
              <Field label="Reported on"><input required type="date" value={claimForm.reported_on} onChange={(e: InputEvent) => setClaimForm({ ...claimForm, reported_on: e.target.value })} /></Field>
              <Field label="Failure date"><input type="date" value={claimForm.failure_date} onChange={(e: InputEvent) => setClaimForm({ ...claimForm, failure_date: e.target.value })} /></Field>
              <Field label="Claimed amount"><input type="number" min="0" step="0.01" value={claimForm.claimed_amount} onChange={(e: InputEvent) => setClaimForm({ ...claimForm, claimed_amount: e.target.value })} /></Field>
              <Field label="Issue description" wide><textarea required value={claimForm.issue_description} onChange={(e: InputEvent) => setClaimForm({ ...claimForm, issue_description: e.target.value })} /></Field>
            </div><button disabled={working}>Create warranty claim</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("inspections", { ...inspectionForm, space_public_id: nullable(inspectionForm.space_public_id), asset_public_id: nullable(inspectionForm.asset_public_id), scheduled_on: nullable(inspectionForm.scheduled_on), inspected_on: nullable(inspectionForm.inspected_on), score: numberOrNull(inspectionForm.score) }, "Condition inspection recorded."); setInspectionForm(emptyInspection); }}>
            <p className={styles.kicker}>CONDITION ASSURANCE</p><h2>Record condition inspection</h2><div className={styles.formGrid}>
              <Field label="Facility" wide><select required value={inspectionForm.facility_public_id} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, facility_public_id: e.target.value, space_public_id: "", asset_public_id: "" })}><option value="">Select facility</option>{facilities.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field>
              <Field label="Space"><select value={inspectionForm.space_public_id} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, space_public_id: e.target.value })}><option value="">No space</option>{spaces.filter((item) => value(item.facility__public_id) === inspectionForm.facility_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)}</option>)}</select></Field>
              <Field label="Asset"><select value={inspectionForm.asset_public_id} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, asset_public_id: e.target.value })}><option value="">No asset</option>{assets.filter((item) => value(item.facility__public_id) === inspectionForm.facility_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.asset_tag)}</option>)}</select></Field>
              <Field label="Inspection number"><input required value={inspectionForm.inspection_number} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, inspection_number: e.target.value })} /></Field>
              <Field label="Inspection type"><select value={inspectionForm.inspection_type_code} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, inspection_type_code: e.target.value })}><option>CONDITION</option><option>STATUTORY</option><option>HANDOVER</option><option>WARRANTY</option><option>SAFETY</option></select></Field>
              <Field label="Condition"><select value={inspectionForm.condition_code} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, condition_code: e.target.value })}><option>EXCELLENT</option><option>GOOD</option><option>FAIR</option><option>POOR</option><option>CRITICAL</option></select></Field>
              <Field label="Scheduled on"><input type="date" value={inspectionForm.scheduled_on} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, scheduled_on: e.target.value })} /></Field>
              <Field label="Inspected on"><input type="date" value={inspectionForm.inspected_on} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, inspected_on: e.target.value })} /></Field>
              <Field label="Score"><input type="number" min="0" max="100" step="0.01" value={inspectionForm.score} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, score: e.target.value })} /></Field>
              <Field label="Findings" wide><textarea value={inspectionForm.findings} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, findings: e.target.value })} /></Field>
              <Field label="Actions required" wide><textarea value={inspectionForm.actions_required} onChange={(e: InputEvent) => setInspectionForm({ ...inspectionForm, actions_required: e.target.value })} /></Field>
            </div><button disabled={working}>Record inspection</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>WARRANTY & CONDITION CONTROL</p><h2>Claims and inspection evidence</h2><div className={styles.tableWrap}><table><thead><tr><th>Claim / inspection</th><th>Asset / facility</th><th>Value / condition</th><th>Date</th><th>Status</th><th>Control</th></tr></thead><tbody>{overview.warranty_claims.map((item) => { const status = value(item.status_code); const next = nextClaim(status); return <tr key={`c-${value(item.public_id)}`}><td><strong>{value(item.claim_number)}</strong><small>{value(item.supplier_reference) || "Warranty claim"}</small></td><td>{value(item.asset__asset_tag)}</td><td>{value(item.currency_code)} {value(item.claimed_amount) || "0"}<small>Approved: {value(item.approved_amount) || "—"}</small></td><td>{displayDate(item.reported_on)}</td><td><Status label={status} /></td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`warranty-claims/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), approved_amount: next === "APPROVED" ? item.claimed_amount : null }, `Warranty claim moved to ${next}.`)}>{next.replaceAll("_", " ")}</button> : "—"}</td></tr>; })}{overview.inspections.map((item) => { const status = value(item.status_code); const next = nextInspection(status); return <tr key={`i-${value(item.public_id)}`}><td><strong>{value(item.inspection_number)}</strong><small>{value(item.inspection_type_code)}</small></td><td>{value(item.asset__asset_tag) || value(item.facility__code)}</td><td><Status label={value(item.condition_code)} /><small>Score: {value(item.score) || "—"}</small></td><td>{displayDate(item.inspected_on || item.scheduled_on)}</td><td><Status label={status} /></td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`inspections/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version) }, `Inspection moved to ${next}.`)}>{next.replaceAll("_", " ")}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}
    </main>
  );
}
