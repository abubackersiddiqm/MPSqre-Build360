"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import styles from "./safety-operations.module.css";

type Incident = {
  public_id: string;
  incident_code: string;
  incident_type_code: string;
  severity_code: string;
  status_code: string;
  title: string;
  occurred_at: string;
  reported_at: string;
  affected_people_count: number;
  lost_time: boolean;
  regulator_reportable: boolean;
  version: number;
};

type Permit = {
  public_id: string;
  permit_code: string;
  permit_type_code: string;
  risk_level_code: string;
  status_code: string;
  work_summary: string;
  valid_from: string;
  valid_until: string;
  expires_soon: boolean;
  expired: boolean;
  version: number;
};

type Observation = {
  public_id: string;
  observation_code: string;
  category_code: string;
  severity_code: string;
  status_code: string;
  title: string;
  observed_at: string;
  due_at: string | null;
  overdue: boolean;
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
  overdue: boolean;
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

type SafetyRisk = {
  public_id: string;
  linked_entity_type_code: string;
  risk_code: string;
  severity_code: string;
  status_code: string;
  message: string;
  due_at: string | null;
  overdue: boolean;
};

type ToolboxTalk = {
  public_id: string;
  talk_code: string;
  topic_code: string;
  status_code: string;
  title: string;
  delivered_at: string;
  attendee_count: number;
  acknowledgement_count: number;
  acknowledgement_percent: number;
};

type SafetyOverview = {
  generated_at: string;
  company: {
    public_id: string;
    code: string;
    display_name: string;
    locale: string;
    timezone: string;
    currency: string;
    unit_system_code: string;
  };
  summary: {
    published_policy_count: number;
    open_observation_count: number;
    overdue_observation_count: number;
    open_incident_count: number;
    critical_incident_count: number;
    active_permit_count: number;
    permit_expiry_watch_count: number;
    inspection_due_count: number;
    failed_inspection_count: number;
    open_action_count: number;
    overdue_action_count: number;
    toolbox_talk_30d_count: number;
    pending_approval_count: number;
    open_risk_count: number;
  };
  open_incidents: Incident[];
  active_permits: Permit[];
  open_observations: Observation[];
  inspection_watch: Inspection[];
  open_actions: CorrectiveAction[];
  pending_approvals: Approval[];
  open_risks: SafetyRisk[];
  recent_toolbox_talks: ToolboxTalk[];
  incident_severity: Array<{ severity_code: string; count: number }>;
  risk_severity: Array<{ severity_code: string; count: number }>;
  governance: {
    workflow_source: string;
    incident_types_hardcoded: boolean;
    permit_types_hardcoded: boolean;
    severity_matrix_hardcoded: boolean;
    cross_tenant_records_allowed: boolean;
    evidence_references_exposed: boolean;
    maker_checker_supported: boolean;
    project_adapter_boundary: string;
    location_adapter_boundary: string;
    regulatory_adapter_boundary: string;
    snapshot_date: string;
  };
};

type ErrorPayload = {
  message?: string;
  detail?: string;
};

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
  if (["ACTIVE", "PASSED", "APPROVED", "VERIFIED", "CLOSED", "RESOLVED"].includes(normalized)) {
    return styles.toneSuccess;
  }
  if (["CRITICAL", "FATAL", "FAILED", "EXPIRED", "REJECTED", "OVERDUE"].includes(normalized)) {
    return styles.toneDanger;
  }
  if (["HIGH", "OPEN", "REPORTED", "PENDING", "APPROVAL_PENDING", "INVESTIGATING", "ACTION_PENDING", "IN_PROGRESS", "SUSPENDED"].includes(normalized)) {
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

export function SafetyOperationsClient() {
  const [overview, setOverview] = useState<SafetyOverview | null>(null);
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
      const response = await fetch("/api/platform/safety-operations/overview", {
        cache: "no-store",
        signal,
      });
      const payload = (await response.json().catch(() => ({}))) as
        | SafetyOverview
        | ErrorPayload;
      if (!response.ok) {
        const failure = payload as ErrorPayload;
        throw new Error(
          failure.message || failure.detail || "Safety operations could not be loaded.",
        );
      }
      setOverview(payload as SafetyOverview);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Safety operations could not be loaded.",
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

  const severitySignal = useMemo(() => {
    if (!overview?.incident_severity.length) return "No open incident severity signals";
    return overview.incident_severity
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
            <p className={styles.kicker}>Safety operations unavailable</p>
            <h1>The HSE control room could not be opened.</h1>
            <p>{error || "Check the API, tenant session and safety permissions."}</p>
            <button type="button" onClick={() => void load()}>
              Retry workspace
            </button>
          </div>
        </section>
      </main>
    );
  }

  const { company, summary } = overview;
  const acknowledgementTotal = overview.recent_toolbox_talks.reduce(
    (total, talk) => total + talk.acknowledgement_count,
    0,
  );
  const attendeeTotal = overview.recent_toolbox_talks.reduce(
    (total, talk) => total + talk.attendee_count,
    0,
  );
  const acknowledgementRate = attendeeTotal
    ? Math.round((acknowledgementTotal / attendeeTotal) * 100)
    : 0;

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 24</p>
          <h1>HSE &amp; safety operations</h1>
          <p className={styles.lead}>
            Govern observations, incidents, permits to work, inspections, toolbox talks,
            corrective actions, approvals and safety risk from one tenant-safe command centre.
          </p>
          <div className={styles.contextChips}>
            <span>{company.display_name}</span>
            <span>{company.locale}</span>
            <span>{company.timezone}</span>
          </div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.phasePill}>PHASE 24 HSE &amp; SAFETY OPERATIONS ACTIVE</span>
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
          label="Open incidents"
          value={summary.open_incident_count}
          detail={`${summary.critical_incident_count} critical severity signals`}
          alert={summary.critical_incident_count > 0}
        />
        <MetricCard
          label="Active permits"
          value={summary.active_permit_count}
          detail={`${summary.permit_expiry_watch_count} expire inside 48 hours`}
          alert={summary.permit_expiry_watch_count > 0}
        />
        <MetricCard
          label="Corrective actions"
          value={summary.open_action_count}
          detail={`${summary.overdue_action_count} overdue controls`}
          alert={summary.overdue_action_count > 0}
        />
        <MetricCard
          label="Safety assurance"
          value={`${acknowledgementRate}%`}
          detail={`${summary.toolbox_talk_30d_count} toolbox talks in 30 days`}
        />
      </section>

      <section className={styles.assuranceGrid}>
        <article className={styles.assuranceCard}>
          <div>
            <p className={styles.panelEyebrow}>Operational exposure</p>
            <h2>Incident severity posture</h2>
            <p>{severitySignal}</p>
          </div>
          <div className={`${styles.assuranceIcon} ${summary.critical_incident_count ? styles.assuranceDanger : ""}`}>
            {summary.critical_incident_count || "✓"}
          </div>
        </article>
        <article className={styles.assuranceCard}>
          <div>
            <p className={styles.panelEyebrow}>Governance posture</p>
            <h2>Policy-driven controls</h2>
            <p>
              {summary.published_policy_count} published policy version
              {summary.published_policy_count === 1 ? "" : "s"} · {summary.pending_approval_count} pending approvals
            </p>
          </div>
          <div className={styles.assuranceIcon}>✓</div>
        </article>
      </section>

      <section className={styles.twoColumnGrid}>
        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Incident command</p>
              <h2>Open incident queue</h2>
            </div>
            <span className={styles.countBadge}>{overview.open_incidents.length}</span>
          </header>
          {overview.open_incidents.length ? (
            <div className={styles.queueList}>
              {overview.open_incidents.map((incident) => (
                <div className={styles.queueItem} key={incident.public_id}>
                  <div>
                    <strong>{incident.incident_code} · {incident.title}</strong>
                    <span>{friendlyCode(incident.incident_type_code)} · reported {formatDateTime(incident.reported_at, company.locale)}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(incident.severity_code)}`}>
                      {friendlyCode(incident.severity_code)}
                    </span>
                    <small>{incident.regulator_reportable ? "Regulator-reportable" : friendlyCode(incident.status_code)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No open safety incident is visible for this tenant.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Permit assurance</p>
              <h2>Active permits to work</h2>
            </div>
            <span className={styles.countBadge}>{overview.active_permits.length}</span>
          </header>
          {overview.active_permits.length ? (
            <div className={styles.queueList}>
              {overview.active_permits.map((permit) => (
                <div className={styles.queueItem} key={permit.public_id}>
                  <div>
                    <strong>{permit.permit_code} · {friendlyCode(permit.permit_type_code)}</strong>
                    <span>{permit.work_summary}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(permit.expired ? "EXPIRED" : permit.risk_level_code)}`}>
                      {permit.expired ? "Expired" : friendlyCode(permit.risk_level_code)}
                    </span>
                    <small>Until {formatDateTime(permit.valid_until, company.locale)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No active permit to work is visible.</EmptyState>
          )}
        </article>
      </section>

      <section className={styles.twoColumnGrid}>
        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Leading indicators</p>
              <h2>Open observations</h2>
            </div>
            <span className={styles.countBadge}>{overview.open_observations.length}</span>
          </header>
          {overview.open_observations.length ? (
            <div className={styles.queueList}>
              {overview.open_observations.map((observation) => (
                <div className={styles.queueItem} key={observation.public_id}>
                  <div>
                    <strong>{observation.observation_code} · {observation.title}</strong>
                    <span>{friendlyCode(observation.category_code)} · {formatDateTime(observation.observed_at, company.locale)}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(observation.overdue ? "OVERDUE" : observation.severity_code)}`}>
                      {observation.overdue ? "Overdue" : friendlyCode(observation.severity_code)}
                    </span>
                    <small>Due {formatDateTime(observation.due_at, company.locale)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No open safety observation is visible.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Corrective control</p>
              <h2>Action closure queue</h2>
            </div>
            <span className={styles.countBadge}>{overview.open_actions.length}</span>
          </header>
          {overview.open_actions.length ? (
            <div className={styles.queueList}>
              {overview.open_actions.map((action) => (
                <div className={styles.queueItem} key={action.public_id}>
                  <div>
                    <strong>{action.action_code} · {action.title}</strong>
                    <span>Source {friendlyCode(action.source_type_code)} · {friendlyCode(action.status_code)}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(action.overdue ? "OVERDUE" : action.priority_code)}`}>
                      {action.overdue ? "Overdue" : friendlyCode(action.priority_code)}
                    </span>
                    <small>Due {formatDateTime(action.due_at, company.locale)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No open corrective action is visible.</EmptyState>
          )}
        </article>
      </section>

      <section className={styles.threeColumnGrid}>
        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Inspection watch</p>
              <h2>Due &amp; overdue</h2>
            </div>
            <span className={styles.countBadge}>{overview.inspection_watch.length}</span>
          </header>
          {overview.inspection_watch.length ? (
            <div className={styles.compactList}>
              {overview.inspection_watch.map((inspection) => (
                <div key={inspection.public_id}>
                  <strong>{inspection.inspection_code}</strong>
                  <span>{friendlyCode(inspection.inspection_type_code)}</span>
                  <small className={inspection.overdue ? styles.dangerText : ""}>
                    {inspection.overdue ? "Overdue" : formatDateTime(inspection.scheduled_at, company.locale)}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No inspection is due inside seven days.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Decision queue</p>
              <h2>Pending approvals</h2>
            </div>
            <span className={styles.countBadge}>{overview.pending_approvals.length}</span>
          </header>
          {overview.pending_approvals.length ? (
            <div className={styles.compactList}>
              {overview.pending_approvals.map((approval) => (
                <div key={approval.public_id}>
                  <strong>{friendlyCode(approval.step_code)}</strong>
                  <span>{friendlyCode(approval.entity_type_code)}</span>
                  <small>Due {formatDateTime(approval.due_at, company.locale)}</small>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No pending safety approval is visible.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Risk control</p>
              <h2>Unresolved risks</h2>
            </div>
            <span className={styles.countBadge}>{overview.open_risks.length}</span>
          </header>
          {overview.open_risks.length ? (
            <div className={styles.compactList}>
              {overview.open_risks.map((risk) => (
                <div key={risk.public_id}>
                  <strong>{friendlyCode(risk.risk_code)}</strong>
                  <span>{risk.message}</span>
                  <small className={risk.overdue ? styles.dangerText : ""}>
                    {friendlyCode(risk.severity_code)} · {risk.overdue ? "Overdue" : formatDateTime(risk.due_at, company.locale)}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No unresolved safety risk is visible.</EmptyState>
          )}
        </article>
      </section>

      <section className={styles.panel}>
        <header className={styles.panelHeader}>
          <div>
            <p className={styles.panelEyebrow}>Workforce engagement</p>
            <h2>Recent toolbox talks</h2>
          </div>
          <span className={styles.generatedAt}>
            Snapshot {formatDateTime(overview.generated_at, company.locale)}
          </span>
        </header>
        {overview.recent_toolbox_talks.length ? (
          <div className={styles.tableScroll}>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th>Talk</th>
                  <th>Topic</th>
                  <th>Delivered</th>
                  <th>Attendance</th>
                  <th>Acknowledgement</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {overview.recent_toolbox_talks.map((talk) => (
                  <tr key={talk.public_id}>
                    <td><strong>{talk.talk_code}</strong><small>{talk.title}</small></td>
                    <td>{friendlyCode(talk.topic_code)}</td>
                    <td>{formatDateTime(talk.delivered_at, company.locale)}</td>
                    <td>{talk.attendee_count}</td>
                    <td>{talk.acknowledgement_count} · {talk.acknowledgement_percent}%</td>
                    <td><span className={`${styles.statusPill} ${statusTone(talk.status_code)}`}>{friendlyCode(talk.status_code)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState>
            No toolbox talk exists in the last 30 days. Publish a reviewed safety policy and record the first governed workforce briefing through the Phase 24 APIs.
          </EmptyState>
        )}
      </section>
    </main>
  );
}
