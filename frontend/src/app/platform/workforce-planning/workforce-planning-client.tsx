"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import styles from "./workforce-planning.module.css";

type WorkforcePlan = {
  public_id: string;
  code: string;
  name: string;
  policy_code: string;
  policy_version: number;
  starts_on: string;
  ends_on: string;
  status_code: string;
  version: number;
  required_headcount: number;
  filled_headcount: number;
  open_gap: number;
  approved_at: string | null;
  locked_at: string | null;
  created_at: string;
  updated_at: string;
};

type WorkforceGap = {
  public_id: string;
  plan_public_id: string;
  plan_code: string;
  demand_code: string;
  role_code: string;
  priority_code: string;
  status_code: string;
  quantity_required: number;
  quantity_filled: number;
  open_quantity: number;
  starts_on: string;
  ends_on: string;
  project_public_id: string | null;
  location_public_id: string | null;
};

type ExpiringCredential = {
  public_id: string;
  employee_public_id: string;
  skill_code: string;
  skill_name: string;
  proficiency_code: string;
  verification_status_code: string;
  expires_on: string;
};

type WorkforceApproval = {
  public_id: string;
  plan_public_id: string;
  plan_code: string;
  step_code: string;
  status_code: string;
  requested_from_membership_public_id: string;
  requested_at: string;
  due_at: string | null;
};

type WorkforceRisk = {
  public_id: string;
  plan_public_id: string | null;
  plan_code: string | null;
  demand_public_id: string | null;
  employee_public_id: string | null;
  risk_code: string;
  severity_code: string;
  status_code: string;
  message: string;
  due_at: string | null;
  created_at: string;
};

type WorkforceOverview = {
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
    plan_count: number;
    active_plan_count: number;
    demand_count: number;
    required_headcount: number;
    filled_headcount: number;
    open_gap: number;
    coverage_percent: number;
    estimated_cost: string;
    currency: string;
    estimated_cost_by_currency: Array<{ currency: string; amount: string }>;
    expiring_credential_count: number;
    expired_credential_count: number;
    pending_approval_count: number;
    open_risk_count: number;
  };
  policies: Array<{
    public_id: string;
    code: string;
    name: string;
    version: number;
    status_code: string;
    effective_from: string;
    effective_to: string | null;
    published_at: string;
  }>;
  recent_plans: WorkforcePlan[];
  critical_gaps: WorkforceGap[];
  expiring_credentials: ExpiringCredential[];
  pending_approvals: WorkforceApproval[];
  open_risks: WorkforceRisk[];
  risk_severity: Array<{ severity_code: string; count: number }>;
  governance: {
    workflow_source: string;
    role_codes_hardcoded: boolean;
    skill_catalog_hardcoded: boolean;
    cross_tenant_assignments_allowed: boolean;
    credential_evidence_exposed: boolean;
    maker_checker_supported: boolean;
    project_adapter_boundary: string;
  };
};

type ErrorPayload = {
  message?: string;
  detail?: string;
  code?: string;
};

function friendlyCode(value: string) {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .toLowerCase()
    .replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string | null, locale: string) {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale || "en-IN", {
    dateStyle: "medium",
  }).format(date);
}

