"use client";

import { FormEvent, useMemo, useState } from "react";

type Member = { public_id: string; display_name: string; email: string };
type Control = {
  public_id: string;
  code: string;
  title: string;
  domain: string;
  severity: string;
  status: string;
  version: number;
};
type Framework = {
  public_id: string;
  code: string;
  name: string;
  framework_type: string;
  jurisdiction: string;
  version_label: string;
  status: string;
  control_count: number;
  controls: Control[];
};
type Evaluation = {
  public_id: string;
  control: Control;
  result: string;
  evidence_summary: string;
  evidence_reference: string;
  remediation_due_at: string | null;
  version: number;
};
type Assessment = {
  public_id: string;
  assessment_code: string;
  assessment_type: string;
  scope: string;
  period_start: string;
  period_end: string;
  status: string;
  framework: { public_id: string; code: string; name: string; version_label: string };
  assessor: Member;
  reviewer: Member | null;
  score_percent: string;
  evidence_sha256: string;
  evaluations: Evaluation[];
  decision_reason: string;
  version: number;
};
type Risk = {
  public_id: string;
  risk_code: string;
  title: string;
  category: string;
  likelihood: number;
  impact: number;
  score: number;
  treatment: string;
  treatment_plan: string;
  status: string;
  owner: Member;
  due_at: string | null;
  version: number;
};
type Exception = {
  public_id: string;
  exception_code: string;
  title: string;
  risk_rating: string;
  status: string;
  justification: string;
  compensating_controls: string;
  expires_at: string;
  requester: Member;
  reviewer: Member | null;
  decision_reason: string;
  version: number;
};
type AccessItem = {
  public_id: string;
  membership: Member;
  role_code: string;
  role_name: string;
  permission_count: number;
  decision: string;
  reason: string;
  version: number;
};
type AccessReview = {
  public_id: string;
  campaign_code: string;
  name: string;
  scope: string;
  status: string;
  owner: Member;
  reviewer: Member | null;
  due_at: string;
  items: AccessItem[];
  version: number;
};

export type CompliancePortfolio = {
  current_membership_public_id: string;
  summary: {
    published_frameworks: number;
    latest_assessment_score: string | null;
    open_risks: number;
    high_risks: number;
    active_exceptions: number;
    pending_access_reviews: number;
  };
  frameworks: Framework[];
  assessments: Assessment[];
  risks: Risk[];
  exceptions: Exception[];
  access_reviews: AccessReview[];
};

