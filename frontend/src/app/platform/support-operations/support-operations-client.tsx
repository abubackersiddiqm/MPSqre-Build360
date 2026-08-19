"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./support-operations.module.css";

type CatalogItem = {
  public_id: string;
  code: string;
  name: string;
  category_code: string;
  response_minutes: number;
  resolution_minutes: number;
  active: boolean;
};
type Ticket = {
  public_id: string;
  catalog_item__code: string | null;
  code: string;
  title: string;
  category_code: string;
  priority_code: string;
  channel_code: string;
  status_code: string;
  requester_name: string;
  requester_email: string;
  assigned_to_public_id: string | null;
  response_due_at: string | null;
  resolution_due_at: string | null;
  first_responded_at: string | null;
  resolved_at: string | null;
  sla_breached: boolean;
  escalation_level: number;
  version: number;
  created_at: string;
};
type Problem = {
  public_id: string;
  source_ticket__code: string | null;
  code: string;
  title: string;
  impact_summary: string;
  root_cause: string;
  permanent_fix: string;
  priority_code: string;
  status_code: string;
  version: number;
};
type ChangeRequest = {
  public_id: string;
  source_ticket__code: string | null;
  problem__code: string | null;
  code: string;
  title: string;
  change_type_code: string;
  risk_code: string;
  status_code: string;
  planned_start_at: string | null;
  planned_end_at: string | null;
  rollback_plan: string;
  version: number;
};
type Article = {
  public_id: string;
  code: string;
  title: string;
  summary: string;
  category_code: string;
  audience_code: string;
  status_code: string;
  published_at: string | null;
  version: number;
};
type Feedback = {
  public_id: string;
  ticket__code: string;
  rating: number;
  comments: string;
  submitted_by_name: string;
  follow_up_required: boolean;
  submitted_at: string;
};
type Improvement = {
  public_id: string;
  code: string;
  title: string;
  theme_code: string;
  priority_code: string;
  status_code: string;
  expected_benefit: string;
  measured_benefit: string;
  due_at: string | null;
  version: number;
};
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: {
    status: string;
    version: number;
    default_response_minutes: number;
    default_resolution_minutes: number;
    escalation_warning_percent: string;
    customer_feedback_required: boolean;
  };
  metrics: Record<string, number>;
  catalog_items: CatalogItem[];
  tickets: Ticket[];
  interactions: Array<{
    public_id: string;
    ticket__code: string;
    interaction_type_code: string;
    body: string;
    customer_visible: boolean;
    occurred_at: string;
  }>;
  problems: Problem[];
  changes: ChangeRequest[];
  knowledge_articles: Article[];
  feedback: Feedback[];
  improvements: Improvement[];
  capabilities: Record<string, boolean>;
};
type Tab = "tickets" | "sla" | "problems" | "knowledge" | "improvement";

const initialTicket = {
  code: "",
  title: "",
  requester_name: "",
  requester_email: "",
  category_code: "APPLICATION",
  priority_code: "P3",
  channel_code: "PORTAL",
  catalog_item_public_id: "",
  description: "",
};

async function readJson(response: Response): Promise<Record<string, unknown>> {
  const raw = await response.text();
  let payload: Record<string, unknown> = {};
  if (raw) {
    try {
      payload = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      payload = {};
    }
  }
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : "";
    const message = typeof payload.message === "string" ? payload.message : "";
    const error = typeof payload.error === "string" ? payload.error : "";
    throw new Error(detail || message || error || `Request failed with status ${response.status}.`);
  }
  return payload;
}

