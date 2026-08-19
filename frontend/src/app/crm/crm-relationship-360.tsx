"use client";

import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { Build360Dialog, Build360Drawer, Build360ErrorDialog } from "@/components/build360-dialog";
import { Build360Toast } from "@/components/build360-toast";

import type { CrmConfiguration } from "./crm-configuration-panel";

type ErrorEnvelope = {
  message?: string;
  detail?: string | string[];
  non_field_errors?: string[];
  field_errors?: Record<string, string[]>;
  [key: string]: unknown;
};

function apiErrorMessage(error: ErrorEnvelope, fallback: string) {
  const fieldMessage = Object.entries(error.field_errors ?? {})
    .flatMap(([field, messages]) => messages.map((message) => `${field}: ${message}`))
    .join(" ");
  if (fieldMessage) return fieldMessage;
  if (error.message) return error.message;
  if (typeof error.detail === "string") return error.detail;
  if (Array.isArray(error.detail)) return error.detail.join(" ");
  if (Array.isArray(error.non_field_errors)) return error.non_field_errors.join(" ");
  for (const [field, value] of Object.entries(error)) {
    if (Array.isArray(value) && value.length) return `${field}: ${value.map(String).join(" ")}`;
  }
  return fallback;
}

async function crmRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/crm/${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as ErrorEnvelope;
    throw new Error(apiErrorMessage(error, `CRM request failed (${response.status})`));
  }
  return (await response.json()) as T;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function relativeAction(value: string | null | undefined) {
  if (!value) return "No next action";
  const date = new Date(value);
  const now = new Date();
  const diff = date.getTime() - now.getTime();
  const minutes = Math.round(Math.abs(diff) / 60000);
  if (diff < 0) {
    if (minutes < 60) return `Overdue ${minutes} min`;
    if (minutes < 1440) return `Overdue ${Math.round(minutes / 60)} hr`;
    return `Overdue ${Math.round(minutes / 1440)} day${Math.round(minutes / 1440) === 1 ? "" : "s"}`;
  }
  if (minutes < 60) return `In ${Math.max(minutes, 1)} min`;
  if (minutes < 1440) return `In ${Math.round(minutes / 60)} hr`;
  return formatDateTime(value);
}

function money(value: string | null | undefined, currency: string) {
  const numeric = Number(value ?? 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: currency || "INR",
    maximumFractionDigits: 0,
  }).format(Number.isFinite(numeric) ? numeric : 0);
}

export type CrmMyWorkPayload = {
  generated_at: string;
  counts: {
    overdue: number;
    today: number;
    tomorrow: number;
    this_week: number;
    callback_requested: number;
    no_next_action: number;
    new_uncontacted: number;
  };
  queue: Array<{
    action_at: string | null;
    is_overdue: boolean;
    is_today: boolean;
    subject: string;
    reason: string;
    priority: string;
    person: {
      public_id: string;
      display_name: string;
      phone_masked: string | null;
      email_masked: string | null;
    } | null;
    company: { public_id: string; display_name: string } | null;
    lead_public_id: string | null;
    activity_public_id: string | null;
    activity_type: string;
  }>;
};

type PeopleRow = {
  person: {
    public_id: string;
    display_name: string;
    job_title: string;
    email_masked: string | null;
    phone_masked: string | null;
    alternate_phone_masked: string | null;
    source_code: string;
    tags: string[];
    created_at: string;
  };
  company: { public_id: string; display_name: string; kind: string } | null;
  relationship: "contact" | "lead" | "converted";
  has_active_lead: boolean;
  has_converted_lead: boolean;
  has_open_opportunity: boolean;
  has_won_opportunity: boolean;
  active_lead: {
    public_id: string;
    title: string;
    stage_code: string;
    stage_name: string;
    source_code: string;
  } | null;
  open_opportunity: {
    public_id: string;
    name: string;
    amount: string;
    currency: string;
  } | null;
  next_follow_up_at: string | null;
  next_action_kind: string | null;
  next_action_label: string;
  is_overdue: boolean;
  last_activity_at: string | null;
  owner: { public_id: string | null; display_name: string };
};

type PeopleResponse = {
  items: PeopleRow[];
  pagination: { page: number; page_size: number; total: number; has_next: boolean; has_previous: boolean };
  filters: { search: string; view: string; stage: string; source: string; owner: string; sort: string };
};

type TimelineItem = {
  kind: string;
  public_id: string;
  occurred_at: string;
  activity_type: string;
  status: string;
  direction: string;
  outcome_code: string;
  duration_seconds: number | null;
  channel_metadata: Record<string, unknown>;
  priority: string;
  subject: string;
  description: string;
  scheduled_for: string | null;
  follow_up_at: string | null;
  lead_public_id: string | null;
  opportunity_public_id: string | null;
  created_by_name: string;
  attachments: Array<{
    public_id: string;
    file_public_id?: string;
    original_name?: string;
    attachment_kind?: string;
    available?: boolean;
  }>;
  version: number;
};

type RelationshipWorkspace = {
  person: {
    public_id: string;
    customer_public_id: string | null;
    display_name: string;
    first_name: string;
    last_name: string;
    job_title: string;
    email_masked: string | null;
    phone_masked: string | null;
    alternate_phone_masked: string | null;
    communication_actions: { email: boolean; phone: boolean; alternate_phone?: boolean };
    consent_status: string;
    preferred_channel_code: string;
    address: Record<string, unknown>;
    source_code: string;
    tags: string[];
    notes: string;
    custom_fields: Record<string, unknown>;
    owner_membership_public_id: string | null;
    created_at: string;
    updated_at: string;
    version: number;
  };
  company: {
    public_id: string;
    display_name: string;
    legal_name: string;
    external_reference: string;
    source_code: string;
    status: string;
    custom_fields: Record<string, unknown>;
    notes: string;
  } | null;
  relationship: {
    has_active_lead: boolean;
    has_converted_lead: boolean;
    has_open_opportunity: boolean;
    has_won_opportunity: boolean;
    lead_count: number;
    opportunity_count: number;
  };
  next_action: {
    at: string;
    kind: string;
    label: string;
    is_overdue: boolean;
    lead_public_id: string | null;
    activity_public_id: string | null;
  } | null;
  last_activity_at: string | null;
  leads: Array<{
    public_id: string;
    title: string;
    description: string;
    source_code: string;
    stage: { public_id: string; code: string; name: string; outcome: string; pipeline_name: string };
    estimated_value: string | null;
    currency: string;
    next_follow_up_at: string | null;
    owner_display_name: string;
    custom_fields: Record<string, unknown>;
    converted_at: string | null;
    disqualified_at: string | null;
    created_at: string;
    version: number;
  }>;
  opportunities: Array<{
    public_id: string;
    name: string;
    source_lead_public_id: string | null;
    stage: { public_id: string; code: string; name: string; outcome: string; pipeline_name: string };
    amount: string;
    currency: string;
    probability_percent: number;
    expected_close_date: string | null;
    owner_display_name: string;
    custom_fields: Record<string, unknown>;
    won_at: string | null;
    lost_at: string | null;
    created_at: string;
    version: number;
  }>;
  timeline: TimelineItem[];
  files: Array<{
    public_id: string;
    file_public_id?: string;
    original_name?: string;
    attachment_kind?: string;
    scan_status?: string;
    available?: boolean;
    activity_subject?: string;
  }>;
  summary: {
    activity_count: number;
    file_count: number;
    active_lead_count: number;
    open_opportunity_count: number;
    won_opportunity_count: number;
    open_pipeline_value: string;
    currency: string;
  };
};

type ActivityResult = {
  public_id: string;
  version: number;
  activity_type: string;
  subject: string;
};

type OutcomeForm = {
  activity: ActivityResult;
  channel: "call" | "whatsapp" | "email";
};


type AiRecommendation = {
  action_code: string;
  label: string;
  reason: string;
  label_tanglish?: string;
  reason_tanglish?: string;
  suggested_due_at: string | null;
  confidence: string | number;
};

type AiLanguagePack = {
  objective: string;
  opening_line: string;
  talking_points: string[];
  questions: string[];
  closing_line: string;
};

type AiInsightPayload = {
  summary?: string | null;
  summary_tanglish?: string | null;
  recommended_next_action?: AiRecommendation | null;
  call_preparation?: {
    english: AiLanguagePack;
    tanglish: AiLanguagePack;
    grounded_context: string;
    safety_note: string;
  } | null;
  message_drafts?: {
    whatsapp?: { english: string; tanglish: string };
    email?: { subject: string; english: string; tanglish: string };
  } | null;
  attention_signals?: Array<{
    code: string; severity: string; label: string; reason: string;
    label_tanglish?: string; reason_tanglish?: string;
  }>;
  data_gaps?: Array<{ code: string; label: string; label_tanglish?: string }>;
};

type LeadAiInsight = {
  lead_public_id: string;
  feature_access: { summary: boolean; recommendation: boolean };
  exists: boolean;
  stale: boolean;
  generated_at: string | null;
  effective: AiInsightPayload | null;
  citations: Array<{ public_id: string; rank: number; source_label: string; excerpt: string }>;
  override_active: boolean;
  advisory_notice: string;
};

const QUICK_VIEWS = [
  ["all", "All people"],
  ["overdue", "Overdue"],
  ["today", "Today"],
  ["active_leads", "Active leads"],
  ["no_next_action", "No next action"],
  ["converted", "Converted"],
  ["contact_only", "Contact only"],
] as const;

const OUTCOME_OPTIONS = {
  call: [
    ["connected", "Connected"],
    ["no_answer", "No answer"],
    ["busy", "Busy"],
    ["callback_requested", "Callback requested"],
    ["wrong_number", "Wrong number"],
  ],
  whatsapp: [
    ["message_sent", "Message sent"],
    ["replied", "Replied"],
    ["no_response", "No response"],
    ["callback_requested", "Callback requested"],
  ],
  email: [
    ["email_sent", "Email sent"],
    ["replied", "Replied"],
    ["follow_up_required", "Follow-up required"],
    ["bounced", "Bounced"],
  ],
} as const;

