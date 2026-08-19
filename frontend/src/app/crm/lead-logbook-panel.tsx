"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { Build360ConfirmDialog, Build360Dialog, Build360ErrorDialog } from "@/components/build360-dialog";
import { Build360Toast } from "@/components/build360-toast";

import type { Lead } from "./crm-workspace";

type Attachment = {
  public_id: string;
  activity_public_id: string;
  file_public_id: string;
  attachment_kind: string;
  caption: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  upload_status: string;
  scan_status: string;
  available: boolean;
  created_at: string;
};

type TimelineItem = {
  kind: "activity" | "stage_change" | "conversion";
  public_id: string;
  occurred_at: string;
  activity_type: string;
  status: string;
  priority: string;
  subject: string;
  description: string;
  scheduled_for: string | null;
  follow_up_at: string | null;
  created_by_public_id: string;
  created_by_name: string;
  attachments: Attachment[];
};

type TimelinePayload = {
  lead: {
    public_id: string;
    title: string;
    source_code: string;
    stage: { code: string; name: string; outcome: string };
  };
  items: TimelineItem[];
  count: number;
};

type ErrorEnvelope = { message?: string; detail?: string; field_errors?: Record<string, string[]> };

type LeadRecommendation = {
  action_code: string;
  label: string;
  reason: string;
  suggested_due_at: string | null;
  confidence: string;
};

type LeadIntelligence = {
  lead_public_id: string;
  feature_access: { summary: boolean; recommendation: boolean };
  exists: boolean;
  stale: boolean;
  generated_at: string | null;
  interaction_public_id: string | null;
  generated: { summary?: string | null; recommended_next_action?: LeadRecommendation | null } | null;
  effective: { summary?: string | null; recommended_next_action?: LeadRecommendation | null } | null;
  override: Record<string, unknown>;
  override_active: boolean;
  overridden_at: string | null;
  citations: Array<{
    public_id: string;
    rank: number;
    source_type: string;
    source_public_id: string;
    source_label: string;
    excerpt: string;
    authorization_basis: string;
  }>;
  version: number | null;
  advisory_notice: string;
};

