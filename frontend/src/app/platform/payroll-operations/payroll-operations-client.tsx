"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import styles from "./payroll-operations.module.css";

type PayrollRun = {
  public_id: string;
  period_code: string;
  policy_code: string;
  policy_version: number;
  run_number: number;
  run_type_code: string;
  status_code: string;
  currency: string;
  version: number;
  gross_amount: string;
  deduction_amount: string;
  employer_cost_amount: string;
  net_amount: string;
  employee_count: number;
  exception_count: number;
  calculated_at: string | null;
  approved_at: string | null;
  locked_at: string | null;
  created_at: string;
  updated_at: string;
};

type PayrollException = {
  public_id: string;
  run_public_id: string;
  period_code: string;
  employee_public_id: string | null;
  exception_code: string;
  severity_code: string;
  status_code: string;
  message: string;
  due_at: string | null;
  created_at: string;
};

type PayrollApproval = {
  public_id: string;
  run_public_id: string;
  period_code: string;
  step_code: string;
  status_code: string;
  requested_from_membership_public_id: string;
  requested_at: string;
  due_at: string | null;
};

type PayrollOverview = {
  generated_at: string;
  company: {
    public_id: string;
    code: string;
    display_name: string;
    locale: string;
    timezone: string;
    currency: string;
  };
  summary: {
    published_policy_count: number;
    period_count: number;
    run_count: number;
    open_exception_count: number;
    pending_approval_count: number;
    latest_employee_count: number;
    latest_net_amount: string;
    latest_currency: string;
  };
  policies: Array<{
    public_id: string;
    code: string;
    name: string;
    version: number;
    status_code: string;
    locale_code: string;
    currency: string;
    effective_from: string;
    effective_to: string | null;
    published_at: string;
  }>;
  periods: Array<{
    public_id: string;
    code: string;
    starts_on: string;
    ends_on: string;
    payment_due_on: string;
    status_code: string;
    lock_version: number;
  }>;
  latest_run: PayrollRun | null;
  recent_runs: PayrollRun[];
  open_exceptions: PayrollException[];
  pending_approvals: PayrollApproval[];
  exception_severity: Array<{ severity_code: string; count: number }>;
  governance: {
    workflow_source: string;
    statutory_formulae_hardcoded: boolean;
    locked_runs_mutable: boolean;
    raw_bank_data_exposed: boolean;
    maker_checker_supported: boolean;
  };
};

type ErrorPayload = {
  message?: string;
  detail?: string;
  code?: string;
};

