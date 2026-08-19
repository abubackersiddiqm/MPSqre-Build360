"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import styles from "./quality-operations.module.css";

type Company = {
  public_id: string;
  code: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
  unit_system_code: string;
};

type Itp = {
  public_id: string;
  itp_code: string;
  discipline_code: string;
  work_package_code: string;
  revision: number;
  status_code: string;
  title: string;
  hold_point_count: number;
  witness_point_count: number;
  version: number;
};

type InspectionRequest = {
  public_id: string;
  request_code: string;
  request_type_code: string;
  activity_code: string;
  lot_or_batch_code: string;
  status_code: string;
  requested_for: string;
  overdue: boolean;
  itp_code: string | null;
  version: number;
};

type Inspection = {
  public_id: string;
  inspection_code: string;
  inspection_type_code: string;
  status_code: string;
  result_code: string;
  scheduled_at: string;
  completed_at: string | null;
  score_percent: string | null;
  sample_size: number;
  accepted_quantity: number;
  rejected_quantity: number;
  overdue: boolean;
};

type Ncr = {
  public_id: string;
  ncr_code: string;
  category_code: string;
  severity_code: string;
  status_code: string;
  title: string;
  detected_at: string;
  due_at: string | null;
  overdue: boolean;
  version: number;
};

type CorrectiveAction = {
  public_id: string;
  action_code: string;
  source_type_code: string;
  priority_code: string;
  status_code: string;
  title: string;
  due_at: string | null;
  overdue: boolean;
  version: number;
};

type TestResult = {
  public_id: string;
  test_code: string;
  test_type_code: string;
  specimen_code: string;
  result_code: string;
  measured_value: string | null;
  unit_code: string;
  tested_at: string;
  inspection_code: string | null;
};

type Approval = {
  public_id: string;
  entity_type_code: string;
  entity_public_id: string;
  step_code: string;
  status_code: string;
  requested_at: string;
  due_at: string | null;
  version: number;
};

type QualityRisk = {
  public_id: string;
  linked_entity_type_code: string;
  risk_code: string;
  severity_code: string;
  status_code: string;
  message: string;
  due_at: string | null;
  overdue: boolean;
  version: number;
};

type QualityOverview = {
  generated_at: string;
  company: Company;
  summary: {
    published_policy_count: number;
    active_itp_count: number;
    open_request_count: number;
    request_due_count: number;
    inspection_due_count: number;
    failed_inspection_count: number;
    completed_inspection_30d_count: number;
    first_pass_acceptance_percent: number;
    failed_test_count: number;
    open_ncr_count: number;
    critical_ncr_count: number;
    overdue_ncr_count: number;
    open_action_count: number;
    overdue_action_count: number;
    pending_approval_count: number;
    open_risk_count: number;
  };
  active_itps: Itp[];
  inspection_queue: InspectionRequest[];
  inspection_watch: Inspection[];
  open_ncrs: Ncr[];
  open_actions: CorrectiveAction[];
  failed_tests: TestResult[];
  pending_approvals: Approval[];
  open_risks: QualityRisk[];
  ncr_severity: Array<{ severity_code: string; count: number }>;
  risk_severity: Array<{ severity_code: string; count: number }>;
  governance: {
    workflow_source: string;
    inspection_types_hardcoded: boolean;
    test_types_hardcoded: boolean;
    acceptance_criteria_hardcoded: boolean;
    disposition_codes_hardcoded: boolean;
    cross_tenant_records_allowed: boolean;
    evidence_references_exposed: boolean;
    maker_checker_supported: boolean;
    project_adapter_boundary: string;
    location_adapter_boundary: string;
    supplier_adapter_boundary: string;
    laboratory_adapter_boundary: string;
    snapshot_date: string;
  };
};

type ErrorPayload = { message?: string; detail?: string };

function friendlyCode(value: string) {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .toLowerCase()
    .replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
}

