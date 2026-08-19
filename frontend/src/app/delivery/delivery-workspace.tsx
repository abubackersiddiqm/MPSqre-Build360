"use client";

import type { Route } from "next";
import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

export type Stage = {
  public_id: string;
  code: string;
  name: string;
  outcome: string;
  allowed_next_codes: string[];
  allows_baseline: boolean;
};

export type Project = {
  public_id: string;
  code: string;
  name: string;
  description: string;
  stage: Stage;
  available_transitions: Stage[];
  planned_start_date: string | null;
  planned_end_date: string | null;
  currency: string;
  approved_budget: string;
  baseline_version: number;
  version: number;
};

export type DesignDocument = {
  public_id: string;
  project_public_id: string;
  project_code: string;
  document_number: string;
  title: string;
  discipline_code: string;
  document_type_code: string;
  latest_version: {
    public_id: string;
    revision_code: string;
    stage: Stage;
    version: number;
  } | null;
};

export type EstimateVersion = {
  public_id: string;
  version_number: number;
  stage: Stage;
  available_transitions: Stage[];
  subtotal: string;
  tax_total: string;
  grand_total: string;
  baselined_at: string | null;
  version: number;
};

export type Estimate = {
  public_id: string;
  project_public_id: string;
  project_code: string;
  code: string;
  name: string;
  currency: string;
  active_version: EstimateVersion | null;
};

export type ProjectSummary = {
  projects: number;
  tasks: number;
  overdue_tasks: number;
  baselined_projects: number;
  approved_budget: string;
  currency: string;
};

export type DesignSummary = {
  documents: number;
  versions: number;
  issued_versions: number;
  open_issues: number;
  pending_reviews: number;
};

export type EstimationSummary = {
  estimates: number;
  versions: number;
  baselined_versions: number;
  baselined_value: string;
  currency: string;
};

export type PortalGrant = {
  public_id: string;
  user_public_id: string;
  portal_type: string;
  scope_type: string;
  scope_public_id: string | null;
  permission_codes: string[];
  revoked_at: string | null;
};

type Company = {
  public_id: string;
  code: string;
  display_name: string;
  currency: string;
  timezone: string;
};

type Props = {
  company: Company;
  permissions: string[];
  initialProjects: Project[];
  initialDocuments: DesignDocument[];
  initialEstimates: Estimate[];
  initialProjectSummary: ProjectSummary;
  initialDesignSummary: DesignSummary;
  initialEstimationSummary: EstimationSummary;
  initialPortalGrants: PortalGrant[];
  defaultTab?: string;
  initialProject?: string;
};

type ApiError = { message?: string; detail?: string; errors?: unknown };

