"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

export type Project = {
  public_id: string;
  code: string;
  name: string;
  stage: { code: string; name: string; outcome: string };
};

type FileMeta = {
  public_id: string;
  status: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  upload_status: string;
  scan_status: string;
  is_image: boolean;
  is_pdf: boolean;
};

type LatestVersion = {
  public_id: string;
  version_number: number;
  revision_code: string;
  stage: { code: string; name: string; outcome: string };
  description: string;
  submitted_at: string | null;
  approved_at: string | null;
  issued_at: string | null;
  superseded_at: string | null;
  pending_reviews: number;
  open_issues: number;
  file: FileMeta | null;
};

type DesignDocument = {
  public_id: string;
  document_number: string;
  title: string;
  discipline_code: string;
  document_type_code: string;
  description: string;
  version_count: number;
  latest_version: LatestVersion | null;
};

type DesignBoard = {
  available: boolean;
  message?: string;
  project: { public_id: string; code: string; name: string; stage_name?: string };
  permissions?: {
    can_manage_documents: boolean;
    can_manage_versions: boolean;
    can_request_review: boolean;
    can_decide_review: boolean;
    can_manage_issues: boolean;
    can_download_files: boolean;
  };
  summary: {
    documents?: number;
    with_files?: number;
    approved_latest?: number;
    issued_latest?: number;
    pending_reviews?: number;
    open_issues?: number;
  };
  disciplines: { code: string; count: number }[];
  documents: DesignDocument[];
};

type Props = {
  initialProjects: Project[];
  initialProject: string;
  initialDocument: string;
};

const outcomeStyle: Record<string, string> = {
  approved: "bg-emerald-50 text-emerald-800",
  issued: "bg-blue-50 text-blue-800",
  review: "bg-amber-50 text-amber-900",
  rejected: "bg-red-50 text-red-800",
  superseded: "bg-slate-100 text-slate-500",
  complete: "bg-emerald-50 text-emerald-800",
  open: "bg-violet-50 text-violet-800",
};

function readableBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

function fileBadge(file: FileMeta | null) {
  if (!file) return "NO FILE";
  if (file.is_pdf) return "PDF";
  if (file.is_image) return "IMAGE";
  const extension = file.original_name.split(".").pop()?.slice(0, 6).toUpperCase();
  return extension || "FILE";
}

