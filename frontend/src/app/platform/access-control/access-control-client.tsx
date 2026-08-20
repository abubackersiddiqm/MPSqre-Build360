"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./access-control.module.css";

type AccessLevel = "NONE" | "VIEW" | "EDIT" | "FULL";

type Person = {
  membership_public_id: string;
  user_public_id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  suspended_at: string | null;
  terminated_at: string | null;
  employee: { employee_number: string; job_title: string; employment_start: string } | null;
  roles: Array<{ public_id: string; code: string; name: string }>;
};

type Invitation = {
  public_id: string;
  email: string;
  display_name: string;
  invitation_type_code: string;
  employee_number: string;
  job_title: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  delivery_status_code: string;
  delivery_attempted_at: string | null;
  delivery_sent_at: string | null;
  delivery_error_code: string;
  delivery_brand_name: string;
  is_expired?: boolean;
};

type Overview = {
  company: { public_id: string; code: string; display_name: string };
  summary: {
    active_people_count: number;
    suspended_people_count: number;
    active_role_count: number;
    permission_catalog_count: number;
    pending_invitation_count: number;
  };
  people: Person[];
  invitations: Invitation[];
};

type AccessArea = {
  code: string;
  label: string;
  description: string;
  permission_counts: { VIEW: number; EDIT: number; FULL: number };
};

type PersonAccess = {
  membership_public_id: string;
  levels: Record<string, AccessLevel>;
  locked: boolean;
  locked_reason: string;
  access_source: string;
};

type AccessMatrix = {
  levels: Array<{ code: AccessLevel; label: string }>;
  areas: AccessArea[];
  people: PersonAccess[];
};

type AccessHistoryChange = {
  area_code: string;
  before: AccessLevel;
  after: AccessLevel;
};

type AccessHistoryItem = {
  public_id: string;
  occurred_at: string;
  actor_public_id: string | null;
  actor_display_name: string;
  actor_email: string;
  reason_code: string;
  correlation_id: string;
  before_levels: Record<string, AccessLevel>;
  after_levels: Record<string, AccessLevel>;
  changes: AccessHistoryChange[];
};

type AccessHistoryResponse = {
  items: AccessHistoryItem[];
};

