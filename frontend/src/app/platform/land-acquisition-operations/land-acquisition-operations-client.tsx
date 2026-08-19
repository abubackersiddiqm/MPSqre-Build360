"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useState } from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";

import styles from "./land-acquisition-operations.module.css";

type Row = Record<string, unknown>;
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: { status: string; version: number; due_diligence_target_days: number; approval_alert_days: number; minimum_margin_percent: string };
  metrics: Record<string, string | number>;
  parcels: Row[];
  ownerships: Row[];
  diligence: Row[];
  feasibilities: Row[];
  opportunities: Row[];
  offers: Row[];
  approvals: Row[];
  risks: Row[];
  events: Row[];
  portfolio: { parcel_status: Row[]; opportunity_stage: Row[]; risk_status: Row[]; pipeline_value: Row[]; accepted_offer_value: Row[]; area_by_unit: Row[] };
};

type Tab = "summary" | "parcels" | "diligence" | "feasibility" | "acquisition" | "approvals";
type InputEvent = ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>;
type FormState = Record<string, string>;

const emptyParcel = { parcel_code: "", name: "", parcel_type_code: "FREEHOLD", jurisdiction_code: "", survey_reference: "", title_reference: "", gross_area: "", usable_area: "", area_unit_code: "SQ_M", zoning_code: "", current_use_code: "", status_code: "PROSPECT" } satisfies FormState;
const emptyOwner = { parcel_public_id: "", owner_name: "", owner_type_code: "INDIVIDUAL", share_percent: "100", ownership_document_reference: "", encumbrance_flag: "false", encumbrance_summary: "" } satisfies FormState;
const emptyDiligence = { parcel_public_id: "", case_number: "", category_code: "TITLE", opened_on: "", target_on: "", risk_rating_code: "MEDIUM", findings: "", blockers: "" } satisfies FormState;
const emptyFeasibility = { parcel_public_id: "", scenario_code: "", name: "", scenario_type_code: "BASE_CASE", gross_development_area: "", saleable_area: "", area_unit_code: "SQ_M", planned_units: "0", estimated_revenue: "0", land_cost: "0", construction_cost: "0", soft_cost: "0", finance_cost: "0", contingency_cost: "0", irr_percent: "", currency_code: "" } satisfies FormState;
const emptyOpportunity = { parcel_public_id: "", feasibility_public_id: "", opportunity_code: "", seller_name: "", acquisition_method_code: "PURCHASE", asking_price: "", target_price: "", approved_budget: "", currency_code: "", probability_percent: "0", expected_close_on: "" } satisfies FormState;
const emptyOffer = { opportunity_public_id: "", offer_number: "", offer_date: "", amount: "", currency_code: "", validity_until: "", conditions: "" } satisfies FormState;
const emptyApproval = { parcel_public_id: "", opportunity_public_id: "", approval_code: "", approval_type_code: "LAND_USE", authority_name: "", application_reference: "", submitted_on: "", expected_on: "", approved_on: "", expiry_on: "", status_code: "PLANNED", mandatory_for_acquisition: "false", evidence_reference: "" } satisfies FormState;
const emptyRisk = { parcel_public_id: "", opportunity_public_id: "", risk_number: "", category_code: "LEGAL", severity_code: "MEDIUM", probability_code: "POSSIBLE", title: "", description: "", mitigation_plan: "", due_on: "" } satisfies FormState;

function value(input: unknown): string {
  if (input === null || input === undefined) return "";
  return String(input);
}

function nullable(input: string): string | null {
  return input.trim() ? input.trim() : null;
}

function decimal(input: string): string {
  return input.trim() || "0";
}

function jsonList(input: string): Array<{ note: string }> {
  return input.trim() ? input.split("\n").map((note) => ({ note: note.trim() })).filter((item) => item.note) : [];
}

