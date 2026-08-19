"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./executive-intelligence.module.css";

type Scalar = string | number | boolean | null;
type Row = Record<string, Scalar | Record<string, unknown> | unknown[]>;
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: { status: string; version: number; review_frequency_code: string };
  metrics: Record<string, string | number>;
  objectives: Row[];
  kpis: Row[];
  observations: Row[];
  portfolio_snapshots: Row[];
  benefits: Row[];
  benefit_measurements: Row[];
  actions: Row[];
  board_reports: Row[];
};

type Tab = "summary" | "kpi" | "portfolio" | "benefits" | "governance";

const emptyObjective = { code: "", name: "", perspective_code: "OPERATIONS", weight_percent: "0", target_date: "", target_outcome: "" };
const emptyObservation = { kpi_public_id: "", period_start: "", period_end: "", actual_value: "", source_code: "MANUAL", source_reference: "" };
const emptySnapshot = { code: "", as_of_date: "", projects_total: "0", projects_healthy: "0", projects_at_risk: "0", projects_critical: "0", schedule_performance_percent: "0", cost_performance_percent: "0", portfolio_value: "0", narrative: "" };
const emptyBenefit = { objective_public_id: "", code: "", name: "", category_code: "EFFICIENCY", unit_code: "PERCENT", baseline_value: "0", target_value: "0", expected_financial_value: "0", target_date: "" };
const emptyAction = { code: "", title: "", description: "", priority_code: "P2", due_at: "" };
const emptyReport = { code: "", title: "", period_start: "", period_end: "", executive_summary: "" };

function stringValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

function formatDate(value: unknown): string {
  const raw = stringValue(value);
  if (!raw) return "—";
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? raw : parsed.toLocaleDateString();
}

