"use client";
import type { Route } from "next";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

export type Company = { public_id: string; code: string; display_name: string; currency: string; timezone: string };
export type Project = { public_id: string; code: string; name: string; stage: { code: string; name: string; outcome: string }; approved_budget: string; currency: string; planned_start_date: string | null; planned_end_date: string | null; location: Record<string, unknown> };
type Checkpoint = { label: string; status: "DONE" | "ACTIVE" | "PENDING" | "ATTENTION"; value?: number | string };
type Step = { code: string; label: string; description: string; status: string; progress_percent: number; evidence: Record<string, unknown>; workspace_href?: Route | null; checkpoints: Checkpoint[]; next_action?: { label: string; href: Route } };
type Experience = { configured: boolean; message?: string; project: { public_id: string; code: string; name: string; stage_code: string; stage_name: string; currency: string; approved_budget: string; planned_start_date: string | null; planned_end_date: string | null; location: Record<string, unknown> }; overall_progress_percent?: number; current_step?: Step | null; steps: Step[]; next_actions: { step_code: string; label: string; href: Route }[]; health?: { overdue_tasks: number; open_design_issues: number | null; status: string }; finance?: { available: boolean; currency?: string; contract_value?: string; approved_variations?: string; certified_or_invoiced?: string; received?: string; outstanding?: string; committed_cost?: string; actual_cost?: string; forecast_cost?: string; forecast_margin_percent?: string } };
type Props = { company: Company; permissions: string[]; initialProjects: Project[]; initialProject?: string };

const money = (value: string | undefined, currency: string) => {
  const number = Number(value ?? 0); if (!Number.isFinite(number)) return `${currency} —`;
  try { return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(number); } catch { return `${currency} ${number.toLocaleString("en-IN")}`; }
};
const statusClasses: Record<string, string> = { COMPLETE: "bg-emerald-600 text-white", IN_PROGRESS: "bg-[var(--brand)] text-white", BLOCKED: "bg-amber-100 text-amber-900", PENDING: "bg-slate-100 text-slate-500", RESTRICTED: "bg-slate-200 text-slate-500" };

type ProjectApiError = { message?: string; detail?: string; non_field_errors?: string[]; [key: string]: unknown };

function projectErrorMessage(body: ProjectApiError, fallback: string) {
  if (body.message) return body.message;
  if (body.detail) return body.detail;
  if (Array.isArray(body.non_field_errors) && body.non_field_errors.length) return body.non_field_errors.join(" ");
  for (const [field, value] of Object.entries(body)) {
    if (Array.isArray(value) && value.length) return `${field}: ${value.map(String).join(" ")}`;
  }
  return fallback;
}

