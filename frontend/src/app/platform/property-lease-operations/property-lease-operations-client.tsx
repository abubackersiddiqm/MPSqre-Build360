"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import styles from "./property-lease-operations.module.css";

type Row = Record<string, unknown>;
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: { status: string; version: number; lease_expiry_alert_days: number; invoice_grace_days: number };
  metrics: Record<string, string | number>;
  properties: Row[];
  units: Row[];
  tenants: Row[];
  leases: Row[];
  charges: Row[];
  occupancies: Row[];
  invoices: Row[];
  tenant_cases: Row[];
  lifecycle_events: Row[];
  portfolio: { unit_status: Row[]; lease_status: Row[]; case_priority: Row[] };
};

type Tab = "summary" | "property" | "leases" | "billing" | "experience";
type InputEvent = ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>;

const emptyProperty = { code: "", name: "", property_type_code: "RESIDENTIAL", external_reference: "", timezone: "", gross_area: "", area_unit_code: "SQ_M", ownership_code: "OWNED" };
const emptyUnit = { property_public_id: "", code: "", name: "", unit_type_code: "APARTMENT", floor_reference: "", area: "", area_unit_code: "SQ_M", bedroom_count: "", parking_count: "0", market_rent: "" };
const emptyTenant = { account_code: "", legal_name: "", display_name: "", tenant_type_code: "ORGANIZATION", contact_name: "", contact_email: "", contact_phone: "", tax_reference: "" };
const emptyLease = { property_public_id: "", unit_public_id: "", tenant_public_id: "", lease_number: "", lease_type_code: "STANDARD", start_on: "", end_on: "", billing_cycle_code: "MONTHLY", base_rent: "", security_deposit: "0", escalation_percent: "0", escalation_frequency_months: "12", notice_days: "30" };
const emptyCharge = { lease_public_id: "", charge_code: "", charge_type_code: "RENT", description: "Base rent", amount: "", frequency_code: "MONTHLY", effective_from: "", effective_to: "", tax_code: "", recoverable: true };
const emptyInvoice = { lease_public_id: "", invoice_number: "", period_start: "", period_end: "", issue_date: "", due_date: "", gross_amount: "", tax_amount: "0", external_finance_reference: "" };
const emptyOccupancy = { lease_public_id: "", occupant_reference: "", move_in_on: "", move_out_on: "", occupant_count: "1", key_handover_reference: "", opening_meter_reference: "" };
const emptyCase = { tenant_public_id: "", property_public_id: "", unit_public_id: "", case_number: "", category_code: "SERVICE", priority_code: "NORMAL", channel_code: "PORTAL", title: "", description: "" };

function value(input: unknown): string {
  if (input === null || input === undefined) return "";
  return String(input);
}

function nullable(input: string): string | null {
  return input.trim() ? input.trim() : null;
}

function numberOrNull(input: string): string | null {
  return input.trim() ? input : null;
}

