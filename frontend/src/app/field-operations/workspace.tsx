"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

export type LabourSummary = {
  active_workers: number;
  active_allocations: number;
  attendance_records: number;
  regular_hours: string | number;
  overtime_hours: string | number;
};
export type EquipmentSummary = {
  assets: number;
  allocated: number;
  open_maintenance: number;
};
export type QualitySummary = {
  templates: number;
  inspections: number;
  pending_inspections: number;
  open_ncrs: number;
  overdue_ncrs: number;
};
export type SafetySummary = {
  incidents: number;
  open_incidents: number;
  critical_incidents: number;
  observations: number;
  open_actions: number;
};
export type FieldSyncSummary = {
  offline_operations: number;
  pending_operations: number;
  open_conflicts: number;
  approved_operation_types: string[];
};
export type Worker = {
  public_id: string;
  code: string;
  display_name: string;
  worker_type: string;
  trade_code: string;
  daily_rate: string;
  currency: string;
};
export type EquipmentAsset = {
  public_id: string;
  code: string;
  name: string;
  category_code: string;
  current_meter: string;
  meter_unit: string;
  stage: { name: string };
};
export type Inspection = {
  public_id: string;
  inspection_number: string;
  title: string;
  project: { code: string; name: string };
  stage: { name: string };
  overall_result: string;
};
export type SafetyIncident = {
  public_id: string;
  incident_number: string;
  title: string;
  severity: string;
  project: { code: string; name: string };
  stage: { name: string };
};

type Project = { public_id: string; code: string; name: string };
type Company = {
  public_id: string;
  code: string;
  display_name: string;
  currency: string;
  timezone: string;
};
type Props = {
  company: Company;
  permissions: string[];
  initialLabourSummary: LabourSummary | null;
  initialEquipmentSummary: EquipmentSummary | null;
  initialQualitySummary: QualitySummary | null;
  initialSafetySummary: SafetySummary | null;
  initialSyncSummary: FieldSyncSummary | null;
  initialWorkers: Worker[];
  initialAssets: EquipmentAsset[];
  initialInspections: Inspection[];
  initialIncidents: SafetyIncident[];
  projects: Project[];
};
type ApiError = { message?: string; detail?: string };
type Scope = "labour" | "equipment" | "quality" | "safety" | "sync";

