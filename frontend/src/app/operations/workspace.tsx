"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

export type Company = {
  public_id: string;
  code: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
};
export type ReportingSummary = {
  active_metrics: number;
  saved_reports: number;
  queued_runs: number;
  completed_runs: number;
  failed_runs: number;
};
export type Metric = {
  public_id: string;
  code: string;
  name: string;
  domain_code: string;
  calculation_code: string;
  unit_code: string;
  data_classification: string;
  is_active: boolean;
  version: number;
};
export type SavedReport = {
  public_id: string;
  code: string;
  name: string;
  description: string;
  report_type: string;
  metric_codes: string[];
  visibility: string;
  default_export_format: string;
  schedule_expression: string;
  version: number;
};
export type ReportRun = {
  public_id: string;
  report_code: string;
  status: string;
  export_format: string;
  row_count: number;
  completed_at: string | null;
  expires_at: string | null;
  error_message: string;
  version: number;
  artifact: {
    file_name: string;
    content_type: string;
    byte_size: number;
    sha256: string;
    download_count: number;
  } | null;
};
export type PortalSummary = {
  pending_invitations: number;
  active_grants: number;
  active_shares: number;
};
export type PortalInvitation = {
  public_id: string;
  email: string;
  portal_type: string;
  scope_type: string;
  scope_public_id: string | null;
  permission_codes: string[];
  status: string;
  expires_at: string;
  acceptance_token?: string;
  version: number;
  delivery: {
    public_id: string;
    channel: string;
    status: string;
    sent_at: string | null;
    delivered_at: string | null;
    suppression_reason: string;
    created_at: string;
  } | null;
};
export type PortalGrant = {
  public_id: string;
  user_public_id: string;
  portal_type: string;
  scope_type: string;
  scope_public_id: string | null;
  permission_codes: string[];
  effective_from: string;
  effective_to: string | null;
  revoked_at: string | null;
  revoke_reason: string;
  version: number;
};
export type PortalShare = {
  public_id: string;
  grant_public_id: string;
  entity_type: string;
  entity_public_id: string;
  access_level: string;
  expires_at: string | null;
  revoked_at: string | null;
  version: number;
};
export type DataopsSummary = {
  active_templates: number;
  pending_imports: number;
  open_privacy_requests: number;
  overdue_privacy_requests: number;
  active_retention_policies: number;
  recovery_checks_passed: number;
};
export type ImportTemplate = {
  public_id: string;
  code: string;
  name: string;
  destination_code: string;
  version: number;
  schema: { fields?: { name: string; required?: boolean; type?: string }[]; max_rows?: number };
  is_active: boolean;
};
export type ImportJob = {
  public_id: string;
  template: ImportTemplate;
  source_name: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  committed_rows: number;
  result_summary: Record<string, unknown>;
  version: number;
};
export type PrivacyRequest = {
  public_id: string;
  request_number: string;
  request_type: string;
  subject_type: string;
  subject_public_id: string;
  status: string;
  due_at: string;
  completed_at: string | null;
  resolution_summary: string;
  version: number;
};
export type RetentionPolicy = {
  public_id: string;
  record_type: string;
  retention_days: number;
  legal_hold_default: boolean;
  effective_from: string;
  is_active: boolean;
  version: number;
};
export type RecoveryVerification = {
  public_id: string;
  reference: string;
  scope: string;
  status: string;
  target_rpo_minutes: number;
  measured_rpo_minutes: number | null;
  target_rto_minutes: number;
  measured_rto_minutes: number | null;
  evidence_summary: string;
  version: number;
};

type Props = {
  company: Company;
  permissions: string[];
  initialReportingSummary: ReportingSummary | null;
  initialMetrics: Metric[];
  initialSavedReports: SavedReport[];
  initialReportRuns: ReportRun[];
  initialPortalSummary: PortalSummary | null;
  initialInvitations: PortalInvitation[];
  initialGrants: PortalGrant[];
  initialShares: PortalShare[];
  initialDataopsSummary: DataopsSummary | null;
  initialTemplates: ImportTemplate[];
  initialImports: ImportJob[];
  initialPrivacy: PrivacyRequest[];
  initialRetention: RetentionPolicy[];
  initialRecovery: RecoveryVerification[];
};
type ApiError = { message?: string; detail?: string };
type Tab = "reports" | "portals" | "imports" | "privacy" | "recovery";