function formatMoney(value: string, currency: string, locale: string) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return `${currency} ${value}`;
  try {
    return new Intl.NumberFormat(locale || "en-IN", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString()}`;
  }
}

function statusTone(statusCode: string) {
  const status = statusCode.toUpperCase();
  if (["APPROVED", "LOCKED", "FILLED", "VERIFIED", "COMPLETED"].includes(status)) {
    return styles.toneSuccess;
  }
  if (["CRITICAL", "EXPIRED", "REJECTED", "BLOCKED", "FAILED"].includes(status)) {
    return styles.toneDanger;
  }
  if (["HIGH", "PENDING", "SUBMITTED", "WARNING"].includes(status)) {
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

export function WorkforcePlanningClient() {
  const [overview, setOverview] = useState<WorkforceOverview | null>(null);
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
        "/api/platform/workforce-planning/overview",
        { cache: "no-store", signal },
      );
      const payload = (await response.json().catch(() => ({}))) as
        | WorkforceOverview
        | ErrorPayload;
      if (!response.ok) {
        const failure = payload as ErrorPayload;
        throw new Error(
          failure.message ||
            failure.detail ||
            "Workforce planning could not be loaded.",
        );
      }
      setOverview(payload as WorkforceOverview);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") {
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Workforce planning could not be loaded.",
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

  const riskSignal = useMemo(() => {
    if (!overview?.risk_severity.length) return "No unresolved severity signals";
    return overview.risk_severity
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
            <p className={styles.kicker}>Workforce planning unavailable</p>
            <h1>The workforce control room could not be opened.</h1>
            <p>{error || "Check the API, tenant session and workforce permissions."}</p>
            <button type="button" onClick={() => void load()}>
              Retry workspace
            </button>
          </div>
        </section>
      </main>
    );
  }

  const { company, summary } = overview;
  const safeCoverage = Math.min(Math.max(summary.coverage_percent, 0), 100);

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div>
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 22</p>
          <h1>Workforce planning</h1>
          <p className={styles.heroText}>
            Align project demand, role capacity, skills, credentials, assignments,
            approvals and workforce risk from one governed, tenant-safe command centre.
          </p>
          <div className={styles.heroMeta}>
            <span>{company.display_name}</span>
            <span>{company.currency}</span>
            <span>{company.timezone}</span>
          </div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.activeBadge}>PHASE 22 WORKFORCE PLANNING ACTIVE</span>
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
          Refresh failed. Showing the last successful workforce snapshot. {error}
        </div>
      ) : null}

      <section className={styles.metrics} aria-label="Workforce planning metrics">
        <MetricCard
          eyebrow="Workforce coverage"
          value={`${summary.coverage_percent.toFixed(1)}%`}
          detail={`${summary.filled_headcount} filled of ${summary.required_headcount} required`}
        />
        <MetricCard
          eyebrow="Open headcount gap"
          value={summary.open_gap}
          detail={`${summary.demand_count} governed demand lines`}
        />
        <MetricCard
          eyebrow="Credential watch"
          value={summary.expiring_credential_count}
          detail={`${summary.expired_credential_count} already expired`}
        />
        <MetricCard
          eyebrow="Open workforce risks"
          value={summary.open_risk_count}
          detail={riskSignal}
        />
      </section>

      <section className={styles.commandGrid}>
        <article className={styles.primaryPanel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Capacity assurance</p>
              <h2>Demand-to-supply coverage</h2>
            </div>
            <span className={styles.planCount}>{summary.active_plan_count} active plans</span>
          </header>
          <div className={styles.coverageBlock}>
            <div className={styles.coverageNumbers}>
              <div>
                <span>Required</span>
                <strong>{summary.required_headcount}</strong>
              </div>
              <div>
                <span>Filled</span>
                <strong>{summary.filled_headcount}</strong>
              </div>
              <div>
                <span>Gap</span>
                <strong>{summary.open_gap}</strong>
              </div>
              <div>
                <span>Estimated cost</span>
                <strong>
                  {formatMoney(summary.estimated_cost, summary.currency, company.locale)}
                </strong>
              </div>
            </div>
            <div
              className={styles.coverageTrack}
              aria-label={`${summary.coverage_percent}% workforce coverage`}
            >
              <span style={{ width: `${safeCoverage}%` }} />
            </div>
            <div className={styles.coverageFootline}>
              <span>{summary.plan_count} total plans</span>
              <span>{summary.published_policy_count} published policies</span>
              <span>{summary.pending_approval_count} pending approvals</span>
            </div>
          </div>
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
            <li><span>Workflow source</span><strong>Versioned policy</strong></li>
            <li><span>Role codes</span><strong>Configurable</strong></li>
            <li><span>Skill catalogue</span><strong>Tenant-owned</strong></li>
            <li><span>Cross-tenant assignments</span><strong>Blocked</strong></li>
            <li><span>Maker-checker</span><strong>Supported</strong></li>
            <li><span>Credential evidence</span><strong>Not exposed</strong></li>
          </ul>
          <p className={styles.governanceNote}>
            Project, labour, certification and regional compliance rules remain
            effective-dated configuration or adapter responsibilities that require
            authorized operational and legal validation before publication.
          </p>
        </article>
      </section>

      <section className={styles.twoColumnGrid}>
        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Staffing pressure</p>
              <h2>Priority workforce gaps</h2>
            </div>
            <span className={styles.countBadge}>{overview.critical_gaps.length}</span>
          </header>
          {overview.critical_gaps.length ? (
            <div className={styles.queueList}>
              {overview.critical_gaps.map((gap) => (
                <div className={styles.queueItem} key={gap.public_id}>
                  <div>
                    <strong>{friendlyCode(gap.role_code)}</strong>
                    <span>{gap.plan_code} · {gap.demand_code}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(gap.priority_code)}`}>
                      {friendlyCode(gap.priority_code)}
                    </span>
                    <small>{gap.open_quantity} open · starts {formatDate(gap.starts_on, company.locale)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No open demand gap is visible for this tenant.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Skills compliance</p>
              <h2>Credential expiry watch</h2>
            </div>
            <span className={styles.countBadge}>{overview.expiring_credentials.length}</span>
          </header>
          {overview.expiring_credentials.length ? (
            <div className={styles.queueList}>
              {overview.expiring_credentials.map((credential) => (
                <div className={styles.queueItem} key={credential.public_id}>
                  <div>
                    <strong>{credential.skill_name}</strong>
                    <span>{credential.skill_code} · {friendlyCode(credential.proficiency_code)}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(credential.verification_status_code)}`}>
                      {friendlyCode(credential.verification_status_code)}
                    </span>
                    <small>Expires {formatDate(credential.expires_on, company.locale)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No credential expires inside the next 60 days.</EmptyState>
          )}
        </article>
      </section>

      <section className={styles.twoColumnGrid}>
        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Decision queue</p>
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
                    <span>Plan {approval.plan_code}</span>
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
            <EmptyState>No pending workforce approval is visible.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Risk control</p>
              <h2>Open workforce risks</h2>
            </div>
            <span className={styles.countBadge}>{overview.open_risks.length}</span>
          </header>
          {overview.open_risks.length ? (
            <div className={styles.queueList}>
              {overview.open_risks.map((risk) => (
                <div className={styles.queueItem} key={risk.public_id}>
                  <div>
                    <strong>{friendlyCode(risk.risk_code)}</strong>
                    <span>{risk.message}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(risk.severity_code)}`}>
                      {friendlyCode(risk.severity_code)}
                    </span>
                    <small>{risk.plan_code || "Workforce control"}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No unresolved workforce risk is visible.</EmptyState>
          )}
        </article>
      </section>

      <section className={styles.panel}>
        <header className={styles.panelHeader}>
          <div>
            <p className={styles.panelEyebrow}>Planning portfolio</p>
            <h2>Recent workforce plans</h2>
          </div>
          <span className={styles.generatedAt}>
            Snapshot {formatDate(overview.generated_at, company.locale)}
          </span>
        </header>
        {overview.recent_plans.length ? (
          <div className={styles.tableScroll}>
            <table className={styles.planTable}>
              <thead>
                <tr>
                  <th>Plan</th>
                  <th>Period</th>
                  <th>Status</th>
                  <th>Required</th>
                  <th>Filled</th>
                  <th>Gap</th>
                  <th>Policy</th>
                </tr>
              </thead>
              <tbody>
                {overview.recent_plans.map((plan) => (
                  <tr key={plan.public_id}>
                    <td><strong>{plan.code}</strong><small>{plan.name}</small></td>
                    <td>{formatDate(plan.starts_on, company.locale)} – {formatDate(plan.ends_on, company.locale)}</td>
                    <td><span className={`${styles.statusPill} ${statusTone(plan.status_code)}`}>{friendlyCode(plan.status_code)}</span></td>
                    <td>{plan.required_headcount}</td>
                    <td>{plan.filled_headcount}</td>
                    <td>{plan.open_gap}</td>
                    <td>{plan.policy_code} v{plan.policy_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState>
            No workforce plan exists yet. Publish a reviewed policy and create the
            first plan through the Phase 22 APIs.
          </EmptyState>
        )}
      </section>
    </main>
  );
}
