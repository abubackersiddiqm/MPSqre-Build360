"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useState } from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";

import styles from "./capital-investment-operations.module.css";

type Row = Record<string, unknown>;
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: { status: string; version: number; covenant_alert_days: number; commitment_expiry_alert_days: number; maximum_leverage_percent: string };
  metrics: Record<string, string | number>;
  programs: Row[];
  investors: Row[];
  joint_ventures: Row[];
  commitments: Row[];
  facilities: Row[];
  drawdowns: Row[];
  covenants: Row[];
  distributions: Row[];
  events: Row[];
  portfolio: { program_status: Row[]; investor_kyc: Row[]; capital_by_currency: Row[]; commitments_by_currency: Row[]; debt_by_currency: Row[]; drawdowns_by_currency: Row[]; distributions_by_currency: Row[] };
};

type Tab = "summary" | "programs" | "investors" | "funding" | "controls" | "distributions";
type InputEvent = ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>;
type FormState = Record<string, string>;

const emptyProgram = { program_code: "", name: "", program_type_code: "PROJECT_FINANCE", project_public_id: "", land_opportunity_public_id: "", currency_code: "", target_capital: "", target_equity: "0", target_debt: "0", committee_public_id: "", start_on: "", target_close_on: "" } satisfies FormState;
const emptyInvestor = { investor_code: "", legal_name: "", investor_type_code: "INSTITUTIONAL", jurisdiction_code: "", risk_rating_code: "MEDIUM", accredited_flag: "false", contact_email: "" } satisfies FormState;
const emptyJointVenture = { program_public_id: "", venture_code: "", partner_name: "", partner_reference: "", ownership_percent: "", profit_share_percent: "", governance_note: "" } satisfies FormState;
const emptyCommitment = { program_public_id: "", investor_public_id: "", joint_venture_public_id: "", commitment_number: "", commitment_type_code: "EQUITY", committed_amount: "", currency_code: "", committed_on: "", expiry_on: "" } satisfies FormState;
const emptyFacility = { program_public_id: "", facility_code: "", lender_name: "", facility_type_code: "TERM_LOAN", principal_limit: "", currency_code: "", interest_rate_percent: "0", tenor_months: "12", start_on: "", maturity_on: "", security_summary: "", covenant_note: "" } satisfies FormState;
const emptyDrawdown = { program_public_id: "", debt_facility_public_id: "", commitment_public_id: "", request_number: "", request_type_code: "DEBT_DRAWDOWN", amount: "", currency_code: "", requested_on: "", required_by: "", purpose: "" } satisfies FormState;
const emptyCovenant = { debt_facility_public_id: "", test_number: "", covenant_code: "LTV", tested_on: "", metric_value: "", threshold_operator: "LTE", threshold_value: "", evidence_note: "" } satisfies FormState;
const emptyDistribution = { program_public_id: "", investor_public_id: "", joint_venture_public_id: "", distribution_number: "", distribution_type_code: "RETURN_OF_CAPITAL", amount: "", currency_code: "", declared_on: "", payable_on: "" } satisfies FormState;
const emptyEvent = { program_public_id: "", event_type_code: "INVESTOR_UPDATE", summary: "", evidence_note: "" } satisfies FormState;

function value(input: unknown): string {
  return input === null || input === undefined ? "" : String(input);
}

function nullable(input: string): string | null {
  return input.trim() ? input.trim() : null;
}

