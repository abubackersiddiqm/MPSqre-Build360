"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./partner.module.css";

type Grant = {
  public_id: string;
  project: { public_id: string; code: string; name: string };
  site: { public_id: string; code: string; name: string } | null;
  scopes: string[];
  effective_to: string | null;
};
type Item = {
  public_id: string;
  reference: string;
  type: string;
  title: string;
  status: string;
  priority: string;
  due_at: string | null;
  project: { public_id: string; code: string; name: string };
  site: { public_id: string; code: string; name: string } | null;
  partner: { public_id: string; code: string; name: string };
  assigned_contact: { public_id: string; name: string } | null;
  submission_count: number;
  message_count: number;
};
type Overview = {
  company: { name: string };
  contact: { name: string; email: string; can_approve: boolean; organization: { name: string; type: string } };
  metrics: Record<string, number>;
  grants: Grant[];
  items: Item[];
};
type Tab = "queue" | "projects" | "submitted";

async function readJson(response: Response) {
  const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok) {
    const message = typeof payload.message === "string" ? payload.message : JSON.stringify(payload);
    throw new Error(message || `Request failed (${response.status})`);
  }
  return payload;
}

async function post(path: string, data: unknown) {
  return readJson(await fetch(`/api/partner/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }));
}

export function PartnerClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState<Tab>("queue");
  const [activeItem, setActiveItem] = useState<string | null>(null);
  const [mode, setMode] = useState<"submit" | "message" | "decide" | null>(null);
  const [query, setQuery] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/partner/overview", { cache: "no-store" });
      setOverview(await readJson(response) as unknown as Overview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Partner workspace could not be loaded.");
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

  const filteredItems = useMemo(() => {
    const source = tab === "submitted" ? (overview?.items ?? []).filter((item) => item.submission_count > 0) : overview?.items ?? [];
    const normalized = query.trim().toLowerCase();
    if (!normalized) return source;
    return source.filter((item) => [item.reference, item.title, item.type, item.project.name, item.status].some((value) => value.toLowerCase().includes(normalized)));
  }, [overview, query, tab]);

  async function execute(action: () => Promise<Record<string, unknown>>, success: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      await action();
      setNotice(success);
      setActiveItem(null); setMode(null);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The request could not be completed.");
    } finally { setBusy(false); }
  }

  async function submitResponse(event: FormEvent<HTMLFormElement>, item: Item) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    let structured: Record<string, unknown> = {};
    const raw = String(data.get("data_json") ?? "").trim();
    if (raw) {
      try { structured = JSON.parse(raw) as Record<string, unknown>; }
      catch { setError("Structured response must be valid JSON."); return; }
    }
    await execute(() => post(`items/${item.public_id}/submissions`, {
      summary: data.get("summary"), data: structured, attachment_references: [],
    }), "Response submitted for review.");
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>, item: Item) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await execute(() => post(`items/${item.public_id}/messages`, { body: data.get("body"), attachment_references: [] }), "Message sent to the project team.");
  }

  async function decide(event: FormEvent<HTMLFormElement>, item: Item) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await execute(() => post(`items/${item.public_id}/decision`, { decision_code: data.get("decision_code"), notes: data.get("notes") }), "Decision recorded.");
  }

  function open(item: Item, nextMode: "submit" | "message" | "decide") {
    setActiveItem(item.public_id); setMode(nextMode); setNotice(""); setError("");
  }

  if (loading && !overview) return <div className={styles.loading}>Opening your external partner desk...</div>;
  if (!overview) {
    return <div className={styles.fatal}><h2>Partner portal unavailable</h2><strong>Your external collaboration profile could not be opened.</strong><p>{error}</p><button className={styles.primary} onClick={() => void refresh()}>Retry portal</button></div>;
  }

  const m = overview.metrics;
  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <div className={styles.eyebrow}>MPSqre Build360 · External Partner Portal · Phase 32</div>
          <h1>Partner desk</h1>
          <p>A secure, project-scoped workspace for requests, submissions, approvals and communication with {overview.company.name}.</p>
          <div className={styles.identity}><span>{overview.contact.organization.name}</span><span>{overview.contact.organization.type}</span><span>{overview.contact.name}</span><span>{overview.contact.email}</span></div>
        </div>
        <div><div className={styles.status}>PHASE 32 PARTNER PORTAL ACTIVE</div><button className={styles.refresh} onClick={() => void refresh()} disabled={busy}>Refresh partner desk</button></div>
      </header>

      <section className={styles.metrics}>
        {[["Active projects",m.active_projects],["Open requests",m.open_items],["Due today",m.due_today],["Overdue",m.overdue],["Submitted",m.submitted]].map(([label,value]) => <article className={styles.metric} key={String(label)}><span>{label}</span><strong>{value}</strong></article>)}
      </section>

      {error ? <div className={styles.error}>{error}</div> : null}
      {notice ? <div className={styles.notice}>{notice}</div> : null}

      <nav className={styles.tabs}>
        <button className={`${styles.tab} ${tab === "queue" ? styles.active : ""}`} onClick={() => setTab("queue")}>My collaboration queue</button>
        <button className={`${styles.tab} ${tab === "projects" ? styles.active : ""}`} onClick={() => setTab("projects")}>Authorized projects</button>
        <button className={`${styles.tab} ${tab === "submitted" ? styles.active : ""}`} onClick={() => setTab("submitted")}>Submitted items</button>
      </nav>

      {tab === "projects" ? (
        <section className={styles.card}>
          <h2>Authorized project access</h2><p>These grants define the exact projects, sites and actions available to your account.</p>
          <div className={styles.grants}>{overview.grants.map((grant) => <article className={styles.grant} key={grant.public_id}><strong>{grant.project.code} · {grant.project.name}</strong><small>{grant.site ? `${grant.site.code} · ${grant.site.name}` : "All authorized project sites"}</small><div className={styles.scopes}>{grant.scopes.map((scope) => <span key={scope}>{scope}</span>)}</div></article>)}{!overview.grants.length ? <div className={styles.empty}>No active project grants are available. Contact the company administrator.</div> : null}</div>
        </section>
      ) : null}

      {tab !== "projects" ? (
        <section className={styles.card}>
          <input className={styles.search} value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Search requests" />
          <div className={styles.queue}>
            {filteredItems.map((item) => {
              const expanded = activeItem === item.public_id;
              return <article className={styles.item} key={item.public_id}>
                <div className={styles.itemTop}><div><div className={styles.ref}>{item.reference} · {item.type}</div><h3>{item.title}</h3></div><span className={styles.badge}>{item.status}</span></div>
                <div className={styles.meta}><span>{item.project.code} · {item.project.name}</span>{item.site ? <span>{item.site.code} · {item.site.name}</span> : null}<span>{item.priority}</span><span>{item.due_at ? new Date(item.due_at).toLocaleString() : "No deadline"}</span><span>{item.submission_count} submission(s)</span><span>{item.message_count} message(s)</span></div>
                <div className={styles.actions}><button className={styles.primary} onClick={() => open(item,"submit")}>Submit response</button><button className={styles.secondary} onClick={() => open(item,"message")}>Message project team</button>{overview.contact.can_approve ? <button className={styles.secondary} onClick={() => open(item,"decide")}>Record decision</button> : null}</div>
                {expanded && mode === "submit" ? <form className={styles.form} onSubmit={(event: FormEvent<HTMLFormElement>) => void submitResponse(event,item)}><textarea name="summary" placeholder="Response summary, commercial clarification or technical note" required /><textarea name="data_json" placeholder='Optional structured JSON, e.g. {"quoted_amount":125000,"currency":"INR"}' /><div className={styles.actions}><button className={styles.primary} disabled={busy}>Submit response</button><button type="button" className={styles.secondary} onClick={() => setActiveItem(null)}>Cancel</button></div></form> : null}
                {expanded && mode === "message" ? <form className={styles.form} onSubmit={(event: FormEvent<HTMLFormElement>) => void sendMessage(event,item)}><textarea name="body" placeholder="Write a governed project message" required /><div className={styles.actions}><button className={styles.primary} disabled={busy}>Send message</button><button type="button" className={styles.secondary} onClick={() => setActiveItem(null)}>Cancel</button></div></form> : null}
                {expanded && mode === "decide" ? <form className={styles.form} onSubmit={(event: FormEvent<HTMLFormElement>) => void decide(event,item)}><select name="decision_code"><option>APPROVED</option><option>REJECTED</option><option>REVISION_REQUIRED</option><option>ACKNOWLEDGED</option></select><textarea name="notes" placeholder="Decision notes" /><div className={styles.actions}><button className={styles.primary} disabled={busy}>Record decision</button><button type="button" className={styles.secondary} onClick={() => setActiveItem(null)}>Cancel</button></div></form> : null}
              </article>;
            })}
            {!filteredItems.length ? <div className={styles.empty}>No collaboration items are available in this view.</div> : null}
          </div>
        </section>
      ) : null}
    </main>
  );
}
