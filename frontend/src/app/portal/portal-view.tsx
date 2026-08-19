"use client";

import Link from "next/link";

export type Company = {
  public_id: string;
  code: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
  primary_domain?: string | null;
  branding?: {
    product_name: string; tagline: string; logo_url: string; compact_logo_url: string; favicon_url: string;
    primary_color: string; accent_color: string; sidebar_style: string; powered_by_build360: boolean; version: number;
  };
};
export type Grant = {
  public_id: string; portal_type: string; scope_type: string; scope_public_id: string | null; permission_codes: string[];
  effective_from: string; effective_to: string | null; revoked_at: string | null;
};
export type SharedEstimate = {
  type: "estimation.version"; estimate_code: string; estimate_name: string; project_code: string; project_name: string;
  currency: string; version_number: number; stage_name: string; subtotal: string; tax_total: string; grand_total: string;
  notes: string; baselined_at: string;
  boq_items: { item_code: string; description: string; unit_code: string; quantity: string; rate: string; amount: string; tax_amount: string; total_amount: string }[];
};
export type SharedProjectProgress = {
  type: "project"; project_code: string; project_name: string; stage_name: string;
  planned_start_date: string | null; planned_end_date: string | null; actual_start_date: string | null; actual_end_date: string | null;
  progress_percent: number; task_count: number; completed_tasks: number; overdue_tasks: number;
  issued_design_versions: number | null; updated_at: string;
};
export type SharedDesignDocument = {
  type: "design.document"; project_code: string; project_name: string; document_number: string; title: string;
  discipline_code: string; document_type_code: string; description: string; revision_code: string | null;
  version_number: number | null; stage_name: string | null; issued_at: string | null;
  file: null | { file_public_id: string; original_name: string; content_type: string; size_bytes: number };
};
export type SharedInvoice = {
  type: "finance.invoice"; project_code: string; project_name: string; invoice_number: string; invoice_type: string;
  counterparty_name: string; stage_name: string; currency: string; invoice_date: string; due_date: string;
  net_amount: string; tax_amount: string; gross_amount: string; outstanding_amount: string; posted_at: string | null;
};
export type SharedPurchaseOrder = {
  type: "procurement.purchase_order"; project_code: string | null; project_name: string | null; po_number: string;
  vendor_name: string; stage_name: string; currency: string; total_amount: string; issued_at: string | null;
  lines: { line_number: number; description: string; quantity_ordered: string; quantity_received: string; unit_code: string; unit_rate: string }[];
};
export type PortalShare = {
  public_id: string; entity_type: string; entity_public_id: string; access_level: string; expires_at: string | null;
  entity: SharedEstimate | SharedProjectProgress | SharedDesignDocument | SharedInvoice | SharedPurchaseOrder | null;
};

const currency = (code: string, value: string) => new Intl.NumberFormat("en-IN", { style: "currency", currency: code, maximumFractionDigits: 2 }).format(Number(value));

async function openSharedDesignFile(sharePublicId: string) {
  const response = await fetch(`/api/portal/me/shares/${sharePublicId}/download`, { cache: "no-store" }).catch(() => null);
  if (!response?.ok) return;
  const body = await response.json().catch(() => null) as { download_url?: string } | null;
  if (body?.download_url) window.open(body.download_url, "_blank", "noopener,noreferrer");
}

