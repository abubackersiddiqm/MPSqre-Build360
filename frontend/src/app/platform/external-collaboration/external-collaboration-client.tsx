"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./external-collaboration.module.css";

type Partner = { public_id: string; code: string; name: string; type: string; status: string; contact_count: number; open_item_count: number };
type Contact = { public_id: string; organization_public_id: string; organization_name: string; name: string; email: string; status: string; can_approve: boolean };
type Site = { public_id: string; code: string; name: string };
type Project = { public_id: string; code: string; name: string; status: string; sites: Site[] };
type Item = {
  public_id: string;
  reference: string;
  type: string;
  title: string;
  status: string;
  priority: string;
  due_at: string | null;
  project: { public_id: string; code: string; name: string };
  site: Site | null;
  partner: { public_id: string; code: string; name: string };
  assigned_contact: { public_id: string; name: string } | null;
  submission_count: number;
  message_count: number;
};
type Overview = {
  company: { name: string; currency: string; timezone: string };
  metrics: Record<string, number>;
  partners: Partner[];
  contacts: Contact[];
  projects: Project[];
  items: Item[];
  capabilities: Record<string, boolean>;
};

type Tab = "partners" | "access" | "requests" | "reviews";

async function readJson(response: Response) {
  const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok) {
    const message = typeof payload.message === "string" ? payload.message : JSON.stringify(payload);
    throw new Error(message || `Request failed (${response.status})`);
  }
  return payload;
}

