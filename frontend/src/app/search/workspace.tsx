"use client";

import type { Route } from "next";
import Link from "next/link";
import { FormEvent, useState } from "react";

type SearchItem = { kind: string; label: string; subtitle: string; href: Route; public_id: string };
type SearchPayload = { query: string; count?: number; message?: string; items: SearchItem[] };

const badges: Record<string, string> = {
  PROJECT: "P3", CUSTOMER: "CU", LEAD: "LD", OPPORTUNITY: "OP", DESIGN: "DR",
  PURCHASE_REQUEST: "PR", PURCHASE_ORDER: "PO", INVOICE: "IN", HANDOVER_ASSET: "HA",
};

export function SearchWorkspace() {
  const [query, setQuery] = useState("");
  const [payload, setPayload] = useState<SearchPayload>({ query: "", items: [] });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true); setMessage("");
    const response = await fetch(`/api/project360/search?q=${encodeURIComponent(query)}`, { cache: "no-store" }).catch(() => null);
    setLoading(false);
    if (!response?.ok) { setMessage("Search could not be completed."); return; }
    setPayload(await response.json() as SearchPayload);
  }

  return <main className="min-h-screen bg-[var(--background)] px-4 py-6 sm:px-7 lg:px-10"><div className="mx-auto max-w-5xl space-y-6">
    <header className="rounded-[30px] border border-[var(--border)] bg-white p-6 shadow-sm lg:p-8">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--brand)]">Universal search</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Find work without hunting through modules.</h1>
      <p className="mt-2 text-sm text-[var(--muted)]">Results are tenant-scoped and permission-aware. Protected contact values are never indexed or returned here.</p>
      <form className="mt-6 flex gap-3" onSubmit={submit}>
        <input autoFocus className="min-w-0 flex-1 rounded-2xl border border-[var(--border)] bg-white px-4 py-3 text-sm outline-none focus:border-[var(--brand)]" onChange={(e) => setQuery(e.target.value)} placeholder="Project, customer, drawing, PR, PO, invoice, asset…" value={query} />
        <button className="rounded-2xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50" disabled={loading || query.trim().length < 2} type="submit">{loading ? "Searching…" : "Search"}</button>
      </form>
    </header>
    {message ? <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{message}</div> : null}
    {payload.message ? <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{payload.message}</div> : null}
    <section className="space-y-3">
      {payload.items.map((item) => <Link className="group flex items-center gap-4 rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-[var(--brand)]" href={item.href} key={`${item.kind}-${item.public_id}`}>
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-[var(--brand-soft)] text-xs font-bold text-[var(--brand)]">{badges[item.kind] ?? item.kind.slice(0,2)}</span>
        <span className="min-w-0 flex-1"><span className="block text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--muted)]">{item.kind.replaceAll("_", " ")}</span><span className="mt-1 block font-semibold">{item.label}</span><span className="mt-1 block truncate text-xs text-[var(--muted)]">{item.subtitle}</span></span>
        <span className="text-xl text-[var(--muted)] group-hover:text-[var(--brand)]">→</span>
      </Link>)}
      {payload.query && !payload.items.length && !payload.message ? <div className="rounded-[28px] border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-[var(--muted)]">No permitted result matched “{payload.query}”.</div> : null}
    </section>
  </div></main>;
}
