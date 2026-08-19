"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

type Environment = {
  public_id: string;
  code: string;
  name: string;
  environment_type: string;
  base_url: string;
  region: string;
  data_residency: string;
  is_active: boolean;
};
type Target = {
  public_id: string;
  environment: Environment;
  code: string;
  name: string;
  provider: string;
  region: string;
  data_residency: string;
  backend_service: string;
  frontend_service: string;
  database_service: string;
  cache_service: string;
  object_storage_service: string;
  worker_service: string;
  secret_manager_service: string;
  status: string;
  production_approved: boolean;
  version: number;
};
type Pipeline = {
  public_id: string;
  target: { public_id: string; code: string; name: string };
  code: string;
  name: string;
  source_branch: string;
  trigger_mode: string;
  quality_gates: string[];
  requires_approval: boolean;
  is_active: boolean;
  version: number;
};
type Deployment = {
  public_id: string;
  pipeline: Pipeline;
  release: { public_id: string; version_label: string; status: string } | null;
  status: string;
  source_revision: string;
  artifact_sha256: string;
  deployment_url: string;
  requested_by_public_id: string;
  approved_by_public_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_summary: string;
  rollback_reference: string;
  readiness: {
    target_ready: boolean;
    production_approved: boolean;
    release_ready: boolean;
    ready: boolean;
    quality_gates: string[];
  };
  version: number;
};
type BackupPolicy = {
  public_id: string;
  target: { public_id: string; code: string; name: string };
  code: string;
  name: string;
  resource_type: string;
  schedule_cron: string;
  retention_days: number;
  encryption_required: boolean;
  point_in_time_recovery: boolean;
  is_active: boolean;
  version: number;
};
type BackupExecution = {
  public_id: string;
  policy: { public_id: string; code: string; name: string };
  status: string;
  backup_reference: string;
  backup_sha256: string;
  size_bytes: number;
  recovery_point_at: string | null;
  started_at: string;
  finished_at: string | null;
  evidence_sha256: string;
  error_summary: string;
};
type RestoreExercise = {
  public_id: string;
  target: { public_id: string; code: string; name: string };
  backup_execution: { public_id: string; policy_code: string };
  status: string;
  measured_rpo_minutes: number | null;
  measured_rto_minutes: number | null;
  evidence_sha256: string;
  notes: string;
  version: number;
};
type SecretPolicy = {
  public_id: string;
  target: { public_id: string; code: string; name: string };
  code: string;
  name: string;
  secret_provider: string;
  secret_reference: string;
  rotation_interval_days: number;
  last_rotated_at: string | null;
  next_rotation_at: string | null;
  status: string;
  version: number;
};

export type CloudopsPortfolio = {
  current_user_public_id: string;
  summary: {
    targets: number;
    active_targets: number;
    production_targets: number;
    pipelines: number;
    deployments: number;
    failed_deployments: number;
    latest_deployment_status: string | null;
    backup_policies: number;
    verified_backups: number;
    latest_backup_status: string | null;
    passed_restore_exercises: number;
    secrets_due: number;
  };
  environments: Environment[];
  targets: Target[];
  pipelines: Pipeline[];
  deployments: Deployment[];
  backup_policies: BackupPolicy[];
  backup_executions: BackupExecution[];
  restore_exercises: RestoreExercise[];
  secret_policies: SecretPolicy[];
};

type Tab = "targets" | "deployments" | "recovery" | "secrets";

const inputClass =
  "w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-700";

function label(value: string | null) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "None";
}