function jsonObject(input: string): Record<string, string> {
  return input.trim() ? { note: input.trim() } : {};
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

function Metric({ label, metric, note }: { label: string; metric: string | number | undefined; note: string }) {
  return <article className={styles.metric}><span>{label}</span><strong>{metric ?? "—"}</strong><small>{note}</small></article>;
}

function Status({ label }: { label: string }) {
  return <span className={styles.pill}>{label || "—"}</span>;
}

function Field({ label, children, wide = false }: { label: string; children?: ReactNode; wide?: boolean }) {
  return <label className={wide ? styles.full : undefined}><span>{label}</span>{children}</label>;
}

function update<T extends FormState>(setter: Dispatch<SetStateAction<T>>, form: T) {
  return (event: InputEvent) =>
    setter({ ...form, [event.target.name]: event.target.value } as T);
}

function nextDiligence(status: string): string {
  if (status === "DRAFT") return "IN_REVIEW";
  if (status === "IN_REVIEW" || status === "CONDITIONAL") return "CLEARED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextFeasibility(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextOpportunity(status: string): string {
  if (status === "IDENTIFIED") return "SCREENING";
  if (status === "SCREENING") return "DUE_DILIGENCE";
  if (status === "DUE_DILIGENCE") return "NEGOTIATION";
  if (status === "NEGOTIATION") return "APPROVED";
  if (status === "APPROVED") return "ACQUIRED";
  if (status === "ACQUIRED") return "CLOSED";
  return "";
}

function nextOffer(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "ISSUED";
  if (status === "ISSUED") return "ACCEPTED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextApproval(status: string): string {
  if (status === "PLANNED") return "SUBMITTED";
  if (status === "SUBMITTED") return "UNDER_REVIEW";
  if (status === "UNDER_REVIEW") return "APPROVED";
  if (["REJECTED", "EXPIRED", "WITHDRAWN"].includes(status)) return "PLANNED";
  return "";
}

function nextRisk(status: string): string {
  if (status === "OPEN") return "MITIGATING";
  if (status === "MITIGATING" || status === "ACCEPTED") return "CLOSED";
  if (status === "CLOSED") return "OPEN";
  return "";
}

export function LandAcquisitionOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [parcelForm, setParcelForm] = useState(emptyParcel);
  const [ownerForm, setOwnerForm] = useState(emptyOwner);
  const [diligenceForm, setDiligenceForm] = useState(emptyDiligence);
  const [feasibilityForm, setFeasibilityForm] = useState(emptyFeasibility);
  const [opportunityForm, setOpportunityForm] = useState(emptyOpportunity);
  const [offerForm, setOfferForm] = useState(emptyOffer);
  const [approvalForm, setApprovalForm] = useState(emptyApproval);
  const [riskForm, setRiskForm] = useState(emptyRisk);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/platform/land-acquisition-operations/overview", { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(payload, "Land acquisition operations could not be loaded."));
      setOverview(payload as Overview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Land acquisition operations could not be loaded.");
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
      const response = await fetch(`/api/platform/land-acquisition-operations/${path}`, {
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

  if (loading && !overview) {
    return <main className={styles.shell}><section className={styles.loading}>Preparing the land acquisition command centre…</section></main>;
  }
  if (!overview) {
    return <main className={styles.shell}><section className={styles.errorCard}><p className={styles.kicker}>LAND CONTROL UNAVAILABLE</p><h2>Land acquisition, feasibility and approvals could not be opened.</h2><p>{error || "The request could not be completed."}</p><button type="button" onClick={() => void refresh()}>Retry workspace</button></section></main>;
  }

  const metrics = overview.metrics;
  const parcels = overview.parcels;
  const ownerships = overview.ownerships;
  const diligence = overview.diligence;
  const feasibilities = overview.feasibilities;
  const opportunities = overview.opportunities;
  const offers = overview.offers;
  const approvals = overview.approvals;
  const risks = overview.risks;

  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 43</p>
          <h1>Land acquisition, development feasibility & statutory approvals</h1>
          <p className={styles.lead}>Govern parcels, ownership evidence, due diligence, investment feasibility, acquisition negotiations, statutory approvals and land risk from one tenant-safe development command centre.</p>
          <div className={styles.tags}><span>{overview.company.name}</span><span>{overview.company.currency}</span><span>{overview.company.timezone}</span><span>Policy {overview.policy.status}</span></div>
        </div>
        <div className={styles.heroActions}><span className={styles.activeLabel}>PHASE 43 LAND ACQUISITION ACTIVE</span><button type="button" onClick={() => void refresh()}>Refresh land cockpit</button></div>
      </header>

      <section className={styles.metrics}>
        <Metric label="Active parcels" metric={metrics.active_parcels} note={`${metrics.verified_owners} verified ownership records`} />
        <Metric label="Due diligence" metric={metrics.open_diligence} note={`${metrics.diligence_blockers} unresolved blockers`} />
        <Metric label="Feasibility" metric={metrics.approved_scenarios} note={`${metrics.margin_exceptions} approved below threshold`} />
        <Metric label="Acquisition pipeline" metric={metrics.pipeline_opportunities} note={`${metrics.accepted_offers} accepted offers`} />
        <Metric label="Approval watch" metric={metrics.expiring_approvals} note={`Inside ${overview.policy.approval_alert_days} days`} />
        <Metric label="Land risk" metric={metrics.open_high_risks} note="Open high or critical exposures" />
      </section>

      {error ? <p className={styles.alert}>{error}</p> : null}
      {notice ? <p className={styles.notice}>{notice}</p> : null}

      <nav className={styles.tabs} aria-label="Land acquisition sections">
        {(["summary", "parcels", "diligence", "feasibility", "acquisition", "approvals"] as Tab[]).map((item) => <button key={item} type="button" className={tab === item ? styles.selected : undefined} onClick={() => setTab(item)}>{item === "summary" ? "Summary" : item === "parcels" ? "Parcels & title" : item === "diligence" ? "Due diligence" : item === "feasibility" ? "Feasibility" : item === "acquisition" ? "Acquisition" : "Approvals & risk"}</button>)}
      </nav>

      {tab === "summary" ? <section className={styles.grid}>
        <article className={styles.card}><p className={styles.kicker}>GOVERNANCE POSTURE</p><h2>Acquisition policy</h2><dl className={styles.definition}><div><dt>Status</dt><dd>{overview.policy.status}</dd></div><div><dt>Due-diligence target</dt><dd>{overview.policy.due_diligence_target_days} days</dd></div><div><dt>Approval watch</dt><dd>{overview.policy.approval_alert_days} days</dd></div><div><dt>Minimum margin</dt><dd>{overview.policy.minimum_margin_percent}%</dd></div></dl></article>
        <article className={styles.card}><p className={styles.kicker}>LAND BANK</p><h2>Area position</h2><div className={styles.statusGrid}>{overview.portfolio.area_by_unit.map((item) => <div key={value(item.area_unit_code)}><span>{value(item.area_unit_code)}</span><strong>{value(item.gross_area)}</strong></div>)}</div></article>
        <article className={styles.card}><p className={styles.kicker}>PIPELINE VALUE</p><h2>Target acquisition position</h2><div className={styles.statusGrid}>{overview.portfolio.pipeline_value.length ? overview.portfolio.pipeline_value.map((item) => <div key={value(item.currency_code)}><span>{value(item.currency_code)}</span><strong>{value(item.amount)}</strong></div>) : <p>No active acquisition pipeline.</p>}</div></article>
        <article className={styles.card}><p className={styles.kicker}>RECENT ACTIVITY</p><h2>Acquisition timeline</h2><div className={styles.tableWrap}><table><thead><tr><th>Opportunity</th><th>Event</th><th>When</th><th>Summary</th></tr></thead><tbody>{overview.events.slice(0, 12).map((item) => <tr key={value(item.public_id)}><td>{value(item.opportunity__opportunity_code)}</td><td>{value(item.event_type_code)}</td><td>{displayDate(item.event_on)}</td><td>{value(item.summary)}</td></tr>)}</tbody></table></div></article>
      </section> : null}

      {tab === "parcels" ? <section className={styles.grid}>
        <article className={styles.card}><p className={styles.kicker}>LAND MASTER</p><h2>Register parcel</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("parcels", { ...parcelForm, gross_area: decimal(parcelForm.gross_area), usable_area: nullable(parcelForm.usable_area) }, "Land parcel registered.").then((result) => { if (result) setParcelForm(emptyParcel); }); }}><div className={styles.formGrid}><Field label="Parcel code"><input name="parcel_code" required value={parcelForm.parcel_code} onChange={update(setParcelForm, parcelForm)} /></Field><Field label="Parcel name"><input name="name" required value={parcelForm.name} onChange={update(setParcelForm, parcelForm)} /></Field><Field label="Type"><select name="parcel_type_code" value={parcelForm.parcel_type_code} onChange={update(setParcelForm, parcelForm)}><option>FREEHOLD</option><option>LEASEHOLD</option><option>GOVERNMENT_ALLOTMENT</option><option>JOINT_DEVELOPMENT</option></select></Field><Field label="Jurisdiction"><input name="jurisdiction_code" value={parcelForm.jurisdiction_code} onChange={update(setParcelForm, parcelForm)} /></Field><Field label="Survey reference"><input name="survey_reference" value={parcelForm.survey_reference} onChange={update(setParcelForm, parcelForm)} /></Field><Field label="Title reference"><input name="title_reference" value={parcelForm.title_reference} onChange={update(setParcelForm, parcelForm)} /></Field><Field label="Gross area"><input type="number" step="0.001" name="gross_area" required value={parcelForm.gross_area} onChange={update(setParcelForm, parcelForm)} /></Field><Field label="Usable area"><input type="number" step="0.001" name="usable_area" value={parcelForm.usable_area} onChange={update(setParcelForm, parcelForm)} /></Field><Field label="Area unit"><select name="area_unit_code" value={parcelForm.area_unit_code} onChange={update(setParcelForm, parcelForm)}><option>SQ_M</option><option>SQ_FT</option><option>ACRE</option><option>HECTARE</option></select></Field><Field label="Zoning"><input name="zoning_code" value={parcelForm.zoning_code} onChange={update(setParcelForm, parcelForm)} /></Field></div><button disabled={working}>Register parcel</button></form></article>
        <article className={styles.card}><p className={styles.kicker}>TITLE CHAIN</p><h2>Add ownership interest</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("ownerships", { ...ownerForm, share_percent: decimal(ownerForm.share_percent), encumbrance_flag: ownerForm.encumbrance_flag === "true" }, "Ownership interest recorded.").then((result) => { if (result) setOwnerForm(emptyOwner); }); }}><div className={styles.formGrid}><Field label="Parcel" wide><select name="parcel_public_id" required value={ownerForm.parcel_public_id} onChange={update(setOwnerForm, ownerForm)}><option value="">Select parcel</option>{parcels.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.parcel_code)} · {value(item.name)}</option>)}</select></Field><Field label="Owner name"><input name="owner_name" required value={ownerForm.owner_name} onChange={update(setOwnerForm, ownerForm)} /></Field><Field label="Owner type"><select name="owner_type_code" value={ownerForm.owner_type_code} onChange={update(setOwnerForm, ownerForm)}><option>INDIVIDUAL</option><option>COMPANY</option><option>TRUST</option><option>GOVERNMENT</option></select></Field><Field label="Share %"><input type="number" step="0.0001" name="share_percent" required value={ownerForm.share_percent} onChange={update(setOwnerForm, ownerForm)} /></Field><Field label="Title document"><input name="ownership_document_reference" value={ownerForm.ownership_document_reference} onChange={update(setOwnerForm, ownerForm)} /></Field><Field label="Encumbrance"><select name="encumbrance_flag" value={ownerForm.encumbrance_flag} onChange={update(setOwnerForm, ownerForm)}><option value="false">No</option><option value="true">Yes</option></select></Field><Field label="Encumbrance summary" wide><textarea name="encumbrance_summary" value={ownerForm.encumbrance_summary} onChange={update(setOwnerForm, ownerForm)} /></Field></div><button disabled={working}>Record ownership</button></form></article>
        <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>PARCEL & TITLE REGISTER</p><h2>Governed land bank</h2><div className={styles.tableWrap}><table><thead><tr><th>Parcel</th><th>Jurisdiction</th><th>Area</th><th>Zoning</th><th>Status</th></tr></thead><tbody>{parcels.map((item) => <tr key={value(item.public_id)}><td><strong>{value(item.parcel_code)}</strong><small>{value(item.name)}</small></td><td>{value(item.jurisdiction_code)}</td><td>{value(item.gross_area)} {value(item.area_unit_code)}</td><td>{value(item.zoning_code)}</td><td><Status label={value(item.status_code)} /></td></tr>)}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Parcel</th><th>Owner</th><th>Share</th><th>Encumbrance</th><th>Verification</th><th>Control</th></tr></thead><tbody>{ownerships.map((item) => <tr key={value(item.public_id)}><td>{value(item.parcel__parcel_code)}</td><td><strong>{value(item.owner_name)}</strong><small>{value(item.owner_type_code)}</small></td><td>{value(item.share_percent)}%</td><td>{value(item.encumbrance_flag) === "true" ? "Yes" : "No"}</td><td><Status label={value(item.verification_status_code)} /></td><td>{value(item.verification_status_code) === "PENDING" ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`ownerships/${value(item.public_id)}/transition`, { status_code: "VERIFIED", expected_version: Number(item.version), note: "Ownership evidence independently verified." }, "Ownership verified.")}>VERIFY</button> : "—"}</td></tr>)}</tbody></table></div></article>
      </section> : null}

      {tab === "diligence" ? <section className={styles.grid}>
        <article className={styles.card}><p className={styles.kicker}>DUE DILIGENCE</p><h2>Open review case</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("diligence", { parcel_public_id: diligenceForm.parcel_public_id, case_number: diligenceForm.case_number, category_code: diligenceForm.category_code, opened_on: nullable(diligenceForm.opened_on), target_on: nullable(diligenceForm.target_on), risk_rating_code: diligenceForm.risk_rating_code, findings: jsonList(diligenceForm.findings), blockers: jsonList(diligenceForm.blockers) }, "Due-diligence case opened.").then((result) => { if (result) setDiligenceForm(emptyDiligence); }); }}><div className={styles.formGrid}><Field label="Parcel" wide><select name="parcel_public_id" required value={diligenceForm.parcel_public_id} onChange={update(setDiligenceForm, diligenceForm)}><option value="">Select parcel</option>{parcels.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.parcel_code)}</option>)}</select></Field><Field label="Case number"><input name="case_number" required value={diligenceForm.case_number} onChange={update(setDiligenceForm, diligenceForm)} /></Field><Field label="Category"><select name="category_code" value={diligenceForm.category_code} onChange={update(setDiligenceForm, diligenceForm)}><option>TITLE</option><option>LEGAL</option><option>TECHNICAL</option><option>ENVIRONMENTAL</option><option>PLANNING</option><option>TAX</option></select></Field><Field label="Opened on"><input type="date" name="opened_on" value={diligenceForm.opened_on} onChange={update(setDiligenceForm, diligenceForm)} /></Field><Field label="Target on"><input type="date" name="target_on" value={diligenceForm.target_on} onChange={update(setDiligenceForm, diligenceForm)} /></Field><Field label="Risk rating"><select name="risk_rating_code" value={diligenceForm.risk_rating_code} onChange={update(setDiligenceForm, diligenceForm)}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></Field><Field label="Findings, one per line" wide><textarea name="findings" value={diligenceForm.findings} onChange={update(setDiligenceForm, diligenceForm)} /></Field><Field label="Blockers, one per line" wide><textarea name="blockers" value={diligenceForm.blockers} onChange={update(setDiligenceForm, diligenceForm)} /></Field></div><button disabled={working}>Open due diligence</button></form></article>
        <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>ASSURANCE REGISTER</p><h2>Due-diligence decisions</h2><div className={styles.tableWrap}><table><thead><tr><th>Case</th><th>Parcel</th><th>Category</th><th>Target</th><th>Risk</th><th>Blockers</th><th>Status</th><th>Control</th></tr></thead><tbody>{diligence.map((item) => { const next = nextDiligence(value(item.status_code)); const blockerCount = Array.isArray(item.blockers) ? item.blockers.length : 0; return <tr key={value(item.public_id)}><td>{value(item.case_number)}</td><td>{value(item.parcel__parcel_code)}</td><td>{value(item.category_code)}</td><td>{displayDate(item.target_on)}</td><td>{value(item.risk_rating_code)}</td><td>{blockerCount}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`diligence/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: next === "CLEARED" ? "Independent due-diligence decision completed." : "Review initiated." }, `Due diligence moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
      </section> : null}

      {tab === "feasibility" ? <section className={styles.grid}>
        <article className={styles.card}><p className={styles.kicker}>INVESTMENT CASE</p><h2>Create feasibility scenario</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("feasibilities", { ...feasibilityForm, gross_development_area: decimal(feasibilityForm.gross_development_area), saleable_area: decimal(feasibilityForm.saleable_area), planned_units: Number(feasibilityForm.planned_units), estimated_revenue: decimal(feasibilityForm.estimated_revenue), land_cost: decimal(feasibilityForm.land_cost), construction_cost: decimal(feasibilityForm.construction_cost), soft_cost: decimal(feasibilityForm.soft_cost), finance_cost: decimal(feasibilityForm.finance_cost), contingency_cost: decimal(feasibilityForm.contingency_cost), irr_percent: nullable(feasibilityForm.irr_percent), currency_code: feasibilityForm.currency_code || undefined }, "Feasibility scenario created.").then((result) => { if (result) setFeasibilityForm(emptyFeasibility); }); }}><div className={styles.formGrid}><Field label="Parcel" wide><select name="parcel_public_id" required value={feasibilityForm.parcel_public_id} onChange={update(setFeasibilityForm, feasibilityForm)}><option value="">Select parcel</option>{parcels.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.parcel_code)}</option>)}</select></Field><Field label="Scenario code"><input name="scenario_code" required value={feasibilityForm.scenario_code} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="Scenario name"><input name="name" required value={feasibilityForm.name} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="Gross development area"><input type="number" step="0.001" name="gross_development_area" value={feasibilityForm.gross_development_area} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="Saleable area"><input type="number" step="0.001" name="saleable_area" value={feasibilityForm.saleable_area} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="Planned units"><input type="number" min="0" name="planned_units" value={feasibilityForm.planned_units} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="Estimated revenue"><input type="number" step="0.01" name="estimated_revenue" value={feasibilityForm.estimated_revenue} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="Land cost"><input type="number" step="0.01" name="land_cost" value={feasibilityForm.land_cost} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="Construction cost"><input type="number" step="0.01" name="construction_cost" value={feasibilityForm.construction_cost} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="Soft cost"><input type="number" step="0.01" name="soft_cost" value={feasibilityForm.soft_cost} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="Finance cost"><input type="number" step="0.01" name="finance_cost" value={feasibilityForm.finance_cost} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="Contingency"><input type="number" step="0.01" name="contingency_cost" value={feasibilityForm.contingency_cost} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field><Field label="IRR %"><input type="number" step="0.0001" name="irr_percent" value={feasibilityForm.irr_percent} onChange={update(setFeasibilityForm, feasibilityForm)} /></Field></div><button disabled={working}>Create feasibility</button></form></article>
        <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>FEASIBILITY REGISTER</p><h2>Development scenarios</h2><div className={styles.tableWrap}><table><thead><tr><th>Scenario</th><th>Parcel</th><th>Revenue</th><th>Land</th><th>Construction</th><th>Margin</th><th>IRR</th><th>Status</th><th>Control</th></tr></thead><tbody>{feasibilities.map((item) => { const next = nextFeasibility(value(item.status_code)); return <tr key={value(item.public_id)}><td><strong>{value(item.scenario_code)}</strong><small>{value(item.name)}</small></td><td>{value(item.parcel__parcel_code)}</td><td>{value(item.currency_code)} {value(item.estimated_revenue)}</td><td>{value(item.land_cost)}</td><td>{value(item.construction_cost)}</td><td>{value(item.projected_margin_percent)}%</td><td>{value(item.irr_percent) || "—"}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`feasibilities/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: next === "APPROVED" ? "Investment decision approved." : "Scenario submitted for review." }, `Feasibility moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
      </section> : null}

      {tab === "acquisition" ? <section className={styles.grid}>
        <article className={styles.card}><p className={styles.kicker}>ACQUISITION PIPELINE</p><h2>Create opportunity</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("opportunities", { ...opportunityForm, feasibility_public_id: nullable(opportunityForm.feasibility_public_id), asking_price: nullable(opportunityForm.asking_price), target_price: nullable(opportunityForm.target_price), approved_budget: nullable(opportunityForm.approved_budget), currency_code: opportunityForm.currency_code || undefined, probability_percent: decimal(opportunityForm.probability_percent), expected_close_on: nullable(opportunityForm.expected_close_on) }, "Acquisition opportunity created.").then((result) => { if (result) setOpportunityForm(emptyOpportunity); }); }}><div className={styles.formGrid}><Field label="Parcel" wide><select name="parcel_public_id" required value={opportunityForm.parcel_public_id} onChange={update(setOpportunityForm, opportunityForm)}><option value="">Select parcel</option>{parcels.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.parcel_code)}</option>)}</select></Field><Field label="Approved feasibility" wide><select name="feasibility_public_id" value={opportunityForm.feasibility_public_id} onChange={update(setOpportunityForm, opportunityForm)}><option value="">Attach later</option>{feasibilities.filter((item) => value(item.status_code) === "APPROVED" && (!opportunityForm.parcel_public_id || value(item.parcel__public_id) === opportunityForm.parcel_public_id)).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.scenario_code)} · {value(item.projected_margin_percent)}%</option>)}</select></Field><Field label="Opportunity code"><input name="opportunity_code" required value={opportunityForm.opportunity_code} onChange={update(setOpportunityForm, opportunityForm)} /></Field><Field label="Seller"><input name="seller_name" required value={opportunityForm.seller_name} onChange={update(setOpportunityForm, opportunityForm)} /></Field><Field label="Method"><select name="acquisition_method_code" value={opportunityForm.acquisition_method_code} onChange={update(setOpportunityForm, opportunityForm)}><option>PURCHASE</option><option>JOINT_VENTURE</option><option>DEVELOPMENT_AGREEMENT</option><option>LONG_LEASE</option><option>GOVERNMENT_ALLOTMENT</option></select></Field><Field label="Asking price"><input type="number" step="0.01" name="asking_price" value={opportunityForm.asking_price} onChange={update(setOpportunityForm, opportunityForm)} /></Field><Field label="Target price"><input type="number" step="0.01" name="target_price" value={opportunityForm.target_price} onChange={update(setOpportunityForm, opportunityForm)} /></Field><Field label="Probability %"><input type="number" step="0.0001" name="probability_percent" value={opportunityForm.probability_percent} onChange={update(setOpportunityForm, opportunityForm)} /></Field><Field label="Expected close"><input type="date" name="expected_close_on" value={opportunityForm.expected_close_on} onChange={update(setOpportunityForm, opportunityForm)} /></Field></div><button disabled={working}>Create opportunity</button></form></article>
        <article className={styles.card}><p className={styles.kicker}>COMMERCIAL OFFER</p><h2>Prepare land offer</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("offers", { opportunity_public_id: offerForm.opportunity_public_id, offer_number: offerForm.offer_number, offer_date: offerForm.offer_date, amount: decimal(offerForm.amount), currency_code: offerForm.currency_code || undefined, validity_until: nullable(offerForm.validity_until), conditions: jsonObject(offerForm.conditions) }, "Commercial offer created.").then((result) => { if (result) setOfferForm(emptyOffer); }); }}><div className={styles.formGrid}><Field label="Negotiation" wide><select name="opportunity_public_id" required value={offerForm.opportunity_public_id} onChange={update(setOfferForm, offerForm)}><option value="">Select opportunity</option>{opportunities.filter((item) => ["NEGOTIATION", "APPROVED"].includes(value(item.stage_code))).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.opportunity_code)} · {value(item.parcel__parcel_code)}</option>)}</select></Field><Field label="Offer number"><input name="offer_number" required value={offerForm.offer_number} onChange={update(setOfferForm, offerForm)} /></Field><Field label="Offer date"><input type="date" name="offer_date" required value={offerForm.offer_date} onChange={update(setOfferForm, offerForm)} /></Field><Field label="Amount"><input type="number" step="0.01" name="amount" required value={offerForm.amount} onChange={update(setOfferForm, offerForm)} /></Field><Field label="Validity"><input type="date" name="validity_until" value={offerForm.validity_until} onChange={update(setOfferForm, offerForm)} /></Field><Field label="Conditions" wide><textarea name="conditions" value={offerForm.conditions} onChange={update(setOfferForm, offerForm)} /></Field></div><button disabled={working}>Create offer</button></form></article>
        <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>PIPELINE GOVERNANCE</p><h2>Opportunity and offer register</h2><div className={styles.tableWrap}><table><thead><tr><th>Opportunity</th><th>Parcel</th><th>Seller</th><th>Method</th><th>Target</th><th>Probability</th><th>Stage</th><th>Control</th></tr></thead><tbody>{opportunities.map((item) => { const next = nextOpportunity(value(item.stage_code)); return <tr key={value(item.public_id)}><td>{value(item.opportunity_code)}</td><td>{value(item.parcel__parcel_code)}</td><td>{value(item.seller_name)}</td><td>{value(item.acquisition_method_code)}</td><td>{value(item.currency_code)} {value(item.target_price)}</td><td>{value(item.probability_percent)}%</td><td><Status label={value(item.stage_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`opportunities/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Acquisition stage advanced to ${next}.` }, `Opportunity moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Offer</th><th>Opportunity</th><th>Date</th><th>Amount</th><th>Valid until</th><th>Status</th><th>Control</th></tr></thead><tbody>{offers.map((item) => { const next = nextOffer(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.offer_number)}</td><td>{value(item.opportunity__opportunity_code)}</td><td>{displayDate(item.offer_date)}</td><td>{value(item.currency_code)} {value(item.amount)}</td><td>{displayDate(item.validity_until)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`offers/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Commercial offer advanced to ${next}.` }, `Offer moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
      </section> : null}

      {tab === "approvals" ? <section className={styles.grid}>
        <article className={styles.card}><p className={styles.kicker}>STATUTORY CONTROL</p><h2>Register approval</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("approvals", { ...approvalForm, opportunity_public_id: nullable(approvalForm.opportunity_public_id), submitted_on: nullable(approvalForm.submitted_on), expected_on: nullable(approvalForm.expected_on), approved_on: nullable(approvalForm.approved_on), expiry_on: nullable(approvalForm.expiry_on), mandatory_for_acquisition: approvalForm.mandatory_for_acquisition === "true" }, "Statutory approval registered.").then((result) => { if (result) setApprovalForm(emptyApproval); }); }}><div className={styles.formGrid}><Field label="Parcel" wide><select name="parcel_public_id" required value={approvalForm.parcel_public_id} onChange={update(setApprovalForm, approvalForm)}><option value="">Select parcel</option>{parcels.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.parcel_code)}</option>)}</select></Field><Field label="Opportunity" wide><select name="opportunity_public_id" value={approvalForm.opportunity_public_id} onChange={update(setApprovalForm, approvalForm)}><option value="">Parcel-level approval</option>{opportunities.filter((item) => !approvalForm.parcel_public_id || value(item.parcel__public_id) === approvalForm.parcel_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.opportunity_code)}</option>)}</select></Field><Field label="Approval code"><input name="approval_code" required value={approvalForm.approval_code} onChange={update(setApprovalForm, approvalForm)} /></Field><Field label="Approval type"><input name="approval_type_code" required value={approvalForm.approval_type_code} onChange={update(setApprovalForm, approvalForm)} /></Field><Field label="Authority"><input name="authority_name" required value={approvalForm.authority_name} onChange={update(setApprovalForm, approvalForm)} /></Field><Field label="Application reference"><input name="application_reference" value={approvalForm.application_reference} onChange={update(setApprovalForm, approvalForm)} /></Field><Field label="Expected decision"><input type="date" name="expected_on" value={approvalForm.expected_on} onChange={update(setApprovalForm, approvalForm)} /></Field><Field label="Expiry"><input type="date" name="expiry_on" value={approvalForm.expiry_on} onChange={update(setApprovalForm, approvalForm)} /></Field><Field label="Mandatory for acquisition"><select name="mandatory_for_acquisition" value={approvalForm.mandatory_for_acquisition} onChange={update(setApprovalForm, approvalForm)}><option value="false">No</option><option value="true">Yes</option></select></Field><Field label="Evidence reference"><input name="evidence_reference" value={approvalForm.evidence_reference} onChange={update(setApprovalForm, approvalForm)} /></Field></div><button disabled={working}>Register approval</button></form></article>
        <article className={styles.card}><p className={styles.kicker}>LAND RISK</p><h2>Register acquisition risk</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("risks", { ...riskForm, opportunity_public_id: nullable(riskForm.opportunity_public_id), due_on: nullable(riskForm.due_on) }, "Land risk registered.").then((result) => { if (result) setRiskForm(emptyRisk); }); }}><div className={styles.formGrid}><Field label="Parcel" wide><select name="parcel_public_id" required value={riskForm.parcel_public_id} onChange={update(setRiskForm, riskForm)}><option value="">Select parcel</option>{parcels.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.parcel_code)}</option>)}</select></Field><Field label="Opportunity" wide><select name="opportunity_public_id" value={riskForm.opportunity_public_id} onChange={update(setRiskForm, riskForm)}><option value="">Parcel-level risk</option>{opportunities.filter((item) => !riskForm.parcel_public_id || value(item.parcel__public_id) === riskForm.parcel_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.opportunity_code)}</option>)}</select></Field><Field label="Risk number"><input name="risk_number" required value={riskForm.risk_number} onChange={update(setRiskForm, riskForm)} /></Field><Field label="Category"><select name="category_code" value={riskForm.category_code} onChange={update(setRiskForm, riskForm)}><option>LEGAL</option><option>TITLE</option><option>PLANNING</option><option>ENVIRONMENTAL</option><option>COMMERCIAL</option><option>ACCESS</option><option>COMMUNITY</option></select></Field><Field label="Severity"><select name="severity_code" value={riskForm.severity_code} onChange={update(setRiskForm, riskForm)}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></Field><Field label="Probability"><select name="probability_code" value={riskForm.probability_code} onChange={update(setRiskForm, riskForm)}><option>UNLIKELY</option><option>POSSIBLE</option><option>LIKELY</option><option>ALMOST_CERTAIN</option></select></Field><Field label="Title" wide><input name="title" required value={riskForm.title} onChange={update(setRiskForm, riskForm)} /></Field><Field label="Description" wide><textarea name="description" value={riskForm.description} onChange={update(setRiskForm, riskForm)} /></Field><Field label="Mitigation" wide><textarea name="mitigation_plan" value={riskForm.mitigation_plan} onChange={update(setRiskForm, riskForm)} /></Field><Field label="Due on"><input type="date" name="due_on" value={riskForm.due_on} onChange={update(setRiskForm, riskForm)} /></Field></div><button disabled={working}>Register risk</button></form></article>
        <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>APPROVAL & RISK REGISTER</p><h2>Readiness controls</h2><div className={styles.tableWrap}><table><thead><tr><th>Approval</th><th>Parcel</th><th>Authority</th><th>Expected</th><th>Expiry</th><th>Mandatory</th><th>Status</th><th>Control</th></tr></thead><tbody>{approvals.map((item) => { const next = nextApproval(value(item.status_code)); return <tr key={value(item.public_id)}><td><strong>{value(item.approval_code)}</strong><small>{value(item.approval_type_code)}</small></td><td>{value(item.parcel__parcel_code)}</td><td>{value(item.authority_name)}</td><td>{displayDate(item.expected_on)}</td><td>{displayDate(item.expiry_on)}</td><td>{value(item.mandatory_for_acquisition) === "true" ? "Yes" : "No"}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`approvals/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Approval advanced to ${next}.` }, `Approval moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Risk</th><th>Parcel</th><th>Category</th><th>Severity</th><th>Due</th><th>Status</th><th>Control</th></tr></thead><tbody>{risks.map((item) => { const next = nextRisk(value(item.status_code)); return <tr key={value(item.public_id)}><td><strong>{value(item.risk_number)}</strong><small>{value(item.title)}</small></td><td>{value(item.parcel__parcel_code)}</td><td>{value(item.category_code)}</td><td>{value(item.severity_code)}</td><td>{displayDate(item.due_on)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`risks/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Risk governance transition to ${next}.` }, `Risk moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
      </section> : null}
    </main>
  );
}
