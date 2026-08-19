"use client";

import type { Route } from "next";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./my-work.module.css";

type Checklist = {
  public_id: string;
  sequence: number;
  title: string;
  is_required: boolean;
  is_completed: boolean;
  version: number;
};
type WorkItem = {
  public_id: string;
  project_public_id: string;
  project_code: string;
  project_name: string;
  site_name: string | null;
  work_package_name: string | null;
  code: string;
  title: string;
  description: string;
  work_type_code: string;
  status_code: string;
  priority_code: string;
  planned_start: string | null;
  due_date: string | null;
  progress_percent: string;
  estimated_hours: string | null;
  reviewer_name: string | null;
  reviewer_public_id: string | null;
  bucket: "TODAY" | "UPCOMING" | "OVERDUE" | "BLOCKED" | "COMPLETED" | "QUEUE";
  is_overdue: boolean;
  allowed_transitions: string[];
  blocked_by: { public_id: string; code: string; title: string; status_code: string }[];
  checklist: Checklist[];
  version: number;
};
type Timesheet = {
  public_id: string;
  project_public_id: string;
  project_code: string;
  project_name: string;
  work_item_public_id: string | null;
  work_item_code: string | null;
  work_date: string;
  hours: string;
  description: string;
  status_code: string;
  review_note: string;
  version: number;
};
type Approval = {
  public_id: string;
  work_item_public_id: string;
  work_item_code: string;
  work_item_title: string;
  project_code: string;
  approval_type_code: string;
  status_code: string;
  request_note: string;
  decision_note: string;
  requested_at: string;
  version: number;
};
type TeamTimesheet = {
  public_id: string;
  employee_name: string;
  employee_number: string;
  project_code: string;
  work_item_code: string | null;
  work_date: string;
  hours: string;
  description: string;
  status_code: string;
  version: number;
};
type Notification = {
  public_id: string;
  notification_type_code: string;
  severity_code: string;
  title: string;
  message: string;
  action_url: string;
  work_item_public_id: string | null;
  read_at: string | null;
  created_at: string;
  version: number;
};
type OfflineDraft = {
  public_id: string;
  client_draft_id: string;
  device_id: string;
  draft_type_code: string;
  work_item_public_id: string | null;
  work_item_code: string | null;
  payload: Record<string, unknown>;
  status_code: string;
  client_updated_at: string;
  synced_at: string | null;
  conflict_reason: string;
  version: number;
};
type Activity = {
  public_id: string;
  activity_type_code: string;
  summary: string;
  work_item_public_id: string | null;
  work_item_code: string | null;
  project_code: string | null;
  occurred_at: string;
  metadata: Record<string, unknown>;
};
type Overview = {
  generated_at: string;
  company: { display_name: string; timezone: string; currency: string };
  profile_state: "ACTIVE" | "EMPLOYEE_PROFILE_REQUIRED";
  employee: null | {
    public_id: string;
    employee_number: string;
    display_name: string;
    email: string;
    job_title: string;
    department_name: string | null;
    designation_name: string | null;
    work_calendar_name: string | null;
  };
  summary: {
    due_today_count: number;
    overdue_count: number;
    blocked_count: number;
    open_count: number;
    pending_approval_count: number;
    submitted_team_timesheet_count: number;
    hours_this_week: string;
    unread_notification_count: number;
    offline_draft_count: number;
  };
  capabilities: {
    can_execute: boolean;
    can_log_time: boolean;
    can_approve: boolean;
    can_use_offline: boolean;
    can_export: boolean;
  };
  work_items: WorkItem[];
  timesheets: Timesheet[];
  approval_inbox: Approval[];
  team_timesheets: TeamTimesheet[];
  notifications: Notification[];
  offline_drafts: OfflineDraft[];
  activity: Activity[];
};
type Tab = "today" | "queue" | "time" | "approvals" | "offline" | "activity";
type DraftRequest = {
  client_draft_id: string;
  device_id: string;
  draft_type_code: "PROGRESS" | "TIMESHEET" | "NOTE";
  work_item_public_id: string | null;
  payload: Record<string, unknown>;
  client_updated_at: string;
};

