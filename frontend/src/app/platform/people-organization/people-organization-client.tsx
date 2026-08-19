"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./people-organization.module.css";

type Department = {
  public_id: string;
  code: string;
  name: string;
  parent_name: string | null;
  location_name: string | null;
  cost_center_code: string;
  is_active: boolean;
};
type Designation = {
  public_id: string;
  code: string;
  name: string;
  level_code: string;
  description: string;
  is_active: boolean;
};
type Calendar = {
  public_id: string;
  code: string;
  name: string;
  timezone: string;
  working_days: number[];
  standard_hours_per_day: string;
  is_active: boolean;
};
type Location = {
  public_id: string;
  code: string;
  name: string;
  location_type_code: string;
};
type PersonProfile = {
  public_id: string;
  department_public_id: string | null;
  department_name: string | null;
  designation_public_id: string | null;
  designation_name: string | null;
  work_calendar_public_id: string | null;
  employment_type_code: string;
  worker_category_code: string;
  mobile: string;
  status_code: string;
  probation_end: string | null;
  confirmation_date: string | null;
  version: number;
};
type Person = {
  employee_public_id: string;
  employee_number: string;
  display_name: string;
  email: string;
  job_title: string;
  employment_start: string;
  employment_end: string | null;
  membership_suspended_at: string | null;
  membership_terminated_at: string | null;
  profile: PersonProfile | null;
  manager: {
    employee_public_id: string;
    employee_number: string;
    display_name: string;
  } | null;
};
type Assignment = {
  public_id: string;
  employee_public_id: string;
  employee_number: string;
  employee_name: string;
  assignment_type_code: string;
  project_code: string;
  site_code: string;
  location_name: string | null;
  work_package_code: string;
  allocation_percent: string;
  effective_from: string;
  effective_to: string | null;
  is_primary: boolean;
};
type LeaveType = {
  public_id: string;
  code: string;
  name: string;
  unit_code: string;
  requires_approval: boolean;
  is_paid: boolean;
  annual_entitlement: string | null;
};
type LeaveRequest = {
  public_id: string;
  employee_public_id: string;
  employee_number: string;
  employee_name: string;
  leave_type_public_id: string;
  leave_type_name: string;
  start_date: string;
  end_date: string;
  quantity: string;
  reason: string;
  status_code: string;
  review_note: string;
  version: number;
};
type Attendance = {
  public_id: string;
  employee_public_id: string;
  employee_number: string;
  employee_name: string;
  work_date: string;
  status_code: string;
  hours_worked: string;
  source_code: string;
  notes: string;
};
type ImportResultRow = { row: number; status: string; acceptance_token?: string; message?: string };
type ImportJob = {
  public_id: string;
  source_name: string;
  status_code: string;
  total_rows: number;
  success_rows: number;
  failed_rows: number;
  created_at: string;
};
type Overview = {
  company: { display_name: string; timezone: string; currency: string };
  summary: {
    employee_count: number;
    active_profile_count: number;
    department_count: number;
    unassigned_employee_count: number;
    pending_leave_count: number;
    attendance_recorded_today: number;
  };
  departments: Department[];
  designations: Designation[];
  work_calendars: Calendar[];
  locations: Location[];
  people: Person[];
  assignments: Assignment[];
  leave_types: LeaveType[];
  leave_requests: LeaveRequest[];
  attendance_entries: Attendance[];
  import_jobs: ImportJob[];
};
type Tab = "people" | "structure" | "assignments" | "leave" | "attendance" | "import";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/platform/people-organization/${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const payload = (await response.json().catch(() => ({}))) as {
    message?: string;
    detail?: string;
    non_field_errors?: string[];
  };
  if (!response.ok) {
    throw new Error(
      payload.message || payload.detail || payload.non_field_errors?.join(" ") || "Request failed.",
    );
  }
  return payload as T;
}