export function ProjectDesignWorkspace({
  initialProjects,
  initialProject,
  initialDocument,
}: Readonly<Props>) {
  const validInitialProject = initialProjects.some((item) => item.public_id === initialProject)
    ? initialProject
    : initialProjects[0]?.public_id ?? "";
  const [selectedProject, setSelectedProject] = useState(validInitialProject);
  const [board, setBoard] = useState<DesignBoard | null>(null);
  const [discipline, setDiscipline] = useState("ALL");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(Boolean(validInitialProject));
  const [message, setMessage] = useState("");
  const [openingFile, setOpeningFile] = useState("");
  const [focusedDocument, setFocusedDocument] = useState(initialDocument);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!selectedProject) {
        setBoard(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setMessage("");
      void fetch(`/api/project360/projects/${selectedProject}/design-board`, {
        signal: controller.signal,
        cache: "no-store",
      })
        .then(async (response) => {
          const body = (await response.json()) as DesignBoard & { message?: string };
          if (!response.ok) throw new Error(body.message || "Design Board could not load.");
          return body;
        })
        .then((body) => {
          if (controller.signal.aborted) return;
          setBoard(body);
          setLoading(false);
        })
        .catch((error) => {
          if (controller.signal.aborted) return;
          setMessage(error instanceof Error ? error.message : "Design Board could not load.");
          setLoading(false);
        });
    });
    return () => controller.abort();
  }, [selectedProject]);

  useEffect(() => {
    if (!focusedDocument || !board?.documents.length) return;
    const element = document.getElementById(`design-document-${focusedDocument}`);
    if (element) {
      window.setTimeout(() => element.scrollIntoView({ behavior: "smooth", block: "center" }), 120);
    }
  }, [board, focusedDocument]);

  const visibleDocuments = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return (board?.documents ?? []).filter((document) => {
      if (discipline !== "ALL" && document.discipline_code !== discipline) return false;
      if (!normalized) return true;
      return `${document.document_number} ${document.title} ${document.discipline_code} ${document.document_type_code}`
        .toLowerCase()
        .includes(normalized);
    });
  }, [board?.documents, discipline, query]);

  async function openGovernedFile(file: FileMeta) {
    setOpeningFile(file.public_id);
    setMessage("");
    const response = await fetch(`/api/files/${file.public_id}/download`, {
      cache: "no-store",
      credentials: "same-origin",
    }).catch(() => null);
    setOpeningFile("");
    if (!response?.ok) {
      setMessage("This governed file could not be opened. Confirm Files download permission and file scan status.");
      return;
    }
    const body = (await response.json()) as { download_url?: string };
    if (!body.download_url) {
      setMessage("The file service did not return a download URL.");
      return;
    }
    window.open(body.download_url, "_blank", "noopener,noreferrer");
  }

  return (
    <main className="min-h-screen bg-[var(--background)] px-4 py-6 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1500px] space-y-6">
        <header className="relative overflow-hidden rounded-[30px] border border-[var(--border)] bg-white p-6 shadow-sm lg:p-8">
          <div
            className="absolute inset-y-0 right-0 hidden w-[42%] opacity-10 lg:block"
            style={{
              background:
                "linear-gradient(135deg, transparent 0 30%, var(--brand) 30% 31%, transparent 31% 45%, var(--brand) 45% 46%, transparent 46%)",
            }}
          />
          <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--brand)]">
                Project 360 · Visual Design Board
              </p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
                Drawings should feel visual, not buried.
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
                Current revisions, reviews, issues and governed files are projected from the
                existing Design domain. No duplicate design records are created here.
              </p>
            </div>
            <div className="flex w-full flex-col gap-2 sm:flex-row lg:w-auto">
              <Link
                className="rounded-xl border border-[var(--border)] bg-white px-4 py-3 text-center text-sm font-semibold"
                href="/approvals"
              >
                My approvals
              </Link>
              <Link
                className="rounded-xl bg-[var(--brand)] px-4 py-3 text-center text-sm font-semibold text-white"
                href="/project360"
              >
                Project 360
              </Link>
            </div>
          </div>
        </header>

        <section className="rounded-[28px] border border-[var(--border)] bg-white p-5 shadow-sm">
          <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
            <label>
              <span className="mb-2 block text-xs font-bold uppercase tracking-[0.14em] text-[var(--muted)]">
                Project
              </span>
              <select
                className="w-full rounded-2xl border border-[var(--border)] bg-white px-4 py-3 text-sm font-semibold"
                onChange={(event) => {
                  setSelectedProject(event.target.value);
                  setFocusedDocument("");
                }}
                value={selectedProject}
              >
                <option value="">Select project</option>
                {initialProjects.map((project) => (
                  <option key={project.public_id} value={project.public_id}>
                    {project.code} · {project.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="mb-2 block text-xs font-bold uppercase tracking-[0.14em] text-[var(--muted)]">
                Search drawings
              </span>
              <input
                className="w-full rounded-2xl border border-[var(--border)] px-4 py-3 text-sm"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Drawing number, room, discipline…"
                value={query}
              />
            </label>
            <div className="flex items-end">
              <button
                className="w-full rounded-2xl border border-[var(--border)] px-4 py-3 text-sm font-semibold lg:w-auto"
                onClick={() => {
                  setQuery("");
                  setDiscipline("ALL");
                }}
                type="button"
              >
                Clear filters
              </button>
            </div>
          </div>
        </section>

        {message ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800">
            {message}
          </div>
        ) : null}

        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[1, 2, 3, 4].map((item) => (
              <div className="h-40 animate-pulse rounded-3xl bg-slate-200" key={item} />
            ))}
          </div>
        ) : null}

        {board?.available ? (
          <>
            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              {[
                ["Documents", board.summary.documents ?? 0],
                ["Files", board.summary.with_files ?? 0],
                ["Approved", board.summary.approved_latest ?? 0],
                ["Issued", board.summary.issued_latest ?? 0],
                ["Pending review", board.summary.pending_reviews ?? 0],
                ["Open issues", board.summary.open_issues ?? 0],
              ].map(([label, value]) => (
                <article
                  className="rounded-3xl border border-[var(--border)] bg-white p-5 shadow-sm"
                  key={label}
                >
                  <p className="text-xs font-bold uppercase tracking-[0.12em] text-[var(--muted)]">
                    {label}
                  </p>
                  <p className="mt-2 text-3xl font-semibold">{value}</p>
                </article>
              ))}
            </section>

            <section className="flex gap-2 overflow-x-auto pb-1">
              <button
                className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold ${
                  discipline === "ALL"
                    ? "bg-[var(--brand)] text-white"
                    : "border border-[var(--border)] bg-white"
                }`}
                onClick={() => setDiscipline("ALL")}
                type="button"
              >
                All · {board.summary.documents ?? 0}
              </button>
              {board.disciplines.map((item) => (
                <button
                  className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold ${
                    discipline === item.code
                      ? "bg-[var(--brand)] text-white"
                      : "border border-[var(--border)] bg-white"
                  }`}
                  key={item.code}
                  onClick={() => setDiscipline(item.code)}
                  type="button"
                >
                  {item.code.replaceAll("_", " ")} · {item.count}
                </button>
              ))}
            </section>

            {visibleDocuments.length ? (
              <section className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                {visibleDocuments.map((document) => {
                  const latest = document.latest_version;
                  const file = latest?.file ?? null;
                  const focused = focusedDocument === document.public_id;
                  return (
                    <article
                      className={`overflow-hidden rounded-[28px] border bg-white shadow-sm transition ${
                        focused
                          ? "border-[var(--brand)] ring-4 ring-[var(--brand-soft)]"
                          : "border-[var(--border)] hover:-translate-y-0.5 hover:border-[var(--brand)]"
                      }`}
                      id={`design-document-${document.public_id}`}
                      key={document.public_id}
                      onClick={() => setFocusedDocument(document.public_id)}
                    >
                      <div
                        className="relative grid h-44 place-items-center overflow-hidden"
                        style={{
                          background:
                            "linear-gradient(145deg, var(--brand-soft), white 48%, #f1f5f9)",
                        }}
                      >
                        <div className="absolute inset-0 opacity-25" style={{
                          backgroundImage:
                            "linear-gradient(#94a3b8 1px, transparent 1px), linear-gradient(90deg, #94a3b8 1px, transparent 1px)",
                          backgroundSize: "28px 28px",
                        }} />
                        <div className="relative text-center">
                          <span className="inline-flex rounded-xl border border-white/80 bg-white/90 px-4 py-2 text-xs font-black tracking-[0.18em] text-[var(--brand)] shadow-sm">
                            {fileBadge(file)}
                          </span>
                          <p className="mt-3 max-w-[260px] truncate text-sm font-semibold">
                            {file?.original_name || document.document_type_code.replaceAll("_", " ")}
                          </p>
                        </div>
                        <span className="absolute left-4 top-4 rounded-full bg-white/90 px-3 py-1 text-[10px] font-bold shadow-sm">
                          {document.discipline_code.replaceAll("_", " ")}
                        </span>
                        {latest ? (
                          <span
                            className={`absolute right-4 top-4 rounded-full px-3 py-1 text-[10px] font-bold ${
                              outcomeStyle[latest.stage.outcome] ?? "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {latest.stage.name}
                          </span>
                        ) : null}
                      </div>
                      <div className="p-5">
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0">
                            <p className="text-xs font-bold uppercase tracking-[0.12em] text-[var(--muted)]">
                              {document.document_number}
                            </p>
                            <h2 className="mt-1 truncate text-lg font-semibold">{document.title}</h2>
                          </div>
                          <div className="rounded-xl bg-slate-50 px-3 py-2 text-center">
                            <span className="block text-[10px] font-bold uppercase text-[var(--muted)]">
                              Revision
                            </span>
                            <strong className="mt-0.5 block text-sm">{latest?.revision_code ?? "—"}</strong>
                          </div>
                        </div>

                        <div className="mt-4 grid grid-cols-3 gap-2">
                          <div className="rounded-xl bg-slate-50 p-3">
                            <p className="text-[10px] font-bold uppercase text-[var(--muted)]">Versions</p>
                            <p className="mt-1 font-semibold">{document.version_count}</p>
                          </div>
                          <div className={`rounded-xl p-3 ${latest?.pending_reviews ? "bg-amber-50" : "bg-slate-50"}`}>
                            <p className="text-[10px] font-bold uppercase text-[var(--muted)]">Reviews</p>
                            <p className="mt-1 font-semibold">{latest?.pending_reviews ?? 0}</p>
                          </div>
                          <div className={`rounded-xl p-3 ${latest?.open_issues ? "bg-red-50" : "bg-slate-50"}`}>
                            <p className="text-[10px] font-bold uppercase text-[var(--muted)]">Issues</p>
                            <p className="mt-1 font-semibold">{latest?.open_issues ?? 0}</p>
                          </div>
                        </div>

                        <div className="mt-4 flex items-center justify-between gap-3 border-t border-[var(--border)] pt-4">
                          <div className="min-w-0 text-xs text-[var(--muted)]">
                            <p className="truncate">{file?.content_type || "No governed file attached"}</p>
                            <p className="mt-1">{file ? readableBytes(file.size_bytes) : "Upload via Design control"}</p>
                          </div>
                          {file && board.permissions?.can_download_files ? (
                            <button
                              className="shrink-0 rounded-xl bg-[var(--brand)] px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-60"
                              disabled={openingFile === file.public_id}
                              onClick={(event) => {
                                event.stopPropagation();
                                void openGovernedFile(file);
                              }}
                              type="button"
                            >
                              {openingFile === file.public_id ? "Opening…" : "Open file"}
                            </button>
                          ) : (
                            <Link
                              className="shrink-0 rounded-xl border border-[var(--border)] px-4 py-2.5 text-xs font-semibold"
                              href="/delivery?tab=design"
                            >
                              Design control
                            </Link>
                          )}
                        </div>
                      </div>
                    </article>
                  );
                })}
              </section>
            ) : (
              <div className="rounded-[28px] border border-dashed border-slate-300 bg-white p-12 text-center">
                <h2 className="text-2xl font-semibold">No drawings match this view</h2>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Change the discipline/search filter or create the governed document in Design control.
                </p>
                <Link
                  className="mt-5 inline-flex rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white"
                  href="/delivery?tab=design"
                >
                  Open Design control
                </Link>
              </div>
            )}
          </>
        ) : null}

        {board && !board.available ? (
          <div className="rounded-[28px] border border-amber-200 bg-amber-50 p-6 text-amber-950">
            <h2 className="text-xl font-semibold">Design Board is restricted</h2>
            <p className="mt-2 text-sm">{board.message}</p>
          </div>
        ) : null}

        {!initialProjects.length ? (
          <div className="rounded-[28px] border border-dashed border-slate-300 bg-white p-12 text-center">
            <h2 className="text-2xl font-semibold">No project is available</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Create/convert a project first, then its governed design information appears here.
            </p>
          </div>
        ) : null}
      </div>
    </main>
  );
}