const LOCAL_DRAFT_KEY = "build360_phase31_local_drafts";
const DEVICE_KEY = "build360_phase31_device";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/platform/my-work/${path}`, {
    cache: "no-store",
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok) {
    const detail = typeof payload.detail === "string"
      ? payload.detail
      : typeof payload.message === "string"
        ? payload.message
        : Object.values(payload).flat().join(" ");
    if (response.status === 403) throw new Error("My Work access is not assigned to this role. Reconcile Phase 31 permissions and sign in again.");
    throw new Error(detail || "The request could not be completed.");
  }
  return payload as T;
}

function formValue(form: FormData, name: string): string {
  return String(form.get(name) ?? "").trim();
}
function today(): string {
  return new Date().toISOString().slice(0, 10);
}
function internalRoute(value: string): Route | null {
  return value.startsWith("/") && !value.startsWith("//") ? (value as Route) : null;
}

function readable(value: string): string {
  return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (character) => character.toUpperCase());
}
function relativeDate(value: string | null): string {
  if (!value) return "No due date";
  const due = new Date(`${value}T00:00:00`);
  const current = new Date(`${today()}T00:00:00`);
  const days = Math.round((due.getTime() - current.getTime()) / 86_400_000);
  if (days === 0) return "Due today";
  if (days === 1) return "Due tomorrow";
  if (days === -1) return "1 day overdue";
  if (days < 0) return `${Math.abs(days)} days overdue`;
  return `Due in ${days} days`;
}
function getDeviceId(): string {
  const existing = window.localStorage.getItem(DEVICE_KEY);
  if (existing) return existing;
  const created = crypto.randomUUID();
  window.localStorage.setItem(DEVICE_KEY, created);
  return created;
}
function loadLocalDrafts(): DraftRequest[] {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(LOCAL_DRAFT_KEY) ?? "[]") as unknown;
    return Array.isArray(parsed) ? parsed as DraftRequest[] : [];
  } catch {
    return [];
  }
}
function saveLocalDrafts(items: DraftRequest[]): void {
  window.localStorage.setItem(LOCAL_DRAFT_KEY, JSON.stringify(items));
}

function WorkCard({ item, busy, canExecute, onTransition, onChecklist }: {
  item: WorkItem;
  busy: boolean;
  canExecute: boolean;
  onTransition: (item: WorkItem, status: string) => void;
  onChecklist: (item: WorkItem, checklist: Checklist) => void;
}) {
  return (
    <article className={styles.workCard} data-overdue={item.is_overdue} data-blocked={item.status_code === "BLOCKED"}>
      <div className={styles.workTop}>
        <div>
          <span className={styles.eyebrow}>{item.project_code} · {item.code}</span>
          <h3>{item.title}</h3>
        </div>
        <span className={styles.status}>{readable(item.status_code)}</span>
      </div>
      <p className={styles.scope}>{item.site_name || item.project_name}{item.work_package_name ? ` · ${item.work_package_name}` : ""}</p>
      <div className={styles.metaRow}>
        <span className={item.is_overdue ? styles.dangerText : ""}>{relativeDate(item.due_date)}</span>
        <span>{item.priority_code}</span>
        <span>{item.progress_percent}% complete</span>
      </div>
      <div className={styles.progress}><span style={{ width: `${Math.min(100, Number(item.progress_percent))}%` }} /></div>
      {item.blocked_by.length ? <p className={styles.warning}>Waiting for {item.blocked_by.map((value) => value.code).join(", ")}</p> : null}
      {item.checklist.length ? (
        <div className={styles.checklist}>
          {item.checklist.map((check) => (
            <button
              type="button"
              key={check.public_id}
              disabled={busy || !canExecute}
              data-complete={check.is_completed}
              onClick={() => onChecklist(item, check)}
            >
              <span>{check.is_completed ? "✓" : "○"}</span>
              <span>{check.title}{check.is_required ? " *" : ""}</span>
            </button>
          ))}
        </div>
      ) : null}
      {item.allowed_transitions.length ? (
        <div className={styles.actions}>
          {item.allowed_transitions.map((status) => (
            <button type="button" key={status} disabled={busy || !canExecute} onClick={() => onTransition(item, status)}>
              {status === "IN_PROGRESS" ? "Start / resume" : status === "REVIEW" ? "Send for review" : readable(status)}
            </button>
          ))}
        </div>
      ) : null}
    </article>
  );
}

export function MyWorkClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("today");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [isOnline, setIsOnline] = useState(true);
  const [localDrafts, setLocalDrafts] = useState<DraftRequest[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setOverview(await api<Overview>("overview"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "My Work could not be loaded.");
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
  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      setIsOnline(navigator.onLine);
      setLocalDrafts(loadLocalDrafts());
    });
    const online = () => setIsOnline(true);
    const offline = () => setIsOnline(false);
    window.addEventListener("online", online);
    window.addEventListener("offline", offline);
    return () => {
      controller.abort();
      window.removeEventListener("online", online);
      window.removeEventListener("offline", offline);
    };
  }, []);

  const visibleWork = useMemo(() => {
    const items = overview?.work_items ?? [];
    const normalized = query.trim().toLowerCase();
    if (!normalized) return items;
    return items.filter((item) => [item.code, item.title, item.project_code, item.project_name, item.status_code].join(" ").toLowerCase().includes(normalized));
  }, [overview, query]);
  const todayWork = visibleWork.filter((item) => item.bucket === "TODAY" || item.bucket === "OVERDUE" || item.bucket === "BLOCKED");
  const queueWork = visibleWork.filter((item) => !["DONE", "CANCELLED"].includes(item.status_code));
  const projects = useMemo(() => {
    const map = new Map<string, { public_id: string; code: string; name: string }>();
    for (const item of overview?.work_items ?? []) {
      map.set(item.project_public_id, { public_id: item.project_public_id, code: item.project_code, name: item.project_name });
    }
    return [...map.values()].sort((left, right) => left.code.localeCompare(right.code));
  }, [overview]);

  async function execute(action: () => Promise<void>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(success);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Operation failed.");
    } finally {
      setBusy(false);
    }
  }

  function transition(item: WorkItem, status: string) {
    void execute(async () => {
      await api(`work-items/${item.public_id}/transition`, {
        method: "POST",
        body: JSON.stringify({ status_code: status, expected_version: item.version }),
      });
    }, `${item.code} moved to ${readable(status)}.`);
  }

  function toggleChecklist(_work: WorkItem, checklist: Checklist) {
    void execute(async () => {
      await api(`checklists/${checklist.public_id}/complete`, {
        method: "POST",
        body: JSON.stringify({ is_completed: !checklist.is_completed, expected_version: checklist.version }),
      });
    }, checklist.is_completed ? "Checklist item reopened." : "Checklist item completed.");
  }

  function queueLocal(draft: DraftRequest) {
    const next = [...localDrafts.filter((item) => item.client_draft_id !== draft.client_draft_id), draft];
    setLocalDrafts(next);
    saveLocalDrafts(next);
    setNotice("Saved securely on this device. It will remain in the offline queue until synchronized.");
    setTab("offline");
  }

  async function saveServerDraft(draft: DraftRequest): Promise<void> {
    await api("offline-drafts", { method: "POST", body: JSON.stringify(draft) });
  }

  async function saveDraftWithFallback(draft: DraftRequest): Promise<void> {
    if (!navigator.onLine) {
      queueLocal(draft);
      return;
    }
    try {
      await saveServerDraft(draft);
      setNotice("Offline-ready draft saved to the governed synchronization queue.");
      await load();
      setTab("offline");
    } catch (cause) {
      if (cause instanceof TypeError) {
        queueLocal(draft);
        return;
      }
      throw cause;
    }
  }

  function submitProgress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!overview) return;
    const element = event.currentTarget;
    const form = new FormData(element);
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const mode = submitter?.value ?? "record";
    const workId = formValue(form, "work_item_public_id");
    const work = overview.work_items.find((item) => item.public_id === workId);
    if (!work) return;
    const payload = {
      progress_date: formValue(form, "progress_date"),
      quantity_completed: formValue(form, "quantity_completed") || "0",
      unit_code: formValue(form, "unit_code"),
      progress_percent: formValue(form, "progress_percent") || null,
      hours_worked: formValue(form, "hours_worked") || "0",
      note: formValue(form, "note"),
      blockers: formValue(form, "blockers"),
      work_item_version: work.version,
    };
    if (mode === "draft") {
      setBusy(true);
      void saveDraftWithFallback({
        client_draft_id: crypto.randomUUID(),
        device_id: getDeviceId(),
        draft_type_code: "PROGRESS",
        work_item_public_id: work.public_id,
        payload,
        client_updated_at: new Date().toISOString(),
      }).catch((cause) => setError(cause instanceof Error ? cause.message : "Draft could not be saved.")).finally(() => setBusy(false));
      return;
    }
    void execute(async () => {
      await api("progress", {
        method: "POST",
        body: JSON.stringify({
          work_item_public_id: work.public_id,
          progress_date: payload.progress_date,
          quantity_completed: payload.quantity_completed,
          unit_code: payload.unit_code,
          progress_percent: payload.progress_percent,
          hours_worked: payload.hours_worked,
          note: payload.note,
          blockers: payload.blockers,
        }),
      });
      element.reset();
    }, "Progress update recorded.");
  }

  function submitTimesheet(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!overview) return;
    const element = event.currentTarget;
    const form = new FormData(element);
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const mode = submitter?.value ?? "record";
    const workId = formValue(form, "work_item_public_id");
    const work = overview.work_items.find((item) => item.public_id === workId);
    const projectId = formValue(form, "project_public_id") || work?.project_public_id || "";
    const payload = {
      project_public_id: projectId,
      work_date: formValue(form, "work_date"),
      hours: formValue(form, "hours"),
      description: formValue(form, "description"),
      submit_now: form.get("submit_now") === "on",
    };
    if (mode === "draft") {
      setBusy(true);
      void saveDraftWithFallback({
        client_draft_id: crypto.randomUUID(),
        device_id: getDeviceId(),
        draft_type_code: "TIMESHEET",
        work_item_public_id: work?.public_id ?? null,
        payload,
        client_updated_at: new Date().toISOString(),
      }).catch((cause) => setError(cause instanceof Error ? cause.message : "Draft could not be saved.")).finally(() => setBusy(false));
      return;
    }
    void execute(async () => {
      await api("timesheets", {
        method: "POST",
        body: JSON.stringify({ ...payload, work_item_public_id: work?.public_id ?? null }),
      });
      element.reset();
    }, "Timesheet saved.");
  }

  function submitExistingTimesheet(item: Timesheet) {
    void execute(async () => {
      await api(`timesheets/${item.public_id}/submit`, {
        method: "POST",
        body: JSON.stringify({ expected_version: item.version }),
      });
    }, "Timesheet submitted for review.");
  }

  function decideApproval(item: Approval, decision: "APPROVED" | "REJECTED") {
    const note = window.prompt(`${readable(decision)} note`, "") ?? "";
    void execute(async () => {
      await api(`approvals/${item.public_id}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision_code: decision, decision_note: note, expected_version: item.version }),
      });
    }, `Approval ${decision.toLowerCase()}.`);
  }

  function decideTeamTimesheet(item: TeamTimesheet, decision: "APPROVED" | "REJECTED") {
    const note = window.prompt(`${readable(decision)} note`, "") ?? "";
    void execute(async () => {
      await api(`team-timesheets/${item.public_id}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision_code: decision, review_note: note, expected_version: item.version }),
      });
    }, `Team timesheet ${decision.toLowerCase()}.`);
  }

  function syncServerDraft(item: OfflineDraft) {
    void execute(async () => {
      const result = await api<{ status_code: string; conflict_reason: string }>(`offline-drafts/${item.public_id}/sync`, {
        method: "POST",
        body: JSON.stringify({ expected_version: item.version }),
      });
      if (result.status_code === "CONFLICT") throw new Error(result.conflict_reason || "Draft synchronization conflict.");
    }, "Draft synchronized successfully.");
  }

  function discardServerDraft(item: OfflineDraft) {
    void execute(async () => {
      await api(`offline-drafts/${item.public_id}/discard`, {
        method: "POST",
        body: JSON.stringify({ expected_version: item.version }),
      });
    }, "Draft discarded.");
  }

  async function syncLocalQueue() {
    if (!navigator.onLine || localDrafts.length === 0) return;
    setBusy(true);
    setError("");
    const remaining: DraftRequest[] = [];
    for (const draft of localDrafts) {
      try {
        await saveServerDraft(draft);
      } catch {
        remaining.push(draft);
      }
    }
    setLocalDrafts(remaining);
    saveLocalDrafts(remaining);
    setBusy(false);
    setNotice(remaining.length ? `${localDrafts.length - remaining.length} local draft(s) uploaded; ${remaining.length} remain.` : "All local drafts uploaded to the governed queue.");
    await load();
  }

  function markNotification(item: Notification, action: "READ" | "UNREAD" | "DISMISS") {
    void execute(async () => {
      await api(`notifications/${item.public_id}/state`, {
        method: "POST",
        body: JSON.stringify({ action, expected_version: item.version }),
      });
    }, action === "DISMISS" ? "Notification dismissed." : "Notification state updated.");
  }

  if (loading) return <main className={styles.loading}><div className={styles.spinner} /><p>Preparing your personal control room…</p></main>;
  if (error && !overview) return <main className={styles.errorState}><h2>My Work unavailable</h2><p>{error}</p><button type="button" onClick={() => void load()}>Retry workspace</button></main>;
  if (!overview) return null;

  if (overview.profile_state === "EMPLOYEE_PROFILE_REQUIRED") {
    return (
      <main className={styles.profileState}>
        <span className={styles.eyebrow}>MPSQRE BUILD360 · PHASE 31</span>
        <h1>My work</h1>
        <div className={styles.profileCard}>
          <span className={styles.profileIcon}>HR</span>
          <div>
            <h2>Complete the employee profile</h2>
            <p>Your login has company access, but it is not yet connected to an employee record. Complete the People & Organization profile, then return here.</p>
            <Link href="/platform/people-organization">Open People & Organization</Link>
          </div>
        </div>
      </main>
    );
  }

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "today", label: "Today", count: todayWork.length },
    { id: "queue", label: "My queue", count: queueWork.length },
    { id: "time", label: "Progress & time" },
    { id: "approvals", label: "Approvals", count: overview.summary.pending_approval_count + overview.summary.submitted_team_timesheet_count },
    { id: "offline", label: "Offline", count: overview.summary.offline_draft_count + localDrafts.length },
    { id: "activity", label: "Activity" },
  ];

  return (
    <main className={styles.page}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>MPSQRE BUILD360 · PHASE 31</span>
          <h1>My work</h1>
          <p>One personal operating cockpit for assigned work, site updates, time, approvals and offline continuity.</p>
          <div className={styles.identity}>
            <strong>{overview.employee?.display_name}</strong>
            <span>{overview.employee?.employee_number} · {overview.employee?.job_title}</span>
            {overview.employee?.department_name ? <span>{overview.employee.department_name}</span> : null}
          </div>
        </div>
        <div className={styles.heroActions}>
          <span className={isOnline ? styles.online : styles.offline}>{isOnline ? "Online" : "Offline mode"}</span>
          <span className={styles.phase}>PHASE 31 MY WORK ACTIVE</span>
          <button type="button" disabled={busy} onClick={() => void load()}>Refresh my day</button>
        </div>
      </header>

      {error ? <div className={styles.alert} data-kind="error">{error}<button type="button" onClick={() => setError("")}>×</button></div> : null}
      {notice ? <div className={styles.alert} data-kind="success">{notice}<button type="button" onClick={() => setNotice("")}>×</button></div> : null}

      <section className={styles.kpis}>
        <article><span>Due today</span><strong>{overview.summary.due_today_count}</strong><small>Immediate execution queue</small></article>
        <article data-risk={overview.summary.overdue_count > 0}><span>Overdue</span><strong>{overview.summary.overdue_count}</strong><small>Needs recovery action</small></article>
        <article data-risk={overview.summary.blocked_count > 0}><span>Blocked</span><strong>{overview.summary.blocked_count}</strong><small>Constraints to escalate</small></article>
        <article><span>Approvals</span><strong>{overview.summary.pending_approval_count + overview.summary.submitted_team_timesheet_count}</strong><small>Waiting for your decision</small></article>
        <article><span>Approved hours</span><strong>{overview.summary.hours_this_week}</strong><small>This week</small></article>
        <article><span>Offline drafts</span><strong>{overview.summary.offline_draft_count + localDrafts.length}</strong><small>Continuity queue</small></article>
      </section>

      <nav className={styles.tabs} aria-label="My Work sections">
        {tabs.map((item) => <button type="button" key={item.id} data-active={tab === item.id} onClick={() => setTab(item.id)}>{item.label}{item.count ? <span>{item.count}</span> : null}</button>)}
      </nav>

      {tab === "today" || tab === "queue" ? (
        <section className={styles.workSection}>
          <div className={styles.sectionHeader}>
            <div><h2>{tab === "today" ? "Today’s execution plan" : "My complete work queue"}</h2><p>{tab === "today" ? "Prioritized by overdue, blocked and due-today signals." : "Every active assignment authorized for your employee profile."}</p></div>
            <input value={query} onChange={(event: { target: HTMLInputElement }) => setQuery(event.target.value)} placeholder="Search my work" />
          </div>
          <div className={styles.workGrid}>
            {(tab === "today" ? todayWork : queueWork).map((item) => <WorkCard key={item.public_id} item={item} busy={busy} canExecute={overview.capabilities.can_execute} onTransition={transition} onChecklist={toggleChecklist} />)}
          </div>
          {(tab === "today" ? todayWork : queueWork).length === 0 ? <div className={styles.empty}><strong>No work in this view</strong><span>Your manager can assign work from Project & Work Management.</span></div> : null}
        </section>
      ) : null}

      {tab === "time" ? (
        <div className={styles.twoColumn}>
          <section className={styles.panel}>
            <h2>Record site progress</h2>
            <p>Capture field evidence against work assigned to you.</p>
            <form className={styles.form} onSubmit={submitProgress}>
              <label>Work item<select name="work_item_public_id" required defaultValue=""><option value="" disabled>Select assigned work</option>{queueWork.map((item) => <option key={item.public_id} value={item.public_id}>{item.project_code} · {item.code} · {item.title}</option>)}</select></label>
              <label>Date<input type="date" name="progress_date" defaultValue={today()} required /></label>
              <label>Progress %<input type="number" name="progress_percent" min="0" max="100" step="0.01" /></label>
              <label>Hours worked<input type="number" name="hours_worked" min="0" max="24" step="0.25" defaultValue="0" /></label>
              <label>Quantity<input type="number" name="quantity_completed" min="0" step="0.001" defaultValue="0" /></label>
              <label>Unit<input name="unit_code" placeholder="M3, SQM, NOS" /></label>
              <label className={styles.full}>Progress note<textarea name="note" placeholder="What was completed?" /></label>
              <label className={styles.full}>Blockers<textarea name="blockers" placeholder="Materials, drawings, access, safety or quality constraints" /></label>
              <div className={`${styles.actions} ${styles.full}`}>
                <button type="submit" name="mode" value="record" disabled={busy || !overview.capabilities.can_execute}>Record now</button>
                <button type="submit" name="mode" value="draft" className={styles.secondary} disabled={busy || !overview.capabilities.can_use_offline}>Save offline draft</button>
              </div>
            </form>
          </section>
          <section className={styles.panel}>
            <h2>Log my time</h2>
            <p>Create or submit governed employee timesheets.</p>
            <form className={styles.form} onSubmit={submitTimesheet}>
              <label>Project<select name="project_public_id" required defaultValue=""><option value="" disabled>Select assigned project</option>{projects.map((project) => <option key={project.public_id} value={project.public_id}>{project.code} · {project.name}</option>)}</select></label>
              <label>Work item<select name="work_item_public_id" defaultValue=""><option value="">Project-level time</option>{queueWork.map((item) => <option key={item.public_id} value={item.public_id}>{item.project_code} · {item.code}</option>)}</select></label>
              <label>Date<input type="date" name="work_date" defaultValue={today()} required /></label>
              <label>Hours<input type="number" name="hours" min="0.01" max="24" step="0.25" defaultValue="8" required /></label>
              <label className={styles.full}>Description<textarea name="description" placeholder="Work completed during these hours" /></label>
              <label className={`${styles.check} ${styles.full}`}><input type="checkbox" name="submit_now" /> Submit immediately for review</label>
              <div className={`${styles.actions} ${styles.full}`}>
                <button type="submit" name="mode" value="record" disabled={busy || !overview.capabilities.can_log_time}>Save timesheet</button>
                <button type="submit" name="mode" value="draft" className={styles.secondary} disabled={busy || !overview.capabilities.can_use_offline}>Save offline draft</button>
              </div>
            </form>
            <div className={styles.list}>
              {overview.timesheets.slice(0, 12).map((item) => <article key={item.public_id}><div><strong>{item.work_date} · {item.hours} hours</strong><span>{item.project_code} · {item.work_item_code || "Project"}</span></div><div><span className={styles.status}>{item.status_code}</span>{["DRAFT", "REJECTED"].includes(item.status_code) ? <button type="button" disabled={busy} onClick={() => submitExistingTimesheet(item)}>Submit</button> : null}</div></article>)}
            </div>
          </section>
        </div>
      ) : null}

      {tab === "approvals" ? (
        <div className={styles.twoColumn}>
          <section className={styles.panel}>
            <h2>Work approval inbox</h2>
            <p>Requests where you are the named independent reviewer.</p>
            <div className={styles.list}>
              {overview.approval_inbox.map((item) => <article key={item.public_id}><div><strong>{item.project_code} · {item.work_item_code}</strong><span>{item.work_item_title}</span><small>{item.approval_type_code} · {item.request_note || "No request note"}</small></div><div><span className={styles.status}>{item.status_code}</span>{item.status_code === "PENDING" && overview.capabilities.can_approve ? <div className={styles.actions}><button type="button" disabled={busy} onClick={() => decideApproval(item, "APPROVED")}>Approve</button><button type="button" disabled={busy} className={styles.reject} onClick={() => decideApproval(item, "REJECTED")}>Reject</button></div> : null}</div></article>)}
              {overview.approval_inbox.length === 0 ? <div className={styles.empty}><strong>No work approvals</strong><span>Assigned review requests will appear here.</span></div> : null}
            </div>
          </section>
          <section className={styles.panel}>
            <h2>Direct-report timesheets</h2>
            <p>Manager decisions are restricted to current reporting lines.</p>
            <div className={styles.list}>
              {overview.team_timesheets.map((item) => <article key={item.public_id}><div><strong>{item.employee_name} · {item.hours} hours</strong><span>{item.work_date} · {item.project_code} · {item.work_item_code || "Project"}</span><small>{item.description || "No description"}</small></div><div><div className={styles.actions}><button type="button" disabled={busy || !overview.capabilities.can_approve} onClick={() => decideTeamTimesheet(item, "APPROVED")}>Approve</button><button type="button" disabled={busy || !overview.capabilities.can_approve} className={styles.reject} onClick={() => decideTeamTimesheet(item, "REJECTED")}>Reject</button></div></div></article>)}
              {overview.team_timesheets.length === 0 ? <div className={styles.empty}><strong>No team timesheets</strong><span>Submitted timesheets from direct reports will appear here.</span></div> : null}
            </div>
          </section>
        </div>
      ) : null}

      {tab === "offline" ? (
        <div className={styles.twoColumn}>
          <section className={styles.panel}>
            <div className={styles.panelTop}><div><h2>Device queue</h2><p>Drafts retained locally when the network is unavailable.</p></div><button type="button" disabled={busy || !isOnline || localDrafts.length === 0} onClick={() => void syncLocalQueue()}>Upload local queue</button></div>
            <div className={styles.list}>
              {localDrafts.map((item) => <article key={item.client_draft_id}><div><strong>{item.draft_type_code} draft</strong><span>{new Date(item.client_updated_at).toLocaleString()}</span></div><span className={styles.status}>LOCAL</span></article>)}
              {localDrafts.length === 0 ? <div className={styles.empty}><strong>Device queue clear</strong><span>No unsent drafts remain on this browser.</span></div> : null}
            </div>
          </section>
          <section className={styles.panel}>
            <h2>Governed synchronization queue</h2>
            <p>Server-side drafts with version and conflict controls.</p>
            <div className={styles.list}>
              {overview.offline_drafts.map((item) => <article key={item.public_id} data-conflict={item.status_code === "CONFLICT"}><div><strong>{item.draft_type_code} · {item.work_item_code || "General"}</strong><span>{new Date(item.client_updated_at).toLocaleString()}</span>{item.conflict_reason ? <small className={styles.dangerText}>{item.conflict_reason}</small> : null}</div><div><span className={styles.status}>{item.status_code}</span>{item.status_code !== "SYNCED" ? <div className={styles.actions}><button type="button" disabled={busy || !isOnline} onClick={() => syncServerDraft(item)}>Sync</button><button type="button" disabled={busy} className={styles.reject} onClick={() => discardServerDraft(item)}>Discard</button></div> : null}</div></article>)}
              {overview.offline_drafts.length === 0 ? <div className={styles.empty}><strong>Synchronization queue clear</strong><span>Offline-ready drafts will appear here.</span></div> : null}
            </div>
          </section>
        </div>
      ) : null}

      {tab === "activity" ? (
        <div className={styles.twoColumn}>
          <section className={styles.panel}>
            <h2>Personal activity history</h2>
            <div className={styles.timeline}>
              {overview.activity.map((item) => <article key={item.public_id}><span className={styles.timelineDot} /><div><strong>{item.summary}</strong><span>{item.project_code && item.work_item_code ? `${item.project_code} · ${item.work_item_code}` : readable(item.activity_type_code)}</span><small>{new Date(item.occurred_at).toLocaleString()}</small></div></article>)}
              {overview.activity.length === 0 ? <div className={styles.empty}><strong>No activity yet</strong><span>Work updates, time and approvals will build your audit-friendly history.</span></div> : null}
            </div>
          </section>
          <section className={styles.panel}>
            <h2>Personal notifications</h2>
            <div className={styles.list}>
              {overview.notifications.map((item) => <article key={item.public_id} data-unread={!item.read_at}><div><strong>{item.title}</strong><span>{item.message}</span><small>{new Date(item.created_at).toLocaleString()}</small></div><div className={styles.actions}>{item.action_url && internalRoute(item.action_url) ? <Link href={internalRoute(item.action_url)!}>Open</Link> : null}<button type="button" disabled={busy} onClick={() => markNotification(item, item.read_at ? "UNREAD" : "READ")}>{item.read_at ? "Unread" : "Read"}</button><button type="button" disabled={busy} className={styles.reject} onClick={() => markNotification(item, "DISMISS")}>Dismiss</button></div></article>)}
              {overview.notifications.length === 0 ? <div className={styles.empty}><strong>No notifications</strong><span>Personal operational alerts will appear here.</span></div> : null}
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