function formatDateTime(value: string | null, locale: string) {
  if (!value) return "Not scheduled";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(locale || "en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function statusTone(code: string) {
  const normalized = code.toUpperCase();
  if (["ACTIVE", "PASSED", "ACCEPTED", "APPROVED", "VERIFIED", "CLOSED"].includes(normalized)) {
    return styles.toneSuccess;
  }
  if (["CRITICAL", "MAJOR", "FAILED", "REJECTED", "EXPIRED", "OVERDUE"].includes(normalized)) {
    return styles.toneDanger;
  }
  if (["OPEN", "PENDING", "SUBMITTED", "SCHEDULED", "IN_PROGRESS", "ACTION_PENDING", "ROOT_CAUSE_PENDING", "DISPOSITION_PENDING"].includes(normalized)) {
    return styles.toneWarning;
  }
  return styles.toneNeutral;
}

function MetricCard({
  label,
  value,
  detail,
  alert = false,
}: {
  label: string;
  value: string | number;
  detail: string;
  alert?: boolean;
}) {
  return (
    <article className={`${styles.metricCard} ${alert ? styles.metricAlert : ""}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

function EmptyState({ children }: { children: string }) {
  return <div className={styles.emptyState}>{children}</div>;
}

function StatusPill({ code }: { code: string }) {
  return (
    <span className={`${styles.statusPill} ${statusTone(code)}`}>
      {friendlyCode(code)}
    </span>
  );
}

export function QualityOperationsClient() {
  const [overview, setOverview] = useState<QualityOverview | null>(null);
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
      const response = await fetch("/api/platform/quality-operations/overview", {
        cache: "no-store",
        signal,
      });
      const payload = (await response.json().catch(() => ({}))) as
        | QualityOverview
        | ErrorPayload;
      if (!response.ok) {
        const failure = payload as ErrorPayload;
        throw new Error(
          failure.message || failure.detail || "Quality operations could not be loaded.",
        );
      }
      setOverview(payload as QualityOverview);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Quality operations could not be loaded.",
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

  const ncrSignal = useMemo(() => {
    if (!overview?.ncr_severity.length) return "No open NCR severity signals";
    return overview.ncr_severity
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
            <p className={styles.kicker}>Quality operations unavailable</p>
            <h1>The QA/QC control room could not be opened.</h1>
            <p>{error || "Check the API, tenant session and quality permissions."}</p>
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
        <div className={styles.heroCopy}>
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 25</p>
          <h1>Quality &amp; QA/QC operations</h1>
          <p className={styles.lead}>
            Govern inspection test plans, material and work requests, inspections,
            laboratory results, NCRs, corrective actions, approvals and quality risk
            from one tenant-safe command centre.
          </p>
          <div className={styles.contextChips}>
            <span>{company.display_name}</span>
            <span>{company.locale}</span>
            <span>{company.timezone}</span>
          </div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.phasePill}>PHASE 25 QUALITY &amp; QA/QC OPERATIONS ACTIVE</span>
          <button
            type="button"
            disabled={isRefreshing}
            onClick={() => void load(undefined, true)}
          >
            {isRefreshing ? "Refreshing…" : "Refresh control room"}
          </button>
        </div>
      </section>

      {error ? <div className={styles.softError}>{error}</div> : null}

      <section className={styles.metricGrid}>
        <MetricCard
          label="First-pass acceptance"
          value={`${summary.first_pass_acceptance_percent}%`}
          detail={`${summary.completed_inspection_30d_count} inspections completed in 30 days`}
        />
        <MetricCard
          label="Inspection queue"
          value={summary.open_request_count}
          detail={`${summary.request_due_count} scheduled inside 7 days`}
          alert={summary.request_due_count > 0}
        />
        <MetricCard
          label="Open NCRs"
          value={summary.open_ncr_count}
          detail={`${summary.critical_ncr_count} critical or major · ${summary.overdue_ncr_count} overdue`}
          alert={summary.critical_ncr_count > 0 || summary.overdue_ncr_count > 0}
        />
        <MetricCard
          label="Test failures"
          value={summary.failed_test_count}
          detail={`${summary.failed_inspection_count} failed inspections`}
          alert={summary.failed_test_count > 0 || summary.failed_inspection_count > 0}
        />
      </section>

      <section className={styles.assuranceGrid}>
        <article className={styles.assuranceCard}>
          <div>
            <p className={styles.panelEyebrow}>Quality exposure</p>
            <h2>NCR severity posture</h2>
            <p>{ncrSignal}</p>
          </div>
          <div className={`${styles.assuranceIcon} ${summary.critical_ncr_count ? styles.assuranceDanger : ""}`}>
            {summary.critical_ncr_count || "✓"}
          </div>
        </article>
        <article className={styles.assuranceCard}>
          <div>
            <p className={styles.panelEyebrow}>Control assurance</p>
            <h2>Governance posture</h2>
            <p>
              Versioned tenant policy, maker-checker approvals and isolated evidence references are active.
            </p>
          </div>
          <div className={styles.assuranceIcon}>✓</div>
        </article>
      </section>

      <section className={styles.twoColumnGrid}>
        <article className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Inspection assurance</p>
              <h2>Upcoming inspection requests</h2>
            </div>
            <span className={styles.countBadge}>{overview.inspection_queue.length}</span>
          </div>
          {overview.inspection_queue.length ? (
            <div className={styles.queueList}>
              {overview.inspection_queue.map((item) => (
                <div className={styles.queueItem} key={item.public_id}>
                  <div>
                    <strong>{item.request_code}</strong>
                    <p>{friendlyCode(item.activity_code)} · {friendlyCode(item.request_type_code)}</p>
                    <span className={styles.queueMeta}>
                      {item.itp_code || "No linked ITP"} · {formatDateTime(item.requested_for, company.locale)}
                    </span>
                  </div>
                  <StatusPill code={item.overdue ? "OVERDUE" : item.status_code} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No inspection requests are due inside the current assurance horizon.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Nonconformance control</p>
              <h2>Open NCR queue</h2>
            </div>
            <span className={styles.countBadge}>{overview.open_ncrs.length}</span>
          </div>
          {overview.open_ncrs.length ? (
            <div className={styles.queueList}>
              {overview.open_ncrs.map((item) => (
                <div className={styles.queueItem} key={item.public_id}>
                  <div>
                    <strong>{item.ncr_code} · {item.title}</strong>
                    <p>{friendlyCode(item.category_code)} · {friendlyCode(item.severity_code)}</p>
                    <span className={styles.queueMeta}>
                      Due {formatDateTime(item.due_at, company.locale)}
                    </span>
                  </div>
                  <StatusPill code={item.overdue ? "OVERDUE" : item.status_code} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No open nonconformance reports are visible to this tenant.</EmptyState>
          )}
        </article>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <div>
            <p className={styles.panelEyebrow}>Inspection test plans</p>
            <h2>Active ITP register</h2>
          </div>
          <span className={styles.countBadge}>{summary.active_itp_count}</span>
        </div>
        {overview.active_itps.length ? (
          <div className={styles.tableScroll}>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th>ITP</th>
                  <th>Discipline</th>
                  <th>Work package</th>
                  <th>Control points</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {overview.active_itps.map((item) => (
                  <tr key={item.public_id}>
                    <td><strong>{item.itp_code}</strong><br />Rev {item.revision}</td>
                    <td>{friendlyCode(item.discipline_code)}</td>
                    <td>{friendlyCode(item.work_package_code)}</td>
                    <td>{item.hold_point_count} hold · {item.witness_point_count} witness</td>
                    <td><StatusPill code={item.status_code} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState>No active inspection test plans are published for this tenant.</EmptyState>
        )}
      </section>

      <section className={styles.threeColumnGrid}>
        <article className={styles.panel}>
          <div className={styles.panelHeader}>
            <div><p className={styles.panelEyebrow}>Corrective controls</p><h2>Actions</h2></div>
            <span className={styles.countBadge}>{summary.open_action_count}</span>
          </div>
          {overview.open_actions.length ? (
            <div className={styles.compactList}>
              {overview.open_actions.map((item) => (
                <div key={item.public_id}>
                  <strong>{item.action_code}</strong>
                  <span>{item.title}</span>
                  <small className={item.overdue ? styles.dangerText : ""}>
                    {friendlyCode(item.priority_code)} · {formatDateTime(item.due_at, company.locale)}
                  </small>
                </div>
              ))}
            </div>
          ) : <EmptyState>No open corrective actions.</EmptyState>}
        </article>

        <article className={styles.panel}>
          <div className={styles.panelHeader}>
            <div><p className={styles.panelEyebrow}>Laboratory assurance</p><h2>Failed tests</h2></div>
            <span className={styles.countBadge}>{summary.failed_test_count}</span>
          </div>
          {overview.failed_tests.length ? (
            <div className={styles.compactList}>
              {overview.failed_tests.map((item) => (
                <div key={item.public_id}>
                  <strong>{item.test_code}</strong>
                  <span>{friendlyCode(item.test_type_code)} · {item.specimen_code || "No specimen"}</span>
                  <small className={styles.dangerText}>{friendlyCode(item.result_code)}</small>
                </div>
              ))}
            </div>
          ) : <EmptyState>No failed test results.</EmptyState>}
        </article>

        <article className={styles.panel}>
          <div className={styles.panelHeader}>
            <div><p className={styles.panelEyebrow}>Maker-checker</p><h2>Approvals</h2></div>
            <span className={styles.countBadge}>{summary.pending_approval_count}</span>
          </div>
          {overview.pending_approvals.length ? (
            <div className={styles.compactList}>
              {overview.pending_approvals.map((item) => (
                <div key={item.public_id}>
                  <strong>{friendlyCode(item.step_code)}</strong>
                  <span>{friendlyCode(item.entity_type_code)}</span>
                  <small>{formatDateTime(item.due_at, company.locale)}</small>
                </div>
              ))}
            </div>
          ) : <EmptyState>No pending quality approvals.</EmptyState>}
        </article>
      </section>

      <p className={styles.generatedAt}>
        Control-room snapshot generated {formatDateTime(overview.generated_at, company.locale)}.
      </p>
    </main>
  );
}
