"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import styles from "./commercial-operations.module.css";

type Company = {
  public_id: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
  unit_system_code: string;
};

type Summary = {
  published_policy_count: number;
  active_contract_count: number;
  completion_due_count: number;
  open_milestone_count: number;
  overdue_milestone_count: number;
  open_variation_count: number;
  overdue_variation_count: number;
  open_payment_count: number;
  overdue_payment_count: number;
  open_claim_count: number;
  overdue_claim_count: number;
  critical_claim_count: number;
  open_eot_count: number;
  overdue_eot_count: number;
  pending_approval_count: number;
  overdue_approval_count: number;
  open_risk_count: number;
  critical_risk_count: number;
};

type Contract = {
  public_id: string;
  contract_number: string;
  title: string;
  counterparty_name: string;
  contract_type_code: string;
  status_code: string;
  currency_code: string;
  current_contract_value: string;
  planned_completion_date: string;
  completion_due: boolean;
  version: number;
};

type Milestone = {
  public_id: string;
  contract_number: string;
  milestone_number: string;
  title: string;
  status_code: string;
  due_date: string;
  currency_code: string;
  milestone_value: string;
  overdue: boolean;
  version: number;
};

type Variation = {
  public_id: string;
  contract_number: string;
  variation_number: string;
  title: string;
  reason_code: string;
  status_code: string;
  currency_code: string;
  submitted_value: string;
  approved_value: string;
  time_impact_days: number;
  decision_due_at: string | null;
  overdue: boolean;
  version: number;
};

type Payment = {
  public_id: string;
  contract_number: string;
  application_number: string;
  status_code: string;
  currency_code: string;
  gross_claimed: string;
  certified_amount: string;
  net_payable: string;
  certification_due_at: string | null;
  overdue: boolean;
  version: number;
};

type Claim = {
  public_id: string;
  contract_number: string;
  claim_number: string;
  claim_type_code: string;
  priority_code: string;
  title: string;
  status_code: string;
  currency_code: string;
  claimed_amount: string;
  assessed_amount: string;
  response_due_at: string | null;
  overdue: boolean;
  version: number;
};

type Eot = {
  public_id: string;
  contract_number: string;
  claim_number: string;
  eot_number: string;
  reason_code: string;
  status_code: string;
  requested_days: number;
  assessed_days: number | null;
  approved_days: number | null;
  decision_due_at: string | null;
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
  overdue: boolean;
  version: number;
};

type Risk = {
  public_id: string;
  contract_number: string;
  linked_entity_type_code: string;
  risk_code: string;
  severity_code: string;
  status_code: string;
  message: string;
  due_at: string | null;
  overdue: boolean;
  version: number;
};

type Exposure = {
  currency_code: string;
  contract_value: string;
  pending_variations: string;
  uncertified_payments: string;
  open_claims: string;
};

