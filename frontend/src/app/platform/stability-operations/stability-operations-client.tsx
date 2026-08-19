"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./stability-operations.module.css";

type Endpoint = {
  public_id: string;
  code: string;
  name: string;
  route_pattern: string;
  method_code: string;
  service_code: string;
  critical: boolean;
  target_p95_ms: number;
  target_availability_percent: string;
  active: boolean;
  version: number;
};
type Incident = {
  public_id: string;
  code: string;
  title: string;
  severity: string;
  status: string;
  source: string;
  service: string;
  impact: string;
  root_cause: string;
  resolution: string;
  detected_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  version: number;
};
type Regression = {
  public_id: string;
  code: string;
  title: string;
  area: string;
  severity: string;
  status: string;
  baseline: string | null;
  current: string | null;
  threshold: string | null;
  unit: string;
  detected_at: string;
  fixed_at: string | null;
  notes: string;
  version: number;
};
type Gate = {
  public_id: string;
  code: string;
  name: string;
  category: string;
  description: string;
  required: boolean;
  status: string;
  notes: string;
  evidence: Record<string, unknown>;
  decided_at: string | null;
  version: number;
};
type Sample = {
  public_id: string;
  endpoint_code: string | null;
  source: string;
  route: string;
  method: string;
  http_status: number | null;
  duration_ms: number;
  observed_at: string;
};
type Scan = {
  public_id: string;
  status: string;
  checks_total: number;
  checks_passed: number;
  checks_failed: number;
  api_p50_ms: number | null;
  api_p95_ms: number | null;
  api_p99_ms: number | null;
  error_rate_percent: string;
  results: { code: string; passed: boolean; critical: boolean; detail: string }[];
  started_at: string;
  completed_at: string | null;
};
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: {
    status: string;
    version: number;
    availability_target_percent: string;
    api_p95_budget_ms: number;
    page_load_budget_ms: number;
    slow_request_threshold_ms: number;
    error_budget_percent: string;
    incident_ack_sla_minutes: number;
    critical_resolution_sla_minutes: number;
    telemetry_retention_days: number;
  };
  metrics: Record<string, number>;
  endpoints: Endpoint[];
  incidents: Incident[];
  regressions: Regression[];
  gates: Gate[];
  recent_samples: Sample[];
  latest_scan: Scan | null;
  capabilities: Record<string, boolean>;
};
type Tab = "health" | "incidents" | "regressions" | "gates" | "telemetry";

const PROBES = [
  { label: "Platform shell", path: "/api/app-shell/context", endpointCode: "TENANT_CONTEXT" },
  { label: "Release readiness", path: "/api/platform/release-readiness/overview", endpointCode: "RELEASE_READINESS" },
  { label: "Project and work", path: "/api/platform/project-work/overview", endpointCode: "PROJECT_WORK" },
  { label: "My Work", path: "/api/platform/my-work/overview", endpointCode: "MY_WORK" },
] as const;

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
      ? `Stability service failed (${response.status}). Review the Django backend log.`
      : `Request failed (${response.status}).`;
    throw new Error(message || fallback);
  }
  return payload;
}

let pendingOverview: Promise<Overview> | null = null;
async function loadOverview(): Promise<Overview> {
  if (pendingOverview) return pendingOverview;
  pendingOverview = fetch("/api/platform/stability-operations/overview", { cache: "no-store" })
    .then(async (response) => await readJson(response) as unknown as Overview)
    .finally(() => { pendingOverview = null; });
  return pendingOverview;
}