async function jsonRequest<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorEnvelope;
    const field = Object.entries(body.field_errors ?? {})
      .flatMap(([name, rows]) => rows.map((row) => `${name}: ${row}`))
      .join(" ");
    throw new Error(field || body.message || body.detail || `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

async function sha256(file: File) {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest)).map((value) => value.toString(16).padStart(2, "0")).join("");
}

function attachmentKind(file: File) {
  if (file.type.startsWith("image/")) return "photo";
  if (file.type.startsWith("video/")) return "video";
  if (file.type.startsWith("audio/")) return "audio";
  if (file.type.includes("pdf") || file.type.includes("document") || file.type.includes("word") || file.type.startsWith("text/")) return "document";
  return "other";
}

async function uploadActivityAttachment(activityPublicId: string, file: File) {
  if (!file.type) throw new Error(`${file.name}: browser did not provide a supported content type.`);
  const hash = await sha256(file);
  const grant = await jsonRequest<{
    file_public_id: string;
    version_public_id: string;
    upload_url: string;
    upload_headers: Record<string, string>;
  }>("/api/files/uploads", {
    method: "POST",
    body: JSON.stringify({
      purpose_code: "crm_activity_attachment",
      data_class: "internal",
      original_name: file.name,
      content_type: file.type,
      size_bytes: file.size,
      sha256: hash,
    }),
  });

  const upload = await fetch(grant.upload_url, {
    method: "PUT",
    headers: grant.upload_headers,
    body: file,
  });
  if (!upload.ok) throw new Error(`${file.name}: object-storage upload failed (${upload.status}).`);

  await jsonRequest(`/api/files/uploads/${grant.version_public_id}/finalize`, {
    method: "POST",
    body: "{}",
  });
  await jsonRequest(`/api/crm/activities/${activityPublicId}/attachments`, {
    method: "POST",
    body: JSON.stringify({
      file_public_id: grant.file_public_id,
      attachment_kind: attachmentKind(file),
      caption: "",
    }),
  });
}

function formatWhen(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

const activityTypes = [
  ["call", "Call"],
  ["whatsapp", "WhatsApp"],
  ["sms", "SMS"],
  ["email", "Email"],
  ["meeting", "Meeting"],
  ["follow_up", "Follow-up"],
  ["note", "Note"],
  ["voice_note", "Voice note"],
  ["document", "Document"],
  ["photo", "Photo"],
  ["video", "Video"],
  ["task", "Task"],
] as const;

export function LeadLogbookPanel({
  lead,
  permissions,
  features,
  onClose,
  onChanged,
  initialTab = "timeline",
}: Readonly<{
  lead: Lead;
  permissions: string[];
  features: Record<string, boolean>;
  onClose: () => void;
  onChanged: () => Promise<void>;
  initialTab?: "timeline" | "add" | "files" | "ai";
}>) {
  const [payload, setPayload] = useState<TimelinePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [intelligence, setIntelligence] = useState<LeadIntelligence | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState("");
  const [activeTab, setActiveTab] = useState<"timeline" | "add" | "files" | "ai">(initialTab);
  const [dirty, setDirty] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);

  const canManage = permissions.includes("crm.activity.manage");
  const canUpload = permissions.includes("files.upload") && features["crm.file_attachments"] === true;
  const canAIRead = permissions.includes("ai.crm_lead.read") && permissions.includes("crm.activity.read");
  const canAIGenerate = permissions.includes("ai.crm_lead.generate");
  const canAIOverride = permissions.includes("ai.crm_lead.override");
  const attachments = useMemo(() => (payload?.items ?? []).flatMap((item) => item.attachments.map((attachment) => ({ item, attachment }))), [payload]);

  function requestClose() {
    if (dirty) {
      setConfirmClose(true);
      return;
    }
    onClose();
  }

  const refreshTimeline = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setPayload(await jsonRequest<TimelinePayload>(`/api/crm/leads/${lead.public_id}/timeline?limit=250`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lead log book could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [lead.public_id]);


  const refreshIntelligenceState = useCallback(async () => {
    if (!canAIRead) return;
    setAiLoading(true);
    setAiError("");
    try {
      setIntelligence(await jsonRequest<LeadIntelligence>(`/api/crm/leads/${lead.public_id}/intelligence`));
    } catch (caught) {
      setAiError(caught instanceof Error ? caught.message : "Lead intelligence could not be loaded.");
    } finally {
      setAiLoading(false);
    }
  }, [canAIRead, lead.public_id]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      void refreshTimeline();
      void refreshIntelligenceState();
    });
    return () => controller.abort();
  }, [refreshTimeline, refreshIntelligenceState]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    setMessage("");
    setError("");
    const form = new FormData(formElement);
    const files = form.getAll("attachments").filter((value): value is File => value instanceof File && value.size > 0);
    try {
      const activity = await jsonRequest<{ public_id: string }>("/api/crm/activities", {
        method: "POST",
        body: JSON.stringify({
          lead_public_id: lead.public_id,
          activity_type: form.get("activity_type"),
          status: form.get("status"),
          priority: form.get("priority"),
          subject: form.get("subject"),
          notes: form.get("notes"),
          scheduled_for: form.get("scheduled_for") || null,
          follow_up_at: form.get("follow_up_at") || null,
          occurred_at: form.get("status") === "completed" ? new Date().toISOString() : null,
        }),
      });
      if (files.length && !canUpload) {
        throw new Error("Activity was saved, but you do not have Files upload permission for attachments.");
      }
      for (const file of files) {
        await uploadActivityAttachment(activity.public_id, file);
      }
      setMessage(
        files.length
          ? "Log entry saved. Attachments remain governed by upload finalization and security scan before download."
          : "Log entry saved.",
      );
      formElement.reset();
      setDirty(false);
      setActiveTab("timeline");
      await Promise.all([refreshTimeline(), refreshIntelligenceState(), onChanged()]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Log entry could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function generateIntelligence() {
    setAiBusy(true);
    setAiError("");
    try {
      const next = await jsonRequest<LeadIntelligence>(`/api/crm/leads/${lead.public_id}/intelligence`, {
        method: "POST",
        body: "{}",
      });
      setIntelligence(next);
    } catch (caught) {
      setAiError(caught instanceof Error ? caught.message : "Lead intelligence could not be refreshed.");
    } finally {
      setAiBusy(false);
    }
  }

  async function saveOverride(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAiBusy(true);
    setAiError("");
    const form = new FormData(event.currentTarget);
    try {
      const next = await jsonRequest<LeadIntelligence>(`/api/crm/leads/${lead.public_id}/intelligence/override`, {
        method: "POST",
        body: JSON.stringify({
          summary: String(form.get("summary") || ""),
          action_label: String(form.get("action_label") || ""),
          action_reason: String(form.get("action_reason") || ""),
          suggested_due_at: form.get("suggested_due_at") || null,
        }),
      });
      setIntelligence(next);
    } catch (caught) {
      setAiError(caught instanceof Error ? caught.message : "Human override could not be saved.");
    } finally {
      setAiBusy(false);
    }
  }

  async function clearOverride() {
    setAiBusy(true);
    setAiError("");
    try {
      const next = await jsonRequest<LeadIntelligence>(`/api/crm/leads/${lead.public_id}/intelligence/override`, {
        method: "POST",
        body: JSON.stringify({ clear_override: true }),
      });
      setIntelligence(next);
    } catch (caught) {
      setAiError(caught instanceof Error ? caught.message : "Human override could not be cleared.");
    } finally {
      setAiBusy(false);
    }
  }

  async function openAttachment(activityPublicId: string, attachment: Attachment) {
    if (!attachment.available) {
      setError(`File is not downloadable yet. Scan status: ${attachment.scan_status}.`);
      return;
    }
    setError("");
    try {
      const body = await jsonRequest<{ download_url: string }>(
        `/api/crm/activities/${activityPublicId}/attachments/${attachment.public_id}/download`,
      );
      window.open(body.download_url, "_blank", "noopener,noreferrer");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Attachment could not be opened.");
    }
  }

  const modalError = error || aiError;
  const logbookTabs: Array<{ value: "timeline" | "add" | "files" | "ai"; label: string }> = [
    { value: "timeline", label: "Timeline" },
    { value: "add", label: "Add interaction" },
    { value: "files", label: `Files${attachments.length ? ` (${attachments.length})` : ""}` },
    ...(canAIRead ? [{ value: "ai" as const, label: "AI Insight" }] : []),
  ];

  return (
    <>
      <Build360Dialog
        description={`${lead.customer?.display_name || "Unlinked prospect"} · ${lead.source_code || "Direct"} · ${lead.stage.name}`}
        kicker="Lead Log Book"
        onClose={requestClose}
        open
        preventBackdropClose={dirty}
        size="workspace"
        title={lead.title}
      >
        <div className="flex min-h-full flex-col bg-slate-50/70">
          <div className="sticky top-0 z-10 border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <nav aria-label="Lead workspace sections" className="flex gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1">
                {logbookTabs.map((item) => (
                  <button
                    aria-pressed={activeTab === item.value}
                    className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs font-semibold transition ${activeTab === item.value ? "bg-white text-slate-950 shadow-sm" : "text-slate-600 hover:text-slate-950"}`}
                    key={item.value}
                    onClick={() => setActiveTab(item.value)}
                    type="button"
                  >
                    {item.label}
                  </button>
                ))}
              </nav>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full bg-white px-3 py-2 font-semibold text-slate-700 shadow-sm">{payload?.count ?? lead.activity_count} timeline entries</span>
                {lead.next_follow_up_at ? <span className="rounded-full bg-amber-50 px-3 py-2 font-semibold text-amber-900">Next follow-up {formatWhen(lead.next_follow_up_at)}</span> : null}
              </div>
            </div>
          </div>

          {activeTab === "timeline" ? (
            <div className="grid flex-1 gap-5 p-4 sm:p-6 xl:grid-cols-[minmax(0,1fr)_320px]">
              <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--brand)]">Chronological history</p>
                    <h3 className="mt-1 text-xl font-semibold">Complete lead timeline</h3>
                    <p className="mt-1 text-sm text-slate-500">Calls, messages, notes, stage changes, files and follow-ups in one governed record.</p>
                  </div>
                  {canManage ? <button className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white" onClick={() => setActiveTab("add")} type="button">+ Add interaction</button> : null}
                </div>
                {loading ? <div className="mt-5 h-48 animate-pulse rounded-2xl bg-slate-100" /> : null}
                {!loading && payload ? (
                  <div className="mt-5 space-y-0">
                    {payload.items.map((item, index) => (
                      <article className="grid grid-cols-[26px_1fr] gap-3" key={`${item.kind}-${item.public_id}`}>
                        <div className="flex flex-col items-center">
                          <span className={`mt-1 h-3 w-3 rounded-full ${item.kind === "stage_change" || item.kind === "conversion" ? "bg-violet-500" : item.priority === "urgent" ? "bg-red-500" : item.priority === "high" ? "bg-amber-500" : "bg-[var(--brand)]"}`} />
                          {index < payload.items.length - 1 ? <span className="mt-1 min-h-16 w-px flex-1 bg-slate-200" /> : null}
                        </div>
                        <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-4">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold uppercase">{item.activity_type.replaceAll("_", " ")}</span>
                            <span className="text-[10px] font-semibold uppercase text-slate-500">{item.status}</span>
                            <span className="ml-auto text-xs text-slate-500">{formatWhen(item.occurred_at)}</span>
                          </div>
                          <h4 className="mt-2 font-semibold">{item.subject}</h4>
                          {item.description ? <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-600">{item.description}</p> : null}
                          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500">
                            <span>By {item.created_by_name || "Build360 user"}</span>
                            {item.scheduled_for ? <span>Scheduled {formatWhen(item.scheduled_for)}</span> : null}
                            {item.follow_up_at ? <span>Follow-up {formatWhen(item.follow_up_at)}</span> : null}
                          </div>
                          {item.attachments.length ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              {item.attachments.map((attachment) => (
                                <button
                                  className={`rounded-xl border px-3 py-2 text-xs font-semibold ${attachment.available ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-900"}`}
                                  key={attachment.public_id}
                                  onClick={() => openAttachment(item.public_id, attachment)}
                                  type="button"
                                >
                                  {attachment.original_name || attachment.attachment_kind} · {attachment.scan_status}
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </article>
                    ))}
                    {!payload.items.length ? (
                      <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
                        <p className="text-sm font-semibold text-slate-800">No lead interactions yet.</p>
                        <p className="mt-1 text-sm text-slate-500">Add the first note, call, follow-up or task without leaving the pipeline.</p>
                        {canManage ? <button className="mt-4 rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white" onClick={() => setActiveTab("add")} type="button">Add first interaction</button> : null}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </section>

              <aside className="space-y-4">
                <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--brand)]">Lead snapshot</p>
                  <dl className="mt-4 space-y-4 text-sm">
                    <div><dt className="text-xs text-slate-500">Stage</dt><dd className="mt-1 font-semibold">{lead.stage.name}</dd></div>
                    <div><dt className="text-xs text-slate-500">Owner</dt><dd className="mt-1 font-semibold">{lead.owner_display_name || "Unassigned"}</dd></div>
                    <div><dt className="text-xs text-slate-500">Source</dt><dd className="mt-1 font-semibold">{lead.source_code || "Direct"}</dd></div>
                    <div><dt className="text-xs text-slate-500">Estimated value</dt><dd className="mt-1 font-semibold">{lead.estimated_value ? `${lead.currency} ${lead.estimated_value}` : "Not set"}</dd></div>
                    <div><dt className="text-xs text-slate-500">Last activity</dt><dd className="mt-1 font-semibold">{formatWhen(lead.last_activity_at)}</dd></div>
                  </dl>
                </article>
                {canAIRead ? (
                  <button className="w-full rounded-2xl border border-violet-200 bg-violet-50 p-5 text-left transition hover:bg-violet-100/70" onClick={() => setActiveTab("ai")} type="button">
                    <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-violet-700">Grounded AI</p>
                    <p className="mt-2 font-semibold text-violet-950">Open AI insight</p>
                    <p className="mt-1 text-xs leading-5 text-violet-800/80">Summary, recommended next action, evidence and human override.</p>
                  </button>
                ) : null}
              </aside>
            </div>
          ) : null}

          {activeTab === "add" ? (
            <div className="mx-auto w-full max-w-4xl p-4 sm:p-6">
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--brand)]">Add interaction</p>
                  <h3 className="mt-1 text-xl font-semibold">Record what happened next</h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500">Use only the fields needed for this activity. Attachments stay governed by the existing Files service.</p>
                </div>
                {canManage ? (
                  <form className="mt-6 space-y-5" onChange={() => setDirty(true)} onSubmit={submit}>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <label className="text-sm font-medium">Interaction type
                        <select className="mt-2 w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/10" name="activity_type" defaultValue="note">
                          {activityTypes.filter(([value]) => (value !== "whatsapp" || features["crm.whatsapp"] === true) && (value !== "email" || features["crm.email"] === true)).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                      </label>
                      <label className="text-sm font-medium">Priority
                        <select className="mt-2 w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/10" name="priority" defaultValue="normal">
                          <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option>
                        </select>
                      </label>
                      <label className="text-sm font-medium">Status
                        <select className="mt-2 w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/10" name="status" defaultValue="completed">
                          <option value="completed">Completed</option><option value="planned">Planned</option>
                        </select>
                      </label>
                      <label className="text-sm font-medium">Scheduled <span className="font-normal text-slate-500">(optional)</span>
                        <input className="mt-2 w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/10" name="scheduled_for" type="datetime-local" />
                      </label>
                    </div>
                    <label className="block text-sm font-medium">Subject
                      <input className="mt-2 w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/10" name="subject" required placeholder="Called customer / quotation requirement / follow-up…" />
                    </label>
                    <label className="block text-sm font-medium">Log note
                      <textarea className="mt-2 min-h-32 w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/10" name="notes" placeholder="What happened, what the customer said, blockers, context…" />
                    </label>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <label className="block text-sm font-medium">Next follow-up <span className="font-normal text-slate-500">(optional)</span>
                        <input className="mt-2 w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/10" name="follow_up_at" type="datetime-local" />
                      </label>
                      <label className="block text-sm font-medium">Attachments
                        <input className="mt-2 block w-full rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs" disabled={!canUpload} multiple name="attachments" type="file" accept="image/*,audio/*,video/*,.pdf,.doc,.docx,.txt" />
                        {!canUpload ? <span className="mt-1 block text-[10px] text-amber-700">Attachments require the CRM file add-on and Files upload permission.</span> : null}
                      </label>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-5">
                      <button className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold" onClick={() => { setDirty(false); setActiveTab("timeline"); }} type="button">Cancel</button>
                      <button className="rounded-xl bg-[var(--brand)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">{busy ? "Saving…" : "Save interaction"}</button>
                    </div>
                  </form>
                ) : <p className="mt-5 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">You have read-only access to this lead history.</p>}
              </section>
            </div>
          ) : null}

          {activeTab === "files" ? (
            <div className="mx-auto w-full max-w-5xl p-4 sm:p-6">
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--brand)]">Governed files</p><h3 className="mt-1 text-xl font-semibold">Lead attachments</h3><p className="mt-1 text-sm text-slate-500">Files remain subject to upload finalization and security scanning.</p></div>
                  <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold">{attachments.length} files</span>
                </div>
                {attachments.length ? (
                  <div className="mt-5 grid gap-3 md:grid-cols-2">
                    {attachments.map(({ item, attachment }) => (
                      <button className="rounded-2xl border border-slate-200 p-4 text-left transition hover:bg-slate-50" key={attachment.public_id} onClick={() => openAttachment(item.public_id, attachment)} type="button">
                        <div className="flex items-start justify-between gap-3"><p className="min-w-0 truncate font-semibold">{attachment.original_name || attachment.attachment_kind}</p><span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-bold uppercase ${attachment.available ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-900"}`}>{attachment.scan_status}</span></div>
                        <p className="mt-2 text-xs text-slate-500">From {item.subject} · {formatWhen(item.occurred_at)}</p>
                      </button>
                    ))}
                  </div>
                ) : <p className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-500">No files have been attached to this lead yet.</p>}
              </section>
            </div>
          ) : null}

          {activeTab === "ai" && canAIRead ? (
            <div className="mx-auto w-full max-w-5xl p-4 sm:p-6">
              <section className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 to-white p-5 shadow-sm sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-violet-700">Grounded AI Lead Intelligence</p>
                    <h3 className="mt-1 text-xl font-semibold">Summary + recommended next action</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-600">Cached from governed lead + log-book evidence. It does not run again on every page load.</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {intelligence?.override_active ? <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-bold text-amber-900">HUMAN OVERRIDE</span> : null}
                    {intelligence?.exists ? <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${intelligence.stale ? "bg-red-100 text-red-800" : "bg-emerald-100 text-emerald-800"}`}>{intelligence.stale ? "NEEDS REFRESH" : "FRESH"}</span> : <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold">NOT GENERATED</span>}
                  </div>
                </div>
                {aiLoading ? <div className="mt-5 h-40 animate-pulse rounded-2xl bg-white" /> : null}
                {!aiLoading && intelligence?.effective ? (
                  <div className="mt-5 grid gap-4 lg:grid-cols-2">
                    {intelligence.feature_access.summary ? <article className="rounded-2xl border border-violet-100 bg-white p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-violet-700">AI Summary</p><p className="mt-3 text-sm leading-6">{intelligence.effective.summary || "No summary is available."}</p></article> : <article className="rounded-2xl bg-slate-50 p-5 text-sm text-slate-500">AI Summary is disabled by subscription entitlement.</article>}
                    {intelligence.feature_access.recommendation && intelligence.effective.recommended_next_action ? <article className="rounded-2xl border border-violet-100 bg-white p-5"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-[10px] font-bold uppercase tracking-wide text-violet-700">Recommended Next Action</p><span className="text-[10px] font-semibold text-slate-500">Confidence {Math.round(Number(intelligence.effective.recommended_next_action.confidence || 0) * 100)}%</span></div><p className="mt-3 text-base font-semibold">{intelligence.effective.recommended_next_action.label}</p><p className="mt-2 text-sm leading-6 text-slate-600">{intelligence.effective.recommended_next_action.reason}</p>{intelligence.effective.recommended_next_action.suggested_due_at ? <p className="mt-3 text-xs font-semibold text-violet-800">Suggested by {formatWhen(intelligence.effective.recommended_next_action.suggested_due_at)}</p> : null}</article> : intelligence.feature_access.recommendation ? null : <article className="rounded-2xl bg-slate-50 p-5 text-sm text-slate-500">AI Recommendation is disabled by subscription entitlement.</article>}
                  </div>
                ) : null}
                <div className="mt-5 flex flex-wrap gap-2">
                  {canAIGenerate && (!intelligence?.exists || intelligence.stale) ? <button className="rounded-xl bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={aiBusy} onClick={generateIntelligence} type="button">{aiBusy ? "Refreshing…" : intelligence?.exists ? "Refresh from latest history" : "Generate intelligence"}</button> : null}
                  {canAIGenerate && intelligence?.exists && !intelligence.stale ? <span className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800">No meaningful CRM change since last generation</span> : null}
                </div>
                {intelligence?.citations.length ? <details className="mt-5 rounded-2xl border border-violet-100 bg-white p-4"><summary className="cursor-pointer text-sm font-semibold">Evidence used · {intelligence.citations.length} citation(s)</summary><div className="mt-3 grid gap-2">{intelligence.citations.slice(0, 12).map((citation) => <div className="rounded-xl bg-slate-50 p-3" key={citation.public_id}><p className="text-xs font-semibold">{citation.rank}. {citation.source_label}</p><p className="mt-1 text-xs leading-5 text-slate-500">{citation.excerpt}</p></div>)}</div></details> : null}
                {intelligence?.advisory_notice ? <p className="mt-4 text-xs leading-5 text-slate-500">{intelligence.advisory_notice}</p> : null}
                {canAIOverride && intelligence?.exists ? (
                  <details className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                    <summary className="cursor-pointer text-sm font-bold text-amber-950">Human override</summary>
                    <form className="mt-4 grid gap-3" onSubmit={saveOverride}>
                      <label className="text-sm font-medium">Override summary<textarea className="mt-2 min-h-24 w-full rounded-xl border border-amber-200 bg-white p-3" defaultValue={String(intelligence.override.summary ?? intelligence.effective?.summary ?? "")} name="summary" /></label>
                      <label className="text-sm font-medium">Override action<input className="mt-2 w-full rounded-xl border border-amber-200 bg-white p-3" defaultValue={String(intelligence.override.action_label ?? intelligence.effective?.recommended_next_action?.label ?? "")} name="action_label" /></label>
                      <label className="text-sm font-medium">Reason<textarea className="mt-2 min-h-20 w-full rounded-xl border border-amber-200 bg-white p-3" defaultValue={String(intelligence.override.action_reason ?? "")} name="action_reason" /></label>
                      <label className="text-sm font-medium">Suggested due<input className="mt-2 w-full rounded-xl border border-amber-200 bg-white p-3" name="suggested_due_at" type="datetime-local" /></label>
                      <div className="flex flex-wrap gap-2"><button className="rounded-xl bg-amber-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={aiBusy} type="submit">Save human override</button>{intelligence.override_active ? <button className="rounded-xl border border-amber-300 bg-white px-4 py-2.5 text-sm font-semibold text-amber-900 disabled:opacity-50" disabled={aiBusy} onClick={clearOverride} type="button">Clear override</button> : null}</div>
                    </form>
                  </details>
                ) : null}
              </section>
            </div>
          ) : null}
        </div>
      </Build360Dialog>

      <Build360ConfirmDialog
        cancelLabel="Keep editing"
        confirmLabel="Discard changes"
        message="You have unsaved interaction details. Closing the Lead Log Book now will discard those changes."
        onCancel={() => setConfirmClose(false)}
        onConfirm={() => { setDirty(false); setConfirmClose(false); onClose(); }}
        open={confirmClose}
        title="Discard unsaved interaction?"
        tone="danger"
      />
      <Build360ErrorDialog
        message={modalError}
        onClose={() => { setError(""); setAiError(""); }}
        open={Boolean(modalError)}
        title={aiError ? "AI action could not be completed" : "Lead Log Book action could not be completed"}
      />
      <Build360Toast message={message} onDismiss={() => setMessage("")} />
    </>
  );
}
