"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

type Employee = {
  public_id: string;
  user_public_id: string;
  employee_number: string;
  display_name: string;
  email: string;
  job_title: string;
};
type Department = {
  public_id: string;
  code: string;
  name: string;
  manager_name: string | null;
  cost_code: string;
  status: string;
};
type Contract = {
  public_id: string;
  employee_name: string;
  department_name: string;
  contract_number: string;
  position_title: string;
  employment_type: string;
  currency: string;
  annual_compensation: string;
  pay_frequency: string;
  status: string;
};
type LeavePolicy = {
  public_id: string;
  code: string;
  name: string;
  leave_type: string;
  annual_days: string;
};
type LeaveBalance = {
  public_id: string;
  employee_name: string;
  policy_public_id: string;
  policy_name: string;
  period_year: number;
  available_days: string;
  taken_days: string;
};
type LeaveRequest = {
  public_id: string;
  employee_name: string;
  policy_name: string;
  leave_type: string;
  start_on: string;
  end_on: string;
  requested_days: string;
  reason: string;
  status: string;
  version: number;
};
type Timesheet = {
  public_id: string;
  employee_name: string;
  week_start: string;
  total_hours: string;
  status: string;
  version: number;
  lines: Array<{ public_id: string; work_date: string; project_name: string | null; hours: string; description: string }>;
};
type PayrollRun = {
  public_id: string;
  code: string;
  period_start: string;
  period_end: string;
  currency: string;
  status: string;
  gross_total: string;
  deduction_total: string;
  net_total: string;
  entry_count: number;
  version: number;
};

export type PeopleopsPortfolio = {
  current_user_public_id: string;
  current_membership_public_id: string;
  summary: {
    employees: number;
    active_contracts: number;
    departments: number;
    pending_leave_requests: number;
    pending_timesheets: number;
    available_leave_days: string;
    payroll_runs: number;
    latest_payroll_status: string;
    latest_payroll_net: string;
    currency: string;
  };
  employees: Employee[];
  departments: Department[];
  contracts: Contract[];
  leave_policies: LeavePolicy[];
  leave_balances: LeaveBalance[];
  leave_requests: LeaveRequest[];
  timesheets: Timesheet[];
  payroll_runs: PayrollRun[];
};

type Tab = "people" | "leave" | "timesheets" | "payroll";

const inputClass =
  "w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-700";

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function Status({ value }: Readonly<{ value: string }>) {
  const positive = ["active", "approved", "posted"].includes(value);
  const negative = ["rejected", "cancelled", "ended"].includes(value);
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${positive ? "bg-emerald-100 text-emerald-900" : negative ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-900"}`}>
      {label(value)}
    </span>
  );
}