type Tab = "frameworks" | "assessments" | "risks" | "exceptions" | "access";

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function Status({ value }: Readonly<{ value: string }>) {
  const positive = ["published", "compliant", "approved", "closed", "retain"].includes(value);
  const negative = ["non_compliant", "rejected", "revoked", "expired", "remove"].includes(value);
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${
        positive
          ? "bg-emerald-100 text-emerald-900"
          : negative
            ? "bg-red-100 text-red-800"
            : "bg-amber-100 text-amber-900"
      }`}
    >
      {label(value)}
    </span>
  );
}

function Field({ children }: Readonly<{ children: React.ReactNode }>) {
  return <div className="grid gap-1.5">{children}</div>;
}

const inputClass =
  "w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-700";

export function ComplianceWorkspace({ initialData }: Readonly<{ initialData: CompliancePortfolio }>) {
  const [data, setData] = useState(initialData);
  const [tab, setTab] = useState<Tab>("frameworks");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [frameworkId, setFrameworkId] = useState(initialData.frameworks[0]?.public_id ?? "");

  const activeFrameworks = useMemo(
    () => data.frameworks.filter((item) => item.status === "published"),
    [data.frameworks],
  );

  async function refresh() {
    const response = await fetch("/api/compliance/portfolio", { cache: "no-store" });
    if (response.ok) setData((await response.json()) as CompliancePortfolio);
  }

  async function post(path: string, body: Record<string, unknown>, key: string) {
    setBusy(key);
    setMessage(null);
    const response = await fetch(`/api/compliance/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = (await response.json().catch(() => ({}))) as {
      message?: string;
      detail?: string;
      non_field_errors?: string[];
    };
    if (!response.ok) {
      setMessage(
        result.message ?? result.detail ?? result.non_field_errors?.join(" ") ?? "The action failed.",
      );
    } else {
      setMessage("Action completed successfully.");
      await refresh();
    }
    setBusy(null);
  }

  async function createAssessment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await post(
      "assessments",
      {
        framework_public_id: String(form.get("framework")),
        assessment_code: String(form.get("code")),
        assessment_type: String(form.get("type")),
        scope: String(form.get("scope")),
        period_start: String(form.get("period_start")),
        period_end: String(form.get("period_end")),
        assessor_membership_public_id: data.current_membership_public_id,
      },
      "create-assessment",
    );
    event.currentTarget.reset();
  }

  async function createRisk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await post(
      "risks",
      {
        risk_code: String(form.get("code")),
        title: String(form.get("title")),
        description: String(form.get("description")),
        category: String(form.get("category")),
        likelihood: Number(form.get("likelihood")),
        impact: Number(form.get("impact")),
        treatment: String(form.get("treatment")),
        treatment_plan: String(form.get("plan")),
        owner_membership_public_id: data.current_membership_public_id,
        due_at: form.get("due_at") ? new Date(String(form.get("due_at"))).toISOString() : null,
      },
      "create-risk",
    );
    event.currentTarget.reset();
  }

  async function createException(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await post(
      "exceptions",
      {
        exception_code: String(form.get("code")),
        control_public_id: form.get("control") ? String(form.get("control")) : null,
        title: String(form.get("title")),
        justification: String(form.get("justification")),
        compensating_controls: String(form.get("compensating_controls")),
        risk_rating: String(form.get("risk_rating")),
        expires_at: new Date(String(form.get("expires_at"))).toISOString(),
      },
      "create-exception",
    );
    event.currentTarget.reset();
  }

  async function createAccessReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await post(
      "access-reviews",
      {
        campaign_code: String(form.get("code")),
        name: String(form.get("name")),
        scope: String(form.get("scope")),
        owner_membership_public_id: data.current_membership_public_id,
        due_at: new Date(String(form.get("due_at"))).toISOString(),
      },
      "create-access-review",
    );
    event.currentTarget.reset();
  }

  const controls = activeFrameworks.flatMap((framework) => framework.controls);

  return (
    <main className="min-h-screen px-4 py-6 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-7xl">
        <header className="border-b border-[var(--border)] pb-6">
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-[var(--brand)]">
            MPSqre Build360 · Security and Compliance
          </p>
          <div className="mt-3 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
                Security posture, risk and assurance
              </h1>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Evidence-backed controls · maker-checker reviews · no certification claims
              </p>
            </div>
            <span className="w-fit rounded-full bg-emerald-950 px-4 py-2 text-sm font-semibold text-white">
              Phase 17 active
            </span>
          </div>
        </header>

        {message ? (
          <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
            {message}
          </div>
        ) : null}

        <section className="grid gap-4 py-6 sm:grid-cols-2 xl:grid-cols-6">
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Published frameworks</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.published_frameworks}</p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Latest score</p>
            <p className="mt-2 text-3xl font-semibold">
              {data.summary.latest_assessment_score ?? "—"}
              {data.summary.latest_assessment_score ? "%" : ""}
            </p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Open risks</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.open_risks}</p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">High risks</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.high_risks}</p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Active exceptions</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.active_exceptions}</p>
          </article>
          <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Pending reviews</p>
            <p className="mt-2 text-3xl font-semibold">{data.summary.pending_access_reviews}</p>
          </article>
        </section>

        <div className="mb-5 flex gap-2 overflow-x-auto pb-1">
          {([
            ["frameworks", "Frameworks"],
            ["assessments", "Assessments"],
            ["risks", "Risk register"],
            ["exceptions", "Exceptions"],
            ["access", "Access reviews"],
          ] as const).map(([key, title]) => (
            <button
              key={key}
              className={`whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-semibold ${
                tab === key
                  ? "bg-emerald-950 text-white"
                  : "border border-[var(--border)] bg-white"
              }`}
              onClick={() => setTab(key)}
              type="button"
            >
              {title}
            </button>
          ))}
        </div>

        {tab === "frameworks" ? (
          <section className="grid gap-5 lg:grid-cols-3">
            {data.frameworks.map((framework) => (
              <article
                className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"
                key={framework.public_id}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-[var(--brand)]">
                      {framework.code} · {framework.version_label}
                    </p>
                    <h2 className="mt-2 text-xl font-semibold">{framework.name}</h2>
                  </div>
                  <Status value={framework.status} />
                </div>
                <p className="mt-3 text-sm text-[var(--muted)]">
                  {label(framework.framework_type)} · {framework.jurisdiction || "Global"} · {framework.control_count} controls
                </p>
                <div className="mt-4 max-h-72 space-y-2 overflow-y-auto">
                  {framework.controls.map((control) => (
                    <div className="rounded-xl bg-slate-50 p-3" key={control.public_id}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold">{control.code}</p>
                        <span className="text-xs font-semibold uppercase text-[var(--muted)]">
                          {control.severity}
                        </span>
                      </div>
                      <p className="mt-1 text-sm">{control.title}</p>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </section>
        ) : null}

        {tab === "assessments" ? (
          <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
            <form className="h-fit rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createAssessment}>
              <h2 className="text-xl font-semibold">Create assessment</h2>
              <div className="mt-4 grid gap-3">
                <Field><label className="text-sm font-medium">Framework</label><select className={inputClass} name="framework" onChange={(event) => setFrameworkId(event.target.value)} required value={frameworkId}>{activeFrameworks.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}</select></Field>
                <Field><label className="text-sm font-medium">Assessment code</label><input className={inputClass} name="code" placeholder="ASSESS-2026-Q3" required /></Field>
                <Field><label className="text-sm font-medium">Type</label><select className={inputClass} name="type"><option value="readiness">Readiness</option><option value="internal">Internal</option><option value="customer">Customer assurance</option><option value="regulatory">Regulatory</option></select></Field>
                <Field><label className="text-sm font-medium">Scope</label><input className={inputClass} name="scope" placeholder="Pilot tenant and application services" required /></Field>
                <Field><label className="text-sm font-medium">Period start</label><input className={inputClass} name="period_start" required type="date" /></Field>
                <Field><label className="text-sm font-medium">Period end</label><input className={inputClass} name="period_end" required type="date" /></Field>
                <button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60" disabled={busy === "create-assessment"} type="submit">Create governed assessment</button>
              </div>
            </form>
            <div className="space-y-5">
              {data.assessments.length ? data.assessments.map((assessment) => (
                <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={assessment.public_id}>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div><p className="text-xs font-bold uppercase tracking-wide text-[var(--brand)]">{assessment.assessment_code}</p><h2 className="mt-1 text-xl font-semibold">{assessment.framework.name}</h2><p className="mt-1 text-sm text-[var(--muted)]">{assessment.scope} · Score {assessment.score_percent}%</p></div>
                    <Status value={assessment.status} />
                  </div>
                  <div className="mt-4 space-y-2">
                    {assessment.evaluations.map((evaluation) => (
                      <div className="flex flex-col gap-3 rounded-xl bg-slate-50 p-3 sm:flex-row sm:items-center sm:justify-between" key={evaluation.public_id}>
                        <div><p className="text-sm font-semibold">{evaluation.control.code} · {evaluation.control.title}</p><p className="mt-1 text-xs text-[var(--muted)]">{evaluation.evidence_reference || "No evidence reference"}</p></div>
                        <div className="flex flex-wrap items-center gap-2"><Status value={evaluation.result} />{["draft", "in_progress"].includes(assessment.status) ? <><button className="rounded-lg border border-emerald-200 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900" onClick={() => { const evidence = window.prompt("Evidence reference", evaluation.evidence_reference || "TEST-EVIDENCE"); if (evidence) void post(`evaluations/${evaluation.public_id}/evaluate`, { result: "compliant", evidence_summary: "Evidence reviewed in the compliance workspace", evidence_reference: evidence, remediation_due_at: null, expected_version: evaluation.version }, `evaluation-${evaluation.public_id}`); }} type="button">Compliant</button><button className="rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-semibold text-red-800" onClick={() => { const due = new Date(Date.now() + 30 * 86400000).toISOString(); void post(`evaluations/${evaluation.public_id}/evaluate`, { result: "non_compliant", evidence_summary: "Remediation is required", evidence_reference: "GAP-REVIEW", remediation_due_at: due, expected_version: evaluation.version }, `evaluation-${evaluation.public_id}`); }} type="button">Gap</button></> : null}</div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {assessment.status === "in_progress" ? <button className="rounded-lg bg-emerald-950 px-4 py-2 text-sm font-semibold text-white" onClick={() => void post(`assessments/${assessment.public_id}/transition`, { target_status: "submitted", expected_version: assessment.version, decision_reason: "" }, `assessment-${assessment.public_id}`)} type="button">Submit assessment</button> : null}
                    {assessment.status === "submitted" ? <><button className="rounded-lg bg-emerald-950 px-4 py-2 text-sm font-semibold text-white" onClick={() => void post(`assessments/${assessment.public_id}/transition`, { target_status: "approved", expected_version: assessment.version, decision_reason: "Independent evidence review completed" }, `assessment-${assessment.public_id}`)} type="button">Approve</button><button className="rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-800" onClick={() => void post(`assessments/${assessment.public_id}/transition`, { target_status: "rejected", expected_version: assessment.version, decision_reason: "Evidence requires correction" }, `assessment-${assessment.public_id}`)} type="button">Reject</button></> : null}
                  </div>
                </article>
              )) : <div className="rounded-2xl border border-[var(--border)] bg-white p-8 text-[var(--muted)]">No compliance assessment has been created.</div>}
            </div>
          </section>
        ) : null}

        {tab === "risks" ? (
          <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
            <form className="h-fit rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createRisk}>
              <h2 className="text-xl font-semibold">Register risk</h2>
              <div className="mt-4 grid gap-3">
                <input className={inputClass} name="code" placeholder="RISK-002" required />
                <input className={inputClass} name="title" placeholder="Risk title" required />
                <textarea className={inputClass} name="description" placeholder="Risk description" />
                <select className={inputClass} name="category"><option value="security">Security</option><option value="privacy">Privacy</option><option value="availability">Availability</option><option value="third_party">Third party</option><option value="compliance">Compliance</option><option value="delivery">Delivery</option></select>
                <div className="grid grid-cols-2 gap-3"><select className={inputClass} name="likelihood">{[1,2,3,4,5].map((value) => <option key={value} value={value}>Likelihood {value}</option>)}</select><select className={inputClass} name="impact">{[1,2,3,4,5].map((value) => <option key={value} value={value}>Impact {value}</option>)}</select></div>
                <select className={inputClass} name="treatment"><option value="mitigate">Mitigate</option><option value="avoid">Avoid</option><option value="transfer">Transfer</option><option value="accept">Accept</option></select>
                <textarea className={inputClass} name="plan" placeholder="Treatment plan or acceptance rationale" required />
                <input className={inputClass} name="due_at" type="datetime-local" />
                <button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" type="submit">Register risk</button>
              </div>
            </form>
            <div className="space-y-3">{data.risks.map((risk) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={risk.public_id}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-wide text-[var(--brand)]">{risk.risk_code} · Score {risk.score}</p><h2 className="mt-1 text-lg font-semibold">{risk.title}</h2><p className="mt-2 text-sm text-[var(--muted)]">{label(risk.category)} · {label(risk.treatment)} · Owner {risk.owner.display_name}</p></div><Status value={risk.status} /></div><p className="mt-3 text-sm">{risk.treatment_plan}</p><div className="mt-4 flex flex-wrap gap-2">{risk.status !== "closed" ? <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" onClick={() => void post(`risks/${risk.public_id}/transition`, { target_status: "treatment", treatment_plan: risk.treatment_plan, expected_version: risk.version }, `risk-${risk.public_id}`)} type="button">Start treatment</button> : null}{risk.status !== "closed" ? <button className="rounded-lg bg-emerald-950 px-3 py-2 text-sm font-semibold text-white" onClick={() => void post(`risks/${risk.public_id}/transition`, { target_status: "closed", treatment_plan: risk.treatment_plan, expected_version: risk.version }, `risk-${risk.public_id}`)} type="button">Close risk</button> : null}</div></article>)}</div>
          </section>
        ) : null}

        {tab === "exceptions" ? (
          <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
            <form className="h-fit rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createException}>
              <h2 className="text-xl font-semibold">Request exception</h2>
              <div className="mt-4 grid gap-3">
                <input className={inputClass} name="code" placeholder="EXC-001" required />
                <input className={inputClass} name="title" placeholder="Exception title" required />
                <select className={inputClass} name="control"><option value="">No specific control</option>{controls.map((control) => <option key={control.public_id} value={control.public_id}>{control.code} · {control.title}</option>)}</select>
                <textarea className={inputClass} name="justification" placeholder="Business justification" required />
                <textarea className={inputClass} name="compensating_controls" placeholder="Compensating controls" required />
                <select className={inputClass} name="risk_rating"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select>
                <input className={inputClass} name="expires_at" required type="datetime-local" />
                <button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" type="submit">Request governed exception</button>
              </div>
            </form>
            <div className="space-y-3">{data.exceptions.map((item) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={item.public_id}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-wide text-[var(--brand)]">{item.exception_code} · {item.risk_rating}</p><h2 className="mt-1 text-lg font-semibold">{item.title}</h2><p className="mt-2 text-sm text-[var(--muted)]">Expires {new Date(item.expires_at).toLocaleString()} · Requester {item.requester.display_name}</p></div><Status value={item.status} /></div><p className="mt-3 text-sm">{item.compensating_controls}</p>{item.status === "requested" ? <div className="mt-4 flex gap-2"><button className="rounded-lg bg-emerald-950 px-3 py-2 text-sm font-semibold text-white" onClick={() => void post(`exceptions/${item.public_id}/decide`, { target_status: "approved", decision_reason: "Compensating controls accepted for the stated expiry period", expected_version: item.version }, `exception-${item.public_id}`)} type="button">Approve</button><button className="rounded-lg border border-red-200 px-3 py-2 text-sm font-semibold text-red-800" onClick={() => void post(`exceptions/${item.public_id}/decide`, { target_status: "rejected", decision_reason: "Risk exceeds approved tolerance", expected_version: item.version }, `exception-${item.public_id}`)} type="button">Reject</button></div> : null}</article>)}</div>
          </section>
        ) : null}

        {tab === "access" ? (
          <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
            <form className="h-fit rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createAccessReview}>
              <h2 className="text-xl font-semibold">Start access review</h2>
              <div className="mt-4 grid gap-3"><input className={inputClass} name="code" placeholder="ACCESS-Q3-2026" required /><input className={inputClass} name="name" placeholder="Quarterly privileged access review" required /><select className={inputClass} name="scope"><option value="all_memberships">All active memberships</option><option value="privileged_roles">Privileged roles</option></select><input className={inputClass} name="due_at" required type="datetime-local" /><button className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" type="submit">Create review campaign</button></div>
            </form>
            <div className="space-y-5">{data.access_reviews.map((campaign) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={campaign.public_id}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-wide text-[var(--brand)]">{campaign.campaign_code}</p><h2 className="mt-1 text-lg font-semibold">{campaign.name}</h2><p className="mt-1 text-sm text-[var(--muted)]">{label(campaign.scope)} · Due {new Date(campaign.due_at).toLocaleString()}</p></div><Status value={campaign.status} /></div><div className="mt-4 space-y-2">{campaign.items.map((item) => <div className="flex flex-col gap-3 rounded-xl bg-slate-50 p-3 sm:flex-row sm:items-center sm:justify-between" key={item.public_id}><div><p className="text-sm font-semibold">{item.membership.display_name} · {item.role_name}</p><p className="mt-1 text-xs text-[var(--muted)]">{item.permission_count} permissions · {item.membership.email}</p></div><div className="flex flex-wrap items-center gap-2"><Status value={item.decision} />{campaign.status === "active" && item.decision === "pending" ? <><button className="rounded-lg border border-emerald-200 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900" onClick={() => void post(`access-review-items/${item.public_id}/decide`, { decision: "retain", reason: "Role remains required for assigned responsibilities", expected_version: item.version }, `access-${item.public_id}`)} type="button">Retain</button><button className="rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-semibold text-red-800" onClick={() => void post(`access-review-items/${item.public_id}/decide`, { decision: "remove", reason: "Access is no longer required", expected_version: item.version }, `access-${item.public_id}`)} type="button">Remove</button></> : null}</div></div>)}</div><div className="mt-4 flex flex-wrap gap-2">{campaign.status === "active" ? <button className="rounded-lg bg-emerald-950 px-4 py-2 text-sm font-semibold text-white" onClick={() => void post(`access-reviews/${campaign.public_id}/transition`, { target_status: "submitted", expected_version: campaign.version }, `campaign-${campaign.public_id}`)} type="button">Submit review</button> : null}{campaign.status === "submitted" ? <button className="rounded-lg bg-emerald-950 px-4 py-2 text-sm font-semibold text-white" onClick={() => void post(`access-reviews/${campaign.public_id}/transition`, { target_status: "approved", expected_version: campaign.version }, `campaign-${campaign.public_id}`)} type="button">Approve review</button> : null}</div></article>)}</div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
