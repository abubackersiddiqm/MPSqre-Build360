"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./go-live-operations.module.css";

type MigrationBatch = {
  public_id: string;
  code: string;
  entity_code: string;
  source_file_name: string;
  status_code: string;
  dry_run: boolean;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  warning_rows: number;
  version: number;
};
type MigrationIssue = {
  public_id: string;
  batch__code: string;
  row_number: number;
  field_name: string;
  severity_code: string;
  issue_code: string;
  message: string;
  resolved: boolean;
  resolution_notes: string;
  version: number;
};
type TrainingCohort = {
  public_id: string;
  code: string;
  title: string;
  audience_code: string;
  delivery_mode_code: string;
  required: boolean;
  starts_at: string;
  ends_at: string;
  minimum_score_percent: string;
  status_code: string;
  facilitator_name: string;
  version: number;
};
type TrainingEnrollment = {
  public_id: string;
  cohort__code: string;
  participant_public_id: string;
  participant_name: string;
  participant_email: string;
  status_code: string;
  score_percent: string | null;
  completed_at: string | null;
  version: number;
};
type CutoverPlan = {
  public_id: string;
  code: string;
  name: string;
  environment_code: string;
  status_code: string;
  planned_start_at: string;
  planned_go_live_at: string;
  actual_go_live_at: string | null;
  rollback_deadline_at: string | null;
  version: number;
};
type CutoverTask = {
  public_id: string;
  plan__code: string;
  code: string;
  title: string;
  category_code: string;
  sequence: number;
  critical: boolean;
  status_code: string;
  due_at: string | null;
  completed_at: string | null;
  notes: string;
  version: number;
};
type GoLiveWave = {
  public_id: string;
  plan__code: string | null;
  code: string;
  name: string;
  scope: Record<string, unknown>;
  status_code: string;
  planned_at: string;
  activated_at: string | null;
  closed_at: string | null;
  version: number;
};
type HypercareIssue = {
  public_id: string;
  wave__code: string | null;
  code: string;
  title: string;
  severity_code: string;
  status_code: string;
  area_code: string;
  impact_summary: string;
  resolution_summary: string;
  reported_at: string;
  resolved_at: string | null;
  version: number;
};
type Gate = {
  public_id: string;
  code: string;
  name: string;
  category_code: string;
  description: string;
  is_required: boolean;
  status_code: string;
  evidence: Record<string, unknown>;
  notes: string;
  decided_at: string | null;
  version: number;
};
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: {
    status: string;
    version: number;
    migration_error_tolerance_percent: string;
    minimum_training_completion_percent: string;
    cutover_freeze_hours: number;
    hypercare_days: number;
  };
  metrics: Record<string, number>;
  migration_batches: MigrationBatch[];
  migration_issues: MigrationIssue[];
  training_cohorts: TrainingCohort[];
  training_enrollments: TrainingEnrollment[];
  cutover_plans: CutoverPlan[];
  cutover_tasks: CutoverTask[];
  go_live_waves: GoLiveWave[];
  hypercare_issues: HypercareIssue[];
  gates: Gate[];
  capabilities: Record<string, boolean>;
};
type Tab = "migration" | "training" | "cutover" | "waves" | "hypercare" | "gates";

async function readJson(response: Response): Promise<Record<string, unknown>> {
  const raw = await response.text();
  let payload: Record<string, unknown> = {};
  if (raw) {
    try {
      payload = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      payload = {};
    }
  }
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : "";
    const message = typeof payload.message === "string" ? payload.message : detail;
    throw new Error(message || `Request failed (${response.status}). Review the Django backend log.`);
  }
  return payload;
}

let pendingOverview: Promise<Overview> | null = null;
async function loadOverview(): Promise<Overview> {
  if (pendingOverview) return pendingOverview;
  pendingOverview = fetch("/api/platform/go-live-operations/overview", { cache: "no-store" })
    .then(async (response) => await readJson(response) as unknown as Overview)
    .finally(() => { pendingOverview = null; });
  return pendingOverview;
}