export function PeopleOperationsWorkspace({ initialData }: Readonly<{ initialData: PeopleopsPortfolio }>) {
  const [data, setData] = useState(initialData);
  const [tab, setTab] = useState<Tab>("people");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const primaryEmployee = data.employees.find((employee) => employee.user_public_id === data.current_user_public_id);
  const balances = useMemo(() => data.leave_balances.filter((item) => item.employee_name === primaryEmployee?.display_name), [data.leave_balances, primaryEmployee]);

  async function refresh() {
    const response = await fetch("/api/peopleops/portfolio", { cache: "no-store" });
    if (response.ok) setData((await response.json()) as PeopleopsPortfolio);
  }

  async function createLeave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!primaryEmployee) {
      setMessage("No employee profile is linked to your current membership.");
      return;
    }
    setBusy(true);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/peopleops/leave-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        employee_public_id: primaryEmployee.public_id,
        policy_public_id: String(form.get("policy")),
        start_on: String(form.get("start_on")),
        end_on: String(form.get("end_on")),
        requested_days: String(form.get("requested_days")),
        reason: String(form.get("reason")),
      }),
    });
    const result = (await response.json().catch(() => ({}))) as { message?: string; detail?: string };
    setMessage(response.ok ? "Leave request submitted." : result.message ?? result.detail ?? "Leave request failed.");
    if (response.ok) {
      event.currentTarget.reset();
      await refresh();
    }
    setBusy(false);
  }

  async function createTimesheet(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!primaryEmployee) {
      setMessage("No employee profile is linked to your current membership.");
      return;
    }
    setBusy(true);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/peopleops/timesheets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        employee_public_id: primaryEmployee.public_id,
        week_start: String(form.get("week_start")),
        lines: [{
          work_date: String(form.get("work_date")),
          hours: String(form.get("hours")),
          description: String(form.get("description")),
        }],
      }),
    });
    const result = (await response.json().catch(() => ({}))) as { message?: string; detail?: string };
    setMessage(response.ok ? "Timesheet submitted." : result.message ?? result.detail ?? "Timesheet submission failed.");
    if (response.ok) {
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
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">MPSqre Build360 · People Operations</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">People, leave, timesheets and payroll</h1>
            <p className="mt-2 text-sm text-[var(--muted)]">Employee administration · maker-checker controls · governed payroll evidence</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-900">Phase 20 active</span>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/platform">Platform</Link>
          </div>
        </header>

        <section className="grid gap-4 py-7 sm:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-sm text-[var(--muted)]">Employees</p><p className="mt-2 text-3xl font-semibold">{data.summary.employees}</p><p className="mt-1 text-xs text-[var(--muted)]">{data.summary.active_contracts} active contracts</p></article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-sm text-[var(--muted)]">Leave available</p><p className="mt-2 text-3xl font-semibold">{data.summary.available_leave_days}</p><p className="mt-1 text-xs text-[var(--muted)]">{data.summary.pending_leave_requests} pending requests</p></article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-sm text-[var(--muted)]">Timesheets</p><p className="mt-2 text-3xl font-semibold">{data.timesheets.length}</p><p className="mt-1 text-xs text-[var(--muted)]">{data.summary.pending_timesheets} pending approvals</p></article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><p className="text-sm text-[var(--muted)]">Latest payroll</p><p className="mt-2 text-3xl font-semibold">{data.summary.currency} {data.summary.latest_payroll_net}</p><p className="mt-1 text-xs text-[var(--muted)]">{label(data.summary.latest_payroll_status)}</p></article>
        </section>

        <div className="mb-6 flex flex-wrap gap-2">
          {(["people", "leave", "timesheets", "payroll"] as Tab[]).map((item) => (
            <button className={`rounded-xl px-4 py-2 text-sm font-semibold ${tab === item ? "bg-emerald-950 text-white" : "border border-[var(--border)] bg-white"}`} key={item} onClick={() => setTab(item)} type="button">{label(item)}</button>
          ))}
        </div>

        {message ? <div className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{message}</div> : null}

        {tab === "people" ? (
          <section className="grid gap-6 lg:grid-cols-2">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Employee register</h2><div className="mt-5 space-y-3">{data.employees.map((employee) => <div className="rounded-xl border border-[var(--border)] p-4" key={employee.public_id}><p className="font-semibold">{employee.display_name}</p><p className="mt-1 text-sm text-[var(--muted)]">{employee.employee_number} · {employee.job_title}</p><p className="mt-1 text-xs text-[var(--muted)]">{employee.email}</p></div>)}</div></article>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Organization structure</h2><div className="mt-5 space-y-3">{data.departments.map((department) => <div className="flex items-center justify-between rounded-xl border border-[var(--border)] p-4" key={department.public_id}><div><p className="font-semibold">{department.name}</p><p className="mt-1 text-xs text-[var(--muted)]">{department.code} · {department.cost_code || "No cost code"}</p></div><Status value={department.status} /></div>)}</div></article>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm lg:col-span-2"><h2 className="text-xl font-semibold">Employment contracts</h2><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[800px] text-left text-sm"><thead className="text-[var(--muted)]"><tr><th className="pb-3">Contract</th><th className="pb-3">Employee</th><th className="pb-3">Department</th><th className="pb-3">Type</th><th className="pb-3">Pay frequency</th><th className="pb-3">Status</th></tr></thead><tbody className="divide-y divide-[var(--border)]">{data.contracts.map((contract) => <tr key={contract.public_id}><td className="py-4 font-medium">{contract.contract_number}</td><td>{contract.employee_name}</td><td>{contract.department_name}</td><td>{label(contract.employment_type)}</td><td>{label(contract.pay_frequency)}</td><td><Status value={contract.status} /></td></tr>)}</tbody></table></div></article>
          </section>
        ) : null}

        {tab === "leave" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createLeave}><h2 className="text-xl font-semibold">Request leave</h2><div className="mt-5 space-y-3"><select className={inputClass} name="policy" required><option value="">Select leave policy</option>{data.leave_policies.map((policy) => <option key={policy.public_id} value={policy.public_id}>{policy.name}</option>)}</select><input className={inputClass} name="start_on" required type="date" /><input className={inputClass} name="end_on" required type="date" /><input className={inputClass} min="0.25" name="requested_days" placeholder="Requested days" required step="0.25" type="number" /><textarea className={inputClass} name="reason" placeholder="Reason" rows={3} /><button className="w-full rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60" disabled={busy} type="submit">Submit leave request</button></div></form>
            <div className="space-y-6"><article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Leave balances</h2><div className="mt-5 grid gap-3 sm:grid-cols-3">{balances.map((balance) => <div className="rounded-xl border border-[var(--border)] p-4" key={balance.public_id}><p className="text-sm text-[var(--muted)]">{balance.policy_name}</p><p className="mt-2 text-2xl font-semibold">{balance.available_days}</p><p className="mt-1 text-xs text-[var(--muted)]">Taken {balance.taken_days}</p></div>)}</div></article><article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Leave request register</h2><div className="mt-5 space-y-3">{data.leave_requests.map((request) => <div className="flex items-start justify-between gap-4 rounded-xl border border-[var(--border)] p-4" key={request.public_id}><div><p className="font-semibold">{request.employee_name} · {request.policy_name}</p><p className="mt-1 text-sm text-[var(--muted)]">{request.start_on} → {request.end_on} · {request.requested_days} days</p><p className="mt-1 text-xs text-[var(--muted)]">{request.reason || "No reason provided"}</p></div><Status value={request.status} /></div>)}{!data.leave_requests.length ? <p className="text-sm text-[var(--muted)]">No leave requests created.</p> : null}</div></article></div>
          </section>
        ) : null}

        {tab === "timesheets" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createTimesheet}><h2 className="text-xl font-semibold">Submit weekly time</h2><div className="mt-5 space-y-3"><input className={inputClass} name="week_start" required type="date" /><input className={inputClass} name="work_date" required type="date" /><input className={inputClass} max="24" min="0.25" name="hours" placeholder="Hours" required step="0.25" type="number" /><textarea className={inputClass} name="description" placeholder="Work description" rows={3} /><button className="w-full rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60" disabled={busy} type="submit">Submit timesheet</button></div></form>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Timesheet register</h2><div className="mt-5 space-y-3">{data.timesheets.map((timesheet) => <div className="flex items-center justify-between gap-4 rounded-xl border border-[var(--border)] p-4" key={timesheet.public_id}><div><p className="font-semibold">{timesheet.employee_name}</p><p className="mt-1 text-sm text-[var(--muted)]">Week of {timesheet.week_start} · {timesheet.total_hours} hours · {timesheet.lines.length} lines</p></div><Status value={timesheet.status} /></div>)}{!data.timesheets.length ? <p className="text-sm text-[var(--muted)]">No timesheets submitted.</p> : null}</div></article>
          </section>
        ) : null}

        {tab === "payroll" ? (
          <section className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm"><div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-xl font-semibold">Payroll evidence register</h2><p className="mt-1 text-sm text-[var(--muted)]">Administrative payroll evidence only; statutory payroll rules require jurisdiction-specific configuration.</p></div></div><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[800px] text-left text-sm"><thead className="text-[var(--muted)]"><tr><th className="pb-3">Run</th><th className="pb-3">Period</th><th className="pb-3">Gross</th><th className="pb-3">Deductions</th><th className="pb-3">Net</th><th className="pb-3">Entries</th><th className="pb-3">Status</th></tr></thead><tbody className="divide-y divide-[var(--border)]">{data.payroll_runs.map((run) => <tr key={run.public_id}><td className="py-4 font-medium">{run.code}</td><td>{run.period_start} → {run.period_end}</td><td>{run.currency} {run.gross_total}</td><td>{run.currency} {run.deduction_total}</td><td>{run.currency} {run.net_total}</td><td>{run.entry_count}</td><td><Status value={run.status} /></td></tr>)}</tbody></table></div></section>
        ) : null}
      </div>
    </main>
  );
}
