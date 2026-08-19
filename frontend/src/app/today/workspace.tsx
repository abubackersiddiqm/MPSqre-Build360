"use client";

import type { Route } from "next";
import Link from "next/link";

type WorkItem = { title: string; meta: string; tone: "ATTENTION" | "WARNING" | "INFO" | "SUCCESS"; href: Route };
type WorkSection = { code: string; title: string; href: Route; items: WorkItem[] };
export type GuidedWorkbench = {
  generated_at: string;
  attention_count: number;
  summary: { my_tasks: number; crm_followups: number; approvals: number; overdue_invoices: number; procurement_due: number };
  sections: WorkSection[];
  quick_actions: { label: string; href: Route }[];
};

const tone: Record<string, string> = {
  ATTENTION: "border-red-200 bg-red-50 text-red-800",
  WARNING: "border-amber-200 bg-amber-50 text-amber-900",
  INFO: "border-slate-200 bg-slate-50 text-slate-700",
  SUCCESS: "border-emerald-200 bg-emerald-50 text-emerald-800",
};

export function TodayWorkspace({ initialPayload }: Readonly<{ initialPayload: GuidedWorkbench }>) {
  const stats = [
    ["My tasks", initialPayload.summary.my_tasks],
    ["CRM follow-ups", initialPayload.summary.crm_followups],
    ["Approvals", initialPayload.summary.approvals],
    ["Overdue invoices", initialPayload.summary.overdue_invoices],
    ["Procurement due", initialPayload.summary.procurement_due],
  ];
  return (
    <main className="min-h-screen bg-[var(--background)] px-4 py-6 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1500px] space-y-6">
        <header className="overflow-hidden rounded-[30px] border border-[var(--border)] bg-white p-6 shadow-sm lg:p-8">
          <div className="grid gap-6 lg:grid-cols-[1.25fr_.75fr] lg:items-end">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--brand)]">Build360 · Today</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">What needs your attention now.</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">This page adapts from your permissions — no hard-coded job title and no duplicate task database.</p>
            </div>
            <div className="rounded-3xl p-5 text-white" style={{ background: "linear-gradient(145deg, var(--brand), var(--brand-strong))" }}>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-white/70">Attention now</p>
              <p className="mt-2 text-4xl font-semibold">{initialPayload.attention_count}</p>
              <p className="mt-1 text-sm text-white/70">Overdue / attention items visible to you</p>
            </div>
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {stats.map(([label, value]) => <div className="rounded-2xl bg-slate-50 p-4" key={String(label)}><p className="text-xs font-semibold text-[var(--muted)]">{label}</p><p className="mt-2 text-2xl font-semibold">{value}</p></div>)}
          </div>
        </header>

        <section className="grid gap-5 xl:grid-cols-2">
          {initialPayload.sections.map((section) => (
            <article className="rounded-[28px] border border-[var(--border)] bg-white p-5 shadow-sm sm:p-6" key={section.code}>
              <div className="flex items-center justify-between gap-4">
                <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--brand)]">{section.code.replaceAll("_", " ")}</p><h2 className="mt-1 text-xl font-semibold">{section.title}</h2></div>
                <Link className="text-xs font-semibold text-[var(--brand)]" href={section.href}>Open →</Link>
              </div>
              <div className="mt-5 space-y-3">
                {section.items.length ? section.items.map((item, index) => (
                  <Link className={`block rounded-2xl border p-4 transition hover:-translate-y-0.5 hover:shadow-sm ${tone[item.tone] ?? tone.INFO}`} href={item.href} key={`${item.title}-${index}`}>
                    <p className="font-semibold">{item.title}</p><p className="mt-1 text-xs opacity-75">{item.meta}</p>
                  </Link>
                )) : <p className="rounded-2xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-800">Nothing pending in this area.</p>}
              </div>
            </article>
          ))}
        </section>
        {!initialPayload.sections.length ? <div className="rounded-[28px] border border-dashed border-slate-300 bg-white p-12 text-center text-sm text-[var(--muted)]">No guided-work sections are available for the current permissions.</div> : null}
      </div>
    </main>
  );
}