export function Project360Workspace({ company, permissions, initialProjects, initialProject = "" }: Readonly<Props>) {
  const preferredProject = initialProjects.some((item) => item.public_id === initialProject) ? initialProject : initialProjects[0]?.public_id ?? "";
  const [projects, setProjects] = useState(initialProjects);
  const [selected, setSelected] = useState(preferredProject);
  const [experience, setExperience] = useState<Experience | null>(null);
  const [loading, setLoading] = useState(Boolean(selected));
  const [message, setMessage] = useState("");
  const [notice, setNotice] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const canCreateProject = permissions.includes("project.project.manage");
  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      if (!selected) {
        setExperience(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setMessage("");
      void fetch(`/api/project360/projects/${selected}/experience`, { signal: controller.signal, cache: "no-store" })
        .then(async (response) => { const body = await response.json() as Experience & { message?: string }; if (!response.ok) throw new Error(body.message ?? "Project360 could not load."); return body; })
        .then((body) => { if (controller.signal.aborted) return; setExperience(body); setLoading(false); })
        .catch((error) => { if (controller.signal.aborted) return; setMessage(error instanceof Error ? error.message : "Project360 could not load."); setLoading(false); });
    });
    return () => controller.abort();
  }, [selected]);
  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setMessage("");
    setNotice("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const locationText = String(form.get("location") || "").trim();
    const payload = {
      code: String(form.get("code") || "").trim(),
      name: String(form.get("name") || "").trim(),
      description: String(form.get("description") || "").trim(),
      approved_budget: String(form.get("approved_budget") || "0").trim() || "0",
      planned_start_date: String(form.get("planned_start_date") || "").trim() || null,
      planned_end_date: String(form.get("planned_end_date") || "").trim() || null,
      location: locationText ? { label: locationText } : {},
    };
    try {
      const response = await fetch("/api/projects/items", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        cache: "no-store",
      });
      const body = (await response.json().catch(() => ({}))) as Project & ProjectApiError;
      if (!response.ok) throw new Error(projectErrorMessage(body, `Project could not be created (${response.status}).`));
      setProjects((current) => [body, ...current.filter((item) => item.public_id !== body.public_id)]);
      setSelected(body.public_id);
      setNotice(`${body.code} · ${body.name} created. Project360 is ready for design, estimation and delivery.`);
      setShowCreate(false);
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Project could not be created.");
    } finally {
      setCreating(false);
    }
  }

  const finance = experience?.finance;

  return <main className="min-h-screen bg-[var(--background)] px-4 py-6 sm:px-7 lg:px-10"><div className="mx-auto max-w-[1500px] space-y-6">
    <header className="relative overflow-hidden rounded-[30px] border border-[var(--border)] bg-white p-6 shadow-sm lg:p-8">
      <div className="absolute inset-y-0 right-0 hidden w-1/3 opacity-10 lg:block" style={{ background: "radial-gradient(circle at center, var(--brand), transparent 65%)" }} />
      <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--brand)]">Build360 · Project 360</p><h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">One project. One visual operating story.</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">CRM, design, estimate, planning, procurement, execution, billing and handover are projected from their existing governed records.</p></div>
        <div className="min-w-0 space-y-3 lg:w-[410px]">
          <div className="flex items-end gap-2">
            <label className="min-w-0 flex-1"><span className="mb-2 block text-xs font-bold uppercase tracking-[0.14em] text-[var(--muted)]">Project</span><select className="w-full rounded-2xl border border-[var(--border)] bg-white px-4 py-3 text-sm font-semibold" onChange={(e) => setSelected(e.target.value)} value={selected}><option value="">Select a project</option>{projects.map((item) => <option key={item.public_id} value={item.public_id}>{item.code} · {item.name}</option>)}</select></label>
            {canCreateProject ? <button className="rounded-2xl bg-[var(--brand)] px-4 py-3 text-sm font-semibold text-white" onClick={() => setShowCreate((value) => !value)} type="button">+ New project</button> : null}
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3"><Link className="rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-center text-xs font-semibold hover:border-[var(--brand)]" href={selected ? `/project360/design?project=${selected}` : "/project360/design"}>Design</Link><Link className="rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-center text-xs font-semibold hover:border-[var(--brand)]" href={selected ? `/project360/site?project=${selected}` : "/project360/site"}>Site Pulse</Link><Link className="rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-center text-xs font-semibold hover:border-[var(--brand)]" href={selected ? `/project360/procurement?project=${selected}` : "/project360/procurement"}>Procurement</Link><Link className="rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-center text-xs font-semibold hover:border-[var(--brand)]" href={selected ? `/project360/handover?project=${selected}` : "/project360/handover"}>Handover</Link><Link className="rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-center text-xs font-semibold hover:border-[var(--brand)]" href="/approvals">Approvals</Link><Link className="rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-center text-xs font-semibold hover:border-[var(--brand)]" href={selected ? `/project360/insights?project=${selected}` : "/project360/insights"}>Evidence</Link><Link className="rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-center text-xs font-semibold hover:border-[var(--brand)]" href="/executive">Executive</Link><Link className="rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-center text-xs font-semibold hover:border-[var(--brand)]" href="/today">Today</Link></div>
        </div>
      </div>
    </header>

    {notice ? <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm font-medium text-emerald-900">{notice}</div> : null}
    {message ? <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800">{message}</div> : null}
    {showCreate && canCreateProject ? <form className="grid gap-4 rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm md:grid-cols-2 xl:grid-cols-4" onSubmit={createProject}>
      <div className="md:col-span-2 xl:col-span-4"><p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--brand)]">Create project</p><h2 className="mt-1 text-2xl font-semibold">Start a governed Project360 workspace</h2><p className="mt-1 text-sm text-[var(--muted)]">Use this for direct operational projects. If the project comes from a sales deal, continue it from CRM so the opportunity linkage is preserved.</p></div>
      <label className="text-sm font-semibold">Project code<input className="mt-1 w-full rounded-xl border border-[var(--border)] px-4 py-3 font-normal" name="code" placeholder="PRJ-001" required /></label>
      <label className="text-sm font-semibold">Project name<input className="mt-1 w-full rounded-xl border border-[var(--border)] px-4 py-3 font-normal" name="name" placeholder="Customer / project name" required /></label>
      <label className="text-sm font-semibold">Approved budget<input className="mt-1 w-full rounded-xl border border-[var(--border)] px-4 py-3 font-normal" min="0" name="approved_budget" placeholder="0" step="0.01" type="number" /></label>
      <label className="text-sm font-semibold">Location<input className="mt-1 w-full rounded-xl border border-[var(--border)] px-4 py-3 font-normal" name="location" placeholder="City / site" /></label>
      <label className="text-sm font-semibold">Planned start<input className="mt-1 w-full rounded-xl border border-[var(--border)] px-4 py-3 font-normal" name="planned_start_date" type="date" /></label>
      <label className="text-sm font-semibold">Planned end<input className="mt-1 w-full rounded-xl border border-[var(--border)] px-4 py-3 font-normal" name="planned_end_date" type="date" /></label>
      <label className="text-sm font-semibold md:col-span-2">Description<textarea className="mt-1 min-h-24 w-full rounded-xl border border-[var(--border)] px-4 py-3 font-normal" name="description" placeholder="Scope / internal context" /></label>
      <div className="flex flex-wrap gap-2 md:col-span-2 xl:col-span-4"><button className="rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50" disabled={creating} type="submit">{creating ? "Creating…" : "Create project"}</button><button className="rounded-xl border border-[var(--border)] px-5 py-3 text-sm font-semibold" disabled={creating} onClick={() => setShowCreate(false)} type="button">Cancel</button></div>
    </form> : null}
    {!projects.length ? <div className="rounded-[28px] border border-dashed border-slate-300 bg-white p-12 text-center"><h2 className="text-2xl font-semibold">No project is available yet</h2><p className="mt-2 text-sm text-[var(--muted)]">Create a project directly, or convert a CRM opportunity so Project360 keeps the sales-to-delivery link.</p><div className="mt-6 flex flex-wrap justify-center gap-3">{canCreateProject ? <button className="rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white" onClick={() => setShowCreate(true)} type="button">Create first project</button> : null}<Link className="inline-block rounded-xl border border-[var(--border)] bg-white px-5 py-3 text-sm font-semibold" href="/crm">Open CRM</Link></div></div> : null}
    {loading ? <div className="grid gap-4 md:grid-cols-3"><div className="h-36 animate-pulse rounded-3xl bg-slate-200" /><div className="h-36 animate-pulse rounded-3xl bg-slate-200" /><div className="h-36 animate-pulse rounded-3xl bg-slate-200" /></div> : null}
    {experience && !experience.configured ? <div className="rounded-[28px] border border-amber-200 bg-amber-50 p-6"><h2 className="text-xl font-semibold">Project360 lifecycle needs publishing</h2><p className="mt-2 text-sm text-amber-900">{experience.message}</p></div> : null}

    {experience?.configured ? <>
      <section className="grid gap-4 xl:grid-cols-[1.35fr_.65fr]">
        <article className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm lg:p-7">
          <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm font-semibold text-[var(--muted)]">{experience.project.code}</p><h2 className="mt-1 text-3xl font-semibold">{experience.project.name}</h2><p className="mt-2 text-sm text-[var(--muted)]">{experience.project.stage_name} · {company.timezone}</p></div><div className="grid h-24 w-24 place-items-center rounded-full border-[10px] border-emerald-100 bg-white text-center"><div><strong className="block text-2xl">{experience.overall_progress_percent ?? 0}%</strong><span className="text-[10px] uppercase text-[var(--muted)]">Journey</span></div></div></div>
          <div className="mt-7 overflow-x-auto pb-2"><div className="flex min-w-max items-start gap-2">{experience.steps.map((step, index) => <div className="flex items-start" key={step.code}><div className="w-40"><div className={`grid h-10 w-10 place-items-center rounded-full text-xs font-bold ${statusClasses[step.status] ?? statusClasses.PENDING}`}>{step.status === "COMPLETE" ? "✓" : String(index + 1).padStart(2, "0")}</div>{step.workspace_href ? <Link className="mt-3 block text-sm font-semibold hover:text-[var(--brand)]" href={step.workspace_href}>{step.label}</Link> : <p className="mt-3 text-sm font-semibold">{step.label}</p>}<p className="mt-1 text-xs text-[var(--muted)]">{step.progress_percent}% · {step.status.replaceAll("_", " ")}</p></div>{index < experience.steps.length - 1 ? <div className="mt-5 h-px w-8 bg-slate-300" /> : null}</div>)}</div></div>
        </article>
        <article className="rounded-[28px] p-6 text-white shadow-sm" style={{ background: "linear-gradient(145deg, var(--brand), var(--brand-strong))" }}><p className="text-xs font-bold uppercase tracking-[0.18em] text-white/65">Current focus</p><h2 className="mt-3 text-2xl font-semibold">{experience.current_step?.label ?? "Journey complete"}</h2><p className="mt-2 text-sm leading-6 text-white/70">{experience.current_step?.description || "All configured lifecycle stages are complete."}</p>{experience.current_step?.next_action ? <Link className="mt-6 inline-flex rounded-xl bg-white px-4 py-3 text-sm font-semibold text-[var(--brand)]" href={experience.current_step.next_action.href}>{experience.current_step.next_action.label} →</Link> : null}<div className="mt-8 grid grid-cols-2 gap-3"><div className="rounded-2xl bg-white/10 p-4"><p className="text-2xl font-semibold">{experience.health?.overdue_tasks ?? 0}</p><p className="text-xs text-white/65">Overdue tasks</p></div><div className="rounded-2xl bg-white/10 p-4"><p className="text-2xl font-semibold">{experience.health?.open_design_issues ?? 0}</p><p className="text-xs text-white/65">Design issues</p></div></div></article>
      </section>

      <section className="grid gap-6 xl:grid-cols-[.72fr_1.28fr]">
        <article className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm"><p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--brand)]">Next best actions</p><h2 className="mt-1 text-2xl font-semibold">What needs attention now</h2><div className="mt-5 space-y-3">{experience.next_actions.length ? experience.next_actions.map((action, index) => <Link className="group flex items-center gap-4 rounded-2xl border border-[var(--border)] p-4 transition hover:-translate-y-0.5 hover:border-[var(--brand)] hover:shadow-sm" href={action.href} key={`${action.step_code}-${index}`}><span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-xs font-bold text-[var(--brand)]">{String(index + 1).padStart(2, "0")}</span><span className="min-w-0 flex-1"><span className="block text-xs font-bold uppercase tracking-wide text-[var(--muted)]">{action.step_code.replaceAll("_", " ")}</span><span className="mt-1 block font-semibold">{action.label}</span></span><span className="text-xl text-[var(--muted)] group-hover:text-[var(--brand)]">→</span></Link>) : <p className="rounded-2xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-800">No incomplete configured stages.</p>}</div></article>
        <article className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm"><div className="flex items-end justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--brand)]">Project financial cockpit</p><h2 className="mt-1 text-2xl font-semibold">Commercial visibility in context</h2></div>{finance?.available ? <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">Permissioned live data</span> : null}</div>{finance?.available ? <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[
          ["Contract value", money(finance.contract_value, finance.currency ?? company.currency)], ["Invoiced", money(finance.certified_or_invoiced, finance.currency ?? company.currency)], ["Received", money(finance.received, finance.currency ?? company.currency)], ["Outstanding", money(finance.outstanding, finance.currency ?? company.currency)], ["Committed cost", money(finance.committed_cost, finance.currency ?? company.currency)], ["Actual cost", money(finance.actual_cost, finance.currency ?? company.currency)], ["Forecast cost", money(finance.forecast_cost, finance.currency ?? company.currency)], ["Forecast margin", `${finance.forecast_margin_percent ?? "0.0"}%`],
        ].map(([label, value]) => <div className="rounded-2xl bg-slate-50 p-4" key={label}><p className="text-xs font-semibold text-[var(--muted)]">{label}</p><p className="mt-2 text-lg font-semibold">{value}</p></div>)}</div> : <div className="mt-6 rounded-2xl bg-slate-50 p-5 text-sm text-[var(--muted)]">Finance data is hidden because this user does not have Finance dashboard permission.</div>}</article>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">{experience.steps.map((step) => <article className="rounded-3xl border border-[var(--border)] bg-white p-5 shadow-sm" key={step.code}><div className="flex items-start justify-between gap-3"><span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${statusClasses[step.status] ?? statusClasses.PENDING}`}>{step.status.replaceAll("_", " ")}</span><span className="text-sm font-semibold text-[var(--muted)]">{step.progress_percent}%</span></div>{step.workspace_href ? <Link className="mt-4 block text-lg font-semibold hover:text-[var(--brand)]" href={step.workspace_href}>{step.label}</Link> : <h3 className="mt-4 text-lg font-semibold">{step.label}</h3>}<p className="mt-2 min-h-10 text-xs leading-5 text-[var(--muted)]">{step.description}</p><div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-[var(--brand)]" style={{ width: `${step.progress_percent}%` }} /></div>{step.checkpoints.length ? <div className="mt-4 space-y-2">{step.checkpoints.slice(0, 3).map((checkpoint) => <div className="flex items-center gap-2 text-xs" key={checkpoint.label}><span className={`h-2.5 w-2.5 rounded-full ${checkpoint.status === "DONE" ? "bg-emerald-500" : checkpoint.status === "ATTENTION" ? "bg-red-500" : checkpoint.status === "ACTIVE" ? "bg-amber-500" : "bg-slate-300"}`} /><span className="min-w-0 flex-1 truncate text-[var(--muted)]">{checkpoint.label}</span>{checkpoint.value !== undefined ? <span className="font-semibold">{checkpoint.value}</span> : null}</div>)}</div> : null}{step.next_action ? <Link className="mt-4 inline-flex text-xs font-semibold text-[var(--brand)]" href={step.next_action.href}>{step.next_action.label} →</Link> : step.workspace_href ? <Link className="mt-4 inline-flex text-xs font-semibold text-[var(--brand)]" href={step.workspace_href}>Open workspace →</Link> : null}</article>)}</section>
    </> : null}
  </div></main>;
}