function formValue(form: FormData, name: string): string {
  return String(form.get(name) ?? "").trim();
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function EmployeeSelect({ people, name = "employee_public_id" }: { people: Person[]; name?: string }) {
  return (
    <select name={name} required defaultValue="">
      <option value="" disabled>
        Select person
      </option>
      {people.map((person) => (
        <option key={person.employee_public_id} value={person.employee_public_id}>
          {person.employee_number} · {person.display_name}
        </option>
      ))}
    </select>
  );
}

function Empty({ children }: { children: string }) {
  return <div className={styles.empty}>{children}</div>;
}

export function PeopleOrganizationClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("people");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [importResults, setImportResults] = useState<ImportResultRow[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setOverview(await api<Overview>("overview"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "People and organization could not be loaded.");
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

  const filteredPeople = useMemo(() => {
    if (!overview) return [];
    const normalized = query.trim().toLowerCase();
    if (!normalized) return overview.people;
    return overview.people.filter((person) =>
      [person.display_name, person.email, person.employee_number, person.job_title]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [overview, query]);

  async function execute(action: () => Promise<void>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(success);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The operation could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  function submitDepartment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    void execute(
      async () => {
        await api("departments", {
          method: "POST",
          body: JSON.stringify({
            code: formValue(form, "code"),
            name: formValue(form, "name"),
            parent_public_id: formValue(form, "parent_public_id") || null,
            location_public_id: formValue(form, "location_public_id") || null,
            cost_center_code: formValue(form, "cost_center_code"),
          }),
        });
        element.reset();
      },
      "Department created.",
    );
  }

  function submitDesignation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    void execute(
      async () => {
        await api("designations", {
          method: "POST",
          body: JSON.stringify({
            code: formValue(form, "code"),
            name: formValue(form, "name"),
            level_code: formValue(form, "level_code"),
            description: formValue(form, "description"),
          }),
        });
        element.reset();
      },
      "Designation created.",
    );
  }

  function submitCalendar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    const workingDays = formValue(form, "working_days")
      .split(/[\s,]+/)
      .filter(Boolean)
      .map(Number);
    void execute(
      async () => {
        await api("work-calendars", {
          method: "POST",
          body: JSON.stringify({
            code: formValue(form, "code"),
            name: formValue(form, "name"),
            timezone: formValue(form, "timezone"),
            working_days: workingDays,
            standard_hours_per_day: formValue(form, "standard_hours_per_day"),
          }),
        });
        element.reset();
      },
      "Work calendar created.",
    );
  }

  function submitProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    const employeeId = formValue(form, "employee_public_id");
    void execute(
      async () => {
        await api(`people/${employeeId}/profile`, {
          method: "PATCH",
          body: JSON.stringify({
            job_title: formValue(form, "job_title"),
            department_public_id: formValue(form, "department_public_id") || null,
            designation_public_id: formValue(form, "designation_public_id") || null,
            work_calendar_public_id: formValue(form, "work_calendar_public_id") || null,
            employment_type_code: formValue(form, "employment_type_code"),
            worker_category_code: formValue(form, "worker_category_code"),
            mobile: formValue(form, "mobile"),
            status_code: formValue(form, "status_code"),
            probation_end: formValue(form, "probation_end") || null,
            confirmation_date: formValue(form, "confirmation_date") || null,
          }),
        });
        element.reset();
      },
      "Employee profile updated.",
    );
  }

  function submitManager(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    const employeeId = formValue(form, "employee_public_id");
    void execute(
      async () => {
        await api(`people/${employeeId}/manager`, {
          method: "POST",
          body: JSON.stringify({
            manager_public_id: formValue(form, "manager_public_id"),
            effective_from: formValue(form, "effective_from"),
          }),
        });
        element.reset();
      },
      "Reporting manager assigned.",
    );
  }

  function submitAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    void execute(
      async () => {
        await api("assignments", {
          method: "POST",
          body: JSON.stringify({
            employee_public_id: formValue(form, "employee_public_id"),
            assignment_type_code: formValue(form, "assignment_type_code"),
            project_code: formValue(form, "project_code"),
            site_code: formValue(form, "site_code"),
            location_public_id: formValue(form, "location_public_id") || null,
            work_package_code: formValue(form, "work_package_code"),
            allocation_percent: formValue(form, "allocation_percent"),
            effective_from: formValue(form, "effective_from"),
            effective_to: formValue(form, "effective_to") || null,
            is_primary: form.get("is_primary") === "on",
          }),
        });
        element.reset();
      },
      "Operating assignment created.",
    );
  }

  function submitLeaveType(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    void execute(
      async () => {
        await api("leave-types", {
          method: "POST",
          body: JSON.stringify({
            code: formValue(form, "code"),
            name: formValue(form, "name"),
            unit_code: formValue(form, "unit_code"),
            requires_approval: form.get("requires_approval") === "on",
            is_paid: form.get("is_paid") === "on",
            annual_entitlement: formValue(form, "annual_entitlement") || null,
          }),
        });
        element.reset();
      },
      "Leave type created.",
    );
  }

  function submitLeave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    void execute(
      async () => {
        await api("leave-requests", {
          method: "POST",
          body: JSON.stringify({
            employee_public_id: formValue(form, "employee_public_id"),
            leave_type_public_id: formValue(form, "leave_type_public_id"),
            start_date: formValue(form, "start_date"),
            end_date: formValue(form, "end_date"),
            quantity: formValue(form, "quantity"),
            reason: formValue(form, "reason"),
          }),
        });
        element.reset();
      },
      "Leave request submitted.",
    );
  }

  function reviewLeave(item: LeaveRequest, decisionCode: "APPROVED" | "REJECTED") {
    const note = window.prompt(`${decisionCode === "APPROVED" ? "Approval" : "Rejection"} note`, "") ?? "";
    void execute(
      async () => {
        await api(`leave-requests/${item.public_id}/review`, {
          method: "POST",
          body: JSON.stringify({
            decision_code: decisionCode,
            review_note: note,
            expected_version: item.version,
          }),
        });
      },
      `Leave request ${decisionCode.toLowerCase()}.`,
    );
  }

  function submitAttendance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    void execute(
      async () => {
        await api("attendance", {
          method: "POST",
          body: JSON.stringify({
            employee_public_id: formValue(form, "employee_public_id"),
            work_date: formValue(form, "work_date"),
            status_code: formValue(form, "status_code"),
            hours_worked: formValue(form, "hours_worked"),
            source_code: "MANUAL",
            notes: formValue(form, "notes"),
          }),
        });
        element.reset();
      },
      "Attendance recorded.",
    );
  }

  function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    void execute(
      async () => {
        const rows = JSON.parse(formValue(form, "rows_json")) as unknown;
        if (!Array.isArray(rows)) throw new Error("Import JSON must be an array of people rows.");
        const result = await api<{ results: ImportResultRow[] }>(
          "imports",
          {
            method: "POST",
            body: JSON.stringify({ source_name: formValue(form, "source_name"), rows }),
          },
        );
        setImportResults(result.results);
        const tokens = result.results.filter((row) => row.acceptance_token);
        if (tokens.length) {
          setNotice(
            `Import completed. ${tokens.length} invitation token(s) were returned once. Copy the API response from browser developer tools before leaving this page.`,
          );
        }
        element.reset();
      },
      "People import completed.",
    );
  }

  if (loading && !overview) {
    return <main className={styles.page}><div className={styles.loading}>Loading people and organization…</div></main>;
  }
  if (!overview) {
    return (
      <main className={styles.page}>
        <section className={styles.panel}>
          <p className={styles.kicker}>People foundation unavailable</p>
          <h1>People & organization could not be opened.</h1>
          <p>{error || "Verify Phase 29 migrations, backend restart and peopleorg.view permission."}</p>
          <button className={styles.primary} type="button" onClick={() => void load()}>Retry workspace</button>
        </section>
      </main>
    );
  }

  const tabs: Array<{ id: Tab; label: string }> = [
    { id: "people", label: "People directory" },
    { id: "structure", label: "Organization structure" },
    { id: "assignments", label: "Assignments" },
    { id: "leave", label: "Leave" },
    { id: "attendance", label: "Attendance" },
    { id: "import", label: "Bulk import" },
  ];

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div>
          <p className={styles.kicker}>MPSqre Build360 · Phase 29</p>
          <h1>People & organization</h1>
          <p>
            Operate departments, designations, reporting lines, workforce allocations, leave and attendance for {overview.company.display_name}.
          </p>
        </div>
        <span className={styles.badge}>Phase 29 active</span>
      </section>

      <section className={styles.metrics}>
        <article><span>Total employees</span><strong>{overview.summary.employee_count}</strong></article>
        <article><span>Active profiles</span><strong>{overview.summary.active_profile_count}</strong></article>
        <article><span>Departments</span><strong>{overview.summary.department_count}</strong></article>
        <article><span>Unassigned</span><strong>{overview.summary.unassigned_employee_count}</strong></article>
        <article><span>Pending leave</span><strong>{overview.summary.pending_leave_count}</strong></article>
        <article><span>Attendance today</span><strong>{overview.summary.attendance_recorded_today}</strong></article>
      </section>

      <nav className={styles.tabs} aria-label="People and organization sections">
        {tabs.map((item) => (
          <button
            key={item.id}
            className={tab === item.id ? styles.activeTab : ""}
            type="button"
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      {error ? <p className={styles.error}>{error}</p> : null}
      {notice ? <p className={styles.notice}>{notice}</p> : null}

      {tab === "people" ? (
        <div className={styles.twoColumn}>
          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><h2>Employee setup</h2><p>Complete the organization profile created through Phase 28 onboarding.</p></div></div>
            <form onSubmit={submitProfile} className={styles.formGrid}>
              <label className={styles.full}>Person<EmployeeSelect people={overview.people} /></label>
              <label>Job title<input name="job_title" required /></label>
              <label>Employment type<input name="employment_type_code" defaultValue="FULL_TIME" required /></label>
              <label>Department<select name="department_public_id" defaultValue=""><option value="">Unassigned</option>{overview.departments.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></label>
              <label>Designation<select name="designation_public_id" defaultValue=""><option value="">Unassigned</option>{overview.designations.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></label>
              <label>Work calendar<select name="work_calendar_public_id" defaultValue=""><option value="">Unassigned</option>{overview.work_calendars.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></label>
              <label>Worker category<input name="worker_category_code" /></label>
              <label>Mobile<input name="mobile" /></label>
              <label>Status<input name="status_code" defaultValue="ACTIVE" required /></label>
              <label>Probation end<input name="probation_end" type="date" /></label>
              <label>Confirmation date<input name="confirmation_date" type="date" /></label>
              <div className={`${styles.actions} ${styles.full}`}><button className={styles.primary} disabled={busy}>Save employee profile</button></div>
            </form>
            <hr />
            <h3>Reporting manager</h3>
            <form onSubmit={submitManager} className={styles.formGrid}>
              <label>Employee<EmployeeSelect people={overview.people} /></label>
              <label>Manager<EmployeeSelect people={overview.people} name="manager_public_id" /></label>
              <label>Effective from<input name="effective_from" type="date" defaultValue={today()} required /></label>
              <div className={styles.actions}><button className={styles.secondary} disabled={busy}>Assign manager</button></div>
            </form>
          </section>
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <div><h2>People directory</h2><p>Search accepted employees and review their organization placement.</p></div>
              <input className={styles.search} value={query} onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Search name, email or number" />
            </div>
            <div className={styles.tableWrap}><table><thead><tr><th>Person</th><th>Organization</th><th>Manager</th><th>Status</th></tr></thead><tbody>
              {filteredPeople.map((person) => <tr key={person.employee_public_id}><td><strong>{person.display_name}</strong><small>{person.employee_number} · {person.email}</small><small>{person.job_title}</small></td><td>{person.profile?.department_name || "No department"}<small>{person.profile?.designation_name || "No designation"}</small></td><td>{person.manager?.display_name || "Not assigned"}<small>{person.manager?.employee_number || ""}</small></td><td><span className={styles.pill}>{person.profile?.status_code || "PROFILE PENDING"}</span></td></tr>)}
            </tbody></table></div>
          </section>
        </div>
      ) : null}

      {tab === "structure" ? (
        <div className={styles.threeColumn}>
          <section className={styles.panel}><h2>Create department</h2><form onSubmit={submitDepartment} className={styles.formStack}><label>Code<input name="code" required /></label><label>Name<input name="name" required /></label><label>Parent<select name="parent_public_id" defaultValue=""><option value="">Top level</option>{overview.departments.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></label><label>Location<select name="location_public_id" defaultValue=""><option value="">No location</option>{overview.locations.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></label><label>Cost centre<input name="cost_center_code" /></label><button className={styles.primary} disabled={busy}>Create department</button></form><div className={styles.list}>{overview.departments.map((item) => <article key={item.public_id}><strong>{item.name}</strong><small>{item.code}{item.parent_name ? ` · ${item.parent_name}` : ""}</small></article>)}</div></section>
          <section className={styles.panel}><h2>Create designation</h2><form onSubmit={submitDesignation} className={styles.formStack}><label>Code<input name="code" required /></label><label>Name<input name="name" required /></label><label>Level<input name="level_code" /></label><label>Description<textarea name="description" /></label><button className={styles.primary} disabled={busy}>Create designation</button></form><div className={styles.list}>{overview.designations.map((item) => <article key={item.public_id}><strong>{item.name}</strong><small>{item.code}{item.level_code ? ` · ${item.level_code}` : ""}</small></article>)}</div></section>
          <section className={styles.panel}><h2>Create work calendar</h2><form onSubmit={submitCalendar} className={styles.formStack}><label>Code<input name="code" required /></label><label>Name<input name="name" required /></label><label>Timezone<input name="timezone" defaultValue={overview.company.timezone} required /></label><label>ISO working days<input name="working_days" defaultValue="1,2,3,4,5,6" required /></label><label>Hours per day<input name="standard_hours_per_day" type="number" step="0.25" defaultValue="8.00" required /></label><button className={styles.primary} disabled={busy}>Create calendar</button></form><div className={styles.list}>{overview.work_calendars.map((item) => <article key={item.public_id}><strong>{item.name}</strong><small>{item.code} · {item.standard_hours_per_day}h · {item.working_days.join(",")}</small></article>)}</div></section>
        </div>
      ) : null}

      {tab === "assignments" ? (
        <div className={styles.twoColumn}>
          <section className={styles.panel}><h2>Assign person to operating scope</h2><p>Project and site codes are provider-neutral references until Phase 30 promotes them into governed project records.</p><form onSubmit={submitAssignment} className={styles.formGrid}><label className={styles.full}>Person<EmployeeSelect people={overview.people} /></label><label>Assignment type<input name="assignment_type_code" defaultValue="PRIMARY" required /></label><label>Allocation %<input name="allocation_percent" type="number" min="0.01" max="100" step="0.01" defaultValue="100" required /></label><label>Project code<input name="project_code" /></label><label>Site code<input name="site_code" /></label><label>Location<select name="location_public_id" defaultValue=""><option value="">No location</option>{overview.locations.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></label><label>Work package<input name="work_package_code" /></label><label>Effective from<input name="effective_from" type="date" defaultValue={today()} required /></label><label>Effective to<input name="effective_to" type="date" /></label><label className={styles.checkbox}><input name="is_primary" type="checkbox" /> Primary assignment</label><div className={`${styles.actions} ${styles.full}`}><button className={styles.primary} disabled={busy}>Create assignment</button></div></form></section>
          <section className={styles.panel}><h2>Active assignments</h2>{overview.assignments.length ? <div className={styles.tableWrap}><table><thead><tr><th>Person</th><th>Scope</th><th>Allocation</th><th>Effective</th></tr></thead><tbody>{overview.assignments.map((item) => <tr key={item.public_id}><td><strong>{item.employee_name}</strong><small>{item.employee_number}</small></td><td>{item.project_code || "No project"}<small>{[item.site_code, item.location_name, item.work_package_code].filter(Boolean).join(" · ")}</small></td><td>{item.allocation_percent}%{item.is_primary ? <small>Primary</small> : null}</td><td>{item.effective_from}<small>{item.effective_to || "Open-ended"}</small></td></tr>)}</tbody></table></div> : <Empty>No active assignments.</Empty>}</section>
        </div>
      ) : null}

      {tab === "leave" ? (
        <div className={styles.twoColumn}>
          <div><section className={styles.panel}><h2>Configure leave type</h2><form onSubmit={submitLeaveType} className={styles.formGrid}><label>Code<input name="code" required /></label><label>Name<input name="name" required /></label><label>Unit<input name="unit_code" defaultValue="DAYS" required /></label><label>Annual entitlement<input name="annual_entitlement" type="number" step="0.5" /></label><label className={styles.checkbox}><input name="requires_approval" type="checkbox" defaultChecked /> Requires approval</label><label className={styles.checkbox}><input name="is_paid" type="checkbox" defaultChecked /> Paid leave</label><div className={`${styles.actions} ${styles.full}`}><button className={styles.primary} disabled={busy}>Create leave type</button></div></form></section><section className={styles.panel}><h2>Submit leave request</h2><form onSubmit={submitLeave} className={styles.formGrid}><label className={styles.full}>Person<EmployeeSelect people={overview.people} /></label><label>Leave type<select name="leave_type_public_id" required defaultValue=""><option value="" disabled>Select leave type</option>{overview.leave_types.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></label><label>Quantity<input name="quantity" type="number" step="0.5" required /></label><label>Start<input name="start_date" type="date" required /></label><label>End<input name="end_date" type="date" required /></label><label className={styles.full}>Reason<textarea name="reason" /></label><div className={`${styles.actions} ${styles.full}`}><button className={styles.primary} disabled={busy}>Submit request</button></div></form></section></div>
          <section className={styles.panel}><h2>Leave approval inbox</h2>{overview.leave_requests.length ? <div className={styles.tableWrap}><table><thead><tr><th>Person</th><th>Leave</th><th>Status</th><th>Decision</th></tr></thead><tbody>{overview.leave_requests.map((item) => <tr key={item.public_id}><td><strong>{item.employee_name}</strong><small>{item.employee_number}</small></td><td>{item.leave_type_name}<small>{item.start_date} → {item.end_date} · {item.quantity}</small></td><td><span className={styles.pill}>{item.status_code}</span></td><td>{item.status_code === "SUBMITTED" ? <div className={styles.rowActions}><button className={styles.approve} disabled={busy} onClick={() => reviewLeave(item, "APPROVED")}>Approve</button><button className={styles.reject} disabled={busy} onClick={() => reviewLeave(item, "REJECTED")}>Reject</button></div> : item.review_note || "Completed"}</td></tr>)}</tbody></table></div> : <Empty>No leave requests.</Empty>}</section>
        </div>
      ) : null}

      {tab === "attendance" ? (
        <div className={styles.twoColumn}>
          <section className={styles.panel}><h2>Record daily attendance</h2><form onSubmit={submitAttendance} className={styles.formGrid}><label className={styles.full}>Person<EmployeeSelect people={overview.people} /></label><label>Date<input name="work_date" type="date" defaultValue={today()} required /></label><label>Status<input name="status_code" defaultValue="PRESENT" required /></label><label>Hours worked<input name="hours_worked" type="number" min="0" max="24" step="0.25" defaultValue="8" required /></label><label className={styles.full}>Notes<textarea name="notes" /></label><div className={`${styles.actions} ${styles.full}`}><button className={styles.primary} disabled={busy}>Save attendance</button></div></form></section>
          <section className={styles.panel}><h2>Recent attendance</h2>{overview.attendance_entries.length ? <div className={styles.tableWrap}><table><thead><tr><th>Person</th><th>Date</th><th>Status</th><th>Hours</th></tr></thead><tbody>{overview.attendance_entries.map((item) => <tr key={item.public_id}><td><strong>{item.employee_name}</strong><small>{item.employee_number}</small></td><td>{item.work_date}</td><td>{item.status_code}<small>{item.source_code}</small></td><td>{item.hours_worked}</td></tr>)}</tbody></table></div> : <Empty>No attendance recorded.</Empty>}</section>
        </div>
      ) : null}

      {tab === "import" ? (
        <div className={styles.twoColumn}>
          <section className={styles.panel}><h2>Bulk people import</h2><p>Paste a JSON array. Existing accepted employees are enriched; new people receive one-time invitation tokens in the response.</p><form onSubmit={submitImport} className={styles.formStack}><label>Source name<input name="source_name" defaultValue="people-import.json" required /></label><label>Rows JSON<textarea name="rows_json" className={styles.json} defaultValue={'[\n  {\n    "display_name": "Example Engineer",\n    "email": "engineer@example.com",\n    "employee_number": "EMP-002",\n    "job_title": "Site Engineer",\n    "role_public_ids": ["ROLE_UUID_FROM_ACCESS_CONTROL"],\n    "department_code": "PROJECT_DELIVERY",\n    "designation_code": "SITE_ENGINEER"\n  }\n]'} required /></label><button className={styles.primary} disabled={busy}>Run governed import</button></form>{importResults.length ? <div className={styles.importResults}><h3>One-time import results</h3>{importResults.map((item) => <article key={`${item.row}-${item.status}`}><strong>Row {item.row}: {item.status}</strong>{item.acceptance_token ? <code>{`${window.location.origin}/accept-invitation?token=${encodeURIComponent(item.acceptance_token)}`}</code> : null}{item.message ? <small>{item.message}</small> : null}</article>)}</div> : null}</section>
          <section className={styles.panel}><h2>Import history</h2>{overview.import_jobs.length ? <div className={styles.list}>{overview.import_jobs.map((item) => <article key={item.public_id}><strong>{item.source_name}</strong><small>{item.status_code} · {item.success_rows}/{item.total_rows} successful · {new Date(item.created_at).toLocaleString()}</small></article>)}</div> : <Empty>No import jobs.</Empty>}</section>
        </div>
      ) : null}
    </main>
  );
}
