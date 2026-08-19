import Link from "next/link";

const JOURNEY = [
  {
    no: "01",
    title: "Save customer contact",
    owner: "CRM executive",
    action: "CRM → Contacts → Save contact",
    detail: "Name, phone/email, customer link and consent are stored in the existing protected CRM contact record.",
    href: "/crm?tab=contacts",
    cta: "Open contacts",
  },
  {
    no: "02",
    title: "Dial and record the call",
    owner: "CRM executive",
    action: "CRM → Leads/Contacts → Dial now",
    detail: "Build360 reveals the protected number only with permission and an audit reason, then opens the device dialer. After the call, save the outcome/follow-up as a CRM activity.",
    href: "/crm?tab=leads",
    cta: "Open CRM calling",
  },
  {
    no: "03",
    title: "Qualify the requirement",
    owner: "CRM / sales",
    action: "Lead → stage movement → Convert",
    detail: "Capture project need, expected value and follow-up. Qualified leads convert once into the existing customer + opportunity flow.",
    href: "/crm?tab=pipeline",
    cta: "Open pipeline",
  },
  {
    no: "04",
    title: "Send to Design & Estimation",
    owner: "Sales manager / preconstruction",
    action: "Opportunity → Send to Design & Estimation",
    detail: "Build360 creates or reuses exactly one preconstruction Project workspace for the opportunity. That same workspace holds architect design and detailed estimation before final award; no duplicate journey database is created.",
    href: "/crm?tab=pipeline",
    cta: "Open opportunity pipeline",
  },
  {
    no: "05",
    title: "Architect uploads design",
    owner: "Architect / designer",
    action: "Delivery → Design → Register document → Upload revision",
    detail: "Each design revision is uploaded through governed file storage and linked to the existing immutable Design Version record. Review/approval/issue remain controlled transitions.",
    href: "/delivery?tab=design",
    cta: "Open design",
  },
  {
    no: "06",
    title: "Estimator prepares BOQ",
    owner: "Estimator",
    action: "Delivery → Estimation → New estimate → BOQ",
    detail: "Estimate versions and BOQ lines stay in the existing Estimation domain. Freeze the approved baseline only after the configured approval path is complete.",
    href: "/delivery?tab=estimation",
    cta: "Open estimation",
  },
  {
    no: "07",
    title: "Share approved estimate",
    owner: "Estimator / commercial",
    action: "Estimation → Freeze approved baseline → Share approved estimate",
    detail: "Choose an active client portal grant. Only the frozen approved estimate version is shareable; the client sees that estimate and its BOQ inside their recipient-scoped portal.",
    href: "/delivery?tab=estimation",
    cta: "Share estimate",
  },
  {
    no: "08",
    title: "Customer decision / award",
    owner: "Sales / commercial",
    action: "Client decision → Opportunity Won",
    detail: "Record the commercial decision in CRM. When awarded, mark the opportunity Won. The existing preconstruction Project is reused and continues into execution instead of creating another project.",
    href: "/crm?tab=pipeline",
    cta: "Update opportunity",
  },
  {
    no: "09",
    title: "Execute and hand over",
    owner: "Project team",
    action: "Project & Work → execution → QA/QC → handover",
    detail: "Tasks, evidence, progress, procurement, finance, completion, warranty and handover remain attached to the controlled project lifecycle.",
    href: "/platform/project-work",
    cta: "Open project work",
  },
] as const;

const RELEASE = [
  ["Stabilization", "No open critical regressions; health, migrations, API and frontend checks recorded."],
  ["UAT", "Real users complete CRM → design → estimate → project scenarios with no release-blocking failures."],
  ["Backup & restore", "A production-equivalent backup exists and a restore test has succeeded."],
  ["Security", "Tenant isolation, object authorization, secrets, uploads, sessions and audit controls are verified."],
  ["Permissions", "Role matrix passes positive and negative tests; maker-checker rules are respected."],
  ["Deployment", "All required release gates are passed, evidence is attached, rollback/smoke checks are ready."],
] as const;

export default function OperationalFlowPage() {
  return (
    <main className="min-h-screen px-4 py-6 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1500px] space-y-6">
        <header className="rounded-3xl border border-[var(--border)] bg-white p-6 shadow-sm sm:p-8">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">Phase 45 stabilization · Start here</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Build360 operational flow</h1>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-[var(--muted)]">
            User-ku software open pannumbodhu “next enna?” clear-ah irukkanum. This page connects the existing CRM, Project, Design, Estimation, Portal and Release Readiness domains without creating duplicate records.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white" href="/crm?tab=contacts">Start with customer</Link>
            <Link className="rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-semibold" href="/platform/release-readiness">Production gates</Link>
            <Link className="rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-semibold" href="/platform/stability-operations">Stability dashboard</Link>
          </div>
        </header>

        <section className="grid gap-4 lg:grid-cols-2">
          {JOURNEY.map((step) => (
            <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={step.no}>
              <div className="flex items-start gap-4">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-emerald-950 text-sm font-bold text-white">{step.no}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div><h2 className="text-lg font-semibold">{step.title}</h2><p className="mt-1 text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">{step.owner}</p></div>
                  </div>
                  <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-sm font-semibold">{step.action}</p>
                  <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{step.detail}</p>
                  <Link className="mt-4 inline-flex rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold hover:bg-slate-50" href={step.href}>{step.cta} →</Link>
                </div>
              </div>
            </article>
          ))}
        </section>

        <section className="rounded-3xl border border-[var(--border)] bg-white p-6 shadow-sm sm:p-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div><p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">Production governance</p><h2 className="mt-2 text-2xl font-semibold">6 stabilization control areas — release readiness enforces the detailed gates</h2></div>
            <Link className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white" href="/platform/release-readiness">Open release readiness</Link>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {RELEASE.map(([name, description], index) => <article className="rounded-2xl border border-[var(--border)] p-4" key={name}><p className="text-xs font-bold text-[var(--brand)]">GATE {index + 1}</p><h3 className="mt-1 font-semibold">{name}</h3><p className="mt-2 text-sm leading-6 text-[var(--muted)]">{description}</p></article>)}
          </div>
        </section>
      </div>
    </main>
  );
}