function RelationshipBadge({ children, tone = "neutral" }: Readonly<{ children: ReactNode; tone?: "brand" | "success" | "warning" | "neutral" }>) {
  const toneClass = tone === "brand"
    ? "bg-[var(--brand-soft)] text-[var(--brand)]"
    : tone === "success"
      ? "bg-emerald-50 text-emerald-800"
      : tone === "warning"
        ? "bg-amber-50 text-amber-900"
        : "bg-slate-100 text-slate-700";
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ${toneClass}`}>{children}</span>;
}

function EmptyState({ title, body }: Readonly<{ title: string; body: string }>) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 p-6 text-center">
      <p className="font-semibold text-slate-900">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-600">{body}</p>
    </div>
  );
}

export function CrmMyWorkPanel({
  initial,
  onOpenPerson,
}: Readonly<{
  initial: CrmMyWorkPayload;
  onOpenPerson: (publicId: string) => void;
}>) {
  const [data, setData] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    setBusy(true);
    setError("");
    try {
      setData(await crmRequest<CrmMyWorkPayload>("my-work?limit=50"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "My Work could not be refreshed.");
    } finally {
      setBusy(false);
    }
  }

  const cards = [
    ["Overdue", data.counts.overdue, "text-red-800 bg-red-50"],
    ["Today", data.counts.today, "text-amber-900 bg-amber-50"],
    ["Tomorrow", data.counts.tomorrow, "text-slate-800 bg-slate-50"],
    ["Callbacks", data.counts.callback_requested, "text-sky-900 bg-sky-50"],
    ["No next action", data.counts.no_next_action, "text-violet-900 bg-violet-50"],
    ["New · not contacted", data.counts.new_uncontacted, "text-emerald-900 bg-emerald-50"],
  ] as const;

  return (
    <section className="mt-5 space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--brand)]">Daily command centre</p>
          <h2 className="mt-1 text-2xl font-semibold text-slate-950">What needs your attention now?</h2>
          <p className="mt-1 text-sm text-slate-600">Build360 puts overdue and next follow-ups first so nothing important is buried inside CRM records.</p>
        </div>
        <button className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-50" disabled={busy} onClick={refresh} type="button">{busy ? "Refreshing…" : "Refresh queue"}</button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {cards.map(([label, value, tone]) => (
          <article className={`rounded-2xl border border-slate-200 p-4 ${tone}`} key={label}>
            <p className="text-xs font-semibold">{label}</p>
            <p className="mt-2 text-3xl font-semibold">{value}</p>
          </article>
        ))}
      </div>

      <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h3 className="font-semibold text-slate-950">Priority queue</h3>
          <p className="mt-1 text-sm text-slate-600">Oldest overdue action first, then today, then upcoming work.</p>
        </div>
        {data.queue.length ? (
          <div className="divide-y divide-slate-100">
            {data.queue.map((item, index) => (
              <button
                className="grid w-full gap-2 px-5 py-4 text-left transition hover:bg-slate-50 md:grid-cols-[44px_minmax(180px,0.8fr)_minmax(260px,1.4fr)_170px] md:items-center"
                key={`${item.activity_public_id ?? item.lead_public_id ?? index}-${item.action_at}`}
                onClick={() => item.person?.public_id && onOpenPerson(item.person.public_id)}
                type="button"
              >
                <span className="text-sm font-bold text-slate-400">{String(index + 1).padStart(2, "0")}</span>
                <span>
                  <span className="block font-semibold text-slate-950">{item.person?.display_name || "CRM record"}</span>
                  <span className="mt-0.5 block text-xs text-slate-500">{item.company?.display_name || item.reason}</span>
                </span>
                <span>
                  <span className="block text-sm font-medium text-slate-900">{item.subject}</span>
                  <span className="mt-1 block text-xs text-slate-500">{item.reason}</span>
                </span>
                <span className={`text-sm font-semibold ${item.is_overdue ? "text-red-700" : item.is_today ? "text-amber-800" : "text-slate-700"}`}>
                  {relativeAction(item.action_at)}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <div className="p-5"><EmptyState body="No overdue or scheduled CRM actions are assigned to you right now." title="Your queue is clear" /></div>
        )}
      </article>
      <Build360ErrorDialog message={error} onClose={() => setError("")} open={Boolean(error)} title="My Work could not be refreshed" />
    </section>
  );
}

function RelationshipDetail({
  data,
  permissions,
  features,
  onChanged,
}: Readonly<{
  data: RelationshipWorkspace;
  permissions: string[];
  features: Record<string, boolean>;
  onChanged: () => Promise<void>;
}>) {
  const [tab, setTab] = useState<"overview" | "timeline" | "ai" | "business" | "files" | "details">("timeline");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<OutcomeForm | null>(null);
  const [showActivity, setShowActivity] = useState(false);
  const [showLeadCreate, setShowLeadCreate] = useState(false);
  const [aiInsight, setAiInsight] = useState<LeadAiInsight | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiLanguage, setAiLanguage] = useState<"english" | "tanglish">("english");

  const can = (code: string) => permissions.includes(code);
  const activeLead = data.leads.find((item) => !item.converted_at && !item.disqualified_at) ?? null;
  const openOpportunity = data.opportunities.find((item) => !item.won_at && !item.lost_at) ?? null;
  const canAIRead = Boolean(activeLead)
    && can("crm.lead.read")
    && can("crm.activity.read")
    && can("ai.crm_lead.read")
    && (features["crm.ai_summary"] === true || features["crm.ai_recommendation"] === true);
  const canAIGenerate = canAIRead && can("ai.crm_lead.generate");

  async function loadAiInsight() {
    if (!activeLead || !canAIRead) {
      setAiInsight(null);
      return null;
    }
    try {
      const insight = await crmRequest<LeadAiInsight>(`leads/${activeLead.public_id}/intelligence`);
      setAiInsight(insight);
      return insight;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI Sales Copilot could not be loaded.");
      return null;
    }
  }

  async function generateAiInsight() {
    if (!activeLead || !canAIGenerate) return;
    setAiBusy(true);
    setError("");
    try {
      const insight = await crmRequest<LeadAiInsight>(`leads/${activeLead.public_id}/intelligence`, { method: "POST" });
      setAiInsight(insight);
      setNotice("AI Sales Copilot refreshed from the latest CRM history.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI Sales Copilot could not be generated.");
    } finally {
      setAiBusy(false);
    }
  }

  async function openAiPrep() {
    if (!canAIRead) return;
    setTab("ai");
    const current = aiInsight ?? await loadAiInsight();
    if (canAIGenerate && (!current?.exists || current.stale)) {
      await generateAiInsight();
    }
  }

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      setAiInsight(null);
      setAiLanguage("english");
      if (canAIRead) void loadAiInsight();
    });
    return () => {
      active = false;
    };
    // Active lead identity is the governed cache subject.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLead?.public_id, canAIRead]);

  async function launchCommunication(channel: "call" | "whatsapp" | "email") {
    if (!can("crm.contact.reveal")) {
      setError("You do not have permission to reveal protected contact endpoints.");
      return;
    }
    if (channel === "whatsapp" && features["crm.whatsapp"] !== true) {
      setError("WhatsApp is disabled for this company subscription.");
      return;
    }
    if (channel === "email" && features["crm.email"] !== true) {
      setError("Email is disabled for this company subscription.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const reason = channel === "call" ? "crm_call" : channel === "whatsapp" ? "crm_whatsapp" : "crm_email";
      const revealed = await crmRequest<{ phone?: string; alternate_phone?: string; email?: string }>(`contacts/${data.person.public_id}/reveal`, {
        method: "POST",
        body: JSON.stringify({ reason_code: reason }),
      });
      if (channel === "call") {
        const phone = (revealed.phone ?? "").trim();
        if (!phone) throw new Error("This person does not have a callable phone number.");
        window.location.assign(`tel:${phone.replace(/[^+0-9]/g, "")}`);
      } else if (channel === "whatsapp") {
        const digits = (revealed.phone ?? "").replace(/\D/g, "");
        if (!digits) throw new Error("This person does not have a WhatsApp-capable number.");
        window.open(`https://wa.me/${digits}`, "_blank", "noopener,noreferrer");
      } else {
        const email = (revealed.email ?? "").trim();
        if (!email) throw new Error("This person does not have an email address.");
        window.location.assign(`mailto:${email}`);
      }

      if (can("crm.activity.manage")) {
        const activity = await crmRequest<ActivityResult>("activities", {
          method: "POST",
          body: JSON.stringify({
            contact_public_id: data.person.public_id,
            ...(activeLead ? { lead_public_id: activeLead.public_id } : {}),
            ...(openOpportunity ? { opportunity_public_id: openOpportunity.public_id } : {}),
            activity_type: channel,
            status: "planned",
            direction: "outbound",
            outcome_code: "started",
            occurred_at: new Date().toISOString(),
            subject: `${channel === "call" ? "Call" : channel === "whatsapp" ? "WhatsApp" : "Email"} ${data.person.display_name}`,
            notes: `Started from Relationship 360. Record the outcome when complete.`,
            channel_metadata: { source: "relationship_360", launch_mode: "device_handoff" },
          }),
        });
        setOutcome({ activity, channel });
      }
      setNotice(`${channel === "call" ? "Dialer" : channel === "whatsapp" ? "WhatsApp" : "Email app"} opened. The interaction is tracked in this person's timeline.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Communication action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function saveOutcome(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!outcome) return;
    const form = new FormData(event.currentTarget);
    const outcomeCode = String(form.get("outcome_code") || "");
    const followUpAt = String(form.get("follow_up_at") || "").trim();
    if (["callback_requested", "follow_up_required"].includes(outcomeCode) && !followUpAt) {
      setError("Choose the next follow-up time for this outcome.");
      return;
    }
    setBusy(true);
    try {
      await crmRequest(`activities/${outcome.activity.public_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_version: outcome.activity.version,
          status: "completed",
          outcome_code: outcomeCode,
          duration_seconds: form.get("duration_seconds") ? Number(form.get("duration_seconds")) : null,
          follow_up_at: followUpAt || null,
          notes: form.get("notes"),
        }),
      });
      setOutcome(null);
      setNotice("Interaction outcome saved. Relationship 360 is up to date.");
      await onChanged();
      if (canAIRead) await loadAiInsight();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Interaction outcome could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function addActivity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const type = String(form.get("activity_type") || "note");
    const scheduled = String(form.get("scheduled_for") || "").trim();
    setBusy(true);
    try {
      await crmRequest("activities", {
        method: "POST",
        body: JSON.stringify({
          contact_public_id: data.person.public_id,
          ...(activeLead ? { lead_public_id: activeLead.public_id } : {}),
          ...(openOpportunity ? { opportunity_public_id: openOpportunity.public_id } : {}),
          activity_type: type,
          status: type === "note" ? "completed" : "planned",
          direction: "internal",
          subject: form.get("subject"),
          notes: form.get("notes"),
          priority: form.get("priority") || "normal",
          scheduled_for: scheduled || null,
          follow_up_at: type === "follow_up" ? scheduled || null : null,
          occurred_at: type === "note" ? new Date().toISOString() : null,
        }),
      });
      setShowActivity(false);
      setNotice(type === "note" ? "Note added to the relationship timeline." : "Next action added to the relationship timeline.");
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Activity could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function createLeadFromPerson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const response = await crmRequest<{ created: boolean }>(`contacts/${data.person.public_id}/convert-lead`, {
        method: "POST",
        body: JSON.stringify({
          title: form.get("title"),
          description: form.get("description"),
          source_code: data.person.source_code,
          estimated_value: form.get("estimated_value") || null,
          next_follow_up_at: form.get("next_follow_up_at") || null,
        }),
      });
      setShowLeadCreate(false);
      setNotice(response.created ? "Lead created for this person. The contact was reused — no duplicate person was created." : "An active lead already exists for this person. Build360 reused it.");
      await onChanged();
      setTab("business");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lead could not be created for this person.");
    } finally {
      setBusy(false);
    }
  }

  const recentTimeline = tab === "overview" ? data.timeline.slice(0, 6) : data.timeline;
  const relationshipTabs = ([
    "overview",
    ...(can("crm.activity.read") ? ["timeline"] : []),
    ...(canAIRead ? ["ai"] : []),
    ...(can("crm.lead.read") || can("crm.opportunity.read") ? ["business"] : []),
    ...(can("crm.activity.read") && features["crm.file_attachments"] ? ["files"] : []),
    "details",
  ] as Array<"overview" | "timeline" | "ai" | "business" | "files" | "details">);

  return (
    <div className="min-h-full bg-slate-50/60">
      <div className="border-b border-slate-200 bg-white p-5 sm:p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <RelationshipBadge>{"Contact"}</RelationshipBadge>
              <MetaSourcePill source={data.person.source_code} />
              {data.relationship.has_active_lead ? <RelationshipBadge tone="brand">Active lead</RelationshipBadge> : null}
              {data.relationship.has_open_opportunity ? <RelationshipBadge tone="warning">Open deal</RelationshipBadge> : null}
              {data.relationship.has_won_opportunity ? <RelationshipBadge tone="success">Won business</RelationshipBadge> : null}
            </div>
            <p className="mt-3 text-sm font-medium text-slate-700">
              {[data.person.job_title, data.company?.display_name].filter(Boolean).join(" · ") || "Individual contact"}
            </p>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-600">
              <span className="whitespace-nowrap">Primary: {data.person.phone_masked || "No phone"}</span>
              {data.person.alternate_phone_masked ? <span className="whitespace-nowrap">Alternate: {data.person.alternate_phone_masked}</span> : null}
              <span className="min-w-0 break-all">{data.person.email_masked || "No email"}</span>
              <span>Last activity: {data.last_activity_at ? formatDateTime(data.last_activity_at) : "None yet"}</span>
            </div>
          </div>
          <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:flex-wrap">
            {!activeLead && can("crm.lead.manage") ? <button className="col-span-2 rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white sm:col-span-1" onClick={() => setShowLeadCreate(true)} type="button">Create lead</button> : null}
            {can("crm.contact.reveal") && data.person.communication_actions.phone ? <button className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={busy} onClick={() => launchCommunication("call")} type="button">Call</button> : null}
            {canAIRead ? <button className="rounded-xl border border-violet-200 bg-violet-50 px-4 py-2.5 text-sm font-semibold text-violet-800 disabled:opacity-50" disabled={aiBusy} onClick={() => void openAiPrep()} type="button">✨ AI Prep</button> : null}
            {can("crm.contact.reveal") && data.person.communication_actions.phone && features["crm.whatsapp"] ? <button className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold disabled:opacity-50" disabled={busy} onClick={() => launchCommunication("whatsapp")} type="button">WhatsApp</button> : null}
            {can("crm.contact.reveal") && data.person.communication_actions.email && features["crm.email"] ? <button className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold disabled:opacity-50" disabled={busy} onClick={() => launchCommunication("email")} type="button">Email</button> : null}
            {can("crm.activity.manage") ? <button className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold" onClick={() => setShowActivity(true)} type="button">+ Activity</button> : null}
          </div>
        </div>
      </div>

      <div className="p-4 sm:p-6">
        <section className={`rounded-2xl border p-4 sm:p-5 ${data.next_action?.is_overdue ? "border-red-200 bg-red-50" : data.next_action ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-white"}`}>
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-600">Next action</p>
          {data.next_action ? (
            <div className="mt-2 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className={`text-lg font-semibold ${data.next_action.is_overdue ? "text-red-900" : "text-slate-950"}`}>{data.next_action.label}</p>
                <p className={`mt-1 text-sm font-semibold ${data.next_action.is_overdue ? "text-red-700" : "text-amber-900"}`}>{relativeAction(data.next_action.at)} · {formatDateTime(data.next_action.at)}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {can("crm.contact.reveal") && data.person.communication_actions.phone ? <button className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white" onClick={() => launchCommunication("call")} type="button">Start call</button> : null}
                {can("crm.activity.manage") ? <button className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold" onClick={() => setShowActivity(true)} type="button">Schedule next step</button> : null}
              </div>
            </div>
          ) : (
            <div className="mt-2 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div><p className="font-semibold text-slate-950">No next action is scheduled</p><p className="mt-1 text-sm text-slate-600">Relationships without a next step are easy to forget.</p></div>
              {can("crm.activity.manage") ? <button className="rounded-xl bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" onClick={() => setShowActivity(true)} type="button">Schedule follow-up</button> : null}
            </div>
          )}
        </section>

        <nav className="mt-5 grid grid-cols-2 gap-1 rounded-xl border border-slate-200 bg-white p-1.5 sm:flex sm:overflow-x-auto" aria-label="Relationship 360 sections">
          {relationshipTabs.map((item) => (
            <button className={`min-w-0 rounded-lg px-3 py-2 text-center text-sm font-semibold capitalize sm:whitespace-nowrap ${tab === item ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-slate-50"}`} key={item} onClick={() => setTab(item)} type="button">{item === "ai" ? "AI Copilot" : item}</button>
          ))}
        </nav>

        {tab === "overview" ? (
          <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
            <TimelineList items={recentTimeline} />
            <div className="space-y-4">
              <article className="rounded-2xl border border-slate-200 bg-white p-5">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Business snapshot</p>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <Metric label="Active leads" value={data.summary.active_lead_count} />
                  <Metric label="Open deals" value={data.summary.open_opportunity_count} />
                  <Metric label="Won deals" value={data.summary.won_opportunity_count} />
                  <Metric label="Open value" value={money(data.summary.open_pipeline_value, data.summary.currency)} />
                </div>
              </article>
              {activeLead ? (
                <article className="rounded-2xl border border-slate-200 bg-white p-5">
                  <div className="flex items-center justify-between gap-3"><p className="font-semibold text-slate-950">{activeLead.title}</p><RelationshipBadge tone="brand">{activeLead.stage.name}</RelationshipBadge></div>
                  <p className="mt-2 text-sm text-slate-600">Source: {activeLead.source_code || "Direct"}</p>
                  <p className="mt-1 text-sm text-slate-600">Owner: {activeLead.owner_display_name || "Unassigned"}</p>
                  <p className="mt-3 text-lg font-semibold text-slate-950">{activeLead.estimated_value ? money(activeLead.estimated_value, activeLead.currency) : "Value not set"}</p>
                </article>
              ) : (
                <article className="rounded-2xl border border-dashed border-slate-300 bg-white p-5">
                  <p className="font-semibold text-slate-950">Contact only — no active lead</p>
                  <p className="mt-1 text-sm leading-6 text-slate-600">This person is already safely saved. Create a lead only when there is an enquiry or sales opportunity.</p>
                  {can("crm.lead.manage") ? <button className="mt-4 w-full rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white sm:w-auto" onClick={() => setShowLeadCreate(true)} type="button">Create lead from this person</button> : null}
                </article>
              )}
            </div>
          </div>
        ) : null}

        {tab === "timeline" ? <div className="mt-5"><TimelineList items={recentTimeline} /></div> : null}

        {tab === "ai" && canAIRead ? (
          <div className="mt-5">
            <AiSalesCopilotPanel
              busy={aiBusy}
              insight={aiInsight}
              language={aiLanguage}
              onGenerate={() => void generateAiInsight()}
              onLanguageChange={setAiLanguage}
            />
          </div>
        ) : null}

        {tab === "business" ? (
          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <BusinessList
              empty="No lead history for this person."
              items={data.leads.map((lead) => ({
                id: lead.public_id,
                title: lead.title,
                status: lead.stage.name,
                meta: `${lead.source_code || "Direct"} · ${lead.owner_display_name || "Unassigned"}`,
                value: lead.estimated_value ? money(lead.estimated_value, lead.currency) : "Value not set",
                sub: lead.next_follow_up_at ? `Next ${formatDateTime(lead.next_follow_up_at)}` : lead.converted_at ? `Converted ${formatDateTime(lead.converted_at)}` : "No next follow-up",
              }))}
              title="Lead history"
            />
            <BusinessList
              empty="No opportunities for this person."
              items={data.opportunities.map((opportunity) => ({
                id: opportunity.public_id,
                title: opportunity.name,
                status: opportunity.stage.name,
                meta: `${opportunity.probability_percent}% · ${opportunity.owner_display_name || "Unassigned"}`,
                value: money(opportunity.amount, opportunity.currency),
                sub: opportunity.expected_close_date ? `Close ${opportunity.expected_close_date}` : opportunity.won_at ? `Won ${formatDateTime(opportunity.won_at)}` : "No close date",
              }))}
              title="Opportunity history"
            />
          </div>
        ) : null}

        {tab === "files" ? (
          <div className="mt-5">
            {data.files.length ? (
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                <div className="divide-y divide-slate-100">
                  {data.files.map((file) => (
                    <div className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between" key={file.public_id}>
                      <div><p className="font-medium text-slate-950">{file.original_name || "CRM attachment"}</p><p className="mt-1 text-xs text-slate-500">{file.activity_subject || file.attachment_kind || "Activity file"}</p></div>
                      <RelationshipBadge tone={file.available ? "success" : "neutral"}>{file.available ? "Available" : file.scan_status || "Pending"}</RelationshipBadge>
                    </div>
                  ))}
                </div>
              </div>
            ) : <EmptyState body="Files shared from calls, WhatsApp, email and lead activities will appear here together." title="No files yet" />}
          </div>
        ) : null}

        {tab === "details" ? (
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <DetailCard title="Person details" values={{
              Name: data.person.display_name,
              "Job title": data.person.job_title || "—",
              "Primary phone": data.person.phone_masked || "—",
              "Alternate phone": data.person.alternate_phone_masked || "—",
              Email: data.person.email_masked || "—",
              Source: crmSourceLabel(data.person.source_code),
              Consent: data.person.consent_status,
              "Preferred channel": data.person.preferred_channel_code || "Not set",
              Tags: data.person.tags.join(", ") || "—",
              Notes: data.person.notes || "—",
            }} />
            <DetailCard title="Company / account" values={{
              Company: data.company?.display_name || "Individual / not linked",
              "Legal name": data.company?.legal_name || "—",
              Reference: data.company?.external_reference || "—",
              Status: data.company?.status || "—",
              Notes: data.company?.notes || "—",
            }} />
            {Object.keys(data.person.custom_fields).length ? <DetailCard title="Configured person fields" values={Object.fromEntries(Object.entries(data.person.custom_fields).map(([key, value]) => [key, String(value ?? "—")]))} /> : null}
            {data.company && Object.keys(data.company.custom_fields).length ? <DetailCard title="Configured company fields" values={Object.fromEntries(Object.entries(data.company.custom_fields).map(([key, value]) => [key, String(value ?? "—")]))} /> : null}
          </div>
        ) : null}
      </div>

      <Build360Dialog
        description="The person stays the same contact. Build360 only adds a sales lead on top of the existing relationship."
        kicker="Create lead from contact"
        onClose={() => setShowLeadCreate(false)}
        open={showLeadCreate}
        size="medium"
        title={`Create lead for ${data.person.display_name}`}
      >
        <form className="grid gap-4 p-4 sm:grid-cols-2 sm:p-6" onSubmit={createLeadFromPerson}>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 sm:col-span-2">
            <p className="text-sm font-semibold text-slate-950">No duplicate contact will be created</p>
            <p className="mt-1 text-sm leading-6 text-slate-600">Primary phone {data.person.phone_masked || "not available"}{data.person.alternate_phone_masked ? ` · Alternate ${data.person.alternate_phone_masked}` : ""}. The lead will point to this same person record.</p>
          </div>
          <label className="text-sm font-medium sm:col-span-2">What is this enquiry about? <span className="text-red-600">*</span><input className="mt-1 w-full rounded-xl border border-slate-200 p-3" defaultValue={`${data.person.display_name} enquiry`} name="title" required /></label>
          <label className="text-sm font-medium">Estimated value<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" min="0" name="estimated_value" step="0.01" type="number" /></label>
          <label className="text-sm font-medium">Next follow-up<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="next_follow_up_at" type="datetime-local" /></label>
          <label className="text-sm font-medium sm:col-span-2">Context / requirement<textarea className="mt-1 min-h-24 w-full rounded-xl border border-slate-200 p-3" name="description" placeholder="What is the person interested in?" /></label>
          <div className="grid gap-2 sm:col-span-2 sm:flex sm:justify-end"><button className="rounded-xl border border-slate-200 px-4 py-2.5 font-semibold" onClick={() => setShowLeadCreate(false)} type="button">Cancel</button><button className="rounded-xl bg-[var(--brand)] px-5 py-2.5 font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Create lead</button></div>
        </form>
      </Build360Dialog>

      <Build360Dialog
        footer={null}
        kicker="Record interaction outcome"
        onClose={() => setOutcome(null)}
        open={Boolean(outcome)}
        size="medium"
        title={`What happened on the ${outcome?.channel ?? "interaction"}?`}
      >
        {outcome ? (
          <form className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6" onSubmit={saveOutcome}>
            <fieldset className="sm:col-span-2">
              <legend className="text-sm font-semibold text-slate-900">Outcome</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {OUTCOME_OPTIONS[outcome.channel].map(([value, label]) => (
                  <label className="cursor-pointer" key={value}>
                    <input className="peer sr-only" name="outcome_code" required type="radio" value={value} />
                    <span className="inline-flex rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 peer-checked:border-[var(--brand)] peer-checked:bg-[var(--brand-soft)] peer-checked:text-[var(--brand)]">{label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            {outcome.channel === "call" ? <label className="text-sm font-medium">Duration in seconds<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" min="0" name="duration_seconds" type="number" /></label> : null}
            <label className="text-sm font-medium">Next follow-up<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="follow_up_at" type="datetime-local" /></label>
            <label className="text-sm font-medium sm:col-span-2">Notes<textarea className="mt-1 min-h-28 w-full rounded-xl border border-slate-200 p-3" name="notes" placeholder="Customer response, requirement, objection, next step…" /></label>
            <div className="flex justify-end gap-2 sm:col-span-2"><button className="rounded-xl border border-slate-200 px-4 py-2.5 font-semibold" onClick={() => setOutcome(null)} type="button">Skip for now</button><button className="rounded-xl bg-[var(--brand)] px-5 py-2.5 font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Save outcome</button></div>
          </form>
        ) : null}
      </Build360Dialog>

      <Build360Dialog kicker="Add to relationship timeline" onClose={() => setShowActivity(false)} open={showActivity} size="medium" title={`Add activity for ${data.person.display_name}`}>
        <form className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6" onSubmit={addActivity}>
          <label className="text-sm font-medium">What do you want to add?<select className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="activity_type"><option value="follow_up">Follow-up</option><option value="task">Task</option><option value="meeting">Meeting</option><option value="note">Note</option></select></label>
          <label className="text-sm font-medium">Priority<select className="mt-1 w-full rounded-xl border border-slate-200 p-3" defaultValue="normal" name="priority"><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option><option value="low">Low</option></select></label>
          <label className="text-sm font-medium sm:col-span-2">Subject<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="subject" placeholder="What needs to happen?" required /></label>
          <label className="text-sm font-medium">When?<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="scheduled_for" type="datetime-local" /></label>
          <label className="text-sm font-medium sm:col-span-2">Notes<textarea className="mt-1 min-h-24 w-full rounded-xl border border-slate-200 p-3" name="notes" /></label>
          <div className="flex justify-end gap-2 sm:col-span-2"><button className="rounded-xl border border-slate-200 px-4 py-2.5 font-semibold" onClick={() => setShowActivity(false)} type="button">Cancel</button><button className="rounded-xl bg-[var(--brand)] px-5 py-2.5 font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Save</button></div>
        </form>
      </Build360Dialog>

      <Build360ErrorDialog message={error} onClose={() => setError("")} open={Boolean(error)} title={tab === "ai" ? "AI Sales Copilot could not be completed" : "Relationship action could not be completed"} />
      <Build360Toast message={notice} onDismiss={() => setNotice("")} />
    </div>
  );
}


export function AiSalesCopilotPanel({
  insight,
  busy,
  language,
  onGenerate,
  onLanguageChange,
}: Readonly<{
  insight: LeadAiInsight | null;
  busy: boolean;
  language: "english" | "tanglish";
  onGenerate: () => void;
  onLanguageChange: (language: "english" | "tanglish") => void;
}>) {
  const effective = insight?.effective;
  const prep = effective?.call_preparation?.[language] ?? null;
  const summary = language === "tanglish" ? effective?.summary_tanglish : effective?.summary;
  const whatsapp = effective?.message_drafts?.whatsapp?.[language] ?? "";
  const emailBody = effective?.message_drafts?.email?.[language] ?? "";
  const recommendationLabel = language === "tanglish"
    ? effective?.recommended_next_action?.label_tanglish || effective?.recommended_next_action?.label
    : effective?.recommended_next_action?.label;
  const recommendationReason = language === "tanglish"
    ? effective?.recommended_next_action?.reason_tanglish || effective?.recommended_next_action?.reason
    : effective?.recommended_next_action?.reason;
  const needsGeneration = !insight?.exists || insight.stale;

  async function copyText(value: string) {
    if (!value) return;
    await navigator.clipboard?.writeText(value);
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 via-white to-white shadow-sm">
      <div className="border-b border-violet-100 p-5 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-violet-700">AI Sales Copilot</p>
            <h3 className="mt-1 text-xl font-semibold text-slate-950">Prepare the next conversation before you call</h3>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">Grounded in the lead and relationship history already recorded in CRM. It gives talking points and drafts only — it does not send or promise anything automatically.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="inline-flex rounded-xl border border-violet-200 bg-white p-1">
              <button className={`rounded-lg px-3 py-2 text-xs font-semibold ${language === "english" ? "bg-violet-700 text-white" : "text-violet-800"}`} onClick={() => onLanguageChange("english")} type="button">English</button>
              <button className={`rounded-lg px-3 py-2 text-xs font-semibold ${language === "tanglish" ? "bg-violet-700 text-white" : "text-violet-800"}`} onClick={() => onLanguageChange("tanglish")} type="button">Tanglish</button>
            </div>
            {needsGeneration ? <button className="rounded-xl bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={busy} onClick={onGenerate} type="button">{busy ? "Preparing…" : insight?.exists ? "Refresh AI Prep" : "Generate AI Prep"}</button> : <button className="rounded-xl border border-violet-200 bg-white px-4 py-2.5 text-sm font-semibold text-violet-800 disabled:opacity-50" disabled={busy} onClick={onGenerate} type="button">{busy ? "Refreshing…" : "Refresh"}</button>}
          </div>
        </div>
        {insight?.exists ? <div className="mt-4 flex flex-wrap gap-2 text-[11px] font-semibold"><span className={`rounded-full px-2.5 py-1 ${insight.stale ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-800"}`}>{insight.stale ? "NEW CRM HISTORY — REFRESH" : "UP TO DATE"}</span>{insight.override_active ? <span className="rounded-full bg-slate-900 px-2.5 py-1 text-white">HUMAN OVERRIDE ACTIVE</span> : null}</div> : null}
      </div>

      {!insight?.exists || !effective ? (
        <div className="p-5 sm:p-6">
          <EmptyState body="Generate AI Prep to get a grounded summary, next-best action, call talking points, Tanglish version, follow-up drafts and attention signals." title="AI Prep is ready when you are" />
        </div>
      ) : (
        <div className="grid gap-5 p-5 sm:p-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(300px,0.75fr)]">
          <div className="space-y-5">
            <article className="rounded-2xl border border-violet-100 bg-white p-5">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-violet-700">Relationship summary</p>
              <p className="mt-3 text-sm leading-6 text-slate-700">{summary || "No summary is available."}</p>
            </article>

            {effective.recommended_next_action ? (
              <article className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-800">Next best action</p><p className="mt-2 text-lg font-semibold text-emerald-950">{recommendationLabel}</p></div><span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-emerald-800">{Math.round(Number(effective.recommended_next_action.confidence || 0) * 100)}% confidence</span></div>
                <p className="mt-2 text-sm leading-6 text-emerald-900/80">{recommendationReason}</p>
                {effective.recommended_next_action.suggested_due_at ? <p className="mt-3 text-xs font-semibold text-emerald-900">Suggested timing: {formatDateTime(effective.recommended_next_action.suggested_due_at)}</p> : null}
              </article>
            ) : null}

            {prep ? (
              <article className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="flex items-center justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-violet-700">Next call playbook</p><h4 className="mt-1 text-lg font-semibold text-slate-950">What to say on the next call</h4></div><button className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold" onClick={() => void copyText([prep.objective, prep.opening_line, ...prep.talking_points, ...prep.questions, prep.closing_line].join("\n\n"))} type="button">Copy call plan</button></div>
                <CopilotBlock label="Call objective" text={prep.objective} />
                <CopilotBlock label="Opening line" text={prep.opening_line} />
                <CopilotList label="Talk about" items={prep.talking_points} />
                <CopilotList label="Ask these questions" items={prep.questions} />
                <CopilotBlock label="Close the call" text={prep.closing_line} />
                {effective.call_preparation?.grounded_context ? <div className="mt-4 rounded-xl bg-slate-50 p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Latest grounded context</p><p className="mt-2 text-sm leading-6 text-slate-700">{effective.call_preparation.grounded_context}</p></div> : null}
              </article>
            ) : null}

            {effective.message_drafts ? (
              <article className="rounded-2xl border border-slate-200 bg-white p-5">
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-violet-700">Follow-up drafts</p>
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <DraftCard label="WhatsApp" onCopy={() => void copyText(whatsapp)} text={whatsapp} />
                  <DraftCard label={`Email · ${effective.message_drafts.email?.subject || "Follow-up"}`} onCopy={() => void copyText(emailBody)} text={emailBody} />
                </div>
              </article>
            ) : null}
          </div>

          <aside className="space-y-5">
            <article className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Attention signals</p>
              <div className="mt-3 space-y-3">{effective.attention_signals?.length ? effective.attention_signals.map((signal) => <div className={`rounded-xl border p-3 ${signal.severity === "high" ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`} key={signal.code}><p className="text-sm font-semibold text-slate-950">{language === "tanglish" ? signal.label_tanglish || signal.label : signal.label}</p><p className="mt-1 text-xs leading-5 text-slate-600">{language === "tanglish" ? signal.reason_tanglish || signal.reason : signal.reason}</p></div>) : <p className="text-sm text-slate-500">No urgent relationship signal is present in the recorded CRM history.</p>}</div>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Data to improve</p>
              <div className="mt-3 space-y-2">{effective.data_gaps?.length ? effective.data_gaps.map((gap) => <div className="rounded-xl bg-slate-50 px-3 py-2.5 text-sm font-medium text-slate-700" key={gap.code}>{language === "tanglish" ? gap.label_tanglish || gap.label : gap.label}</div>) : <p className="text-sm text-slate-500">No obvious CRM data gap was detected for this lead.</p>}</div>
            </article>
            {insight.citations.length ? <details className="rounded-2xl border border-slate-200 bg-white p-5"><summary className="cursor-pointer text-sm font-semibold text-slate-900">Evidence used · {insight.citations.length}</summary><div className="mt-3 space-y-2">{insight.citations.slice(0, 8).map((citation) => <div className="rounded-xl bg-slate-50 p-3" key={citation.public_id}><p className="text-xs font-semibold text-slate-800">{citation.rank}. {citation.source_label}</p><p className="mt-1 text-xs leading-5 text-slate-500">{citation.excerpt}</p></div>)}</div></details> : null}
            <p className="text-xs leading-5 text-slate-500">{insight.advisory_notice}</p>
          </aside>
        </div>
      )}
    </section>
  );
}

function CopilotBlock({ label, text }: Readonly<{ label: string; text: string }>) {
  return <div className="mt-4"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-1 text-sm leading-6 text-slate-800">{text}</p></div>;
}

function CopilotList({ label, items }: Readonly<{ label: string; items: string[] }>) {
  return <div className="mt-4"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</p><ol className="mt-2 space-y-2">{items.map((item, index) => <li className="flex gap-3 text-sm leading-6 text-slate-800" key={`${label}-${index}`}><span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-100 text-[10px] font-bold text-violet-800">{index + 1}</span><span>{item}</span></li>)}</ol></div>;
}

function DraftCard({ label, text, onCopy }: Readonly<{ label: string; text: string; onCopy: () => void }>) {
  return <div className="rounded-xl bg-slate-50 p-4"><div className="flex items-center justify-between gap-3"><p className="text-sm font-semibold text-slate-900">{label}</p><button className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold" onClick={onCopy} type="button">Copy</button></div><p className="mt-3 whitespace-pre-line text-sm leading-6 text-slate-700">{text || "No draft is available."}</p></div>;
}

function TimelineList({ items }: Readonly<{ items: TimelineItem[] }>) {
  if (!items.length) return <EmptyState body="Calls, WhatsApp, email, tasks, notes and stage changes will appear here in one chronological story." title="No relationship history yet" />;
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-4"><h3 className="font-semibold text-slate-950">Complete relationship timeline</h3><p className="mt-1 text-sm text-slate-600">Newest interaction first.</p></div>
      <div className="divide-y divide-slate-100">
        {items.map((item) => (
          <div className="grid gap-2 px-5 py-4 sm:grid-cols-[110px_minmax(0,1fr)]" key={`${item.kind}-${item.public_id}`}>
            <div><p className="text-xs font-semibold text-slate-500">{new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(item.occurred_at))}</p></div>
            <div>
              <div className="flex flex-wrap items-center gap-2"><RelationshipBadge tone={item.kind === "stage_change" ? "neutral" : "brand"}>{item.activity_type.replaceAll("_", " ")}</RelationshipBadge>{item.outcome_code ? <RelationshipBadge>{item.outcome_code.replaceAll("_", " ")}</RelationshipBadge> : null}</div>
              <p className="mt-2 font-semibold text-slate-950">{item.subject}</p>
              {item.description ? <p className="mt-1 text-sm leading-6 text-slate-600">{item.description}</p> : null}
              <MetaSubmissionDetails metadata={item.channel_metadata || {}} />
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500"><span>{item.created_by_name || "Build360 user"}</span>{item.follow_up_at ? <span>Next {formatDateTime(item.follow_up_at)}</span> : null}{item.attachments.length ? <span>{item.attachments.length} file(s)</span> : null}</div>
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}

function Metric({ label, value }: Readonly<{ label: string; value: ReactNode }>) {
  return <div className="min-w-0 rounded-xl bg-slate-50 p-3"><p className="text-[11px] font-semibold text-slate-500">{label}</p><p className="mt-1 break-words font-semibold text-slate-950">{value}</p></div>;
}

function BusinessList({ title, items, empty }: Readonly<{ title: string; items: Array<{ id: string; title: string; status: string; meta: string; value: string; sub: string }>; empty: string }>) {
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-4"><h3 className="font-semibold text-slate-950">{title}</h3></div>
      {items.length ? <div className="divide-y divide-slate-100">{items.map((item) => <div className="p-5" key={item.id}><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold text-slate-950">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.meta}</p></div><RelationshipBadge tone="brand">{item.status}</RelationshipBadge></div><p className="mt-3 text-lg font-semibold text-slate-950">{item.value}</p><p className="mt-1 text-xs text-slate-500">{item.sub}</p></div>)}</div> : <div className="p-5"><EmptyState body={empty} title="Nothing here yet" /></div>}
    </article>
  );
}

function DetailCard({ title, values }: Readonly<{ title: string; values: Record<string, string> }>) {
  return <article className="rounded-2xl border border-slate-200 bg-white p-5"><h3 className="font-semibold text-slate-950">{title}</h3><dl className="mt-4 divide-y divide-slate-100">{Object.entries(values).map(([label, value]) => <div className="grid gap-1 py-3 sm:grid-cols-[140px_minmax(0,1fr)]" key={label}><dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt><dd className="min-w-0 break-words text-sm leading-6 text-slate-800">{value}</dd></div>)}</dl></article>;
}

export function CrmRelationshipDialog({
  contactPublicId,
  permissions,
  features,
  onClose,
  previousContactPublicId = null,
  nextContactPublicId = null,
  onNavigate,
}: Readonly<{
  contactPublicId: string | null;
  permissions: string[];
  features: Record<string, boolean>;
  onClose: () => void;
  previousContactPublicId?: string | null;
  nextContactPublicId?: string | null;
  onNavigate?: (publicId: string) => void;
}>) {
  const [data, setData] = useState<RelationshipWorkspace | null>(null);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);

  async function load() {
    if (!contactPublicId) return;
    setData(null);
    try {
      setData(await crmRequest<RelationshipWorkspace>(`people/${contactPublicId}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Relationship 360 could not be loaded.");
    }
  }

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      if (contactPublicId) void load();
      else setData(null);
    });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contactPublicId]);

  return (
    <>
      <Build360Drawer
        description="One person, one complete relationship story. Your people list stays exactly where you left it."
        expanded={expanded}
        headerActions={
          <>
            {onNavigate ? (
              <>
                <button
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!previousContactPublicId}
                  onClick={() => previousContactPublicId && onNavigate(previousContactPublicId)}
                  type="button"
                >
                  ← Previous
                </button>
                <button
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!nextContactPublicId}
                  onClick={() => nextContactPublicId && onNavigate(nextContactPublicId)}
                  type="button"
                >
                  Next →
                </button>
              </>
            ) : null}
            <button
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700"
              onClick={() => setExpanded((value) => !value)}
              type="button"
            >
              {expanded ? "Compact view" : "Expand workspace"}
            </button>
          </>
        }
        kicker="Relationship 360"
        onClose={() => {
          setExpanded(false);
          onClose();
        }}
        open={Boolean(contactPublicId)}
        title={data?.person.display_name || "Loading relationship…"}
      >
        {data ? (
          <RelationshipDetail data={data} features={features} onChanged={load} permissions={permissions} />
        ) : (
          <div className="grid h-64 place-items-center px-6 text-sm text-slate-500">Loading person history…</div>
        )}
      </Build360Drawer>
      <Build360ErrorDialog message={error} onClose={() => setError("")} open={Boolean(error)} title="Relationship 360 could not be loaded" />
    </>
  );
}

const META_PEOPLE_SOURCES = [
  { public_id: "meta-source-facebook", code: "FACEBOOK", name: "Facebook", channel_type: "social", sort_order: 20, source_pack_code: "meta" },
  { public_id: "meta-source-instagram", code: "INSTAGRAM", name: "Instagram", channel_type: "social", sort_order: 21, source_pack_code: "meta" },
  { public_id: "meta-source-meta-ads", code: "META_ADS", name: "Meta Ads", channel_type: "ads", sort_order: 22, source_pack_code: "meta" },
] as const;

function crmSourceLabel(value: string | null | undefined) {
  const source = String(value || "").trim().toUpperCase();
  if (source === "FACEBOOK") return "Facebook";
  if (source === "INSTAGRAM") return "Instagram";
  if (source === "META_ADS") return "Meta Ads";
  return value?.trim() || "Direct";
}

function MetaSourcePill({ source }: Readonly<{ source: string | null | undefined }>) {
  const normalized = String(source || "").trim().toUpperCase();
  const isMeta = ["FACEBOOK", "INSTAGRAM", "META_ADS"].includes(normalized);
  return <span className={`inline-flex max-w-full items-center rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${isMeta ? "bg-violet-50 text-violet-800" : "bg-slate-100 text-slate-700"}`}>{crmSourceLabel(source)}</span>;
}

function metadataRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function MetaSubmissionDetails({ metadata }: Readonly<{ metadata: Record<string, unknown> }>) {
  if (String(metadata.provider || "") !== "meta_lead_ads") return null;
  const answers = metadataRecord(metadata.submitted_answers);
  const rows = [
    ["Source", crmSourceLabel(String(metadata.source_code || "META_ADS"))],
    ["Campaign", String(metadata.campaign_name || metadata.campaign_id || "—")],
    ["Ad Set", String(metadata.adset_name || metadata.adset_id || "—")],
    ["Ad", String(metadata.ad_name || metadata.ad_id || "—")],
    ["Form", String(metadata.form_id || "—")],
    ["Meta Lead ID", String(metadata.lead_id || "—")],
  ];
  return (
    <div className="mt-3 rounded-xl border border-violet-100 bg-violet-50/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-bold uppercase tracking-[0.14em] text-violet-800">Meta ad enquiry</p><MetaSourcePill source={String(metadata.source_code || "META_ADS")} /></div>
      <dl className="mt-3 grid gap-x-4 gap-y-2 sm:grid-cols-2">{rows.slice(1).map(([label, value]) => <div className="min-w-0" key={label}><dt className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-0.5 break-words text-xs font-medium text-slate-800">{value}</dd></div>)}</dl>
      {Object.keys(answers).length ? <div className="mt-4 border-t border-violet-100 pt-3"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Submitted ad details</p><dl className="mt-2 grid gap-x-4 gap-y-2 sm:grid-cols-2">{Object.entries(answers).map(([label, value]) => <div className="min-w-0" key={label}><dt className="break-words text-[10px] font-semibold text-slate-500">{label.replaceAll("_", " ")}</dt><dd className="mt-0.5 break-words text-xs font-medium text-slate-800">{String(value || "—")}</dd></div>)}</dl></div> : null}
      <p className="mt-3 text-[10px] leading-4 text-slate-500">Phone and email remain protected on the Person record and are revealed only through authorized communication actions.</p>
    </div>
  );
}

export function CrmPeoplePanel({
  permissions,
  features,
  configuration,
}: Readonly<{
  permissions: string[];
  features: Record<string, boolean>;
  configuration: CrmConfiguration;
}>) {
  const can = (code: string) => permissions.includes(code);
  const defaultSort = can("crm.lead.read") || can("crm.activity.read") ? "next_action" : "name";
  const [data, setData] = useState<PeopleResponse>({ items: [], pagination: { page: 1, page_size: 50, total: 0, has_next: false, has_previous: false }, filters: { search: "", view: "all", stage: "", source: "", owner: "", sort: defaultSort } });
  const [search, setSearch] = useState("");
  const [view, setView] = useState("all");
  const [stage, setStage] = useState("");
  const [source, setSource] = useState("");
  const [owner, setOwner] = useState("");
  const [sort, setSort] = useState(defaultSort);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [density, setDensity] = useState<"comfortable" | "compact">("comfortable");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const debounceRef = useRef<number | null>(null);

  async function loadPeople(targetPage = page) {
    const params = new URLSearchParams({ page: String(targetPage), page_size: "50", view, sort });
    if (search.trim()) params.set("search", search.trim());
    if (stage) params.set("stage", stage);
    if (source) params.set("source", source);
    if (owner) params.set("owner", owner);
    setBusy(true);
    try {
      const next = await crmRequest<PeopleResponse>(`people?${params.toString()}`);
      setData(next);
      setPage(next.pagination.page);
      if (selectedId && !next.items.some((item) => item.person.public_id === selectedId)) setSelectedId(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "People could not be loaded.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => void loadPeople(1), 220);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, view, stage, source, owner, sort]);

  useEffect(() => {
    const syncFromUrl = () => {
      const url = new URL(window.location.href);
      const person = url.searchParams.get("person");
      if (person) setSelectedId(person);
      else setSelectedId(null);
    };
    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, []);

  function updatePersonUrl(publicId: string | null, mode: "push" | "replace" = "push") {
    const url = new URL(window.location.href);
    if (publicId) {
      url.searchParams.set("tab", "people");
      url.searchParams.set("person", publicId);
    } else {
      url.searchParams.delete("person");
    }
    const nextUrl = `${url.pathname}${url.search}${url.hash}`;
    if (mode === "push") window.history.pushState({}, "", nextUrl);
    else window.history.replaceState({}, "", nextUrl);
  }

  function openPerson(publicId: string) {
    setSelectedId(publicId);
    updatePersonUrl(publicId, "push");
  }

  function closePerson() {
    setSelectedId(null);
    updatePersonUrl(null, "replace");
  }

  async function createPerson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const created = await crmRequest<{ public_id: string }>("contacts", {
        method: "POST",
        body: JSON.stringify({
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
          job_title: form.get("job_title"),
          email: form.get("email"),
          phone: form.get("phone"),
          alternate_phone: form.get("alternate_phone"),
          source_code: form.get("source_code"),
          consent_status: "unknown",
        }),
      });
      setShowCreate(false);
      setNotice("Person saved.");
      await loadPeople(1);
      openPerson(created.public_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Person could not be created.");
    } finally {
      setBusy(false);
    }
  }

  const leadStages = useMemo(() => configuration.stages.filter((item) => item.entity_type === "lead"), [configuration.stages]);
  const peopleSourceOptions = useMemo(() => {
    const seen = new Set<string>();
    return [...configuration.lead_sources, ...META_PEOPLE_SOURCES]
      .filter((item) => {
        const code = String(item.code || "").toUpperCase();
        if (!code || seen.has(code)) return false;
        seen.add(code);
        return true;
      });
  }, [configuration.lead_sources]);

  const quickViews = QUICK_VIEWS.filter(([code]) => {
    if (["overdue", "today"].includes(code)) return can("crm.lead.read") || can("crm.activity.read");
    if (["active_leads", "contact_only"].includes(code)) return can("crm.lead.read");
    if (code === "no_next_action") return can("crm.lead.read") || (can("crm.opportunity.read") && can("crm.activity.read"));
    if (code === "converted") return can("crm.lead.read") || can("crm.opportunity.read");
    return true;
  });
  const selectedIndex = selectedId ? data.items.findIndex((item) => item.person.public_id === selectedId) : -1;
  const previousContactPublicId = selectedIndex > 0 ? data.items[selectedIndex - 1]?.person.public_id ?? null : null;
  const nextContactPublicId = selectedIndex >= 0 && selectedIndex < data.items.length - 1 ? data.items[selectedIndex + 1]?.person.public_id ?? null : null;
  const rowPadding = density === "compact" ? "py-2.5" : "py-4";

  return (
    <section className="mt-5 space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-950">People</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {features["crm.meta_ads"] === true && can("integration.meta_leads.read") ? <a className="rounded-xl border border-violet-200 bg-violet-50 px-4 py-2.5 text-sm font-semibold text-violet-800" href="/crm/meta-leads">Meta Ads</a> : null}
            {can("crm.contact.manage") ? <button className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white" onClick={() => setShowCreate(true)} type="button">New person</button> : null}
            <button className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold" onClick={() => setShowFilters((value) => !value)} type="button">Filters{stage || source || owner ? " · active" : ""}</button>
          </div>
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(260px,1fr)_auto_auto] xl:items-center">
          <label className="relative"><span className="sr-only">Search people</span><input className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-[var(--brand)] focus:bg-white" onChange={(event) => setSearch(event.target.value)} placeholder="Search name, exact phone/email, company, lead…" value={search} /></label>
          <select className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm font-medium" onChange={(event) => setSort(event.target.value)} value={sort}>{can("crm.lead.read") || can("crm.activity.read") ? <option value="next_action">Sort: Next action first</option> : null}{can("crm.activity.read") ? <option value="recent">Sort: Recent activity</option> : null}<option value="name">Sort: Name</option><option value="newest">Sort: Newest</option></select>
          <div className="grid grid-cols-2 rounded-xl border border-slate-200 bg-slate-50 p-1 text-xs font-semibold">
            <button className={`rounded-lg px-3 py-2 ${density === "comfortable" ? "bg-white text-slate-950 shadow-sm" : "text-slate-500"}`} onClick={() => setDensity("comfortable")} type="button">Comfortable</button>
            <button className={`rounded-lg px-3 py-2 ${density === "compact" ? "bg-white text-slate-950 shadow-sm" : "text-slate-500"}`} onClick={() => setDensity("compact")} type="button">Compact</button>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
          {quickViews.map(([code, label]) => <button className={`min-w-0 rounded-full px-3 py-2 text-center text-xs font-semibold sm:whitespace-nowrap ${view === code ? "bg-slate-950 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`} key={code} onClick={() => { setView(code); setPage(1); }} type="button">{label}</button>)}
        </div>
        {showFilters ? <div className="mt-4 grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-2 xl:grid-cols-4">{can("crm.lead.read") ? <label className="text-xs font-semibold text-slate-600">Lead stage<select className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2.5 text-sm" onChange={(event) => setStage(event.target.value)} value={stage}><option value="">Any stage</option>{leadStages.map((item) => <option key={item.public_id} value={item.code}>{item.name}</option>)}</select></label> : null}<label className="text-xs font-semibold text-slate-600">Source<select className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2.5 text-sm" onChange={(event) => setSource(event.target.value)} value={source}><option value="">Any source</option>{peopleSourceOptions.map((item) => <option key={item.public_id} value={item.code}>{item.name}</option>)}</select></label><label className="text-xs font-semibold text-slate-600">Owner<select className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2.5 text-sm" onChange={(event) => setOwner(event.target.value)} value={owner}><option value="">Any owner</option><option value="me">Only my records</option></select></label><div className="flex items-end"><button className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold" onClick={() => { setStage(""); setSource(""); setOwner(""); }} type="button">Clear advanced filters</button></div></div> : null}
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3 text-xs text-slate-500 sm:px-5">
          <span>{busy ? "Loading…" : `${data.pagination.total.toLocaleString("en-IN")} people`}</span>
          <span>{sort === "next_action" ? "Next action first" : sort === "recent" ? "Recent activity first" : sort === "newest" ? "Newest first" : "Name order"}</span>
        </div>
        <div className="hidden xl:block">
          <div className="sticky top-0 z-10 grid grid-cols-[minmax(0,1.25fr)_minmax(0,0.72fr)_minmax(0,1.15fr)_minmax(0,0.78fr)_minmax(0,0.95fr)_minmax(0,0.78fr)_minmax(0,0.88fr)] gap-4 border-b border-slate-200 bg-slate-50 px-5 py-3 text-[11px] font-bold uppercase tracking-wide text-slate-500">
            <span>Person</span><span>Source</span><span>Next action</span><span>Relationship</span><span>Company</span><span>Owner</span><span>Last activity</span>
          </div>
          <div className="divide-y divide-slate-100">
            {data.items.map((item) => (
              <button
                aria-label={`Open ${item.person.display_name}`}
                className={`grid w-full grid-cols-[minmax(0,1.25fr)_minmax(0,0.72fr)_minmax(0,1.15fr)_minmax(0,0.78fr)_minmax(0,0.95fr)_minmax(0,0.78fr)_minmax(0,0.88fr)] items-center gap-4 border-l-4 px-4 text-left transition ${rowPadding} ${selectedId === item.person.public_id ? "border-l-[var(--brand)] bg-[var(--brand-soft)]/60" : "border-l-transparent hover:bg-slate-50"}`}
                key={item.person.public_id}
                onClick={() => openPerson(item.person.public_id)}
                type="button"
              >
                <span className="min-w-0"><span className="block truncate font-semibold text-slate-950">{item.person.display_name}</span><span className="mt-0.5 block truncate text-xs text-slate-500">{item.person.phone_masked || item.person.email_masked || item.person.job_title || "No endpoint"}</span></span>
                <span className="min-w-0"><MetaSourcePill source={item.person.source_code} /></span>
                <span className="min-w-0"><span className={`block truncate text-sm font-semibold ${item.is_overdue ? "text-red-700" : item.next_follow_up_at ? "text-slate-800" : "text-violet-700"}`}>{relativeAction(item.next_follow_up_at)}</span><span className="mt-0.5 block truncate text-xs text-slate-500">{item.next_action_label || "No scheduled next step"}</span></span>
                <span className="min-w-0"><RelationshipBadge tone={item.relationship === "lead" ? "brand" : item.relationship === "converted" ? "success" : "neutral"}>{item.relationship === "lead" ? item.active_lead?.stage_name || "Lead" : item.relationship}</RelationshipBadge></span>
                <span className="min-w-0 truncate text-sm text-slate-700">{item.company?.display_name || "Individual"}</span>
                <span className="min-w-0 truncate text-sm text-slate-600">{item.owner.display_name || "Unassigned"}</span>
                <span className="min-w-0 text-xs text-slate-500">{item.last_activity_at ? formatDateTime(item.last_activity_at) : "No activity"}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="divide-y divide-slate-100 xl:hidden">
          {data.items.map((item) => (
            <button aria-label={`Open ${item.person.display_name}`} className={`w-full border-l-4 px-4 text-left transition ${rowPadding} ${selectedId === item.person.public_id ? "border-l-[var(--brand)] bg-[var(--brand-soft)]/60" : "border-l-transparent hover:bg-slate-50"}`} key={item.person.public_id} onClick={() => openPerson(item.person.public_id)} type="button">
              <span className="flex min-w-0 items-start justify-between gap-3"><span className="min-w-0"><span className="block truncate font-semibold text-slate-950">{item.person.display_name}</span><span className="mt-0.5 block truncate text-xs text-slate-500">{item.company?.display_name || "Individual"}{item.owner.display_name ? ` · ${item.owner.display_name}` : ""}</span><span className="mt-2 block"><MetaSourcePill source={item.person.source_code} /></span></span><RelationshipBadge tone={item.relationship === "lead" ? "brand" : item.relationship === "converted" ? "success" : "neutral"}>{item.relationship === "lead" ? item.active_lead?.stage_name || "Lead" : item.relationship}</RelationshipBadge></span>
              <span className={`mt-3 block text-sm font-semibold ${item.is_overdue ? "text-red-700" : item.next_follow_up_at ? "text-slate-800" : "text-violet-700"}`}>{relativeAction(item.next_follow_up_at)}</span>
              <span className="mt-1 block line-clamp-2 text-xs leading-5 text-slate-500">{item.next_action_label || "No scheduled next step"}</span>
            </button>
          ))}
        </div>
        {!data.items.length && !busy ? <div className="p-5"><EmptyState body="Try a different quick view, search or filter." title="No people match this view" /></div> : null}
        <div className="grid grid-cols-[auto_1fr_auto] items-center gap-2 border-t border-slate-200 px-4 py-3 sm:px-5"><button className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold disabled:opacity-40" disabled={!data.pagination.has_previous || busy} onClick={() => { const target = Math.max(page - 1, 1); setPage(target); void loadPeople(target); }} type="button">Previous</button><span className="text-center text-xs text-slate-500">Page {data.pagination.page} · {Math.min((data.pagination.page - 1) * data.pagination.page_size + 1, data.pagination.total || 0)}–{Math.min(data.pagination.page * data.pagination.page_size, data.pagination.total)} of {data.pagination.total.toLocaleString("en-IN")}</span><button className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold disabled:opacity-40" disabled={!data.pagination.has_next || busy} onClick={() => { const target = page + 1; setPage(target); void loadPeople(target); }} type="button">Next</button></div>
      </div>

      <CrmRelationshipDialog
        contactPublicId={selectedId}
        features={features}
        nextContactPublicId={nextContactPublicId}
        onClose={closePerson}
        onNavigate={(publicId) => {
          setSelectedId(publicId);
          updatePersonUrl(publicId, "replace");
        }}
        permissions={permissions}
        previousContactPublicId={previousContactPublicId}
      />

      <Build360Dialog kicker="People" onClose={() => setShowCreate(false)} open={showCreate} size="medium" title="Add a person">
        <form className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6" onSubmit={createPerson}>
          <label className="text-sm font-medium">First name<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="first_name" required /></label>
          <label className="text-sm font-medium">Last name<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="last_name" /></label>
          <label className="text-sm font-medium">Primary phone<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" inputMode="tel" name="phone" /></label>
          <label className="text-sm font-medium">Alternate phone <span className="font-normal text-slate-500">(optional)</span><input className="mt-1 w-full rounded-xl border border-slate-200 p-3" inputMode="tel" name="alternate_phone" /></label>
          <label className="text-sm font-medium">Email<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="email" type="email" /></label>
          <label className="text-sm font-medium">Job title<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="job_title" /></label>
          <label className="text-sm font-medium">Source<select className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="source_code"><option value="">Direct / not specified</option>{peopleSourceOptions.map((item) => <option key={item.public_id} value={item.code}>{item.name}</option>)}</select></label>
          <p className="text-xs leading-5 text-slate-500 sm:col-span-2">Primary phone or email is required. Alternate phone is optional. All protected endpoints stay masked until an authorized communication action.</p>
          <div className="flex justify-end gap-2 sm:col-span-2"><button className="rounded-xl border border-slate-200 px-4 py-2.5 font-semibold" onClick={() => setShowCreate(false)} type="button">Cancel</button><button className="rounded-xl bg-[var(--brand)] px-5 py-2.5 font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Save person</button></div>
        </form>
      </Build360Dialog>

      <Build360ErrorDialog message={error} onClose={() => setError("")} open={Boolean(error)} title="People workspace needs attention" />
      <Build360Toast message={notice} onDismiss={() => setNotice("")} />
    </section>
  );
}

type AccountRow = {
  company: { public_id: string; display_name: string; legal_name: string; external_reference: string; status: string };
  contact_count: number;
  active_lead_count: number;
  open_opportunity_count: number;
  open_pipeline_value: string;
  currency: string;
  last_activity_at: string | null;
};

type AccountWorkspace = {
  company: { public_id: string; display_name: string; legal_name: string; external_reference: string; source_code: string; status: string; notes: string };
  contacts: RelationshipWorkspace["person"][];
  leads: RelationshipWorkspace["leads"];
  opportunities: RelationshipWorkspace["opportunities"];
  recent_activity: Array<{ public_id: string; activity_type: string; status: string; subject: string; notes: string; occurred_at: string; contact_public_id: string | null; created_by_name: string }>;
  summary: { contact_count: number; active_lead_count: number; open_opportunity_count: number; open_pipeline_value: string; currency: string };
};

export function CrmCompaniesPanel({ onOpenPerson }: Readonly<{ onOpenPerson: (publicId: string) => void }>) {
  const [items, setItems] = useState<AccountRow[]>([]);
  const [pagination, setPagination] = useState({ page: 1, total: 0, has_next: false, has_previous: false });
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<AccountWorkspace | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const timerRef = useRef<number | null>(null);

  async function load(page = 1) {
    setBusy(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: "50" });
      if (search.trim()) params.set("search", search.trim());
      const response = await crmRequest<{ items: AccountRow[]; pagination: { page: number; total: number; has_next: boolean; has_previous: boolean } }>(`accounts?${params.toString()}`);
      setItems(response.items);
      setPagination(response.pagination);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Companies could not be loaded.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => void load(1), 220);
    return () => { if (timerRef.current) window.clearTimeout(timerRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  async function openAccount(publicId: string) {
    try {
      setSelected(await crmRequest<AccountWorkspace>(`accounts/${publicId}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Company 360 could not be loaded.");
    }
  }

  return (
    <section className="mt-5 space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between"><div><h2 className="text-2xl font-semibold text-slate-950">Companies</h2></div><input className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm lg:w-auto lg:min-w-[280px]" onChange={(event) => setSearch(event.target.value)} placeholder="Search company or reference…" value={search} /></div></div>
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="hidden grid-cols-[minmax(220px,1.3fr)_100px_100px_110px_150px_150px] gap-3 border-b border-slate-200 bg-slate-50 px-5 py-3 text-[11px] font-bold uppercase tracking-wide text-slate-500 lg:grid"><span>Company</span><span>People</span><span>Leads</span><span>Deals</span><span>Open value</span><span>Last activity</span></div>
        <div className="divide-y divide-slate-100">{items.map((item) => <button className="w-full px-4 py-4 text-left hover:bg-slate-50 sm:px-5" key={item.company.public_id} onClick={() => openAccount(item.company.public_id)} type="button"><span className="grid min-w-0 gap-3 lg:grid-cols-[minmax(220px,1.3fr)_100px_100px_110px_150px_150px] lg:items-center"><span className="min-w-0"><span className="block truncate font-semibold text-slate-950">{item.company.display_name}</span><span className="mt-0.5 block truncate text-xs text-slate-500">{item.company.external_reference || item.company.legal_name || "Account"}</span></span><span className="hidden text-sm text-slate-700 lg:block">{item.contact_count}</span><span className="hidden text-sm text-slate-700 lg:block">{item.active_lead_count}</span><span className="hidden text-sm text-slate-700 lg:block">{item.open_opportunity_count}</span><span className="hidden font-semibold text-slate-900 lg:block">{money(item.open_pipeline_value, item.currency)}</span><span className="hidden text-xs text-slate-500 lg:block">{item.last_activity_at ? formatDateTime(item.last_activity_at) : "None"}</span><span className="grid grid-cols-2 gap-2 text-xs lg:hidden"><span className="rounded-lg bg-slate-50 p-2"><span className="block text-slate-500">People</span><strong className="mt-0.5 block text-slate-900">{item.contact_count}</strong></span><span className="rounded-lg bg-slate-50 p-2"><span className="block text-slate-500">Open deals</span><strong className="mt-0.5 block text-slate-900">{item.open_opportunity_count}</strong></span><span className="rounded-lg bg-slate-50 p-2"><span className="block text-slate-500">Pipeline</span><strong className="mt-0.5 block truncate text-slate-900">{money(item.open_pipeline_value, item.currency)}</strong></span><span className="rounded-lg bg-slate-50 p-2"><span className="block text-slate-500">Last activity</span><strong className="mt-0.5 block truncate text-slate-900">{item.last_activity_at ? formatDateTime(item.last_activity_at) : "None"}</strong></span></span></span></button>)}</div>
        {!items.length && !busy ? <div className="p-5"><EmptyState body="Companies/accounts linked to CRM relationships will appear here." title="No companies found" /></div> : null}
        <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3"><button className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold disabled:opacity-40" disabled={!pagination.has_previous || busy} onClick={() => load(Math.max(1, pagination.page - 1))} type="button">Previous</button><span className="text-xs text-slate-500">{pagination.total.toLocaleString("en-IN")} companies · page {pagination.page}</span><button className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold disabled:opacity-40" disabled={!pagination.has_next || busy} onClick={() => load(pagination.page + 1)} type="button">Next</button></div>
      </div>

      <Build360Dialog description="People, leads, opportunities and recent activity for one company/account." kicker="Company 360" onClose={() => setSelected(null)} open={Boolean(selected)} size="large" title={selected?.company.display_name || "Company"}>
        {selected ? <div className="space-y-5 bg-slate-50 p-5 sm:p-6"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="People" value={selected.summary.contact_count} /><Metric label="Active leads" value={selected.summary.active_lead_count} /><Metric label="Open deals" value={selected.summary.open_opportunity_count} /><Metric label="Open pipeline" value={money(selected.summary.open_pipeline_value, selected.summary.currency)} /></div><article className="rounded-2xl border border-slate-200 bg-white"><div className="border-b border-slate-200 px-5 py-4"><h3 className="font-semibold">People</h3></div><div className="divide-y divide-slate-100">{selected.contacts.map((contact) => <button className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-slate-50" key={contact.public_id} onClick={() => { setSelected(null); onOpenPerson(contact.public_id); }} type="button"><span><span className="block font-semibold text-slate-950">{contact.display_name}</span><span className="mt-1 block text-xs text-slate-500">{contact.job_title || contact.phone_masked || contact.email_masked || "Contact"}</span></span><span className="text-sm font-semibold text-[var(--brand)]">Open 360 →</span></button>)}</div></article><BusinessList empty="No open or historical opportunities." items={selected.opportunities.map((item) => ({ id: item.public_id, title: item.name, status: item.stage.name, meta: `${item.probability_percent}% · ${item.owner_display_name || "Unassigned"}`, value: money(item.amount, item.currency), sub: item.expected_close_date ? `Close ${item.expected_close_date}` : "No close date" }))} title="Deals" /></div> : null}
      </Build360Dialog>
      <Build360ErrorDialog message={error} onClose={() => setError("")} open={Boolean(error)} title="Companies workspace needs attention" />
    </section>
  );
}