type Overview = {
  generated_at: string;
  company: Company;
  summary: Summary;
  active_contracts: Contract[];
  milestone_queue: Milestone[];
  variation_queue: Variation[];
  payment_queue: Payment[];
  open_claims: Claim[];
  eot_queue: Eot[];
  pending_approvals: Approval[];
  open_risks: Risk[];
  financial_exposure: Exposure[];
  contract_types: Array<{ contract_type_code: string; count: number }>;
  claim_priorities: Array<{ priority_code: string; count: number }>;
  risk_severity: Array<{ severity_code: string; count: number }>;
  governance: {
    workflow_source: string;
    contract_types_hardcoded: boolean;
    variation_reasons_hardcoded: boolean;
    claim_types_hardcoded: boolean;
    payment_certification_hardcoded: boolean;
    currencies_aggregated_together: boolean;
    cross_tenant_records_allowed: boolean;
    maker_checker_supported: boolean;
    project_adapter_boundary: string;
    party_adapter_boundary: string;
    accounting_adapter_boundary: string;
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
      maximumFractionDigits: 2,
      notation: Math.abs(amount) >= 10_000_000 ? "compact" : "standard",
    }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString()}`;
  }
}

function statusTone(code: string) {
  const normalized = code.toUpperCase();
  if (["ACTIVE", "APPROVED", "CERTIFIED", "PAID", "ACHIEVED", "SETTLED", "CLOSED"].includes(normalized)) {
    return styles.toneSuccess;
  }
  if (["CRITICAL", "HIGH", "URGENT", "REJECTED", "OVERDUE"].includes(normalized)) {
    return styles.toneDanger;
  }
  if (["DRAFT", "NOTICE", "PLANNED", "SUBMITTED", "UNDER_REVIEW", "UNDER_ASSESSMENT", "UNDER_CERTIFICATION", "PENDING"].includes(normalized)) {
    return styles.toneWarning;
  }
  return styles.toneNeutral;
}

function StatusPill({ code }: { code: string }) {
  return <span className={`${styles.statusPill} ${statusTone(code)}`}>{friendlyCode(code)}</span>;
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

function PanelHeader({
  eyebrow,
  title,
  count,
}: {
  eyebrow: string;
  title: string;
  count: number;
}) {
  return (
    <header className={styles.panelHeader}>
      <div>
        <p>{eyebrow}</p>
        <h2>{title}</h2>
      </div>
      <span>{count}</span>
    </header>
  );
}

function EmptyState({ children }: { children: string }) {
  return <div className={styles.emptyState}>{children}</div>;
}

export function CommercialOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
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
      const response = await fetch("/api/platform/commercial-operations/overview", {
        cache: "no-store",
        signal,
      });
      const payload = (await response.json().catch(() => ({}))) as Overview | ErrorPayload;
      if (!response.ok) {
        const failure = payload as ErrorPayload;
        throw new Error(
          failure.message || failure.detail || "Commercial operations could not be loaded.",
        );
      }
      setOverview(payload as Overview);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Commercial operations could not be loaded.",
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

  const portfolioSignal = useMemo(() => {
    if (!overview?.contract_types.length) return "No active contract-type signals";
    return overview.contract_types
      .slice(0, 4)
      .map((entry) => `${friendlyCode(entry.contract_type_code)} ${entry.count}`)
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
            <p className={styles.kicker}>Commercial control unavailable</p>
            <h1>The contracts and claims control room could not be opened.</h1>
            <p>{error || "Check the API, tenant session and commercial permissions."}</p>
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
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 27</p>
          <h1>Commercial, contracts &amp; claims</h1>
          <p className={styles.heroCopy}>
            Govern contract value, milestones, variations, payment certification,
            claims, extensions of time, approvals and commercial exposure from one
            tenant-safe command centre.
          </p>
          <div className={styles.contextChips}>
            <span>{company.display_name}</span>
            <span>{company.currency}</span>
            <span>{company.timezone}</span>
          </div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.phaseBadge}>
            PHASE 27 COMMERCIAL, CONTRACTS &amp; CLAIMS OPERATIONS ACTIVE
          </span>
          <button
            type="button"
            onClick={() => void load(undefined, true)}
            disabled={isRefreshing}
          >
            {isRefreshing ? "Refreshing controls..." : "Refresh control room"}
          </button>
        </div>
      </section>

      {error ? <div className={styles.inlineAlert}>{error}</div> : null}

      <section className={styles.metricGrid} aria-label="Commercial operating metrics">
        <MetricCard
          label="Active contracts"
          value={summary.active_contract_count}
          detail={`${summary.completion_due_count} approach completion in 45 days`}
          alert={summary.completion_due_count > 0}
        />
        <MetricCard
          label="Variation control"
          value={summary.open_variation_count}
          detail={`${summary.overdue_variation_count} decision deadlines overdue`}
          alert={summary.overdue_variation_count > 0}
        />
        <MetricCard
          label="Payment certification"
          value={summary.open_payment_count}
          detail={`${summary.overdue_payment_count} certification deadlines overdue`}
          alert={summary.overdue_payment_count > 0}
        />
        <MetricCard
          label="Claims & EOT exposure"
          value={summary.open_claim_count + summary.open_eot_count}
          detail={`${summary.critical_claim_count} critical claims · ${summary.overdue_eot_count} EOT overdue`}
          alert={summary.critical_claim_count + summary.overdue_eot_count > 0}
        />
      </section>

      <section className={styles.primaryGrid}>
        <article className={styles.panel}>
          <PanelHeader
            eyebrow="Portfolio assurance"
            title="Active contract register"
            count={overview.active_contracts.length}
          />
          <p className={styles.panelSignal}>{portfolioSignal}</p>
          {overview.active_contracts.length ? (
            <div className={styles.tableWrap}>
              <table>
                <thead>
                  <tr>
                    <th>Contract</th>
                    <th>Counterparty</th>
                    <th>Value</th>
                    <th>Completion</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.active_contracts.map((item) => (
                    <tr key={item.public_id}>
                      <td>
                        <strong>{item.contract_number}</strong>
                        <span>{item.title}</span>
                      </td>
                      <td>
                        {item.counterparty_name}
                        <span>{friendlyCode(item.contract_type_code)}</span>
                      </td>
                      <td>{formatMoney(item.current_contract_value, item.currency_code, company.locale)}</td>
                      <td className={item.completion_due ? styles.deadline : ""}>
                        {formatDate(item.planned_completion_date, company.locale)}
                      </td>
                      <td><StatusPill code={item.status_code} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState>No active contracts are visible under the published commercial policy.</EmptyState>
          )}
        </article>

        <article className={styles.panel}>
          <PanelHeader
            eyebrow="Currency-safe exposure"
            title="Commercial value posture"
            count={overview.financial_exposure.length}
          />
          {overview.financial_exposure.length ? (
            <div className={styles.exposureList}>
              {overview.financial_exposure.map((item) => (
                <div className={styles.exposureCard} key={item.currency_code}>
                  <div>
                    <span>{item.currency_code}</span>
                    <strong>{formatMoney(item.contract_value, item.currency_code, company.locale)}</strong>
                    <small>Active contract value</small>
                  </div>
                  <dl>
                    <div><dt>Pending variations</dt><dd>{formatMoney(item.pending_variations, item.currency_code, company.locale)}</dd></div>
                    <div><dt>Uncertified payments</dt><dd>{formatMoney(item.uncertified_payments, item.currency_code, company.locale)}</dd></div>
                    <div><dt>Open claim delta</dt><dd>{formatMoney(item.open_claims, item.currency_code, company.locale)}</dd></div>
                  </dl>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No currency exposure is available until governed commercial records are active.</EmptyState>
          )}
          <div className={styles.guardrail}>
            <span>Control guardrail</span>
            <p>Amounts remain segregated by currency. Build360 never combines currencies into a false portfolio total.</p>
          </div>
        </article>
      </section>

      <section className={styles.queueGrid}>
        <article className={styles.panel}>
          <PanelHeader eyebrow="Change governance" title="Variation decision queue" count={overview.variation_queue.length} />
          <div className={styles.queueList}>
            {overview.variation_queue.length ? overview.variation_queue.map((item) => (
              <div className={styles.queueItem} key={item.public_id}>
                <div className={styles.queueLead}>
                  <strong>{item.variation_number}</strong>
                  <span>{item.contract_number} · {item.title}</span>
                </div>
                <div className={styles.queueValue}>
                  <strong>{formatMoney(item.submitted_value, item.currency_code, company.locale)}</strong>
                  <span>{item.time_impact_days} day impact</span>
                </div>
                <div className={item.overdue ? styles.deadline : ""}>
                  {formatDate(item.decision_due_at, company.locale)}
                </div>
                <StatusPill code={item.status_code} />
              </div>
            )) : <EmptyState>No variations require a decision inside the configured horizon.</EmptyState>}
          </div>
        </article>

        <article className={styles.panel}>
          <PanelHeader eyebrow="Cashflow assurance" title="Payment certification queue" count={overview.payment_queue.length} />
          <div className={styles.queueList}>
            {overview.payment_queue.length ? overview.payment_queue.map((item) => (
              <div className={styles.queueItem} key={item.public_id}>
                <div className={styles.queueLead}>
                  <strong>{item.application_number}</strong>
                  <span>{item.contract_number}</span>
                </div>
                <div className={styles.queueValue}>
                  <strong>{formatMoney(item.gross_claimed, item.currency_code, company.locale)}</strong>
                  <span>Certified {formatMoney(item.certified_amount, item.currency_code, company.locale)}</span>
                </div>
                <div className={item.overdue ? styles.deadline : ""}>
                  {formatDate(item.certification_due_at, company.locale)}
                </div>
                <StatusPill code={item.status_code} />
              </div>
            )) : <EmptyState>No payment applications require certification.</EmptyState>}
          </div>
        </article>
      </section>

      <section className={styles.queueGrid}>
        <article className={styles.panel}>
          <PanelHeader eyebrow="Entitlement management" title="Claims register" count={overview.open_claims.length} />
          <div className={styles.queueList}>
            {overview.open_claims.length ? overview.open_claims.map((item) => (
              <div className={styles.queueItem} key={item.public_id}>
                <div className={styles.queueLead}>
                  <strong>{item.claim_number}</strong>
                  <span>{item.contract_number} · {item.title}</span>
                </div>
                <div className={styles.queueValue}>
                  <strong>{formatMoney(item.claimed_amount, item.currency_code, company.locale)}</strong>
                  <span>{friendlyCode(item.claim_type_code)}</span>
                </div>
                <StatusPill code={item.priority_code} />
                <StatusPill code={item.status_code} />
              </div>
            )) : <EmptyState>No open commercial claims are visible.</EmptyState>}
          </div>
        </article>

        <article className={styles.panel}>
          <PanelHeader eyebrow="Time entitlement" title="Extension-of-time queue" count={overview.eot_queue.length} />
          <div className={styles.queueList}>
            {overview.eot_queue.length ? overview.eot_queue.map((item) => (
              <div className={styles.queueItem} key={item.public_id}>
                <div className={styles.queueLead}>
                  <strong>{item.eot_number}</strong>
                  <span>{item.contract_number}{item.claim_number ? ` · ${item.claim_number}` : ""}</span>
                </div>
                <div className={styles.queueValue}>
                  <strong>{item.requested_days} days</strong>
                  <span>{friendlyCode(item.reason_code)}</span>
                </div>
                <div className={item.overdue ? styles.deadline : ""}>{formatDate(item.decision_due_at, company.locale)}</div>
                <StatusPill code={item.status_code} />
              </div>
            )) : <EmptyState>No extension-of-time requests require assessment.</EmptyState>}
          </div>
        </article>
      </section>

      <section className={styles.governanceGrid}>
        <article className={styles.panel}>
          <PanelHeader eyebrow="Decision governance" title="Approval inbox" count={overview.pending_approvals.length} />
          <div className={styles.compactList}>
            {overview.pending_approvals.length ? overview.pending_approvals.map((item) => (
              <div key={item.public_id}>
                <span>{friendlyCode(item.entity_type_code)} · {friendlyCode(item.step_code)}</span>
                <strong className={item.overdue ? styles.deadline : ""}>{formatDate(item.due_at, company.locale)}</strong>
              </div>
            )) : <EmptyState>No pending commercial approvals are visible.</EmptyState>}
          </div>
        </article>

        <article className={styles.panel}>
          <PanelHeader eyebrow="Exposure controls" title="Commercial risk register" count={overview.open_risks.length} />
          <div className={styles.riskList}>
            {overview.open_risks.length ? overview.open_risks.map((item) => (
              <div key={item.public_id}>
                <StatusPill code={item.severity_code} />
                <div><strong>{friendlyCode(item.risk_code)}</strong><span>{item.contract_number || friendlyCode(item.linked_entity_type_code)}</span></div>
                <p>{item.message}</p>
              </div>
            )) : <EmptyState>No unresolved commercial risk signals are visible.</EmptyState>}
          </div>
        </article>

        <article className={`${styles.panel} ${styles.governancePanel}`}>
          <PanelHeader eyebrow="Control assurance" title="Governance posture" count={summary.published_policy_count} />
          <ul>
            <li><span>Tenant-configured workflows</span><strong>Enforced</strong></li>
            <li><span>Maker-checker decisions</span><strong>{overview.governance.maker_checker_supported ? "Enabled" : "Disabled"}</strong></li>
            <li><span>Cross-tenant records</span><strong>{overview.governance.cross_tenant_records_allowed ? "Allowed" : "Blocked"}</strong></li>
            <li><span>Currency aggregation</span><strong>{overview.governance.currencies_aggregated_together ? "Combined" : "Separated"}</strong></li>
            <li><span>Configuration source</span><strong>{friendlyCode(overview.governance.workflow_source)}</strong></li>
          </ul>
        </article>
      </section>

      <footer className={styles.workspaceFooter}>
        <span>Snapshot {formatDate(overview.generated_at, company.locale)}</span>
        <span>Commercial policy versions published: {summary.published_policy_count}</span>
      </footer>
    </main>
  );
}
