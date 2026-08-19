"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./project-work.module.css";

type Person = { public_id: string; employee_number: string; display_name: string; job_title: string };
type Location = { public_id: string; code: string; name: string; location_type_code: string };
type Project = {
  public_id: string; code: string; name: string; description: string; project_type_code: string;
  status_code: string; priority_code: string; manager_public_id: string | null; manager_name: string | null;
  location_public_id: string | null; location_name: string | null; start_date: string; target_end_date: string;
  actual_end_date: string | null; currency: string; budget: string | null; version: number;
};
type Site = { public_id: string; project_public_id: string; project_code: string; code: string; name: string; location_name: string | null; status_code: string; start_date: string | null; target_end_date: string | null; version: number };
type WBS = { public_id: string; project_public_id: string; project_code: string; code: string; name: string; parent_public_id: string | null; parent_name: string | null; sequence: number; level: number; status_code: string; version: number };
type WorkPackage = { public_id: string; project_public_id: string; project_code: string; wbs_node_public_id: string; wbs_name: string; code: string; name: string; owner_name: string | null; planned_start: string; planned_end: string; status_code: string; progress_weight: string; version: number };
type Milestone = { public_id: string; project_public_id: string; project_code: string; code: string; name: string; target_date: string; owner_name: string | null; status_code: string; version: number };
type Checklist = { public_id: string; sequence: number; title: string; is_required: boolean; is_completed: boolean; version: number };
type WorkItem = {
  public_id: string; project_public_id: string; project_code: string; site_public_id: string | null; site_name: string | null;
  work_package_public_id: string | null; work_package_name: string | null; code: string; title: string; description: string;
  work_type_code: string; status_code: string; priority_code: string; planned_start: string | null; due_date: string | null;
  progress_percent: string; estimated_hours: string | null; primary_assignee_public_id: string | null; primary_assignee_name: string | null;
  reviewer_public_id: string | null; reviewer_name: string | null; is_overdue: boolean; version: number; checklist: Checklist[];
};
type ProgressEntry = { public_id: string; project_code: string; work_item_code: string | null; progress_date: string; quantity_completed: string; unit_code: string; progress_percent: string | null; hours_worked: string; note: string; blockers: string; recorded_by_name: string | null };
type Timesheet = { public_id: string; employee_public_id: string; employee_number: string; employee_name: string; project_public_id: string; project_code: string; work_item_public_id: string | null; work_item_code: string | null; work_date: string; hours: string; description: string; status_code: string; review_note: string; version: number };
type Approval = { public_id: string; work_item_public_id: string; work_item_code: string; work_item_title: string; project_code: string; approval_type_code: string; reviewer_public_id: string; reviewer_name: string; status_code: string; request_note: string; decision_note: string; requested_at: string; version: number };
type Overview = {
  company: { display_name: string; timezone: string; currency: string };
  summary: { active_project_count: number; open_work_count: number; overdue_work_count: number; blocked_work_count: number; pending_approval_count: number; submitted_timesheet_count: number; approved_hours_this_week: string; milestones_due_30_days: number };
  projects: Project[]; sites: Site[]; wbs_nodes: WBS[]; work_packages: WorkPackage[]; milestones: Milestone[];
  work_items: WorkItem[]; progress_entries: ProgressEntry[]; timesheets: Timesheet[]; approvals: Approval[];
  people: Person[]; locations: Location[];
};
type Tab = "portfolio" | "planning" | "work" | "progress" | "approvals";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/platform/project-work/${path}`, {
    cache: "no-store",
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : typeof payload.message === "string" ? payload.message : Object.values(payload).flat().join(" ");
    throw new Error(detail || "Request failed.");
  }
  return payload as T;
}

function value(form: FormData, name: string): string { return String(form.get(name) ?? "").trim(); }
function nullable(form: FormData, name: string): string | null { return value(form, name) || null; }
function today(): string { return new Date().toISOString().slice(0, 10); }
function plusDays(days: number): string { const date = new Date(); date.setDate(date.getDate() + days); return date.toISOString().slice(0, 10); }

function ProjectSelect({ projects, name = "project_public_id" }: { projects: Project[]; name?: string }) {
  return <select name={name} required defaultValue=""><option value="" disabled>Select project</option>{projects.map((item) => <option key={item.public_id} value={item.public_id}>{item.code} · {item.name}</option>)}</select>;
}
function PersonSelect({ people, name, required = false }: { people: Person[]; name: string; required?: boolean }) {
  return <select name={name} required={required} defaultValue=""><option value="">{required ? "Select person" : "Unassigned"}</option>{people.map((item) => <option key={item.public_id} value={item.public_id}>{item.employee_number} · {item.display_name}</option>)}</select>;
}
function WorkSelect({ items, name = "work_item_public_id", required = false }: { items: WorkItem[]; name?: string; required?: boolean }) {
  return <select name={name} required={required} defaultValue=""><option value="">{required ? "Select work item" : "No work item"}</option>{items.map((item) => <option key={item.public_id} value={item.public_id}>{item.project_code} · {item.code} · {item.title}</option>)}</select>;
}

export function ProjectWorkClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("portfolio");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setOverview(await api<Overview>("overview")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Project and work management could not be loaded."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void load();
    });
    return () => controller.abort();
  }, [load]);

  const filteredWork = useMemo(() => {
    if (!overview) return [];
    const q = query.trim().toLowerCase();
    if (!q) return overview.work_items;
    return overview.work_items.filter((item) => [item.code, item.title, item.project_code, item.primary_assignee_name ?? "", item.status_code].join(" ").toLowerCase().includes(q));
  }, [overview, query]);

  async function execute(action: () => Promise<void>, success: string) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); setNotice(success); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Operation failed."); }
    finally { setBusy(false); }
  }

  function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => {
      await api("projects", { method: "POST", body: JSON.stringify({
        code: value(form, "code"), name: value(form, "name"), description: value(form, "description"),
        project_type_code: value(form, "project_type_code"), priority_code: value(form, "priority_code"),
        manager_public_id: nullable(form, "manager_public_id"), location_public_id: nullable(form, "location_public_id"),
        start_date: value(form, "start_date"), target_end_date: value(form, "target_end_date"),
        currency: value(form, "currency"), budget: nullable(form, "budget"),
      }) }); element.reset();
    }, "Project created.");
  }
  function submitSite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("sites", { method: "POST", body: JSON.stringify({
      project_public_id: value(form, "project_public_id"), code: value(form, "code"), name: value(form, "name"),
      location_public_id: nullable(form, "location_public_id"), start_date: nullable(form, "start_date"), target_end_date: nullable(form, "target_end_date"), address: {},
    }) }); element.reset(); }, "Project site created.");
  }
  function submitWBS(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("wbs", { method: "POST", body: JSON.stringify({ project_public_id: value(form, "project_public_id"), code: value(form, "code"), name: value(form, "name"), parent_public_id: nullable(form, "parent_public_id"), sequence: Number(value(form, "sequence")) }) }); element.reset(); }, "WBS node created.");
  }
  function submitPackage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("work-packages", { method: "POST", body: JSON.stringify({ project_public_id: value(form, "project_public_id"), wbs_node_public_id: value(form, "wbs_node_public_id"), code: value(form, "code"), name: value(form, "name"), owner_public_id: nullable(form, "owner_public_id"), planned_start: value(form, "planned_start"), planned_end: value(form, "planned_end"), progress_weight: value(form, "progress_weight"), description: value(form, "description") }) }); element.reset(); }, "Work package created.");
  }
  function submitMilestone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("milestones", { method: "POST", body: JSON.stringify({ project_public_id: value(form, "project_public_id"), code: value(form, "code"), name: value(form, "name"), target_date: value(form, "target_date"), owner_public_id: nullable(form, "owner_public_id") }) }); element.reset(); }, "Milestone created.");
  }
  function submitWork(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("work-items", { method: "POST", body: JSON.stringify({
      project_public_id: value(form, "project_public_id"), site_public_id: nullable(form, "site_public_id"), work_package_public_id: nullable(form, "work_package_public_id"),
      code: value(form, "code"), title: value(form, "title"), description: value(form, "description"), work_type_code: value(form, "work_type_code"), priority_code: value(form, "priority_code"),
      planned_start: nullable(form, "planned_start"), due_date: nullable(form, "due_date"), estimated_hours: nullable(form, "estimated_hours"),
      primary_assignee_public_id: nullable(form, "primary_assignee_public_id"), reviewer_public_id: nullable(form, "reviewer_public_id"),
    }) }); element.reset(); }, "Work item created and routed.");
  }
  function submitAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("assignments", { method: "POST", body: JSON.stringify({ work_item_public_id: value(form, "work_item_public_id"), employee_public_id: value(form, "employee_public_id"), assignment_role_code: value(form, "assignment_role_code"), allocation_percent: value(form, "allocation_percent"), effective_from: value(form, "effective_from"), effective_to: nullable(form, "effective_to"), make_primary: form.get("make_primary") === "on" }) }); element.reset(); }, "Employee assigned to work.");
  }
  function submitDependency(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("dependencies", { method: "POST", body: JSON.stringify({ predecessor_public_id: value(form, "predecessor_public_id"), successor_public_id: value(form, "successor_public_id"), dependency_type_code: value(form, "dependency_type_code"), lag_days: Number(value(form, "lag_days")) }) }); element.reset(); }, "Dependency created.");
  }
  function submitChecklist(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("checklists", { method: "POST", body: JSON.stringify({ work_item_public_id: value(form, "work_item_public_id"), sequence: Number(value(form, "sequence")), title: value(form, "title"), is_required: form.get("is_required") === "on" }) }); element.reset(); }, "Checklist control added.");
  }
  function submitProgress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("progress", { method: "POST", body: JSON.stringify({ project_public_id: value(form, "project_public_id"), site_public_id: nullable(form, "site_public_id"), work_item_public_id: nullable(form, "work_item_public_id"), recorded_by_public_id: nullable(form, "recorded_by_public_id"), progress_date: value(form, "progress_date"), quantity_completed: value(form, "quantity_completed"), unit_code: value(form, "unit_code"), progress_percent: nullable(form, "progress_percent"), hours_worked: value(form, "hours_worked"), note: value(form, "note"), blockers: value(form, "blockers") }) }); element.reset(); }, "Daily progress recorded.");
  }
  function submitTimesheet(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("timesheets", { method: "POST", body: JSON.stringify({ employee_public_id: value(form, "employee_public_id"), project_public_id: value(form, "project_public_id"), work_item_public_id: nullable(form, "work_item_public_id"), work_date: value(form, "work_date"), hours: value(form, "hours"), description: value(form, "description"), submit_now: form.get("submit_now") === "on" }) }); element.reset(); }, "Timesheet saved.");
  }
  function submitApproval(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    void execute(async () => { await api("approvals", { method: "POST", body: JSON.stringify({ work_item_public_id: value(form, "work_item_public_id"), reviewer_public_id: value(form, "reviewer_public_id"), approval_type_code: value(form, "approval_type_code"), request_note: value(form, "request_note") }) }); element.reset(); }, "Approval requested.");
  }

  function transitionWork(item: WorkItem, status: string) { void execute(async () => { await api(`work-items/${item.public_id}/transition`, { method: "POST", body: JSON.stringify({ status_code: status, expected_version: item.version }) }); }, `${item.code} moved to ${status}.`); }
  function transitionProjectStatus(item: Project, status: string) { void execute(async () => { await api(`projects/${item.public_id}/transition`, { method: "POST", body: JSON.stringify({ status_code: status, expected_version: item.version }) }); }, `${item.code} moved to ${status}.`); }
  function toggleChecklist(item: Checklist) { void execute(async () => { await api(`checklists/${item.public_id}/complete`, { method: "POST", body: JSON.stringify({ is_completed: !item.is_completed, expected_version: item.version }) }); }, "Checklist updated."); }
  function reviewApproval(item: Approval, decision: "APPROVED" | "REJECTED") { void execute(async () => { await api(`approvals/${item.public_id}/review`, { method: "POST", body: JSON.stringify({ decision_code: decision, decision_note: decision === "APPROVED" ? "Approved in Build360." : "Returned for correction.", expected_version: item.version }) }); }, `Approval ${decision.toLowerCase()}.`); }
  function submitExistingTimesheet(item: Timesheet) { void execute(async () => { await api(`timesheets/${item.public_id}/submit`, { method: "POST", body: JSON.stringify({ expected_version: item.version }) }); }, "Timesheet submitted."); }
  function reviewTimesheet(item: Timesheet, decision: "APPROVED" | "REJECTED") { void execute(async () => { await api(`timesheets/${item.public_id}/review`, { method: "POST", body: JSON.stringify({ decision_code: decision, review_note: decision === "APPROVED" ? "Approved." : "Please correct and resubmit.", expected_version: item.version }) }); }, `Timesheet ${decision.toLowerCase()}.`); }

  if (loading && !overview) return <main className={styles.page}><div className={styles.loading}>Loading project and work control room…</div></main>;
  if (!overview) return <main className={styles.page}><section className={styles.panel}><p className={styles.kicker}>Project control unavailable</p><h1>Project & work management could not be opened.</h1><p>{error || "Verify Phase 30 migrations, backend restart and work.view permission."}</p><button type="button" className={styles.primary} onClick={() => void load()}>Retry workspace</button></section></main>;

  const tabs: Array<{ id: Tab; label: string }> = [
    { id: "portfolio", label: "Project portfolio" }, { id: "planning", label: "WBS & planning" },
    { id: "work", label: "Work board" }, { id: "progress", label: "Progress & time" }, { id: "approvals", label: "Approvals" },
  ];
  const boardGroups = ["BACKLOG", "READY", "ASSIGNED", "IN_PROGRESS", "BLOCKED", "REVIEW", "APPROVED", "DONE"];

  return <main className={styles.page}>
    <section className={styles.hero}><div><p className={styles.kicker}>MPSqre Build360 · Phase 30</p><h1>Project & work management</h1><p>Create projects, structure WBS, assign work, govern dependencies, capture site progress, approve completion and account for time across {overview.company.display_name}.</p></div><span className={styles.badge}>Phase 30 active</span></section>
    <section className={styles.metrics}>
      <article><span>Active projects</span><strong>{overview.summary.active_project_count}</strong></article>
      <article><span>Open work</span><strong>{overview.summary.open_work_count}</strong></article>
      <article><span>Overdue work</span><strong>{overview.summary.overdue_work_count}</strong></article>
      <article><span>Blocked work</span><strong>{overview.summary.blocked_work_count}</strong></article>
      <article><span>Pending approvals</span><strong>{overview.summary.pending_approval_count}</strong></article>
      <article><span>Approved hours</span><strong>{overview.summary.approved_hours_this_week}</strong></article>
    </section>
    <nav className={styles.tabs} aria-label="Project and work sections">{tabs.map((item) => <button key={item.id} type="button" className={tab === item.id ? styles.activeTab : ""} onClick={() => setTab(item.id)}>{item.label}</button>)}</nav>
    {error ? <p className={styles.error}>{error}</p> : null}{notice ? <p className={styles.notice}>{notice}</p> : null}

    {tab === "portfolio" ? <div className={styles.twoColumn}>
      <section className={styles.panel}><h2>Create project</h2><p>Establish a governed delivery container before planning or assigning work.</p><form className={styles.formGrid} onSubmit={submitProject}>
        <label>Project code<input name="code" required /></label><label>Project name<input name="name" required /></label>
        <label>Type<input name="project_type_code" defaultValue="CONSTRUCTION" required /></label><label>Priority<select name="priority_code" defaultValue="NORMAL"><option>NORMAL</option><option>HIGH</option><option>CRITICAL</option></select></label>
        <label>Manager<PersonSelect people={overview.people} name="manager_public_id" /></label><label>Location<select name="location_public_id" defaultValue=""><option value="">No location</option>{overview.locations.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></label>
        <label>Start date<input type="date" name="start_date" defaultValue={today()} required /></label><label>Target end<input type="date" name="target_end_date" defaultValue={plusDays(180)} required /></label>
        <label>Currency<input name="currency" defaultValue={overview.company.currency} maxLength={3} required /></label><label>Budget<input name="budget" type="number" min="0" step="0.01" /></label>
        <label className={styles.full}>Description<textarea name="description" /></label><div className={`${styles.actions} ${styles.full}`}><button disabled={busy} className={styles.primary}>Create project</button></div>
      </form><hr /><h3>Create project site</h3><form className={styles.formGrid} onSubmit={submitSite}><label className={styles.full}>Project<ProjectSelect projects={overview.projects} /></label><label>Site code<input name="code" required /></label><label>Site name<input name="name" required /></label><label>Location<select name="location_public_id" defaultValue=""><option value="">No location</option>{overview.locations.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></label><label>Start<input type="date" name="start_date" /></label><label>Target end<input type="date" name="target_end_date" /></label><div className={styles.actions}><button disabled={busy} className={styles.secondary}>Create site</button></div></form></section>
      <section className={styles.panel}><div className={styles.panelHeader}><div><h2>Project portfolio</h2><p>Current lifecycle position, owner and delivery window.</p></div></div><div className={styles.tableWrap}><table><thead><tr><th>Project</th><th>Owner</th><th>Window</th><th>Status</th><th>Controls</th></tr></thead><tbody>{overview.projects.map((item) => <tr key={item.public_id}><td><strong>{item.code} · {item.name}</strong><small>{item.project_type_code} · {item.location_name || "No location"}</small></td><td>{item.manager_name || "Unassigned"}<small>{item.currency} {item.budget || "No budget"}</small></td><td>{item.start_date}<small>to {item.target_end_date}</small></td><td><span className={item.status_code === "ACTIVE" ? styles.goodPill : styles.pill}>{item.status_code}</span></td><td><div className={styles.actions}>{item.status_code === "DRAFT" ? <button type="button" className={styles.tiny} disabled={busy} onClick={() => transitionProjectStatus(item, "ACTIVE")}>Activate</button> : null}{item.status_code === "ACTIVE" ? <button type="button" className={styles.tiny} disabled={busy} onClick={() => transitionProjectStatus(item, "ON_HOLD")}>Hold</button> : null}</div></td></tr>)}</tbody></table></div><h3>Sites</h3><div className={styles.list}>{overview.sites.map((item) => <article key={item.public_id}><strong>{item.project_code} · {item.code} · {item.name}</strong><small>{item.location_name || "No linked location"} · {item.status_code}</small></article>)}</div></section>
    </div> : null}

    {tab === "planning" ? <div className={styles.threeColumn}>
      <section className={styles.panel}><h2>WBS node</h2><form className={styles.formStack} onSubmit={submitWBS}><label>Project<ProjectSelect projects={overview.projects} /></label><label>Code<input name="code" required /></label><label>Name<input name="name" required /></label><label>Parent<select name="parent_public_id" defaultValue=""><option value="">Top level</option>{overview.wbs_nodes.map((item) => <option key={item.public_id} value={item.public_id}>{item.project_code} · {item.code} · {item.name}</option>)}</select></label><label>Sequence<input name="sequence" type="number" min="1" defaultValue="1" required /></label><button disabled={busy} className={styles.primary}>Create WBS node</button></form><div className={styles.list}>{overview.wbs_nodes.map((item) => <article key={item.public_id}><strong>{item.project_code} · {item.code} · {item.name}</strong><small>Level {item.level}{item.parent_name ? ` · ${item.parent_name}` : ""}</small></article>)}</div></section>
      <section className={styles.panel}><h2>Work package</h2><form className={styles.formStack} onSubmit={submitPackage}><label>Project<ProjectSelect projects={overview.projects} /></label><label>WBS node<select name="wbs_node_public_id" required defaultValue=""><option value="" disabled>Select WBS node</option>{overview.wbs_nodes.map((item) => <option key={item.public_id} value={item.public_id}>{item.project_code} · {item.code} · {item.name}</option>)}</select></label><label>Code<input name="code" required /></label><label>Name<input name="name" required /></label><label>Owner<PersonSelect people={overview.people} name="owner_public_id" /></label><label>Planned start<input type="date" name="planned_start" defaultValue={today()} required /></label><label>Planned end<input type="date" name="planned_end" defaultValue={plusDays(30)} required /></label><label>Progress weight<input type="number" name="progress_weight" min="0.01" max="100" step="0.01" defaultValue="1.00" required /></label><label>Description<textarea name="description" /></label><button disabled={busy} className={styles.primary}>Create package</button></form><div className={styles.list}>{overview.work_packages.map((item) => <article key={item.public_id}><strong>{item.project_code} · {item.code} · {item.name}</strong><small>{item.wbs_name} · {item.owner_name || "No owner"} · {item.status_code}</small></article>)}</div></section>
      <section className={styles.panel}><h2>Milestone</h2><form className={styles.formStack} onSubmit={submitMilestone}><label>Project<ProjectSelect projects={overview.projects} /></label><label>Code<input name="code" required /></label><label>Name<input name="name" required /></label><label>Target date<input type="date" name="target_date" defaultValue={plusDays(30)} required /></label><label>Owner<PersonSelect people={overview.people} name="owner_public_id" /></label><button disabled={busy} className={styles.primary}>Create milestone</button></form><div className={styles.list}>{overview.milestones.map((item) => <article key={item.public_id}><strong>{item.project_code} · {item.code} · {item.name}</strong><small>{item.target_date} · {item.owner_name || "No owner"} · {item.status_code}</small></article>)}</div></section>
    </div> : null}

    {tab === "work" ? <><div className={styles.twoColumn}><section className={styles.panel}><h2>Create and route work</h2><form className={styles.formGrid} onSubmit={submitWork}><label>Project<ProjectSelect projects={overview.projects} /></label><label>Site<select name="site_public_id" defaultValue=""><option value="">No site</option>{overview.sites.map((item) => <option key={item.public_id} value={item.public_id}>{item.project_code} · {item.code} · {item.name}</option>)}</select></label><label>Work package<select name="work_package_public_id" defaultValue=""><option value="">No package</option>{overview.work_packages.map((item) => <option key={item.public_id} value={item.public_id}>{item.project_code} · {item.code} · {item.name}</option>)}</select></label><label>Code<input name="code" required /></label><label className={styles.full}>Title<input name="title" required /></label><label>Type<input name="work_type_code" defaultValue="TASK" required /></label><label>Priority<select name="priority_code" defaultValue="NORMAL"><option>NORMAL</option><option>HIGH</option><option>CRITICAL</option></select></label><label>Planned start<input type="date" name="planned_start" /></label><label>Due date<input type="date" name="due_date" /></label><label>Estimated hours<input type="number" step="0.25" min="0" name="estimated_hours" /></label><label>Primary assignee<PersonSelect people={overview.people} name="primary_assignee_public_id" /></label><label>Reviewer<PersonSelect people={overview.people} name="reviewer_public_id" /></label><label className={styles.full}>Description<textarea name="description" /></label><div className={`${styles.actions} ${styles.full}`}><button disabled={busy} className={styles.primary}>Create work item</button></div></form></section>
      <section className={styles.panel}><h2>Assignment, dependency & checklist</h2><div className={styles.split}><form className={styles.formStack} onSubmit={submitAssignment}><h3>Assign person</h3><label>Work item<WorkSelect items={overview.work_items} required /></label><label>Person<PersonSelect people={overview.people} name="employee_public_id" required /></label><label>Role<input name="assignment_role_code" defaultValue="ASSIGNEE" required /></label><label>Allocation %<input type="number" name="allocation_percent" min="0.01" max="100" step="0.01" defaultValue="100.00" required /></label><label>Effective from<input type="date" name="effective_from" defaultValue={today()} required /></label><label>Effective to<input type="date" name="effective_to" /></label><label className={styles.checkbox}><input type="checkbox" name="make_primary" /> Make primary assignee</label><button disabled={busy} className={styles.secondary}>Assign person</button></form>
      <form className={styles.formStack} onSubmit={submitDependency}><h3>Add dependency</h3><label>Predecessor<WorkSelect items={overview.work_items} name="predecessor_public_id" required /></label><label>Successor<WorkSelect items={overview.work_items} name="successor_public_id" required /></label><label>Type<input name="dependency_type_code" defaultValue="FINISH_TO_START" required /></label><label>Lag days<input type="number" name="lag_days" defaultValue="0" required /></label><button disabled={busy} className={styles.secondary}>Add dependency</button></form></div><hr /><form className={styles.formGrid} onSubmit={submitChecklist}><label>Work item<WorkSelect items={overview.work_items} required /></label><label>Sequence<input type="number" name="sequence" min="1" defaultValue="1" required /></label><label className={styles.full}>Checklist control<input name="title" required /></label><label className={styles.checkbox}><input type="checkbox" name="is_required" defaultChecked /> Required for completion</label><div className={styles.actions}><button disabled={busy} className={styles.secondary}>Add checklist</button></div></form></section></div>
      <section className={styles.panel}><div className={styles.panelHeader}><div><h2>Unified work board</h2><p>Move work through one governed status model.</p></div><input className={styles.search} value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Search work, project or person" /></div><div className={styles.board}>{boardGroups.map((status) => { const items = filteredWork.filter((item) => item.status_code === status); return <section className={styles.column} key={status}><h3>{status.replaceAll("_", " ")}<span>{items.length}</span></h3>{items.map((item) => <article className={styles.card} key={item.public_id}><strong>{item.code} · {item.title}</strong><small>{item.project_code} · {item.primary_assignee_name || "Unassigned"}</small><p>{item.due_date ? `Due ${item.due_date}` : "No due date"} {item.is_overdue ? <span className={styles.dangerPill}>OVERDUE</span> : null}</p><div className={styles.progress}><span style={{ width: `${Math.min(100, Number(item.progress_percent))}%` }} /></div><small>{item.progress_percent}% complete</small>{item.checklist.length ? <div className={styles.checklist}>{item.checklist.map((check) => <button type="button" data-complete={check.is_completed} key={check.public_id} disabled={busy} onClick={() => toggleChecklist(check)}><span>{check.is_completed ? "✓" : "○"}</span><span>{check.title}{check.is_required ? " *" : ""}</span></button>)}</div> : null}<div className={styles.actions}>{item.status_code === "BACKLOG" ? <button type="button" className={styles.tiny} onClick={() => transitionWork(item, "READY")}>Ready</button> : null}{["READY", "ASSIGNED", "BLOCKED"].includes(item.status_code) ? <button type="button" className={styles.tiny} onClick={() => transitionWork(item, "IN_PROGRESS")}>Start</button> : null}{item.status_code === "IN_PROGRESS" ? <><button type="button" className={styles.tiny} onClick={() => transitionWork(item, "BLOCKED")}>Block</button><button type="button" className={styles.tiny} onClick={() => transitionWork(item, "REVIEW")}>Review</button></> : null}{item.status_code === "APPROVED" ? <button type="button" className={styles.tiny} onClick={() => transitionWork(item, "DONE")}>Complete</button> : null}</div></article>)}</section>; })}</div></section>
    </> : null}

    {tab === "progress" ? <div className={styles.twoColumn}><section className={styles.panel}><h2>Daily progress</h2><form className={styles.formGrid} onSubmit={submitProgress}><label>Project<ProjectSelect projects={overview.projects} /></label><label>Site<select name="site_public_id" defaultValue=""><option value="">No site</option>{overview.sites.map((item) => <option key={item.public_id} value={item.public_id}>{item.project_code} · {item.name}</option>)}</select></label><label>Work item<WorkSelect items={overview.work_items} /></label><label>Recorded by<PersonSelect people={overview.people} name="recorded_by_public_id" /></label><label>Date<input type="date" name="progress_date" defaultValue={today()} required /></label><label>Progress %<input type="number" name="progress_percent" min="0" max="100" step="0.01" /></label><label>Quantity<input type="number" name="quantity_completed" min="0" step="0.001" defaultValue="0" required /></label><label>Unit<input name="unit_code" /></label><label>Hours<input type="number" name="hours_worked" min="0" step="0.25" defaultValue="0" required /></label><label className={styles.full}>Progress note<textarea name="note" /></label><label className={styles.full}>Blockers<textarea name="blockers" /></label><div className={`${styles.actions} ${styles.full}`}><button disabled={busy} className={styles.primary}>Record progress</button></div></form><hr /><h2>Timesheet</h2><form className={styles.formGrid} onSubmit={submitTimesheet}><label>Person<PersonSelect people={overview.people} name="employee_public_id" required /></label><label>Project<ProjectSelect projects={overview.projects} /></label><label>Work item<WorkSelect items={overview.work_items} /></label><label>Date<input type="date" name="work_date" defaultValue={today()} required /></label><label>Hours<input type="number" name="hours" min="0.01" max="24" step="0.25" defaultValue="8" required /></label><label className={styles.full}>Description<textarea name="description" /></label><label className={styles.checkbox}><input type="checkbox" name="submit_now" /> Submit immediately</label><div className={styles.actions}><button disabled={busy} className={styles.secondary}>Save timesheet</button></div></form></section>
      <section className={styles.panel}><h2>Latest site progress</h2><div className={styles.tableWrap}><table><thead><tr><th>Date</th><th>Scope</th><th>Progress</th><th>Hours</th><th>Signals</th></tr></thead><tbody>{overview.progress_entries.map((item) => <tr key={item.public_id}><td>{item.progress_date}</td><td><strong>{item.project_code}</strong><small>{item.work_item_code || "Project-level update"}</small></td><td>{item.progress_percent ? `${item.progress_percent}%` : "—"}<small>{item.quantity_completed} {item.unit_code}</small></td><td>{item.hours_worked}</td><td>{item.note || "No note"}<small>{item.blockers ? `Blocker: ${item.blockers}` : "No blocker"}</small></td></tr>)}</tbody></table></div><h2>Timesheets</h2><div className={styles.tableWrap}><table><thead><tr><th>Person</th><th>Scope</th><th>Date</th><th>Hours</th><th>Status</th><th>Control</th></tr></thead><tbody>{overview.timesheets.map((item) => <tr key={item.public_id}><td>{item.employee_name}<small>{item.employee_number}</small></td><td>{item.project_code}<small>{item.work_item_code || "Project"}</small></td><td>{item.work_date}</td><td>{item.hours}</td><td><span className={item.status_code === "APPROVED" ? styles.goodPill : styles.pill}>{item.status_code}</span></td><td>{["DRAFT", "REJECTED"].includes(item.status_code) ? <button type="button" className={styles.tiny} disabled={busy} onClick={() => submitExistingTimesheet(item)}>Submit</button> : null}</td></tr>)}</tbody></table></div></section></div> : null}

    {tab === "approvals" ? <div className={styles.twoColumn}><section className={styles.panel}><h2>Request work approval</h2><p>Route completion, inspection or handover evidence to a named reviewer.</p><form className={styles.formStack} onSubmit={submitApproval}><label>Work item<WorkSelect items={overview.work_items} required /></label><label>Reviewer<PersonSelect people={overview.people} name="reviewer_public_id" required /></label><label>Approval type<input name="approval_type_code" defaultValue="WORK_COMPLETION" required /></label><label>Request note<textarea name="request_note" /></label><button disabled={busy} className={styles.primary}>Request approval</button></form></section><section className={styles.panel}><h2>Approval inbox</h2><div className={styles.tableWrap}><table><thead><tr><th>Work</th><th>Reviewer</th><th>Type</th><th>Status</th><th>Decision</th></tr></thead><tbody>{overview.approvals.map((item) => <tr key={item.public_id}><td><strong>{item.project_code} · {item.work_item_code}</strong><small>{item.work_item_title}</small></td><td>{item.reviewer_name}</td><td>{item.approval_type_code}</td><td><span className={item.status_code === "APPROVED" ? styles.goodPill : item.status_code === "REJECTED" ? styles.dangerPill : styles.pill}>{item.status_code}</span><small>{item.decision_note || item.request_note}</small></td><td>{item.status_code === "PENDING" ? <div className={styles.actions}><button type="button" className={styles.approve} disabled={busy} onClick={() => reviewApproval(item, "APPROVED")}>Approve</button><button type="button" className={styles.reject} disabled={busy} onClick={() => reviewApproval(item, "REJECTED")}>Reject</button></div> : null}</td></tr>)}</tbody></table></div><h2>Timesheet review</h2><div className={styles.tableWrap}><table><thead><tr><th>Person</th><th>Scope</th><th>Hours</th><th>Status</th><th>Decision</th></tr></thead><tbody>{overview.timesheets.filter((item) => item.status_code === "SUBMITTED").map((item) => <tr key={item.public_id}><td>{item.employee_name}<small>{item.work_date}</small></td><td>{item.project_code}<small>{item.work_item_code || "Project"}</small></td><td>{item.hours}</td><td>{item.status_code}</td><td><div className={styles.actions}><button type="button" className={styles.approve} disabled={busy} onClick={() => reviewTimesheet(item, "APPROVED")}>Approve</button><button type="button" className={styles.reject} disabled={busy} onClick={() => reviewTimesheet(item, "REJECTED")}>Reject</button></div></td></tr>)}</tbody></table></div></section></div> : null}
  </main>;
}