async function post(path: string, data: unknown) {
  return readJson(await fetch(`/api/platform/stability-operations/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }));
}

function statusClass(status: string) {
  if (["PASSED", "ACTIVE", "RESOLVED", "CLOSED", "FIXED"].includes(status)) return styles.good;
  if (["FAILED", "P0", "P1", "CRITICAL", "HIGH", "OPEN"].includes(status)) return styles.bad;
  return styles.warn;
}

function nowLocalInput() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

export function StabilityOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("health");
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
      setError(caught instanceof Error ? caught.message : "Stability operations could not be loaded.");
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

  async function createEndpoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = Object.fromEntries(data.entries()) as Record<string, unknown>;
    payload.critical = data.get("critical") === "on";
    payload.active = data.get("active") === "on";
    payload.target_p95_ms = Number(payload.target_p95_ms);
    await execute(() => post("endpoints", payload), "Monitored endpoint registered.");
    form.reset();
  }

  async function createIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries());
    await execute(() => post("incidents", payload), "Production incident created.");
    form.reset();
  }

  async function transitionIncident(incident: Incident, status: string) {
    const resolution = status === "RESOLVED" || status === "CLOSED"
      ? window.prompt("Resolution summary", incident.resolution) ?? ""
      : "";
    await execute(() => post(`incidents/${incident.public_id}/transition`, {
      status_code: status,
      expected_version: incident.version,
      root_cause: incident.root_cause,
      resolution_summary: resolution,
    }), `Incident moved to ${status.toLowerCase()}.`);
  }

  async function createRegression(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = Object.fromEntries(data.entries()) as Record<string, unknown>;
    for (const key of ["baseline_value", "current_value", "threshold_value"]) {
      if (!payload[key]) payload[key] = null;
    }
    payload.evidence = { source: "phase34-ui", captured_at: new Date().toISOString() };
    await execute(() => post("regressions", payload), "Stabilization regression recorded.");
    form.reset();
  }

  async function transitionRegression(regression: Regression, status: string) {
    const notes = window.prompt("Decision notes", regression.notes) ?? regression.notes;
    await execute(() => post(`regressions/${regression.public_id}/transition`, {
      status_code: status,
      notes,
      expected_version: regression.version,
    }), `Regression moved to ${status.toLowerCase()}.`);
  }

  async function decideGate(gate: Gate, status: "PASSED" | "FAILED" | "WAIVED") {
    const notes = window.prompt(`${status} notes for ${gate.name}`, gate.notes) ?? "";
    await execute(() => post(`gates/${gate.public_id}/decision`, {
      status_code: status,
      notes,
      evidence: { source: "phase34-stability-control-room", recorded_at: new Date().toISOString() },
      expected_version: gate.version,
    }), `Gate ${status.toLowerCase()}.`);
  }

  async function runScan() {
    await execute(() => post("scans", {}), "Production stabilization scan completed.");
  }

  async function runBrowserBenchmark() {
    if (!overview) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const endpointByCode = new Map(overview.endpoints.map((endpoint) => [endpoint.code, endpoint]));
      for (const probe of PROBES) {
        const started = performance.now();
        let status = 599;
        try {
          const response = await fetch(probe.path, { cache: "no-store" });
          status = response.status;
          await response.arrayBuffer();
        } catch {
          status = 599;
        }
        const durationMs = Math.max(0, Math.round(performance.now() - started));
        const endpoint = endpointByCode.get(probe.endpointCode);
        await post("samples", {
          endpoint_public_id: endpoint?.public_id ?? null,
          source_code: "BROWSER",
          route_label: probe.path,
          method_code: "GET",
          http_status: status,
          duration_ms: durationMs,
          observed_at: new Date().toISOString(),
          metadata: { label: probe.label, navigation_type: performance.getEntriesByType("navigation")[0]?.entryType ?? "navigation" },
        });
      }
      setNotice("Browser benchmark captured for core platform routes.");
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Browser benchmark failed.");
    } finally {
      setBusy(false);
    }
  }

  const filteredIncidents = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return overview?.incidents ?? [];
    return (overview?.incidents ?? []).filter((item) =>
      [item.code, item.title, item.severity, item.status, item.service].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [overview, query]);

  const filteredRegressions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return overview?.regressions ?? [];
    return (overview?.regressions ?? []).filter((item) =>
      [item.code, item.title, item.area, item.severity, item.status].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [overview, query]);

  if (loading && !overview) return <div className={styles.loading}>Opening the Build360 production stability control room...</div>;
  if (!overview) {
    return <div className={styles.fatal}><div className={styles.eyebrow}>Stability control unavailable</div><h2>Production stabilization could not be opened.</h2><p>{error}</p><button className={styles.primary} onClick={() => void refresh()}>Retry workspace</button></div>;
  }

  const metrics = overview.metrics;
  const latestScan = overview.latest_scan;
  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <div className={styles.eyebrow}>MPSqre Build360 · Phase 34 · v1 stabilization</div>
          <h1>Stability & production operations</h1>
          <p>Measure platform performance, enforce budgets, register production incidents, govern regressions and complete the final stabilization gates before broad customer rollout.</p>
          <div className={styles.chips}><span>{overview.company.name}</span><span>{overview.company.timezone}</span><span>Policy v{overview.policy.version} · {overview.policy.status}</span></div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.phase}>PHASE 34 V1 STABILIZATION ACTIVE</span>
          <button className={styles.primary} onClick={() => void refresh()} disabled={busy}>Refresh control room</button>
        </div>
      </header>

      {error ? <div className={styles.alertError}>{error}</div> : null}
      {notice ? <div className={styles.alertSuccess}>{notice}</div> : null}

      <section className={styles.metrics}>
        <article><span>Availability · 24h</span><strong>{metrics.availability_24h?.toFixed?.(3) ?? metrics.availability_24h}%</strong><small>Target {overview.policy.availability_target_percent}%</small></article>
        <article><span>API p95</span><strong>{metrics.api_p95_ms ?? 0} ms</strong><small>Budget {overview.policy.api_p95_budget_ms} ms</small></article>
        <article><span>Error rate · 24h</span><strong>{metrics.error_rate_24h?.toFixed?.(3) ?? metrics.error_rate_24h}%</strong><small>Budget {overview.policy.error_budget_percent}%</small></article>
        <article><span>Open incidents</span><strong>{metrics.open_incidents ?? 0}</strong><small>{metrics.critical_incidents ?? 0} critical</small></article>
        <article><span>Open regressions</span><strong>{metrics.open_regressions ?? 0}</strong><small>Stabilization backlog</small></article>
        <article><span>Stabilization gates</span><strong>{metrics.required_gates_passed ?? 0}/{metrics.required_gates_total ?? 0}</strong><small>Required controls passed</small></article>
      </section>

      <section className={styles.controlBar}>
        <div><div className={styles.sectionLabel}>Latest automated scan</div><h2>{latestScan?.status ?? "NOT RUN"}</h2><p>{latestScan ? `${latestScan.checks_passed}/${latestScan.checks_total} checks passed · p95 ${latestScan.api_p95_ms ?? 0} ms` : "Capture browser telemetry, then run the governed stability scan."}</p></div>
        <div className={styles.inlineActions}>
          <button className={styles.secondary} onClick={() => void runBrowserBenchmark()} disabled={busy || !overview.capabilities.can_record_telemetry}>Run browser benchmark</button>
          <button className={styles.primary} onClick={() => void runScan()} disabled={busy || !overview.capabilities.can_scan}>Run stabilization scan</button>
        </div>
      </section>

      <nav className={styles.tabs} aria-label="Stability operations sections">
        <button className={tab === "health" ? styles.activeTab : ""} onClick={() => setTab("health")}>Health & performance</button>
        <button className={tab === "incidents" ? styles.activeTab : ""} onClick={() => setTab("incidents")}>Incidents</button>
        <button className={tab === "regressions" ? styles.activeTab : ""} onClick={() => setTab("regressions")}>Regressions</button>
        <button className={tab === "gates" ? styles.activeTab : ""} onClick={() => setTab("gates")}>Stabilization gates</button>
        <button className={tab === "telemetry" ? styles.activeTab : ""} onClick={() => setTab("telemetry")}>Telemetry</button>
      </nav>

      {tab === "health" ? <section className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.sectionLabel}>Endpoint registry</div><h2>Add monitored route</h2>
          <form onSubmit={createEndpoint}>
            <div className={styles.formGrid}>
              <label>Code<input name="code" placeholder="PROCUREMENT_OVERVIEW" required /></label>
              <label>Name<input name="name" placeholder="Procurement overview" required /></label>
              <label className={styles.full}>Backend route<input name="route_pattern" placeholder="/api/v1/..." required /></label>
              <label>Method<select name="method_code" defaultValue="GET"><option>GET</option><option>POST</option><option>PATCH</option></select></label>
              <label>Service<input name="service_code" defaultValue="BACKEND" required /></label>
              <label>p95 budget ms<input name="target_p95_ms" type="number" min="1" defaultValue="750" required /></label>
              <label>Availability %<input name="target_availability_percent" type="number" step="0.01" min="0" max="100" defaultValue="99.90" required /></label>
              <label className={styles.checkbox}><input name="critical" type="checkbox" defaultChecked />Critical route</label>
              <label className={styles.checkbox}><input name="active" type="checkbox" defaultChecked />Active monitoring</label>
            </div>
            <button className={styles.primary} disabled={busy || !overview.capabilities.can_configure}>Register endpoint</button>
          </form>
        </article>
        <article className={styles.card}>
          <div className={styles.sectionLabel}>Automated evidence</div><h2>Latest scan results</h2>
          <div className={styles.checkGrid}>
            {(latestScan?.results ?? []).map((item) => <div className={item.passed ? styles.checkPassed : styles.checkFailed} key={item.code}><strong>{item.code}</strong><span>{item.passed ? "PASS" : item.critical ? "FAIL" : "WARN"}</span><p>{item.detail}</p></div>)}
            {!latestScan ? <p className={styles.empty}>No stability scan has been executed.</p> : null}
          </div>
        </article>
        <article className={`${styles.card} ${styles.fullCard}`}>
          <div className={styles.sectionLabel}>Monitored surface</div><h2>Core endpoint budgets</h2>
          <div className={styles.tableWrap}><table><thead><tr><th>Endpoint</th><th>Route</th><th>Service</th><th>p95 budget</th><th>Availability</th><th>Critical</th></tr></thead><tbody>{overview.endpoints.map((endpoint) => <tr key={endpoint.public_id}><td><strong>{endpoint.code}</strong><small>{endpoint.name}</small></td><td>{endpoint.method_code} {endpoint.route_pattern}</td><td>{endpoint.service_code}</td><td>{endpoint.target_p95_ms} ms</td><td>{endpoint.target_availability_percent}%</td><td>{endpoint.critical ? "YES" : "NO"}</td></tr>)}</tbody></table></div>
        </article>
      </section> : null}

      {tab === "incidents" ? <section className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.sectionLabel}>Incident intake</div><h2>Create production incident</h2>
          <form onSubmit={createIncident}>
            <div className={styles.formGrid}>
              <label>Incident code<input name="code" placeholder="INC-2026-001" required /></label>
              <label>Severity<select name="severity_code" defaultValue="P2"><option>P0</option><option>P1</option><option>P2</option><option>P3</option></select></label>
              <label className={styles.full}>Title<input name="title" required /></label>
              <label>Source<input name="source_code" defaultValue="MANUAL" /></label>
              <label>Affected service<input name="affected_service_code" /></label>
              <label className={styles.full}>Impact<textarea name="impact_summary" rows={3} /></label>
              <label>Detected at<input name="detected_at" type="datetime-local" defaultValue={nowLocalInput()} required /></label>
            </div>
            <button className={styles.primary} disabled={busy || !overview.capabilities.can_manage_incidents}>Create incident</button>
          </form>
        </article>
        <article className={styles.card}>
          <div className={styles.listHeader}><div><div className={styles.sectionLabel}>Production response</div><h2>Incident register</h2></div><input className={styles.search} value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Search incidents" /></div>
          <div className={styles.list}>{filteredIncidents.map((incident) => <div className={styles.listRow} key={incident.public_id}><div><strong>{incident.code} · {incident.title}</strong><small>{incident.service || "General"} · {new Date(incident.detected_at).toLocaleString()}</small></div><span className={`${styles.badge} ${statusClass(incident.severity)}`}>{incident.severity}</span><span className={`${styles.badge} ${statusClass(incident.status)}`}>{incident.status}</span><div className={styles.inlineActions}><button onClick={() => void transitionIncident(incident, "ACKNOWLEDGED")} disabled={busy || incident.status !== "OPEN"}>Acknowledge</button><button onClick={() => void transitionIncident(incident, "MITIGATING")} disabled={busy || ["RESOLVED", "CLOSED"].includes(incident.status)}>Mitigate</button><button onClick={() => void transitionIncident(incident, "RESOLVED")} disabled={busy || ["RESOLVED", "CLOSED"].includes(incident.status)}>Resolve</button><button onClick={() => void transitionIncident(incident, "CLOSED")} disabled={busy || incident.status !== "RESOLVED"}>Close</button></div></div>)}{!filteredIncidents.length ? <p className={styles.empty}>No incident matches this view.</p> : null}</div>
        </article>
      </section> : null}

      {tab === "regressions" ? <section className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.sectionLabel}>Regression intake</div><h2>Record stabilization regression</h2>
          <form onSubmit={createRegression}>
            <div className={styles.formGrid}>
              <label>Regression code<input name="code" placeholder="REG-PERF-001" required /></label>
              <label>Severity<select name="severity_code" defaultValue="MEDIUM"><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></label>
              <label className={styles.full}>Title<input name="title" required /></label>
              <label>Area<input name="area_code" defaultValue="PERFORMANCE" /></label>
              <label>Unit<input name="unit_code" placeholder="ms / % / count" /></label>
              <label>Baseline<input name="baseline_value" type="number" step="0.001" /></label>
              <label>Current<input name="current_value" type="number" step="0.001" /></label>
              <label>Threshold<input name="threshold_value" type="number" step="0.001" /></label>
              <label>Detected at<input name="detected_at" type="datetime-local" defaultValue={nowLocalInput()} required /></label>
              <label className={styles.full}>Notes<textarea name="notes" rows={3} /></label>
            </div>
            <button className={styles.primary} disabled={busy || !overview.capabilities.can_manage_regressions}>Record regression</button>
          </form>
        </article>
        <article className={styles.card}>
          <div className={styles.listHeader}><div><div className={styles.sectionLabel}>Stabilization backlog</div><h2>Regression register</h2></div><input className={styles.search} value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Search regressions" /></div>
          <div className={styles.list}>{filteredRegressions.map((item) => <div className={styles.listRow} key={item.public_id}><div><strong>{item.code} · {item.title}</strong><small>{item.area} · {item.baseline ?? "-"} → {item.current ?? "-"} {item.unit}</small></div><span className={`${styles.badge} ${statusClass(item.severity)}`}>{item.severity}</span><span className={`${styles.badge} ${statusClass(item.status)}`}>{item.status}</span><div className={styles.inlineActions}><button onClick={() => void transitionRegression(item, "ACCEPTED")} disabled={busy || item.status !== "OPEN"}>Accept</button><button onClick={() => void transitionRegression(item, "FIXED")} disabled={busy || item.status === "FIXED"}>Mark fixed</button><button onClick={() => void transitionRegression(item, "WONT_FIX")} disabled={busy || item.status === "FIXED"}>Won&apos;t fix</button></div></div>)}{!filteredRegressions.length ? <p className={styles.empty}>No regression matches this view.</p> : null}</div>
        </article>
      </section> : null}

      {tab === "gates" ? <section className={styles.card}>
        <div className={styles.sectionLabel}>Governed launch assurance</div><h2>Build360 v1 stabilization gates</h2>
        <div className={styles.list}>{overview.gates.map((gate) => <div className={styles.listRow} key={gate.public_id}><div><strong>{gate.name}</strong><small>{gate.category} · {gate.code}{gate.required ? " · Required" : ""}</small><p>{gate.description}</p></div><span className={`${styles.badge} ${statusClass(gate.status)}`}>{gate.status}</span><div className={styles.inlineActions}><button onClick={() => void decideGate(gate, "PASSED")} disabled={busy || !overview.capabilities.can_decide_gates}>Pass</button><button onClick={() => void decideGate(gate, "FAILED")} disabled={busy || !overview.capabilities.can_decide_gates}>Fail</button><button onClick={() => void decideGate(gate, "WAIVED")} disabled={busy || !overview.capabilities.can_decide_gates}>Waive</button></div></div>)}</div>
      </section> : null}

      {tab === "telemetry" ? <section className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.sectionLabel}>Performance policy</div><h2>Current operating budgets</h2>
          <dl className={styles.definition}><div><dt>Availability target</dt><dd>{overview.policy.availability_target_percent}%</dd></div><div><dt>API p95 budget</dt><dd>{overview.policy.api_p95_budget_ms} ms</dd></div><div><dt>Page load budget</dt><dd>{overview.policy.page_load_budget_ms} ms</dd></div><div><dt>Slow request threshold</dt><dd>{overview.policy.slow_request_threshold_ms} ms</dd></div><div><dt>Error budget</dt><dd>{overview.policy.error_budget_percent}%</dd></div><div><dt>Telemetry retention</dt><dd>{overview.policy.telemetry_retention_days} days</dd></div></dl>
        </article>
        <article className={`${styles.card} ${styles.fullCard}`}>
          <div className={styles.sectionLabel}>Recent measurements</div><h2>Performance telemetry</h2>
          <div className={styles.tableWrap}><table><thead><tr><th>Observed</th><th>Source</th><th>Endpoint</th><th>Route</th><th>Status</th><th>Duration</th></tr></thead><tbody>{overview.recent_samples.map((sample) => <tr key={sample.public_id}><td>{new Date(sample.observed_at).toLocaleString()}</td><td>{sample.source}</td><td>{sample.endpoint_code ?? "UNMAPPED"}</td><td>{sample.method} {sample.route}</td><td>{sample.http_status ?? "-"}</td><td><strong>{sample.duration_ms} ms</strong></td></tr>)}</tbody></table>{!overview.recent_samples.length ? <p className={styles.empty}>No telemetry captured. Run the browser benchmark.</p> : null}</div>
        </article>
      </section> : null}
    </main>
  );
}