export function PortalView({ company, grants, shares }: Readonly<{ company: Company; grants: Grant[]; shares: PortalShare[] }>) {
  const brand = company.branding;
  const estimates = shares.filter((share): share is PortalShare & { entity: SharedEstimate } => share.entity?.type === "estimation.version");
  const projects = shares.filter((share): share is PortalShare & { entity: SharedProjectProgress } => share.entity?.type === "project");
  const documents = shares.filter((share): share is PortalShare & { entity: SharedDesignDocument } => share.entity?.type === "design.document");
  const invoices = shares.filter((share): share is PortalShare & { entity: SharedInvoice } => share.entity?.type === "finance.invoice");
  const purchaseOrders = shares.filter((share): share is PortalShare & { entity: SharedPurchaseOrder } => share.entity?.type === "procurement.purchase_order");
  const projectNames = new Set([...estimates.map((share) => share.entity.project_name), ...projects.map((share) => share.entity.project_name), ...documents.map((share) => share.entity.project_name), ...invoices.map((share) => share.entity.project_name), ...purchaseOrders.map((share) => share.entity.project_name).filter((value): value is string => Boolean(value))]);
  return (
    <main className="min-h-screen bg-[var(--background)] px-4 py-6 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="overflow-hidden rounded-[30px] border border-[var(--border)] bg-white shadow-sm">
          <div className="grid gap-6 p-6 lg:grid-cols-[1.2fr_.8fr] lg:p-8">
            <div>
              <div className="flex items-center gap-3">
                {brand?.logo_url ? <span aria-label="Company logo" className="h-12 w-36 rounded-xl bg-contain bg-left bg-no-repeat" role="img" style={{ backgroundImage: `url(${brand.logo_url})` }} /> : <span className="grid h-12 w-12 place-items-center rounded-xl bg-[var(--brand-soft)] text-xs font-black text-[var(--brand)]">{company.code.slice(0,2)}</span>}
                <div><p className="text-xs font-bold uppercase tracking-[.18em] text-[var(--brand)]">Client portal</p><p className="mt-1 text-sm text-[var(--muted)]">{brand?.product_name || "MPSqre Build360"}</p></div>
              </div>
              <h1 className="mt-6 text-3xl font-semibold tracking-tight sm:text-4xl">{company.display_name}</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">Approved, recipient-scoped project information in one clean client-facing experience. Internal records that were not explicitly shared stay hidden.</p>
            </div>
            <div className="rounded-[24px] p-5 text-white" style={{ background: `linear-gradient(145deg, ${brand?.primary_color || "#174D3C"}, ${brand?.accent_color || "#0F766E"})` }}>
              <p className="text-xs font-bold uppercase tracking-[.16em] text-white/70">Your access</p>
              <div className="mt-5 grid grid-cols-3 gap-3"><div><p className="text-3xl font-semibold">{grants.length}</p><p className="mt-1 text-xs text-white/65">Scopes</p></div><div><p className="text-3xl font-semibold">{projectNames.size}</p><p className="mt-1 text-xs text-white/65">Projects</p></div><div><p className="text-3xl font-semibold">{shares.length}</p><p className="mt-1 text-xs text-white/65">Shared records</p></div></div>
              <p className="mt-7 text-xs text-white/65">Project-scoped · expiring · auditable</p>
              {brand?.powered_by_build360 ? <p className="mt-2 text-[10px] text-white/50">Powered by MPSqre Build360</p> : null}
              <button className="mt-4 rounded-xl border border-white/30 px-3 py-2 text-xs font-semibold text-white print:hidden" onClick={() => window.print()} type="button">Print branded client report</button>
            </div>
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-3">
          <article className="rounded-[24px] border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-xs text-[var(--muted)]">Authorized scopes</p><p className="mt-2 text-3xl font-semibold">{grants.length}</p></article>
          <article className="rounded-[24px] border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-xs text-[var(--muted)]">Approved shares</p><p className="mt-2 text-3xl font-semibold">{shares.length}</p></article>
          <article className="rounded-[24px] border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-xs text-[var(--muted)]">Security</p><p className="mt-2 text-lg font-semibold">Least-privilege portal access</p></article>
        </section>

        {projects.length?<section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm print:shadow-none"><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Project progress</p><h2 className="mt-1 text-2xl font-semibold">Shared delivery status</h2><p className="mt-1 text-sm text-[var(--muted)]">Aggregate client-safe progress only. Internal task names, budgets and internal notes are not exposed by this project share.</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{projects.length} project(s)</span></div><div className="mt-5 grid gap-4 lg:grid-cols-2">{projects.map((share)=><article className="rounded-[24px] border border-[var(--border)] p-5" key={share.public_id}><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.14em] text-[var(--brand)]">{share.entity.project_code}</p><h3 className="mt-1 text-xl font-semibold">{share.entity.project_name}</h3><p className="mt-1 text-sm text-[var(--muted)]">{share.entity.stage_name}</p></div><span className="rounded-full bg-[var(--brand-soft)] px-3 py-1 text-xs font-bold text-[var(--brand)]">{share.entity.progress_percent}%</span></div><div className="mt-5"><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-[var(--brand)]" style={{width:`${Math.min(100,Math.max(0,share.entity.progress_percent))}%`}}/></div></div><div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4"><div className="rounded-2xl bg-slate-50 p-3"><p className="text-[10px] text-[var(--muted)]">Completed</p><p className="mt-1 font-semibold">{share.entity.completed_tasks}/{share.entity.task_count}</p></div><div className="rounded-2xl bg-slate-50 p-3"><p className="text-[10px] text-[var(--muted)]">Overdue</p><p className="mt-1 font-semibold">{share.entity.overdue_tasks}</p></div><div className="rounded-2xl bg-slate-50 p-3"><p className="text-[10px] text-[var(--muted)]">Planned finish</p><p className="mt-1 text-xs font-semibold">{share.entity.planned_end_date ?? "Not set"}</p></div><div className="rounded-2xl bg-slate-50 p-3"><p className="text-[10px] text-[var(--muted)]">Issued design</p><p className="mt-1 font-semibold">{share.entity.issued_design_versions ?? "Restricted"}</p></div></div><p className="mt-4 text-[10px] text-[var(--muted)]">Status updated {new Date(share.entity.updated_at).toLocaleString()}</p></article>)}</div></section>:null}

        {documents.length ? <section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm print:shadow-none">
          <div className="flex items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Issued documents</p><h2 className="mt-1 text-2xl font-semibold">Design documents shared with you</h2></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{documents.length}</span></div>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">{documents.map((share) => <article className="rounded-[24px] border border-[var(--border)] p-5" key={share.public_id}>
            <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.12em] text-[var(--brand)]">{share.entity.document_number}</p><h3 className="mt-1 text-lg font-semibold">{share.entity.title}</h3><p className="mt-1 text-xs text-[var(--muted)]">{share.entity.project_name} · {share.entity.discipline_code}</p></div><span className="rounded-full bg-[var(--brand-soft)] px-3 py-1 text-[10px] font-bold text-[var(--brand)]">{share.entity.revision_code ?? "NO ISSUE"}</span></div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-xs"><div className="rounded-2xl bg-slate-50 p-3"><p className="text-[var(--muted)]">Stage</p><p className="mt-1 font-semibold">{share.entity.stage_name ?? "Not issued"}</p></div><div className="rounded-2xl bg-slate-50 p-3"><p className="text-[var(--muted)]">Issued</p><p className="mt-1 font-semibold">{share.entity.issued_at ? new Date(share.entity.issued_at).toLocaleDateString() : "—"}</p></div></div>
            {share.entity.file ? <button className="mt-4 rounded-xl bg-[var(--brand)] px-4 py-2.5 text-xs font-semibold text-white print:hidden" onClick={() => openSharedDesignFile(share.public_id)} type="button">Open governed file</button> : <p className="mt-4 text-xs text-[var(--muted)]">No CLEAN governed file is available for this issued revision.</p>}
          </article>)}</div>
        </section> : null}

        {invoices.length ? <section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm print:shadow-none">
          <div className="flex items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Invoices</p><h2 className="mt-1 text-2xl font-semibold">Shared billing records</h2></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{invoices.length}</span></div>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">{invoices.map((share) => <article className="rounded-[24px] border border-[var(--border)] p-5" key={share.public_id}>
            <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.12em] text-[var(--brand)]">{share.entity.invoice_number}</p><h3 className="mt-1 text-lg font-semibold">{share.entity.project_name}</h3><p className="mt-1 text-xs text-[var(--muted)]">{share.entity.stage_name} · due {share.entity.due_date}</p></div><span className="text-lg font-semibold">{share.entity.currency} {Number(share.entity.gross_amount).toLocaleString("en-IN")}</span></div>
            <div className="mt-4 grid grid-cols-3 gap-3 text-xs"><div className="rounded-2xl bg-slate-50 p-3"><p className="text-[var(--muted)]">Net</p><p className="mt-1 font-semibold">{Number(share.entity.net_amount).toLocaleString("en-IN")}</p></div><div className="rounded-2xl bg-slate-50 p-3"><p className="text-[var(--muted)]">Tax</p><p className="mt-1 font-semibold">{Number(share.entity.tax_amount).toLocaleString("en-IN")}</p></div><div className="rounded-2xl bg-red-50 p-3"><p className="text-red-700">Outstanding</p><p className="mt-1 font-semibold text-red-900">{Number(share.entity.outstanding_amount).toLocaleString("en-IN")}</p></div></div>
          </article>)}</div>
        </section> : null}

        {purchaseOrders.length ? <section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm print:shadow-none">
          <div className="flex items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Purchase orders</p><h2 className="mt-1 text-2xl font-semibold">Governed vendor order shares</h2></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{purchaseOrders.length}</span></div>
          <div className="mt-5 space-y-4">{purchaseOrders.map((share) => <article className="rounded-[24px] border border-[var(--border)] p-5" key={share.public_id}>
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.12em] text-[var(--brand)]">{share.entity.po_number}</p><h3 className="mt-1 text-lg font-semibold">{share.entity.vendor_name}</h3><p className="mt-1 text-xs text-[var(--muted)]">{share.entity.project_name ?? "Company scope"} · {share.entity.stage_name}</p></div><p className="text-lg font-semibold">{share.entity.currency} {Number(share.entity.total_amount).toLocaleString("en-IN")}</p></div>
            <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead className="text-[var(--muted)]"><tr><th className="pb-2">#</th><th>Description</th><th>Qty</th><th>Received</th><th>Rate</th></tr></thead><tbody className="divide-y divide-[var(--border)]">{share.entity.lines.map((line) => <tr key={line.line_number}><td className="py-3">{line.line_number}</td><td className="font-medium">{line.description}</td><td>{line.quantity_ordered} {line.unit_code}</td><td>{line.quantity_received}</td><td>{Number(line.unit_rate).toLocaleString("en-IN")}</td></tr>)}</tbody></table></div>
          </article>)}</div>
        </section> : null}

        <section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Shared with you</p><h2 className="mt-1 text-2xl font-semibold">Approved commercial records</h2><p className="mt-1 text-sm text-[var(--muted)]">Only records explicitly shared to your active portal grant are rendered.</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{estimates.length} estimate(s)</span></div>
          <div className="mt-5 space-y-5">{estimates.map((share) => <article className="overflow-hidden rounded-[24px] border border-[var(--border)]" key={share.public_id}><div className="grid gap-4 border-b border-[var(--border)] bg-slate-50 p-5 sm:grid-cols-[1fr_auto] sm:items-end"><div><p className="text-xs font-bold uppercase tracking-[.14em] text-[var(--brand)]">Approved estimate · v{share.entity.version_number}</p><h3 className="mt-1 text-xl font-semibold">{share.entity.project_name}</h3><p className="mt-1 text-sm text-[var(--muted)]">{share.entity.project_code} · {share.entity.estimate_code} · {share.entity.estimate_name}</p></div><div className="sm:text-right"><p className="text-xs text-[var(--muted)]">Approved total</p><p className="mt-1 text-2xl font-semibold">{currency(share.entity.currency, share.entity.grand_total)}</p></div></div><div className="grid gap-3 p-5 sm:grid-cols-4"><div className="rounded-2xl bg-slate-50 p-3"><p className="text-xs text-[var(--muted)]">Subtotal</p><p className="mt-1 font-semibold">{currency(share.entity.currency, share.entity.subtotal)}</p></div><div className="rounded-2xl bg-slate-50 p-3"><p className="text-xs text-[var(--muted)]">Tax</p><p className="mt-1 font-semibold">{currency(share.entity.currency, share.entity.tax_total)}</p></div><div className="rounded-2xl bg-slate-50 p-3"><p className="text-xs text-[var(--muted)]">Status</p><p className="mt-1 font-semibold">{share.entity.stage_name}</p></div><div className="rounded-2xl bg-slate-50 p-3"><p className="text-xs text-[var(--muted)]">BOQ lines</p><p className="mt-1 font-semibold">{share.entity.boq_items.length}</p></div></div>{share.entity.notes ? <p className="px-5 pb-4 text-sm text-[var(--muted)]">{share.entity.notes}</p> : null}<details className="border-t border-[var(--border)]"><summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-[var(--brand)]">View BOQ details</summary><div className="overflow-x-auto border-t border-[var(--border)]"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-slate-50 text-[var(--muted)]"><tr><th className="p-3">Item</th><th>Description</th><th>Qty</th><th>Rate</th><th>Total</th></tr></thead><tbody className="divide-y divide-[var(--border)]">{share.entity.boq_items.map((item)=><tr key={item.item_code}><td className="p-3 font-medium">{item.item_code}</td><td>{item.description}</td><td>{item.quantity} {item.unit_code}</td><td>{item.rate}</td><td className="font-semibold">{item.total_amount}</td></tr>)}</tbody></table></div></details></article>)}{!estimates.length?<div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center"><p className="font-semibold">Nothing shared yet</p><p className="mt-2 text-sm text-[var(--muted)]">When an approved estimate or other supported record is shared to your portal grant, it will appear here.</p></div>:null}</div>
        </section>

        <section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm"><div className="flex items-center justify-between"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Access register</p><h2 className="mt-1 text-xl font-semibold">What you are authorized to see</h2></div><Link className="text-xs font-semibold text-[var(--brand)]" href="/platform">Back to platform →</Link></div><div className="mt-5 grid gap-3 md:grid-cols-2">{grants.map((grant)=><article className="rounded-2xl border border-[var(--border)] p-4" key={grant.public_id}><div className="flex items-center justify-between gap-3"><p className="font-semibold capitalize">{grant.portal_type} portal</p><span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold">{grant.scope_type}</span></div><p className="mt-2 text-xs text-[var(--muted)]">{grant.permission_codes.length} permission(s) · effective {new Date(grant.effective_from).toLocaleDateString()}</p></article>)}</div></section>
      </div>
    </main>
  );
}