type InviteResult = {
  public_id: string;
  email: string;
  expires_at: string;
  acceptance_url?: string;
  delivery: { status: string; error_code: string };
};

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/platform/access-control/${path}`, {
    cache: "no-store",
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const payload = await response.json().catch(() => ({})) as { message?: string; detail?: string };
  if (!response.ok) throw new Error(payload.message || payload.detail || "The request could not be completed.");
  return payload as T;
}

function initials(value: string): string {
  return value.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("") || "U";
}

function preset(areas: AccessArea[], level: AccessLevel): Record<string, AccessLevel> {
  return Object.fromEntries(areas.map((area) => [area.code, level]));
}

function AccessMatrixGrid({
  areas,
  levels,
  value,
  disabled,
  onChange,
}: {
  areas: AccessArea[];
  levels: Array<{ code: AccessLevel; label: string }>;
  value: Record<string, AccessLevel>;
  disabled?: boolean;
  onChange: (next: Record<string, AccessLevel>) => void;
}) {
  return <div className={styles.matrix}>
    <div className={styles.matrixHead}>
      <span>Module</span>
      {levels.map((level) => <span key={level.code}>{level.label}</span>)}
    </div>
    {areas.map((area) => <div className={styles.matrixRow} key={area.code}>
      <div className={styles.areaCopy}>
        <strong>{area.label}</strong>
        <small>{area.description}</small>
      </div>
      {levels.map((level) => {
        const selected = (value[area.code] ?? "NONE") === level.code;
        const unavailable =
          level.code !== "NONE" &&
          area.permission_counts[level.code as "VIEW" | "EDIT" | "FULL"] === 0;
        return <button
          aria-label={`${area.label}: ${level.label}`}
          aria-pressed={selected}
          className={`${styles.levelCell} ${selected ? styles.levelCellActive : ""}`}
          disabled={disabled || unavailable}
          key={level.code}
          onClick={() => onChange({ ...value, [area.code]: level.code })}
          type="button"
        >
          <span>{selected ? "✓" : ""}</span>
        </button>;
      })}
    </div>)}
  </div>;
}

export function AccessControlClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [matrix, setMatrix] = useState<AccessMatrix | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [draft, setDraft] = useState<Record<string, AccessLevel>>({});
  const [inviteDraft, setInviteDraft] = useState<Record<string, AccessLevel>>({});
  const [query, setQuery] = useState("");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [latestInviteUrl, setLatestInviteUrl] = useState("");
  const [historyItems, setHistoryItems] = useState<AccessHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [changeReason, setChangeReason] = useState("company-admin-permission-change");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextOverview, nextMatrix] = await Promise.all([
        jsonRequest<Overview>("company/overview"),
        jsonRequest<AccessMatrix>("company/access-matrix"),
      ]);
      const now = Date.now();
      nextOverview.invitations = nextOverview.invitations.map((item) => ({
        ...item,
        is_expired: new Date(item.expires_at).getTime() <= now,
      }));
      setOverview(nextOverview);
      setMatrix(nextMatrix);
      setSelectedId((current) =>
        current && nextOverview.people.some((person) => person.membership_public_id === current)
          ? current
          : nextOverview.people[0]?.membership_public_id ?? "",
      );
      setInviteDraft((current) =>
        Object.keys(current).length ? current : preset(nextMatrix.areas, "NONE"),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "User administration could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const accessByMembership = useMemo(
    () => new Map((matrix?.people ?? []).map((item) => [item.membership_public_id, item])),
    [matrix],
  );

  const selectedPerson = overview?.people.find((person) => person.membership_public_id === selectedId) ?? null;
  const selectedAccess = selectedPerson ? accessByMembership.get(selectedPerson.membership_public_id) ?? null : null;

  useEffect(() => {
    if (!selectedPerson || !matrix) return;
    setDraft({ ...(selectedAccess?.levels ?? preset(matrix.areas, "NONE")) });
  }, [selectedPerson, selectedAccess, matrix]);

  useEffect(() => {
    if (!selectedPerson) {
      setHistoryItems([]);
      setHistoryError("");
      return;
    }
    let activeRequest = true;
    setHistoryLoading(true);
    setHistoryError("");
    void jsonRequest<AccessHistoryResponse>(
      `company/people/${selectedPerson.membership_public_id}/access-history`,
    )
      .then((payload) => {
        if (activeRequest) setHistoryItems(payload.items);
      })
      .catch((caught) => {
        if (activeRequest) {
          setHistoryItems([]);
          setHistoryError(caught instanceof Error ? caught.message : "Permission history could not be loaded.");
        }
      })
      .finally(() => {
        if (activeRequest) setHistoryLoading(false);
      });
    return () => {
      activeRequest = false;
    };
  }, [selectedPerson]);

  const filteredPeople = useMemo(() => {
    const people = overview?.people ?? [];
    const needle = query.trim().toLowerCase();
    if (!needle) return people;
    return people.filter((person) =>
      [person.display_name, person.email, person.employee?.employee_number ?? "", person.employee?.job_title ?? ""]
        .some((value) => value.toLowerCase().includes(needle)),
    );
  }, [overview, query]);

  async function savePermissions() {
    if (!selectedPerson || selectedAccess?.locked) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await jsonRequest(`company/people/${selectedPerson.membership_public_id}/access-profile`, {
        method: "POST",
        body: JSON.stringify({
          access_levels: draft,
          reason_code: changeReason.trim() || "company-admin-permission-change",
        }),
      });
      setNotice(`Permissions updated for ${selectedPerson.display_name}.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Permissions could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await jsonRequest<InviteResult>("company/invitations", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          display_name: form.get("display_name"),
          invitation_type_code: "EMPLOYEE",
          role_public_ids: [],
          access_levels: inviteDraft,
          employee_number: form.get("employee_number"),
          job_title: form.get("job_title"),
          ttl_hours: 72,
        }),
      });
      setLatestInviteUrl(result.acceptance_url || "");
      setNotice(
        result.delivery.status === "SENT"
          ? `Invitation email sent to ${result.email}.`
          : `Invitation created for ${result.email}${result.delivery.error_code ? ` (${result.delivery.error_code})` : ""}.`,
      );
      formElement.reset();
      setInviteOpen(false);
      if (matrix) setInviteDraft(preset(matrix.areas, "NONE"));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "User invitation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(person: Person, status: "ACTIVE" | "SUSPENDED" | "TERMINATED") {
    if (status === "TERMINATED" && !window.confirm(`Remove ${person.display_name} from this company?`)) return;
    setBusy(true);
    setError("");
    try {
      await jsonRequest(`company/people/${person.membership_public_id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status_code: status, reason_code: "company_user_admin" }),
      });
      setNotice(`${person.display_name} status updated.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "User status update failed.");
    } finally {
      setBusy(false);
    }
  }

  async function resend(invitation: Invitation) {
    setBusy(true);
    setError("");
    try {
      const result = await jsonRequest<InviteResult>(`company/invitations/${invitation.public_id}/regenerate`, {
        method: "POST",
        body: JSON.stringify({ ttl_hours: 72 }),
      });
      setLatestInviteUrl(result.acceptance_url || "");
      setNotice(`Fresh invitation prepared for ${result.email}.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Invitation resend failed.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(invitation: Invitation) {
    setBusy(true);
    setError("");
    try {
      await jsonRequest(`company/invitations/${invitation.public_id}/revoke`, { method: "POST", body: "{}" });
      setNotice(`Invitation revoked for ${invitation.display_name}.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Invitation revocation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function copyInvite() {
    if (!latestInviteUrl) return;
    try {
      await navigator.clipboard.writeText(latestInviteUrl);
      setNotice("Invitation link copied.");
    } catch {
      setNotice(`Copy this invitation link: ${latestInviteUrl}`);
    }
  }

  if (loading && !overview) return <main className={styles.page}><div className={styles.loading}>Loading users & permissions…</div></main>;
  if (!overview || !matrix) return <main className={styles.page}><div className={styles.loading}>{error || "Users & permissions unavailable."}</div></main>;

  const active = selectedPerson ? !selectedPerson.suspended_at && !selectedPerson.terminated_at : false;
  const pending = overview.invitations.filter((item) => !item.accepted_at && !item.revoked_at);

  return <main className={styles.page}>
    <header className={styles.header}>
      <div>
        <p className={styles.kicker}>Company administration</p>
        <h1>Users & permissions</h1>
        <p>Invite users and control exactly what each person can view or edit.</p>
      </div>
      <div className={styles.headerActions}>
        <span className={styles.companyPill}>{overview.company.display_name}</span>
        <button className={styles.primaryButton} onClick={() => setInviteOpen(true)} type="button">+ Add user</button>
      </div>
    </header>

    {error ? <div className={styles.error}>{error}</div> : null}
    {notice ? <div className={styles.notice}><span>{notice}</span>{latestInviteUrl ? <button className={styles.secondaryButton} onClick={() => void copyInvite()} type="button">Copy invite link</button> : null}</div> : null}

    <section className={styles.stats}>
      <div><strong>{overview.summary.active_people_count}</strong><span>Active users</span></div>
      <div><strong>{overview.summary.suspended_people_count}</strong><span>Suspended</span></div>
      <div><strong>{matrix.areas.length}</strong><span>Enabled modules</span></div>
      <div><strong>{overview.summary.pending_invitation_count}</strong><span>Pending invites</span></div>
    </section>

    <section className={styles.workspace}>
      <aside className={styles.userListPane}>
        <div className={styles.searchBox}>
          <span aria-hidden="true">⌕</span>
          <input aria-label="Search users" onChange={(event) => setQuery(event.target.value)} placeholder="Search users…" value={query} />
        </div>
        <div className={styles.userList}>
          {filteredPeople.map((person) => {
            const isSelected = person.membership_public_id === selectedId;
            const isActive = !person.suspended_at && !person.terminated_at;
            return <button className={`${styles.userRow} ${isSelected ? styles.userRowActive : ""}`} key={person.membership_public_id} onClick={() => setSelectedId(person.membership_public_id)} type="button">
              <span className={styles.avatar}>{initials(person.display_name || person.email)}</span>
              <span className={styles.userCopy}>
                <strong>{person.display_name || person.email}</strong>
                <small>{person.employee?.job_title || person.email}</small>
              </span>
              <span className={`${styles.dot} ${isActive ? styles.dotActive : ""}`} />
            </button>;
          })}
          {!filteredPeople.length ? <p className={styles.empty}>No matching users.</p> : null}
        </div>
      </aside>

      <section className={styles.permissionPane}>
        {selectedPerson ? <>
          <div className={styles.personHeader}>
            <div className={styles.identity}>
              <span className={styles.avatarLarge}>{initials(selectedPerson.display_name || selectedPerson.email)}</span>
              <div>
                <h2>{selectedPerson.display_name || selectedPerson.email}</h2>
                <p>{selectedPerson.employee?.job_title || "Company user"} · {selectedPerson.email}</p>
                <div className={styles.tags}>
                  <span>{active ? "Active" : selectedPerson.terminated_at ? "Removed" : "Suspended"}</span>
                  <span>{selectedAccess?.access_source.replaceAll("_", " ") || "Managed"}</span>
                </div>
              </div>
            </div>
            {!selectedPerson.terminated_at ? <div className={styles.personActions}>
              {active
                ? <button className={styles.secondaryButton} disabled={busy} onClick={() => void setStatus(selectedPerson, "SUSPENDED")} type="button">Suspend</button>
                : <button className={styles.secondaryButton} disabled={busy} onClick={() => void setStatus(selectedPerson, "ACTIVE")} type="button">Reactivate</button>}
              <button className={styles.dangerButton} disabled={busy} onClick={() => void setStatus(selectedPerson, "TERMINATED")} type="button">Remove</button>
            </div> : null}
          </div>

          <div className={styles.matrixToolbar}>
            <div><h3>Module access</h3><p>Only modules purchased for this company can be granted.</p></div>
            {!selectedAccess?.locked ? <div className={styles.presets}>
              <button onClick={() => setDraft(preset(matrix.areas, "VIEW"))} type="button">View only</button>
              <button onClick={() => setDraft(preset(matrix.areas, "EDIT"))} type="button">Standard</button>
              <button onClick={() => setDraft(preset(matrix.areas, "FULL"))} type="button">Full</button>
              <button onClick={() => setDraft(preset(matrix.areas, "NONE"))} type="button">Clear</button>
            </div> : null}
          </div>

          {selectedAccess?.locked ? <div className={styles.locked}><strong>Access locked here.</strong><span>{selectedAccess.locked_reason}</span></div> : null}

          <AccessMatrixGrid
            areas={matrix.areas}
            disabled={busy || Boolean(selectedAccess?.locked)}
            levels={matrix.levels}
            onChange={setDraft}
            value={draft}
          />

          {!selectedAccess?.locked ? <div className={styles.saveBar}>
            <label className={styles.reasonField}>
              <span>Change reason</span>
              <input
                maxLength={100}
                onChange={(event) => setChangeReason(event.target.value)}
                value={changeReason}
              />
            </label>
            <div className={styles.saveAction}>
              <span>Backend permissions are enforced immediately after save.</span>
              <button className={styles.primaryButton} disabled={busy} onClick={() => void savePermissions()} type="button">{busy ? "Saving…" : "Save permissions"}</button>
            </div>
          </div> : null}

          <section className={styles.historyPanel}>
            <div className={styles.historyHeader}>
              <div>
                <h3>Permission history</h3>
                <p>Append-only audit trail for this user&apos;s managed access changes.</p>
              </div>
              <span>{historyItems.length} changes</span>
            </div>
            {historyLoading ? <div className={styles.historyEmpty}>Loading permission history…</div> : null}
            {historyError ? <div className={styles.historyError}>{historyError}</div> : null}
            {!historyLoading && !historyError && historyItems.length === 0
              ? <div className={styles.historyEmpty}>No managed permission changes recorded yet.</div>
              : null}
            {!historyLoading && !historyError && historyItems.length > 0
              ? <div className={styles.historyList}>
                  {historyItems.map((item) => <article className={styles.historyItem} key={item.public_id}>
                    <div className={styles.historyDot} aria-hidden="true" />
                    <div className={styles.historyContent}>
                      <div className={styles.historyMeta}>
                        <strong>{new Date(item.occurred_at).toLocaleString()}</strong>
                        <span>Changed by {item.actor_display_name || item.actor_email || "System"}</span>
                      </div>
                      <div className={styles.historyChanges}>
                        {item.changes.map((change) => <span key={`${item.public_id}-${change.area_code}`}>
                          <b>{change.area_code}</b>
                          <em>{change.before.replaceAll("_", " ")}</em>
                          <i>→</i>
                          <em>{change.after.replaceAll("_", " ")}</em>
                        </span>)}
                      </div>
                      <div className={styles.historyFoot}>
                        <span>Reason: {item.reason_code || "company-admin-permission-change"}</span>
                        <code title={item.correlation_id}>{item.correlation_id.slice(0, 8)}</code>
                      </div>
                    </div>
                  </article>)}
                </div>
              : null}
          </section>
        </> : <div className={styles.loading}>Select a user.</div>}
      </section>
    </section>

    <section className={styles.pendingPanel}>
      <div className={styles.sectionTitle}><div><h2>Pending invitations</h2><p>Track activation and resend or revoke invitations.</p></div><span>{pending.length} pending</span></div>
      {pending.length ? <div className={styles.pendingList}>{pending.map((item) => <div className={styles.pendingRow} key={item.public_id}>
        <div><strong>{item.display_name}</strong><small>{item.email} · {item.job_title || "Company user"}</small></div>
        <span className={styles.delivery}>{item.delivery_status_code.replaceAll("_", " ")}</span>
        <div><button className={styles.secondaryButton} disabled={busy} onClick={() => void resend(item)} type="button">Resend</button><button className={styles.textDangerButton} disabled={busy} onClick={() => void revoke(item)} type="button">Revoke</button></div>
      </div>)}</div> : <p className={styles.empty}>No pending invitations.</p>}
    </section>

    {inviteOpen ? <div className={styles.modalBackdrop}>
      <section aria-modal="true" className={styles.modal} role="dialog">
        <div className={styles.modalHead}>
          <div><p className={styles.kicker}>New company user</p><h2>Add user</h2><p>Enter user details and choose access before sending the invitation.</p></div>
          <button className={styles.closeButton} onClick={() => setInviteOpen(false)} type="button">×</button>
        </div>
        <form onSubmit={invite}>
          <div className={styles.formGrid}>
            <label>Full name<input name="display_name" required /></label>
            <label>Email<input name="email" required type="email" /></label>
            <label>Employee number<input name="employee_number" required /></label>
            <label>Job title<input name="job_title" required /></label>
          </div>
          <div className={styles.matrixToolbar}>
            <div><h3>Access</h3><p>Choose No access, View only, Read + edit or Full for each module.</p></div>
            <div className={styles.presets}>
              <button onClick={() => setInviteDraft(preset(matrix.areas, "VIEW"))} type="button">View only</button>
              <button onClick={() => setInviteDraft(preset(matrix.areas, "EDIT"))} type="button">Standard</button>
              <button onClick={() => setInviteDraft(preset(matrix.areas, "FULL"))} type="button">Full</button>
              <button onClick={() => setInviteDraft(preset(matrix.areas, "NONE"))} type="button">Clear</button>
            </div>
          </div>
          <AccessMatrixGrid areas={matrix.areas} levels={matrix.levels} onChange={setInviteDraft} value={inviteDraft} />
          <div className={styles.modalActions}>
            <button className={styles.secondaryButton} onClick={() => setInviteOpen(false)} type="button">Cancel</button>
            <button className={styles.primaryButton} disabled={busy} type="submit">{busy ? "Sending…" : "Send invitation"}</button>
          </div>
        </form>
      </section>
    </div> : null}
  </main>;
}
