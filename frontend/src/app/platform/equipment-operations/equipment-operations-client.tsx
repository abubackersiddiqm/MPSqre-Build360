"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import styles from "./equipment-operations.module.css";

type Asset = {
  public_id: string;
  asset_code: string;
  name: string;
  category_code: string;
  asset_type_code: string;
  ownership_code: string;
  status_code: string;
  current_meter_value: string;
  meter_type_code: string;
  next_service_on: string | null;
  next_service_meter: string | null;
  compliance_due_on: string | null;
  policy_code: string;
  policy_version: number;
  version: number;
  created_at: string;
  updated_at: string;
};

type Deployment = {
  public_id: string;
  asset_public_id: string;
  asset_code: string;
  asset_name: string;
  deployment_code: string;
  project_public_id: string | null;
  location_public_id: string | null;
  status_code: string;
  starts_at: string;
  ends_at: string | null;
  operator_employee_public_id: string | null;
};

type ServiceDue = {
  public_id: string;
  asset_code: string;
  asset_name: string;
  status_code: string;
  next_service_on: string | null;
  next_service_meter: string | null;
  current_meter_value: string;
  meter_type_code: string;
  overdue: boolean;
};

type ComplianceWatch = {
  public_id: string;
  asset_code: string;
  asset_name: string;
  category_code: string;
  status_code: string;
  compliance_due_on: string;
  expired: boolean;
};

type WorkOrder = {
  public_id: string;
  asset_public_id: string;
  asset_code: string;
  asset_name: string;
  code: string;
  maintenance_type_code: string;
  priority_code: string;
  status_code: string;
  summary: string;
  reported_at: string;
  scheduled_start: string | null;
  estimated_cost: string;
  currency: string;
  requires_approval: boolean;
  version: number;
};

type Approval = {
  public_id: string;
  work_order_public_id: string;
  work_order_code: string;
  asset_code: string;
  step_code: string;
  status_code: string;
  requested_from_membership_public_id: string;
  requested_at: string;
  due_at: string | null;
};

type EquipmentRisk = {
  public_id: string;
  asset_public_id: string;
  asset_code: string;
  work_order_public_id: string | null;
  risk_code: string;
  severity_code: string;
  status_code: string;
  message: string;
  due_at: string | null;
  created_at: string;
};