async function api<T>(scope: Scope, path: string, init?: RequestInit) {
  const response = await fetch(`/api/field/${scope}/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = (await response.json().catch(() => ({}))) as T & ApiError;
  if (!response.ok) {
    throw new Error(body.message ?? body.detail ?? "The operation could not be completed.");
  }
  return body as T;
}

function Card({ label, value }: { label: string; value: string | number }) {
  return (
    <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
      <p className="text-sm text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
    </article>
  );
}

export function FieldOperationsWorkspace(props: Readonly<Props>) {
  const { company, permissions, projects } = props;
  const [tab, setTab] = useState<"labour" | "equipment" | "quality" | "safety" | "offline">(
    "labour",
  );
  const [workers, setWorkers] = useState(props.initialWorkers);
  const [assets, setAssets] = useState(props.initialAssets);
  const [inspections, setInspections] = useState(props.initialInspections);
  const [incidents, setIncidents] = useState(props.initialIncidents);
  const [labourSummary, setLabourSummary] = useState(
    props.initialLabourSummary ?? {
      active_workers: 0,
      active_allocations: 0,
      attendance_records: 0,
      regular_hours: 0,
      overtime_hours: 0,
    },
  );
  const [equipmentSummary, setEquipmentSummary] = useState(
    props.initialEquipmentSummary ?? { assets: 0, allocated: 0, open_maintenance: 0 },
  );
  const [qualitySummary, setQualitySummary] = useState(
    props.initialQualitySummary ?? {
      templates: 0,
      inspections: 0,
      pending_inspections: 0,
      open_ncrs: 0,
      overdue_ncrs: 0,
    },
  );
  const [safetySummary, setSafetySummary] = useState(
    props.initialSafetySummary ?? {
      incidents: 0,
      open_incidents: 0,
      critical_incidents: 0,
      observations: 0,
      open_actions: 0,
    },
  );
  const syncSummary = props.initialSyncSummary ?? {
    offline_operations: 0,
    pending_operations: 0,
    open_conflicts: 0,
    approved_operation_types: [],
  };
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refresh() {
    const [labour, equipment, quality, safety, workerList, assetList, inspectionList, incidentList] =
      await Promise.all([
        api<LabourSummary>("labour", "summary"),
        api<EquipmentSummary>("equipment", "summary"),
        api<QualitySummary>("quality", "summary"),
        api<SafetySummary>("safety", "summary"),
        api<{ items: Worker[] }>("labour", "workers"),
        api<{ items: EquipmentAsset[] }>("equipment", "assets"),
        api<{ items: Inspection[] }>("quality", "inspections"),
        api<{ items: SafetyIncident[] }>("safety", "incidents"),
      ]);
    setLabourSummary(labour);
    setEquipmentSummary(equipment);
    setQualitySummary(quality);
    setSafetySummary(safety);
    setWorkers(workerList.items);
    setAssets(assetList.items);
    setInspections(inspectionList.items);
    setIncidents(incidentList.items);
  }

  async function run(action: () => Promise<void>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh();
      setNotice(message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The operation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createWorker(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api("labour", "workers", {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          display_name: form.get("display_name"),
          worker_type: form.get("worker_type"),
          trade_code: form.get("trade_code"),
          joined_on: form.get("joined_on"),
          currency: company.currency,
          daily_rate: form.get("daily_rate") || "0",
          skill_codes: String(form.get("skill_codes") || "")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
        }),
      });
      event.currentTarget.reset();
    }, "Worker profile created with tenant-safe trade and rate controls.");
  }

  async function createEquipment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api("equipment", "assets", {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          name: form.get("name"),
          category_code: form.get("category_code"),
          ownership_type: form.get("ownership_type"),
          currency: company.currency,
          hourly_cost: form.get("hourly_cost") || "0",
          meter_unit: form.get("meter_unit") || "hours",
        }),
      });
      event.currentTarget.reset();
    }, "Equipment asset created with lifecycle and meter controls.");
  }

  async function createInspectionTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      const checklist = String(form.get("checklist") || "")
        .split("\n")
        .map((label, index) => ({ code: `item_${index + 1}`, label: label.trim(), required: true }))
        .filter((item) => item.label);
      await api("quality", "templates", {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          name: form.get("name"),
          discipline_code: form.get("discipline_code"),
          checklist,
        }),
      });
      event.currentTarget.reset();
    }, "Inspection template created with versioned checklist content.");
  }

  async function reportIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api("safety", "incidents", {
        method: "POST",
        body: JSON.stringify({
          project_public_id: form.get("project_public_id"),
          incident_number: form.get("incident_number"),
          title: form.get("title"),
          description: form.get("description"),
          severity: form.get("severity"),
          occurred_at: form.get("occurred_at"),
          immediate_actions: form.get("immediate_actions") || "",
        }),
      });
      event.currentTarget.reset();
    }, "Safety incident reported with immutable audit evidence.");
  }

  const tabs = [
    ["labour", "Labour"],
    ["equipment", "Equipment"],
    ["quality", "Quality"],
    ["safety", "Safety"],
    ["offline", "Offline sync"],
  ] as const;

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
              MPSqre Build360 · Field operations
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              Labour, equipment, quality and safety
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {company.display_name} · {company.code} · {company.timezone}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <span className="rounded-full bg-emerald-50 px-3 py-2 text-xs font-semibold uppercase text-emerald-900">
              Phase 7 active
            </span>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/supply">
              Supply
            </Link>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/delivery">
              Delivery
            </Link>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/platform">
              Platform
            </Link>
          </div>
        </header>

        {(error || notice) && (
          <div className={`mt-5 rounded-xl border p-4 text-sm ${error ? "border-red-200 bg-red-50 text-red-800" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`}>
            {error || notice}
          </div>
        )}

        <section className="grid gap-4 py-7 sm:grid-cols-2 xl:grid-cols-6">
          <Card label="Active workers" value={labourSummary.active_workers} />
          <Card label="Attendance records" value={labourSummary.attendance_records} />
          <Card label="Equipment assets" value={equipmentSummary.assets} />
          <Card label="Open maintenance" value={equipmentSummary.open_maintenance} />
          <Card label="Open NCRs" value={qualitySummary.open_ncrs} />
          <Card label="Open incidents" value={safetySummary.open_incidents} />
        </section>

        <nav className="mb-6 flex gap-2 overflow-x-auto">
          {tabs.map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === id ? "bg-[var(--brand)] text-white" : "border border-[var(--border)] bg-white"}`}
            >
              {label}
            </button>
          ))}
        </nav>

        {tab === "labour" && (
          <section className="grid gap-6 lg:grid-cols-[380px_1fr]">
            <form onSubmit={createWorker} className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Create worker profile</h2>
              <div className="mt-5 grid gap-4">
                <input name="code" required placeholder="Worker code" />
                <input name="display_name" required placeholder="Worker name" />
                <select name="worker_type" defaultValue="contract">
                  <option value="employee">Employee</option>
                  <option value="contract">Contract labour</option>
                  <option value="subcontract">Subcontract labour</option>
                </select>
                <input name="trade_code" required placeholder="Trade, e.g. masonry" />
                <input name="skill_codes" placeholder="Skills, comma separated" />
                <input name="daily_rate" type="number" min="0" step="0.01" placeholder="Daily rate" />
                <input name="joined_on" required type="date" />
                <button disabled={busy || !permissions.includes("labour.worker.manage")} className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white">
                  Create worker
                </button>
              </div>
            </form>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Worker register</h2>
              <div className="mt-4 divide-y divide-[var(--border)]">
                {workers.map((worker) => (
                  <div key={worker.public_id} className="flex items-center justify-between gap-4 py-4">
                    <div>
                      <p className="font-semibold">{worker.code} · {worker.display_name}</p>
                      <p className="text-sm text-[var(--muted)]">{worker.worker_type} · {worker.trade_code}</p>
                    </div>
                    <span className="text-xs font-semibold uppercase text-[var(--brand)]">{worker.currency} {worker.daily_rate}</span>
                  </div>
                ))}
                {!workers.length && <p className="py-5 text-sm text-[var(--muted)]">No workers created.</p>}
              </div>
            </article>
          </section>
        )}

        {tab === "equipment" && (
          <section className="grid gap-6 lg:grid-cols-[380px_1fr]">
            <form onSubmit={createEquipment} className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Register equipment</h2>
              <div className="mt-5 grid gap-4">
                <input name="code" required placeholder="Equipment code" />
                <input name="name" required placeholder="Equipment name" />
                <input name="category_code" required placeholder="Category" />
                <select name="ownership_type" defaultValue="owned">
                  <option value="owned">Owned</option>
                  <option value="leased">Leased</option>
                  <option value="hired">Hired</option>
                </select>
                <input name="hourly_cost" type="number" min="0" step="0.01" placeholder="Hourly cost" />
                <input name="meter_unit" defaultValue="hours" placeholder="Meter unit" />
                <button disabled={busy || !permissions.includes("equipment.asset.manage")} className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white">
                  Create equipment
                </button>
              </div>
            </form>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Equipment register</h2>
              <div className="mt-4 divide-y divide-[var(--border)]">
                {assets.map((asset) => (
                  <div key={asset.public_id} className="flex items-center justify-between gap-4 py-4">
                    <div>
                      <p className="font-semibold">{asset.code} · {asset.name}</p>
                      <p className="text-sm text-[var(--muted)]">{asset.category_code} · {asset.current_meter} {asset.meter_unit}</p>
                    </div>
                    <span className="text-xs font-semibold uppercase text-[var(--brand)]">{asset.stage.name}</span>
                  </div>
                ))}
                {!assets.length && <p className="py-5 text-sm text-[var(--muted)]">No equipment registered.</p>}
              </div>
            </article>
          </section>
        )}

        {tab === "quality" && (
          <section className="grid gap-6 lg:grid-cols-[420px_1fr]">
            <form onSubmit={createInspectionTemplate} className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Create inspection template</h2>
              <div className="mt-5 grid gap-4">
                <input name="code" required placeholder="Template code" />
                <input name="name" required placeholder="Template name" />
                <input name="discipline_code" required placeholder="Discipline" />
                <textarea name="checklist" required rows={6} placeholder={"Checklist item 1\nChecklist item 2\nChecklist item 3"} />
                <button disabled={busy || !permissions.includes("quality.template.manage")} className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white">
                  Create template
                </button>
              </div>
            </form>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Inspection register</h2>
                <span className="text-sm text-[var(--muted)]">{qualitySummary.pending_inspections} pending</span>
              </div>
              <div className="mt-4 divide-y divide-[var(--border)]">
                {inspections.map((inspection) => (
                  <div key={inspection.public_id} className="flex items-center justify-between gap-4 py-4">
                    <div>
                      <p className="font-semibold">{inspection.inspection_number} · {inspection.title}</p>
                      <p className="text-sm text-[var(--muted)]">{inspection.project.code} · {inspection.project.name}</p>
                    </div>
                    <span className="text-xs font-semibold uppercase text-[var(--brand)]">{inspection.stage.name}</span>
                  </div>
                ))}
                {!inspections.length && <p className="py-5 text-sm text-[var(--muted)]">No inspections scheduled.</p>}
              </div>
            </article>
          </section>
        )}

        {tab === "safety" && (
          <section className="grid gap-6 lg:grid-cols-[420px_1fr]">
            <form onSubmit={reportIncident} className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Report safety incident</h2>
              <div className="mt-5 grid gap-4">
                <select name="project_public_id" required defaultValue="">
                  <option value="" disabled>Select project</option>
                  {projects.map((project) => <option key={project.public_id} value={project.public_id}>{project.code} · {project.name}</option>)}
                </select>
                <input name="incident_number" required placeholder="Incident number" />
                <input name="title" required placeholder="Incident title" />
                <textarea name="description" required rows={4} placeholder="What happened?" />
                <select name="severity" defaultValue="near_miss">
                  <option value="near_miss">Near miss</option>
                  <option value="minor">Minor</option>
                  <option value="major">Major</option>
                  <option value="critical">Critical</option>
                  <option value="fatal">Fatal</option>
                </select>
                <input name="occurred_at" required type="datetime-local" />
                <textarea name="immediate_actions" rows={3} placeholder="Immediate actions taken" />
                <button disabled={busy || !permissions.includes("safety.incident.report")} className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white">
                  Report incident
                </button>
              </div>
            </form>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Incident register</h2>
                <span className="text-sm text-[var(--muted)]">{safetySummary.critical_incidents} critical</span>
              </div>
              <div className="mt-4 divide-y divide-[var(--border)]">
                {incidents.map((incident) => (
                  <div key={incident.public_id} className="flex items-center justify-between gap-4 py-4">
                    <div>
                      <p className="font-semibold">{incident.incident_number} · {incident.title}</p>
                      <p className="text-sm text-[var(--muted)]">{incident.project.code} · {incident.project.name}</p>
                    </div>
                    <span className="text-xs font-semibold uppercase text-[var(--brand)]">{incident.severity} · {incident.stage.name}</span>
                  </div>
                ))}
                {!incidents.length && <p className="py-5 text-sm text-[var(--muted)]">No incidents reported.</p>}
              </div>
            </article>
          </section>
        )}

        {tab === "offline" && (
          <section className="grid gap-6 lg:grid-cols-3">
            <Card label="Offline operations" value={syncSummary.offline_operations} />
            <Card label="Pending operations" value={syncSummary.pending_operations} />
            <Card label="Open conflicts" value={syncSummary.open_conflicts} />
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm lg:col-span-3">
              <h2 className="text-xl font-semibold">Approved offline workflows</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Only explicitly approved, idempotent operations can be queued. Financial, access-control, deletion and workflow-approval actions remain online-only.
              </p>
              <ul className="mt-5 grid gap-3 md:grid-cols-2">
                {syncSummary.approved_operation_types.map((operation) => (
                  <li key={operation} className="rounded-xl border border-[var(--border)] p-4 font-mono text-sm">{operation}</li>
                ))}
              </ul>
            </article>
          </section>
        )}
      </div>
    </main>
  );
}