function fmt(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function Metric({ label, value, note }: { label: string; value: number | string; note: string }) {
  return (
    <article className={styles.metric}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

export function SupportOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("tickets");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ticketForm, setTicketForm] = useState(initialTicket);
  const [selectedTicket, setSelectedTicket] = useState("");
  const [interactionBody, setInteractionBody] = useState("");
  const [problemForm, setProblemForm] = useState({ code: "", title: "", priority_code: "P2", source_ticket_public_id: "", impact_summary: "" });
  const [changeForm, setChangeForm] = useState({ code: "", title: "", change_type_code: "NORMAL", risk_code: "MEDIUM", source_ticket_public_id: "", rollback_plan: "" });
  const [articleForm, setArticleForm] = useState({ code: "", title: "", category_code: "GENERAL", audience_code: "INTERNAL", summary: "", content: "" });
  const [feedbackForm, setFeedbackForm] = useState({ ticket_public_id: "", rating: "5", comments: "" });
  const [improvementForm, setImprovementForm] = useState({ code: "", title: "", theme_code: "SERVICE_QUALITY", priority_code: "P3", expected_benefit: "" });

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/platform/support-operations/overview", { cache: "no-store" });
      setOverview((await readJson(response)) as unknown as Overview);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Support operations could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void load();
    });
    return () => controller.abort();
  }, [load]);

  const post = useCallback(async (path: string, body: Record<string, unknown>) => {
    setWorking(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/platform/support-operations/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      await readJson(response);
      setNotice("Control updated successfully.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The operation could not be completed.");
      throw reason;
    } finally {
      setWorking(false);
    }
  }, [load]);

  const openTickets = useMemo(
    () => overview?.tickets.filter((ticket) => !["CLOSED", "CANCELLED"].includes(ticket.status_code)) ?? [],
    [overview],
  );

  async function createTicket(event: FormEvent) {
    event.preventDefault();
    const body: Record<string, unknown> = { ...ticketForm };
    if (!ticketForm.catalog_item_public_id) delete body.catalog_item_public_id;
    await post("tickets", body);
    setTicketForm(initialTicket);
  }

  async function addInteraction(event: FormEvent) {
    event.preventDefault();
    if (!selectedTicket) return;
    await post("interactions", {
      ticket_public_id: selectedTicket,
      interaction_type_code: "RESPONSE",
      visibility_code: "CUSTOMER",
      body: interactionBody,
      customer_visible: true,
    });
    setInteractionBody("");
  }

  async function transitionTicket(ticket: Ticket, status: string) {
    const resolution = status === "RESOLVED" || status === "CLOSED"
      ? window.prompt("Resolution summary") ?? ""
      : "";
    await post(`tickets/${ticket.public_id}/transition`, {
      status_code: status,
      expected_version: ticket.version,
      resolution_summary: resolution,
    });
  }

  async function createProblem(event: FormEvent) {
    event.preventDefault();
    const body: Record<string, unknown> = { ...problemForm };
    if (!problemForm.source_ticket_public_id) delete body.source_ticket_public_id;
    await post("problems", body);
    setProblemForm({ code: "", title: "", priority_code: "P2", source_ticket_public_id: "", impact_summary: "" });
  }

  async function createChange(event: FormEvent) {
    event.preventDefault();
    const body: Record<string, unknown> = { ...changeForm };
    if (!changeForm.source_ticket_public_id) delete body.source_ticket_public_id;
    await post("changes", body);
    setChangeForm({ code: "", title: "", change_type_code: "NORMAL", risk_code: "MEDIUM", source_ticket_public_id: "", rollback_plan: "" });
  }

  async function createArticle(event: FormEvent) {
    event.preventDefault();
    await post("knowledge", articleForm);
    setArticleForm({ code: "", title: "", category_code: "GENERAL", audience_code: "INTERNAL", summary: "", content: "" });
  }

  async function createFeedback(event: FormEvent) {
    event.preventDefault();
    await post("feedback", { ...feedbackForm, rating: Number(feedbackForm.rating) });
    setFeedbackForm({ ticket_public_id: "", rating: "5", comments: "" });
  }

  async function createImprovement(event: FormEvent) {
    event.preventDefault();
    await post("improvements", improvementForm);
    setImprovementForm({ code: "", title: "", theme_code: "SERVICE_QUALITY", priority_code: "P3", expected_benefit: "" });
  }

  if (loading && !overview) {
    return <main className={styles.loading}>Loading service operations…</main>;
  }

  if (error && !overview) {
    return (
      <main className={styles.loading}>
        <section className={styles.errorCard}>
          <span>SERVICE CONTROL UNAVAILABLE</span>
          <h1>Support operations could not be opened.</h1>
          <p>{error}</p>
          <button type="button" onClick={() => void load()}>Retry workspace</button>
        </section>
      </main>
    );
  }

  if (!overview) return null;
  const metrics = overview.metrics;

  return (
    <main className={styles.page}>
      <header className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>MPSQRE BUILD360 · PHASE 36</p>
          <h1>Service desk & continuous improvement</h1>
          <p className={styles.subtitle}>
            Govern customer support, SLA commitments, problem management, controlled changes,
            knowledge, feedback and improvement from one tenant-safe command centre.
          </p>
          <div className={styles.chips}>
            <span>{overview.company.name}</span>
            <span>{overview.company.timezone}</span>
            <span>Policy {overview.policy.status}</span>
          </div>
        </div>
        <div className={styles.heroActions}>
          <span className={styles.activeBadge}>PHASE 36 SUPPORT OPERATIONS ACTIVE</span>
          <button type="button" disabled={working} onClick={() => void load()}>Refresh control room</button>
        </div>
      </header>

      {error ? <div className={styles.bannerError}>{error}</div> : null}
      {notice ? <div className={styles.bannerSuccess}>{notice}</div> : null}

      <section className={styles.metrics}>
        <Metric label="Open tickets" value={metrics.open_tickets ?? 0} note={`${metrics.unassigned_tickets ?? 0} unassigned`} />
        <Metric label="Critical tickets" value={metrics.critical_tickets ?? 0} note="P0 and P1 exposure" />
        <Metric label="SLA breaches" value={metrics.sla_breaches ?? 0} note={`${metrics.response_breaches ?? 0} response · ${metrics.resolution_breaches ?? 0} resolution`} />
        <Metric label="Open problems" value={metrics.open_problems ?? 0} note="Root-cause backlog" />
        <Metric label="Pending changes" value={metrics.pending_changes ?? 0} note="Assessment through schedule" />
        <Metric label="Customer rating" value={Number(metrics.average_feedback_rating ?? 0).toFixed(2)} note={`${metrics.feedback_responses ?? 0} responses`} />
      </section>

      <nav className={styles.tabs} aria-label="Support operations sections">
        {[
          ["tickets", "Service desk"],
          ["sla", "SLA control"],
          ["problems", "Problems & changes"],
          ["knowledge", "Knowledge"],
          ["improvement", "Feedback & improvement"],
        ].map(([key, label]) => (
          <button key={key} type="button" className={tab === key ? styles.tabActive : ""} onClick={() => setTab(key as Tab)}>
            {label}
          </button>
        ))}
      </nav>

      {tab === "tickets" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => void createTicket(event)}>
            <p className={styles.kicker}>TICKET INTAKE</p>
            <h2>Create support ticket</h2>
            <div className={styles.formGrid}>
              <label>Ticket code<input required value={ticketForm.code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setTicketForm({ ...ticketForm, code: event.target.value })} /></label>
              <label>Priority<select value={ticketForm.priority_code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setTicketForm({ ...ticketForm, priority_code: event.target.value })}><option>P0</option><option>P1</option><option>P2</option><option>P3</option><option>P4</option></select></label>
              <label className={styles.full}>Title<input required value={ticketForm.title} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setTicketForm({ ...ticketForm, title: event.target.value })} /></label>
              <label>Requester<input required value={ticketForm.requester_name} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setTicketForm({ ...ticketForm, requester_name: event.target.value })} /></label>
              <label>Email<input type="email" value={ticketForm.requester_email} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setTicketForm({ ...ticketForm, requester_email: event.target.value })} /></label>
              <label>Service<select value={ticketForm.catalog_item_public_id} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setTicketForm({ ...ticketForm, catalog_item_public_id: event.target.value })}><option value="">Default SLA</option>{overview.catalog_items.filter((item) => item.active).map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></label>
              <label>Category<input value={ticketForm.category_code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setTicketForm({ ...ticketForm, category_code: event.target.value })} /></label>
              <label className={styles.full}>Description<textarea value={ticketForm.description} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setTicketForm({ ...ticketForm, description: event.target.value })} /></label>
            </div>
            <button className={styles.primary} disabled={working}>Create ticket</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => void addInteraction(event)}>
            <p className={styles.kicker}>CUSTOMER RESPONSE</p>
            <h2>Add governed interaction</h2>
            <label>Ticket<select required value={selectedTicket} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setSelectedTicket(event.target.value)}><option value="">Select ticket</option>{openTickets.map((ticket) => <option key={ticket.public_id} value={ticket.public_id}>{ticket.code} · {ticket.title}</option>)}</select></label>
            <label>Response<textarea required value={interactionBody} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setInteractionBody(event.target.value)} /></label>
            <button className={styles.primary} disabled={working || !selectedTicket}>Record response</button>
          </form>

          <article className={`${styles.card} ${styles.wide}`}>
            <div className={styles.cardHeading}><div><p className={styles.kicker}>SERVICE QUEUE</p><h2>Active support tickets</h2></div><span>{openTickets.length} open</span></div>
            <div className={styles.tableWrap}>
              <table>
                <thead><tr><th>Ticket</th><th>Requester</th><th>Priority</th><th>Status</th><th>Response due</th><th>Resolution due</th><th>SLA</th><th>Action</th></tr></thead>
                <tbody>
                  {overview.tickets.map((ticket) => (
                    <tr key={ticket.public_id}>
                      <td><strong>{ticket.code}</strong><small>{ticket.title}</small></td>
                      <td>{ticket.requester_name}</td>
                      <td><span className={styles.pill}>{ticket.priority_code}</span></td>
                      <td>{ticket.status_code}</td>
                      <td>{fmt(ticket.response_due_at)}</td>
                      <td>{fmt(ticket.resolution_due_at)}</td>
                      <td className={ticket.sla_breached ? styles.danger : styles.good}>{ticket.sla_breached ? "BREACHED" : "CONTROLLED"}</td>
                      <td>
                        <select aria-label={`Transition ${ticket.code}`} defaultValue="" onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { const value = event.target.value; event.currentTarget.value = ""; if (value) void transitionTicket(ticket, value); }}>
                          <option value="">Select</option>
                          <option value="TRIAGED">Triage</option>
                          <option value="IN_PROGRESS">Start</option>
                          <option value="WAITING_CUSTOMER">Wait customer</option>
                          <option value="WAITING_INTERNAL">Wait internal</option>
                          <option value="RESOLVED">Resolve</option>
                          <option value="CLOSED">Close</option>
                          <option value="REOPENED">Reopen</option>
                          <option value="CANCELLED">Cancel</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                  {!overview.tickets.length ? <tr><td colSpan={8} className={styles.empty}>No support tickets registered.</td></tr> : null}
                </tbody>
              </table>
            </div>
          </article>
        </section>
      ) : null}

      {tab === "sla" ? (
        <section className={styles.grid}>
          <article className={styles.card}>
            <p className={styles.kicker}>SERVICE POLICY</p>
            <h2>Governance posture</h2>
            <dl className={styles.definition}>
              <div><dt>Default response</dt><dd>{overview.policy.default_response_minutes} minutes</dd></div>
              <div><dt>Default resolution</dt><dd>{overview.policy.default_resolution_minutes} minutes</dd></div>
              <div><dt>Escalation warning</dt><dd>{overview.policy.escalation_warning_percent}%</dd></div>
              <div><dt>Feedback required</dt><dd>{overview.policy.customer_feedback_required ? "Yes" : "No"}</dd></div>
            </dl>
            <button className={styles.primary} disabled={working} onClick={() => void post("sla/refresh", {})}>Refresh SLA clocks</button>
          </article>
          <article className={styles.card}>
            <p className={styles.kicker}>SERVICE CATALOG</p>
            <h2>Response commitments</h2>
            <div className={styles.catalogList}>
              {overview.catalog_items.map((item) => <div key={item.public_id}><strong>{item.name}</strong><span>{item.response_minutes}m response · {item.resolution_minutes}m resolution</span></div>)}
            </div>
          </article>
          <article className={`${styles.card} ${styles.wide}`}>
            <p className={styles.kicker}>RECENT CONTACT</p>
            <h2>Interaction timeline</h2>
            <div className={styles.timeline}>
              {overview.interactions.map((item) => <div key={item.public_id}><span>{item.ticket__code}</span><strong>{item.interaction_type_code}</strong><p>{item.body}</p><small>{fmt(item.occurred_at)}</small></div>)}
              {!overview.interactions.length ? <p className={styles.empty}>No support interactions recorded.</p> : null}
            </div>
          </article>
        </section>
      ) : null}

      {tab === "problems" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => void createProblem(event)}>
            <p className={styles.kicker}>PROBLEM MANAGEMENT</p>
            <h2>Register root-cause investigation</h2>
            <label>Problem code<input required value={problemForm.code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setProblemForm({ ...problemForm, code: event.target.value })} /></label>
            <label>Title<input required value={problemForm.title} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setProblemForm({ ...problemForm, title: event.target.value })} /></label>
            <label>Source ticket<select value={problemForm.source_ticket_public_id} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setProblemForm({ ...problemForm, source_ticket_public_id: event.target.value })}><option value="">No source ticket</option>{overview.tickets.map((ticket) => <option key={ticket.public_id} value={ticket.public_id}>{ticket.code}</option>)}</select></label>
            <label>Impact<textarea value={problemForm.impact_summary} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setProblemForm({ ...problemForm, impact_summary: event.target.value })} /></label>
            <button className={styles.primary} disabled={working}>Create problem</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => void createChange(event)}>
            <p className={styles.kicker}>CHANGE GOVERNANCE</p>
            <h2>Create controlled change</h2>
            <label>Change code<input required value={changeForm.code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setChangeForm({ ...changeForm, code: event.target.value })} /></label>
            <label>Title<input required value={changeForm.title} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setChangeForm({ ...changeForm, title: event.target.value })} /></label>
            <div className={styles.formGrid}>
              <label>Type<select value={changeForm.change_type_code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setChangeForm({ ...changeForm, change_type_code: event.target.value })}><option>STANDARD</option><option>NORMAL</option><option>EMERGENCY</option></select></label>
              <label>Risk<select value={changeForm.risk_code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setChangeForm({ ...changeForm, risk_code: event.target.value })}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></label>
            </div>
            <label>Rollback plan<textarea value={changeForm.rollback_plan} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setChangeForm({ ...changeForm, rollback_plan: event.target.value })} /></label>
            <button className={styles.primary} disabled={working}>Create change</button>
          </form>

          <article className={styles.card}>
            <p className={styles.kicker}>KNOWN PROBLEMS</p>
            <h2>Problem register</h2>
            <div className={styles.list}>
              {overview.problems.map((item) => <div key={item.public_id}><span>{item.priority_code}</span><strong>{item.code} · {item.title}</strong><small>{item.status_code}</small></div>)}
              {!overview.problems.length ? <p className={styles.empty}>No problem records.</p> : null}
            </div>
          </article>

          <article className={styles.card}>
            <p className={styles.kicker}>CHANGE PORTFOLIO</p>
            <h2>Governed service changes</h2>
            <div className={styles.list}>
              {overview.changes.map((item) => <div key={item.public_id}><span>{item.risk_code}</span><strong>{item.code} · {item.title}</strong><small>{item.status_code}</small></div>)}
              {!overview.changes.length ? <p className={styles.empty}>No change requests.</p> : null}
            </div>
          </article>
        </section>
      ) : null}

      {tab === "knowledge" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => void createArticle(event)}>
            <p className={styles.kicker}>KNOWLEDGE CREATION</p>
            <h2>Draft knowledge article</h2>
            <div className={styles.formGrid}>
              <label>Article code<input required value={articleForm.code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setArticleForm({ ...articleForm, code: event.target.value })} /></label>
              <label>Audience<select value={articleForm.audience_code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setArticleForm({ ...articleForm, audience_code: event.target.value })}><option>INTERNAL</option><option>CUSTOMER</option><option>PARTNER</option><option>PUBLIC</option></select></label>
              <label className={styles.full}>Title<input required value={articleForm.title} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setArticleForm({ ...articleForm, title: event.target.value })} /></label>
              <label className={styles.full}>Summary<textarea value={articleForm.summary} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setArticleForm({ ...articleForm, summary: event.target.value })} /></label>
              <label className={styles.full}>Content<textarea required value={articleForm.content} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setArticleForm({ ...articleForm, content: event.target.value })} /></label>
            </div>
            <button className={styles.primary} disabled={working}>Create draft</button>
          </form>
          <article className={styles.card}>
            <p className={styles.kicker}>KNOWLEDGE BASE</p>
            <h2>Controlled articles</h2>
            <div className={styles.list}>
              {overview.knowledge_articles.map((item) => <div key={item.public_id}><span>{item.audience_code}</span><strong>{item.code} · {item.title}</strong><small>{item.status_code}</small></div>)}
              {!overview.knowledge_articles.length ? <p className={styles.empty}>No knowledge articles.</p> : null}
            </div>
          </article>
        </section>
      ) : null}

      {tab === "improvement" ? (
        <section className={styles.grid}>
          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => void createFeedback(event)}>
            <p className={styles.kicker}>VOICE OF CUSTOMER</p>
            <h2>Record customer feedback</h2>
            <label>Resolved ticket<select required value={feedbackForm.ticket_public_id} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setFeedbackForm({ ...feedbackForm, ticket_public_id: event.target.value })}><option value="">Select ticket</option>{overview.tickets.filter((item) => ["RESOLVED", "CLOSED"].includes(item.status_code)).map((ticket) => <option key={ticket.public_id} value={ticket.public_id}>{ticket.code}</option>)}</select></label>
            <label>Rating<select value={feedbackForm.rating} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setFeedbackForm({ ...feedbackForm, rating: event.target.value })}><option value="5">5 · Excellent</option><option value="4">4 · Good</option><option value="3">3 · Acceptable</option><option value="2">2 · Poor</option><option value="1">1 · Critical</option></select></label>
            <label>Comments<textarea value={feedbackForm.comments} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setFeedbackForm({ ...feedbackForm, comments: event.target.value })} /></label>
            <button className={styles.primary} disabled={working || !feedbackForm.ticket_public_id}>Record feedback</button>
          </form>

          <form className={styles.card} onSubmit={(event: FormEvent<HTMLFormElement>) => void createImprovement(event)}>
            <p className={styles.kicker}>CONTINUOUS IMPROVEMENT</p>
            <h2>Create improvement item</h2>
            <label>Improvement code<input required value={improvementForm.code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setImprovementForm({ ...improvementForm, code: event.target.value })} /></label>
            <label>Title<input required value={improvementForm.title} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setImprovementForm({ ...improvementForm, title: event.target.value })} /></label>
            <label>Theme<input value={improvementForm.theme_code} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setImprovementForm({ ...improvementForm, theme_code: event.target.value })} /></label>
            <label>Expected benefit<textarea value={improvementForm.expected_benefit} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setImprovementForm({ ...improvementForm, expected_benefit: event.target.value })} /></label>
            <button className={styles.primary} disabled={working}>Add to backlog</button>
          </form>

          <article className={styles.card}>
            <p className={styles.kicker}>CUSTOMER SENTIMENT</p>
            <h2>Recent feedback</h2>
            <div className={styles.list}>
              {overview.feedback.map((item) => <div key={item.public_id}><span>{item.rating}/5</span><strong>{item.ticket__code}</strong><small>{item.comments || "No comment"}</small></div>)}
              {!overview.feedback.length ? <p className={styles.empty}>No feedback received.</p> : null}
            </div>
          </article>

          <article className={styles.card}>
            <p className={styles.kicker}>IMPROVEMENT PORTFOLIO</p>
            <h2>Value realization backlog</h2>
            <div className={styles.list}>
              {overview.improvements.map((item) => <div key={item.public_id}><span>{item.priority_code}</span><strong>{item.code} · {item.title}</strong><small>{item.status_code}</small></div>)}
              {!overview.improvements.length ? <p className={styles.empty}>No improvement items.</p> : null}
            </div>
          </article>
        </section>
      ) : null}
    </main>
  );
}