async function post(path: string, data: unknown): Promise<Record<string, unknown>> {
  return readJson(await fetch(`/api/platform/go-live-operations/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }));
}

function statusClass(status: string): string {
  if (["PASSED", "VALIDATED", "APPROVED", "IMPORTED", "COMPLETED", "DONE", "LIVE", "HYPERCARE", "CLOSED", "RESOLVED"].includes(status)) return styles.good ?? "";
  if (["FAILED", "BLOCKED", "BLOCKER", "P0", "P1", "ROLLED_BACK", "CANCELLED"].includes(status)) return styles.bad ?? "";
  return styles.warn ?? "";
}

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function localDateTime(offsetHours = 0): string {
  const date = new Date(Date.now() + offsetHours * 60 * 60 * 1000);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

export function GoLiveOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("migration");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setOverview(await loadOverview());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Go-live operations could not be loaded.");
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

  async function execute(action: () => Promise<Record<string, unknown>>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(success);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The request could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  async function createMigrationBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = Object.fromEntries(data.entries()) as Record<string, unknown>;
    payload.dry_run = data.get("dry_run") === "on";
    for (const field of ["total_rows", "valid_rows", "invalid_rows", "warning_rows"]) payload[field] = Number(payload[field] ?? 0);
    await execute(() => post("migration-batches", payload), "Migration batch registered.");
    form.reset();
  }

  async function transitionMigration(batch: MigrationBatch, status: string) {
    await execute(() => post(`migration-batches/${batch.public_id}/transition`, {
      status_code: status,
      expected_version: batch.version,
      total_rows: batch.total_rows,
      valid_rows: batch.valid_rows,
      invalid_rows: batch.invalid_rows,
      warning_rows: batch.warning_rows,
      notes: `Transitioned from Phase 35 control room at ${new Date().toISOString()}`,
    }), `Migration batch moved to ${status.toLowerCase()}.`);
  }

  async function resolveIssue(issue: MigrationIssue) {
    const resolution = window.prompt("Resolution notes", issue.resolution_notes) ?? "";
    if (!resolution.trim()) return;
    await execute(() => post(`migration-issues/${issue.public_id}/resolve`, {
      expected_version: issue.version,
      resolution_notes: resolution,
    }), "Migration issue resolved.");
  }

  async function createTraining(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = Object.fromEntries(data.entries()) as Record<string, unknown>;
    payload.required = data.get("required") === "on";
    await execute(() => post("training-cohorts", payload), "Training cohort created.");
    form.reset();
  }

  async function completeEnrollment(enrollment: TrainingEnrollment) {
    const rawScore = window.prompt("Completion score (0-100)", enrollment.score_percent ?? "100");
    if (rawScore === null) return;
    const score = Number(rawScore);
    if (!Number.isFinite(score)) return;
    await execute(() => post(`training-enrollments/${enrollment.public_id}/transition`, {
      status_code: "COMPLETED",
      expected_version: enrollment.version,
      score_percent: score,
      evidence: { source: "phase35-ui", completed_at: new Date().toISOString() },
    }), "Training completion recorded.");
  }

  async function createCutoverPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries());
    await execute(() => post("cutover-plans", payload), "Cutover plan created.");
    form.reset();
  }

  async function createWave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload: Record<string, unknown> = Object.fromEntries(data.entries());
    payload.plan_public_id = payload.plan_public_id || null;
    payload.scope = { company: overview?.company.code ?? "", source: "phase35-ui" };
    await execute(() => post("waves", payload), "Go-live wave created.");
    form.reset();
  }

  async function transitionWave(wave: GoLiveWave, status: string) {
    await execute(() => post(`waves/${wave.public_id}/transition`, {
      status_code: status,
      expected_version: wave.version,
    }), `Go-live wave moved to ${status.toLowerCase()}.`);
  }

  async function createHypercare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload: Record<string, unknown> = Object.fromEntries(data.entries());
    payload.wave_public_id = payload.wave_public_id || null;
    await execute(() => post("hypercare-issues", payload), "Hypercare issue created.");
    form.reset();
  }

  async function transitionHypercare(issue: HypercareIssue, status: string) {
    const resolution = ["RESOLVED", "CLOSED"].includes(status)
      ? window.prompt("Resolution summary", issue.resolution_summary) ?? ""
      : "";
    await execute(() => post(`hypercare-issues/${issue.public_id}/transition`, {
      status_code: status,
      expected_version: issue.version,
      resolution_summary: resolution,
    }), `Hypercare issue moved to ${status.toLowerCase()}.`);
  }

  async function decideGate(gate: Gate, status: "PASSED" | "FAILED" | "WAIVED") {
    const notes = window.prompt(`${status} notes for ${gate.name}`, gate.notes) ?? "";
    await execute(() => post(`gates/${gate.public_id}/decision`, {
      status_code: status,
      expected_version: gate.version,
      notes,
      evidence: { source: "phase35-go-live-control-room", recorded_at: new Date().toISOString() },
    }), `Gate ${status.toLowerCase()}.`);
  }

  const filteredIssues = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return overview?.migration_issues ?? [];
    return (overview?.migration_issues ?? []).filter((item) =>
      [item.batch__code, item.field_name, item.issue_code, item.message, item.severity_code].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [overview, query]);

  const filteredHypercare = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return overview?.hypercare_issues ?? [];
    return (overview?.hypercare_issues ?? []).filter((item) =>
      [item.code, item.title, item.area_code, item.severity_code, item.status_code].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [overview, query]);

  if (loading && !overview) return <div className={styles.loading}>Opening the Build360 go-live and enablement control room...</div>;
  if (!overview) {
    return <div className={styles.fatal}><div className={styles.eyebrow}>Go-live control unavailable</div><h2>Data migration, cutover and enablement could not be opened.</h2><p>{error}</p><button className={styles.primary} onClick={() => void refresh()}>Retry workspace</button></div>;
  }

  const metrics = overview.metrics;
  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <div className={styles.eyebrow}>MPSQRE BUILD360 · PHASE 35</div>
          <h1>Go-live & enablement operations</h1>
          <p>Govern master-data migration, user readiness, cutover execution, production waves and hypercare from one tenant-safe command centre.</p>
          <div className={styles.chips}><span>{overview.company.name}</span><span>{overview.company.currency}</span><span>{overview.company.timezone}</span></div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.activeBadge}>PHASE 35 GO-LIVE & ENABLEMENT ACTIVE</span>
          <button className={styles.primary} disabled={busy} onClick={() => void refresh()}>{busy ? "Working..." : "Refresh control room"}</button>
        </div>
      </header>

      {error ? <div className={styles.error}>{error}</div> : null}
      {notice ? <div className={styles.notice}>{notice}</div> : null}

      <section className={styles.metrics} aria-label="Go-live readiness metrics">
        <article><span>Migration pass</span><strong>{metrics.migration_pass_percent ?? 0}%</strong><small>{metrics.migration_invalid_rows ?? 0} invalid rows</small></article>
        <article><span>Training completion</span><strong>{metrics.training_completion_percent ?? 0}%</strong><small>{metrics.training_completed ?? 0} completed</small></article>
        <article><span>Cutover blockers</span><strong>{metrics.blocked_critical_tasks ?? 0}</strong><small>{metrics.open_cutover_tasks ?? 0} open tasks</small></article>
        <article><span>Go-live readiness</span><strong>{metrics.go_live_readiness_percent ?? 0}%</strong><small>{metrics.go_live_gates_passed ?? 0}/{metrics.go_live_gates_total ?? 0} gates passed</small></article>
        <article><span>Hypercare</span><strong>{metrics.open_hypercare_issues ?? 0}</strong><small>{metrics.critical_hypercare_issues ?? 0} P0/P1 signals</small></article>
      </section>

      <nav className={styles.tabs} aria-label="Go-live operations views">
        {([
          ["migration", "Data migration"],
          ["training", "Training"],
          ["cutover", "Cutover"],
          ["waves", "Go-live waves"],
          ["hypercare", "Hypercare"],
          ["gates", "Readiness gates"],
        ] as const).map(([key, label]) => <button key={key} className={tab === key ? styles.tabActive : ""} onClick={() => setTab(key)}>{label}</button>)}
      </nav>

      {tab === "migration" ? (
        <section className={styles.gridTwo}>
          <form className={styles.panel} onSubmit={createMigrationBatch}>
            <div className={styles.sectionLabel}>DATA CONTROL</div><h2>Register migration batch</h2>
            <div className={styles.formGrid}>
              <label>Batch code<input name="code" required placeholder="EMPLOYEE_2026_01" /></label>
              <label>Entity<input name="entity_code" required placeholder="EMPLOYEE" /></label>
              <label className={styles.full}>Source file<input name="source_file_name" required placeholder="employees.csv" /></label>
              <label className={styles.full}>SHA-256<input name="source_checksum" pattern="[0-9a-fA-F]{64}" placeholder="Optional 64-character checksum" /></label>
              <label>Total rows<input name="total_rows" type="number" min="0" defaultValue="0" /></label>
              <label>Valid rows<input name="valid_rows" type="number" min="0" defaultValue="0" /></label>
              <label>Invalid rows<input name="invalid_rows" type="number" min="0" defaultValue="0" /></label>
              <label>Warning rows<input name="warning_rows" type="number" min="0" defaultValue="0" /></label>
              <label className={styles.checkbox}><input name="dry_run" type="checkbox" defaultChecked /> Dry run</label>
            </div>
            <button className={styles.primary} disabled={busy}>Register batch</button>
          </form>
          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><div className={styles.sectionLabel}>MIGRATION REGISTER</div><h2>Governed batches</h2></div><span>{overview.migration_batches.length} recent</span></div>
            <div className={styles.tableWrap}><table><thead><tr><th>Batch</th><th>Rows</th><th>Status</th><th>Control</th></tr></thead><tbody>
              {overview.migration_batches.map((batch) => <tr key={batch.public_id}><td><strong>{batch.code}</strong><small>{batch.entity_code} · {batch.source_file_name}</small></td><td>{batch.valid_rows}/{batch.total_rows}<small>{batch.invalid_rows} invalid · {batch.warning_rows} warnings</small></td><td><span className={statusClass(batch.status_code)}>{batch.status_code}</span></td><td><div className={styles.actions}>
                {batch.status_code === "DRAFT" ? <button onClick={() => void transitionMigration(batch, "VALIDATING")}>Validate</button> : null}
                {batch.status_code === "VALIDATING" ? <button onClick={() => void transitionMigration(batch, batch.invalid_rows ? "FAILED" : "VALIDATED")}>Finish</button> : null}
                {batch.status_code === "VALIDATED" ? <button onClick={() => void transitionMigration(batch, "APPROVED")}>Approve</button> : null}
                {batch.status_code === "APPROVED" ? <button onClick={() => void transitionMigration(batch, "IMPORTED")}>Mark imported</button> : null}
              </div></td></tr>)}
              {!overview.migration_batches.length ? <tr><td colSpan={4}>No migration batches have been registered.</td></tr> : null}
            </tbody></table></div>
          </section>
          <section className={`${styles.panel} ${styles.fullSpan}`}>
            <div className={styles.panelHeader}><div><div className={styles.sectionLabel}>DATA QUALITY</div><h2>Migration issues</h2></div><input className={styles.search} value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Search issues" /></div>
            <div className={styles.tableWrap}><table><thead><tr><th>Batch / row</th><th>Issue</th><th>Severity</th><th>Status</th></tr></thead><tbody>
              {filteredIssues.map((issue) => <tr key={issue.public_id}><td><strong>{issue.batch__code}</strong><small>Row {issue.row_number} · {issue.field_name || "record"}</small></td><td><strong>{issue.issue_code}</strong><small>{issue.message}</small></td><td><span className={statusClass(issue.severity_code)}>{issue.severity_code}</span></td><td>{issue.resolved ? <span className={styles.good}>RESOLVED</span> : <button onClick={() => void resolveIssue(issue)}>Resolve</button>}</td></tr>)}
              {!filteredIssues.length ? <tr><td colSpan={4}>No migration issues are visible.</td></tr> : null}
            </tbody></table></div>
          </section>
        </section>
      ) : null}

      {tab === "training" ? (
        <section className={styles.gridTwo}>
          <form className={styles.panel} onSubmit={createTraining}>
            <div className={styles.sectionLabel}>USER ENABLEMENT</div><h2>Create training cohort</h2>
            <div className={styles.formGrid}>
              <label>Cohort code<input name="code" required placeholder="SITE_ENGINEERS_01" /></label>
              <label>Audience<input name="audience_code" required defaultValue="ALL_USERS" /></label>
              <label className={styles.full}>Title<input name="title" required placeholder="Build360 operating fundamentals" /></label>
              <label>Delivery<select name="delivery_mode_code" defaultValue="ONLINE"><option>ONLINE</option><option>CLASSROOM</option><option>BLENDED</option><option>SITE</option></select></label>
              <label>Minimum score<input name="minimum_score_percent" type="number" min="0" max="100" step="0.01" defaultValue="80" /></label>
              <label>Starts<input name="starts_at" type="datetime-local" required defaultValue={localDateTime(24)} /></label>
              <label>Ends<input name="ends_at" type="datetime-local" required defaultValue={localDateTime(26)} /></label>
              <label className={styles.full}>Facilitator<input name="facilitator_name" /></label>
              <label className={styles.checkbox}><input name="required" type="checkbox" defaultChecked /> Required</label>
            </div>
            <button className={styles.primary} disabled={busy}>Create cohort</button>
          </form>
          <section className={styles.panel}><div className={styles.sectionLabel}>TRAINING PORTFOLIO</div><h2>Cohorts</h2><div className={styles.tableWrap}><table><thead><tr><th>Cohort</th><th>Schedule</th><th>Status</th></tr></thead><tbody>
            {overview.training_cohorts.map((cohort) => <tr key={cohort.public_id}><td><strong>{cohort.code}</strong><small>{cohort.title} · {cohort.audience_code}</small></td><td>{formatDate(cohort.starts_at)}<small>{cohort.delivery_mode_code}</small></td><td><span className={statusClass(cohort.status_code)}>{cohort.status_code}</span></td></tr>)}
            {!overview.training_cohorts.length ? <tr><td colSpan={3}>No training cohort exists.</td></tr> : null}
          </tbody></table></div></section>
          <section className={`${styles.panel} ${styles.fullSpan}`}><div className={styles.sectionLabel}>COMPLETION EVIDENCE</div><h2>Enrollments</h2><div className={styles.tableWrap}><table><thead><tr><th>Participant</th><th>Cohort</th><th>Status</th><th>Action</th></tr></thead><tbody>
            {overview.training_enrollments.map((enrollment) => <tr key={enrollment.public_id}><td><strong>{enrollment.participant_name}</strong><small>{enrollment.participant_email}</small></td><td>{enrollment.cohort__code}</td><td><span className={statusClass(enrollment.status_code)}>{enrollment.status_code}</span><small>{enrollment.score_percent ? `${enrollment.score_percent}%` : "No score"}</small></td><td>{enrollment.status_code !== "COMPLETED" ? <button onClick={() => void completeEnrollment(enrollment)}>Complete</button> : "Recorded"}</td></tr>)}
            {!overview.training_enrollments.length ? <tr><td colSpan={4}>Enroll users through the API or governed import workflow.</td></tr> : null}
          </tbody></table></div></section>
        </section>
      ) : null}

      {tab === "cutover" ? (
        <section className={styles.gridTwo}>
          <form className={styles.panel} onSubmit={createCutoverPlan}>
            <div className={styles.sectionLabel}>CUTOVER GOVERNANCE</div><h2>Create cutover plan</h2>
            <div className={styles.formGrid}>
              <label>Plan code<input name="code" required placeholder="BUILD360_V1" /></label>
              <label>Environment<input name="environment_code" required defaultValue="PRODUCTION" /></label>
              <label className={styles.full}>Plan name<input name="name" required placeholder="Build360 v1 production cutover" /></label>
              <label>Planned start<input name="planned_start_at" type="datetime-local" required defaultValue={localDateTime(48)} /></label>
              <label>Go-live<input name="planned_go_live_at" type="datetime-local" required defaultValue={localDateTime(72)} /></label>
              <label className={styles.full}>Rollback deadline<input name="rollback_deadline_at" type="datetime-local" defaultValue={localDateTime(96)} /></label>
            </div>
            <button className={styles.primary} disabled={busy}>Create plan</button>
          </form>
          <section className={styles.panel}><div className={styles.sectionLabel}>CUTOVER PORTFOLIO</div><h2>Plans</h2><div className={styles.tableWrap}><table><thead><tr><th>Plan</th><th>Go-live</th><th>Status</th></tr></thead><tbody>
            {overview.cutover_plans.map((plan) => <tr key={plan.public_id}><td><strong>{plan.code}</strong><small>{plan.name} · {plan.environment_code}</small></td><td>{formatDate(plan.planned_go_live_at)}</td><td><span className={statusClass(plan.status_code)}>{plan.status_code}</span></td></tr>)}
            {!overview.cutover_plans.length ? <tr><td colSpan={3}>No cutover plan exists.</td></tr> : null}
          </tbody></table></div></section>
          <section className={`${styles.panel} ${styles.fullSpan}`}><div className={styles.sectionLabel}>EXECUTION RUNBOOK</div><h2>Cutover tasks</h2><div className={styles.tableWrap}><table><thead><tr><th>Plan / task</th><th>Category</th><th>Due</th><th>Status</th></tr></thead><tbody>
            {overview.cutover_tasks.map((task) => <tr key={task.public_id}><td><strong>{task.plan__code} · {task.code}</strong><small>{task.title}{task.critical ? " · Critical" : ""}</small></td><td>{task.category_code}</td><td>{formatDate(task.due_at)}</td><td><span className={statusClass(task.status_code)}>{task.status_code}</span></td></tr>)}
            {!overview.cutover_tasks.length ? <tr><td colSpan={4}>Add cutover tasks through the API or seeded runbook.</td></tr> : null}
          </tbody></table></div></section>
        </section>
      ) : null}

      {tab === "waves" ? (
        <section className={styles.gridTwo}>
          <form className={styles.panel} onSubmit={createWave}>
            <div className={styles.sectionLabel}>PRODUCTION ACTIVATION</div><h2>Create go-live wave</h2>
            <div className={styles.formGrid}>
              <label>Wave code<input name="code" required placeholder="WAVE_01" /></label>
              <label>Cutover plan<select name="plan_public_id" defaultValue=""><option value="">No linked plan</option>{overview.cutover_plans.map((plan) => <option key={plan.public_id} value={plan.public_id}>{plan.code}</option>)}</select></label>
              <label className={styles.full}>Wave name<input name="name" required placeholder="Production pilot wave" /></label>
              <label className={styles.full}>Planned activation<input name="planned_at" type="datetime-local" required defaultValue={localDateTime(72)} /></label>
            </div>
            <button className={styles.primary} disabled={busy}>Create wave</button>
          </form>
          <section className={styles.panel}><div className={styles.sectionLabel}>WAVE CONTROL</div><h2>Production waves</h2><div className={styles.tableWrap}><table><thead><tr><th>Wave</th><th>Status</th><th>Control</th></tr></thead><tbody>
            {overview.go_live_waves.map((wave) => <tr key={wave.public_id}><td><strong>{wave.code}</strong><small>{wave.name} · {wave.plan__code || "No plan"}<br />{formatDate(wave.planned_at)}</small></td><td><span className={statusClass(wave.status_code)}>{wave.status_code}</span></td><td><div className={styles.actions}>
              {wave.status_code === "DRAFT" ? <button onClick={() => void transitionWave(wave, "READY")}>Ready</button> : null}
              {wave.status_code === "READY" ? <button onClick={() => void transitionWave(wave, "APPROVED")}>Approve</button> : null}
              {wave.status_code === "APPROVED" ? <button onClick={() => void transitionWave(wave, "LIVE")}>Go live</button> : null}
              {wave.status_code === "LIVE" ? <button onClick={() => void transitionWave(wave, "HYPERCARE")}>Hypercare</button> : null}
              {wave.status_code === "HYPERCARE" ? <button onClick={() => void transitionWave(wave, "CLOSED")}>Close</button> : null}
            </div></td></tr>)}
            {!overview.go_live_waves.length ? <tr><td colSpan={3}>No go-live wave exists.</td></tr> : null}
          </tbody></table></div></section>
        </section>
      ) : null}

      {tab === "hypercare" ? (
        <section className={styles.gridTwo}>
          <form className={styles.panel} onSubmit={createHypercare}>
            <div className={styles.sectionLabel}>POST-GO-LIVE SUPPORT</div><h2>Log hypercare issue</h2>
            <div className={styles.formGrid}>
              <label>Issue code<input name="code" required placeholder="HC_001" /></label>
              <label>Severity<select name="severity_code" defaultValue="P2"><option>P0</option><option>P1</option><option>P2</option><option>P3</option></select></label>
              <label className={styles.full}>Title<input name="title" required /></label>
              <label>Area<input name="area_code" required defaultValue="GENERAL" /></label>
              <label>Wave<select name="wave_public_id" defaultValue=""><option value="">Unassigned</option>{overview.go_live_waves.map((wave) => <option key={wave.public_id} value={wave.public_id}>{wave.code}</option>)}</select></label>
              <label className={styles.full}>Impact<textarea name="impact_summary" rows={3} /></label>
              <input name="reported_at" type="hidden" value={new Date().toISOString()} readOnly />
            </div>
            <button className={styles.primary} disabled={busy}>Create issue</button>
          </form>
          <section className={styles.panel}><div className={styles.panelHeader}><div><div className={styles.sectionLabel}>HYPERCARE QUEUE</div><h2>Production issues</h2></div><input className={styles.search} value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Search hypercare" /></div><div className={styles.tableWrap}><table><thead><tr><th>Issue</th><th>Status</th><th>Control</th></tr></thead><tbody>
            {filteredHypercare.map((issue) => <tr key={issue.public_id}><td><strong>{issue.code} · {issue.title}</strong><small>{issue.area_code} · {issue.wave__code || "No wave"} · {formatDate(issue.reported_at)}</small></td><td><span className={statusClass(issue.severity_code)}>{issue.severity_code}</span> <span className={statusClass(issue.status_code)}>{issue.status_code}</span></td><td><div className={styles.actions}>
              {issue.status_code === "OPEN" ? <button onClick={() => void transitionHypercare(issue, "ACKNOWLEDGED")}>Acknowledge</button> : null}
              {["OPEN", "ACKNOWLEDGED"].includes(issue.status_code) ? <button onClick={() => void transitionHypercare(issue, "MITIGATING")}>Mitigate</button> : null}
              {issue.status_code === "MITIGATING" ? <button onClick={() => void transitionHypercare(issue, "RESOLVED")}>Resolve</button> : null}
              {issue.status_code === "RESOLVED" ? <button onClick={() => void transitionHypercare(issue, "CLOSED")}>Close</button> : null}
            </div></td></tr>)}
            {!filteredHypercare.length ? <tr><td colSpan={3}>No hypercare issues are visible.</td></tr> : null}
          </tbody></table></div></section>
        </section>
      ) : null}

      {tab === "gates" ? (
        <section className={styles.gateGrid}>
          {overview.gates.map((gate) => <article key={gate.public_id} className={styles.gateCard}><div><div className={styles.sectionLabel}>{gate.category_code}</div><h3>{gate.name}</h3><p>{gate.description}</p></div><div className={styles.gateFooter}><span className={statusClass(gate.status_code)}>{gate.status_code}</span><div className={styles.actions}><button onClick={() => void decideGate(gate, "PASSED")}>Pass</button><button onClick={() => void decideGate(gate, "FAILED")}>Fail</button><button onClick={() => void decideGate(gate, "WAIVED")}>Waive</button></div></div></article>)}
        </section>
      ) : null}
    </main>
  );
}
