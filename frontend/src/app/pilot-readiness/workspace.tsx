"use client";

import { useMemo, useState } from "react";

type Program = {
  public_id: string;
  cohort_code: string;
  name: string;
  status: string;
  owner: { display_name: string; email: string };
  target_start_date: string | null;
  target_go_live_at: string | null;
  actual_go_live_at: string | null;
  version: number;
};

type ChecklistItem = {
  public_id: string;
  code: string;
  category: string;
  title: string;
  description: string;
  is_required: boolean;
  status: string;
  due_at: string | null;
  completed_at: string | null;
  evidence: Record<string, unknown>;
  waiver_reason: string;
  version: number;
};

type MasterDataItem = {
  public_id: string;
  domain_code: string;
  domain_name: string;
  minimum_records: number;
  current_records: number;
  is_required: boolean;
  status: string;
  last_validated_at: string | null;
};

type TrainingModule = {
  public_id: string;
  code: string;
  title: string;
  description: string;
  audience_codes: string[];
  is_required: boolean;
  status: string;
};

type TrainingCompletion = {
  public_id: string;
  module_public_id: string;
  module_code: string;
  module_title: string;
  membership_public_id: string;
  user: { email: string; display_name: string };
  status: string;
  score_percent: string | null;
  completed_at: string | null;
  version: number;
};

type Signoff = {
  public_id: string;
  code: string;
  area: string;
  title: string;
  is_required: boolean;
  status: string;
  signer: { display_name: string } | null;
  signed_at: string | null;
  reason: string;
  version: number;
};

type GoLivePlan = {
  public_id: string;
  target_at: string | null;
  cutover_window_minutes: number;
  support_window_hours: number;
  rollback_reference: string;
  cutover_steps: Array<{ sequence: number; code: string; title: string }>;
  status: string;
  version: number;
  signoffs: Signoff[];
};

type Assessment = {
  public_id: string;
  assessed_at: string;
  score_percent: number;
  critical_blockers: Array<{ type: string; code: string; title: string }>;
  warnings: Array<{ type: string; code: string; title: string }>;
  checksum_sha256: string;
};

type Adoption = {
  public_id: string;
  period_start: string;
  period_end: string;
  active_users: number;
  total_users: number;
  training_completion_percent: string;
  completed_checklist_items: number;
  total_checklist_items: number;
  key_activity_count: number;
};

export type PilotPortfolio = {
  program: Program | null;
  readiness?: {
    score_percent: number;
    ready: boolean;
    checklist: { completed: number; total: number };
    master_data: { ready: number; total: number };
    training: { completed: number; total: number };
    signoffs: { approved: number; total: number };
    critical_blockers: Array<{ type: string; code: string; title: string }>;
    warnings: Array<{ type: string; code: string; title: string }>;
  };
  checklist?: ChecklistItem[];
  master_data?: MasterDataItem[];
  training_modules?: TrainingModule[];
  training_completions?: TrainingCompletion[];
  latest_assessment?: Assessment | null;
  go_live_plan?: GoLivePlan | null;
  adoption?: Adoption[];
};