function decimal(input: string): string {
  return input.trim() || "0";
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

function nextProgram(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "ACTIVE";
  if (status === "ACTIVE" || status === "SUSPENDED") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextInvestor(status: string): string {
  if (status === "PENDING") return "VERIFIED";
  if (status === "REJECTED") return "PENDING";
  if (status === "VERIFIED") return "SUSPENDED";
  if (status === "SUSPENDED") return "VERIFIED";
  return "";
}

function nextGeneric(status: string, activeClose = true): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "ACTIVE";
  if (status === "ACTIVE" && activeClose) return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextCommitment(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "ACTIVE";
  if (status === "FULLY_FUNDED") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextDrawdown(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "DISBURSED";
  if (status === "DISBURSED") return "SETTLED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextCovenant(status: string, compliant: boolean): string {
  if (status === "OPEN") return "REVIEWED";
  if (status === "REVIEWED") return compliant ? "CLOSED" : "WAIVED";
  if (status === "WAIVED") return "CLOSED";
  return "";
}

function nextDistribution(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "PAID";
  if (status === "PAID") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

export function CapitalInvestmentOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [programForm, setProgramForm] = useState(emptyProgram);
  const [investorForm, setInvestorForm] = useState(emptyInvestor);
  const [jointVentureForm, setJointVentureForm] = useState(emptyJointVenture);
  const [commitmentForm, setCommitmentForm] = useState(emptyCommitment);
  const [facilityForm, setFacilityForm] = useState(emptyFacility);
  const [drawdownForm, setDrawdownForm] = useState(emptyDrawdown);
  const [covenantForm, setCovenantForm] = useState(emptyCovenant);
  const [distributionForm, setDistributionForm] = useState(emptyDistribution);
  const [eventForm, setEventForm] = useState(emptyEvent);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/platform/capital-investment-operations/overview", { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(payload, "Capital and investor operations could not be loaded."));
      setOverview(payload as Overview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capital and investor operations could not be loaded.");
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
      const response = await fetch(`/api/platform/capital-investment-operations/${path}`, {
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
    return <main className={styles.shell}><section className={styles.loading}>Preparing the capital and investor command centre…</section></main>;
  }
  if (!overview) {
    return <main className={styles.shell}><section className={styles.errorCard}><p className={styles.kicker}>CAPITAL CONTROL UNAVAILABLE</p><h2>Capital planning, joint ventures and funding could not be opened.</h2><p>{error || "The request could not be completed."}</p><button type="button" onClick={() => void refresh()}>Retry workspace</button></section></main>;
  }

  const { metrics, programs, investors, joint_ventures: jointVentures, commitments, facilities, drawdowns, covenants, distributions, events } = overview;

  return <main className={styles.shell}>
    <section className={styles.hero}>
      <div>
        <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 44</p>
        <h1>Capital, joint venture & investor operations</h1>
        <p className={styles.lead}>Govern capital programs, verified investors, joint ventures, commitments, debt facilities, drawdowns, covenants and distributions from one tenant-safe funding command centre.</p>
        <div className={styles.tags}><span>{overview.company.name}</span><span>{overview.company.currency}</span><span>{overview.company.timezone}</span><span>Policy {overview.policy.status}</span></div>
      </div>
      <div className={styles.heroActions}><span className={styles.activeLabel}>PHASE 44 CAPITAL & INVESTOR OPERATIONS ACTIVE</span><button type="button" onClick={() => void refresh()} disabled={loading}>Refresh capital cockpit</button></div>
    </section>

    {error ? <p className={styles.alert}>{error}</p> : null}
    {notice ? <p className={styles.notice}>{notice}</p> : null}

    <section className={styles.metrics}>
      <Metric label="Active programs" metric={metrics.active_programs ?? 0} note="Approved through active" />
      <Metric label="Verified investors" metric={metrics.verified_investors ?? 0} note="KYC-controlled counterparties" />
      <Metric label="Active joint ventures" metric={metrics.active_joint_ventures ?? 0} note="Approved partner structures" />
      <Metric label="Pending drawdowns" metric={metrics.pending_drawdowns ?? 0} note="Draft through approved" />
      <Metric label="Covenant breaches" metric={metrics.covenant_breaches ?? 0} note="Open non-compliance" />
      <Metric label="Pending distributions" metric={metrics.pending_distributions ?? 0} note="Awaiting approval or payment" />
    </section>

    <nav className={styles.tabs} aria-label="Capital operations sections">
      {(["summary", "programs", "investors", "funding", "controls", "distributions"] as Tab[]).map((item) => <button type="button" key={item} className={tab === item ? styles.selected : ""} onClick={() => setTab(item)}>{item === "summary" ? "Executive summary" : item === "programs" ? "Programs & JVs" : item === "investors" ? "Investors & commitments" : item === "funding" ? "Facilities & drawdowns" : item === "controls" ? "Covenants" : "Returns & events"}</button>)}
    </nav>

    {tab === "summary" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>GOVERNANCE POSTURE</p><h2>Capital policy</h2><dl className={styles.definition}><div><dt>Status</dt><dd>{overview.policy.status}</dd></div><div><dt>Maximum leverage</dt><dd>{overview.policy.maximum_leverage_percent}%</dd></div><div><dt>Covenant alert</dt><dd>{overview.policy.covenant_alert_days} days</dd></div><div><dt>Commitment expiry alert</dt><dd>{overview.policy.commitment_expiry_alert_days} days</dd></div></dl></article>
      <article className={styles.card}><p className={styles.kicker}>PROGRAM PORTFOLIO</p><h2>Status distribution</h2><div className={styles.statusGrid}>{overview.portfolio.program_status.map((item) => <div key={value(item.status_code)}><span>{value(item.status_code)}</span><strong>{value(item.count)}</strong></div>)}</div></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>CAPITAL POSITION</p><h2>Currency-safe funding summary</h2><div className={styles.tableWrap}><table><thead><tr><th>Currency</th><th>Target capital</th><th>Equity target</th><th>Debt target</th></tr></thead><tbody>{overview.portfolio.capital_by_currency.map((item) => <tr key={value(item.currency_code)}><td><strong>{value(item.currency_code)}</strong></td><td>{value(item.target_capital)}</td><td>{value(item.target_equity)}</td><td>{value(item.target_debt)}</td></tr>)}</tbody></table></div></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>RECENT CAPITAL EVENTS</p><h2>Investor and funding timeline</h2><div className={styles.tableWrap}><table><thead><tr><th>Program</th><th>Event</th><th>Date</th><th>Summary</th></tr></thead><tbody>{events.map((item) => <tr key={value(item.public_id)}><td>{value(item.program__program_code)}</td><td><Status label={value(item.event_type_code)} /></td><td>{displayDate(item.event_on)}</td><td>{value(item.summary)}</td></tr>)}</tbody></table></div></article>
    </section> : null}

    {tab === "programs" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>CAPITAL PROGRAM</p><h2>Create funding plan</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("programs", { ...programForm, project_public_id: nullable(programForm.project_public_id), land_opportunity_public_id: nullable(programForm.land_opportunity_public_id), committee_public_id: nullable(programForm.committee_public_id), currency_code: programForm.currency_code.trim(), target_capital: decimal(programForm.target_capital), target_equity: decimal(programForm.target_equity), target_debt: decimal(programForm.target_debt), start_on: nullable(programForm.start_on), target_close_on: nullable(programForm.target_close_on) }, "Funding program created.").then((result) => { if (result) setProgramForm(emptyProgram); }); }}><div className={styles.formGrid}><Field label="Program code"><input name="program_code" required value={programForm.program_code} onChange={update(setProgramForm, programForm)} /></Field><Field label="Program name"><input name="name" required value={programForm.name} onChange={update(setProgramForm, programForm)} /></Field><Field label="Program type"><select name="program_type_code" value={programForm.program_type_code} onChange={update(setProgramForm, programForm)}><option>PROJECT_FINANCE</option><option>CORPORATE_FUNDING</option><option>JOINT_VENTURE</option><option>LAND_FINANCE</option></select></Field><Field label="Currency"><input name="currency_code" maxLength={3} placeholder={overview.company.currency} value={programForm.currency_code} onChange={update(setProgramForm, programForm)} /></Field><Field label="Total capital"><input type="number" step="0.01" name="target_capital" required value={programForm.target_capital} onChange={update(setProgramForm, programForm)} /></Field><Field label="Equity target"><input type="number" step="0.01" name="target_equity" value={programForm.target_equity} onChange={update(setProgramForm, programForm)} /></Field><Field label="Debt target"><input type="number" step="0.01" name="target_debt" value={programForm.target_debt} onChange={update(setProgramForm, programForm)} /></Field><Field label="Target close"><input type="date" name="target_close_on" value={programForm.target_close_on} onChange={update(setProgramForm, programForm)} /></Field></div><button disabled={working}>Create program</button></form></article>
      <article className={styles.card}><p className={styles.kicker}>JOINT VENTURE</p><h2>Register partner structure</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("joint-ventures", { ...jointVentureForm, partner_reference: nullable(jointVentureForm.partner_reference), ownership_percent: decimal(jointVentureForm.ownership_percent), profit_share_percent: decimal(jointVentureForm.profit_share_percent), governance: jointVentureForm.governance_note.trim() ? { note: jointVentureForm.governance_note.trim() } : {} }, "Joint venture registered.").then((result) => { if (result) setJointVentureForm(emptyJointVenture); }); }}><div className={styles.formGrid}><Field label="Program" wide><select name="program_public_id" required value={jointVentureForm.program_public_id} onChange={update(setJointVentureForm, jointVentureForm)}><option value="">Select program</option>{programs.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.program_code)} · {value(item.name)}</option>)}</select></Field><Field label="Venture code"><input name="venture_code" required value={jointVentureForm.venture_code} onChange={update(setJointVentureForm, jointVentureForm)} /></Field><Field label="Partner name"><input name="partner_name" required value={jointVentureForm.partner_name} onChange={update(setJointVentureForm, jointVentureForm)} /></Field><Field label="Ownership %"><input type="number" step="0.0001" name="ownership_percent" required value={jointVentureForm.ownership_percent} onChange={update(setJointVentureForm, jointVentureForm)} /></Field><Field label="Profit share %"><input type="number" step="0.0001" name="profit_share_percent" required value={jointVentureForm.profit_share_percent} onChange={update(setJointVentureForm, jointVentureForm)} /></Field><Field label="Governance note" wide><textarea name="governance_note" value={jointVentureForm.governance_note} onChange={update(setJointVentureForm, jointVentureForm)} /></Field></div><button disabled={working}>Register joint venture</button></form></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>PROGRAM REGISTER</p><h2>Funding pipeline</h2><div className={styles.tableWrap}><table><thead><tr><th>Program</th><th>Type</th><th>Capital</th><th>Equity</th><th>Debt</th><th>Close</th><th>Status</th><th>Control</th></tr></thead><tbody>{programs.map((item) => { const next = nextProgram(value(item.status_code)); return <tr key={value(item.public_id)}><td><strong>{value(item.program_code)}</strong><small>{value(item.name)}</small></td><td>{value(item.program_type_code)}</td><td>{value(item.currency_code)} {value(item.target_capital)}</td><td>{value(item.target_equity)}</td><td>{value(item.target_debt)}</td><td>{displayDate(item.target_close_on)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} disabled={working} type="button" onClick={() => void post(`programs/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Program moved to ${next}.` }, `Program moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Program</th><th>Venture</th><th>Partner</th><th>Ownership</th><th>Profit share</th><th>Status</th><th>Control</th></tr></thead><tbody>{jointVentures.map((item) => { const next = nextGeneric(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.program__program_code)}</td><td>{value(item.venture_code)}</td><td>{value(item.partner_name)}</td><td>{value(item.ownership_percent)}%</td><td>{value(item.profit_share_percent)}%</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} disabled={working} type="button" onClick={() => void post(`joint-ventures/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Joint venture moved to ${next}.` }, `Joint venture moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
    </section> : null}

    {tab === "investors" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>INVESTOR MASTER</p><h2>Register investor</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("investors", { investor_code: investorForm.investor_code, legal_name: investorForm.legal_name, investor_type_code: investorForm.investor_type_code, jurisdiction_code: investorForm.jurisdiction_code, contact_data: investorForm.contact_email.trim() ? { email: investorForm.contact_email.trim() } : {}, risk_rating_code: investorForm.risk_rating_code, accredited_flag: investorForm.accredited_flag === "true" }, "Investor registered.").then((result) => { if (result) setInvestorForm(emptyInvestor); }); }}><div className={styles.formGrid}><Field label="Investor code"><input name="investor_code" required value={investorForm.investor_code} onChange={update(setInvestorForm, investorForm)} /></Field><Field label="Legal name"><input name="legal_name" required value={investorForm.legal_name} onChange={update(setInvestorForm, investorForm)} /></Field><Field label="Investor type"><select name="investor_type_code" value={investorForm.investor_type_code} onChange={update(setInvestorForm, investorForm)}><option>INSTITUTIONAL</option><option>FUND</option><option>FAMILY_OFFICE</option><option>INDIVIDUAL</option><option>LENDER</option></select></Field><Field label="Jurisdiction"><input name="jurisdiction_code" value={investorForm.jurisdiction_code} onChange={update(setInvestorForm, investorForm)} /></Field><Field label="Risk rating"><select name="risk_rating_code" value={investorForm.risk_rating_code} onChange={update(setInvestorForm, investorForm)}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></Field><Field label="Accredited"><select name="accredited_flag" value={investorForm.accredited_flag} onChange={update(setInvestorForm, investorForm)}><option value="false">No</option><option value="true">Yes</option></select></Field><Field label="Contact email" wide><input type="email" name="contact_email" value={investorForm.contact_email} onChange={update(setInvestorForm, investorForm)} /></Field></div><button disabled={working}>Register investor</button></form></article>
      <article className={styles.card}><p className={styles.kicker}>CAPITAL COMMITMENT</p><h2>Record commitment</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("commitments", { ...commitmentForm, investor_public_id: nullable(commitmentForm.investor_public_id), joint_venture_public_id: nullable(commitmentForm.joint_venture_public_id), committed_amount: decimal(commitmentForm.committed_amount), currency_code: commitmentForm.currency_code.trim(), expiry_on: nullable(commitmentForm.expiry_on) }, "Capital commitment recorded.").then((result) => { if (result) setCommitmentForm(emptyCommitment); }); }}><div className={styles.formGrid}><Field label="Program" wide><select name="program_public_id" required value={commitmentForm.program_public_id} onChange={update(setCommitmentForm, commitmentForm)}><option value="">Select program</option>{programs.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.program_code)}</option>)}</select></Field><Field label="Investor"><select name="investor_public_id" value={commitmentForm.investor_public_id} onChange={update(setCommitmentForm, commitmentForm)}><option value="">None</option>{investors.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.investor_code)} · {value(item.legal_name)}</option>)}</select></Field><Field label="Joint venture"><select name="joint_venture_public_id" value={commitmentForm.joint_venture_public_id} onChange={update(setCommitmentForm, commitmentForm)}><option value="">None</option>{jointVentures.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.venture_code)} · {value(item.partner_name)}</option>)}</select></Field><Field label="Commitment number"><input name="commitment_number" required value={commitmentForm.commitment_number} onChange={update(setCommitmentForm, commitmentForm)} /></Field><Field label="Type"><select name="commitment_type_code" value={commitmentForm.commitment_type_code} onChange={update(setCommitmentForm, commitmentForm)}><option>EQUITY</option><option>MEZZANINE</option><option>DEBT</option><option>SPONSOR</option></select></Field><Field label="Amount"><input type="number" step="0.01" name="committed_amount" required value={commitmentForm.committed_amount} onChange={update(setCommitmentForm, commitmentForm)} /></Field><Field label="Committed on"><input type="date" name="committed_on" required value={commitmentForm.committed_on} onChange={update(setCommitmentForm, commitmentForm)} /></Field><Field label="Expiry"><input type="date" name="expiry_on" value={commitmentForm.expiry_on} onChange={update(setCommitmentForm, commitmentForm)} /></Field></div><button disabled={working}>Record commitment</button></form></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>INVESTOR & COMMITMENT REGISTER</p><h2>Counterparty assurance and funding capacity</h2><div className={styles.tableWrap}><table><thead><tr><th>Investor</th><th>Type</th><th>Jurisdiction</th><th>Risk</th><th>KYC</th><th>Control</th></tr></thead><tbody>{investors.map((item) => { const next = nextInvestor(value(item.kyc_status_code)); return <tr key={value(item.public_id)}><td><strong>{value(item.investor_code)}</strong><small>{value(item.legal_name)}</small></td><td>{value(item.investor_type_code)}</td><td>{value(item.jurisdiction_code)}</td><td>{value(item.risk_rating_code)}</td><td><Status label={value(item.kyc_status_code)} bad={value(item.kyc_status_code) === "REJECTED"} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`investors/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Investor moved to ${next}.` }, `Investor moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Commitment</th><th>Program</th><th>Counterparty</th><th>Committed</th><th>Funded</th><th>Expiry</th><th>Status</th><th>Control</th></tr></thead><tbody>{commitments.map((item) => { const next = nextCommitment(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.commitment_number)}</td><td>{value(item.program__program_code)}</td><td>{value(item.investor__legal_name) || value(item.joint_venture__partner_name)}</td><td>{value(item.currency_code)} {value(item.committed_amount)}</td><td>{value(item.funded_amount)}</td><td>{displayDate(item.expiry_on)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`commitments/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Commitment moved to ${next}.` }, `Commitment moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
    </section> : null}

    {tab === "funding" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>DEBT FACILITY</p><h2>Register financing line</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("facilities", { ...facilityForm, principal_limit: decimal(facilityForm.principal_limit), interest_rate_percent: decimal(facilityForm.interest_rate_percent), tenor_months: Number(facilityForm.tenor_months), currency_code: facilityForm.currency_code.trim(), start_on: nullable(facilityForm.start_on), maturity_on: nullable(facilityForm.maturity_on), covenants: facilityForm.covenant_note.trim() ? { note: facilityForm.covenant_note.trim() } : {} }, "Debt facility registered.").then((result) => { if (result) setFacilityForm(emptyFacility); }); }}><div className={styles.formGrid}><Field label="Program" wide><select name="program_public_id" required value={facilityForm.program_public_id} onChange={update(setFacilityForm, facilityForm)}><option value="">Select program</option>{programs.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.program_code)}</option>)}</select></Field><Field label="Facility code"><input name="facility_code" required value={facilityForm.facility_code} onChange={update(setFacilityForm, facilityForm)} /></Field><Field label="Lender"><input name="lender_name" required value={facilityForm.lender_name} onChange={update(setFacilityForm, facilityForm)} /></Field><Field label="Type"><select name="facility_type_code" value={facilityForm.facility_type_code} onChange={update(setFacilityForm, facilityForm)}><option>TERM_LOAN</option><option>CONSTRUCTION_FINANCE</option><option>REVOLVING_CREDIT</option><option>BRIDGE_LOAN</option></select></Field><Field label="Principal limit"><input type="number" step="0.01" name="principal_limit" required value={facilityForm.principal_limit} onChange={update(setFacilityForm, facilityForm)} /></Field><Field label="Interest rate %"><input type="number" step="0.000001" name="interest_rate_percent" value={facilityForm.interest_rate_percent} onChange={update(setFacilityForm, facilityForm)} /></Field><Field label="Tenor months"><input type="number" name="tenor_months" min="1" value={facilityForm.tenor_months} onChange={update(setFacilityForm, facilityForm)} /></Field><Field label="Maturity"><input type="date" name="maturity_on" value={facilityForm.maturity_on} onChange={update(setFacilityForm, facilityForm)} /></Field><Field label="Security summary" wide><textarea name="security_summary" value={facilityForm.security_summary} onChange={update(setFacilityForm, facilityForm)} /></Field></div><button disabled={working}>Register facility</button></form></article>
      <article className={styles.card}><p className={styles.kicker}>CAPITAL CALL / DRAWDOWN</p><h2>Request funding</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("drawdowns", { ...drawdownForm, debt_facility_public_id: nullable(drawdownForm.debt_facility_public_id), commitment_public_id: nullable(drawdownForm.commitment_public_id), amount: decimal(drawdownForm.amount), currency_code: drawdownForm.currency_code.trim(), required_by: nullable(drawdownForm.required_by) }, "Funding request created.").then((result) => { if (result) setDrawdownForm(emptyDrawdown); }); }}><div className={styles.formGrid}><Field label="Program" wide><select name="program_public_id" required value={drawdownForm.program_public_id} onChange={update(setDrawdownForm, drawdownForm)}><option value="">Select program</option>{programs.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.program_code)}</option>)}</select></Field><Field label="Debt facility"><select name="debt_facility_public_id" value={drawdownForm.debt_facility_public_id} onChange={update(setDrawdownForm, drawdownForm)}><option value="">None</option>{facilities.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.facility_code)} · {value(item.lender_name)}</option>)}</select></Field><Field label="Commitment"><select name="commitment_public_id" value={drawdownForm.commitment_public_id} onChange={update(setDrawdownForm, drawdownForm)}><option value="">None</option>{commitments.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.commitment_number)}</option>)}</select></Field><Field label="Request number"><input name="request_number" required value={drawdownForm.request_number} onChange={update(setDrawdownForm, drawdownForm)} /></Field><Field label="Amount"><input type="number" step="0.01" name="amount" required value={drawdownForm.amount} onChange={update(setDrawdownForm, drawdownForm)} /></Field><Field label="Requested on"><input type="date" name="requested_on" required value={drawdownForm.requested_on} onChange={update(setDrawdownForm, drawdownForm)} /></Field><Field label="Required by"><input type="date" name="required_by" value={drawdownForm.required_by} onChange={update(setDrawdownForm, drawdownForm)} /></Field><Field label="Purpose" wide><textarea name="purpose" value={drawdownForm.purpose} onChange={update(setDrawdownForm, drawdownForm)} /></Field></div><button disabled={working}>Request funding</button></form></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>FUNDING REGISTER</p><h2>Facilities and drawdowns</h2><div className={styles.tableWrap}><table><thead><tr><th>Facility</th><th>Program</th><th>Lender</th><th>Limit</th><th>Rate</th><th>Maturity</th><th>Status</th><th>Control</th></tr></thead><tbody>{facilities.map((item) => { const next = nextGeneric(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.facility_code)}</td><td>{value(item.program__program_code)}</td><td>{value(item.lender_name)}</td><td>{value(item.currency_code)} {value(item.principal_limit)}</td><td>{value(item.interest_rate_percent)}%</td><td>{displayDate(item.maturity_on)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`facilities/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Facility moved to ${next}.` }, `Facility moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Request</th><th>Program</th><th>Source</th><th>Amount</th><th>Required</th><th>Status</th><th>Reference</th><th>Control</th></tr></thead><tbody>{drawdowns.map((item) => { const next = nextDrawdown(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.request_number)}</td><td>{value(item.program__program_code)}</td><td>{value(item.debt_facility__facility_code) || value(item.commitment__commitment_number)}</td><td>{value(item.currency_code)} {value(item.amount)}</td><td>{displayDate(item.required_by)}</td><td><Status label={value(item.status_code)} /></td><td>{value(item.disbursement_reference) || "—"}</td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`drawdowns/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Drawdown moved to ${next}.`, ...(next === "DISBURSED" ? { disbursement_reference: `MANUAL-${Date.now()}` } : {}) }, `Drawdown moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
    </section> : null}

    {tab === "controls" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>COVENANT TEST</p><h2>Record compliance result</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("covenants", { debt_facility_public_id: covenantForm.debt_facility_public_id, test_number: covenantForm.test_number, covenant_code: covenantForm.covenant_code, tested_on: covenantForm.tested_on, metric_value: decimal(covenantForm.metric_value), threshold_operator: covenantForm.threshold_operator, threshold_value: decimal(covenantForm.threshold_value), evidence: covenantForm.evidence_note.trim() ? { note: covenantForm.evidence_note.trim() } : {} }, "Covenant test recorded.").then((result) => { if (result) setCovenantForm(emptyCovenant); }); }}><div className={styles.formGrid}><Field label="Debt facility" wide><select name="debt_facility_public_id" required value={covenantForm.debt_facility_public_id} onChange={update(setCovenantForm, covenantForm)}><option value="">Select facility</option>{facilities.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.facility_code)} · {value(item.lender_name)}</option>)}</select></Field><Field label="Test number"><input name="test_number" required value={covenantForm.test_number} onChange={update(setCovenantForm, covenantForm)} /></Field><Field label="Covenant code"><input name="covenant_code" required value={covenantForm.covenant_code} onChange={update(setCovenantForm, covenantForm)} /></Field><Field label="Tested on"><input type="date" name="tested_on" required value={covenantForm.tested_on} onChange={update(setCovenantForm, covenantForm)} /></Field><Field label="Metric value"><input type="number" step="0.000001" name="metric_value" required value={covenantForm.metric_value} onChange={update(setCovenantForm, covenantForm)} /></Field><Field label="Operator"><select name="threshold_operator" value={covenantForm.threshold_operator} onChange={update(setCovenantForm, covenantForm)}><option>LT</option><option>LTE</option><option>GT</option><option>GTE</option><option>EQ</option></select></Field><Field label="Threshold"><input type="number" step="0.000001" name="threshold_value" required value={covenantForm.threshold_value} onChange={update(setCovenantForm, covenantForm)} /></Field><Field label="Evidence note" wide><textarea name="evidence_note" value={covenantForm.evidence_note} onChange={update(setCovenantForm, covenantForm)} /></Field></div><button disabled={working}>Record covenant test</button></form></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>COVENANT REGISTER</p><h2>Lender compliance posture</h2><div className={styles.tableWrap}><table><thead><tr><th>Test</th><th>Facility</th><th>Covenant</th><th>Metric</th><th>Threshold</th><th>Result</th><th>Status</th><th>Control</th></tr></thead><tbody>{covenants.map((item) => { const compliant = Boolean(item.compliant); const next = nextCovenant(value(item.status_code), compliant); return <tr key={value(item.public_id)}><td>{value(item.test_number)}</td><td>{value(item.debt_facility__facility_code)}</td><td>{value(item.covenant_code)}</td><td>{value(item.metric_value)}</td><td>{value(item.threshold_operator)} {value(item.threshold_value)}</td><td><Status label={compliant ? "COMPLIANT" : "BREACH"} bad={!compliant} /></td><td>{value(item.status_code)}</td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`covenants/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: next === "WAIVED" ? "Independent temporary waiver recorded." : `Covenant moved to ${next}.` }, `Covenant moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
    </section> : null}

    {tab === "distributions" ? <section className={styles.grid}>
      <article className={styles.card}><p className={styles.kicker}>INVESTOR RETURN</p><h2>Create distribution</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("distributions", { ...distributionForm, investor_public_id: nullable(distributionForm.investor_public_id), joint_venture_public_id: nullable(distributionForm.joint_venture_public_id), amount: decimal(distributionForm.amount), currency_code: distributionForm.currency_code.trim(), payable_on: nullable(distributionForm.payable_on) }, "Distribution created.").then((result) => { if (result) setDistributionForm(emptyDistribution); }); }}><div className={styles.formGrid}><Field label="Program" wide><select name="program_public_id" required value={distributionForm.program_public_id} onChange={update(setDistributionForm, distributionForm)}><option value="">Select program</option>{programs.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.program_code)}</option>)}</select></Field><Field label="Investor"><select name="investor_public_id" value={distributionForm.investor_public_id} onChange={update(setDistributionForm, distributionForm)}><option value="">None</option>{investors.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.investor_code)} · {value(item.legal_name)}</option>)}</select></Field><Field label="Joint venture"><select name="joint_venture_public_id" value={distributionForm.joint_venture_public_id} onChange={update(setDistributionForm, distributionForm)}><option value="">None</option>{jointVentures.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.venture_code)} · {value(item.partner_name)}</option>)}</select></Field><Field label="Distribution number"><input name="distribution_number" required value={distributionForm.distribution_number} onChange={update(setDistributionForm, distributionForm)} /></Field><Field label="Type"><select name="distribution_type_code" value={distributionForm.distribution_type_code} onChange={update(setDistributionForm, distributionForm)}><option>RETURN_OF_CAPITAL</option><option>DIVIDEND</option><option>PROFIT_SHARE</option><option>INTEREST</option></select></Field><Field label="Amount"><input type="number" step="0.01" name="amount" required value={distributionForm.amount} onChange={update(setDistributionForm, distributionForm)} /></Field><Field label="Declared on"><input type="date" name="declared_on" required value={distributionForm.declared_on} onChange={update(setDistributionForm, distributionForm)} /></Field><Field label="Payable on"><input type="date" name="payable_on" value={distributionForm.payable_on} onChange={update(setDistributionForm, distributionForm)} /></Field></div><button disabled={working}>Create distribution</button></form></article>
      <article className={styles.card}><p className={styles.kicker}>CAPITAL EVENT</p><h2>Record investor communication</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("events", { program_public_id: eventForm.program_public_id, event_type_code: eventForm.event_type_code, summary: eventForm.summary, evidence: eventForm.evidence_note.trim() ? { note: eventForm.evidence_note.trim() } : {} }, "Capital event recorded.").then((result) => { if (result) setEventForm(emptyEvent); }); }}><div className={styles.formGrid}><Field label="Program" wide><select name="program_public_id" required value={eventForm.program_public_id} onChange={update(setEventForm, eventForm)}><option value="">Select program</option>{programs.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.program_code)}</option>)}</select></Field><Field label="Event type"><select name="event_type_code" value={eventForm.event_type_code} onChange={update(setEventForm, eventForm)}><option>INVESTOR_UPDATE</option><option>COMMITMENT_SIGNED</option><option>DRAWDOWN_NOTICE</option><option>COVENANT_NOTICE</option><option>DISTRIBUTION_NOTICE</option><option>COMMITTEE_DECISION</option></select></Field><Field label="Summary" wide><textarea name="summary" required value={eventForm.summary} onChange={update(setEventForm, eventForm)} /></Field><Field label="Evidence note" wide><textarea name="evidence_note" value={eventForm.evidence_note} onChange={update(setEventForm, eventForm)} /></Field></div><button disabled={working}>Record event</button></form></article>
      <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>DISTRIBUTION REGISTER</p><h2>Investor returns and payment evidence</h2><div className={styles.tableWrap}><table><thead><tr><th>Distribution</th><th>Program</th><th>Beneficiary</th><th>Type</th><th>Amount</th><th>Payable</th><th>Status</th><th>Reference</th><th>Control</th></tr></thead><tbody>{distributions.map((item) => { const next = nextDistribution(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.distribution_number)}</td><td>{value(item.program__program_code)}</td><td>{value(item.investor__legal_name) || value(item.joint_venture__partner_name)}</td><td>{value(item.distribution_type_code)}</td><td>{value(item.currency_code)} {value(item.amount)}</td><td>{displayDate(item.payable_on)}</td><td><Status label={value(item.status_code)} /></td><td>{value(item.payment_reference) || "—"}</td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`distributions/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: `Distribution moved to ${next}.`, ...(next === "PAID" ? { payment_reference: `PAY-${Date.now()}` } : {}) }, `Distribution moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
    </section> : null}
  </main>;
}
