"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

type Account = {
  public_id: string;
  code: string;
  display_name: string;
  segment: string;
  status: string;
  health_score: number;
  risk_level: string;
  renewal_on: string | null;
  desired_outcomes: unknown[];
  risk_summary: string;
};
type Invoice = {
  public_id: string;
  account_name: string;
  invoice_number: string;
  currency: string;
  total_amount: string;
  outstanding_amount: string;
  status: string;
  due_on: string | null;
};
type Ticket = {
  public_id: string;
  account_name: string;
  ticket_number: string;
  subject: string;
  severity: string;
  status: string;
  response_due_at: string;
  resolution_due_at: string;
  version: number;
};
type SuccessPlan = {
  public_id: string;
  code: string;
  title: string;
  status: string;
  health_score: number;
  next_review_on: string | null;
  renewal_on: string | null;
  objectives: unknown[];
};
type Adoption = {
  public_id: string;
  captured_on: string;
  active_users: number;
  active_projects: number;
  support_ticket_count: number;
  adoption_score: number;
  engagement_score: number;
  feature_utilization: Record<string, unknown>;
};
type Membership = {
  membership_public_id: string;
  display_name: string;
  email: string;
};

export type SuccessopsPortfolio = {
  current_user_public_id: string;
  summary: {
    accounts: number;
    active_accounts: number;
    at_risk_accounts: number;
    average_health_score: number;
    open_tickets: number;
    sla_breaches: number;
    outstanding_invoices: number;
    overdue_invoices: number;
    outstanding_amount: string;
    currency: string;
    adoption_score: number;
    engagement_score: number;
  };
  memberships: Membership[];
  accounts: Account[];
  invoices: Invoice[];
  tickets: Ticket[];
  success_plans: SuccessPlan[];
  adoption_snapshots: Adoption[];
};

type Tab = "health" | "billing" | "support" | "adoption";

