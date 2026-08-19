"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useState } from "react";

import styles from "./access-control.module.css";

type Role = { public_id: string; code: string; name: string; version: number; permission_codes: string[] };
type Person = { membership_public_id: string; user_public_id: string; email: string; display_name: string; is_active: boolean; suspended_at: string | null; terminated_at: string | null; employee: { employee_number: string; job_title: string; employment_start: string } | null; roles: Array<{ public_id: string; code: string; name: string }> };
type Invitation = { public_id: string; email: string; display_name: string; invitation_type_code: string; employee_number: string; job_title: string; expires_at: string; accepted_at: string | null; revoked_at: string | null; delivery_status_code: string; delivery_attempted_at: string | null; delivery_sent_at: string | null; delivery_error_code: string; delivery_brand_name: string; is_expired?: boolean };
type Overview = { company: { public_id: string; code: string; display_name: string; locale: string; timezone: string; currency: string }; summary: { active_people_count: number; suspended_people_count: number; active_role_count: number; permission_catalog_count: number; pending_invitation_count: number }; people: Person[]; roles: Role[]; permissions: Array<{ code: string; description: string }>; invitations: Invitation[] };
type InviteResult = { public_id: string; email: string; expires_at: string; acceptance_token?: string; acceptance_url?: string; delivery: { status: string; brand_name: string; sender_name: string; error_code: string } };

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/platform/access-control/${path}`, { cache: "no-store", ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  const payload = await response.json().catch(() => ({})) as { message?: string; detail?: string };
  if (!response.ok) throw new Error(payload.message || payload.detail || "The request could not be completed.");
  return payload as T;
}

function RolePicker({ person, roles, busy, onApply }: { person: Person; roles: Role[]; busy: boolean; onApply: (person: Person, rolePublicIds: string[]) => Promise<void> }) {
  const [selected, setSelected] = useState<string[]>(person.roles.map((role) => role.public_id));
  return <div className={styles.rolePicker}><select multiple aria-label={`Access levels for ${person.display_name}`} value={selected} onChange={(event: ChangeEvent<HTMLSelectElement>) => setSelected(Array.from(event.target.selectedOptions, (option) => option.value))} disabled={busy}>{roles.map((role) => <option key={role.public_id} value={role.public_id}>{role.name}</option>)}</select><button className={`${styles.button} ${styles.buttonSecondary}`} type="button" disabled={busy} onClick={() => void onApply(person, selected)}>Apply</button></div>;
}

export function AccessControlClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [latestInviteUrl, setLatestInviteUrl] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await jsonRequest<Overview>("company/overview");
      const checkedAt = Date.now();
      setOverview({
        ...payload,
        invitations: payload.invitations.map((invitation) => ({
          ...invitation,
          is_expired: new Date(invitation.expires_at).getTime() <= checkedAt,
        })),
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "User administration could not be loaded.");
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

  async function createRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    setError("");
    setNotice("");
    const form = new FormData(formElement);
    const codes = String(form.get("permission_codes") || "").split(/[\s,]+/).map((value) => value.trim()).filter(Boolean);
    try {
      await jsonRequest("company/roles", { method: "POST", body: JSON.stringify({ code: form.get("code"), name: form.get("name"), permission_codes: codes }) });
      setNotice("Access level published successfully.");
      formElement.reset();
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Access level creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    setError("");
    setNotice("");
    const form = new FormData(formElement);
    const role = String(form.get("role_public_id") || "");
    try {
      const result = await jsonRequest<InviteResult>("company/invitations", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          display_name: form.get("display_name"),
          invitation_type_code: "EMPLOYEE",
          role_public_ids: role ? [role] : [],
          employee_number: form.get("employee_number"),
          job_title: form.get("job_title"),
          ttl_hours: 72,
        }),
      });
      setLatestInviteUrl(result.acceptance_url || "");
      if (result.delivery.status === "SENT") {
        setNotice(`Invitation email sent to ${result.email}.`);
      } else if (result.delivery.status === "LOCAL_PREVIEW") {
        setNotice(`Invitation prepared for ${result.email}.`);
      } else {
        setNotice(`Invitation created, but email delivery failed${result.delivery.error_code ? ` (${result.delivery.error_code})` : ""}. Use Resend after email delivery is available.`);
      }
      formElement.reset();
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "User invitation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function assignRoles(person: Person, rolePublicIds: string[]) {
    setBusy(true);
    setError("");
    try {
      await jsonRequest(`company/people/${person.membership_public_id}/roles`, { method: "POST", body: JSON.stringify({ role_public_ids: rolePublicIds }) });
      setNotice(`Access levels updated for ${person.display_name}.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Access level assignment failed.");
    } finally {
      setBusy(false);
    }
  }

  async function setPersonStatus(person: Person, statusCode: "ACTIVE" | "SUSPENDED" | "TERMINATED") {
    if (statusCode === "TERMINATED" && !window.confirm(`Remove ${person.display_name} from this company?`)) return;
    setBusy(true);
    setError("");
    try {
      await jsonRequest(`company/people/${person.membership_public_id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status_code: statusCode, reason_code: "company_user_admin" }),
      });
      setNotice(statusCode === "TERMINATED" ? `${person.display_name} removed from the company.` : `${person.display_name} status updated.`);
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
    setNotice("");
    try {
      const result = await jsonRequest<InviteResult>(`company/invitations/${invitation.public_id}/regenerate`, { method: "POST", body: JSON.stringify({ ttl_hours: 72 }) });
      setLatestInviteUrl(result.acceptance_url || "");
      if (result.delivery.status === "SENT") {
        setNotice(`Fresh invitation email sent to ${result.email}. The previous pending invitation was revoked.`);
      } else if (result.delivery.status === "LOCAL_PREVIEW") {
        setNotice(`Fresh invitation prepared for ${result.email}.`);
      } else {
        setNotice(`A fresh invitation was created, but email delivery failed${result.delivery.error_code ? ` (${result.delivery.error_code})` : ""}.`);
      }
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Invitation resend failed.");
    } finally {
      setBusy(false);
    }
  }

  async function copyLatestInvite() {
    if (!latestInviteUrl) return;
    try {
      await navigator.clipboard.writeText(latestInviteUrl);
      setNotice("One-time invitation link copied.");
    } catch {
      setNotice(`Copy this one-time invitation link: ${latestInviteUrl}`);
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

  if (loading && !overview) return <main className={styles.page}><div className={styles.loading}>Loading company users…</div></main>;
  if (!overview) return <main className={styles.page}><section className={styles.panel}><p className={styles.kicker}>User administration unavailable</p><h1>Company users could not be opened.</h1><p className={styles.panelIntro}>{error || "Select a company and verify Company Administrator access."}</p><button className={styles.button} onClick={() => void load()} type="button">Retry</button></section></main>;

  const canManageRoles = overview.permissions.length > 0;
  const employeeRoles = overview.roles.filter((role) => role.code !== "COMPANY_ADMIN" && role.code !== "COMPANY_ADMINISTRATOR");

  return <main className={styles.page}>
    <section className={styles.hero}><div><p className={styles.kicker}>Company administration</p><h1>Users</h1><p>This page manages user onboarding and membership lifecycle. Purchased white-label branding is configured separately in the Brand workspace; SaaS packages, modules, release, cloud and platform controls remain with Build360 Super Admin.</p></div><span className={styles.badge}>User lifecycle</span></section>

    <section className={styles.metrics}>
      <article className={styles.metric}><span>Active users</span><strong>{overview.summary.active_people_count}</strong></article>
      <article className={styles.metric}><span>Suspended users</span><strong>{overview.summary.suspended_people_count}</strong></article>
      <article className={styles.metric}><span>Available access levels</span><strong>{overview.roles.length}</strong></article>
      <article className={styles.metric}><span>Pending invites</span><strong>{overview.summary.pending_invitation_count}</strong></article>
      <article className={styles.metric}><span>Company</span><strong className={styles.companyMetric}>{overview.company.code}</strong></article>
    </section>

    {error ? <p className={styles.error}>{error}</p> : null}
    {notice ? <div className={styles.notice}><span>{notice}</span>{latestInviteUrl ? <button className={`${styles.button} ${styles.buttonSecondary}`} type="button" onClick={() => void copyLatestInvite()}>Copy fresh invite link</button> : null}</div> : null}

    <div className={styles.grid}>
      <div>
        <section className={styles.panel}><h2>Add user</h2><p className={styles.panelIntro}>{canManageRoles ? "Invite a user and choose an existing access level." : "Invite or remove users only. New users automatically receive the Company User access level provisioned by Build360 Super Admin from the company SaaS package."}</p><form onSubmit={invite}><div className={styles.formGrid}><div className={styles.field}><label>Full name</label><input name="display_name" required /></div><div className={styles.field}><label>Email</label><input name="email" type="email" required /></div><div className={styles.field}><label>Employee number</label><input name="employee_number" required /></div><div className={styles.field}><label>Job title</label><input name="job_title" required /></div>{canManageRoles ? <div className={`${styles.field} ${styles.fieldFull}`}><label>Access level</label><select name="role_public_id" required defaultValue=""><option value="" disabled>Select access level</option>{employeeRoles.map((role) => <option key={role.public_id} value={role.public_id}>{role.name}</option>)}</select></div> : <div className={`${styles.field} ${styles.fieldFull}`}><label>Access level</label><div className={styles.readOnlyAccess}>Company User · controlled by Super Admin package</div></div>}</div><div className={styles.actions}><button className={styles.button} disabled={busy || (canManageRoles && employeeRoles.length === 0)} type="submit">{busy ? "Working…" : "Send invitation"}</button></div>{canManageRoles && employeeRoles.length === 0 ? <p className={styles.emptyInline}>No employee access level is configured yet. Re-apply the company SaaS package from Super Admin.</p> : null}</form></section>
        {canManageRoles ? <section className={styles.panel}><h2>Advanced access levels</h2><p className={styles.panelIntro}>Visible only to Build360 platform/access operators. Company Administrators do not receive permission-role publishing capability.</p><form onSubmit={createRole}><div className={styles.formGrid}><div className={styles.field}><label>Access code</label><input name="code" placeholder="SITE_ENGINEER" required /></div><div className={styles.field}><label>Access name</label><input name="name" placeholder="Site Engineer" required /></div><div className={`${styles.field} ${styles.fieldFull}`}><label>Permission codes</label><textarea name="permission_codes" placeholder="project.dashboard.read, work.view" required /></div></div><div className={styles.actions}><button className={styles.button} disabled={busy} type="submit">Publish access level</button></div></form><details style={{ marginTop: 16 }}><summary>Permission catalogue</summary><div className={styles.code}>{overview.permissions.map((permission) => permission.code).join("\n")}</div></details></section> : null}
      </div>

      <div><section className={styles.panel}><h2>Company users</h2><p className={styles.panelIntro}>Add, suspend, reactivate or remove users. Permission-role editing is intentionally outside the Company Administrator surface.</p><div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>User</th><th>Employee</th><th>Access</th><th>Status</th><th>Controls</th></tr></thead><tbody>{overview.people.map((person) => { const active = !person.suspended_at && !person.terminated_at; return <tr key={person.membership_public_id}><td><strong>{person.display_name}</strong><div className={styles.subtle}>{person.email}</div></td><td>{person.employee ? <><strong>{person.employee.employee_number}</strong><div className={styles.subtle}>{person.employee.job_title}</div></> : "No employee profile"}</td><td>{canManageRoles ? <RolePicker key={`${person.membership_public_id}:${person.roles.map((role) => role.public_id).join(",")}`} person={person} roles={overview.roles} busy={busy} onApply={assignRoles} /> : person.roles.length ? person.roles.map((role) => role.name).join(", ") : "No access level"}</td><td><span className={`${styles.pill} ${active ? styles.pillActive : styles.pillDanger}`}>{active ? "ACTIVE" : person.terminated_at ? "REMOVED" : "SUSPENDED"}</span></td><td>{person.terminated_at ? "Locked" : <div className={styles.rowActions}><button className={`${styles.button} ${active ? styles.buttonSecondary : styles.button}`} type="button" disabled={busy} onClick={() => void setPersonStatus(person, active ? "SUSPENDED" : "ACTIVE")}>{active ? "Suspend" : "Reactivate"}</button><button className={`${styles.button} ${styles.buttonDanger}`} type="button" disabled={busy} onClick={() => void setPersonStatus(person, "TERMINATED")}>Remove</button></div>}</td></tr>; })}</tbody></table></div></section>

      <section className={styles.panel}><h2>Invitations</h2><p className={styles.panelIntro}>Invitations are delivered by email. Resend securely revokes the previous pending invitation and sends a fresh one.</p><div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Invitee</th><th>Expires</th><th>Status</th><th>Delivery</th><th>Actions</th></tr></thead><tbody>{overview.invitations.length ? overview.invitations.map((invitation) => { const pending = !invitation.accepted_at && !invitation.revoked_at; const expired = invitation.is_expired === true; return <tr key={invitation.public_id}><td><strong>{invitation.display_name}</strong><div className={styles.subtle}>{invitation.email}</div>{invitation.delivery_brand_name ? <div className={styles.subtle}>Brand: {invitation.delivery_brand_name}</div> : null}</td><td>{new Date(invitation.expires_at).toLocaleString()}</td><td>{invitation.accepted_at ? "ACCEPTED" : invitation.revoked_at ? "REVOKED" : expired ? "EXPIRED" : "PENDING"}</td><td><strong>{invitation.delivery_status_code.replaceAll("_", " ")}</strong>{invitation.delivery_error_code ? <div className={styles.subtle}>{invitation.delivery_error_code}</div> : null}</td><td>{!invitation.accepted_at ? <div className={styles.rowActions}><button className={`${styles.button} ${styles.buttonSecondary}`} disabled={busy} onClick={() => void resend(invitation)} type="button">Resend</button>{pending ? <button className={`${styles.button} ${styles.buttonDanger}`} disabled={busy} onClick={() => void revoke(invitation)} type="button">Revoke</button> : null}</div> : "—"}</td></tr>; }) : <tr><td colSpan={5} className={styles.empty}>No invitations yet.</td></tr>}</tbody></table></div></section></div>
    </div>
  </main>;
}