async function api<T>(scope: "reporting" | "portal" | "dataops", path: string, init?: RequestInit) {
  const response = await fetch(`/api/operations/${scope}/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = (await response.json().catch(() => ({}))) as T & ApiError;
  if (!response.ok) {
    throw new Error(body.message ?? body.detail ?? "The operations request could not be completed.");
  }
  return body as T;
}

function Card({ label, value, note }: { label: string; value: number | string; note?: string }) {
  return (
    <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
      <p className="text-sm text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
      {note ? <p className="mt-2 text-xs text-[var(--muted)]">{note}</p> : null}
    </article>
  );
}

function Status({ value }: { value: string }) {
  return (
    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-slate-700">
      {value.replaceAll("_", " ")}
    </span>
  );
}

function Field({
  name,
  placeholder,
  type = "text",
  required = false,
}: {
  name: string;
  placeholder: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <input
      className="w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-sm"
      name={name}
      placeholder={placeholder}
      required={required}
      type={type}
    />
  );
}

export function OperationsWorkspace(props: Readonly<Props>) {
  const { company, permissions } = props;
  const [tab, setTab] = useState<Tab>("reports");
  const [reportingSummary, setReportingSummary] = useState(
    props.initialReportingSummary ?? {
      active_metrics: 0,
      saved_reports: 0,
      queued_runs: 0,
      completed_runs: 0,
      failed_runs: 0,
    },
  );
  const [metrics, setMetrics] = useState(props.initialMetrics);
  const [savedReports, setSavedReports] = useState(props.initialSavedReports);
  const [reportRuns, setReportRuns] = useState(props.initialReportRuns);
  const [portalSummary, setPortalSummary] = useState(
    props.initialPortalSummary ?? { pending_invitations: 0, active_grants: 0, active_shares: 0 },
  );
  const [invitations, setInvitations] = useState(props.initialInvitations);
  const [grants, setGrants] = useState(props.initialGrants);
  const [shares, setShares] = useState(props.initialShares);
  const [dataopsSummary, setDataopsSummary] = useState(
    props.initialDataopsSummary ?? {
      active_templates: 0,
      pending_imports: 0,
      open_privacy_requests: 0,
      overdue_privacy_requests: 0,
      active_retention_policies: 0,
      recovery_checks_passed: 0,
    },
  );
  const [templates, setTemplates] = useState(props.initialTemplates);
  const [imports, setImports] = useState(props.initialImports);
  const [privacy, setPrivacy] = useState(props.initialPrivacy);
  const [retention, setRetention] = useState(props.initialRetention);
  const [recovery, setRecovery] = useState(props.initialRecovery);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [latestInvitationToken, setLatestInvitationToken] = useState("");

  const defaultTemplateRows = useMemo(() => {
    const template = templates[0];
    if (!template?.schema.fields) return "[]";
    const row = Object.fromEntries(
      template.schema.fields.map((field) => [field.name, field.required ? "REQUIRED_VALUE" : ""]),
    );
    return JSON.stringify([row], null, 2);
  }, [templates]);

  async function refresh() {
    const [rs, m, sr, rr, ps, pi, pg, psh, ds, it, ij, pr, rp, rv] = await Promise.all([
      api<ReportingSummary>("reporting", "summary"),
      api<{ items: Metric[] }>("reporting", "metrics"),
      api<{ items: SavedReport[] }>("reporting", "saved"),
      api<{ items: ReportRun[] }>("reporting", "runs"),
      api<PortalSummary>("portal", "summary"),
      api<{ items: PortalInvitation[] }>("portal", "invitations"),
      api<{ items: PortalGrant[] }>("portal", "grants"),
      api<{ items: PortalShare[] }>("portal", "shares"),
      api<DataopsSummary>("dataops", "summary"),
      api<{ items: ImportTemplate[] }>("dataops", "templates"),
      api<{ items: ImportJob[] }>("dataops", "imports"),
      api<{ items: PrivacyRequest[] }>("dataops", "privacy"),
      api<{ items: RetentionPolicy[] }>("dataops", "retention"),
      api<{ items: RecoveryVerification[] }>("dataops", "recovery"),
    ]);
    setReportingSummary(rs);
    setMetrics(m.items);
    setSavedReports(sr.items);
    setReportRuns(rr.items);
    setPortalSummary(ps);
    setInvitations(pi.items);
    setGrants(pg.items);
    setShares(psh.items);
    setDataopsSummary(ds);
    setTemplates(it.items);
    setImports(ij.items);
    setPrivacy(pr.items);
    setRetention(rp.items);
    setRecovery(rv.items);
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
      setError(caught instanceof Error ? caught.message : "The operations request failed.");
    } finally {
      setBusy(false);
    }
  }

  async function executeReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api("reporting", "runs", {
        method: "POST",
        body: JSON.stringify({
          saved_report_public_id: form.get("saved_report_public_id"),
          export_format: form.get("export_format"),
          idempotency_key: `ui-${crypto.randomUUID()}`,
          parameters: {},
        }),
      });
    }, "Report executed and export integrity evidence created.");
  }

  async function createInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      const result = await api<PortalInvitation>("portal", "invitations", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          portal_type: form.get("portal_type"),
          scope_type: "company",
          scope_public_id: null,
          permission_codes: String(form.get("permission_codes") ?? "")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
          expires_in_days: Number(form.get("expires_in_days") ?? 7),
        }),
      });
      setLatestInvitationToken(result.acceptance_token ?? "");
      event.currentTarget.reset();
    }, "Portal invitation created. Communication Engine delivery is preferred; the one-time token remains a manual fallback.");
  }

  async function deliverInvitation(item: PortalInvitation, dispatchNow: boolean) {
    await run(async () => {
      await api("portal", `invitations/${item.public_id}/deliver`, {
        method: "POST",
        body: JSON.stringify({ dispatch_now: dispatchNow }),
      });
    }, dispatchNow
      ? "Invitation handed to the governed Communication Engine for dispatch."
      : "Invitation communication queued through the governed Communication Engine.");
  }

  async function createImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      const raw = String(form.get("rows") ?? "[]");
      const rows = JSON.parse(raw) as Record<string, unknown>[];
      await api("dataops", "imports", {
        method: "POST",
        body: JSON.stringify({
          template_public_id: form.get("template_public_id"),
          source_name: form.get("source_name"),
          idempotency_key: `ui-${crypto.randomUUID()}`,
          rows,
        }),
      });
    }, "Import preview completed. Review row errors before committing.");
  }

  async function commitImport(item: ImportJob) {
    await run(async () => {
      await api("dataops", `imports/${item.public_id}/commit`, {
        method: "POST",
        body: JSON.stringify({ expected_version: item.version, allow_partial: false }),
      });
    }, "Validated import rows committed through domain services.");
  }

  async function createPrivacy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api("dataops", "privacy", {
        method: "POST",
        body: JSON.stringify({
          request_number: form.get("request_number"),
          request_type: form.get("request_type"),
          subject_type: form.get("subject_type"),
          subject_public_id: form.get("subject_public_id"),
          due_in_days: Number(form.get("due_in_days") ?? 30),
        }),
      });
      event.currentTarget.reset();
    }, "Privacy request registered with a governed response deadline.");
  }

  async function createRetention(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api("dataops", "retention", {
        method: "POST",
        body: JSON.stringify({
          record_type: form.get("record_type"),
          retention_days: Number(form.get("retention_days")),
          legal_hold_default: form.get("legal_hold_default") === "on",
        }),
      });
      event.currentTarget.reset();
    }, "A new effective retention-policy version was published.");
  }

  async function createRecovery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api("dataops", "recovery", {
        method: "POST",
        body: JSON.stringify({
          reference: form.get("reference"),
          scope: form.get("scope"),
          target_rpo_minutes: Number(form.get("target_rpo_minutes")),
          target_rto_minutes: Number(form.get("target_rto_minutes")),
        }),
      });
      event.currentTarget.reset();
    }, "Recovery verification exercise added to the operational register.");
  }

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
              MPSqre Build360 · Operational maturity
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              Reports, portals and data governance
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {company.display_name} · {company.code} · governed exports · bounded external access
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-900">
              Phase 10 active
            </span>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/portal">
              External portal
            </Link>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/platform">
              Platform
            </Link>
          </div>
        </header>

        <section className="grid gap-4 py-7 sm:grid-cols-2 xl:grid-cols-4">
          <Card label="Governed metrics" value={reportingSummary.active_metrics} />
          <Card label="Completed report runs" value={reportingSummary.completed_runs} />
          <Card label="Active portal grants" value={portalSummary.active_grants} />
          <Card
            label="Open privacy requests"
            value={dataopsSummary.open_privacy_requests}
            note={`${dataopsSummary.overdue_privacy_requests} overdue`}
          />
        </section>

        <nav className="mb-6 flex flex-wrap gap-2" aria-label="Operations sections">
          {([
            ["reports", "Reports"],
            ["portals", "Portals"],
            ["imports", "Import centre"],
            ["privacy", "Privacy & retention"],
            ["recovery", "Recovery evidence"],
          ] as [Tab, string][]).map(([value, label]) => (
            <button
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-[var(--brand)] text-white" : "border border-[var(--border)] bg-white"}`}
              key={value}
              onClick={() => setTab(value)}
              type="button"
            >
              {label}
            </button>
          ))}
        </nav>

        {error ? <p className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</p> : null}
        {notice ? <p className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</p> : null}

        {tab === "reports" ? (
          <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={executeReport}>
              <h2 className="text-xl font-semibold">Run governed report</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">Exports are integrity checked and expire automatically.</p>
              <select className="mt-5 w-full rounded-xl border border-[var(--border)] px-3 py-2.5" name="saved_report_public_id" required>
                <option value="">Select saved report</option>
                {savedReports.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}
              </select>
              <select className="mt-3 w-full rounded-xl border border-[var(--border)] px-3 py-2.5" name="export_format" defaultValue="pdf">
                <option value="csv">CSV</option>
                <option value="xlsx">Excel</option>
                <option value="pdf">PDF</option>
              </select>
              <button className="mt-4 w-full rounded-xl bg-[var(--brand)] px-4 py-3 font-semibold text-white disabled:opacity-60" disabled={busy} type="submit">
                Execute report
              </button>
              <div className="mt-6 border-t border-[var(--border)] pt-5">
                <p className="text-sm font-semibold">Metric catalogue</p>
                <ul className="mt-3 space-y-2 text-sm text-[var(--muted)]">
                  {metrics.slice(0, 8).map((item) => <li key={item.public_id}>{item.name} · {item.data_classification}</li>)}
                </ul>
              </div>
            </form>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-xl font-semibold">Report execution register</h2>
                <span className="text-sm text-[var(--muted)]">{reportRuns.length} visible</span>
              </div>
              {reportRuns.length ? (
                <div className="mt-5 overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <thead className="text-[var(--muted)]"><tr><th className="pb-3">Report</th><th>Status</th><th>Format</th><th>Rows</th><th>Artifact</th></tr></thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {reportRuns.map((item) => (
                        <tr key={item.public_id}>
                          <td className="py-4 font-medium">{item.report_code}</td>
                          <td><Status value={item.status} /></td>
                          <td className="uppercase">{item.export_format}</td>
                          <td>{item.row_count}</td>
                          <td>
                            {item.artifact ? (
                              <a className="font-semibold text-[var(--brand)] underline" href={`/api/operations/reporting/runs/${item.public_id}/download`}>
                                Download · {Math.ceil(item.artifact.byte_size / 1024)} KB
                              </a>
                            ) : item.error_message || "Pending"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="mt-5 text-sm text-[var(--muted)]">No report has been executed.</p>}
            </article>
          </section>
        ) : null}

        {tab === "portals" ? (
          <section className="grid gap-6 lg:grid-cols-[380px_1fr]">
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createInvitation}>
              <h2 className="text-xl font-semibold">Invite external participant</h2>
              <div className="mt-5 space-y-3">
                <Field name="email" placeholder="External user email" type="email" required />
                <select className="w-full rounded-xl border border-[var(--border)] px-3 py-2.5" name="portal_type" defaultValue="client">
                  <option value="client">Client portal</option>
                  <option value="vendor">Vendor portal</option>
                </select>
                <Field name="permission_codes" placeholder="portal.project.view, portal.document.view, portal.estimate.view" required />
                <Field name="expires_in_days" placeholder="Expiry days" type="number" required />
              </div>
              <button className="mt-4 w-full rounded-xl bg-[var(--brand)] px-4 py-3 font-semibold text-white" disabled={busy} type="submit">Create invitation</button>
              {latestInvitationToken ? (
                <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <p className="text-sm font-semibold text-amber-900">One-time acceptance token</p>
                  <code className="mt-2 block break-all text-xs">{latestInvitationToken}</code>
                  <p className="mt-3 text-xs text-amber-900">
                    Manual fallback path (Communication Engine delivery uses a tokenless invitation-ID link):
                  </p>
                  <code className="mt-1 block break-all text-xs">
                    /portal/accept?token={encodeURIComponent(latestInvitationToken)}
                  </code>
                  <Link
                    className="mt-3 inline-block text-sm font-semibold text-amber-950 underline"
                    href={`/portal/accept?token=${encodeURIComponent(latestInvitationToken)}`}
                  >
                    Test invitation acceptance
                  </Link>
                </div>
              ) : null}
            </form>
            <div className="space-y-6">
              <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold">Invitation register</h2>
                <ul className="mt-5 divide-y divide-[var(--border)]">
                  {invitations.map((item) => (
                    <li className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between" key={item.public_id}>
                      <div className="min-w-0">
                        <p className="font-medium">{item.email}</p>
                        <p className="text-sm text-[var(--muted)]">{item.portal_type} · {item.scope_type} · expires {new Date(item.expires_at).toLocaleDateString()}</p>
                        {item.delivery ? (
                          <p className="mt-1 text-xs text-[var(--muted)]">
                            Communication: <span className="font-semibold">{item.delivery.status}</span>
                            {item.delivery.suppression_reason ? ` · ${item.delivery.suppression_reason}` : ""}
                          </p>
                        ) : <p className="mt-1 text-xs text-[var(--muted)]">Communication not queued yet.</p>}
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Status value={item.status} />
                        {item.status === "pending" && permissions.includes("communication.request.create") ? (
                          <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold" disabled={busy} onClick={() => deliverInvitation(item, false)} type="button">Queue email</button>
                        ) : null}
                        {item.status === "pending" && permissions.includes("communication.request.create") && permissions.includes("communication.request.dispatch") ? (
                          <button className="rounded-lg bg-[var(--brand)] px-3 py-2 text-xs font-semibold text-white" disabled={busy} onClick={() => deliverInvitation(item, true)} type="button">Send now</button>
                        ) : null}
                      </div>
                    </li>
                  ))}
                  {!invitations.length ? <li className="py-4 text-sm text-[var(--muted)]">No external invitation has been issued.</li> : null}
                </ul>
              </article>
              <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold">Active access grants</h2>
                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  {grants.filter((item) => !item.revoked_at).map((item) => (
                    <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                      <div className="flex items-center justify-between"><p className="font-medium capitalize">{item.portal_type} portal</p><Status value={item.scope_type} /></div>
                      <p className="mt-2 break-all text-xs text-[var(--muted)]">User {item.user_public_id}</p>
                      <p className="mt-3 text-sm">{item.permission_codes.join(", ")}</p>
                    </div>
                  ))}
                </div>
                <p className="mt-4 text-sm text-[var(--muted)]">{shares.length} governed record shares registered.</p>
              </article>
            </div>
          </section>
        ) : null}

        {tab === "imports" ? (
          <section className="grid gap-6 lg:grid-cols-[420px_1fr]">
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createImport}>
              <h2 className="text-xl font-semibold">Validate import preview</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">Rows are staged and validated before any business record is committed.</p>
              <select className="mt-5 w-full rounded-xl border border-[var(--border)] px-3 py-2.5" name="template_public_id" required>
                <option value="">Select import template</option>
                {templates.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}
              </select>
              <div className="mt-3"><Field name="source_name" placeholder="Source filename or batch name" required /></div>
              <textarea className="mt-3 min-h-60 w-full rounded-xl border border-[var(--border)] p-3 font-mono text-xs" defaultValue={defaultTemplateRows} name="rows" required />
              <button className="mt-4 w-full rounded-xl bg-[var(--brand)] px-4 py-3 font-semibold text-white" disabled={busy} type="submit">Run validation preview</button>
            </form>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Import job register</h2>
              <div className="mt-5 space-y-3">
                {imports.map((item) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}>
                    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-medium">{item.source_name}</p><p className="text-sm text-[var(--muted)]">{item.template.name}</p></div><Status value={item.status} /></div>
                    <div className="mt-4 grid grid-cols-4 gap-2 text-center text-sm"><div><b>{item.total_rows}</b><br />Total</div><div><b>{item.valid_rows}</b><br />Valid</div><div><b>{item.error_rows}</b><br />Errors</div><div><b>{item.committed_rows}</b><br />Committed</div></div>
                    {item.status === "validated" && permissions.includes("dataops.import.commit") ? (
                      <button className="mt-4 rounded-lg bg-[var(--brand)] px-3 py-2 text-sm font-semibold text-white" disabled={busy} onClick={() => commitImport(item)} type="button">Commit valid rows</button>
                    ) : null}
                  </div>
                ))}
                {!imports.length ? <p className="text-sm text-[var(--muted)]">No import preview has been created.</p> : null}
              </div>
            </article>
          </section>
        ) : null}

        {tab === "privacy" ? (
          <section className="grid gap-6 lg:grid-cols-2">
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createPrivacy}>
              <h2 className="text-xl font-semibold">Register privacy request</h2>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <Field name="request_number" placeholder="Request number" required />
                <select className="rounded-xl border border-[var(--border)] px-3 py-2.5" name="request_type" defaultValue="access"><option value="access">Access</option><option value="rectification">Rectification</option><option value="deletion">Deletion</option><option value="restriction">Restriction</option></select>
                <Field name="subject_type" placeholder="Subject type, e.g. user" required />
                <Field name="subject_public_id" placeholder="Subject public UUID" required />
                <Field name="due_in_days" placeholder="Due in days" type="number" required />
              </div>
              <button className="mt-4 rounded-xl bg-[var(--brand)] px-4 py-3 font-semibold text-white" disabled={busy} type="submit">Register request</button>
              <div className="mt-6 space-y-3">
                {privacy.map((item) => <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}><div className="flex items-center justify-between"><p className="font-medium">{item.request_number} · {item.request_type}</p><Status value={item.status} /></div><p className="mt-2 text-sm text-[var(--muted)]">Due {new Date(item.due_at).toLocaleString()} · {item.subject_type}</p></div>)}
              </div>
            </form>
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createRetention}>
              <h2 className="text-xl font-semibold">Publish retention policy</h2>
              <div className="mt-5 space-y-3">
                <Field name="record_type" placeholder="Record type, e.g. project.document" required />
                <Field name="retention_days" placeholder="Retention days" type="number" required />
                <label className="flex items-center gap-2 text-sm"><input name="legal_hold_default" type="checkbox" /> Default legal hold</label>
              </div>
              <button className="mt-4 rounded-xl bg-[var(--brand)] px-4 py-3 font-semibold text-white" disabled={busy} type="submit">Publish version</button>
              <ul className="mt-6 divide-y divide-[var(--border)]">
                {retention.map((item) => <li className="flex items-center justify-between py-3" key={item.public_id}><div><p className="font-medium">{item.record_type}</p><p className="text-sm text-[var(--muted)]">{item.retention_days} days · v{item.version}</p></div>{item.legal_hold_default ? <Status value="legal hold" /> : null}</li>)}
              </ul>
            </form>
          </section>
        ) : null}

        {tab === "recovery" ? (
          <section className="grid gap-6 lg:grid-cols-[380px_1fr]">
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createRecovery}>
              <h2 className="text-xl font-semibold">Plan recovery verification</h2>
              <div className="mt-5 space-y-3">
                <Field name="reference" placeholder="Exercise reference" required />
                <select className="w-full rounded-xl border border-[var(--border)] px-3 py-2.5" name="scope" defaultValue="restore"><option value="backup">Backup</option><option value="restore">Restore</option><option value="rollback">Rollback</option></select>
                <Field name="target_rpo_minutes" placeholder="Target RPO minutes" type="number" required />
                <Field name="target_rto_minutes" placeholder="Target RTO minutes" type="number" required />
              </div>
              <button className="mt-4 w-full rounded-xl bg-[var(--brand)] px-4 py-3 font-semibold text-white" disabled={busy} type="submit">Create exercise</button>
            </form>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Recovery evidence register</h2>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {recovery.map((item) => <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}><div className="flex items-center justify-between"><p className="font-medium">{item.reference}</p><Status value={item.status} /></div><p className="mt-2 text-sm text-[var(--muted)]">{item.scope} · RPO {item.measured_rpo_minutes ?? "—"}/{item.target_rpo_minutes} min · RTO {item.measured_rto_minutes ?? "—"}/{item.target_rto_minutes} min</p></div>)}
              </div>
            </article>
          </section>
        ) : null}
      </div>
    </main>
  );
}