async function apiRequest<T>(scope: "projects" | "design" | "estimation" | "files" | "portal", path: string, init?: RequestInit) {
  const response = await fetch(`/api/${scope}/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = (await response.json().catch(() => ({}))) as T & ApiError;
  if (!response.ok) {
    throw new Error(body.message ?? body.detail ?? "The operation could not be completed.");
  }
  return body as T;
}


async function sha256Hex(file: File): Promise<string> {
  const bytes = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((value) => value.toString(16).padStart(2, "0")).join("");
}

type UploadGrant = {
  file_public_id: string;
  version_public_id: string;
  upload_url: string;
  upload_headers: Record<string, string>;
  upload_status: string;
};

function money(value: string, currency: string) {
  const amount = Number(value || 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(amount) ? amount : 0);
}

function Pill({ children }: Readonly<{ children: string }>) {
  return (
    <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-900">
      {children}
    </span>
  );
}

export function DeliveryWorkspace({
  company,
  permissions,
  initialProjects,
  initialDocuments,
  initialEstimates,
  initialProjectSummary,
  initialDesignSummary,
  initialEstimationSummary,
  initialPortalGrants,
  defaultTab,
  initialProject = "",
}: Readonly<Props>) {
  const [projects, setProjects] = useState(initialProjects);
  const [documents, setDocuments] = useState(initialDocuments);
  const [estimates, setEstimates] = useState(initialEstimates);
  const [projectSummary, setProjectSummary] = useState(initialProjectSummary);
  const [designSummary, setDesignSummary] = useState(initialDesignSummary);
  const [estimationSummary, setEstimationSummary] = useState(initialEstimationSummary);
  const [tab, setTab] = useState<"projects" | "design" | "estimation">(() => defaultTab === "design" || defaultTab === "estimation" ? defaultTab : "projects");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [showDocumentForm, setShowDocumentForm] = useState(false);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [showEstimateForm, setShowEstimateForm] = useState(false);
  const [boqEstimateId, setBoqEstimateId] = useState<string | null>(null);
  const [shareEstimateId, setShareEstimateId] = useState<string | null>(null);
  const projectOptions = useMemo(() => projects.map((item) => ({ id: item.public_id, label: `${item.code} — ${item.name}` })), [projects]);
  const selectedProject = projects.some((item) => item.public_id === initialProject) ? initialProject : "";
  const selectedProjectRecord = projects.find((item) => item.public_id === selectedProject);
  const clientEstimateGrants = useMemo(
    () => initialPortalGrants.filter((grant) => !grant.revoked_at && grant.portal_type === "client" && grant.permission_codes.includes("portal.estimate.view")),
    [initialPortalGrants],
  );

  async function refresh() {
    const [pSummary, dSummary, eSummary, pList, dList, eList] = await Promise.all([
      apiRequest<ProjectSummary>("projects", "summary"),
      apiRequest<DesignSummary>("design", "summary"),
      apiRequest<EstimationSummary>("estimation", "summary"),
      apiRequest<{ items: Project[] }>("projects", "items?limit=100"),
      apiRequest<{ items: DesignDocument[] }>("design", "documents?limit=100"),
      apiRequest<{ items: Estimate[] }>("estimation", "estimates?limit=100"),
    ]);
    setProjectSummary(pSummary);
    setDesignSummary(dSummary);
    setEstimationSummary(eSummary);
    setProjects(pList.items);
    setDocuments(dList.items);
    setEstimates(eList.items);
  }

  async function run(action: () => Promise<void>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh();
      setNotice(success);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The operation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await apiRequest<Project>("projects", "items", {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          name: form.get("name"),
          description: form.get("description"),
          planned_start_date: form.get("planned_start_date") || null,
          planned_end_date: form.get("planned_end_date") || null,
          approved_budget: form.get("approved_budget") || "0",
          currency: company.currency,
          location: { city: form.get("city") || "" },
        }),
      });
      setShowProjectForm(false);
    }, "Project created with tenant isolation, stage history, audit evidence and outbox event.");
  }

  async function createDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await apiRequest<DesignDocument>("design", "documents", {
        method: "POST",
        body: JSON.stringify({
          project_public_id: form.get("project_public_id"),
          document_number: form.get("document_number"),
          title: form.get("title"),
          discipline_code: form.get("discipline_code"),
          document_type_code: form.get("document_type_code"),
          description: form.get("description"),
        }),
      });
      setShowDocumentForm(false);
    }, "Design document registered. Create immutable revisions through the version API.");
  }


  async function uploadDesignRevision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const fileValue = form.get("design_file");
    if (!(fileValue instanceof File) || !fileValue.size) {
      setError("Choose a design file to upload.");
      return;
    }
    await run(async () => {
      const checksum = await sha256Hex(fileValue);
      const contentType = fileValue.type || "application/pdf";
      const grant = await apiRequest<UploadGrant>("files", "uploads", {
        method: "POST",
        body: JSON.stringify({
          purpose_code: "design.document",
          data_class: "project_confidential",
          original_name: fileValue.name,
          content_type: contentType,
          size_bytes: fileValue.size,
          sha256: checksum,
        }),
      });
      const uploadHeaders = new Headers(grant.upload_headers);
      const uploadResponse = await fetch(grant.upload_url, { method: "PUT", headers: uploadHeaders, body: fileValue });
      if (!uploadResponse.ok) throw new Error(`Object storage upload failed (${uploadResponse.status}). Check storage CORS and credentials.`);
      await apiRequest("files", `uploads/${grant.version_public_id}/finalize`, { method: "POST", body: JSON.stringify({}) });
      await apiRequest("design", `documents/${String(form.get("document_public_id"))}/versions`, {
        method: "POST",
        body: JSON.stringify({
          revision_code: form.get("revision_code"),
          description: form.get("description"),
          file_object_public_id: grant.file_public_id,
          checksum_sha256: checksum,
        }),
      });
      setShowUploadForm(false);
    }, "Design revision uploaded as a governed immutable version. Review/approval/issue transitions remain controlled.");
  }

  async function createEstimate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await apiRequest<Estimate>("estimation", "estimates", {
        method: "POST",
        body: JSON.stringify({
          project_public_id: form.get("project_public_id"),
          code: form.get("code"),
          name: form.get("name"),
          currency: company.currency,
          notes: form.get("notes"),
        }),
      });
      setShowEstimateForm(false);
    }, "Estimate v1 created with a configurable lifecycle and BOQ workspace.");
  }

  async function addBoqItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const estimate = estimates.find((item) => item.public_id === boqEstimateId);
    if (!estimate?.active_version) { setError("Choose an estimate with an active version."); return; }
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await apiRequest("estimation", `versions/${estimate.active_version!.public_id}/items`, {
        method: "POST",
        body: JSON.stringify({
          item_code: form.get("item_code"),
          description: form.get("description"),
          unit_code: form.get("unit_code"),
          quantity: form.get("quantity"),
          rate: form.get("rate"),
          tax_rate_percent: form.get("tax_rate_percent") || "0",
        }),
      });
      setBoqEstimateId(null);
    }, "BOQ line added and estimate totals recalculated in the controlled estimate version.");
  }

  async function shareEstimate(event: FormEvent<HTMLFormElement>, estimate: Estimate) {
    event.preventDefault();
    if (!estimate.active_version?.baselined_at) {
      setError("Only an approved, frozen estimate baseline can be shared with a client.");
      return;
    }
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await apiRequest("portal", "shares", {
        method: "POST",
        body: JSON.stringify({
          grant_public_id: form.get("grant_public_id"),
          entity_type: "estimation.version",
          entity_public_id: estimate.active_version!.public_id,
          access_level: "view",
          expires_at: null,
        }),
      });
      setShareEstimateId(null);
    }, "Approved estimate shared to the selected client portal. The recipient can now view the estimate and BOQ.");
  }

  async function transitionEstimate(estimate: Estimate, target: Stage) {
    if (!estimate.active_version) return;
    await run(async () => {
      await apiRequest("estimation", `versions/${estimate.active_version!.public_id}/transition`, {
        method: "POST",
        body: JSON.stringify({ target_stage_public_id: target.public_id, expected_version: estimate.active_version!.version }),
      });
    }, `${estimate.code} moved to ${target.name}.`);
  }

  async function baselineEstimate(estimate: Estimate) {
    if (!estimate.active_version) return;
    await run(async () => {
      await apiRequest("estimation", `versions/${estimate.active_version!.public_id}/baseline`, {
        method: "POST",
        body: JSON.stringify({ expected_version: estimate.active_version!.version }),
      });
    }, `${estimate.code} approved version frozen as the commercial baseline.`);
  }

  async function transitionProject(project: Project, target: Stage) {
    await run(async () => {
      await apiRequest<Project>("projects", `${project.public_id}/transition`, {
        method: "POST",
        body: JSON.stringify({
          target_stage_public_id: target.public_id,
          expected_version: project.version,
        }),
      });
    }, `${project.code} moved to ${target.name}.`);
  }

  async function baseline(project: Project) {
    await run(async () => {
      await apiRequest("projects", `${project.public_id}/baseline`, {
        method: "POST",
        body: JSON.stringify({ expected_version: project.version }),
      });
    }, `${project.code} baseline ${project.baseline_version + 1} was frozen.`);
  }

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">MPSqre Build360 · Delivery spine</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Projects, design and BOQ</h1>
            <p className="mt-2 text-sm text-[var(--muted)]">{company.display_name} · {company.code} · {company.timezone}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Pill>Phase 5 active</Pill>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/crm">CRM</Link>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/platform">Platform</Link>
          </div>
        </header>

        {(error || notice) && (
          <div className={`mt-5 rounded-xl border p-4 text-sm ${error ? "border-red-200 bg-red-50 text-red-800" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`}>
            {error || notice}
          </div>
        )}

        <section className="grid gap-4 py-7 sm:grid-cols-2 xl:grid-cols-6">
          {[
            ["Projects", projectSummary.projects],
            ["Tasks", projectSummary.tasks],
            ["Design documents", designSummary.documents],
            ["Open design issues", designSummary.open_issues],
            ["Estimates", estimationSummary.estimates],
            ["Baselined value", money(estimationSummary.baselined_value, estimationSummary.currency)],
          ].map(([label, value]) => (
            <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={String(label)}>
              <p className="text-sm text-[var(--muted)]">{label}</p>
              <p className="mt-2 text-2xl font-semibold">{value}</p>
            </article>
          ))}
        </section>

        <nav className="mb-6 flex flex-wrap gap-2" aria-label="Delivery workspace sections">
          {(["projects", "design", "estimation"] as const).map((item) => (
            <button
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === item ? "bg-[var(--brand)] text-white" : "border border-[var(--border)] bg-white"}`}
              key={item}
              onClick={() => setTab(item)}
              type="button"
            >
              {item === "projects" ? "Projects & WBS" : item === "design" ? "Design control" : "Estimation & BOQ"}
            </button>
          ))}
        </nav>

        {selectedProjectRecord ? (
          <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950 sm:flex-row sm:items-center sm:justify-between">
            <div><strong>CRM handoff project:</strong> {selectedProjectRecord.code} · {selectedProjectRecord.name}<p className="mt-1 text-xs text-blue-800">New design documents and estimates will default to this project where applicable.</p></div>
            <Link className="rounded-lg border border-blue-300 bg-white px-3 py-2 text-xs font-semibold" href={`/project360?project=${selectedProjectRecord.public_id}` as Route}>Open Project 360</Link>
          </div>
        ) : null}

        {tab === "projects" && (
          <section className="space-y-5">
            <div className="flex items-center justify-between gap-4">
              <div><h2 className="text-2xl font-semibold">Project portfolio</h2><p className="mt-1 text-sm text-[var(--muted)]">Configurable stages, WBS, tasks and immutable baselines.</p></div>
              {permissions.includes("project.project.manage") && <button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" onClick={() => setShowProjectForm((value) => !value)} type="button">New project</button>}
            </div>
            {showProjectForm && <form className="grid gap-4 rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm md:grid-cols-2" onSubmit={createProject}>
              <label className="text-sm font-medium">Project code<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="code" required /></label>
              <label className="text-sm font-medium">Project name<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="name" required /></label>
              <label className="text-sm font-medium">Planned start<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="planned_start_date" type="date" /></label>
              <label className="text-sm font-medium">Planned finish<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="planned_end_date" type="date" /></label>
              <label className="text-sm font-medium">Approved budget<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" min="0" name="approved_budget" step="0.01" type="number" /></label>
              <label className="text-sm font-medium">City<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="city" /></label>
              <label className="text-sm font-medium md:col-span-2">Description<textarea className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="description" rows={3} /></label>
              <button className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white md:col-span-2" disabled={busy}>Create project</button>
            </form>}
            <div className="grid gap-4 lg:grid-cols-2">
              {projects.map((project) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={project.public_id}>
                <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-[var(--brand)]">{project.code}</p><h3 className="mt-1 text-xl font-semibold">{project.name}</h3></div><Pill>{project.stage.name}</Pill></div>
                <dl className="mt-5 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-[var(--muted)]">Budget</dt><dd className="mt-1 font-semibold">{money(project.approved_budget, project.currency)}</dd></div><div><dt className="text-[var(--muted)]">Baseline</dt><dd className="mt-1 font-semibold">v{project.baseline_version}</dd></div><div><dt className="text-[var(--muted)]">Start</dt><dd className="mt-1">{project.planned_start_date ?? "Not set"}</dd></div><div><dt className="text-[var(--muted)]">Finish</dt><dd className="mt-1">{project.planned_end_date ?? "Not set"}</dd></div></dl>
                <div className="mt-5 flex flex-wrap gap-2">
                  {permissions.includes("project.project.transition") && project.available_transitions.map((target) => <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} key={target.public_id} onClick={() => transitionProject(project, target)} type="button">Move to {target.name}</button>)}
                  {permissions.includes("project.project.baseline") && project.stage.allows_baseline && <button className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white" disabled={busy} onClick={() => baseline(project)} type="button">Freeze baseline</button>}
                </div>
              </article>)}
              {!projects.length && <p className="rounded-2xl border border-dashed border-[var(--border)] p-8 text-sm text-[var(--muted)]">No projects yet. Create the first controlled project.</p>}
            </div>
          </section>
        )}

        {tab === "design" && (
          <section className="space-y-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-2xl font-semibold">Design register</h2><p className="mt-1 text-sm text-[var(--muted)]">Architect flow: register document → upload revision → review → approve → issue.</p></div><div className="flex flex-wrap gap-2">{permissions.includes("design.version.manage") && permissions.includes("files.upload") ? <button className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" onClick={() => setShowUploadForm((value) => !value)} type="button">Upload design revision</button> : null}{permissions.includes("design.document.manage") && <button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" onClick={() => setShowDocumentForm((value) => !value)} type="button">Register document</button>}</div></div>
            {showDocumentForm && <form className="grid gap-4 rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm md:grid-cols-2" onSubmit={createDocument}>
              <label className="text-sm font-medium">Project<select className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" defaultValue={selectedProject} name="project_public_id" required><option value="">Choose project</option>{projectOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
              <label className="text-sm font-medium">Document number<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="document_number" required /></label>
              <label className="text-sm font-medium">Title<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="title" required /></label>
              <label className="text-sm font-medium">Discipline code<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="discipline_code" required /></label>
              <label className="text-sm font-medium">Document type<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="document_type_code" required /></label>
              <label className="text-sm font-medium">Description<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="description" /></label>
              <button className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white md:col-span-2" disabled={busy}>Register document</button>
            </form>}
            {showUploadForm ? <form className="grid gap-4 rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm md:grid-cols-2" onSubmit={uploadDesignRevision}>
              <div className="md:col-span-2 rounded-xl bg-amber-50 p-4 text-sm text-amber-950"><strong>Architect upload location:</strong> choose the registered document, revision code (R0/R1/R2...), and file. Current governed storage accepts PDF, JPG, PNG, WebP, DOCX, XLSX and CSV; CAD/BIM formats should only be enabled after the malware/preview pipeline is configured for those types.</div>
              <label className="text-sm font-medium">Registered document<select className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="document_public_id" required><option value="">Choose document</option>{documents.map((item) => <option key={item.public_id} value={item.public_id}>{item.project_code} · {item.document_number} · {item.title}</option>)}</select></label>
              <label className="text-sm font-medium">Revision code<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="revision_code" placeholder="R0" required /></label>
              <label className="text-sm font-medium md:col-span-2">Design file<input accept=".pdf,.jpg,.jpeg,.png,.webp,.docx,.xlsx,.csv" className="mt-2 w-full rounded-lg border border-[var(--border)] bg-white p-3" name="design_file" required type="file" /></label>
              <label className="text-sm font-medium md:col-span-2">Revision note<textarea className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="description" rows={3} placeholder="What changed in this revision?" /></label>
              <div className="flex justify-end gap-2 md:col-span-2"><button className="rounded-lg border border-[var(--border)] px-4 py-2" onClick={() => setShowUploadForm(false)} type="button">Cancel</button><button className="rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white" disabled={busy} type="submit">Upload immutable revision</button></div>
            </form> : null}
            <div className="overflow-x-auto rounded-2xl border border-[var(--border)] bg-white shadow-sm"><table className="min-w-full text-left text-sm"><thead className="border-b border-[var(--border)] bg-slate-50"><tr><th className="p-4">Document</th><th className="p-4">Project</th><th className="p-4">Discipline</th><th className="p-4">Latest revision</th><th className="p-4">Stage</th></tr></thead><tbody>{documents.map((document) => <tr className="border-b border-[var(--border)] last:border-0" key={document.public_id}><td className="p-4"><p className="font-semibold">{document.document_number}</p><p className="mt-1 text-[var(--muted)]">{document.title}</p></td><td className="p-4">{document.project_code}</td><td className="p-4">{document.discipline_code}</td><td className="p-4">{document.latest_version?.revision_code ?? "Not uploaded"}</td><td className="p-4">{document.latest_version?.stage.name ?? "Register only"}</td></tr>)}</tbody></table>{!documents.length && <p className="p-8 text-sm text-[var(--muted)]">No controlled design documents yet.</p>}</div>
          </section>
        )}

        {tab === "estimation" && (
          <section className="space-y-5">
            <div className="flex items-center justify-between gap-4"><div><h2 className="text-2xl font-semibold">Estimation and BOQ</h2><p className="mt-1 text-sm text-[var(--muted)]">Immutable versions, fixed-precision money and controlled baselines.</p></div>{permissions.includes("estimation.estimate.manage") && <button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" onClick={() => setShowEstimateForm((value) => !value)} type="button">New estimate</button>}</div>
            {showEstimateForm && <form className="grid gap-4 rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm md:grid-cols-2" onSubmit={createEstimate}>
              <label className="text-sm font-medium">Project<select className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" defaultValue={selectedProject} name="project_public_id" required><option value="">Choose project</option>{projectOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
              <label className="text-sm font-medium">Estimate code<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="code" required /></label>
              <label className="text-sm font-medium md:col-span-2">Estimate name<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="name" required /></label>
              <label className="text-sm font-medium md:col-span-2">Version notes<textarea className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="notes" rows={3} /></label>
              <button className="rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white md:col-span-2" disabled={busy}>Create estimate v1</button>
            </form>}
            <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm leading-6 text-blue-950"><strong>Estimator flow:</strong> create estimate → add BOQ lines → submit/review/approve using configured stages → freeze baseline. Customer sharing must use the governed Portal/Communications workspace; production approval is blocked until that customer-facing UAT passes.</div>
            <div className="grid gap-4 lg:grid-cols-2">{estimates.map((estimate) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={estimate.public_id}><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-[var(--brand)]">{estimate.project_code} · {estimate.code}</p><h3 className="mt-1 text-xl font-semibold">{estimate.name}</h3></div>{estimate.active_version && <Pill>{estimate.active_version.stage.name}</Pill>}</div><dl className="mt-5 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-[var(--muted)]">Active version</dt><dd className="mt-1 font-semibold">v{estimate.active_version?.version_number ?? 0}</dd></div><div><dt className="text-[var(--muted)]">Grand total</dt><dd className="mt-1 font-semibold">{money(estimate.active_version?.grand_total ?? "0", estimate.currency)}</dd></div><div><dt className="text-[var(--muted)]">Tax</dt><dd className="mt-1">{money(estimate.active_version?.tax_total ?? "0", estimate.currency)}</dd></div><div><dt className="text-[var(--muted)]">Baseline</dt><dd className="mt-1">{estimate.active_version?.baselined_at ? "Frozen" : "Not frozen"}</dd></div></dl><div className="mt-5 flex flex-wrap gap-2">{estimate.active_version && permissions.includes("estimation.boq.manage") && !estimate.active_version.baselined_at ? <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" onClick={() => setBoqEstimateId(estimate.public_id)} type="button">Add BOQ line</button> : null}{estimate.active_version && permissions.includes("estimation.version.transition") ? estimate.active_version.available_transitions.map((target) => <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} key={target.public_id} onClick={() => transitionEstimate(estimate, target)} type="button">Move to {target.name}</button>) : null}{estimate.active_version && permissions.includes("estimation.version.baseline") && estimate.active_version.stage.allows_baseline && !estimate.active_version.baselined_at ? <button className="rounded-lg bg-slate-950 px-3 py-2 text-sm font-semibold text-white" disabled={busy} onClick={() => baselineEstimate(estimate)} type="button">Freeze approved baseline</button> : null}{estimate.active_version?.baselined_at && permissions.includes("portal.share.manage") ? <button className="rounded-lg bg-[var(--brand)] px-3 py-2 text-sm font-semibold text-white" onClick={() => setShareEstimateId(estimate.public_id)} type="button">Share approved estimate</button> : null}<Link className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" href="/operations">Manage client access</Link></div>{shareEstimateId === estimate.public_id ? <form className="mt-4 rounded-xl border border-[var(--border)] bg-slate-50 p-4" onSubmit={(event) => shareEstimate(event, estimate)}><p className="text-sm font-semibold">Send to client portal</p><p className="mt-1 text-xs text-[var(--muted)]">Only active client grants with portal.estimate.view are listed.</p><select className="mt-3 w-full rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm" name="grant_public_id" required><option value="">Select client</option>{clientEstimateGrants.map((grant) => <option key={grant.public_id} value={grant.public_id}>Client user · {grant.user_public_id.slice(0, 8)}… · {grant.scope_type}</option>)}</select>{!clientEstimateGrants.length ? <p className="mt-2 text-xs font-semibold text-amber-800">No eligible client grant. Open Manage client access, invite/activate the client with portal.estimate.view, then return here.</p> : null}<div className="mt-3 flex gap-2"><button className="rounded-lg bg-slate-950 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={busy || !clientEstimateGrants.length} type="submit">Share estimate</button><button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" onClick={() => setShareEstimateId(null)} type="button">Cancel</button></div></form> : null}</article>)}{!estimates.length && <p className="rounded-2xl border border-dashed border-[var(--border)] p-8 text-sm text-[var(--muted)]">No estimates yet.</p>}</div>
            {boqEstimateId ? <form className="grid gap-4 rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm md:grid-cols-6" onSubmit={addBoqItem}><h3 className="text-lg font-semibold md:col-span-6">Add BOQ line</h3><label className="text-sm font-medium">Item code<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="item_code" required /></label><label className="text-sm font-medium md:col-span-2">Description<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="description" required /></label><label className="text-sm font-medium">Unit<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" name="unit_code" placeholder="sqft / nos" required /></label><label className="text-sm font-medium">Quantity<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" min="0" name="quantity" step="0.0001" type="number" required /></label><label className="text-sm font-medium">Rate<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" min="0" name="rate" step="0.0001" type="number" required /></label><label className="text-sm font-medium">Tax %<input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" min="0" max="100" name="tax_rate_percent" step="0.0001" type="number" /></label><div className="flex justify-end gap-2 md:col-span-5"><button className="rounded-lg border border-[var(--border)] px-4 py-2" onClick={() => setBoqEstimateId(null)} type="button">Cancel</button><button className="rounded-lg bg-[var(--brand)] px-4 py-2 font-semibold text-white" disabled={busy} type="submit">Add BOQ line</button></div></form> : null}
          </section>
        )}
      </div>
    </main>
  );
}