function formatMoney(value: string, currency: string, locale: string) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return `${currency} ${value}`;
  }
  try {
    return new Intl.NumberFormat(locale || "en-IN", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString()}`;
  }
}

function formatDate(value: string | null, locale: string) {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale || "en-IN", {
    dateStyle: "medium",
  }).format(date);
}

function friendlyCode(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
}

function statusTone(statusCode: string) {
  const status = statusCode.toUpperCase();
  if (["APPROVED", "LOCKED", "PAID", "COMPLETED", "PUBLISHED"].includes(status)) {
    return styles.toneSuccess;
  }
  if (["FAILED", "REJECTED", "CRITICAL", "BLOCKED"].includes(status)) {
    return styles.toneDanger;
  }
  if (["PENDING_APPROVAL", "CALCULATED", "HIGH", "WARNING"].includes(status)) {
    return styles.toneWarning;
  }
  return styles.toneNeutral;
}

function MetricCard({
  eyebrow,
  value,
  detail,
}: {
  eyebrow: string;
  value: string | number;
  detail: string;
}) {
  return (
    <article className={styles.metricCard}>
      <p>{eyebrow}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

function EmptyState({ children }: { children: string }) {
  return <div className={styles.emptyState}>{children}</div>;
}

export function PayrollOperationsClient() {
  const [overview, setOverview] = useState<PayrollOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal, refresh = false) => {
    if (refresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const response = await fetch(
        "/api/platform/payroll-operations/overview",
        { cache: "no-store", signal },
      );
      const payload = (await response.json().catch(() => ({}))) as
        | PayrollOverview
        | ErrorPayload;
      if (!response.ok) {
        const failure = payload as ErrorPayload;
        throw new Error(
          failure.message || failure.detail || "Payroll operations could not be loaded.",
        );
      }
      setOverview(payload as PayrollOverview);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") {
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Payroll operations could not be loaded.",
      );
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void load(controller.signal);
    });
    return () => controller.abort();
  }, [load]);

  const severityText = useMemo(() => {
    if (!overview?.exception_severity.length) return "No unresolved severity signals";
    return overview.exception_severity
      .map((entry) => `${friendlyCode(entry.severity_code)} ${entry.count}`)
      .join(" · ");
  }, [overview]);

  if (isLoading && !overview) {
    return (
      <main className={styles.page} aria-busy="true">
        <div className={styles.loadingHero} />
        <div className={styles.loadingGrid}>
          {Array.from({ length: 4 }).map((_, index) => (
            <div className={styles.loadingCard} key={index} />
          ))}
        </div>
        <div className={styles.loadingPanel} />
      </main>
    );
  }

  if (!overview) {
    return (
      <main className={styles.page}>
        <section className={styles.failurePanel}>
          <div className={styles.failureIcon}>!</div>
          <div>
            <p className={styles.kicker}>Payroll operations unavailable</p>
            <h1>The governed payroll workspace could not be opened.</h1>
            <p>{error || "Please retry after checking the API and tenant session."}</p>
            <button type="button" onClick={() => void load()}>
              Retry workspace
            </button>
          </div>
        </section>
      </main>
    );
  }

  const { company, summary } = overview;

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div>
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 21</p>
          <h1>Payroll operations</h1>
          <p className={styles.heroText}>
            Govern payroll periods, controlled runs, maker-checker approvals,
            exceptions and downstream exports from one tenant-safe command centre.
          </p>
          <div className={styles.heroMeta}>
            <span>{company.display_name}</span>
            <span>{company.currency}</span>
            <span>{company.timezone}</span>
          </div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.activeBadge}>PHASE 21 PAYROLL OPERATIONS ACTIVE</span>
          <button
            className={styles.refreshButton}
            disabled={isRefreshing}
            onClick={() => void load(undefined, true)}
            type="button"
          >
            {isRefreshing ? "Refreshing…" : "Refresh control room"}
          </button>
        </div>
      </section>

      {error ? (
        <div className={styles.staleNotice} role="status">
          Refresh failed. Showing the last successful payroll snapshot. {error}
        </div>
      ) : null}

      <section className={styles.metrics} aria-label="Payroll operating metrics">
        <MetricCard
          eyebrow="Latest net payroll"
          value={formatMoney(
            summary.latest_net_amount,
            summary.latest_currency,
            company.locale,
          )}
          detail={`${summary.latest_employee_count} employees in latest run`}
        />
        <MetricCard
          eyebrow="Pending approvals"
          value={summary.pending_approval_count}
          detail="Maker-checker decisions awaiting action"
        />
        <MetricCard
          eyebrow="Open exceptions"
          value={summary.open_exception_count}
          detail={severityText}
        />
        <MetricCard
          eyebrow="Published policies"
          value={summary.published_policy_count}
          detail={`${summary.period_count} periods · ${summary.run_count} runs`}
        />
      </section>

      <section className={styles.commandGrid}>
        <article className={styles.primaryPanel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Current operating position</p>
              <h2>Latest payroll run</h2>
            </div>
            {overview.latest_run ? (
              <span
                className={`${styles.statusPill} ${statusTone(
                  overview.latest_run.status_code,
                )}`}
              >
                {friendlyCode(overview.latest_run.status_code)}
              </span>
            ) : null}
          </header>

          {overview.latest_run ? (
            <div className={styles.latestRun}>
              <div className={styles.runIdentity}>
                <span>Period {overview.latest_run.period_code}</span>
                <strong>
                  {friendlyCode(overview.latest_run.run_type_code)} run #
                  {overview.latest_run.run_number}
                </strong>
                <small>
                  Policy {overview.latest_run.policy_code} v
                  {overview.latest_run.policy_version} · record v
                  {overview.latest_run.version}
                </small>
              </div>
              <div className={styles.amountGrid}>
                <div>
                  <span>Gross</span>
                  <strong>
                    {formatMoney(
                      overview.latest_run.gross_amount,
                      overview.latest_run.currency,
                      company.locale,
                    )}
                  </strong>
                </div>
                <div>
                  <span>Deductions</span>
                  <strong>
                    {formatMoney(
                      overview.latest_run.deduction_amount,
                      overview.latest_run.currency,
                      company.locale,
                    )}
                  </strong>
                </div>
                <div>
                  <span>Net</span>
                  <strong>
                    {formatMoney(
                      overview.latest_run.net_amount,
                      overview.latest_run.currency,
                      company.locale,
                    )}
                  </strong>
                </div>
                <div>
                  <span>Employer cost</span>
                  <strong>
                    {formatMoney(
                      overview.latest_run.employer_cost_amount,
                      overview.latest_run.currency,
                      company.locale,
                    )}
                  </strong>
                </div>
              </div>
              <div className={styles.runFootline}>
                <span>{overview.latest_run.employee_count} employee records</span>
                <span>{overview.latest_run.exception_count} run exceptions</span>
                <span>Updated {formatDate(overview.latest_run.updated_at, company.locale)}</span>
              </div>
            </div>
          ) : (
            <EmptyState>
              No payroll run exists yet. Publish a validated policy, create a period,
              and initiate the first governed run through the Phase 21 APIs.
            </EmptyState>
          )}
        </article>

        <article className={styles.governancePanel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Control assurance</p>
              <h2>Governance posture</h2>
            </div>
            <span className={styles.shield}>✓</span>
          </header>
          <ul className={styles.controlList}>
            <li>
              <span>Workflow source</span>
              <strong>Versioned policy</strong>
            </li>
            <li>
              <span>Statutory formulas</span>
              <strong>Not hardcoded</strong>
            </li>
            <li>
              <span>Locked run mutation</span>
              <strong>Blocked</strong>
            </li>
            <li>
              <span>Maker-checker</span>
              <strong>Supported</strong>
            </li>
            <li>
              <span>Bank data in overview</span>
              <strong>Not exposed</strong>
            </li>
          </ul>
          <p className={styles.governanceNote}>
            Country statutory logic remains adapter-driven and must be validated by
            authorized payroll, accounting and legal specialists before activation.
          </p>
        </article>
      </section>

      <section className={styles.twoColumnGrid}>
        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Action queue</p>
              <h2>Pending approvals</h2>
            </div>
            <span className={styles.countBadge}>{overview.pending_approvals.length}</span>
          </header>
          {overview.pending_approvals.length ? (
            <div className={styles.queueList}>
              {overview.pending_approvals.map((approval) => (
                <div className={styles.queueItem} key={approval.public_id}>
                  <div>
                    <strong>{friendlyCode(approval.step_code)}</strong>
                    <span>Period {approval.period_code}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(approval.status_code)}`}>
                      {friendlyCode(approval.status_code)}
                    </span>
                    <small>Due {formatDate(approval.due_at, company.locale)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No payroll approval is currently waiting for a decision.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Exception watchlist</p>
              <h2>Open controls</h2>
            </div>
            <span className={styles.countBadge}>{overview.open_exceptions.length}</span>
          </header>
          {overview.open_exceptions.length ? (
            <div className={styles.queueList}>
              {overview.open_exceptions.map((exception) => (
                <div className={styles.queueItem} key={exception.public_id}>
                  <div>
                    <strong>{friendlyCode(exception.exception_code)}</strong>
                    <span>{exception.message}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span
                      className={`${styles.statusPill} ${statusTone(
                        exception.severity_code,
                      )}`}
                    >
                      {friendlyCode(exception.severity_code)}
                    </span>
                    <small>Due {formatDate(exception.due_at, company.locale)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No unresolved payroll exception is visible to this tenant.</EmptyState>
          )}
        </article>
      </section>

      <section className={styles.panel}>
        <header className={styles.panelHeader}>
          <div>
            <p className={styles.panelEyebrow}>Operational history</p>
            <h2>Recent payroll runs</h2>
          </div>
          <span className={styles.generatedAt}>
            Snapshot {formatDate(overview.generated_at, company.locale)}
          </span>
        </header>
        {overview.recent_runs.length ? (
          <div className={styles.tableScroll}>
            <table className={styles.runTable}>
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Employees</th>
                  <th>Exceptions</th>
                  <th>Net payroll</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {overview.recent_runs.map((run) => (
                  <tr key={run.public_id}>
                    <td><strong>{run.period_code}</strong></td>
                    <td>{friendlyCode(run.run_type_code)} #{run.run_number}</td>
                    <td>
                      <span className={`${styles.statusPill} ${statusTone(run.status_code)}`}>
                        {friendlyCode(run.status_code)}
                      </span>
                    </td>
                    <td>{run.employee_count}</td>
                    <td>{run.exception_count}</td>
                    <td>{formatMoney(run.net_amount, run.currency, company.locale)}</td>
                    <td>{formatDate(run.updated_at, company.locale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState>No payroll run history is available.</EmptyState>
        )}
      </section>
    </main>
  );
}
