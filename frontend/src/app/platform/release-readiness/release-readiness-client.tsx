"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./release-readiness.module.css";

type Target = {
  public_id: string;
  code: string;
  name: string;
  environment: string;
  frontend_url: string;
  backend_url: string;
  health_url: string;
  provider: string;
  region: string;
  status: string;
  version: number;
};
type Release = {
  public_id: string;
  release_code: string;
  version_label: string;
  title: string;
  summary: string;
  status: string;
  source_reference: string;
  artifact_reference: string;
  artifact_sha256: string;
  planned_at: string | null;
  approved_at: string | null;
  published_at: string | null;
  target: { public_id: string; code: string; name: string } | null;
  version: number;
};
type Gate = {
  public_id: string;
  code: string;
  name: string;
  category: string;
  required: boolean;
  status: string;
  notes: string;
  evidence: Record<string, unknown>;
  version: number;
};
type Scenario = {
  public_id: string;
  code: string;
  title: string;
  module: string;
  persona: string;
  required: boolean;
  steps: string[];
  expected_result: string;
  execution: null | {
    public_id: string;
    status: string;
    notes: string;
    defect_reference: string;
    evidence: Record<string, unknown>;
    version: number;
  };
};
type Backup = {
  public_id: string;
  reference: string;
  type: string;
  status: string;
  storage_reference: string;
  restore_tested: boolean;
  captured_at: string;
  retention_until: string | null;
  release_code: string | null;
  target_code: string | null;
};
type ReadinessRun = {
  public_id: string;
  status: string;
  checks_total: number;
  checks_passed: number;
  checks_failed: number;
  results: { code: string; passed: boolean; critical: boolean; detail: string }[];
  started_at: string;
  completed_at: string | null;
  release_code: string | null;
};
type Overview = {
  company: { name: string; timezone: string; currency: string };
  metrics: Record<string, number>;
  current_release: Release | null;
  targets: Target[];
  gates: Gate[];
  scenarios: Scenario[];
  backups: Backup[];
  readiness_runs: ReadinessRun[];
  capabilities: Record<string, boolean>;
};
type Tab = "gates" | "uat" | "targets" | "backup";

async function readJson(response: Response) {
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
    const fallback = response.status >= 500
      ? `Release readiness service failed (${response.status}). Review the Django backend log.`
      : `Request failed (${response.status}).`;
    throw new Error(message || fallback);
  }
  return payload;
}

let pendingOverviewRequest: Promise<Overview> | null = null;

async function loadOverview(): Promise<Overview> {
  if (pendingOverviewRequest) return pendingOverviewRequest;
  pendingOverviewRequest = fetch("/api/platform/release-readiness/overview", { cache: "no-store" })
    .then(async (response) => await readJson(response) as unknown as Overview)
    .finally(() => {
      pendingOverviewRequest = null;
    });
  return pendingOverviewRequest;
}

