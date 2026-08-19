"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useState } from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";

import styles from "./risk-transfer-operations.module.css";

type Row = Record<string, unknown>;
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: { status: string; version: number; expiry_alert_days: number; claim_notification_sla_days: number; minimum_coverage_percent: string };
  metrics: Record<string, string | number>;
  programs: Row[];
  counterparties: Row[];
  coverages: Row[];
  premiums: Row[];
  losses: Row[];
  claims: Row[];
  instruments: Row[];
  calls: Row[];
  events: Row[];
  portfolio: Record<string, Row[]>;
};

type Tab = "summary" | "programs" | "insurance" | "claims" | "guarantees";
type InputEvent = ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>;
type FormState = Record<string, string>;

const emptyProgram = { program_code: "", name: "", program_type_code: "CONSTRUCTION_RISK", project_public_id: "", contract_public_id: "", aggregate_exposure: "", currency_code: "", starts_on: "", ends_on: "" } satisfies FormState;
const emptyParty = { counterparty_code: "", legal_name: "", counterparty_type_code: "INSURER", jurisdiction_code: "", financial_rating_code: "UNRATED", contact_email: "" } satisfies FormState;
const emptyCoverage = { program_public_id: "", counterparty_public_id: "", policy_number: "", coverage_type_code: "CONSTRUCTION_ALL_RISK", coverage_limit: "", deductible_amount: "0", annual_premium: "0", starts_on: "", ends_on: "" } satisfies FormState;
const emptyPremium = { coverage_public_id: "", installment_number: "", due_on: "", amount: "" } satisfies FormState;
const emptyLoss = { program_public_id: "", loss_number: "", occurrence_on: "", reported_on: "", loss_type_code: "PROPERTY_DAMAGE", description: "", estimated_loss: "0", severity_code: "MEDIUM" } satisfies FormState;
const emptyClaim = { loss_event_public_id: "", coverage_public_id: "", claim_number: "", notified_on: "", claimed_amount: "", reserved_amount: "0", adjuster_reference: "" } satisfies FormState;
const emptyInstrument = { program_public_id: "", counterparty_public_id: "", instrument_number: "", instrument_type_code: "PERFORMANCE_BOND", beneficiary_name: "", applicant_name: "", amount: "", issued_on: "", expiry_on: "", auto_renew_flag: "false" } satisfies FormState;
const emptyCall = { instrument_public_id: "", call_number: "", called_on: "", amount: "", reason: "" } satisfies FormState;

function value(input: unknown): string {
  return input === null || input === undefined ? "" : String(input);
}