async function post(path: string, data: unknown) {
  return readJson(await fetch(`/api/platform/external-collaboration/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }));
}

export function ExternalCollaborationClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("partners");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [invitationUrl, setInvitationUrl] = useState("");
  const [query, setQuery] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/platform/external-collaboration/overview", { cache: "no-store" });
      setOverview(await readJson(response) as unknown as Overview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "External collaboration could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void refresh();
    });
    return () => controller.abort();
  }, [refresh]);

  const selectedPartner = overview?.partners[0];
  const selectedProject = overview?.projects[0];
  const filteredItems = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return overview?.items ?? [];
    return (overview?.items ?? []).filter((item) =>
      [item.reference, item.title, item.type, item.partner.name, item.project.name, item.status]
        .some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [overview, query]);

  async function execute(action: () => Promise<Record<string, unknown>>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await action();
      const url = typeof result.invitation_url === "string" ? result.invitation_url : "";
      if (url) setInvitationUrl(`${window.location.origin}${url}`);
      setNotice(success);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The request could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  async function createPartner(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await execute(() => post("partners", Object.fromEntries(data.entries())), "Partner organization created.");
    event.currentTarget.reset();
  }

  async function inviteContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const partnerId = String(data.get("partner_public_id") ?? "");
    await execute(() => post(`partners/${partnerId}/invite`, {
      full_name: data.get("full_name"),
      email: data.get("email"),
      mobile: data.get("mobile"),
      job_title: data.get("job_title"),
      can_approve: data.get("can_approve") === "on",
      is_primary: data.get("is_primary") === "on",
    }), "External contact invited. Copy the one-time activation URL below.");
    event.currentTarget.reset();
  }

  async function createGrant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const scopes = data.getAll("scopes").map(String);
    await execute(() => post("grants", {
      contact_public_id: data.get("contact_public_id"),
      project_public_id: data.get("project_public_id"),
      site_public_id: data.get("site_public_id") || null,
      scopes,
      effective_from: data.get("effective_from"),
      effective_to: data.get("effective_to") || null,
    }), "Project access granted.");
    event.currentTarget.reset();
  }

  async function createItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const amount = String(data.get("amount") ?? "").trim();
    await execute(() => post("items", {
      organization_public_id: data.get("organization_public_id"),
      project_public_id: data.get("project_public_id"),
      site_public_id: data.get("site_public_id") || null,
      assigned_contact_public_id: data.get("assigned_contact_public_id") || null,
      reference: data.get("reference"),
      item_type_code: data.get("item_type_code"),
      title: data.get("title"),
      description: data.get("description"),
      priority_code: data.get("priority_code"),
      due_at: data.get("due_at") || null,
      response_required: data.get("response_required") === "on",
      approval_required: data.get("approval_required") === "on",
      amount: amount || null,
      currency: amount ? data.get("currency") : "",
      status_code: "ISSUED",
    }), "Collaboration request issued.");
    event.currentTarget.reset();
  }

  async function decide(item: Item, decisionCode: string) {
    const notes = window.prompt(`${decisionCode.replaceAll("_", " ")} notes`, "") ?? "";
    await execute(() => post(`items/${item.public_id}/decision`, { decision_code: decisionCode, notes }), `Item ${decisionCode.toLowerCase().replaceAll("_", " ")}.`);
  }

  async function message(item: Item) {
    const body = window.prompt(`Message ${item.partner.name} about ${item.reference}`, "");
    if (!body) return;
    await execute(() => post(`items/${item.public_id}/messages`, { body, attachment_references: [], is_internal: false }), "Message posted.");
  }

  if (loading && !overview) return <div className={styles.loading}>Opening the external collaboration control room...</div>;
  if (!overview) {
    return <div className={styles.fatal}><h2>External collaboration unavailable</h2><strong>The partner control room could not be opened.</strong><p>{error}</p><button className={styles.primary} onClick={() => void refresh()}>Retry workspace</button></div>;
  }

  const m = overview.metrics;
  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <div className={styles.eyebrow}>MPSqre Build360 · Phase 32</div>
          <h1>External collaboration</h1>
          <p>Onboard vendors, subcontractors, clients and consultants; grant project-scoped access; issue requests; receive submissions; govern decisions and retain a complete communication trail.</p>
        </div>
        <div className={styles.status}>
          <span className={styles.pill}>PHASE 32 EXTERNAL COLLABORATION ACTIVE</span>
          <button className={styles.primary} onClick={() => void refresh()} disabled={busy}>Refresh control room</button>
        </div>
      </header>

      <section className={styles.metrics} aria-label="Collaboration metrics">
        {[
          ["Active partners", m.active_partners], ["Active contacts", m.active_contacts], ["Pending invites", m.pending_invites],
          ["Project grants", m.active_project_grants], ["Open items", m.open_items], ["Overdue", m.overdue_items], ["Awaiting review", m.pending_submissions],
        ].map(([label, value]) => <article className={styles.metric} key={String(label)}><span>{label}</span><strong>{value}</strong></article>)}
      </section>

      {error ? <div className={styles.error}>{error}</div> : null}
      {notice ? <div className={styles.notice}>{notice}</div> : null}
      {invitationUrl ? <div className={styles.copyBox}><span>{invitationUrl}</span><button className={styles.smallButton} onClick={() => void navigator.clipboard.writeText(invitationUrl)}>Copy invitation</button></div> : null}

      <nav className={styles.tabs} aria-label="External collaboration sections">
        {(["partners", "access", "requests", "reviews"] as Tab[]).map((value) => (
          <button key={value} className={`${styles.tab} ${tab === value ? styles.active : ""}`} onClick={() => setTab(value)}>
            {value === "partners" ? "Partner network" : value === "access" ? "Access grants" : value === "requests" ? "Requests & submissions" : "Review & decisions"}
          </button>
        ))}
      </nav>

      {tab === "partners" ? (
        <section className={styles.grid}>
          <article className={styles.card}>
            <div className={styles.sectionLabel}>Partner master</div><h2>Create partner organization</h2><p>Register the legal counterparty before inviting external users.</p>
            <form onSubmit={createPartner}>
              <div className={styles.formGrid}>
                <div className={styles.field}><label>Partner code</label><input name="code" required placeholder="VND-001" /></div>
                <div className={styles.field}><label>Partner type</label><select name="organization_type_code"><option>VENDOR</option><option>SUBCONTRACTOR</option><option>CLIENT</option><option>CONSULTANT</option><option>OTHER</option></select></div>
                <div className={`${styles.field} ${styles.full}`}><label>Legal name</label><input name="legal_name" required /></div>
                <div className={`${styles.field} ${styles.full}`}><label>Display name</label><input name="display_name" required /></div>
                <div className={styles.field}><label>Registration number</label><input name="registration_number" /></div>
                <div className={styles.field}><label>Tax registration</label><input name="tax_registration_number" /></div>
                <div className={styles.field}><label>Country code</label><input name="country_code" maxLength={2} placeholder="IN" /></div>
                <div className={styles.field}><label>Risk rating</label><select name="risk_rating_code"><option>UNASSESSED</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option></select></div>
                <div className={styles.field}><label>Primary email</label><input name="primary_email" type="email" /></div>
                <div className={styles.field}><label>Primary phone</label><input name="primary_phone" /></div>
              </div>
              <div className={styles.actions}><button className={styles.primary} disabled={busy || !overview.capabilities.can_manage}>Create partner</button></div>
            </form>
          </article>
          <article className={styles.card}>
            <div className={styles.sectionLabel}>Partner directory</div><h2>Registered counterparties</h2>
            <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Partner</th><th>Type</th><th>Contacts</th><th>Open items</th><th>Status</th></tr></thead><tbody>
              {overview.partners.map((partner) => <tr key={partner.public_id}><td><div className={styles.titleStack}><strong>{partner.name}</strong><small>{partner.code}</small></div></td><td>{partner.type}</td><td>{partner.contact_count}</td><td>{partner.open_item_count}</td><td><span className={styles.badge}>{partner.status}</span></td></tr>)}
              {!overview.partners.length ? <tr><td colSpan={5} className={styles.empty}>No partner organizations have been registered.</td></tr> : null}
            </tbody></table></div>
            <hr />
            <div className={styles.sectionLabel}>External identity</div><h2>Invite partner contact</h2>
            <form onSubmit={inviteContact}>
              <div className={styles.formGrid}>
                <div className={`${styles.field} ${styles.full}`}><label>Partner organization</label><select name="partner_public_id" required defaultValue={selectedPartner?.public_id ?? ""}><option value="" disabled>Select partner</option>{overview.partners.map((partner) => <option key={partner.public_id} value={partner.public_id}>{partner.code} · {partner.name}</option>)}</select></div>
                <div className={styles.field}><label>Full name</label><input name="full_name" required /></div>
                <div className={styles.field}><label>Email</label><input name="email" type="email" required /></div>
                <div className={styles.field}><label>Mobile</label><input name="mobile" /></div>
                <div className={styles.field}><label>Job title</label><input name="job_title" /></div>
                <label className={styles.checkRow}><input type="checkbox" name="is_primary" /> Primary contact</label>
                <label className={styles.checkRow}><input type="checkbox" name="can_approve" /> External approver</label>
              </div>
              <div className={styles.actions}><button className={styles.primary} disabled={busy || !overview.capabilities.can_invite}>Create invitation</button></div>
            </form>
          </article>
        </section>
      ) : null}

      {tab === "access" ? (
        <section className={styles.grid}>
          <article className={styles.card}>
            <div className={styles.sectionLabel}>Least-privilege access</div><h2>Grant project access</h2><p>External contacts see only explicitly granted projects, sites and collaboration scopes.</p>
            <form onSubmit={createGrant}>
              <div className={styles.formGrid}>
                <div className={`${styles.field} ${styles.full}`}><label>Partner contact</label><select name="contact_public_id" required><option value="">Select contact</option>{overview.contacts.map((contact) => <option key={contact.public_id} value={contact.public_id}>{contact.organization_name} · {contact.name}</option>)}</select></div>
                <div className={`${styles.field} ${styles.full}`}><label>Project</label><select name="project_public_id" required defaultValue={selectedProject?.public_id ?? ""}><option value="" disabled>Select project</option>{overview.projects.map((project) => <option key={project.public_id} value={project.public_id}>{project.code} · {project.name}</option>)}</select></div>
                <div className={`${styles.field} ${styles.full}`}><label>Site (optional)</label><select name="site_public_id"><option value="">All project sites</option>{overview.projects.flatMap((project) => project.sites.map((site) => <option key={site.public_id} value={site.public_id}>{project.code} · {site.code} · {site.name}</option>))}</select></div>
                <div className={styles.field}><label>Effective from</label><input name="effective_from" type="datetime-local" required /></div>
                <div className={styles.field}><label>Effective to</label><input name="effective_to" type="datetime-local" /></div>
                <div className={`${styles.field} ${styles.full}`}><label>Scopes</label><div className={styles.scopeGrid}>{["SUBMIT", "MESSAGE", "APPROVE", "RFQ", "SUBMITTAL", "DOCUMENT_REVIEW", "INVOICE", "CLAIM", "ALL"].map((scope) => <label className={styles.scope} key={scope}><input type="checkbox" name="scopes" value={scope} defaultChecked={scope === "SUBMIT" || scope === "MESSAGE"} />{scope}</label>)}</div></div>
              </div>
              <div className={styles.actions}><button className={styles.primary} disabled={busy || !overview.capabilities.can_grant}>Grant access</button></div>
            </form>
          </article>
          <article className={styles.card}>
            <div className={styles.sectionLabel}>External identities</div><h2>Contact access posture</h2>
            <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Contact</th><th>Partner</th><th>Email</th><th>Role posture</th><th>Status</th></tr></thead><tbody>
              {overview.contacts.map((contact) => <tr key={contact.public_id}><td>{contact.name}</td><td>{contact.organization_name}</td><td>{contact.email}</td><td>{contact.can_approve ? "External approver" : "External collaborator"}</td><td><span className={styles.badge}>{contact.status}</span></td></tr>)}
              {!overview.contacts.length ? <tr><td colSpan={5} className={styles.empty}>Invite a partner contact to begin scoped collaboration.</td></tr> : null}
            </tbody></table></div>
          </article>
        </section>
      ) : null}

      {tab === "requests" ? (
        <section className={styles.grid}>
          <article className={styles.card}>
            <div className={styles.sectionLabel}>Controlled request</div><h2>Issue collaboration item</h2>
            <form onSubmit={createItem}>
              <div className={styles.formGrid}>
                <div className={styles.field}><label>Partner</label><select name="organization_public_id" required><option value="">Select partner</option>{overview.partners.map((partner) => <option key={partner.public_id} value={partner.public_id}>{partner.code} · {partner.name}</option>)}</select></div>
                <div className={styles.field}><label>Assigned contact</label><select name="assigned_contact_public_id"><option value="">Any authorized contact</option>{overview.contacts.map((contact) => <option key={contact.public_id} value={contact.public_id}>{contact.organization_name} · {contact.name}</option>)}</select></div>
                <div className={styles.field}><label>Project</label><select name="project_public_id" required><option value="">Select project</option>{overview.projects.map((project) => <option key={project.public_id} value={project.public_id}>{project.code} · {project.name}</option>)}</select></div>
                <div className={styles.field}><label>Site</label><select name="site_public_id"><option value="">Project-wide</option>{overview.projects.flatMap((project) => project.sites.map((site) => <option key={site.public_id} value={site.public_id}>{project.code} · {site.name}</option>))}</select></div>
                <div className={styles.field}><label>Reference</label><input name="reference" required placeholder="RFQ-2026-001" /></div>
                <div className={styles.field}><label>Type</label><select name="item_type_code"><option>RFQ</option><option>SUBMITTAL</option><option>DOCUMENT_REVIEW</option><option>APPROVAL</option><option>INVOICE</option><option>CLAIM</option><option>MEETING_ACTION</option><option>GENERAL</option></select></div>
                <div className={`${styles.field} ${styles.full}`}><label>Title</label><input name="title" required /></div>
                <div className={`${styles.field} ${styles.full}`}><label>Description</label><textarea name="description" /></div>
                <div className={styles.field}><label>Priority</label><select name="priority_code"><option>NORMAL</option><option>LOW</option><option>HIGH</option><option>CRITICAL</option></select></div>
                <div className={styles.field}><label>Due at</label><input name="due_at" type="datetime-local" /></div>
                <div className={styles.field}><label>Amount</label><input name="amount" type="number" min="0" step="0.01" /></div>
                <div className={styles.field}><label>Currency</label><input name="currency" defaultValue={overview.company.currency} maxLength={3} /></div>
                <label className={styles.checkRow}><input type="checkbox" name="response_required" defaultChecked /> Response required</label>
                <label className={styles.checkRow}><input type="checkbox" name="approval_required" /> Approval required</label>
              </div>
              <div className={styles.actions}><button className={styles.primary} disabled={busy || !overview.capabilities.can_request}>Issue request</button></div>
            </form>
          </article>
          <article className={styles.card}>
            <div className={styles.toolbar}><div><div className={styles.sectionLabel}>Collaboration ledger</div><h2>Requests and submissions</h2></div><input value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Search request" /></div>
            <div className={styles.itemCards}>{filteredItems.map((item) => <div className={styles.itemCard} key={item.public_id}><div className={styles.itemTop}><div className={styles.titleStack}><strong>{item.reference} · {item.title}</strong><small>{item.partner.name} · {item.project.name}{item.site ? ` · ${item.site.name}` : ""}</small></div><span className={styles.badge}>{item.status}</span></div><div className={styles.itemMeta}><span>{item.type}</span><span>{item.priority}</span><span>{item.submission_count} submission(s)</span><span>{item.message_count} message(s)</span><span>{item.due_at ? new Date(item.due_at).toLocaleString() : "No deadline"}</span></div><div className={styles.rowActions}><button className={styles.smallButton} onClick={() => void message(item)}>Message partner</button></div></div>)}{!filteredItems.length ? <div className={styles.empty}>No collaboration items match this view.</div> : null}</div>
          </article>
        </section>
      ) : null}

      {tab === "reviews" ? (
        <section className={styles.card}>
          <div className={styles.toolbar}><div><div className={styles.sectionLabel}>Maker-checker governance</div><h2>Submission review queue</h2></div><input value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Search review queue" /></div>
          <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Request</th><th>Partner / project</th><th>Status</th><th>Submissions</th><th>Decision</th></tr></thead><tbody>
            {filteredItems.map((item) => <tr key={item.public_id}><td><div className={styles.titleStack}><strong>{item.reference}</strong><small>{item.title}</small></div></td><td>{item.partner.name}<br /><span className={styles.muted}>{item.project.name}</span></td><td><span className={styles.badge}>{item.status}</span></td><td>{item.submission_count}</td><td><div className={styles.rowActions}><button className={styles.smallButton} onClick={() => void decide(item, "APPROVED")}>Approve</button><button className={styles.smallButton} onClick={() => void decide(item, "REVISION_REQUIRED")}>Revision</button><button className={styles.danger} onClick={() => void decide(item, "REJECTED")}>Reject</button></div></td></tr>)}
            {!filteredItems.length ? <tr><td colSpan={5} className={styles.empty}>No collaboration items are awaiting action.</td></tr> : null}
          </tbody></table></div>
        </section>
      ) : null}
    </main>
  );
}