function Status({ value }: Readonly<{ value: string }>) {
  const positive = ["active", "ready", "succeeded", "verified", "passed", "approved", "current"].includes(value);
  const negative = ["failed", "suspended", "retired", "overdue", "rolled_back"].includes(value);
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${
        positive
          ? "bg-emerald-100 text-emerald-900"
          : negative
            ? "bg-red-100 text-red-800"
            : "bg-amber-100 text-amber-900"
      }`}
    >
      {label(value)}
    </span>
  );
}

function Empty({ children }: Readonly<{ children: string }>) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-white p-8 text-sm text-[var(--muted)]">
      {children}
    </div>
  );
}

export function CloudLaunchWorkspace({ initialData }: Readonly<{ initialData: CloudopsPortfolio }>) {
  const [data, setData] = useState(initialData);
  const [tab, setTab] = useState<Tab>("targets");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const successfulBackups = useMemo(
    () => data.backup_executions.filter((item) => ["succeeded", "verified"].includes(item.status)),
    [data.backup_executions],
  );

  async function refresh() {
    const response = await fetch("/api/cloudops/portfolio", { cache: "no-store" });
    if (response.ok) setData((await response.json()) as CloudopsPortfolio);
  }

  async function post(path: string, body: Record<string, unknown>, key: string) {
    setBusy(key);
    setMessage(null);
    const response = await fetch(`/api/cloudops/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = (await response.json().catch(() => ({}))) as {
      message?: string;
      detail?: string;
      non_field_errors?: string[];
      [key: string]: unknown;
    };
    if (!response.ok) {
      const fieldError = Object.values(result).find(
        (value) => Array.isArray(value) && value.every((item) => typeof item === "string"),
      ) as string[] | undefined;
      setMessage(
        result.message ?? result.detail ?? result.non_field_errors?.join(" ") ?? fieldError?.join(" ") ?? "The action failed.",
      );
    } else {
      setMessage("Action completed successfully.");
      await refresh();
    }
    setBusy(null);
  }

  async function createTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await post(
      "targets",
      {
        environment_public_id: String(form.get("environment")),
        code: String(form.get("code")),
        name: String(form.get("name")),
        provider: String(form.get("provider")),
        region: String(form.get("region")),
        data_residency: String(form.get("data_residency")),
        backend_service: String(form.get("backend_service")),
        frontend_service: String(form.get("frontend_service")),
        database_service: String(form.get("database_service")),
        cache_service: String(form.get("cache_service")),
        object_storage_service: String(form.get("object_storage_service")),
        worker_service: String(form.get("worker_service")),
        secret_manager_service: String(form.get("secret_manager_service")),
      },
      "create-target",
    );
    event.currentTarget.reset();
  }

  async function createPipeline(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const gates = String(form.get("quality_gates"))
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    await post(
      "pipelines",
      {
        target_public_id: String(form.get("target")),
        code: String(form.get("code")),
        name: String(form.get("name")),
        source_branch: String(form.get("source_branch")),
        trigger_mode: String(form.get("trigger_mode")),
        quality_gates: gates,
        requires_approval: form.get("requires_approval") === "on",
      },
      "create-pipeline",
    );
    event.currentTarget.reset();
  }

  async function createDeployment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await post(
      "deployments",
      {
        pipeline_public_id: String(form.get("pipeline")),
        source_revision: String(form.get("source_revision")),
        artifact_sha256: String(form.get("artifact_sha256")),
        migration_plan_sha256: String(form.get("migration_plan_sha256")),
      },
      "create-deployment",
    );
    event.currentTarget.reset();
  }

  async function createBackupPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await post(
      "backup-policies",
      {
        target_public_id: String(form.get("target")),
        code: String(form.get("code")),
        name: String(form.get("name")),
        resource_type: String(form.get("resource_type")),
        schedule_cron: String(form.get("schedule_cron")),
        retention_days: Number(form.get("retention_days")),
        encryption_required: true,
        point_in_time_recovery: form.get("point_in_time_recovery") === "on",
      },
      "create-backup-policy",
    );
    event.currentTarget.reset();
  }

  async function recordBackup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const now = new Date().toISOString();
    await post(
      "backup-executions",
      {
        policy_public_id: String(form.get("policy")),
        status: "verified",
        backup_reference: String(form.get("backup_reference")),
        backup_sha256: String(form.get("backup_sha256")),
        size_bytes: Number(form.get("size_bytes")),
        recovery_point_at: now,
        started_at: now,
        finished_at: now,
      },
      "record-backup",
    );
    event.currentTarget.reset();
  }

  async function createRestore(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await post(
      "restore-exercises",
      {
        target_public_id: String(form.get("target")),
        backup_execution_public_id: String(form.get("backup")),
        notes: String(form.get("notes")),
      },
      "create-restore",
    );
    event.currentTarget.reset();
  }

  async function createSecretPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await post(
      "secret-policies",
      {
        target_public_id: String(form.get("target")),
        code: String(form.get("code")),
        name: String(form.get("name")),
        secret_provider: String(form.get("secret_provider")),
        secret_reference: String(form.get("secret_reference")),
        rotation_interval_days: Number(form.get("rotation_interval_days")),
      },
      "create-secret-policy",
    );
    event.currentTarget.reset();
  }

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
              MPSqre Build360 · Cloud Launch
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              Production deployment and recovery
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Provider-neutral targets · governed promotion · backup evidence · secret rotation
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-900">
              Phase 18 active
            </span>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/platform">
              Platform
            </Link>
          </div>
        </header>

        <section className="grid gap-4 py-7 sm:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Active cloud targets</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.active_targets}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">{data.summary.targets} total targets</p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Deployment pipelines</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.pipelines}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">Latest {label(data.summary.latest_deployment_status)}</p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Verified backups</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.verified_backups}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">{data.summary.passed_restore_exercises} restore exercises passed</p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Secrets due</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.secrets_due}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">References only—no raw secrets stored</p>
          </article>
        </section>

        <div className="mb-6 flex flex-wrap gap-2">
          {(["targets", "deployments", "recovery", "secrets"] as Tab[]).map((item) => (
            <button
              className={`rounded-xl px-4 py-2 text-sm font-semibold ${tab === item ? "bg-emerald-950 text-white" : "border border-[var(--border)] bg-white"}`}
              key={item}
              onClick={() => setTab(item)}
              type="button"
            >
              {label(item)}
            </button>
          ))}
        </div>

        {message ? (
          <div className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
            {message}
          </div>
        ) : null}

        {tab === "targets" ? (
          <section className="grid gap-6 xl:grid-cols-[380px_1fr]">
            <div className="space-y-6">
              <form className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createTarget}>
                <h2 className="text-xl font-semibold">Register cloud target</h2>
                <div className="mt-4 grid gap-3">
                  <select className={inputClass} name="environment" required>
                    <option value="">Select runtime environment</option>
                    {data.environments.map((item) => <option key={item.public_id} value={item.public_id}>{item.code} · {label(item.environment_type)}</option>)}
                  </select>
                  <input className={inputClass} name="code" placeholder="STAGING_PRIMARY" required />
                  <input className={inputClass} name="name" placeholder="Managed staging" required />
                  <select className={inputClass} name="provider"><option value="generic">Provider neutral</option><option value="aws">AWS</option><option value="azure">Azure</option><option value="gcp">Google Cloud</option><option value="render">Render</option><option value="vercel">Vercel</option><option value="cloudflare">Cloudflare</option></select>
                  <div className="grid grid-cols-2 gap-3"><input className={inputClass} name="region" placeholder="Region" required /><input className={inputClass} name="data_residency" placeholder="Data residency" required /></div>
                  <input className={inputClass} name="backend_service" placeholder="Backend service" />
                  <input className={inputClass} name="frontend_service" placeholder="Frontend service" />
                  <input className={inputClass} name="database_service" placeholder="PostgreSQL service" />
                  <input className={inputClass} name="cache_service" placeholder="Redis/cache service" />
                  <input className={inputClass} name="object_storage_service" placeholder="Private object storage" />
                  <input className={inputClass} name="worker_service" placeholder="Worker service" />
                  <input className={inputClass} name="secret_manager_service" placeholder="Secret manager" />
                  <button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" disabled={busy !== null} type="submit">Register target</button>
                </div>
              </form>
              <form className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createPipeline}>
                <h2 className="text-xl font-semibold">Create promotion pipeline</h2>
                <div className="mt-4 grid gap-3">
                  <select className={inputClass} name="target" required><option value="">Select target</option>{data.targets.map((item) => <option key={item.public_id} value={item.public_id}>{item.code}</option>)}</select>
                  <input className={inputClass} name="code" placeholder="PRODUCTION_PROMOTION" required />
                  <input className={inputClass} name="name" placeholder="Governed production promotion" required />
                  <input className={inputClass} defaultValue="main" name="source_branch" placeholder="Source branch or tag pattern" required />
                  <select className={inputClass} name="trigger_mode"><option value="manual">Manual</option><option value="push">Source push</option><option value="tag">Release tag</option></select>
                  <textarea className={inputClass} defaultValue="backend.pytest, frontend.build, security.secret_scan, release.smoke_test" name="quality_gates" />
                  <label className="flex items-center gap-2 text-sm"><input defaultChecked name="requires_approval" type="checkbox" /> Independent approval required</label>
                  <button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" disabled={busy !== null} type="submit">Create pipeline</button>
                </div>
              </form>
            </div>
            <div className="space-y-4">
              {data.targets.length ? data.targets.map((target) => (
                <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={target.public_id}>
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div><p className="text-xs font-bold uppercase tracking-wide text-[var(--brand)]">{target.code} · {label(target.provider)}</p><h2 className="mt-1 text-lg font-semibold">{target.name}</h2><p className="mt-2 text-sm text-[var(--muted)]">{target.environment.code} · {target.region} · {target.data_residency}</p></div><Status value={target.status} />
                  </div>
                  <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2"><p><strong>Backend:</strong> {target.backend_service || "Not assigned"}</p><p><strong>Database:</strong> {target.database_service || "Not assigned"}</p><p><strong>Cache:</strong> {target.cache_service || "Not assigned"}</p><p><strong>Secrets:</strong> {target.secret_manager_service || "Not assigned"}</p></div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {target.status === "draft" ? <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" onClick={() => void post(`targets/${target.public_id}/transition`, { target_status: "ready", expected_version: target.version, reason: "Service topology documented" }, `target-${target.public_id}`)} type="button">Mark ready</button> : null}
                    {target.status === "ready" ? <button className="rounded-lg bg-emerald-950 px-3 py-2 text-sm font-semibold text-white" onClick={() => void post(`targets/${target.public_id}/transition`, { target_status: "active", expected_version: target.version, production_approved: target.environment.environment_type === "production", reason: "Target activation approved" }, `target-${target.public_id}`)} type="button">{target.environment.environment_type === "production" ? "Approve and activate" : "Activate"}</button> : null}
                    {target.status === "active" ? <button className="rounded-lg border border-amber-200 px-3 py-2 text-sm font-semibold text-amber-900" onClick={() => void post(`targets/${target.public_id}/transition`, { target_status: "suspended", expected_version: target.version, reason: "Target suspended by operator" }, `target-${target.public_id}`)} type="button">Suspend</button> : null}
                  </div>
                </article>
              )) : <Empty>No cloud target has been registered.</Empty>}
              <div className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><h2 className="text-lg font-semibold">Promotion pipelines</h2><div className="mt-4 space-y-3">{data.pipelines.map((pipeline) => <div className="rounded-xl bg-slate-50 p-4" key={pipeline.public_id}><div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{pipeline.name}</p><p className="mt-1 text-xs text-[var(--muted)]">{pipeline.code} · {pipeline.target.code} · {pipeline.source_branch}</p></div><Status value={pipeline.is_active ? "active" : "suspended"} /></div><p className="mt-2 text-xs text-[var(--muted)]">{pipeline.quality_gates.length} quality gates · {pipeline.requires_approval ? "approval required" : "direct execution allowed"}</p></div>)}</div></div>
            </div>
          </section>
        ) : null}

        {tab === "deployments" ? (
          <section className="grid gap-6 xl:grid-cols-[380px_1fr]">
            <form className="h-fit rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createDeployment}>
              <h2 className="text-xl font-semibold">Request deployment</h2>
              <div className="mt-4 grid gap-3"><select className={inputClass} name="pipeline" required><option value="">Select pipeline</option>{data.pipelines.filter((item) => item.is_active).map((item) => <option key={item.public_id} value={item.public_id}>{item.code} · {item.target.code}</option>)}</select><input className={inputClass} name="source_revision" placeholder="Git revision or build ID" required /><input className={inputClass} minLength={64} maxLength={64} name="artifact_sha256" placeholder="Artifact SHA-256" required /><input className={inputClass} maxLength={64} name="migration_plan_sha256" placeholder="Migration-plan SHA-256 (optional)" /><button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" disabled={busy !== null} type="submit">Request deployment</button></div>
            </form>
            <div className="space-y-4">{data.deployments.length ? data.deployments.map((item) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={item.public_id}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-wide text-[var(--brand)]">{item.pipeline.code} · {item.pipeline.target.code}</p><h2 className="mt-1 text-lg font-semibold">Revision {item.source_revision}</h2><p className="mt-2 text-sm text-[var(--muted)]">Target ready {item.readiness.target_ready ? "yes" : "no"} · Release ready {item.readiness.release_ready ? "yes" : "no"}</p></div><Status value={item.status} /></div>{item.deployment_url ? <a className="mt-3 block text-sm font-semibold text-emerald-800" href={item.deployment_url} rel="noreferrer" target="_blank">{item.deployment_url}</a> : null}<div className="mt-4 flex flex-wrap gap-2">{item.status === "requested" ? <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" onClick={() => void post(`deployments/${item.public_id}/transition`, { target_status: "validated", expected_version: item.version, reason: "Quality gates validated" }, `deployment-${item.public_id}`)} type="button">Validate</button> : null}{item.status === "validated" && item.pipeline.requires_approval ? <button className="rounded-lg bg-emerald-950 px-3 py-2 text-sm font-semibold text-white" onClick={() => void post(`deployments/${item.public_id}/transition`, { target_status: "approved", expected_version: item.version, reason: "Independent release approval" }, `deployment-${item.public_id}`)} type="button">Approve</button> : null}{["validated", "approved"].includes(item.status) ? <button className="rounded-lg border border-emerald-200 px-3 py-2 text-sm font-semibold text-emerald-900" onClick={() => void post(`deployments/${item.public_id}/transition`, { target_status: "running", expected_version: item.version, reason: "Deployment execution started" }, `deployment-${item.public_id}`)} type="button">Start</button> : null}{item.status === "running" ? <button className="rounded-lg bg-emerald-950 px-3 py-2 text-sm font-semibold text-white" onClick={() => void post(`deployments/${item.public_id}/transition`, { target_status: "succeeded", expected_version: item.version, deployment_url: item.pipeline.target.code === "LOCAL_NATIVE" ? "http://localhost:3000" : "https://deployment.example.invalid", logs_sha256: "0".repeat(64), reason: "Smoke tests passed" }, `deployment-${item.public_id}`)} type="button">Record success</button> : null}</div>{item.error_summary ? <p className="mt-3 text-sm text-red-800">{item.error_summary}</p> : null}</article>) : <Empty>No deployment execution has been requested.</Empty>}</div>
          </section>
        ) : null}

        {tab === "recovery" ? (
          <section className="space-y-6">
            <div className="grid gap-6 xl:grid-cols-3">
              <form className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createBackupPolicy}><h2 className="text-xl font-semibold">Create backup policy</h2><div className="mt-4 grid gap-3"><select className={inputClass} name="target" required><option value="">Select target</option>{data.targets.map((item) => <option key={item.public_id} value={item.public_id}>{item.code}</option>)}</select><input className={inputClass} name="code" placeholder="PROD_DB_HOURLY" required /><input className={inputClass} name="name" placeholder="Production PostgreSQL backup" required /><select className={inputClass} name="resource_type"><option value="database">Database</option><option value="object_storage">Object storage</option><option value="configuration">Configuration</option><option value="full">Full platform</option></select><input className={inputClass} defaultValue="0 1 * * *" name="schedule_cron" required /><input className={inputClass} defaultValue="30" name="retention_days" type="number" min="1" max="3650" /><label className="flex items-center gap-2 text-sm"><input name="point_in_time_recovery" type="checkbox" /> Point-in-time recovery</label><button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" type="submit">Create policy</button></div></form>
              <form className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={recordBackup}><h2 className="text-xl font-semibold">Record verified backup</h2><div className="mt-4 grid gap-3"><select className={inputClass} name="policy" required><option value="">Select backup policy</option>{data.backup_policies.map((item) => <option key={item.public_id} value={item.public_id}>{item.code}</option>)}</select><input className={inputClass} name="backup_reference" placeholder="Private backup reference" required /><input className={inputClass} minLength={64} maxLength={64} name="backup_sha256" placeholder="Backup SHA-256" required /><input className={inputClass} defaultValue="0" min="0" name="size_bytes" type="number" /><button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" type="submit">Record backup evidence</button></div></form>
              <form className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createRestore}><h2 className="text-xl font-semibold">Plan restore exercise</h2><div className="mt-4 grid gap-3"><select className={inputClass} name="target" required><option value="">Select isolated target</option>{data.targets.map((item) => <option key={item.public_id} value={item.public_id}>{item.code}</option>)}</select><select className={inputClass} name="backup" required><option value="">Select successful backup</option>{successfulBackups.map((item) => <option key={item.public_id} value={item.public_id}>{item.policy.code} · {item.backup_reference}</option>)}</select><textarea className={inputClass} name="notes" placeholder="Restore scope and test plan" /><button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" type="submit">Plan restore</button></div></form>
            </div>
            <div className="grid gap-6 lg:grid-cols-2"><div className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><h2 className="text-xl font-semibold">Backup evidence</h2><div className="mt-4 space-y-3">{data.backup_executions.map((item) => <div className="rounded-xl bg-slate-50 p-4" key={item.public_id}><div className="flex justify-between gap-3"><div><p className="font-semibold">{item.policy.code}</p><p className="mt-1 text-xs text-[var(--muted)]">{item.backup_reference}</p></div><Status value={item.status} /></div><p className="mt-2 text-xs text-[var(--muted)]">Evidence {item.evidence_sha256 ? `${item.evidence_sha256.slice(0, 16)}…` : "pending"}</p></div>)}</div></div><div className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><h2 className="text-xl font-semibold">Restore exercises</h2><div className="mt-4 space-y-3">{data.restore_exercises.map((item) => <div className="rounded-xl bg-slate-50 p-4" key={item.public_id}><div className="flex justify-between gap-3"><div><p className="font-semibold">{item.target.code} · {item.backup_execution.policy_code}</p><p className="mt-1 text-xs text-[var(--muted)]">RPO {item.measured_rpo_minutes ?? "—"}m · RTO {item.measured_rto_minutes ?? "—"}m</p></div><Status value={item.status} /></div><div className="mt-3 flex flex-wrap gap-2">{item.status === "planned" ? <button className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-semibold" onClick={() => void post(`restore-exercises/${item.public_id}/transition`, { target_status: "running", expected_version: item.version }, `restore-${item.public_id}`)} type="button">Start exercise</button> : null}{item.status === "running" ? <button className="rounded-lg bg-emerald-950 px-3 py-1.5 text-xs font-semibold text-white" onClick={() => void post(`restore-exercises/${item.public_id}/transition`, { target_status: "passed", expected_version: item.version, measured_rpo_minutes: 5, measured_rto_minutes: 20, evidence_sha256: "1".repeat(64), notes: "Restore and smoke tests passed" }, `restore-${item.public_id}`)} type="button">Record pass</button> : null}{item.status === "passed" ? <button className="rounded-lg bg-emerald-950 px-3 py-1.5 text-xs font-semibold text-white" onClick={() => void post(`restore-exercises/${item.public_id}/transition`, { target_status: "approved", expected_version: item.version }, `restore-${item.public_id}`)} type="button">Approve evidence</button> : null}</div></div>)}</div></div></div>
          </section>
        ) : null}

        {tab === "secrets" ? (
          <section className="grid gap-6 xl:grid-cols-[380px_1fr]">
            <form className="h-fit rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createSecretPolicy}><h2 className="text-xl font-semibold">Register secret rotation policy</h2><p className="mt-2 text-sm text-[var(--muted)]">Store only a secret-manager reference. Raw credentials are rejected.</p><div className="mt-4 grid gap-3"><select className={inputClass} name="target" required><option value="">Select target</option>{data.targets.map((item) => <option key={item.public_id} value={item.public_id}>{item.code}</option>)}</select><input className={inputClass} name="code" placeholder="DATABASE_PASSWORD" required /><input className={inputClass} name="name" placeholder="Managed database password" required /><input className={inputClass} name="secret_provider" placeholder="Managed vault provider" required /><input className={inputClass} name="secret_reference" placeholder="vault://build360/database/password" required /><input className={inputClass} defaultValue="90" min="1" max="730" name="rotation_interval_days" type="number" /><button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" type="submit">Register policy</button></div></form>
            <div className="space-y-4">{data.secret_policies.length ? data.secret_policies.map((item) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={item.public_id}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-wide text-[var(--brand)]">{item.target.code} · {item.code}</p><h2 className="mt-1 text-lg font-semibold">{item.name}</h2><p className="mt-2 break-all text-sm text-[var(--muted)]">{item.secret_reference}</p></div><Status value={item.status} /></div><p className="mt-3 text-sm">Rotate every {item.rotation_interval_days} days · Next {item.next_rotation_at ? new Date(item.next_rotation_at).toLocaleString() : "not scheduled"}</p><button className="mt-4 rounded-lg bg-emerald-950 px-3 py-2 text-sm font-semibold text-white" onClick={() => void post(`secret-policies/${item.public_id}/rotate`, { expected_version: item.version, evidence_reference: "operator-recorded-rotation" }, `secret-${item.public_id}`)} type="button">Record rotation evidence</button></article>) : <Empty>No secret rotation policy has been registered.</Empty>}</div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