type Tab = "checklist" | "master" | "training" | "go-live" | "adoption";

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function Status({ value }: Readonly<{ value: string }>) {
  const positive = ["ready", "completed", "approved", "live", "published"].includes(value);
  const negative = ["blocked", "rejected", "rolled_back", "cancelled"].includes(value);
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

export function PilotReadinessWorkspace({ initialData }: Readonly<{ initialData: PilotPortfolio }>) {
  const [data, setData] = useState(initialData);
  const [tab, setTab] = useState<Tab>("checklist");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const checklist = useMemo(() => data.checklist ?? [], [data.checklist]);
  const master = data.master_data ?? [];
  const training = data.training_completions ?? [];
  const plan = data.go_live_plan ?? null;
  const readiness = data.readiness;
  const progress = readiness?.score_percent ?? 0;

  const groupedChecklist = useMemo(() => {
    const grouped = new Map<string, ChecklistItem[]>();
    for (const item of checklist) {
      grouped.set(item.category, [...(grouped.get(item.category) ?? []), item]);
    }
    return [...grouped.entries()];
  }, [checklist]);

  async function refresh() {
    const response = await fetch("/api/pilotops/portfolio", { cache: "no-store" });
    if (response.ok) setData((await response.json()) as PilotPortfolio);
  }

  async function post(path: string, body: Record<string, unknown>, key: string) {
    setBusy(key);
    setMessage(null);
    const response = await fetch(`/api/pilotops/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = (await response.json().catch(() => ({}))) as { message?: string; detail?: string };
    if (!response.ok) {
      setMessage(result.message ?? result.detail ?? "The action could not be completed.");
    } else {
      setMessage("Action completed successfully.");
      await refresh();
    }
    setBusy(null);
  }

  if (!data.program) {
    return (
      <main className="min-h-screen px-5 py-8 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-5xl rounded-3xl border border-[var(--border)] bg-white p-8 shadow-sm">
          <p className="text-sm font-bold uppercase tracking-[0.16em] text-[var(--brand)]">MPSqre Build360</p>
          <h1 className="mt-3 text-3xl font-semibold">Pilot operations</h1>
          <p className="mt-4 text-[var(--muted)]">Run the Phase 16 initializer to create the governed pilot programme.</p>
        </div>
      </main>
    );
  }

  const program = data.program;
  return (
    <main className="min-h-screen px-4 py-6 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-7xl">
        <header className="border-b border-[var(--border)] pb-6">
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-[var(--brand)]">MPSqre Build360 · Pilot Operations</p>
          <div className="mt-3 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Pilot launch and go-live readiness</h1>
              <p className="mt-2 text-sm text-[var(--muted)]">{program.name} · {program.cohort_code} · Owner: {program.owner.display_name}</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Status value={program.status} />
              <span className="rounded-full bg-emerald-950 px-4 py-2 text-sm font-semibold text-white">Phase 16 active</span>
            </div>
          </div>
        </header>

        {message ? <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">{message}</div> : null}

        <section className="grid gap-4 py-6 sm:grid-cols-2 xl:grid-cols-5">
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm xl:col-span-1">
            <p className="text-sm text-[var(--muted)]">Readiness score</p>
            <p className="mt-2 text-4xl font-semibold">{progress}%</p>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-emerald-700" style={{ width: `${progress}%` }} /></div>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-sm text-[var(--muted)]">Checklist</p><p className="mt-2 text-3xl font-semibold">{readiness?.checklist.completed ?? 0}/{readiness?.checklist.total ?? 0}</p></article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-sm text-[var(--muted)]">Master data</p><p className="mt-2 text-3xl font-semibold">{readiness?.master_data.ready ?? 0}/{readiness?.master_data.total ?? 0}</p></article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-sm text-[var(--muted)]">Training</p><p className="mt-2 text-3xl font-semibold">{readiness?.training.completed ?? 0}/{readiness?.training.total ?? 0}</p></article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-sm text-[var(--muted)]">Sign-offs</p><p className="mt-2 text-3xl font-semibold">{readiness?.signoffs.approved ?? 0}/{readiness?.signoffs.total ?? 0}</p></article>
        </section>

        <div className="mb-5 flex gap-2 overflow-x-auto pb-1">
          {([[
            "checklist", "Checklist"], ["master", "Master data"], ["training", "Training"], ["go-live", "Go-live"], ["adoption", "Adoption"]] as const).map(([key, title]) => (
            <button key={key} className={`whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-semibold ${tab === key ? "bg-emerald-950 text-white" : "border border-[var(--border)] bg-white"}`} onClick={() => setTab(key)} type="button">{title}</button>
          ))}
        </div>

        {tab === "checklist" ? (
          <section className="space-y-5">
            {groupedChecklist.map(([category, items]) => (
              <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={category}>
                <h2 className="text-xl font-semibold">{label(category)}</h2>
                <div className="mt-4 divide-y divide-[var(--border)]">
                  {items.map((item) => (
                    <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between" key={item.public_id}>
                      <div><div className="flex flex-wrap items-center gap-2"><p className="font-semibold">{item.title}</p>{item.is_required ? <span className="text-xs font-semibold text-red-700">Required</span> : null}</div><p className="mt-1 text-sm text-[var(--muted)]">{item.code}{item.due_at ? ` · Due ${new Date(item.due_at).toLocaleDateString()}` : ""}</p></div>
                      <div className="flex flex-wrap items-center gap-2"><Status value={item.status} />{item.status !== "completed" ? <button className="rounded-lg bg-[var(--brand)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={busy === item.public_id} onClick={() => void post(`checklist/${item.public_id}/transition`, { status: "completed", expected_version: item.version, evidence: { source: "pilot_workspace" } }, item.public_id)} type="button">Complete</button> : null}</div>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </section>
        ) : null}

        {tab === "master" ? (
          <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-xl font-semibold">Master-data readiness</h2><p className="mt-1 text-sm text-[var(--muted)]">Validate minimum pilot records against the live tenant database.</p></div><button className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={busy === "master"} onClick={() => void post(`programs/${program.public_id}/validate-master-data`, {}, "master")} type="button">Validate all</button></div>
            <div className="mt-5 grid gap-3 md:grid-cols-2">{master.map((item) => <article className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}><div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{item.domain_name}</p><p className="mt-1 text-sm text-[var(--muted)]">{item.current_records} records · minimum {item.minimum_records}</p></div><Status value={item.status} /></div></article>)}</div>
          </section>
        ) : null}

        {tab === "training" ? (
          <section className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><h2 className="text-xl font-semibold">Training catalogue</h2><div className="mt-4 space-y-3">{(data.training_modules ?? []).map((item) => <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}><div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{item.title}</p><p className="mt-1 text-xs uppercase text-[var(--muted)]">{item.code}</p></div><Status value={item.status} /></div></div>)}</div></article>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><h2 className="text-xl font-semibold">Assignments</h2><div className="mt-4 divide-y divide-[var(--border)]">{training.map((item) => <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between" key={item.public_id}><div><p className="font-semibold">{item.module_title}</p><p className="mt-1 text-sm text-[var(--muted)]">{item.user.display_name} · {item.user.email}</p></div><div className="flex items-center gap-2"><Status value={item.status} />{item.status !== "completed" ? <button className="rounded-lg bg-[var(--brand)] px-3 py-2 text-sm font-semibold text-white" onClick={() => void post(`training/${item.public_id}/complete`, { status: "completed", expected_version: item.version, score_percent: "100", evidence: { source: "self_attestation" } }, item.public_id)} type="button">Complete</button> : null}</div></div>)}</div></article>
          </section>
        ) : null}

        {tab === "go-live" && plan ? (
          <section className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><div className="flex items-center justify-between gap-3"><h2 className="text-xl font-semibold">Cutover plan</h2><Status value={plan.status} /></div><dl className="mt-5 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-[var(--muted)]">Target</dt><dd className="mt-1 font-semibold">{plan.target_at ? new Date(plan.target_at).toLocaleString() : "Not set"}</dd></div><div><dt className="text-[var(--muted)]">Window</dt><dd className="mt-1 font-semibold">{plan.cutover_window_minutes} minutes</dd></div><div><dt className="text-[var(--muted)]">Hypercare</dt><dd className="mt-1 font-semibold">{plan.support_window_hours} hours</dd></div><div><dt className="text-[var(--muted)]">Version</dt><dd className="mt-1 font-semibold">v{plan.version}</dd></div></dl><ol className="mt-5 space-y-2">{plan.cutover_steps.map((step) => <li className="rounded-lg bg-slate-50 px-3 py-2 text-sm" key={step.code}>{step.sequence}. {step.title}</li>)}</ol><button className="mt-5 w-full rounded-xl bg-[var(--brand)] px-4 py-3 text-sm font-semibold text-white" onClick={() => void post(`programs/${program.public_id}/assess-readiness`, {}, "assess")} type="button">Run readiness assessment</button></article>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><h2 className="text-xl font-semibold">Required sign-offs</h2><div className="mt-4 divide-y divide-[var(--border)]">{plan.signoffs.map((item) => <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between" key={item.public_id}><div><p className="font-semibold">{item.title}</p><p className="mt-1 text-sm text-[var(--muted)]">{label(item.area)}{item.signer ? ` · ${item.signer.display_name}` : ""}</p></div><div className="flex items-center gap-2"><Status value={item.status} />{item.status !== "approved" ? <button className="rounded-lg bg-[var(--brand)] px-3 py-2 text-sm font-semibold text-white" onClick={() => void post(`signoffs/${item.public_id}/decide`, { status: "approved", expected_version: item.version, evidence: { source: "pilot_workspace" } }, item.public_id)} type="button">Approve</button> : null}</div></div>)}</div></article>
          </section>
        ) : null}

        {tab === "adoption" ? (
          <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-xl font-semibold">Pilot adoption evidence</h2><p className="mt-1 text-sm text-[var(--muted)]">Append-only snapshots of usage, training and checklist progress.</p></div><button className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white" onClick={() => void post(`programs/${program.public_id}/collect-adoption`, {}, "adoption")} type="button">Collect snapshot</button></div><div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{(data.adoption ?? []).map((item) => <article className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}><p className="text-sm font-semibold">{item.period_start} → {item.period_end}</p><dl className="mt-3 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-[var(--muted)]">Active users</dt><dd className="font-semibold">{item.active_users}/{item.total_users}</dd></div><div><dt className="text-[var(--muted)]">Training</dt><dd className="font-semibold">{item.training_completion_percent}%</dd></div><div><dt className="text-[var(--muted)]">Checklist</dt><dd className="font-semibold">{item.completed_checklist_items}/{item.total_checklist_items}</dd></div><div><dt className="text-[var(--muted)]">Activities</dt><dd className="font-semibold">{item.key_activity_count}</dd></div></dl></article>)}</div></section>
        ) : null}
      </div>
    </main>
  );
}