function Metric({ label, value, note }: { label: string; value: string | number; note: string }) {
  return <article className={styles.metric}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

export function ExecutiveIntelligenceClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [objectiveForm, setObjectiveForm] = useState(emptyObjective);
  const [observationForm, setObservationForm] = useState(emptyObservation);
  const [snapshotForm, setSnapshotForm] = useState(emptySnapshot);
  const [benefitForm, setBenefitForm] = useState(emptyBenefit);
  const [actionForm, setActionForm] = useState(emptyAction);
  const [reportForm, setReportForm] = useState(emptyReport);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/platform/executive-intelligence/overview", { cache: "no-store" });
      const payload = (await response.json().catch(() => ({}))) as Overview & { message?: string; detail?: string };
      if (!response.ok) throw new Error(payload.message ?? payload.detail ?? "Executive intelligence could not be loaded.");
      setOverview(payload);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Executive intelligence could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void load();
    });
    return () => controller.abort();
  }, [load]);

  async function post(path: string, body: Record<string, unknown>) {
    setWorking(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/platform/executive-intelligence/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await response.json().catch(() => ({}))) as { message?: string; detail?: string };
      if (!response.ok) throw new Error(payload.message ?? payload.detail ?? "The request could not be completed.");
      setNotice("Executive control record saved successfully.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The request could not be completed.");
    } finally {
      setWorking(false);
    }
  }

  const latestSnapshot = overview?.portfolio_snapshots?.[0];
  const openActions = useMemo(() => overview?.actions.filter((item) => !["COMPLETED", "CANCELLED"].includes(stringValue(item.status_code))) ?? [], [overview]);

  if (loading && !overview) return <main className={styles.loading}>Loading executive intelligence…</main>;
  if (error && !overview) {
    return <main className={styles.loading}><section className={styles.errorCard}><span>EXECUTIVE CONTROL UNAVAILABLE</span><h1>Portfolio intelligence could not be opened.</h1><p>{error}</p><button type="button" onClick={() => void load()}>Retry workspace</button></section></main>;
  }
  if (!overview) return null;
  const metrics = overview.metrics;

  return (
    <main className={styles.page}>
      <header className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>MPSQRE BUILD360 · PHASE 37</p>
          <h1>Executive portfolio intelligence</h1>
          <p className={styles.subtitle}>Connect strategy, KPI performance, portfolio health, benefits realization, executive actions and board governance in one tenant-safe decision cockpit.</p>
          <div className={styles.chips}><span>{overview.company.name}</span><span>{overview.company.currency}</span><span>{overview.company.timezone}</span><span>Policy {overview.policy.status}</span></div>
        </div>
        <div className={styles.heroActions}><span className={styles.activeBadge}>PHASE 37 EXECUTIVE INTELLIGENCE ACTIVE</span><button type="button" disabled={working} onClick={() => void load()}>Refresh decision cockpit</button></div>
      </header>

      {error ? <div className={styles.bannerError}>{error}</div> : null}
      {notice ? <div className={styles.bannerSuccess}>{notice}</div> : null}

      <section className={styles.metrics}>
        <Metric label="KPI health" value={`${metrics.kpi_health_percent ?? 0}%`} note={`${metrics.kpis_on_target ?? 0} on target`} />
        <Metric label="Active objectives" value={metrics.active_objectives ?? 0} note={`${metrics.active_kpis ?? 0} governed KPIs`} />
        <Metric label="Portfolio exposure" value={metrics.portfolio_at_risk ?? 0} note={`${metrics.portfolio_projects ?? 0} total projects`} />
        <Metric label="Realized benefit" value={`${overview.company.currency} ${metrics.realized_benefit ?? 0}`} note={`${metrics.benefit_confidence_percent ?? 0}% confidence`} />
        <Metric label="Open actions" value={metrics.open_actions ?? 0} note={`${metrics.overdue_actions ?? 0} overdue`} />
        <Metric label="Board packs" value={metrics.pending_board_reports ?? 0} note="Draft through approved" />
      </section>

      <nav className={styles.tabs} aria-label="Executive intelligence sections">
        {[["summary", "Executive summary"], ["kpi", "Objectives & KPIs"], ["portfolio", "Portfolio"], ["benefits", "Benefits"], ["governance", "Board governance"]].map(([key, label]) => (
          <button key={key} type="button" className={tab === key ? styles.tabActive : ""} onClick={() => setTab(key as Tab)}>{label}</button>
        ))}
      </nav>

      {tab === "summary" ? (
        <section className={styles.grid}>
          <article className={styles.card}><p className={styles.kicker}>PORTFOLIO SIGNAL</p><h2>Latest portfolio position</h2>{latestSnapshot ? <dl className={styles.definition}><div><dt>Snapshot</dt><dd>{stringValue(latestSnapshot.code)}</dd></div><div><dt>As of</dt><dd>{formatDate(latestSnapshot.as_of_date)}</dd></div><div><dt>Schedule</dt><dd>{stringValue(latestSnapshot.schedule_performance_percent)}%</dd></div><div><dt>Cost</dt><dd>{stringValue(latestSnapshot.cost_performance_percent)}%</dd></div><div><dt>Critical</dt><dd>{stringValue(latestSnapshot.projects_critical)}</dd></div></dl> : <p className={styles.empty}>No portfolio snapshot registered.</p>}</article>
          <article className={styles.card}><p className={styles.kicker}>EXECUTIVE FOLLOW-UP</p><h2>Priority actions</h2><div className={styles.list}>{openActions.slice(0, 6).map((item) => <div key={stringValue(item.public_id)}><strong>{stringValue(item.code)} · {stringValue(item.title)}</strong><small>{stringValue(item.priority_code)} · {stringValue(item.status_code)} · due {formatDate(item.due_at)}</small></div>)}{!openActions.length ? <p className={styles.empty}>No open executive actions.</p> : null}</div></article>
          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>ENTERPRISE SCORECARD</p><h2>Current KPI status</h2><div className={styles.tableWrap}><table><thead><tr><th>KPI</th><th>Objective</th><th>Actual</th><th>Target</th><th>Period</th><th>Status</th></tr></thead><tbody>{overview.kpis.map((item) => <tr key={stringValue(item.public_id)}><td><strong>{stringValue(item.code)}</strong><small>{stringValue(item.name)}</small></td><td>{stringValue(item.objective__code) || "—"}</td><td>{stringValue(item.latest_actual) || "—"} {stringValue(item.unit_code)}</td><td>{stringValue(item.target_value) || stringValue(item.target_low) || "—"}</td><td>{formatDate(item.latest_period_end)}</td><td><span className={styles.pill}>{stringValue(item.status)}</span></td></tr>)}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "kpi" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("objectives", { ...objectiveForm, weight_percent: Number(objectiveForm.weight_percent), target_date: objectiveForm.target_date || null }); setObjectiveForm(emptyObjective); }}><p className={styles.kicker}>STRATEGY</p><h2>Create strategic objective</h2><div className={styles.formGrid}><label>Code<input required value={objectiveForm.code} onChange={(event) => setObjectiveForm({ ...objectiveForm, code: event.target.value })} /></label><label>Perspective<input value={objectiveForm.perspective_code} onChange={(event) => setObjectiveForm({ ...objectiveForm, perspective_code: event.target.value })} /></label><label className={styles.full}>Objective name<input required value={objectiveForm.name} onChange={(event) => setObjectiveForm({ ...objectiveForm, name: event.target.value })} /></label><label>Weight %<input type="number" min="0" max="100" value={objectiveForm.weight_percent} onChange={(event) => setObjectiveForm({ ...objectiveForm, weight_percent: event.target.value })} /></label><label>Target date<input type="date" value={objectiveForm.target_date} onChange={(event) => setObjectiveForm({ ...objectiveForm, target_date: event.target.value })} /></label><label className={styles.full}>Target outcome<textarea value={objectiveForm.target_outcome} onChange={(event) => setObjectiveForm({ ...objectiveForm, target_outcome: event.target.value })} /></label></div><button className={styles.primary} disabled={working}>Create objective</button></form>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("observations", { ...observationForm, actual_value: Number(observationForm.actual_value) }); setObservationForm(emptyObservation); }}><p className={styles.kicker}>KPI OBSERVATION</p><h2>Record scorecard value</h2><label>KPI<select required value={observationForm.kpi_public_id} onChange={(event: ChangeEvent<HTMLSelectElement>) => setObservationForm({ ...observationForm, kpi_public_id: event.target.value })}><option value="">Select KPI</option>{overview.kpis.filter((item) => Boolean(item.active)).map((item) => <option key={stringValue(item.public_id)} value={stringValue(item.public_id)}>{stringValue(item.code)} · {stringValue(item.name)}</option>)}</select></label><div className={styles.formGrid}><label>Period start<input required type="date" value={observationForm.period_start} onChange={(event) => setObservationForm({ ...observationForm, period_start: event.target.value })} /></label><label>Period end<input required type="date" value={observationForm.period_end} onChange={(event) => setObservationForm({ ...observationForm, period_end: event.target.value })} /></label><label>Actual value<input required type="number" step="0.0001" value={observationForm.actual_value} onChange={(event) => setObservationForm({ ...observationForm, actual_value: event.target.value })} /></label><label>Source<input value={observationForm.source_code} onChange={(event) => setObservationForm({ ...observationForm, source_code: event.target.value })} /></label></div><button className={styles.primary} disabled={working}>Record observation</button></form>
          <article className={`${styles.card} ${styles.wide}`}><div className={styles.cardHeading}><div><p className={styles.kicker}>STRATEGIC REGISTER</p><h2>Objectives and accountability</h2></div><span>{overview.objectives.length} objectives</span></div><div className={styles.tableWrap}><table><thead><tr><th>Objective</th><th>Perspective</th><th>Status</th><th>Weight</th><th>Target date</th><th>Outcome</th></tr></thead><tbody>{overview.objectives.map((item) => <tr key={stringValue(item.public_id)}><td><strong>{stringValue(item.code)}</strong><small>{stringValue(item.name)}</small></td><td>{stringValue(item.perspective_code)}</td><td>{stringValue(item.status_code)}</td><td>{stringValue(item.weight_percent)}%</td><td>{formatDate(item.target_date)}</td><td>{stringValue(item.target_outcome) || "—"}</td></tr>)}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "portfolio" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("portfolio-snapshots", Object.fromEntries(Object.entries(snapshotForm).map(([key, value]) => [key, ["code", "as_of_date", "narrative"].includes(key) ? value : Number(value)]))); setSnapshotForm(emptySnapshot); }}><p className={styles.kicker}>PORTFOLIO CONTROL</p><h2>Create portfolio snapshot</h2><div className={styles.formGrid}>{(["code", "as_of_date", "projects_total", "projects_healthy", "projects_at_risk", "projects_critical", "schedule_performance_percent", "cost_performance_percent", "portfolio_value"] as const).map((key) => <label key={key}>{key.replaceAll("_", " ")}<input required={key === "code" || key === "as_of_date"} type={key === "as_of_date" ? "date" : key === "code" ? "text" : "number"} step="0.01" value={snapshotForm[key]} onChange={(event) => setSnapshotForm({ ...snapshotForm, [key]: event.target.value })} /></label>)}<label className={styles.full}>Narrative<textarea value={snapshotForm.narrative} onChange={(event) => setSnapshotForm({ ...snapshotForm, narrative: event.target.value })} /></label></div><button className={styles.primary} disabled={working}>Create snapshot</button></form>
          <article className={styles.card}><p className={styles.kicker}>GOVERNED SNAPSHOTS</p><h2>Approval queue</h2><div className={styles.list}>{overview.portfolio_snapshots.map((item) => <div key={stringValue(item.public_id)}><strong>{stringValue(item.code)} · {stringValue(item.status_code)}</strong><small>{formatDate(item.as_of_date)} · {stringValue(item.projects_at_risk)} at risk · {stringValue(item.projects_critical)} critical</small><select defaultValue="" onChange={(event) => { const value = event.target.value; event.currentTarget.value = ""; if (value) void post(`portfolio-snapshots/${stringValue(item.public_id)}/transition`, { status_code: value, expected_version: Number(item.version) }); }}><option value="">Transition</option><option value="IN_REVIEW">Submit review</option><option value="APPROVED">Approve</option><option value="PUBLISHED">Publish</option><option value="DRAFT">Return draft</option><option value="CANCELLED">Cancel</option></select></div>)}</div></article>
        </section>
      ) : null}

      {tab === "benefits" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("benefits", { ...benefitForm, objective_public_id: benefitForm.objective_public_id || null, baseline_value: Number(benefitForm.baseline_value), target_value: Number(benefitForm.target_value), expected_financial_value: Number(benefitForm.expected_financial_value), target_date: benefitForm.target_date || null }); setBenefitForm(emptyBenefit); }}><p className={styles.kicker}>VALUE REALIZATION</p><h2>Create benefit plan</h2><div className={styles.formGrid}><label>Code<input required value={benefitForm.code} onChange={(event) => setBenefitForm({ ...benefitForm, code: event.target.value })} /></label><label>Category<input value={benefitForm.category_code} onChange={(event) => setBenefitForm({ ...benefitForm, category_code: event.target.value })} /></label><label className={styles.full}>Benefit name<input required value={benefitForm.name} onChange={(event) => setBenefitForm({ ...benefitForm, name: event.target.value })} /></label><label>Objective<select value={benefitForm.objective_public_id} onChange={(event) => setBenefitForm({ ...benefitForm, objective_public_id: event.target.value })}><option value="">No linked objective</option>{overview.objectives.map((item) => <option key={stringValue(item.public_id)} value={stringValue(item.public_id)}>{stringValue(item.code)} · {stringValue(item.name)}</option>)}</select></label><label>Unit<input value={benefitForm.unit_code} onChange={(event) => setBenefitForm({ ...benefitForm, unit_code: event.target.value })} /></label><label>Baseline<input type="number" step="0.0001" value={benefitForm.baseline_value} onChange={(event) => setBenefitForm({ ...benefitForm, baseline_value: event.target.value })} /></label><label>Target<input type="number" step="0.0001" value={benefitForm.target_value} onChange={(event) => setBenefitForm({ ...benefitForm, target_value: event.target.value })} /></label><label>Expected financial value<input type="number" step="0.01" value={benefitForm.expected_financial_value} onChange={(event) => setBenefitForm({ ...benefitForm, expected_financial_value: event.target.value })} /></label><label>Target date<input type="date" value={benefitForm.target_date} onChange={(event) => setBenefitForm({ ...benefitForm, target_date: event.target.value })} /></label></div><button className={styles.primary} disabled={working}>Create benefit</button></form>
          <article className={styles.card}><p className={styles.kicker}>BENEFIT REGISTER</p><h2>Expected versus realized</h2><div className={styles.list}>{overview.benefits.map((item) => <div key={stringValue(item.public_id)}><strong>{stringValue(item.code)} · {stringValue(item.name)}</strong><small>{stringValue(item.status_code)} · target {stringValue(item.target_value)} {stringValue(item.unit_code)} · {stringValue(item.currency)} {stringValue(item.expected_financial_value)}</small></div>)}{!overview.benefits.length ? <p className={styles.empty}>No benefit plans registered.</p> : null}</div></article>
        </section>
      ) : null}

      {tab === "governance" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("actions", { ...actionForm, due_at: actionForm.due_at || null }); setActionForm(emptyAction); }}><p className={styles.kicker}>EXECUTIVE ACTION</p><h2>Create decision follow-up</h2><div className={styles.formGrid}><label>Code<input required value={actionForm.code} onChange={(event) => setActionForm({ ...actionForm, code: event.target.value })} /></label><label>Priority<select value={actionForm.priority_code} onChange={(event) => setActionForm({ ...actionForm, priority_code: event.target.value })}><option>P0</option><option>P1</option><option>P2</option><option>P3</option><option>P4</option></select></label><label className={styles.full}>Title<input required value={actionForm.title} onChange={(event) => setActionForm({ ...actionForm, title: event.target.value })} /></label><label className={styles.full}>Description<textarea value={actionForm.description} onChange={(event) => setActionForm({ ...actionForm, description: event.target.value })} /></label><label>Due at<input type="datetime-local" value={actionForm.due_at} onChange={(event) => setActionForm({ ...actionForm, due_at: event.target.value })} /></label></div><button className={styles.primary} disabled={working}>Create action</button></form>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void post("board-reports", reportForm); setReportForm(emptyReport); }}><p className={styles.kicker}>BOARD PACK</p><h2>Prepare governance report</h2><div className={styles.formGrid}><label>Code<input required value={reportForm.code} onChange={(event) => setReportForm({ ...reportForm, code: event.target.value })} /></label><label>Title<input required value={reportForm.title} onChange={(event) => setReportForm({ ...reportForm, title: event.target.value })} /></label><label>Period start<input required type="date" value={reportForm.period_start} onChange={(event) => setReportForm({ ...reportForm, period_start: event.target.value })} /></label><label>Period end<input required type="date" value={reportForm.period_end} onChange={(event) => setReportForm({ ...reportForm, period_end: event.target.value })} /></label><label className={styles.full}>Executive summary<textarea value={reportForm.executive_summary} onChange={(event) => setReportForm({ ...reportForm, executive_summary: event.target.value })} /></label></div><button className={styles.primary} disabled={working}>Create board report</button></form>
          <article className={`${styles.card} ${styles.wide}`}><div className={styles.cardHeading}><div><p className={styles.kicker}>GOVERNANCE REGISTER</p><h2>Board reports and decisions</h2></div><span>{overview.board_reports.length} reports</span></div><div className={styles.tableWrap}><table><thead><tr><th>Report</th><th>Period</th><th>Status</th><th>Summary</th><th>Decision</th></tr></thead><tbody>{overview.board_reports.map((item) => <tr key={stringValue(item.public_id)}><td><strong>{stringValue(item.code)}</strong><small>{stringValue(item.title)}</small></td><td>{formatDate(item.period_start)} – {formatDate(item.period_end)}</td><td>{stringValue(item.status_code)}</td><td>{stringValue(item.executive_summary) || "—"}</td><td><select defaultValue="" onChange={(event) => { const value = event.target.value; event.currentTarget.value = ""; if (value) void post(`board-reports/${stringValue(item.public_id)}/transition`, { status_code: value, expected_version: Number(item.version) }); }}><option value="">Transition</option><option value="IN_REVIEW">Submit review</option><option value="APPROVED">Approve</option><option value="PUBLISHED">Publish</option><option value="ARCHIVED">Archive</option><option value="DRAFT">Return draft</option></select></td></tr>)}</tbody></table></div></article>
        </section>
      ) : null}
    </main>
  );
}