const inputClass =
  "w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-700";

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function Status({ value }: Readonly<{ value: string }>) {
  const positive = ["active", "paid", "resolved", "closed", "low"].includes(value);
  const negative = ["at_risk", "overdue", "critical", "high", "churned"].includes(value);
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

export function CustomerSuccessWorkspace({
  initialData,
}: Readonly<{ initialData: SuccessopsPortfolio }>) {
  const [data, setData] = useState(initialData);
  const [tab, setTab] = useState<Tab>("health");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const primaryAccount = data.accounts[0];
  const latestAdoption = data.adoption_snapshots[0];
  const openTickets = useMemo(
    () => data.tickets.filter((item) => !["resolved", "closed"].includes(item.status)),
    [data.tickets],
  );

  async function refresh() {
    const response = await fetch("/api/successops/portfolio", { cache: "no-store" });
    if (response.ok) setData((await response.json()) as SuccessopsPortfolio);
  }

  async function createTicket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!primaryAccount) return;
    setBusy(true);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/successops/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_public_id: primaryAccount.public_id,
        subject: String(form.get("subject")),
        description: String(form.get("description")),
        category: String(form.get("category")),
        severity: String(form.get("severity")),
      }),
    });
    const result = (await response.json().catch(() => ({}))) as { message?: string; detail?: string };
    if (!response.ok) setMessage(result.message ?? result.detail ?? "Ticket creation failed.");
    else {
      setMessage("Support ticket created.");
      event.currentTarget.reset();
      await refresh();
    }
    setBusy(false);
  }

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
              MPSqre Build360 · Customer Success
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              Billing, support and adoption operations
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Account health · subscription billing · support SLAs · renewal evidence
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-900">
              Phase 19 active
            </span>
            <Link
              className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold"
              href="/platform"
            >
              Platform
            </Link>
          </div>
        </header>

        <section className="grid gap-4 py-7 sm:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Account health</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.average_health_score}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">{data.summary.at_risk_accounts} at-risk accounts</p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Outstanding billing</p>
            <p className="mt-2 text-3xl font-semibold">
              {data.summary.currency} {data.summary.outstanding_amount}
            </p>
            <p className="mt-1 text-xs text-[var(--muted)]">{data.summary.overdue_invoices} overdue invoices</p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Open support</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.open_tickets}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">{data.summary.sla_breaches} SLA breaches</p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Adoption score</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.adoption_score}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">Engagement {data.summary.engagement_score}</p>
          </article>
        </section>

        <div className="mb-6 flex flex-wrap gap-2">
          {(["health", "billing", "support", "adoption"] as Tab[]).map((item) => (
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
          <div className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            {message}
          </div>
        ) : null}

        {tab === "health" ? (
          <section className="grid gap-6 lg:grid-cols-2">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Customer account</h2>
              {primaryAccount ? (
                <div className="mt-5 space-y-4">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="font-semibold">{primaryAccount.display_name}</p>
                      <p className="text-sm text-[var(--muted)]">{primaryAccount.code} · {label(primaryAccount.segment)}</p>
                    </div>
                    <Status value={primaryAccount.status} />
                  </div>
                  <dl className="grid grid-cols-2 gap-4 text-sm">
                    <div><dt className="text-[var(--muted)]">Health</dt><dd className="mt-1 text-xl font-semibold">{primaryAccount.health_score}</dd></div>
                    <div><dt className="text-[var(--muted)]">Risk</dt><dd className="mt-2"><Status value={primaryAccount.risk_level} /></dd></div>
                    <div><dt className="text-[var(--muted)]">Renewal</dt><dd className="mt-1 font-medium">{primaryAccount.renewal_on ?? "Not scheduled"}</dd></div>
                    <div><dt className="text-[var(--muted)]">Outcomes</dt><dd className="mt-1 font-medium">{primaryAccount.desired_outcomes.length}</dd></div>
                  </dl>
                  <p className="text-sm leading-6 text-[var(--muted)]">{primaryAccount.risk_summary}</p>
                </div>
              ) : <p className="mt-5 text-sm text-[var(--muted)]">No customer success account is configured.</p>}
            </article>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Success plans</h2>
              <div className="mt-5 space-y-3">
                {data.success_plans.map((plan) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={plan.public_id}>
                    <div className="flex items-start justify-between gap-4"><div><p className="font-semibold">{plan.title}</p><p className="mt-1 text-xs text-[var(--muted)]">{plan.code} · next review {plan.next_review_on ?? "not scheduled"}</p></div><Status value={plan.status} /></div>
                    <p className="mt-3 text-sm text-[var(--muted)]">Health {plan.health_score} · {plan.objectives.length} outcomes</p>
                  </div>
                ))}
                {!data.success_plans.length ? <p className="text-sm text-[var(--muted)]">No success plan has been created.</p> : null}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "billing" ? (
          <section className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold">Subscription invoice register</h2>
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="text-[var(--muted)]"><tr><th className="pb-3">Invoice</th><th className="pb-3">Account</th><th className="pb-3">Total</th><th className="pb-3">Outstanding</th><th className="pb-3">Due</th><th className="pb-3">Status</th></tr></thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {data.invoices.map((invoice) => <tr key={invoice.public_id}><td className="py-4 font-medium">{invoice.invoice_number}</td><td>{invoice.account_name}</td><td>{invoice.currency} {invoice.total_amount}</td><td>{invoice.currency} {invoice.outstanding_amount}</td><td>{invoice.due_on ?? "Draft"}</td><td><Status value={invoice.status} /></td></tr>)}
                </tbody>
              </table>
              {!data.invoices.length ? <p className="py-8 text-sm text-[var(--muted)]">No subscription invoices have been created.</p> : null}
            </div>
          </section>
        ) : null}

        {tab === "support" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createTicket}>
              <h2 className="text-xl font-semibold">Create support ticket</h2>
              <div className="mt-5 space-y-3">
                <input className={inputClass} name="subject" placeholder="Issue subject" required />
                <textarea className={inputClass} name="description" placeholder="Issue description" required rows={5} />
                <input className={inputClass} defaultValue="general" name="category" placeholder="Category" />
                <select className={inputClass} defaultValue="medium" name="severity"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select>
                <button className="w-full rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50" disabled={busy || !primaryAccount} type="submit">{busy ? "Creating…" : "Create ticket"}</button>
              </div>
            </form>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Support queue</h2>
              <div className="mt-5 space-y-3">
                {openTickets.map((ticket) => <div className="rounded-xl border border-[var(--border)] p-4" key={ticket.public_id}><div className="flex items-start justify-between gap-4"><div><p className="font-semibold">{ticket.subject}</p><p className="mt-1 text-xs text-[var(--muted)]">{ticket.ticket_number} · {ticket.account_name}</p></div><Status value={ticket.severity} /></div><div className="mt-3 flex items-center justify-between text-sm"><Status value={ticket.status} /><span className="text-[var(--muted)]">Resolution due {new Date(ticket.resolution_due_at).toLocaleString()}</span></div></div>)}
                {!openTickets.length ? <p className="text-sm text-[var(--muted)]">No open support tickets.</p> : null}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "adoption" ? (
          <section className="grid gap-6 lg:grid-cols-2">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Latest adoption evidence</h2>{latestAdoption ? <dl className="mt-5 grid grid-cols-2 gap-5"><div><dt className="text-sm text-[var(--muted)]">Captured</dt><dd className="mt-1 font-semibold">{latestAdoption.captured_on}</dd></div><div><dt className="text-sm text-[var(--muted)]">Active users</dt><dd className="mt-1 text-2xl font-semibold">{latestAdoption.active_users}</dd></div><div><dt className="text-sm text-[var(--muted)]">Active projects</dt><dd className="mt-1 text-2xl font-semibold">{latestAdoption.active_projects}</dd></div><div><dt className="text-sm text-[var(--muted)]">Support tickets</dt><dd className="mt-1 text-2xl font-semibold">{latestAdoption.support_ticket_count}</dd></div></dl> : <p className="mt-5 text-sm text-[var(--muted)]">No adoption snapshot is available.</p>}</article>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Feature utilization</h2><div className="mt-5 space-y-3">{latestAdoption ? Object.entries(latestAdoption.feature_utilization).map(([key, value]) => <div className="flex items-center justify-between rounded-xl border border-[var(--border)] px-4 py-3" key={key}><span className="font-medium">{label(key)}</span><span className="text-sm text-[var(--muted)]">{String(value)}%</span></div>) : null}</div></article>
          </section>
        ) : null}
      </div>
    </main>
  );
}