function nullable(input: string): string | null {
  return input.trim() ? input.trim() : null;
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

function Status({ label, bad = false }: { label: string; bad?: boolean }) {
  return <span className={`${styles.pill} ${bad ? styles.bad : ""}`}>{label || "—"}</span>;
}

function Field({ label, children, wide = false }: { label: string; children?: ReactNode; wide?: boolean }) {
  return <label className={wide ? styles.full : undefined}><span>{label}</span>{children}</label>;
}

function update<T extends FormState>(setter: Dispatch<SetStateAction<T>>, form: T) {
  return (event: InputEvent) =>
    setter({ ...form, [event.target.name]: event.target.value } as T);
}

function nextGeneric(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "ACTIVE";
  if (status === "ACTIVE" || status === "SUSPENDED") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextParty(status: string): string {
  if (status === "PENDING") return "VERIFIED";
  if (status === "REJECTED") return "PENDING";
  if (status === "VERIFIED") return "SUSPENDED";
  if (status === "SUSPENDED") return "VERIFIED";
  return "";
}

function nextLoss(status: string): string {
  if (status === "OPEN") return "INVESTIGATING";
  if (status === "INVESTIGATING") return "CLAIMED";
  if (status === "CLAIMED") return "RECOVERING";
  if (status === "RECOVERING") return "CLOSED";
  return "";
}

function nextClaim(status: string): string {
  if (status === "DRAFT") return "NOTIFIED";
  if (status === "NOTIFIED" || status === "UNDER_REVIEW") return "ADMITTED";
  if (status === "ADMITTED") return "SETTLED";
  if (status === "SETTLED" || status === "REJECTED" || status === "PARTIALLY_SETTLED") return "CLOSED";
  return "";
}

function nextCall(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED" || status === "DISPUTED") return "SETTLED";
  if (status === "SETTLED") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

export function RiskTransferOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [programForm, setProgramForm] = useState(emptyProgram);
  const [partyForm, setPartyForm] = useState(emptyParty);
  const [coverageForm, setCoverageForm] = useState(emptyCoverage);
  const [premiumForm, setPremiumForm] = useState(emptyPremium);
  const [lossForm, setLossForm] = useState(emptyLoss);
  const [claimForm, setClaimForm] = useState(emptyClaim);
  const [instrumentForm, setInstrumentForm] = useState(emptyInstrument);
  const [callForm, setCallForm] = useState(emptyCall);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/platform/risk-transfer-operations/overview", { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(payload, "Risk-transfer operations could not be loaded."));
      setOverview(payload as Overview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Risk-transfer operations could not be loaded.");
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
      const response = await fetch(`/api/platform/risk-transfer-operations/${path}`, {
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
    return <main className={styles.shell}><section className={styles.loading}>Preparing the insurance, bonds and risk-transfer command centre…</section></main>;
  }
  if (!overview) {
    return <main className={styles.shell}><section className={styles.errorCard}><p className={styles.kicker}>RISK TRANSFER CONTROL UNAVAILABLE</p><h2>Insurance, bonds and guarantees could not be opened.</h2><p>{error || "The request could not be completed."}</p><button type="button" onClick={() => void refresh()}>Retry workspace</button></section></main>;
  }

  const { company, policy, metrics, programs, counterparties, coverages, premiums, losses, claims, instruments, calls, portfolio } = overview;

  return <main className={styles.shell}>
    <header className={styles.hero}>
      <div>
        <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 45</p>
        <h1>Insurance, bonds & risk transfer</h1>
        <p className={styles.lead}>Govern insurance programs, coverage, premiums, losses, claims, bank guarantees, surety bonds and recoveries from one tenant-safe construction risk cockpit.</p>
        <div className={styles.tags}><span>{company.name}</span><span>{company.currency}</span><span>{company.timezone}</span><span>Policy {policy.status}</span><span>{policy.expiry_alert_days} day expiry watch</span></div>
      </div>
      <div className={styles.heroActions}><span className={styles.activeLabel}>PHASE 45 RISK TRANSFER OPERATIONS ACTIVE</span><button type="button" disabled={loading} onClick={() => void refresh()}>Refresh risk cockpit</button></div>
    </header>

    {error ? <p className={styles.alert}>{error}</p> : null}
    {notice ? <p className={styles.notice}>{notice}</p> : null}

    <section className={styles.metrics}>
      <Metric label="Active programs" metric={metrics.active_programs ?? 0} note={`${metrics.coverage_gaps ?? 0} coverage gaps`} />
      <Metric label="Active coverages" metric={metrics.active_coverages ?? 0} note={`${metrics.expiring_coverages ?? 0} expiring soon`} />
      <Metric label="Premium exposure" metric={metrics.unpaid_premiums ?? 0} note="Due or partly paid" />
      <Metric label="Open losses" metric={metrics.open_losses ?? 0} note="Occurrence through closure" />
      <Metric label="Open claims" metric={metrics.open_claims ?? 0} note="Notification through recovery" />
      <Metric label="Guarantee watch" metric={metrics.expiring_instruments ?? 0} note={`${metrics.open_calls ?? 0} open calls`} />
    </section>

    <nav className={styles.tabs} aria-label="Risk transfer sections">
      {(["summary", "programs", "insurance", "claims", "guarantees"] as Tab[]).map((item) => <button type="button" key={item} className={tab === item ? styles.selected : ""} onClick={() => setTab(item)}>{item === "summary" ? "Executive summary" : item === "programs" ? "Programs & counterparties" : item === "insurance" ? "Coverage & premiums" : item === "claims" ? "Losses & claims" : "Bonds & guarantees"}</button>)}
    </nav>

    {tab === "summary" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>GOVERNANCE POSTURE</p><h2>Risk-transfer policy</h2><dl className={styles.definition}><div><dt>Status</dt><dd>{policy.status}</dd></div><div><dt>Policy version</dt><dd>{policy.version}</dd></div><div><dt>Expiry alert</dt><dd>{policy.expiry_alert_days} days</dd></div><div><dt>Claim notification SLA</dt><dd>{policy.claim_notification_sla_days} days</dd></div><div><dt>Minimum coverage</dt><dd>{policy.minimum_coverage_percent}%</dd></div></dl></article>
      <article className={styles.card}><p className={styles.kicker}>PORTFOLIO SIGNALS</p><h2>Current control exposure</h2><div className={styles.statusGrid}><div><span>Verified counterparties</span><strong>{metrics.verified_counterparties ?? 0}</strong></div><div><span>Coverage gaps</span><strong>{metrics.coverage_gaps ?? 0}</strong></div><div><span>Open calls</span><strong>{metrics.open_calls ?? 0}</strong></div><div><span>Expiring instruments</span><strong>{metrics.expiring_instruments ?? 0}</strong></div></div></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>CURRENCY-SAFE EXPOSURE</p><h2>Coverage, loss, claim and guarantee values</h2><div className={styles.tableWrap}><table><thead><tr><th>Measure</th><th>Currency</th><th>Primary value</th><th>Secondary value</th><th>Recovered / premium</th></tr></thead><tbody>{Object.entries(portfolio).flatMap(([key, rows]) => key.endsWith("_by_currency") ? rows.map((row) => <tr key={`${key}-${value(row.currency_code)}`}><td>{key.replaceAll("_", " ")}</td><td>{value(row.currency_code)}</td><td>{value(row.coverage_limit) || value(row.estimated_loss) || value(row.claimed_amount) || value(row.instrument_amount) || value(row.called_amount)}</td><td>{value(row.reserved_amount) || "—"}</td><td>{value(row.recovered_amount) || value(row.annual_premium) || "—"}</td></tr>) : [])}</tbody></table></div></article>
    </section> : null}

    {tab === "programs" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>PROGRAM MASTER</p><h2>Create insurance program</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("programs", { ...programForm, project_public_id: nullable(programForm.project_public_id), contract_public_id: nullable(programForm.contract_public_id), aggregate_exposure: programForm.aggregate_exposure, currency_code: programForm.currency_code.trim(), starts_on: nullable(programForm.starts_on), ends_on: nullable(programForm.ends_on) }, "Insurance program created.").then((result) => { if (result) setProgramForm(emptyProgram); }); }}><div className={styles.formGrid}><Field label="Program code"><input name="program_code" required value={programForm.program_code} onChange={update(setProgramForm, programForm)} /></Field><Field label="Name"><input name="name" required value={programForm.name} onChange={update(setProgramForm, programForm)} /></Field><Field label="Type"><select name="program_type_code" value={programForm.program_type_code} onChange={update(setProgramForm, programForm)}><option>CONSTRUCTION_RISK</option><option>PROJECT_INSURANCE</option><option>CORPORATE_INSURANCE</option><option>CONTRACT_RISK</option></select></Field><Field label="Exposure"><input type="number" step="0.01" name="aggregate_exposure" required value={programForm.aggregate_exposure} onChange={update(setProgramForm, programForm)} /></Field><Field label="Starts"><input type="date" name="starts_on" value={programForm.starts_on} onChange={update(setProgramForm, programForm)} /></Field><Field label="Ends"><input type="date" name="ends_on" value={programForm.ends_on} onChange={update(setProgramForm, programForm)} /></Field></div><button disabled={working}>Create program</button></form></article>
      <article className={styles.card}><p className={styles.kicker}>COUNTERPARTY ASSURANCE</p><h2>Register insurer, bank or surety</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("counterparties", { counterparty_code: partyForm.counterparty_code, legal_name: partyForm.legal_name, counterparty_type_code: partyForm.counterparty_type_code, jurisdiction_code: partyForm.jurisdiction_code, financial_rating_code: partyForm.financial_rating_code, contact_data: partyForm.contact_email ? { email: partyForm.contact_email } : {} }, "Risk counterparty registered.").then((result) => { if (result) setPartyForm(emptyParty); }); }}><div className={styles.formGrid}><Field label="Code"><input name="counterparty_code" required value={partyForm.counterparty_code} onChange={update(setPartyForm, partyForm)} /></Field><Field label="Legal name"><input name="legal_name" required value={partyForm.legal_name} onChange={update(setPartyForm, partyForm)} /></Field><Field label="Type"><select name="counterparty_type_code" value={partyForm.counterparty_type_code} onChange={update(setPartyForm, partyForm)}><option>INSURER</option><option>BANK</option><option>SURETY</option><option>BROKER</option></select></Field><Field label="Rating"><input name="financial_rating_code" value={partyForm.financial_rating_code} onChange={update(setPartyForm, partyForm)} /></Field><Field label="Jurisdiction"><input name="jurisdiction_code" value={partyForm.jurisdiction_code} onChange={update(setPartyForm, partyForm)} /></Field><Field label="Email"><input type="email" name="contact_email" value={partyForm.contact_email} onChange={update(setPartyForm, partyForm)} /></Field></div><button disabled={working}>Register counterparty</button></form></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>PROGRAM & COUNTERPARTY REGISTER</p><h2>Governed risk-transfer structure</h2><div className={styles.tableWrap}><table><thead><tr><th>Program</th><th>Type</th><th>Exposure</th><th>Period</th><th>Status</th><th>Control</th></tr></thead><tbody>{programs.map((item) => { const next = nextGeneric(value(item.status_code)); return <tr key={value(item.public_id)}><td><strong>{value(item.program_code)}</strong><small>{value(item.name)}</small></td><td>{value(item.program_type_code)}</td><td>{value(item.currency_code)} {value(item.aggregate_exposure)}</td><td>{displayDate(item.starts_on)} – {displayDate(item.ends_on)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`programs/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Program moved to ${next}.` }, `Program moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Counterparty</th><th>Type</th><th>Jurisdiction</th><th>Rating</th><th>Status</th><th>Control</th></tr></thead><tbody>{counterparties.map((item) => { const next = nextParty(value(item.status_code)); return <tr key={value(item.public_id)}><td><strong>{value(item.counterparty_code)}</strong><small>{value(item.legal_name)}</small></td><td>{value(item.counterparty_type_code)}</td><td>{value(item.jurisdiction_code) || "—"}</td><td>{value(item.financial_rating_code)}</td><td><Status label={value(item.status_code)} bad={value(item.status_code) === "REJECTED"} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`counterparties/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Counterparty moved to ${next}.` }, `Counterparty moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
    </section> : null}

    {tab === "insurance" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>INSURANCE COVERAGE</p><h2>Register policy coverage</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("coverages", { ...coverageForm, coverage_limit: coverageForm.coverage_limit, deductible_amount: coverageForm.deductible_amount, annual_premium: coverageForm.annual_premium, insured_subject_type_code: "PROGRAM", insured_subject_public_id: null }, "Insurance coverage registered.").then((result) => { if (result) setCoverageForm(emptyCoverage); }); }}><div className={styles.formGrid}><Field label="Program" wide><select name="program_public_id" required value={coverageForm.program_public_id} onChange={update(setCoverageForm, coverageForm)}><option value="">Select program</option>{programs.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.program_code)}</option>)}</select></Field><Field label="Counterparty" wide><select name="counterparty_public_id" required value={coverageForm.counterparty_public_id} onChange={update(setCoverageForm, coverageForm)}><option value="">Select verified counterparty</option>{counterparties.filter((item) => value(item.status_code) === "VERIFIED").map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.counterparty_code)} · {value(item.legal_name)}</option>)}</select></Field><Field label="Policy number"><input name="policy_number" required value={coverageForm.policy_number} onChange={update(setCoverageForm, coverageForm)} /></Field><Field label="Coverage type"><select name="coverage_type_code" value={coverageForm.coverage_type_code} onChange={update(setCoverageForm, coverageForm)}><option>CONSTRUCTION_ALL_RISK</option><option>THIRD_PARTY_LIABILITY</option><option>PROFESSIONAL_INDEMNITY</option><option>EQUIPMENT_BREAKDOWN</option><option>WORKERS_COMPENSATION</option></select></Field><Field label="Coverage limit"><input type="number" step="0.01" name="coverage_limit" required value={coverageForm.coverage_limit} onChange={update(setCoverageForm, coverageForm)} /></Field><Field label="Deductible"><input type="number" step="0.01" name="deductible_amount" value={coverageForm.deductible_amount} onChange={update(setCoverageForm, coverageForm)} /></Field><Field label="Annual premium"><input type="number" step="0.01" name="annual_premium" value={coverageForm.annual_premium} onChange={update(setCoverageForm, coverageForm)} /></Field><Field label="Starts"><input type="date" name="starts_on" required value={coverageForm.starts_on} onChange={update(setCoverageForm, coverageForm)} /></Field><Field label="Ends"><input type="date" name="ends_on" required value={coverageForm.ends_on} onChange={update(setCoverageForm, coverageForm)} /></Field></div><button disabled={working}>Register coverage</button></form></article>
      <article className={styles.card}><p className={styles.kicker}>PREMIUM CONTROL</p><h2>Create premium installment</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("premiums", { ...premiumForm, amount: premiumForm.amount }, "Premium installment created.").then((result) => { if (result) setPremiumForm(emptyPremium); }); }}><div className={styles.formGrid}><Field label="Coverage" wide><select name="coverage_public_id" required value={premiumForm.coverage_public_id} onChange={update(setPremiumForm, premiumForm)}><option value="">Select coverage</option>{coverages.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.policy_number)}</option>)}</select></Field><Field label="Installment"><input name="installment_number" required value={premiumForm.installment_number} onChange={update(setPremiumForm, premiumForm)} /></Field><Field label="Due date"><input type="date" name="due_on" required value={premiumForm.due_on} onChange={update(setPremiumForm, premiumForm)} /></Field><Field label="Amount"><input type="number" step="0.01" name="amount" required value={premiumForm.amount} onChange={update(setPremiumForm, premiumForm)} /></Field></div><button disabled={working}>Create installment</button></form></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>COVERAGE & PREMIUM REGISTER</p><h2>Insurance assurance position</h2><div className={styles.tableWrap}><table><thead><tr><th>Policy</th><th>Program</th><th>Insurer</th><th>Type</th><th>Limit</th><th>Expiry</th><th>Status</th><th>Control</th></tr></thead><tbody>{coverages.map((item) => { const next = nextGeneric(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.policy_number)}</td><td>{value(item.program__program_code)}</td><td>{value(item.counterparty__legal_name)}</td><td>{value(item.coverage_type_code)}</td><td>{value(item.currency_code)} {value(item.coverage_limit)}</td><td>{displayDate(item.ends_on)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`coverages/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Coverage moved to ${next}.` }, `Coverage moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Installment</th><th>Policy</th><th>Due</th><th>Amount</th><th>Paid</th><th>Status</th><th>Control</th></tr></thead><tbody>{premiums.map((item) => <tr key={value(item.public_id)}><td>{value(item.installment_number)}</td><td>{value(item.coverage__policy_number)}</td><td>{displayDate(item.due_on)}</td><td>{value(item.currency_code)} {value(item.amount)}</td><td>{value(item.paid_amount)}</td><td><Status label={value(item.status_code)} bad={value(item.status_code) === "DUE" && new Date(value(item.due_on)) < new Date()} /></td><td>{["DUE", "PARTIALLY_PAID"].includes(value(item.status_code)) ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`premiums/${value(item.public_id)}/transition`, { status_code: "PAID", expected_version: Number(item.version), note: "Premium marked paid.", payment_reference: `PAY-${Date.now()}` }, "Premium marked paid.")}>PAID</button> : "—"}</td></tr>)}</tbody></table></div></article>
    </section> : null}

    {tab === "claims" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>LOSS NOTIFICATION</p><h2>Record loss event</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("losses", { ...lossForm, estimated_loss: lossForm.estimated_loss }, "Loss event recorded.").then((result) => { if (result) setLossForm(emptyLoss); }); }}><div className={styles.formGrid}><Field label="Program" wide><select name="program_public_id" required value={lossForm.program_public_id} onChange={update(setLossForm, lossForm)}><option value="">Select program</option>{programs.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.program_code)}</option>)}</select></Field><Field label="Loss number"><input name="loss_number" required value={lossForm.loss_number} onChange={update(setLossForm, lossForm)} /></Field><Field label="Type"><select name="loss_type_code" value={lossForm.loss_type_code} onChange={update(setLossForm, lossForm)}><option>PROPERTY_DAMAGE</option><option>THIRD_PARTY_INJURY</option><option>EQUIPMENT_DAMAGE</option><option>DESIGN_ERROR</option><option>BUSINESS_INTERRUPTION</option></select></Field><Field label="Occurrence"><input type="datetime-local" name="occurrence_on" required value={lossForm.occurrence_on} onChange={update(setLossForm, lossForm)} /></Field><Field label="Reported"><input type="datetime-local" name="reported_on" required value={lossForm.reported_on} onChange={update(setLossForm, lossForm)} /></Field><Field label="Estimated loss"><input type="number" step="0.01" name="estimated_loss" value={lossForm.estimated_loss} onChange={update(setLossForm, lossForm)} /></Field><Field label="Severity"><select name="severity_code" value={lossForm.severity_code} onChange={update(setLossForm, lossForm)}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></Field><Field label="Description" wide><textarea name="description" required value={lossForm.description} onChange={update(setLossForm, lossForm)} /></Field></div><button disabled={working}>Record loss</button></form></article>
      <article className={styles.card}><p className={styles.kicker}>CLAIM RECOVERY</p><h2>Create insurance claim</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("claims", { ...claimForm, claimed_amount: claimForm.claimed_amount, reserved_amount: claimForm.reserved_amount }, "Insurance claim created.").then((result) => { if (result) setClaimForm(emptyClaim); }); }}><div className={styles.formGrid}><Field label="Loss event" wide><select name="loss_event_public_id" required value={claimForm.loss_event_public_id} onChange={update(setClaimForm, claimForm)}><option value="">Select loss</option>{losses.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.loss_number)}</option>)}</select></Field><Field label="Coverage" wide><select name="coverage_public_id" required value={claimForm.coverage_public_id} onChange={update(setClaimForm, claimForm)}><option value="">Select coverage</option>{coverages.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.policy_number)}</option>)}</select></Field><Field label="Claim number"><input name="claim_number" required value={claimForm.claim_number} onChange={update(setClaimForm, claimForm)} /></Field><Field label="Notified"><input type="date" name="notified_on" required value={claimForm.notified_on} onChange={update(setClaimForm, claimForm)} /></Field><Field label="Claimed amount"><input type="number" step="0.01" name="claimed_amount" required value={claimForm.claimed_amount} onChange={update(setClaimForm, claimForm)} /></Field><Field label="Reserve"><input type="number" step="0.01" name="reserved_amount" value={claimForm.reserved_amount} onChange={update(setClaimForm, claimForm)} /></Field><Field label="Adjuster reference" wide><input name="adjuster_reference" value={claimForm.adjuster_reference} onChange={update(setClaimForm, claimForm)} /></Field></div><button disabled={working}>Create claim</button></form></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>LOSS & CLAIM REGISTER</p><h2>Notification, admission and recovery</h2><div className={styles.tableWrap}><table><thead><tr><th>Loss</th><th>Program</th><th>Type</th><th>Estimate</th><th>Severity</th><th>Status</th><th>Control</th></tr></thead><tbody>{losses.map((item) => { const next = nextLoss(value(item.status_code)); return <tr key={value(item.public_id)}><td><strong>{value(item.loss_number)}</strong><small>{value(item.description)}</small></td><td>{value(item.program__program_code)}</td><td>{value(item.loss_type_code)}</td><td>{value(item.currency_code)} {value(item.estimated_loss)}</td><td>{value(item.severity_code)}</td><td><Status label={value(item.status_code)} bad={value(item.severity_code) === "CRITICAL"} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`losses/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Loss moved to ${next}.` }, `Loss moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Claim</th><th>Loss</th><th>Policy</th><th>Claimed</th><th>Recovered</th><th>Status</th><th>Control</th></tr></thead><tbody>{claims.map((item) => { const next = nextClaim(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.claim_number)}</td><td>{value(item.loss_event__loss_number)}</td><td>{value(item.coverage__policy_number)}</td><td>{value(item.currency_code)} {value(item.claimed_amount)}</td><td>{value(item.recovered_amount)}</td><td><Status label={value(item.status_code)} bad={value(item.status_code) === "REJECTED"} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`claims/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Claim moved to ${next}.`, ...(next === "SETTLED" ? { recovered_amount: value(item.claimed_amount), settlement_reference: `SET-${Date.now()}` } : {}) }, `Claim moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
    </section> : null}

    {tab === "guarantees" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>BOND / GUARANTEE</p><h2>Register risk-transfer instrument</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("instruments", { ...instrumentForm, amount: instrumentForm.amount, auto_renew_flag: instrumentForm.auto_renew_flag === "true", secured_obligation_public_id: null }, "Guarantee instrument registered.").then((result) => { if (result) setInstrumentForm(emptyInstrument); }); }}><div className={styles.formGrid}><Field label="Program" wide><select name="program_public_id" required value={instrumentForm.program_public_id} onChange={update(setInstrumentForm, instrumentForm)}><option value="">Select program</option>{programs.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.program_code)}</option>)}</select></Field><Field label="Issuer" wide><select name="counterparty_public_id" required value={instrumentForm.counterparty_public_id} onChange={update(setInstrumentForm, instrumentForm)}><option value="">Select verified bank / surety</option>{counterparties.filter((item) => value(item.status_code) === "VERIFIED").map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.counterparty_code)} · {value(item.legal_name)}</option>)}</select></Field><Field label="Instrument number"><input name="instrument_number" required value={instrumentForm.instrument_number} onChange={update(setInstrumentForm, instrumentForm)} /></Field><Field label="Type"><select name="instrument_type_code" value={instrumentForm.instrument_type_code} onChange={update(setInstrumentForm, instrumentForm)}><option>PERFORMANCE_BOND</option><option>BID_BOND</option><option>ADVANCE_PAYMENT_GUARANTEE</option><option>RETENTION_GUARANTEE</option><option>BANK_GUARANTEE</option></select></Field><Field label="Beneficiary"><input name="beneficiary_name" required value={instrumentForm.beneficiary_name} onChange={update(setInstrumentForm, instrumentForm)} /></Field><Field label="Applicant"><input name="applicant_name" required value={instrumentForm.applicant_name} onChange={update(setInstrumentForm, instrumentForm)} /></Field><Field label="Amount"><input type="number" step="0.01" name="amount" required value={instrumentForm.amount} onChange={update(setInstrumentForm, instrumentForm)} /></Field><Field label="Issued"><input type="date" name="issued_on" required value={instrumentForm.issued_on} onChange={update(setInstrumentForm, instrumentForm)} /></Field><Field label="Expiry"><input type="date" name="expiry_on" required value={instrumentForm.expiry_on} onChange={update(setInstrumentForm, instrumentForm)} /></Field><Field label="Auto renew"><select name="auto_renew_flag" value={instrumentForm.auto_renew_flag} onChange={update(setInstrumentForm, instrumentForm)}><option value="false">No</option><option value="true">Yes</option></select></Field></div><button disabled={working}>Register instrument</button></form></article>
      <article className={styles.card}><p className={styles.kicker}>INSTRUMENT CALL</p><h2>Record guarantee call</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("calls", { ...callForm, amount: callForm.amount }, "Guarantee call created.").then((result) => { if (result) setCallForm(emptyCall); }); }}><div className={styles.formGrid}><Field label="Instrument" wide><select name="instrument_public_id" required value={callForm.instrument_public_id} onChange={update(setCallForm, callForm)}><option value="">Select active instrument</option>{instruments.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.instrument_number)}</option>)}</select></Field><Field label="Call number"><input name="call_number" required value={callForm.call_number} onChange={update(setCallForm, callForm)} /></Field><Field label="Called on"><input type="date" name="called_on" required value={callForm.called_on} onChange={update(setCallForm, callForm)} /></Field><Field label="Amount"><input type="number" step="0.01" name="amount" required value={callForm.amount} onChange={update(setCallForm, callForm)} /></Field><Field label="Reason" wide><textarea name="reason" required value={callForm.reason} onChange={update(setCallForm, callForm)} /></Field></div><button disabled={working}>Create call</button></form></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>INSTRUMENT & CALL REGISTER</p><h2>Expiry, call and settlement assurance</h2><div className={styles.tableWrap}><table><thead><tr><th>Instrument</th><th>Type</th><th>Issuer</th><th>Beneficiary</th><th>Amount</th><th>Expiry</th><th>Status</th><th>Control</th></tr></thead><tbody>{instruments.map((item) => { const next = nextGeneric(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.instrument_number)}</td><td>{value(item.instrument_type_code)}</td><td>{value(item.counterparty__legal_name)}</td><td>{value(item.beneficiary_name)}</td><td>{value(item.currency_code)} {value(item.amount)}</td><td>{displayDate(item.expiry_on)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`instruments/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Instrument moved to ${next}.` }, `Instrument moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Call</th><th>Instrument</th><th>Called on</th><th>Amount</th><th>Reason</th><th>Status</th><th>Control</th></tr></thead><tbody>{calls.map((item) => { const next = nextCall(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.call_number)}</td><td>{value(item.instrument__instrument_number)}</td><td>{displayDate(item.called_on)}</td><td>{value(item.currency_code)} {value(item.amount)}</td><td>{value(item.reason)}</td><td><Status label={value(item.status_code)} bad={value(item.status_code) === "DISPUTED"} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`calls/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Guarantee call moved to ${next}.`, ...(next === "SETTLED" ? { settlement_reference: `CALL-SET-${Date.now()}` } : {}) }, `Guarantee call moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
    </section> : null}
  </main>;
}
