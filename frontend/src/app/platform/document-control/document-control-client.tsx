"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import styles from "./document-control.module.css";

type Company = {
  public_id: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
  unit_system_code: string;
};

type ControlledDocument = {
  public_id: string;
  document_number: string;
  discipline_code: string;
  document_type_code: string;
  title: string;
  status_code: string;
  current_revision_code: string;
  confidentiality_code: string;
  version: number;
};

type Revision = {
  public_id: string;
  document_number: string;
  revision_code: string;
  purpose_code: string;
  status_code: string;
  submitted_at: string | null;
  issued_at: string | null;
  version: number;
};

type Transmittal = {
  public_id: string;
  transmittal_number: string;
  direction_code: string;
  status_code: string;
  subject: string;
  issued_at: string | null;
  due_at: string | null;
  document_count: number;
  overdue: boolean;
  version: number;
};

type Rfi = {
  public_id: string;
  rfi_number: string;
  discipline_code: string;
  priority_code: string;
  status_code: string;
  subject: string;
  raised_at: string;
  response_due_at: string | null;
  overdue: boolean;
  version: number;
};

type Submittal = {
  public_id: string;
  submittal_number: string;
  revision_number: number;
  category_code: string;
  package_code: string;
  status_code: string;
  title: string;
  submitted_at: string | null;
  review_due_at: string | null;
  decision_code: string;
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

type Distribution = {
  public_id: string;
  document_number: string;
  revision_code: string;
  recipient_type_code: string;
  purpose_code: string;
  status_code: string;
  distributed_at: string;
  acknowledged_at: string | null;
  version: number;
};

type DocumentRisk = {
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

type DocumentOverview = {
  generated_at: string;
  company: Company;
  summary: {
    published_policy_count: number;
    active_document_count: number;
    revision_review_count: number;
    revision_due_count: number;
    open_transmittal_count: number;
    overdue_transmittal_count: number;
    open_rfi_count: number;
    overdue_rfi_count: number;
    critical_rfi_count: number;
    open_submittal_count: number;
    submittal_due_count: number;
    overdue_submittal_count: number;
    reviewed_submittal_30d_count: number;
    submittal_approval_percent: number;
    pending_approval_count: number;
    overdue_approval_count: number;
    unacknowledged_distribution_count: number;
    open_risk_count: number;
  };
  active_documents: ControlledDocument[];
  revision_queue: Revision[];
  open_transmittals: Transmittal[];
  open_rfis: Rfi[];
  submittal_queue: Submittal[];
  pending_approvals: Approval[];
  recent_distributions: Distribution[];
  open_risks: DocumentRisk[];
  document_disciplines: Array<{ discipline_code: string; count: number }>;
  rfi_priorities: Array<{ priority_code: string; count: number }>;
  risk_severity: Array<{ severity_code: string; count: number }>;
  governance: {
    workflow_source: string;
    document_types_hardcoded: boolean;
    discipline_codes_hardcoded: boolean;
    revision_schemes_hardcoded: boolean;
    submittal_decisions_hardcoded: boolean;
    cross_tenant_records_allowed: boolean;
    file_references_exposed: boolean;
    checksums_exposed: boolean;
    maker_checker_supported: boolean;
    project_adapter_boundary: string;
    party_adapter_boundary: string;
    storage_adapter_boundary: string;
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
  if (
    [
      "ACTIVE",
      "ISSUED",
      "APPROVED",
      "ACKNOWLEDGED",
      "RESPONDED",
      "CLOSED",
      "RESOLVED",
    ].includes(normalized)
  ) {
    return styles.toneSuccess;
  }
  if (
    [
      "CRITICAL",
      "URGENT",
      "REJECTED",
      "REVOKED",
      "OVERDUE",
      "SUPERSEDED",
    ].includes(normalized)
  ) {
    return styles.toneDanger;
  }
  if (
    [
      "OPEN",
      "PENDING",
      "SUBMITTED",
      "UNDER_REVIEW",
      "ASSIGNED",
      "RESPONSE_PENDING",
      "REVISION_REQUIRED",
      "DRAFT",
    ].includes(normalized)
  ) {
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

function StatusPill({ code }: { code: string }) {
  return (
    <span className={`${styles.statusPill} ${statusTone(code)}`}>
      {friendlyCode(code)}
    </span>
  );
}

function EmptyState({ children }: { children: string }) {
  return <div className={styles.emptyState}>{children}</div>;
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

export function DocumentControlClient() {
  const [overview, setOverview] = useState<DocumentOverview | null>(null);
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
      const response = await fetch("/api/platform/document-control/overview", {
        cache: "no-store",
        signal,
      });
      const payload = (await response.json().catch(() => ({}))) as
        | DocumentOverview
        | ErrorPayload;
      if (!response.ok) {
        const failure = payload as ErrorPayload;
        throw new Error(
          failure.message || failure.detail || "Document control could not be loaded.",
        );
      }
      setOverview(payload as DocumentOverview);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") {
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Document control could not be loaded.",
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

  const disciplineSignal = useMemo(() => {
    if (!overview?.document_disciplines.length) return "No active discipline signals";
    return overview.document_disciplines
      .slice(0, 5)
      .map((entry) => `${friendlyCode(entry.discipline_code)} ${entry.count}`)
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
            <p className={styles.kicker}>Document control unavailable</p>
            <h1>The engineering information control room could not be opened.</h1>
            <p>{error || "Check the API, tenant session and document permissions."}</p>
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
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 26</p>
          <h1>Document control &amp; engineering operations</h1>
          <p className={styles.lead}>
            Govern controlled documents, revisions, transmittals, RFIs, technical
            submittals, distributions, approvals and engineering risk from one
            tenant-safe command centre.
          </p>
          <div className={styles.contextChips}>
            <span>{company.display_name}</span>
            <span>{company.locale}</span>
            <span>{company.timezone}</span>
          </div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.phasePill}>
            PHASE 26 DOCUMENT CONTROL &amp; ENGINEERING OPERATIONS ACTIVE
          </span>
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
          label="Controlled documents"
          value={summary.active_document_count}
          detail={disciplineSignal}
        />
        <MetricCard
          label="Revision review"
          value={summary.revision_review_count}
          detail={`${summary.revision_due_count} submitted and awaiting governance`}
          alert={summary.revision_due_count > 0}
        />
        <MetricCard
          label="RFI exposure"
          value={summary.overdue_rfi_count}
          detail={`${summary.open_rfi_count} open · ${summary.critical_rfi_count} critical`}
          alert={summary.overdue_rfi_count > 0 || summary.critical_rfi_count > 0}
        />
        <MetricCard
          label="Submittal assurance"
          value={`${summary.submittal_approval_percent}%`}
          detail={`${summary.reviewed_submittal_30d_count} reviewed in 30 days`}
          alert={summary.overdue_submittal_count > 0}
        />
      </section>

      <section className={styles.commandGrid}>
        <article className={styles.primaryPanel}>
          <PanelHeader
            eyebrow="INFORMATION ASSURANCE"
            title="Controlled document register"
            count={overview.active_documents.length}
          />
          {overview.active_documents.length ? (
            <div className={styles.tableWrap}>
              <table>
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Discipline</th>
                    <th>Type</th>
                    <th>Revision</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.active_documents.map((document) => (
                    <tr key={document.public_id}>
                      <td>
                        <strong>{document.document_number}</strong>
                        <span>{document.title}</span>
                      </td>
                      <td>{friendlyCode(document.discipline_code)}</td>
                      <td>{friendlyCode(document.document_type_code)}</td>
                      <td>{document.current_revision_code || "Not issued"}</td>
                      <td><StatusPill code={document.status_code} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState>No governed documents are active for this tenant.</EmptyState>
          )}
        </article>

        <article className={styles.assurancePanel}>
          <PanelHeader
            eyebrow="CONTROL ASSURANCE"
            title="Governance posture"
            count={summary.published_policy_count}
          />
          <div className={styles.assuranceScore}>
            <strong>{overview.governance.maker_checker_supported ? "✓" : "!"}</strong>
            <div>
              <p>Maker-checker control</p>
              <span>Policy-led workflow and tenant isolation are enforced.</span>
            </div>
          </div>
          <dl className={styles.governanceList}>
            <div><dt>Workflow source</dt><dd>{friendlyCode(overview.governance.workflow_source)}</dd></div>
            <div><dt>Hardcoded document types</dt><dd>{overview.governance.document_types_hardcoded ? "Yes" : "No"}</dd></div>
            <div><dt>Cross-tenant records</dt><dd>{overview.governance.cross_tenant_records_allowed ? "Allowed" : "Blocked"}</dd></div>
            <div><dt>File references exposed</dt><dd>{overview.governance.file_references_exposed ? "Yes" : "No"}</dd></div>
            <div><dt>Checksum exposed</dt><dd>{overview.governance.checksums_exposed ? "Yes" : "No"}</dd></div>
          </dl>
        </article>
      </section>

      <section className={styles.queueGrid}>
        <article className={styles.queuePanel}>
          <PanelHeader eyebrow="REVISION GATE" title="Review queue" count={overview.revision_queue.length} />
          {overview.revision_queue.length ? (
            <div className={styles.stackList}>
              {overview.revision_queue.map((revision) => (
                <div className={styles.stackItem} key={revision.public_id}>
                  <div>
                    <strong>{revision.document_number} · Rev {revision.revision_code}</strong>
                    <span>{friendlyCode(revision.purpose_code)} · {formatDateTime(revision.submitted_at, company.locale)}</span>
                  </div>
                  <StatusPill code={revision.status_code} />
                </div>
              ))}
            </div>
          ) : <EmptyState>No revisions are waiting for review.</EmptyState>}
        </article>

        <article className={styles.queuePanel}>
          <PanelHeader eyebrow="DESIGN CLARITY" title="Open RFIs" count={overview.open_rfis.length} />
          {overview.open_rfis.length ? (
            <div className={styles.stackList}>
              {overview.open_rfis.map((rfi) => (
                <div className={`${styles.stackItem} ${rfi.overdue ? styles.overdueItem : ""}`} key={rfi.public_id}>
                  <div>
                    <strong>{rfi.rfi_number} · {rfi.subject}</strong>
                    <span>{friendlyCode(rfi.discipline_code)} · Due {formatDateTime(rfi.response_due_at, company.locale)}</span>
                  </div>
                  <StatusPill code={rfi.overdue ? "OVERDUE" : rfi.priority_code} />
                </div>
              ))}
            </div>
          ) : <EmptyState>No open RFIs require engineering response.</EmptyState>}
        </article>

        <article className={styles.queuePanel}>
          <PanelHeader eyebrow="TECHNICAL REVIEW" title="Submittal queue" count={overview.submittal_queue.length} />
          {overview.submittal_queue.length ? (
            <div className={styles.stackList}>
              {overview.submittal_queue.map((submittal) => (
                <div className={`${styles.stackItem} ${submittal.overdue ? styles.overdueItem : ""}`} key={submittal.public_id}>
                  <div>
                    <strong>{submittal.submittal_number} · Rev {submittal.revision_number}</strong>
                    <span>{submittal.title} · Due {formatDateTime(submittal.review_due_at, company.locale)}</span>
                  </div>
                  <StatusPill code={submittal.overdue ? "OVERDUE" : submittal.status_code} />
                </div>
              ))}
            </div>
          ) : <EmptyState>No technical submittals are due inside seven days.</EmptyState>}
        </article>

        <article className={styles.queuePanel}>
          <PanelHeader eyebrow="ISSUE CONTROL" title="Open transmittals" count={overview.open_transmittals.length} />
          {overview.open_transmittals.length ? (
            <div className={styles.stackList}>
              {overview.open_transmittals.map((transmittal) => (
                <div className={`${styles.stackItem} ${transmittal.overdue ? styles.overdueItem : ""}`} key={transmittal.public_id}>
                  <div>
                    <strong>{transmittal.transmittal_number} · {transmittal.subject}</strong>
                    <span>{friendlyCode(transmittal.direction_code)} · {transmittal.document_count} documents</span>
                  </div>
                  <StatusPill code={transmittal.overdue ? "OVERDUE" : transmittal.status_code} />
                </div>
              ))}
            </div>
          ) : <EmptyState>No transmittals are awaiting acknowledgement or closure.</EmptyState>}
        </article>
      </section>

      <section className={styles.lowerGrid}>
        <article className={styles.queuePanel}>
          <PanelHeader eyebrow="DECISION CONTROL" title="Approval inbox" count={overview.pending_approvals.length} />
          {overview.pending_approvals.length ? (
            <div className={styles.stackList}>
              {overview.pending_approvals.map((approval) => (
                <div className={`${styles.stackItem} ${approval.overdue ? styles.overdueItem : ""}`} key={approval.public_id}>
                  <div>
                    <strong>{friendlyCode(approval.entity_type_code)} · {friendlyCode(approval.step_code)}</strong>
                    <span>Due {formatDateTime(approval.due_at, company.locale)}</span>
                  </div>
                  <StatusPill code={approval.overdue ? "OVERDUE" : approval.status_code} />
                </div>
              ))}
            </div>
          ) : <EmptyState>No document-control approvals are pending.</EmptyState>}
        </article>

        <article className={styles.queuePanel}>
          <PanelHeader eyebrow="DISTRIBUTION TRACE" title="Recent issues" count={overview.recent_distributions.length} />
          {overview.recent_distributions.length ? (
            <div className={styles.stackList}>
              {overview.recent_distributions.map((distribution) => (
                <div className={styles.stackItem} key={distribution.public_id}>
                  <div>
                    <strong>{distribution.document_number} · Rev {distribution.revision_code}</strong>
                    <span>{friendlyCode(distribution.recipient_type_code)} · {friendlyCode(distribution.purpose_code)}</span>
                  </div>
                  <StatusPill code={distribution.status_code} />
                </div>
              ))}
            </div>
          ) : <EmptyState>No document distributions were recorded in 30 days.</EmptyState>}
        </article>

        <article className={`${styles.queuePanel} ${styles.riskPanel}`}>
          <PanelHeader eyebrow="ENGINEERING EXPOSURE" title="Open risks" count={overview.open_risks.length} />
          {overview.open_risks.length ? (
            <div className={styles.stackList}>
              {overview.open_risks.map((risk) => (
                <div className={`${styles.stackItem} ${risk.overdue ? styles.overdueItem : ""}`} key={risk.public_id}>
                  <div>
                    <strong>{risk.risk_code} · {friendlyCode(risk.linked_entity_type_code)}</strong>
                    <span>{risk.message}</span>
                  </div>
                  <StatusPill code={risk.overdue ? "OVERDUE" : risk.severity_code} />
                </div>
              ))}
            </div>
          ) : <EmptyState>No unresolved document-control risks are visible.</EmptyState>}
        </article>
      </section>

      <footer className={styles.workspaceFooter}>
        <span>Snapshot {formatDateTime(overview.generated_at, company.locale)}</span>
        <span>Configuration-led · Tenant-safe · Audit-ready</span>
      </footer>
    </main>
  );
}