async function post(path: string, data: unknown) {
  return readJson(await fetch(`/api/platform/release-readiness/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }));
}

function badgeClass(status: string) {
  if (["PASSED", "APPROVED", "PUBLISHED", "AVAILABLE", "ACTIVE"].includes(status)) return styles.good;
  if (["FAILED", "REJECTED", "BLOCKED"].includes(status)) return styles.bad;
  return styles.pending;
}

export function ReleaseReadinessClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("gates");
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
      setError(caught instanceof Error ? caught.message : "Release readiness could not be loaded.");
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

  async function createTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await execute(() => post("targets", Object.fromEntries(data.entries())), "Deployment target created.");
    form.reset();
  }

  async function createRelease(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = Object.fromEntries(data.entries()) as Record<string, unknown>;
    if (!payload.planned_at) payload.planned_at = null;
    await execute(() => post("releases", payload), "Release candidate and governance pack created.");
    form.reset();
  }

  async function decideGate(gate: Gate, status: "PASSED" | "FAILED") {
    const notes = window.prompt(`${status} notes for ${gate.name}`, gate.notes) ?? "";
    await execute(() => post(`gates/${gate.public_id}/decision`, {
      status_code: status,
      notes,
      evidence: { source: "release-readiness-ui", recorded_at: new Date().toISOString() },
      expected_version: gate.version,
    }), `Gate ${status.toLowerCase()}.`);
  }

  async function decideUat(scenario: Scenario, status: "PASSED" | "FAILED" | "BLOCKED") {
    if (!scenario.execution) return;
    const notes = window.prompt(`${status} notes for ${scenario.code}`, scenario.execution.notes) ?? "";
    const defect = status === "PASSED" ? "" : (window.prompt("Defect or blocker reference", scenario.execution.defect_reference) ?? "");
    await execute(() => post(`uat/${scenario.execution?.public_id}/execute`, {
      status_code: status,
      notes,
      defect_reference: defect,
      evidence: { source: "uat-control-room", recorded_at: new Date().toISOString() },
      expected_version: scenario.execution?.version,
    }), `UAT ${scenario.code} recorded as ${status.toLowerCase()}.`);
  }

  async function createBackup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = Object.fromEntries(data.entries()) as Record<string, unknown>;
    payload.release_public_id = payload.release_public_id || null;
    payload.target_public_id = payload.target_public_id || null;
    payload.restore_tested = data.get("restore_tested") === "on";
    payload.database_included = data.get("database_included") === "on";
    payload.media_included = data.get("media_included") === "on";
    payload.configuration_included = data.get("configuration_included") === "on";
    payload.restore_tested_at = payload.restore_tested ? new Date().toISOString() : null;
    payload.retention_until = payload.retention_until || null;
    await execute(() => post("backups", payload), "Backup and restore evidence registered.");
    form.reset();
  }

  async function runReadiness() {
    await execute(() => post("readiness-runs", {
      release_public_id: overview?.current_release?.public_id ?? null,
    }), "Readiness scan completed.");
  }

  async function approve() {
    const release = overview?.current_release;
    if (!release) return;
    await execute(() => post(`releases/${release.public_id}/approve`, { expected_version: release.version }), "Release candidate approved.");
  }

  async function publish() {
    const release = overview?.current_release;
    if (!release) return;
    if (!window.confirm(`Publish ${release.release_code} to ${release.target?.name ?? "the selected target"}?`)) return;
    await execute(() => post(`releases/${release.public_id}/publish`, { expected_version: release.version }), "Build360 v1 release published.");
  }

  const filteredScenarios = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return overview?.scenarios ?? [];
    return (overview?.scenarios ?? []).filter((scenario) =>
      [scenario.code, scenario.title, scenario.module, scenario.persona, scenario.execution?.status ?? ""]
        .some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [overview, query]);

  if (loading && !overview) return <div className={styles.loading}>Opening the Build360 v1 release control room...</div>;
  if (!overview) {
    return <div className={styles.fatal}><div className={styles.eyebrow}>Release control unavailable</div><h2>Deployment, UAT and release readiness could not be opened.</h2><p>{error}</p><button className={styles.primary} onClick={() => void refresh()}>Retry workspace</button></div>;
  }

  const m = overview.metrics;
  const release = overview.current_release;
  const latestRun = overview.readiness_runs[0];
  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <div className={styles.eyebrow}>MPSqre Build360 · Phase 33 · v1 completion</div>
          <h1>Deployment, UAT & release readiness</h1>
          <p>Convert the complete Construction Operating System into a controlled, evidence-backed production release with deployment targets, release gates, end-to-end UAT, backup assurance and maker-checker publication.</p>
          <div className={styles.chips}><span>{overview.company.name}</span><span>{overview.company.timezone}</span><span>{release?.version_label ?? "v1.0.0"}</span></div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.phase}>PHASE 33 BUILD360 V1 RELEASE ACTIVE</span>
          <button className={styles.primary} onClick={() => void refresh()} disabled={busy}>Refresh control room</button>
        </div>
      </header>

      {error ? <div className={styles.alertError}>{error}</div> : null}
      {notice ? <div className={styles.alertSuccess}>{notice}</div> : null}

      <section className={styles.metrics}>
        <article><span>Release status</span><strong>{release?.status ?? "NOT STARTED"}</strong><small>{release?.release_code ?? "Create the first release candidate"}</small></article>
        <article><span>Required gates</span><strong>{m.required_gates_passed ?? 0}/{m.required_gates_total ?? 0}</strong><small>Governance assurance</small></article>
        <article><span>End-to-end UAT</span><strong>{m.uat_passed ?? 0}/{m.uat_total ?? 0}</strong><small>Required journeys passed</small></article>
        <article><span>Backups</span><strong>{m.available_backups ?? 0}</strong><small>Available recovery points</small></article>
        <article><span>Readiness</span><strong>{latestRun?.status ?? "NOT RUN"}</strong><small>{latestRun ? `${latestRun.checks_passed}/${latestRun.checks_total} checks passed` : "Run the release scan"}</small></article>
      </section>

      <section className={styles.releaseBar}>
        <div>
          <div className={styles.sectionLabel}>Current release candidate</div>
          <h2>{release ? `${release.version_label} · ${release.title}` : "No release candidate yet"}</h2>
          <p>{release?.summary || "Create the controlled Build360 v1 release baseline, then complete every required gate and UAT journey."}</p>
        </div>
        <div className={styles.releaseActions}>
          <button className={styles.secondary} onClick={() => void runReadiness()} disabled={busy || !overview.capabilities.can_manage}>Run readiness scan</button>
          <button className={styles.secondary} onClick={() => void approve()} disabled={busy || !release || !overview.capabilities.can_approve || release.status === "APPROVED" || release.status === "PUBLISHED"}>Approve release</button>
          <button className={styles.primary} onClick={() => void publish()} disabled={busy || !release || !overview.capabilities.can_publish || release.status !== "APPROVED"}>Publish v1</button>
        </div>
      </section>

      <nav className={styles.tabs} aria-label="Release readiness sections">
        <button className={tab === "gates" ? styles.activeTab : ""} onClick={() => setTab("gates")}>Release gates</button>
        <button className={tab === "uat" ? styles.activeTab : ""} onClick={() => setTab("uat")}>End-to-end UAT</button>
        <button className={tab === "targets" ? styles.activeTab : ""} onClick={() => setTab("targets")}>Deployment targets</button>
        <button className={tab === "backup" ? styles.activeTab : ""} onClick={() => setTab("backup")}>Backup & recovery</button>
      </nav>

      {tab === "gates" ? <section className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.sectionLabel}>Release baseline</div><h2>Create release candidate</h2>
          <form onSubmit={createRelease}>
            <div className={styles.formGrid}>
              <label>Release code<input name="release_code" defaultValue="BUILD360_V1" required /></label>
              <label>Version<input name="version_label" defaultValue="v1.0.0" required /></label>
              <label className={styles.full}>Title<input name="title" defaultValue="MPSqre Build360 v1 production release" required /></label>
              <label className={styles.full}>Summary<textarea name="summary" rows={3} defaultValue="First governed Build360 Construction Operating System release." /></label>
              <label>Deployment target<select name="target_public_id" required defaultValue={overview.targets[0]?.public_id ?? ""}><option value="" disabled>Create a target first</option>{overview.targets.map((target) => <option key={target.public_id} value={target.public_id}>{target.code} · {target.name}</option>)}</select></label>
              <label>Planned deployment<input name="planned_at" type="datetime-local" /></label>
              <label>Source reference<input name="source_reference" placeholder="Git commit / branch" /></label>
              <label>Artifact reference<input name="artifact_reference" placeholder="Image tag / archive / URL" /></label>
              <label className={styles.full}>Artifact SHA-256<input name="artifact_sha256" maxLength={64} placeholder="Optional 64-character checksum" /></label>
            </div>
            <button className={styles.primary} disabled={busy || !overview.capabilities.can_manage || overview.targets.length === 0}>Create governed release</button>
          </form>
        </article>
        <article className={styles.card}>
          <div className={styles.sectionLabel}>Control assurance</div><h2>Required release gates</h2>
          <div className={styles.list}>
            {overview.gates.map((gate) => <div className={styles.listRow} key={gate.public_id}>
              <div><strong>{gate.name}</strong><small>{gate.category} · {gate.code}{gate.required ? " · Required" : ""}</small></div>
              <span className={`${styles.badge} ${badgeClass(gate.status)}`}>{gate.status}</span>
              <div className={styles.inlineActions}>
                <button onClick={() => void decideGate(gate, "PASSED")} disabled={busy || !overview.capabilities.can_gate}>Pass</button>
                <button onClick={() => void decideGate(gate, "FAILED")} disabled={busy || !overview.capabilities.can_gate}>Fail</button>
              </div>
            </div>)}
            {!overview.gates.length ? <p className={styles.empty}>Create a release candidate to generate the ten required release gates.</p> : null}
          </div>
        </article>
        <article className={`${styles.card} ${styles.fullCard}`}>
          <div className={styles.sectionLabel}>Readiness evidence</div><h2>Latest automated control scan</h2>
          {latestRun ? <div className={styles.checkGrid}>{latestRun.results.map((item) => <div className={item.passed ? styles.checkPassed : styles.checkFailed} key={item.code}><strong>{item.code}</strong><span>{item.passed ? "PASS" : "FAIL"}</span><p>{item.detail}</p></div>)}</div> : <p className={styles.empty}>No readiness scan has been executed.</p>}
        </article>
      </section> : null}

      {tab === "uat" ? <section className={styles.card}>
        <div className={styles.tableHeader}><div><div className={styles.sectionLabel}>Business acceptance</div><h2>Twenty end-to-end Build360 journeys</h2></div><input className={styles.search} value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Search UAT journey" /></div>
        <div className={styles.tableWrap}><table><thead><tr><th>Scenario</th><th>Module</th><th>Persona</th><th>Status</th><th>Decision</th></tr></thead><tbody>
          {filteredScenarios.map((scenario) => <tr key={scenario.public_id}><td><strong>{scenario.code}</strong><span>{scenario.title}</span></td><td>{scenario.module}</td><td>{scenario.persona || "—"}</td><td><span className={`${styles.badge} ${badgeClass(scenario.execution?.status ?? "NOT_RUN")}`}>{scenario.execution?.status ?? "NOT RUN"}</span>{scenario.execution?.defect_reference ? <small>{scenario.execution.defect_reference}</small> : null}</td><td><div className={styles.inlineActions}><button onClick={() => void decideUat(scenario, "PASSED")} disabled={busy || !scenario.execution || !overview.capabilities.can_uat}>Pass</button><button onClick={() => void decideUat(scenario, "FAILED")} disabled={busy || !scenario.execution || !overview.capabilities.can_uat}>Fail</button><button onClick={() => void decideUat(scenario, "BLOCKED")} disabled={busy || !scenario.execution || !overview.capabilities.can_uat}>Block</button></div></td></tr>)}
          {!filteredScenarios.length ? <tr><td colSpan={5} className={styles.empty}>Create a release candidate to initialize UAT executions.</td></tr> : null}
        </tbody></table></div>
      </section> : null}

      {tab === "targets" ? <section className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.sectionLabel}>Deployment topology</div><h2>Create deployment target</h2>
          <form onSubmit={createTarget}><div className={styles.formGrid}>
            <label>Code<input name="code" defaultValue="PRODUCTION" required /></label>
            <label>Name<input name="name" defaultValue="Build360 Production" required /></label>
            <label>Environment<select name="environment_code" defaultValue="PRODUCTION"><option>LOCAL</option><option>DEVELOPMENT</option><option>STAGING</option><option>PRODUCTION</option></select></label>
            <label>Hosting provider<input name="hosting_provider_code" placeholder="Vercel / Render / AWS" /></label>
            <label className={styles.full}>Frontend URL<input name="frontend_url" type="url" placeholder="https://app.example.com" required /></label>
            <label className={styles.full}>Backend URL<input name="backend_url" type="url" placeholder="https://api.example.com" required /></label>
            <label className={styles.full}>Readiness URL<input name="health_url" type="url" placeholder="https://api.example.com/api/v1/health/ready" /></label>
            <label>Region<input name="region_code" placeholder="ap-south-1" /></label>
          </div><button className={styles.primary} disabled={busy || !overview.capabilities.can_target}>Create target</button></form>
        </article>
        <article className={styles.card}><div className={styles.sectionLabel}>Environment register</div><h2>Deployment targets</h2><div className={styles.list}>{overview.targets.map((target) => <div className={styles.target} key={target.public_id}><div><strong>{target.name}</strong><small>{target.code} · {target.environment} · {target.provider || "Provider not set"}</small></div><span className={`${styles.badge} ${badgeClass(target.status)}`}>{target.status}</span><a href={target.frontend_url} target="_blank" rel="noreferrer">Open</a></div>)}{!overview.targets.length ? <p className={styles.empty}>No deployment targets configured.</p> : null}</div></article>
      </section> : null}

      {tab === "backup" ? <section className={styles.grid}>
        <article className={styles.card}><div className={styles.sectionLabel}>Recovery assurance</div><h2>Register backup evidence</h2>
          <form onSubmit={createBackup}><div className={styles.formGrid}>
            <label>Reference<input name="reference" defaultValue={`BUILD360-${new Date().toISOString().slice(0, 10)}`} required /></label>
            <label>Backup type<select name="backup_type_code" defaultValue="FULL"><option>FULL</option><option>DATABASE</option><option>MEDIA</option><option>CONFIGURATION</option></select></label>
            <label>Release<select name="release_public_id" defaultValue={release?.public_id ?? ""}><option value="">General recovery point</option>{release ? <option value={release.public_id}>{release.release_code}</option> : null}</select></label>
            <label>Target<select name="target_public_id" defaultValue={release?.target?.public_id ?? overview.targets[0]?.public_id ?? ""}><option value="">Select target</option>{overview.targets.map((target) => <option key={target.public_id} value={target.public_id}>{target.code}</option>)}</select></label>
            <label className={styles.full}>Storage reference<input name="storage_reference" placeholder="Encrypted object key / vault reference" required /></label>
            <label className={styles.full}>SHA-256<input name="checksum_sha256" maxLength={64} placeholder="Optional checksum" /></label>
            <label>Captured at<input name="captured_at" type="datetime-local" required /></label>
            <label>Retention until<input name="retention_until" type="datetime-local" /></label>
            <label className={styles.check}><input name="database_included" type="checkbox" defaultChecked /> Database included</label>
            <label className={styles.check}><input name="media_included" type="checkbox" defaultChecked /> Media included</label>
            <label className={styles.check}><input name="configuration_included" type="checkbox" defaultChecked /> Configuration included</label>
            <label className={styles.check}><input name="restore_tested" type="checkbox" /> Restore drill passed</label>
          </div><button className={styles.primary} disabled={busy || !overview.capabilities.can_backup}>Register backup</button></form>
        </article>
        <article className={styles.card}><div className={styles.sectionLabel}>Recovery points</div><h2>Backup register</h2><div className={styles.list}>{overview.backups.map((backup) => <div className={styles.listRow} key={backup.public_id}><div><strong>{backup.reference}</strong><small>{backup.type} · {backup.release_code ?? "General"} · {new Date(backup.captured_at).toLocaleString()}</small></div><span className={`${styles.badge} ${badgeClass(backup.status)}`}>{backup.restore_tested ? "RESTORE TESTED" : backup.status}</span></div>)}{!overview.backups.length ? <p className={styles.empty}>No backup evidence registered.</p> : null}</div></article>
      </section> : null}
    </main>
  );
}