function displayDate(input: unknown): string {
  const raw = value(input);
  if (!raw) return "—";
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? raw : parsed.toLocaleDateString();
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

function Metric({ label, metric, note }: { label: string; metric: string | number; note: string }) {
  return <article className={styles.metric}><span>{label}</span><strong>{metric}</strong><small>{note}</small></article>;
}

function Status({ label }: { label: string }) {
  return <span className={styles.pill}>{label || "—"}</span>;
}

function Field({ label, children, wide = false }: { label: string; children?: ReactNode; wide?: boolean }) {
  return <label className={wide ? styles.full : undefined}><span>{label}</span>{children}</label>;
}

function nextLease(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "ACTIVE";
  if (status === "ACTIVE") return "EXPIRED";
  if (status === "EXPIRED" || status === "TERMINATED") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextOccupancy(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "VERIFIED";
  if (status === "VERIFIED") return "OCCUPIED";
  if (status === "OCCUPIED") return "MOVED_OUT";
  if (status === "MOVED_OUT") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextInvoice(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "ISSUED";
  if (status === "ISSUED" || status === "PARTIALLY_PAID") return "PAID";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextCase(status: string): string {
  if (status === "NEW") return "ACKNOWLEDGED";
  if (status === "ACKNOWLEDGED" || status === "ASSIGNED") return "IN_PROGRESS";
  if (status === "IN_PROGRESS") return "RESOLVED";
  if (status === "RESOLVED") return "CLOSED";
  if (status === "REOPENED" || status === "ON_HOLD") return "IN_PROGRESS";
  return "";
}

export function PropertyLeaseOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [propertyForm, setPropertyForm] = useState(emptyProperty);
  const [unitForm, setUnitForm] = useState(emptyUnit);
  const [tenantForm, setTenantForm] = useState(emptyTenant);
  const [leaseForm, setLeaseForm] = useState(emptyLease);
  const [chargeForm, setChargeForm] = useState(emptyCharge);
  const [invoiceForm, setInvoiceForm] = useState(emptyInvoice);
  const [occupancyForm, setOccupancyForm] = useState(emptyOccupancy);
  const [caseForm, setCaseForm] = useState(emptyCase);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/platform/property-lease-operations/overview", { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(payload, "Property and lease operations could not be loaded."));
      setOverview(payload as Overview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Property and lease operations could not be loaded.");
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
      const response = await fetch(`/api/platform/property-lease-operations/${path}`, {
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

  const properties = overview?.properties ?? [];
  const units = overview?.units ?? [];
  const tenants = overview?.tenants ?? [];
  const leases = overview?.leases ?? [];
  const recentEvents = useMemo(() => (overview?.lifecycle_events ?? []).slice(0, 12), [overview]);

  if (loading && !overview) {
    return <main className={styles.shell}><section className={styles.loading}>Preparing the property and lease command centre…</section></main>;
  }

  if (!overview) {
    return <main className={styles.shell}><section className={styles.errorCard}><p className={styles.kicker}>PROPERTY CONTROL UNAVAILABLE</p><h2>Property, lease and occupancy operations could not be opened.</h2><p>{error || "The request could not be completed."}</p><button type="button" onClick={() => void refresh()}>Retry workspace</button></section></main>;
  }

  const metrics = overview.metrics;
  const currency = overview.company.currency;

  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 41</p>
          <h1>Property, lease, occupancy & tenant experience</h1>
          <p className={styles.lead}>Govern property portfolios, leaseable units, tenants, contracts, receivables, move-in evidence and tenant experience from one tenant-safe command centre.</p>
          <div className={styles.tags}><span>{overview.company.name}</span><span>{currency}</span><span>{overview.company.timezone}</span><span>Policy {overview.policy.status}</span></div>
        </div>
        <div className={styles.heroActions}><span className={styles.activeLabel}>PHASE 41 PROPERTY & LEASE OPERATIONS ACTIVE</span><button type="button" onClick={() => void refresh()}>Refresh property cockpit</button></div>
      </header>

      {error ? <p className={styles.alert}>{error}</p> : null}
      {notice ? <p className={styles.notice}>{notice}</p> : null}

      <section className={styles.metrics} aria-label="Property portfolio metrics">
        <Metric label="Active properties" metric={metrics.active_properties ?? 0} note={`${metrics.available_units} units available`} />
        <Metric label="Occupancy rate" metric={`${metrics.occupancy_rate}%`} note={`${metrics.active_leases} active leases`} />
        <Metric label="Lease expiry watch" metric={metrics.expiring_leases ?? 0} note={`Inside ${overview.policy.lease_expiry_alert_days} days`} />
        <Metric label="Open receivable" metric={`${currency} ${metrics.open_receivable}`} note={`${currency} ${metrics.overdue_receivable} overdue`} />
        <Metric label="Tenant cases" metric={metrics.open_cases ?? 0} note={`${metrics.case_sla_breaches} SLA breaches`} />
        <Metric label="Security deposits" metric={`${currency} ${metrics.security_deposits}`} note="Approved and active leases" />
      </section>

      <nav className={styles.tabs} aria-label="Property and lease operations tabs">
        {(["summary", "property", "leases", "billing", "experience"] as Tab[]).map((item) => <button type="button" key={item} className={tab === item ? styles.selected : ""} onClick={() => setTab(item)}>{item === "property" ? "Properties & units" : item === "leases" ? "Tenants & leases" : item === "billing" ? "Billing & receivables" : item === "experience" ? "Occupancy & experience" : "Summary"}</button>)}
      </nav>

      {tab === "summary" ? (
        <section className={styles.grid}>
          <article className={styles.card}><p className={styles.kicker}>PORTFOLIO POSITION</p><h2>Governance posture</h2><dl className={styles.definition}><div><dt>Properties</dt><dd>{properties.length}</dd></div><div><dt>Leaseable units</dt><dd>{units.length}</dd></div><div><dt>Tenant accounts</dt><dd>{tenants.length}</dd></div><div><dt>Policy version</dt><dd>v{overview.policy.version}</dd></div><div><dt>Invoice grace</dt><dd>{overview.policy.invoice_grace_days} days</dd></div></dl></article>
          <article className={styles.card}><p className={styles.kicker}>UNIT AVAILABILITY</p><h2>Unit-state distribution</h2><dl className={styles.definition}>{overview.portfolio.unit_status.map((item) => <div key={value(item.status_code)}><dt>{value(item.status_code)}</dt><dd>{value(item.count)}</dd></div>)}</dl></article>
          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>RECENT LEASE EVIDENCE</p><h2>Lifecycle activity</h2><div className={styles.tableWrap}><table><thead><tr><th>Lease</th><th>Event</th><th>Summary</th><th>Value</th><th>Occurred</th></tr></thead><tbody>{recentEvents.map((item) => <tr key={value(item.public_id)}><td><strong>{value(item.lease__lease_number)}</strong></td><td><Status label={value(item.event_type_code)} /></td><td>{value(item.summary)}</td><td>{value(item.currency_code)} {value(item.amount)}</td><td>{displayDate(item.occurred_at)}</td></tr>)}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "property" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("properties", { ...propertyForm, gross_area: numberOrNull(propertyForm.gross_area), address: {} }, "Property registered."); setPropertyForm(emptyProperty); }}>
            <p className={styles.kicker}>PROPERTY MASTER</p><h2>Register managed property</h2><div className={styles.formGrid}>
              <Field label="Property code"><input required value={propertyForm.code} onChange={(e: InputEvent) => setPropertyForm({ ...propertyForm, code: e.target.value })} /></Field>
              <Field label="Property name"><input required value={propertyForm.name} onChange={(e: InputEvent) => setPropertyForm({ ...propertyForm, name: e.target.value })} /></Field>
              <Field label="Property type"><select value={propertyForm.property_type_code} onChange={(e: InputEvent) => setPropertyForm({ ...propertyForm, property_type_code: e.target.value })}><option>RESIDENTIAL</option><option>COMMERCIAL</option><option>RETAIL</option><option>INDUSTRIAL</option><option>MIXED_USE</option><option>HOSPITALITY</option></select></Field>
              <Field label="Ownership"><select value={propertyForm.ownership_code} onChange={(e: InputEvent) => setPropertyForm({ ...propertyForm, ownership_code: e.target.value })}><option>OWNED</option><option>MANAGED</option><option>JOINT_VENTURE</option><option>LEASED_IN</option></select></Field>
              <Field label="External reference"><input value={propertyForm.external_reference} onChange={(e: InputEvent) => setPropertyForm({ ...propertyForm, external_reference: e.target.value })} /></Field>
              <Field label="Timezone"><input placeholder={overview.company.timezone} value={propertyForm.timezone} onChange={(e: InputEvent) => setPropertyForm({ ...propertyForm, timezone: e.target.value })} /></Field>
              <Field label="Gross area"><input type="number" min="0" step="0.001" value={propertyForm.gross_area} onChange={(e: InputEvent) => setPropertyForm({ ...propertyForm, gross_area: e.target.value })} /></Field>
              <Field label="Area unit"><select value={propertyForm.area_unit_code} onChange={(e: InputEvent) => setPropertyForm({ ...propertyForm, area_unit_code: e.target.value })}><option>SQ_M</option><option>SQ_FT</option></select></Field>
            </div><button disabled={working}>Register property</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("units", { ...unitForm, bedroom_count: numberOrNull(unitForm.bedroom_count), parking_count: unitForm.parking_count, area: numberOrNull(unitForm.area), market_rent: numberOrNull(unitForm.market_rent), currency_code: currency, attributes: {} }, "Leaseable unit created."); setUnitForm(emptyUnit); }}>
            <p className={styles.kicker}>UNIT INVENTORY</p><h2>Create leaseable unit</h2><div className={styles.formGrid}>
              <Field label="Property" wide><select required value={unitForm.property_public_id} onChange={(e: InputEvent) => setUnitForm({ ...unitForm, property_public_id: e.target.value })}><option value="">Select property</option>{properties.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field>
              <Field label="Unit code"><input required value={unitForm.code} onChange={(e: InputEvent) => setUnitForm({ ...unitForm, code: e.target.value })} /></Field>
              <Field label="Unit name"><input required value={unitForm.name} onChange={(e: InputEvent) => setUnitForm({ ...unitForm, name: e.target.value })} /></Field>
              <Field label="Unit type"><select value={unitForm.unit_type_code} onChange={(e: InputEvent) => setUnitForm({ ...unitForm, unit_type_code: e.target.value })}><option>APARTMENT</option><option>OFFICE</option><option>RETAIL_UNIT</option><option>WAREHOUSE</option><option>PARKING</option><option>VILLA</option></select></Field>
              <Field label="Floor"><input value={unitForm.floor_reference} onChange={(e: InputEvent) => setUnitForm({ ...unitForm, floor_reference: e.target.value })} /></Field>
              <Field label="Area"><input type="number" min="0" step="0.001" value={unitForm.area} onChange={(e: InputEvent) => setUnitForm({ ...unitForm, area: e.target.value })} /></Field>
              <Field label="Market rent"><input type="number" min="0" step="0.01" value={unitForm.market_rent} onChange={(e: InputEvent) => setUnitForm({ ...unitForm, market_rent: e.target.value })} /></Field>
              <Field label="Bedrooms"><input type="number" min="0" value={unitForm.bedroom_count} onChange={(e: InputEvent) => setUnitForm({ ...unitForm, bedroom_count: e.target.value })} /></Field>
              <Field label="Parking"><input type="number" min="0" value={unitForm.parking_count} onChange={(e: InputEvent) => setUnitForm({ ...unitForm, parking_count: e.target.value })} /></Field>
            </div><button disabled={working}>Create unit</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>PROPERTY PORTFOLIO</p><h2>Properties and leaseable inventory</h2><div className={styles.tableWrap}><table><thead><tr><th>Property / unit</th><th>Type</th><th>Area</th><th>Market rent</th><th>Status</th></tr></thead><tbody>{properties.map((item) => <tr key={`p-${value(item.public_id)}`}><td><strong>{value(item.code)} · {value(item.name)}</strong><small>{value(item.external_reference)}</small></td><td>{value(item.property_type_code)}</td><td>{value(item.gross_area)} {value(item.area_unit_code)}</td><td>—</td><td><Status label={value(item.status_code)} /></td></tr>)}{units.map((item) => <tr key={`u-${value(item.public_id)}`}><td><strong>{value(item.property__code)} / {value(item.code)}</strong><small>{value(item.name)} · {value(item.floor_reference)}</small></td><td>{value(item.unit_type_code)}</td><td>{value(item.area)} {value(item.area_unit_code)}</td><td>{value(item.currency_code)} {value(item.market_rent)}</td><td><Status label={value(item.status_code)} /></td></tr>)}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "leases" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("tenants", { ...tenantForm, billing_address: {} }, "Tenant account created."); setTenantForm(emptyTenant); }}>
            <p className={styles.kicker}>TENANT MASTER</p><h2>Create tenant account</h2><div className={styles.formGrid}>
              <Field label="Account code"><input required value={tenantForm.account_code} onChange={(e: InputEvent) => setTenantForm({ ...tenantForm, account_code: e.target.value })} /></Field>
              <Field label="Tenant type"><select value={tenantForm.tenant_type_code} onChange={(e: InputEvent) => setTenantForm({ ...tenantForm, tenant_type_code: e.target.value })}><option>ORGANIZATION</option><option>INDIVIDUAL</option><option>GOVERNMENT</option><option>INTERNAL</option></select></Field>
              <Field label="Legal name" wide><input required value={tenantForm.legal_name} onChange={(e: InputEvent) => setTenantForm({ ...tenantForm, legal_name: e.target.value })} /></Field>
              <Field label="Display name"><input required value={tenantForm.display_name} onChange={(e: InputEvent) => setTenantForm({ ...tenantForm, display_name: e.target.value })} /></Field>
              <Field label="Contact name"><input value={tenantForm.contact_name} onChange={(e: InputEvent) => setTenantForm({ ...tenantForm, contact_name: e.target.value })} /></Field>
              <Field label="Email"><input type="email" value={tenantForm.contact_email} onChange={(e: InputEvent) => setTenantForm({ ...tenantForm, contact_email: e.target.value })} /></Field>
              <Field label="Phone"><input value={tenantForm.contact_phone} onChange={(e: InputEvent) => setTenantForm({ ...tenantForm, contact_phone: e.target.value })} /></Field>
            </div><button disabled={working}>Create tenant</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("leases", { ...leaseForm, base_rent: leaseForm.base_rent, security_deposit: leaseForm.security_deposit, escalation_percent: leaseForm.escalation_percent, escalation_frequency_months: leaseForm.escalation_frequency_months, notice_days: leaseForm.notice_days, currency_code: currency }, "Lease agreement created."); setLeaseForm(emptyLease); }}>
            <p className={styles.kicker}>LEASE CONTRACT</p><h2>Create lease agreement</h2><div className={styles.formGrid}>
              <Field label="Property"><select required value={leaseForm.property_public_id} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, property_public_id: e.target.value, unit_public_id: "" })}><option value="">Select property</option>{properties.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)}</option>)}</select></Field>
              <Field label="Unit"><select required value={leaseForm.unit_public_id} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, unit_public_id: e.target.value })}><option value="">Select unit</option>{units.filter((item) => value(item.property__public_id) === leaseForm.property_public_id && ["AVAILABLE", "RESERVED"].includes(value(item.status_code))).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field>
              <Field label="Tenant" wide><select required value={leaseForm.tenant_public_id} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, tenant_public_id: e.target.value })}><option value="">Select tenant</option>{tenants.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.account_code)} · {value(item.display_name)}</option>)}</select></Field>
              <Field label="Lease number"><input required value={leaseForm.lease_number} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, lease_number: e.target.value })} /></Field>
              <Field label="Lease type"><select value={leaseForm.lease_type_code} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, lease_type_code: e.target.value })}><option>STANDARD</option><option>COMMERCIAL</option><option>LICENSE</option><option>SHORT_TERM</option><option>GROUND_LEASE</option></select></Field>
              <Field label="Start date"><input required type="date" value={leaseForm.start_on} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, start_on: e.target.value })} /></Field>
              <Field label="End date"><input required type="date" value={leaseForm.end_on} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, end_on: e.target.value })} /></Field>
              <Field label="Base rent"><input required type="number" min="0" step="0.01" value={leaseForm.base_rent} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, base_rent: e.target.value })} /></Field>
              <Field label="Security deposit"><input type="number" min="0" step="0.01" value={leaseForm.security_deposit} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, security_deposit: e.target.value })} /></Field>
              <Field label="Escalation %"><input type="number" min="0" step="0.0001" value={leaseForm.escalation_percent} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, escalation_percent: e.target.value })} /></Field>
              <Field label="Notice days"><input type="number" min="0" value={leaseForm.notice_days} onChange={(e: InputEvent) => setLeaseForm({ ...leaseForm, notice_days: e.target.value })} /></Field>
            </div><button disabled={working}>Create lease</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>LEASE PORTFOLIO</p><h2>Contract lifecycle</h2><div className={styles.tableWrap}><table><thead><tr><th>Lease</th><th>Tenant / unit</th><th>Term</th><th>Rent / deposit</th><th>Status</th><th>Control</th></tr></thead><tbody>{leases.map((item) => { const status = value(item.status_code); const next = nextLease(status); return <tr key={value(item.public_id)}><td><strong>{value(item.lease_number)}</strong><small>{value(item.lease_type_code)}</small></td><td>{value(item.tenant__display_name)}<small>{value(item.property__code)} / {value(item.unit__code)}</small></td><td>{displayDate(item.start_on)}<small>to {displayDate(item.end_on)}</small></td><td>{value(item.currency_code)} {value(item.base_rent)}<small>Deposit: {value(item.security_deposit)}</small></td><td><Status label={status} /></td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`leases/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version) }, `Lease moved to ${next}.`)}>{next.replaceAll("_", " ")}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "billing" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("charges", { ...chargeForm, effective_to: nullable(chargeForm.effective_to), currency_code: currency }, "Lease charge created."); setChargeForm(emptyCharge); }}>
            <p className={styles.kicker}>RECURRING CHARGES</p><h2>Configure lease charge</h2><div className={styles.formGrid}>
              <Field label="Lease" wide><select required value={chargeForm.lease_public_id} onChange={(e: InputEvent) => setChargeForm({ ...chargeForm, lease_public_id: e.target.value })}><option value="">Select lease</option>{leases.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.lease_number)} · {value(item.tenant__display_name)}</option>)}</select></Field>
              <Field label="Charge code"><input required value={chargeForm.charge_code} onChange={(e: InputEvent) => setChargeForm({ ...chargeForm, charge_code: e.target.value })} /></Field>
              <Field label="Charge type"><select value={chargeForm.charge_type_code} onChange={(e: InputEvent) => setChargeForm({ ...chargeForm, charge_type_code: e.target.value })}><option>RENT</option><option>CAM</option><option>UTILITIES</option><option>PARKING</option><option>INSURANCE</option><option>TAX_RECOVERY</option></select></Field>
              <Field label="Description" wide><input required value={chargeForm.description} onChange={(e: InputEvent) => setChargeForm({ ...chargeForm, description: e.target.value })} /></Field>
              <Field label="Amount"><input required type="number" min="0" step="0.01" value={chargeForm.amount} onChange={(e: InputEvent) => setChargeForm({ ...chargeForm, amount: e.target.value })} /></Field>
              <Field label="Frequency"><select value={chargeForm.frequency_code} onChange={(e: InputEvent) => setChargeForm({ ...chargeForm, frequency_code: e.target.value })}><option>MONTHLY</option><option>QUARTERLY</option><option>ANNUAL</option><option>ONE_TIME</option></select></Field>
              <Field label="Effective from"><input required type="date" value={chargeForm.effective_from} onChange={(e: InputEvent) => setChargeForm({ ...chargeForm, effective_from: e.target.value })} /></Field>
              <Field label="Effective to"><input type="date" value={chargeForm.effective_to} onChange={(e: InputEvent) => setChargeForm({ ...chargeForm, effective_to: e.target.value })} /></Field>
            </div><button disabled={working}>Create charge</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("invoices", { ...invoiceForm, currency_code: currency }, "Rent invoice created."); setInvoiceForm(emptyInvoice); }}>
            <p className={styles.kicker}>RECEIVABLE CONTROL</p><h2>Create rent invoice</h2><div className={styles.formGrid}>
              <Field label="Lease" wide><select required value={invoiceForm.lease_public_id} onChange={(e: InputEvent) => setInvoiceForm({ ...invoiceForm, lease_public_id: e.target.value })}><option value="">Select lease</option>{leases.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.lease_number)} · {value(item.tenant__display_name)}</option>)}</select></Field>
              <Field label="Invoice number"><input required value={invoiceForm.invoice_number} onChange={(e: InputEvent) => setInvoiceForm({ ...invoiceForm, invoice_number: e.target.value })} /></Field>
              <Field label="Finance reference"><input value={invoiceForm.external_finance_reference} onChange={(e: InputEvent) => setInvoiceForm({ ...invoiceForm, external_finance_reference: e.target.value })} /></Field>
              <Field label="Period start"><input required type="date" value={invoiceForm.period_start} onChange={(e: InputEvent) => setInvoiceForm({ ...invoiceForm, period_start: e.target.value })} /></Field>
              <Field label="Period end"><input required type="date" value={invoiceForm.period_end} onChange={(e: InputEvent) => setInvoiceForm({ ...invoiceForm, period_end: e.target.value })} /></Field>
              <Field label="Issue date"><input required type="date" value={invoiceForm.issue_date} onChange={(e: InputEvent) => setInvoiceForm({ ...invoiceForm, issue_date: e.target.value })} /></Field>
              <Field label="Due date"><input required type="date" value={invoiceForm.due_date} onChange={(e: InputEvent) => setInvoiceForm({ ...invoiceForm, due_date: e.target.value })} /></Field>
              <Field label="Gross amount"><input required type="number" min="0" step="0.01" value={invoiceForm.gross_amount} onChange={(e: InputEvent) => setInvoiceForm({ ...invoiceForm, gross_amount: e.target.value })} /></Field>
              <Field label="Tax amount"><input type="number" min="0" step="0.01" value={invoiceForm.tax_amount} onChange={(e: InputEvent) => setInvoiceForm({ ...invoiceForm, tax_amount: e.target.value })} /></Field>
            </div><button disabled={working}>Create invoice</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>BILLING & COLLECTION</p><h2>Charges and rent invoices</h2><div className={styles.tableWrap}><table><thead><tr><th>Invoice / charge</th><th>Lease / tenant</th><th>Period / due</th><th>Total / outstanding</th><th>Status</th><th>Control</th></tr></thead><tbody>{overview.invoices.map((item) => { const status = value(item.status_code); const next = nextInvoice(status); return <tr key={`i-${value(item.public_id)}`}><td><strong>{value(item.invoice_number)}</strong><small>{value(item.external_finance_reference)}</small></td><td>{value(item.lease__lease_number)}<small>{value(item.lease__tenant__display_name)} · {value(item.lease__unit__code)}</small></td><td>{displayDate(item.period_start)} – {displayDate(item.period_end)}<small>Due {displayDate(item.due_date)}</small></td><td>{value(item.currency_code)} {value(item.invoice_total)}<small>Outstanding: {value(item.outstanding)}</small></td><td><Status label={status} /></td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`invoices/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), paid_amount: next === "PAID" ? item.invoice_total : null }, `Invoice moved to ${next}.`)}>{next.replaceAll("_", " ")}</button> : "—"}</td></tr>; })}{overview.charges.map((item) => <tr key={`c-${value(item.public_id)}`}><td><strong>{value(item.charge_code)}</strong><small>{value(item.charge_type_code)} · {value(item.description)}</small></td><td>{value(item.lease__lease_number)}</td><td>{displayDate(item.effective_from)}<small>{value(item.frequency_code)}</small></td><td>{value(item.currency_code)} {value(item.amount)}</td><td><Status label={value(item.status_code)} /></td><td>—</td></tr>)}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "experience" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("occupancies", { lease_public_id: occupancyForm.lease_public_id, occupant_reference: occupancyForm.occupant_reference, move_in_on: nullable(occupancyForm.move_in_on), move_out_on: nullable(occupancyForm.move_out_on), occupant_count: occupancyForm.occupant_count, key_handover_evidence: occupancyForm.key_handover_reference ? { reference: occupancyForm.key_handover_reference } : {}, meter_readings: occupancyForm.opening_meter_reference ? { opening_reference: occupancyForm.opening_meter_reference } : {} }, "Occupancy record created."); setOccupancyForm(emptyOccupancy); }}>
            <p className={styles.kicker}>MOVE-IN / MOVE-OUT</p><h2>Record occupancy evidence</h2><div className={styles.formGrid}>
              <Field label="Lease" wide><select required value={occupancyForm.lease_public_id} onChange={(e: InputEvent) => setOccupancyForm({ ...occupancyForm, lease_public_id: e.target.value })}><option value="">Select lease</option>{leases.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.lease_number)} · {value(item.unit__code)}</option>)}</select></Field>
              <Field label="Occupant reference"><input value={occupancyForm.occupant_reference} onChange={(e: InputEvent) => setOccupancyForm({ ...occupancyForm, occupant_reference: e.target.value })} /></Field>
              <Field label="Occupant count"><input type="number" min="1" value={occupancyForm.occupant_count} onChange={(e: InputEvent) => setOccupancyForm({ ...occupancyForm, occupant_count: e.target.value })} /></Field>
              <Field label="Move-in date"><input type="date" value={occupancyForm.move_in_on} onChange={(e: InputEvent) => setOccupancyForm({ ...occupancyForm, move_in_on: e.target.value })} /></Field>
              <Field label="Move-out date"><input type="date" value={occupancyForm.move_out_on} onChange={(e: InputEvent) => setOccupancyForm({ ...occupancyForm, move_out_on: e.target.value })} /></Field>
              <Field label="Key handover reference" wide><input value={occupancyForm.key_handover_reference} onChange={(e: InputEvent) => setOccupancyForm({ ...occupancyForm, key_handover_reference: e.target.value })} /></Field>
              <Field label="Opening meter reference" wide><input value={occupancyForm.opening_meter_reference} onChange={(e: InputEvent) => setOccupancyForm({ ...occupancyForm, opening_meter_reference: e.target.value })} /></Field>
            </div><button disabled={working}>Create occupancy record</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("cases", { ...caseForm, unit_public_id: nullable(caseForm.unit_public_id) }, "Tenant experience case created."); setCaseForm(emptyCase); }}>
            <p className={styles.kicker}>TENANT EXPERIENCE</p><h2>Raise tenant case</h2><div className={styles.formGrid}>
              <Field label="Tenant"><select required value={caseForm.tenant_public_id} onChange={(e: InputEvent) => setCaseForm({ ...caseForm, tenant_public_id: e.target.value })}><option value="">Select tenant</option>{tenants.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.display_name)}</option>)}</select></Field>
              <Field label="Property"><select required value={caseForm.property_public_id} onChange={(e: InputEvent) => setCaseForm({ ...caseForm, property_public_id: e.target.value, unit_public_id: "" })}><option value="">Select property</option>{properties.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)}</option>)}</select></Field>
              <Field label="Unit"><select value={caseForm.unit_public_id} onChange={(e: InputEvent) => setCaseForm({ ...caseForm, unit_public_id: e.target.value })}><option value="">No unit</option>{units.filter((item) => value(item.property__public_id) === caseForm.property_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)}</option>)}</select></Field>
              <Field label="Case number"><input required value={caseForm.case_number} onChange={(e: InputEvent) => setCaseForm({ ...caseForm, case_number: e.target.value })} /></Field>
              <Field label="Category"><select value={caseForm.category_code} onChange={(e: InputEvent) => setCaseForm({ ...caseForm, category_code: e.target.value })}><option>SERVICE</option><option>COMPLAINT</option><option>BILLING</option><option>ACCESS</option><option>FEEDBACK</option><option>MOVE_IN</option><option>MOVE_OUT</option></select></Field>
              <Field label="Priority"><select value={caseForm.priority_code} onChange={(e: InputEvent) => setCaseForm({ ...caseForm, priority_code: e.target.value })}><option>LOW</option><option>NORMAL</option><option>HIGH</option><option>CRITICAL</option></select></Field>
              <Field label="Title" wide><input required value={caseForm.title} onChange={(e: InputEvent) => setCaseForm({ ...caseForm, title: e.target.value })} /></Field>
              <Field label="Description" wide><textarea value={caseForm.description} onChange={(e: InputEvent) => setCaseForm({ ...caseForm, description: e.target.value })} /></Field>
            </div><button disabled={working}>Create tenant case</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>OCCUPANCY & EXPERIENCE CONTROL</p><h2>Move-in evidence and tenant cases</h2><div className={styles.tableWrap}><table><thead><tr><th>Record / case</th><th>Lease / tenant</th><th>Unit / priority</th><th>Dates / SLA</th><th>Status</th><th>Control</th></tr></thead><tbody>{overview.occupancies.map((item) => { const status = value(item.status_code); const next = nextOccupancy(status); return <tr key={`o-${value(item.public_id)}`}><td><strong>Occupancy</strong><small>{value(item.occupant_reference) || "Lease occupant"}</small></td><td>{value(item.lease__lease_number)}</td><td>{value(item.unit__code)}<small>{value(item.occupant_count)} occupants</small></td><td>{displayDate(item.move_in_on)}<small>{displayDate(item.move_out_on)}</small></td><td><Status label={status} /></td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`occupancies/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version) }, `Occupancy moved to ${next}.`)}>{next.replaceAll("_", " ")}</button> : "—"}</td></tr>; })}{overview.tenant_cases.map((item) => { const status = value(item.status_code); const next = nextCase(status); return <tr key={`x-${value(item.public_id)}`}><td><strong>{value(item.case_number)}</strong><small>{value(item.title)}</small></td><td>{value(item.tenant__display_name)}<small>{value(item.property__code)}</small></td><td>{value(item.unit__code) || "General"}<small>{value(item.priority_code)} · {value(item.category_code)}</small></td><td>{displayDate(item.response_due_at)}<small>{displayDate(item.resolution_due_at)}</small></td><td><Status label={status} /></td><td>{next ? <button className={styles.smallButton} type="button" onClick={() => void post(`cases/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), satisfaction_score: next === "CLOSED" ? 5 : null }, `Tenant case moved to ${next}.`)}>{next.replaceAll("_", " ")}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}
    </main>
  );
}