type EquipmentOverview = {
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
    asset_count: number;
    active_asset_count: number;
    deployed_asset_count: number;
    utilization_percent: number;
    service_due_count: number;
    service_overdue_count: number;
    compliance_watch_count: number;
    compliance_expired_count: number;
    open_work_order_count: number;
    pending_approval_count: number;
    open_risk_count: number;
    estimated_maintenance_cost: string;
    currency: string;
    estimated_cost_by_currency: Array<{ currency: string; amount: string }>;
  };
  recent_assets: Asset[];
  active_deployments: Deployment[];
  service_due: ServiceDue[];
  compliance_watch: ComplianceWatch[];
  open_work_orders: WorkOrder[];
  pending_approvals: Approval[];
  open_risks: EquipmentRisk[];
  risk_severity: Array<{ severity_code: string; count: number }>;
  governance: {
    workflow_source: string;
    asset_categories_hardcoded: boolean;
    ownership_models_hardcoded: boolean;
    cross_tenant_deployments_allowed: boolean;
    inspection_evidence_exposed: boolean;
    meter_evidence_exposed: boolean;
    maker_checker_supported: boolean;
    project_adapter_boundary: string;
    maintenance_provider_boundary: string;
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
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(locale || "en-IN", {
    dateStyle: "medium",
  }).format(parsed);
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
  const code = statusCode.toUpperCase();
  if (["AVAILABLE", "ACTIVE", "DEPLOYED", "PASSED", "APPROVED", "COMPLETED", "CLOSED"].includes(code)) {
    return styles.toneSuccess;
  }
  if (["CRITICAL", "EXPIRED", "FAILED", "REJECTED", "BLOCKED", "OVERDUE"].includes(code)) {
    return styles.toneDanger;
  }
  if (["HIGH", "PENDING", "OPEN", "APPROVAL_PENDING", "PLANNED", "IN_PROGRESS", "MAINTENANCE_HOLD"].includes(code)) {
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

export function EquipmentOperationsClient() {
  const [overview, setOverview] = useState<EquipmentOverview | null>(null);
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
        "/api/platform/equipment-operations/overview",
        { cache: "no-store", signal },
      );
      const payload = (await response.json().catch(() => ({}))) as
        | EquipmentOverview
        | ErrorPayload;
      if (!response.ok) {
        const failure = payload as ErrorPayload;
        throw new Error(
          failure.message ||
            failure.detail ||
            "Equipment operations could not be loaded.",
        );
      }
      setOverview(payload as EquipmentOverview);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") {
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Equipment operations could not be loaded.",
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
            <p className={styles.kicker}>Equipment operations unavailable</p>
            <h1>The equipment control room could not be opened.</h1>
            <p>{error || "Check the API, tenant session and equipment permissions."}</p>
            <button type="button" onClick={() => void load()}>
              Retry workspace
            </button>
          </div>
        </section>
      </main>
    );
  }

  const { company, summary } = overview;
  const utilization = Math.min(Math.max(summary.utilization_percent, 0), 100);

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div>
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 23</p>
          <h1>Equipment &amp; fleet operations</h1>
          <p className={styles.heroText}>
            Govern plant, machinery, fleet deployments, utilization, maintenance,
            inspections, approvals and operational risk from one tenant-safe command centre.
          </p>
          <div className={styles.heroMeta}>
            <span>{company.display_name}</span>
            <span>{company.currency}</span>
            <span>{friendlyCode(company.unit_system_code)}</span>
            <span>{company.timezone}</span>
          </div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.activeBadge}>PHASE 23 EQUIPMENT OPERATIONS ACTIVE</span>
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
          Refresh failed. Showing the last successful equipment snapshot. {error}
        </div>
      ) : null}

      <section className={styles.metrics} aria-label="Equipment operations metrics">
        <MetricCard
          eyebrow="Fleet utilization"
          value={`${summary.utilization_percent.toFixed(1)}%`}
          detail={`${summary.deployed_asset_count} deployed of ${summary.active_asset_count} active assets`}
        />
        <MetricCard
          eyebrow="Service assurance"
          value={summary.service_due_count}
          detail={`${summary.service_overdue_count} already overdue`}
        />
        <MetricCard
          eyebrow="Compliance watch"
          value={summary.compliance_watch_count}
          detail={`${summary.compliance_expired_count} expired records`}
        />
        <MetricCard
          eyebrow="Open equipment risks"
          value={summary.open_risk_count}
          detail={riskSignal}
        />
      </section>

      <section className={styles.assuranceGrid}>
        <article className={styles.utilizationPanel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Asset assurance</p>
              <h2>Fleet capacity &amp; utilization</h2>
            </div>
            <span className={styles.planCount}>{summary.asset_count} registered assets</span>
          </header>
          <div className={styles.utilizationBlock}>
            <div className={styles.utilizationNumbers}>
              <div><span>Active</span><strong>{summary.active_asset_count}</strong></div>
              <div><span>Deployed</span><strong>{summary.deployed_asset_count}</strong></div>
              <div><span>Open work orders</span><strong>{summary.open_work_order_count}</strong></div>
              <div>
                <span>Planned maintenance cost</span>
                <strong>{formatMoney(summary.estimated_maintenance_cost, summary.currency, company.locale)}</strong>
              </div>
            </div>
            <div
              className={styles.utilizationTrack}
              aria-label={`${summary.utilization_percent}% equipment utilization`}
            >
              <span style={{ width: `${utilization}%` }} />
            </div>
            <div className={styles.utilizationFootline}>
              <span>{summary.published_policy_count} published policies</span>
              <span>{summary.pending_approval_count} pending approvals</span>
              <span>{summary.open_work_order_count} maintenance actions</span>
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
            <li><span>Asset taxonomy</span><strong>Configurable</strong></li>
            <li><span>Ownership models</span><strong>Tenant-owned</strong></li>
            <li><span>Cross-tenant deployment</span><strong>Blocked</strong></li>
            <li><span>Maker-checker</span><strong>Supported</strong></li>
            <li><span>Evidence object keys</span><strong>Not exposed</strong></li>
          </ul>
          <p className={styles.governanceNote}>
            Equipment classes, statutory inspections, service intervals, meter rules,
            approval thresholds and maintenance providers remain reviewed configuration
            or adapter responsibilities before publication.
          </p>
        </article>
      </section>

      <section className={styles.twoColumnGrid}>
        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Deployment control</p>
              <h2>Active site deployments</h2>
            </div>
            <span className={styles.countBadge}>{overview.active_deployments.length}</span>
          </header>
          {overview.active_deployments.length ? (
            <div className={styles.queueList}>
              {overview.active_deployments.map((deployment) => (
                <div className={styles.queueItem} key={deployment.public_id}>
                  <div>
                    <strong>{deployment.asset_code} · {deployment.asset_name}</strong>
                    <span>{deployment.deployment_code} · starts {formatDate(deployment.starts_at, company.locale)}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(deployment.status_code)}`}>
                      {friendlyCode(deployment.status_code)}
                    </span>
                    <small>{deployment.ends_at ? `Until ${formatDate(deployment.ends_at, company.locale)}` : "Open-ended deployment"}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No active equipment deployment is visible for this tenant.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Maintenance pressure</p>
              <h2>Service due &amp; overdue</h2>
            </div>
            <span className={styles.countBadge}>{overview.service_due.length}</span>
          </header>
          {overview.service_due.length ? (
            <div className={styles.queueList}>
              {overview.service_due.map((item) => (
                <div className={styles.queueItem} key={item.public_id}>
                  <div>
                    <strong>{item.asset_code} · {item.asset_name}</strong>
                    <span>{item.meter_type_code ? `${item.current_meter_value} ${friendlyCode(item.meter_type_code)}` : "Meter not configured"}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(item.overdue ? "OVERDUE" : "PLANNED")}`}>
                      {item.overdue ? "Overdue" : "Due soon"}
                    </span>
                    <small>{item.next_service_on ? formatDate(item.next_service_on, company.locale) : `Meter ${item.next_service_meter || "not set"}`}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No equipment service is due inside the configured horizon.</EmptyState>
          )}
        </article>
      </section>

      <section className={styles.twoColumnGrid}>
        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Compliance assurance</p>
              <h2>Inspection &amp; certification watch</h2>
            </div>
            <span className={styles.countBadge}>{overview.compliance_watch.length}</span>
          </header>
          {overview.compliance_watch.length ? (
            <div className={styles.queueList}>
              {overview.compliance_watch.map((item) => (
                <div className={styles.queueItem} key={item.public_id}>
                  <div>
                    <strong>{item.asset_code} · {item.asset_name}</strong>
                    <span>{friendlyCode(item.category_code)}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(item.expired ? "EXPIRED" : "PENDING")}`}>
                      {item.expired ? "Expired" : "Due soon"}
                    </span>
                    <small>{formatDate(item.compliance_due_on, company.locale)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No inspection or certification expiry is inside the next 60 days.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Decision queue</p>
              <h2>Pending maintenance approvals</h2>
            </div>
            <span className={styles.countBadge}>{overview.pending_approvals.length}</span>
          </header>
          {overview.pending_approvals.length ? (
            <div className={styles.queueList}>
              {overview.pending_approvals.map((approval) => (
                <div className={styles.queueItem} key={approval.public_id}>
                  <div>
                    <strong>{approval.work_order_code} · {approval.asset_code}</strong>
                    <span>{friendlyCode(approval.step_code)}</span>
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
            <EmptyState>No pending equipment approval is visible.</EmptyState>
          )}
        </article>
      </section>

      <section className={styles.twoColumnGrid}>
        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Maintenance execution</p>
              <h2>Open work orders</h2>
            </div>
            <span className={styles.countBadge}>{overview.open_work_orders.length}</span>
          </header>
          {overview.open_work_orders.length ? (
            <div className={styles.queueList}>
              {overview.open_work_orders.map((order) => (
                <div className={styles.queueItem} key={order.public_id}>
                  <div>
                    <strong>{order.code} · {order.asset_code}</strong>
                    <span>{order.summary}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(order.priority_code)}`}>
                      {friendlyCode(order.priority_code)}
                    </span>
                    <small>{formatMoney(order.estimated_cost, order.currency, company.locale)} · {friendlyCode(order.status_code)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No open maintenance work order is visible.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHeader}>
            <div>
              <p className={styles.panelEyebrow}>Risk control</p>
              <h2>Open equipment risks</h2>
            </div>
            <span className={styles.countBadge}>{overview.open_risks.length}</span>
          </header>
          {overview.open_risks.length ? (
            <div className={styles.queueList}>
              {overview.open_risks.map((risk) => (
                <div className={styles.queueItem} key={risk.public_id}>
                  <div>
                    <strong>{risk.asset_code} · {friendlyCode(risk.risk_code)}</strong>
                    <span>{risk.message}</span>
                  </div>
                  <div className={styles.queueMeta}>
                    <span className={`${styles.statusPill} ${statusTone(risk.severity_code)}`}>
                      {friendlyCode(risk.severity_code)}
                    </span>
                    <small>Due {formatDate(risk.due_at, company.locale)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No unresolved equipment risk is visible.</EmptyState>
          )}
        </article>
      </section>

      <section className={styles.panel}>
        <header className={styles.panelHeader}>
          <div>
            <p className={styles.panelEyebrow}>Asset portfolio</p>
            <h2>Recently registered equipment</h2>
          </div>
          <span className={styles.generatedAt}>
            Snapshot {formatDate(overview.generated_at, company.locale)}
          </span>
        </header>
        {overview.recent_assets.length ? (
          <div className={styles.tableScroll}>
            <table className={styles.assetTable}>
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Ownership</th>
                  <th>Meter</th>
                  <th>Next service</th>
                  <th>Policy</th>
                </tr>
              </thead>
              <tbody>
                {overview.recent_assets.map((asset) => (
                  <tr key={asset.public_id}>
                    <td><strong>{asset.asset_code}</strong><small>{asset.name}</small></td>
                    <td>{friendlyCode(asset.category_code)}<small>{friendlyCode(asset.asset_type_code)}</small></td>
                    <td><span className={`${styles.statusPill} ${statusTone(asset.status_code)}`}>{friendlyCode(asset.status_code)}</span></td>
                    <td>{friendlyCode(asset.ownership_code)}</td>
                    <td>{asset.meter_type_code ? `${asset.current_meter_value} ${friendlyCode(asset.meter_type_code)}` : "Not configured"}</td>
                    <td>{asset.next_service_on ? formatDate(asset.next_service_on, company.locale) : asset.next_service_meter ? `At ${asset.next_service_meter}` : "Not scheduled"}</td>
                    <td>{asset.policy_code} v{asset.policy_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState>
            No equipment asset exists yet. Publish a reviewed policy and register the
            first plant, machinery or fleet asset through the Phase 23 APIs.
          </EmptyState>
        )}
      </section>
    </main>
  );
}
