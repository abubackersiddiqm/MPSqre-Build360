"use client";

import Link from "next/link";

import { Build360Dialog, Build360ErrorDialog } from "@/components/build360-dialog";
import { Build360Toast } from "@/components/build360-toast";
import { CrmOpportunityHandoffPanel, type OpportunityHandoffResult } from "./crm-opportunity-handoff-panel";
import { CSSProperties, FormEvent, useEffect, useMemo, useState } from "react";

import { CrmConfigurationPanel, type CrmConfiguration } from "./crm-configuration-panel";
import { CrmAutomationPanel } from "./crm-automation-panel";
import { CrmContactCenterPanel } from "./crm-contact-center-panel";
import { LeadLogbookPanel } from "./lead-logbook-panel";
import {
  CrmCompaniesPanel,
  CrmMyWorkPanel,
  CrmPeoplePanel,
  CrmRelationshipDialog,
  type CrmMyWorkPayload,
} from "./crm-relationship-360";

export type PipelineStage = {
  public_id: string;
  entity_type: "lead" | "opportunity";
  pipeline_public_id: string | null;
  pipeline_code: string;
  pipeline_name: string;
  code: string;
  name: string;
  outcome: string;
  sort_order: number;
  probability_percent: number;
  allowed_next_codes: string[];
  is_initial: boolean;
  allows_conversion: boolean;
};

export type Contact = {
  public_id: string;
  customer_public_id: string | null;
  first_name: string;
  last_name: string;
  display_name: string;
  job_title: string;
  email_masked: string | null;
  phone_masked: string | null;
  alternate_phone_masked: string | null;
  consent_status: string;
  preferred_channel_code: string;
  address: Record<string, unknown>;
  source_code: string;
  tags: string[];
  notes: string;
  custom_fields: Record<string, unknown>;
  owner_membership_public_id: string | null;
  status: string;
  is_primary: boolean;
  is_active: boolean;
  communication_actions: { email: boolean; phone: boolean; alternate_phone?: boolean };
  version: number;
};

export type Customer = {
  public_id: string;
  kind: string;
  display_name: string;
  legal_name: string;
  external_reference: string;
  source_code: string;
  custom_fields: Record<string, unknown>;
  status: string;
  version: number;
  created_at: string;
};

export type Lead = {
  public_id: string;
  title: string;
  description: string;
  source_code: string;
  pipeline_public_id: string | null;
  pipeline_name: string;
  custom_fields: Record<string, unknown>;
  stage: PipelineStage;
  available_transitions: PipelineStage[];
  customer: Customer | null;
  primary_contact: Contact | null;
  owner_membership_public_id: string;
  owner_display_name: string;
  activity_count: number;
  last_activity_at: string | null;
  next_activity_at: string | null;
  estimated_value: string | null;
  currency: string;
  next_follow_up_at: string | null;
  version: number;
  created_at: string;
  converted_at: string | null;
};

export type Opportunity = {
  public_id: string;
  name: string;
  customer: Customer;
  primary_contact: Contact | null;
  source_lead_public_id: string | null;
  pipeline_public_id: string | null;
  pipeline_name: string;
  custom_fields: Record<string, unknown>;
  stage: PipelineStage;
  available_transitions: PipelineStage[];
  amount: string;
  currency: string;
  expected_close_date: string | null;
  probability_percent: number;
  version: number;
  created_at: string;
};

export type Activity = {
  public_id: string;
  activity_type: string;
  status: string;
  direction: string;
  outcome_code: string;
  duration_seconds: number | null;
  channel_metadata: Record<string, unknown>;
  priority: string;
  subject: string;
  notes: string;
  customer_public_id: string | null;
  contact_public_id: string | null;
  lead_public_id: string | null;
  opportunity_public_id: string | null;
  scheduled_for: string | null;
  follow_up_at: string | null;
  occurred_at: string | null;
  completed_at: string | null;
  created_at: string;
  created_by_public_id: string;
  created_by_name: string;
  location: Record<string, unknown>;
  attachments: Array<{
    public_id: string;
    original_name?: string;
    scan_status?: string;
    available?: boolean;
  }>;
  version: number;
};

export type CrmSummary = {
  customers: number;
  contacts: number;
  leads: number;
  opportunities: number;
  overdue_followups: number;
  pipeline_total: string;
  weighted_pipeline: string;
  currency: string;
  lead_stages: Array<{ stage__code: string; stage__name: string; count: number }>;
  opportunity_stages: Array<{
    stage__code: string;
    stage__name: string;
    count: number;
    amount: string | null;
  }>;
};


export type ActivityDashboard = {
  generated_at: string;
  today: number;
  overdue: number;
  upcoming_7d: number;
  followups: number;
  recent_activity_24h: number;
  new_leads_24h: number;
  unassigned_leads: number;
  by_type: Array<{ activity_type: string; count: number }>;
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
  features: Record<string, boolean>;
  summary: CrmSummary;
  contacts: Contact[];
  leads: Lead[];
  customers: Customer[];
  opportunities: Opportunity[];
  stages: PipelineStage[];
  activities: Activity[];
  activityDashboard: ActivityDashboard;
  configuration: CrmConfiguration;
  myWork?: CrmMyWorkPayload;
  defaultTab?: string;
};

type Tab = "my-work" | "people" | "companies" | "pipeline" | "activities" | "automations" | "setup" | "overview" | "contacts" | "contact-center" | "leads" | "customers";

const VALID_TABS = new Set<Tab>(["my-work", "people", "companies", "pipeline", "activities", "automations", "setup", "overview", "contacts", "contact-center", "leads", "customers"]);

function initialTab(value?: string): Tab {
  const aliases: Record<string, Tab> = {
    overview: "my-work",
    contacts: "people",
    "contact-center": "people",
    leads: "people",
    customers: "companies",
  };
  if (!value) return "my-work";
  if (aliases[value]) return aliases[value];
  return VALID_TABS.has(value as Tab) ? (value as Tab) : "my-work";
}

type ErrorEnvelope = {
  message?: string;
  code?: string;
  detail?: string | string[];
  non_field_errors?: string[];
  field_errors?: Record<string, string[]>;
  details?: string[];
  [key: string]: unknown;
};
function crmErrorMessage(error: ErrorEnvelope, fallback: string) {
  const fieldMessage = Object.entries(error.field_errors ?? {})
    .flatMap(([field, messages]) => messages.map((message) => `${field}: ${message}`))
    .join(" ");
  if (fieldMessage) return fieldMessage;
  if (error.message) return error.message;
  if (typeof error.detail === "string") return error.detail;
  if (Array.isArray(error.detail) && error.detail.length) return error.detail.join(" ");
  if (Array.isArray(error.non_field_errors) && error.non_field_errors.length) return error.non_field_errors.join(" ");
  if (Array.isArray(error.details) && error.details.length) return error.details.join(" ");
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
    throw new Error(crmErrorMessage(error, `CRM request failed (${response.status})`));
  }
  return (await response.json()) as T;
}

async function projectRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/projects/${path}`, {
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
    throw new Error(crmErrorMessage(error, `Project handoff failed (${response.status})`));
  }
  return (await response.json()) as T;
}

function money(value: string, currency: string) {
  const numeric = Number(value);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number.isFinite(numeric) ? numeric : 0);
}

function formatDate(value: string | null) {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

type CustomFieldDefinition = CrmConfiguration["custom_fields"][number];

function configuredFieldValue(form: FormData, field: CustomFieldDefinition): unknown {
  const name = `custom_${field.code}`;
  if (field.field_type === "boolean") return form.get(name) === "on";
  if (field.field_type === "multiselect") return form.getAll(name).map(String).filter(Boolean);
  const raw = String(form.get(name) || "").trim();
  if (!raw) return null;
  if (["number", "currency", "percent"].includes(field.field_type)) return Number(raw);
  return raw;
}

function configuredFieldPayload(form: FormData, fields: CustomFieldDefinition[]) {
  return Object.fromEntries(fields.map((field) => [field.code, configuredFieldValue(form, field)]));
}

function ConfiguredFieldInputs({ fields }: Readonly<{ fields: CustomFieldDefinition[] }>) {
  if (!fields.length) return null;
  return <>
    {fields.map((field) => {
      const name = `custom_${field.code}`;
      if (field.field_type === "boolean") return <label className="flex items-center gap-2 text-sm font-medium" key={field.public_id}><input name={name} type="checkbox" /> {field.label}{field.is_required ? " *" : ""}</label>;
      if (field.field_type === "select") return <label className="text-sm font-medium" key={field.public_id}>{field.label}<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name={name} required={field.is_required}><option value="">Choose</option>{field.options.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>;
      if (field.field_type === "multiselect") return <label className="text-sm font-medium" key={field.public_id}>{field.label}<select className="mt-1 min-h-28 w-full rounded-lg border border-[var(--border)] p-3" multiple name={name} required={field.is_required}>{field.options.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>;
      if (field.field_type === "long_text") return <label className="text-sm font-medium sm:col-span-2" key={field.public_id}>{field.label}<textarea className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] p-3" name={name} required={field.is_required} /></label>;
      const inputType = field.field_type === "date" ? "date" : field.field_type === "datetime" ? "datetime-local" : field.field_type === "email" ? "email" : field.field_type === "url" ? "url" : ["number", "currency", "percent"].includes(field.field_type) ? "number" : "text";
      return <label className="text-sm font-medium" key={field.public_id}>{field.label}<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name={name} required={field.is_required} step={inputType === "number" ? "any" : undefined} type={inputType} /></label>;
    })}
  </>;
}

function StageBadge({ stage }: Readonly<{ stage: PipelineStage }>) {
  const terminal = ["won", "converted"].includes(stage.outcome);
  const negative = ["lost", "disqualified"].includes(stage.outcome);
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${
        terminal
          ? "bg-emerald-50 text-emerald-800"
          : negative
            ? "bg-red-50 text-red-800"
            : "bg-amber-50 text-amber-900"
      }`}
    >
      {stage.name}
    </span>
  );
}

function Empty({ children }: Readonly<{ children: string }>) {
  return <p className="rounded-xl border border-dashed border-[var(--border)] p-5 text-sm text-[var(--muted)]">{children}</p>;
}

export function CrmWorkspace(initial: Readonly<Props>) {
  const [tab, setTab] = useState<Tab>(() => initialTab(initial.defaultTab));
  const [summary, setSummary] = useState(initial.summary);
  const [contacts, setContacts] = useState(initial.contacts);
  const [leads, setLeads] = useState(initial.leads);
  const [customers, setCustomers] = useState(initial.customers);
  const [opportunities, setOpportunities] = useState(initial.opportunities);
  const [activities, setActivities] = useState(initial.activities);
  const [activityDashboard, setActivityDashboard] = useState(initial.activityDashboard);
  const [configuration, setConfiguration] = useState(initial.configuration);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [selectedLeadTab, setSelectedLeadTab] = useState<"timeline" | "add">("timeline");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showLeadForm, setShowLeadForm] = useState(false);
  const [showContactForm, setShowContactForm] = useState(false);
  const [showCustomerForm, setShowCustomerForm] = useState(false);
  const [showActivityForm, setShowActivityForm] = useState(false);
  const [handoffResult, setHandoffResult] = useState<OpportunityHandoffResult | null>(null);
  const [relationshipContactId, setRelationshipContactId] = useState<string | null>(null);

  useEffect(() => {
    const syncRelationshipFromUrl = () => {
      const url = new URL(window.location.href);
      if (url.searchParams.get("tab") === "people") {
        setRelationshipContactId(null);
        return;
      }
      setRelationshipContactId(url.searchParams.get("person"));
    };
    syncRelationshipFromUrl();
    window.addEventListener("popstate", syncRelationshipFromUrl);
    return () => window.removeEventListener("popstate", syncRelationshipFromUrl);
  }, []);

  function openRelationship(publicId: string) {
    setRelationshipContactId(publicId);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tab);
    url.searchParams.set("person", publicId);
    window.history.pushState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }

  function closeRelationship() {
    setRelationshipContactId(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("person");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }

  const can = (permission: string) => initial.permissions.includes(permission);
  const feature = (code: string) => initial.features[code] === true;
  const canOpenCrmSetup = can("access.user.manage") && can("crm.configuration.read");
  const canManageCrmSetup = can("access.user.manage") && can("crm.configuration.manage");
  useEffect(() => {
    if (tab !== "setup" || canOpenCrmSetup) return;
    let active = true;
    queueMicrotask(() => {
      if (active) setTab("my-work");
    });
    return () => {
      active = false;
    };
  }, [tab, canOpenCrmSetup]);

  const defaultOpportunityPipeline = configuration.pipelines.find((pipeline) => pipeline.entity_type === "opportunity" && pipeline.is_default);
  const opportunityStages = useMemo(
    () => configuration.stages.filter((stage) => stage.entity_type === "opportunity" && (!defaultOpportunityPipeline || stage.pipeline_public_id === defaultOpportunityPipeline.public_id)),
    [configuration.stages, defaultOpportunityPipeline],
  );
  const leadFields = configuration.custom_fields.filter((field) => field.entity_type === "lead");
  const contactFields = configuration.custom_fields.filter((field) => field.entity_type === "contact");
  const customerFields = configuration.custom_fields.filter((field) => field.entity_type === "customer");
  const leadPipelines = configuration.pipelines.filter((pipeline) => pipeline.entity_type === "lead" && pipeline.stage_count > 0);
  const term = (key: string, fallback: string) => configuration.profile.terminology[key] || fallback;
  const pluralTerm = (key: string, fallback: string) => {
    const value = term(key, fallback);
    return value.toLowerCase().endsWith("s") ? value : `${value}s`;
  };
  const myWork = initial.myWork ?? {
    generated_at: "",
    counts: { overdue: 0, today: 0, tomorrow: 0, this_week: 0, callback_requested: 0, no_next_action: 0, new_uncontacted: 0 },
    queue: [],
  };

  async function refresh() {
    setBusy(true);
    setError("");
    try {
      const [newSummary, newContacts, newLeads, newCustomers, newOpportunities, newActivities, newActivityDashboard] =
        await Promise.all([
          crmRequest<CrmSummary>("summary"),
          can("crm.contact.read")
            ? crmRequest<{ items: Contact[] }>("contacts?limit=100")
            : Promise.resolve({ items: [] }),
          can("crm.lead.read")
            ? crmRequest<{ items: Lead[] }>("leads?limit=100")
            : Promise.resolve({ items: [] }),
          can("crm.customer.read")
            ? crmRequest<{ items: Customer[] }>("customers?limit=100")
            : Promise.resolve({ items: [] }),
          can("crm.opportunity.read")
            ? crmRequest<{ items: Opportunity[] }>("opportunities?limit=100")
            : Promise.resolve({ items: [] }),
          can("crm.activity.read")
            ? crmRequest<{ items: Activity[] }>("activities?limit=100")
            : Promise.resolve({ items: [] }),
          can("crm.activity.read") && feature("crm.analytics")
            ? crmRequest<ActivityDashboard>("activities/dashboard")
            : Promise.resolve({ generated_at: "", today: 0, overdue: 0, upcoming_7d: 0, followups: 0, recent_activity_24h: 0, new_leads_24h: 0, unassigned_leads: 0, by_type: [] }),
        ]);
      setSummary(newSummary);
      setContacts(newContacts.items);
      setLeads(newLeads.items);
      setCustomers(newCustomers.items);
      setOpportunities(newOpportunities.items);
      setActivities(newActivities.items);
      setActivityDashboard(newActivityDashboard);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "CRM data could not be refreshed.");
    } finally {
      setBusy(false);
    }
  }


  async function submitContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim();
    const phone = String(form.get("phone") || "").trim();
    const alternatePhone = String(form.get("alternate_phone") || "").trim();
    try {
      if (can("crm.contact.read") && (email || phone)) {
        const params = new URLSearchParams();
        if (email) params.set("email", email);
        if (phone) params.set("phone", phone);
        if (alternatePhone) params.set("alternate_phone", alternatePhone);
        const duplicates = await crmRequest<{ items: Contact[] }>(`contacts/duplicates?${params.toString()}`);
        const duplicate = duplicates.items[0];
        if (duplicate) {
          throw new Error(`Possible duplicate contact exists: ${duplicate.display_name || "existing contact"}. Search and reuse it instead of creating another record.`);
        }
      }
      await crmRequest<Contact>("contacts", {
        method: "POST",
        body: JSON.stringify({
          customer_public_id: form.get("customer_public_id") || null,
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
          job_title: form.get("job_title"),
          email,
          phone,
          alternate_phone: alternatePhone,
          consent_status: form.get("consent_status"),
          preferred_channel_code: form.get("preferred_channel_code"),
          address: String(form.get("address") || "").trim() ? { formatted: String(form.get("address") || "").trim() } : {},
          source_code: form.get("source_code"),
          tags: String(form.get("tags") || "").split(",").map((value) => value.trim()).filter(Boolean),
          notes: form.get("notes"),
          custom_fields: configuredFieldPayload(form, contactFields),
          is_primary: form.get("is_primary") === "on",
        }),
      });
      setNotice("Contact saved in protected CRM storage. Phone/email remain masked until an authorized reveal action.");
      setShowContactForm(false);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Contact could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function dialContact(contact: Contact, relation?: { type: "lead" | "customer" | "opportunity"; id: string; label: string }) {
    if (!can("crm.contact.reveal")) {
      setError("You do not have permission to reveal protected contact details for calling.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const revealed = await crmRequest<{ phone?: string; email?: string }>(`contacts/${contact.public_id}/reveal`, {
        method: "POST",
        body: JSON.stringify({ reason_code: "crm_call" }),
      });
      const phone = (revealed.phone ?? "").trim();
      if (!phone) throw new Error("This contact does not have a callable phone number.");
      window.location.assign(`tel:${phone.replace(/[^+0-9]/g, "")}`);
      if (can("crm.activity.manage")) {
        await crmRequest<Activity>("activities", {
          method: "POST",
          body: JSON.stringify({
            contact_public_id: contact.public_id,
            activity_type: "call",
            status: "planned",
            direction: "outbound",
            outcome_code: "started",
            occurred_at: new Date().toISOString(),
            subject: `Call ${contact.display_name || relation?.label || "contact"}`,
            notes: "Dial initiated from Build360. Record the final outcome in Contact Center after the call.",
            channel_metadata: { source: "crm_quick_action", launch_mode: "device_handoff" },
            ...(relation?.type === "lead" ? { lead_public_id: relation.id } : {}),
            ...(relation?.type === "customer" ? { customer_public_id: relation.id } : {}),
            ...(relation?.type === "opportunity" ? { opportunity_public_id: relation.id } : {}),
          }),
        });
      }
      setNotice("Device dialer opened. Call action was audited; update the CRM activity after the call.");
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Dial action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function convertContactToLead(contact: Contact) {
    setBusy(true); setError(""); setNotice("");
    try {
      const lead = await crmRequest<Lead & { created: boolean }>(`contacts/${contact.public_id}/convert-lead`, {
        method: "POST",
        body: JSON.stringify({
          title: `${contact.display_name || "Contact"} enquiry`,
          source_code: contact.source_code,
        }),
      });
      setNotice(lead.created ? `${contact.display_name} converted to a lead without duplicating the contact.` : `An active lead already exists for ${contact.display_name}; Build360 reused it.`);
      setTab("leads");
      await refresh();
      setSelectedLead(lead);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Contact could not be converted to a lead.");
    } finally {
      setBusy(false);
    }
  }

  async function whatsappContact(contact: Contact, lead: Lead) {
    if (!feature("crm.whatsapp")) {
      setError("WhatsApp is disabled for this company subscription.");
      return;
    }
    if (!can("crm.contact.reveal")) {
      setError("You do not have permission to reveal protected contact details for WhatsApp.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      const revealed = await crmRequest<{ phone?: string; email?: string }>(`contacts/${contact.public_id}/reveal`, {
        method: "POST",
        body: JSON.stringify({ reason_code: "crm_whatsapp" }),
      });
      const digits = (revealed.phone ?? "").replace(/\D/g, "");
      if (!digits) throw new Error("This contact does not have a WhatsApp-capable phone number.");
      window.open(`https://wa.me/${digits}`, "_blank", "noopener,noreferrer");
      if (can("crm.activity.manage")) {
        await crmRequest<Activity>("activities", {
          method: "POST",
          body: JSON.stringify({
            contact_public_id: contact.public_id,
            lead_public_id: lead.public_id,
            activity_type: "whatsapp",
            status: "planned",
            direction: "outbound",
            outcome_code: "started",
            occurred_at: new Date().toISOString(),
            priority: "normal",
            subject: `WhatsApp ${contact.display_name}`,
            notes: "WhatsApp conversation opened from Build360. Record the outcome in Contact Center or the Lead Log Book.",
            channel_metadata: { source: "crm_quick_action", launch_mode: "device_handoff" },
          }),
        });
      }
      setNotice("WhatsApp opened and the action was added to CRM activity history.");
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "WhatsApp action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function submitLead(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const createdLead = await crmRequest<Lead>("leads", {
        method: "POST",
        body: JSON.stringify({
          title: form.get("title"),
          customer_display_name: form.get("customer_display_name"),
          contact_first_name: form.get("contact_first_name"),
          contact_last_name: form.get("contact_last_name"),
          contact_email: form.get("contact_email"),
          contact_phone: form.get("contact_phone"),
          contact_alternate_phone: form.get("contact_alternate_phone"),
          source_code: form.get("source_code"),
          pipeline_public_id: form.get("pipeline_public_id") || null,
          custom_fields: configuredFieldPayload(form, leadFields),
          estimated_value: form.get("estimated_value") || null,
          next_follow_up_at: form.get("next_follow_up_at") || null,
          description: form.get("description"),
        }),
      });
      setNotice("Person saved and lead created. Build360 keeps one contact master and links the lead to it.");
      setShowLeadForm(false);
      await refresh();
      if (createdLead.primary_contact?.public_id) {
        setTab("people");
        openRelationship(createdLead.primary_contact.public_id);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lead could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function submitCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await crmRequest<Customer>("customers", {
        method: "POST",
        body: JSON.stringify({
          kind: form.get("kind"),
          display_name: form.get("display_name"),
          legal_name: form.get("legal_name"),
          external_reference: form.get("external_reference"),
          source_code: form.get("source_code"),
          notes: form.get("notes"),
          custom_fields: configuredFieldPayload(form, customerFields),
        }),
      });
      setNotice("Customer created successfully.");
      setShowCustomerForm(false);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Customer could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function submitActivity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const relation = String(form.get("relation") || "");
    const [relationType, relationId] = relation.split(":");
    const activityType = String(form.get("activity_type") || "");
    const locationText = String(form.get("location") || "").trim();
    try {
      await crmRequest<Activity>("activities", {
        method: "POST",
        body: JSON.stringify({
          activity_type: activityType,
          status: form.get("status"),
          subject: form.get("subject"),
          notes: form.get("notes"),
          scheduled_for: form.get("scheduled_for") || null,
          follow_up_at: form.get("follow_up_at") || null,
          priority: form.get("priority") || "normal",
          location: locationText ? { address: locationText } : {},
          ...(relationType === "lead" ? { lead_public_id: relationId } : {}),
          ...(relationType === "opportunity" ? { opportunity_public_id: relationId } : {}),
          ...(relationType === "customer" ? { customer_public_id: relationId } : {}),
        }),
      });
      setNotice("Activity added to the CRM timeline.");
      setShowActivityForm(false);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Activity could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function transitionLead(lead: Lead, target: PipelineStage) {
    setBusy(true);
    setError("");
    try {
      await crmRequest<Lead>(`leads/${lead.public_id}/transition`, {
        method: "POST",
        body: JSON.stringify({
          target_stage_public_id: target.public_id,
          expected_version: lead.version,
        }),
      });
      setNotice(`${lead.title} moved to ${target.name}.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lead transition failed.");
    } finally {
      setBusy(false);
    }
  }

  async function convert(lead: Lead) {
    setBusy(true);
    setError("");
    try {
      await crmRequest(`leads/${lead.public_id}/convert`, {
        method: "POST",
        body: JSON.stringify({ expected_version: lead.version }),
      });
      setNotice(`${lead.title} converted into a customer and opportunity exactly once.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lead conversion failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createProjectFromOpportunity(opportunity: Opportunity, preconstruction = false) {
    setBusy(true);
    setError("");
    setNotice("");
    setHandoffResult(null);
    try {
      const project = await projectRequest<Omit<OpportunityHandoffResult, "opportunity_public_id">>(
        `from-crm-opportunity/${opportunity.public_id}`,
        {
          method: "POST",
          body: JSON.stringify({ mode: preconstruction ? "preconstruction" : "award" }),
        },
      );
      setHandoffResult({ ...project, opportunity_public_id: opportunity.public_id });
      setNotice(`${project.message} ${project.code} · ${project.name}.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Project workspace creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function transitionOpportunity(opportunity: Opportunity, target: PipelineStage) {
    setBusy(true);
    setError("");
    try {
      await crmRequest<Opportunity>(`opportunities/${opportunity.public_id}/transition`, {
        method: "POST",
        body: JSON.stringify({
          target_stage_public_id: target.public_id,
          expected_version: opportunity.version,
        }),
      });
      setNotice(`${opportunity.name} moved to ${target.name}.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Opportunity transition failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-5 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1500px]">
        <header className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm sm:p-7">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">MPSqre Build360 · CRM</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Customer relationships & revenue</h1>
              <p className="mt-2 text-sm text-[var(--muted)]">{initial.company.display_name} · One person, one relationship story · {initial.company.timezone}</p>
            </div>
            <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:flex-wrap">
              <button className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-semibold disabled:opacity-50" disabled={busy} onClick={refresh} type="button">{busy ? "Working…" : "Refresh"}</button>
              <Link className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-semibold" href="/platform">Back to workspace</Link>
              {can("crm.lead.manage") ? <button className="col-span-2 rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white sm:col-span-1" onClick={() => setShowLeadForm(true)} type="button">{`New ${term("lead", "Lead")}`}</button> : null}
            </div>
          </div>
        </header>

        {handoffResult ? (
          <CrmOpportunityHandoffPanel
            canOpenDesign={can("design.document.read")}
            canOpenEstimation={can("estimation.estimate.read")}
            onClose={() => setHandoffResult(null)}
            result={handoffResult}
          />
        ) : null}

        <nav className="mt-5 grid grid-cols-2 gap-2 rounded-xl border border-[var(--border)] bg-white p-2 sm:grid-cols-3 md:flex md:overflow-x-auto" aria-label="CRM workspace">
          {([
            ["my-work", "My Work"],
            ...(can("crm.contact.read") ? [["people", "People"]] : []),
            ...(can("crm.customer.read") ? [["companies", "Companies"]] : []),
            ...(can("crm.opportunity.read") ? [["pipeline", term("pipeline", "Pipeline")]] : []),
            ...(can("crm.activity.read") ? [["activities", "Activities"]] : []),
            ...(feature("crm.automation") && can("crm.automation.read") ? [["automations", "Automations"]] : []),
            ...(canOpenCrmSetup ? [["setup", "CRM setup"]] : []),
          ] as Array<[Tab, string]>).map(([item, label]) => (
            <button className={`min-w-0 rounded-lg px-3 py-2.5 text-center text-sm font-semibold md:whitespace-nowrap ${tab === item ? "bg-[var(--brand)] text-white" : "text-[var(--muted)] hover:bg-slate-50"}`} key={item} onClick={() => setTab(item)} type="button">{label}</button>
          ))}
        </nav>

        {tab === "my-work" ? (
          <CrmMyWorkPanel initial={myWork} onOpenPerson={openRelationship} />
        ) : null}

        {tab === "people" && can("crm.contact.read") ? (
          <CrmPeoplePanel configuration={configuration} features={initial.features} permissions={initial.permissions} />
        ) : null}

        {tab === "companies" && can("crm.customer.read") ? (
          <CrmCompaniesPanel onOpenPerson={openRelationship} />
        ) : null}

        {tab === "overview" ? (
          <section className="mt-5 space-y-5">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
              {[
                [pluralTerm("customer", "Customer"), summary.customers], [pluralTerm("contact", "Contact"), summary.contacts], [pluralTerm("lead", "Lead"), summary.leads], [pluralTerm("opportunity", "Opportunity"), summary.opportunities], ["Overdue follow-ups", summary.overdue_followups], [`Weighted ${term("pipeline", "Pipeline").toLowerCase()}`, money(summary.weighted_pipeline, summary.currency)],
              ].map(([label, value]) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={String(label)}><p className="text-sm text-[var(--muted)]">{label}</p><p className="mt-2 text-2xl font-semibold">{value}</p></article>)}
            </div>
            <div className="grid gap-5 lg:grid-cols-2">
              <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><h2 className="text-lg font-semibold">{term("lead", "Lead")} funnel</h2><div className="mt-4 space-y-3">{summary.lead_stages.length ? summary.lead_stages.map((stage, index) => <div className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3" key={`${stage.stage__code}-${index}`}><span>{stage.stage__name}</span><strong>{stage.count}</strong></div>) : <Empty>{`${term("lead", "Lead")} funnel will populate after your first record.`}</Empty>}</div></article>
              <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"><h2 className="text-lg font-semibold">{term("opportunity", "Opportunity")} {term("pipeline", "Pipeline").toLowerCase()}</h2><p className="mt-1 text-sm text-[var(--muted)]">Total {money(summary.pipeline_total, summary.currency)}</p><div className="mt-4 space-y-3">{summary.opportunity_stages.length ? summary.opportunity_stages.map((stage, index) => <div className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3" key={`${stage.stage__code}-${index}`}><span>{stage.stage__name} · {stage.count}</span><strong>{money(stage.amount || "0", summary.currency)}</strong></div>) : <Empty>{`Convert a qualified ${term("lead", "Lead").toLowerCase()} to create the first ${term("opportunity", "Opportunity").toLowerCase()}.`}</Empty>}</div></article>
            </div>
          </section>
        ) : null}


        {tab === "contact-center" && can("crm.contact_center.use") && can("crm.contact.read") && can("crm.activity.read") ? (
          <CrmContactCenterPanel contacts={contacts} features={initial.features} permissions={initial.permissions} />
        ) : null}

        {tab === "contacts" ? (
          <section className="mt-5 space-y-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div><h2 className="text-2xl font-semibold">{pluralTerm("contact", "Contact")} & communication</h2><p className="mt-1 text-sm text-[var(--muted)]">Keep contact details, conversations and follow-ups together.</p></div>
              {can("crm.contact.manage") ? <button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" onClick={() => setShowContactForm((value) => !value)} type="button">Save contact</button> : null}
            </div>
            {showContactForm ? <form className="grid gap-4 rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm sm:grid-cols-2 lg:grid-cols-4" onSubmit={submitContact}>
              <label className="text-sm font-medium">Customer (optional)<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="customer_public_id"><option value="">Unlinked prospect</option>{customers.map((customer) => <option key={customer.public_id} value={customer.public_id}>{customer.display_name}</option>)}</select></label>
              <label className="text-sm font-medium">First name<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="first_name" required /></label>
              <label className="text-sm font-medium">Last name<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="last_name" /></label>
              <label className="text-sm font-medium">Job title<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="job_title" /></label>
              <label className="text-sm font-medium">Primary phone<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" inputMode="tel" name="phone" placeholder="+91..." /></label>
              <label className="text-sm font-medium">Alternate phone<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" inputMode="tel" name="alternate_phone" placeholder="Optional" /></label>
              <label className="text-sm font-medium">Email<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="email" type="email" /></label>
              <label className="text-sm font-medium">Consent<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="consent_status" defaultValue="unknown"><option value="unknown">Unknown</option><option value="granted">Granted</option><option value="withdrawn">Withdrawn</option></select></label>
              <label className="text-sm font-medium">Preferred channel<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="preferred_channel_code" defaultValue="phone"><option value="phone">Phone</option><option value="whatsapp">WhatsApp</option><option value="email">Email</option><option value="sms">SMS</option></select></label>
              <label className="text-sm font-medium">Source<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="source_code"><option value="">Direct / not specified</option>{configuration.lead_sources.map((source) => <option key={source.public_id} value={source.code}>{source.name}</option>)}</select></label>
              <label className="text-sm font-medium">Tags<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="tags" placeholder="builder, premium, coimbatore" /></label>
              <label className="text-sm font-medium sm:col-span-2">Address<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="address" /></label>
              <label className="text-sm font-medium sm:col-span-2">Contact notes<textarea className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] p-3" name="notes" /></label>
              <ConfiguredFieldInputs fields={contactFields} />
              <label className="flex items-center gap-2 text-sm font-medium sm:col-span-2"><input name="is_primary" type="checkbox" /> Primary contact for this customer</label>
              <div className="flex justify-end gap-2 sm:col-span-2 lg:col-span-4"><button className="rounded-lg border border-[var(--border)] px-4 py-2" onClick={() => setShowContactForm(false)} type="button">Cancel</button><button className="rounded-lg bg-[var(--brand)] px-5 py-2 font-semibold text-white" disabled={busy} type="submit">Save protected contact</button></div>
            </form> : null}
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{contacts.length ? contacts.map((contact) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={contact.public_id}><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">{contact.display_name}</h3><p className="mt-1 text-sm text-[var(--muted)]">{contact.job_title || "Contact"}</p></div><span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold uppercase">{contact.consent_status}</span></div><p className="mt-4 text-sm text-[var(--muted)]">{contact.phone_masked || "No phone"}{contact.alternate_phone_masked ? ` · Alt ${contact.alternate_phone_masked}` : ""} · {contact.email_masked || "No email"}</p>{contact.source_code || contact.tags.length ? <div className="mt-3 flex flex-wrap gap-2"><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase">{contact.source_code || "direct"}</span>{contact.tags.slice(0,4).map((tag)=><span className="rounded-full bg-[var(--brand-soft)] px-2 py-1 text-[10px] font-semibold text-[var(--brand)]" key={tag}>{tag}</span>)}</div> : null}<div className="mt-4 flex flex-wrap gap-2">{contact.communication_actions.phone && can("crm.contact.reveal") ? <button className="rounded-lg bg-[var(--brand)] px-3 py-2 text-sm font-semibold text-white" disabled={busy} onClick={() => dialContact(contact, contact.customer_public_id ? { type: "customer", id: contact.customer_public_id, label: contact.display_name } : undefined)} type="button">Dial now</button> : null}{can("crm.lead.manage") ? <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} onClick={() => convertContactToLead(contact)} type="button">Convert to Lead</button> : null}</div></article>) : <div className="md:col-span-2 xl:col-span-3"><Empty>No contacts yet. Save the first customer/prospect contact here.</Empty></div>}</div>
          </section>
        ) : null}

        {tab === "leads" ? (
          <section className="mt-5 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><p className="text-xs font-bold uppercase tracking-[.14em] text-[var(--brand)]">{`${term("lead", "Lead")} workspace`}</p><p className="mt-1 text-sm text-[var(--muted)]">Manage enquiries, follow-ups and progress in one place.</p></div>
              {can("integration.meta_leads.read") && feature("crm.meta_ads") ? <Link className="rounded-xl border border-[var(--border)] bg-white px-4 py-2.5 text-sm font-semibold text-[var(--brand)]" href="/crm/meta-leads">Meta Ads →</Link> : null}
            </div>
            <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {leads.length ? leads.map((lead) => <article className="rounded-[24px] border border-[var(--border)] bg-white p-5 shadow-sm" key={lead.public_id}>
                <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="text-[10px] font-bold uppercase tracking-[.14em] text-[var(--brand)]">{lead.source_code || "DIRECT"}</p><h2 className="mt-1 truncate text-lg font-semibold"><button className="max-w-full truncate text-left hover:text-[var(--brand)]" onClick={() => { setSelectedLeadTab("timeline"); setSelectedLead(lead); }} type="button">{lead.title}</button></h2><p className="mt-1 text-sm text-[var(--muted)]">{lead.customer?.display_name || "Unlinked prospect"}</p></div><StageBadge stage={lead.stage} /></div>
                <div className="mt-4 rounded-2xl bg-slate-50 p-4"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[var(--muted)]">Current context</p><p className="mt-1 line-clamp-3 text-sm leading-5">{lead.description || "No lead note yet. Open the Log Book to capture the latest customer context."}</p></div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-[var(--muted)]">Assigned</dt><dd className="truncate font-medium">{lead.owner_display_name || "Current CRM owner"}</dd></div><div><dt className="text-[var(--muted)]">Value</dt><dd className="font-medium">{lead.estimated_value ? money(lead.estimated_value, lead.currency) : "Not estimated"}</dd></div><div><dt className="text-[var(--muted)]">Last activity</dt><dd className="font-medium">{formatDate(lead.last_activity_at)}</dd></div><div><dt className="text-[var(--muted)]">Next activity</dt><dd className="font-medium">{formatDate(lead.next_activity_at || lead.next_follow_up_at)}</dd></div></dl>
                <div className="mt-4 flex items-center justify-between rounded-xl border border-[var(--border)] px-3 py-2"><span className="text-xs text-[var(--muted)]">Activity history</span><strong className="text-sm">{lead.activity_count}</strong></div>
                {lead.primary_contact ? <div className="mt-4 rounded-xl border border-[var(--border)] p-3 text-sm"><p className="font-medium">{lead.primary_contact.display_name}</p><p className="mt-1 text-[var(--muted)]">{lead.primary_contact.email_masked || "No email"} · {lead.primary_contact.phone_masked || "No phone"}</p><div className="mt-3 flex flex-wrap gap-2">{lead.primary_contact.communication_actions.phone && can("crm.contact.reveal") ? <button className="rounded-lg bg-slate-950 px-3 py-2 text-xs font-semibold text-white" disabled={busy} onClick={() => dialContact(lead.primary_contact!, { type: "lead", id: lead.public_id, label: lead.title })} type="button">Call</button> : null}{lead.primary_contact.communication_actions.phone && can("crm.contact.reveal") && feature("crm.whatsapp") ? <button className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800" disabled={busy} onClick={() => whatsappContact(lead.primary_contact!, lead)} type="button">WhatsApp</button> : null}</div></div> : null}
                <div className="mt-4 flex flex-wrap gap-2"><button className="rounded-lg bg-[var(--brand)] px-3 py-2 text-xs font-semibold text-white" onClick={() => { setSelectedLeadTab("timeline"); setSelectedLead(lead); }} type="button">Open Log Book</button>{can("crm.activity.manage") ? <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold" onClick={() => { setSelectedLeadTab("add"); setSelectedLead(lead); }} type="button">Add activity</button> : null}{can("crm.lead.transition") ? lead.available_transitions.filter((stage) => stage.outcome !== "converted").map((stage) => <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold" disabled={busy} key={stage.public_id} onClick={() => transitionLead(lead, stage)} type="button">{stage.name}</button>) : null}{can("crm.lead.convert") && lead.stage.allows_conversion ? <button className="rounded-lg border border-[var(--brand)] px-3 py-2 text-xs font-semibold text-[var(--brand)]" disabled={busy} onClick={() => convert(lead)} type="button">Convert</button> : null}</div>
              </article>) : <div className="lg:col-span-2 xl:col-span-3"><Empty>No records yet. Create the first CRM lead to start the pipeline.</Empty></div>}
            </div>
            {selectedLead ? <LeadLogbookPanel initialTab={selectedLeadTab} lead={leads.find((item)=>item.public_id===selectedLead.public_id) ?? selectedLead} onChanged={refresh} onClose={() => setSelectedLead(null)} permissions={initial.permissions} features={initial.features} /> : null}
          </section>
        ) : null}

        {tab === "customers" ? (
          <section className="mt-5">
            <div className="mb-4 flex justify-end">{can("crm.customer.manage") ? <button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" onClick={() => setShowCustomerForm((value) => !value)} type="button">{`New ${term("customer", "Customer")}`}</button> : null}</div>
            {showCustomerForm ? <form className="mb-5 grid gap-4 rounded-2xl border border-[var(--border)] bg-white p-5 sm:grid-cols-2 lg:grid-cols-3" onSubmit={submitCustomer}><label className="text-sm font-medium">Kind<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="kind"><option value="organization">Organization</option><option value="person">Person</option></select></label><label className="text-sm font-medium">Display name<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="display_name" required /></label><label className="text-sm font-medium">Legal name<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="legal_name" /></label><label className="text-sm font-medium">External reference<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="external_reference" /></label><label className="text-sm font-medium">Source<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="source_code"><option value="">Direct / not specified</option>{configuration.lead_sources.map((source) => <option key={source.public_id} value={source.code}>{source.name}</option>)}</select></label><label className="text-sm font-medium">Notes<textarea className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="notes" /></label><ConfiguredFieldInputs fields={customerFields} /><div className="sm:col-span-2 lg:col-span-3 flex justify-end"><button className="rounded-lg bg-[var(--brand)] px-5 py-2 font-semibold text-white" type="submit">{`Create ${term("customer", "Customer")}`}</button></div></form> : null}
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{customers.length ? customers.map((customer) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={customer.public_id}><div className="flex items-center justify-between"><h2 className="font-semibold">{customer.display_name}</h2><span className="text-xs font-semibold uppercase text-[var(--brand)]">{customer.kind}</span></div><p className="mt-2 text-sm text-[var(--muted)]">{customer.legal_name || "No separate legal name"}</p><p className="mt-4 text-xs uppercase tracking-wide text-[var(--muted)]">{customer.source_code || "Direct"} · {customer.status}</p></article>) : <div className="sm:col-span-2 xl:col-span-3"><Empty>No customers are registered yet.</Empty></div>}</div>
          </section>
        ) : null}

        {tab === "pipeline" ? (
          <section className="mt-5 grid grid-cols-1 gap-4 md:overflow-x-auto md:[grid-template-columns:var(--pipeline-cols)]" style={{ "--pipeline-cols": `repeat(${Math.max(opportunityStages.length, 1)}, minmax(270px, 1fr))` } as CSSProperties}>
            {opportunityStages.length ? opportunityStages.map((stage) => (
              <article className="min-h-[320px] rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm" key={stage.public_id}>
                <div className="flex items-center justify-between"><h2 className="font-semibold">{stage.name}</h2><span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold">{opportunities.filter((item) => item.stage.public_id === stage.public_id).length}</span></div>
                <div className="mt-4 space-y-2">
                  {opportunities.filter((item) => item.stage.public_id === stage.public_id).map((opportunity) => (
                    <div className="rounded-xl border border-[var(--border)] bg-white p-3.5" key={opportunity.public_id}>
                      <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate font-semibold text-slate-950">{opportunity.name}</p>{opportunity.primary_contact ? <button className="mt-1 text-left text-sm font-medium text-[var(--brand)] hover:underline" onClick={() => opportunity.primary_contact?.public_id && openRelationship(opportunity.primary_contact.public_id)} type="button">{opportunity.primary_contact.display_name}</button> : <p className="mt-1 text-sm text-[var(--muted)]">{opportunity.customer.display_name}</p>}</div><span className="text-xs font-semibold text-slate-500">{opportunity.probability_percent}%</span></div>
                      <div className="mt-3 flex items-end justify-between gap-3"><div><p className="text-lg font-semibold">{money(opportunity.amount, opportunity.currency)}</p><p className="mt-0.5 text-xs text-[var(--muted)]">{opportunity.expected_close_date || "No close date"}</p></div></div>
                      <div className="mt-3 flex flex-wrap gap-1.5">{can("crm.opportunity.transition") ? opportunity.available_transitions.map((target) => <button className="rounded-lg border border-[var(--border)] px-2.5 py-1.5 text-xs font-semibold" disabled={busy} key={target.public_id} onClick={() => transitionOpportunity(opportunity, target)} type="button">{target.name}</button>) : null}{opportunity.stage.outcome !== "lost" && feature("module.delivery") && can("crm.opportunity.manage") && can("project.project.manage") ? <button className="rounded-lg bg-[var(--brand)] px-2.5 py-1.5 text-xs font-semibold text-white" disabled={busy} onClick={() => createProjectFromOpportunity(opportunity, opportunity.stage.outcome !== "won")} type="button">{opportunity.stage.outcome === "won" ? "Continue project" : "Start preconstruction"}</button> : null}</div>
                    </div>
                  ))}
                </div>
              </article>
            )) : <Empty>{canOpenCrmSetup ? `${term("pipeline", "Pipeline")} stages are not configured. Open CRM setup to add stages.` : `${term("pipeline", "Pipeline")} is not configured yet. Contact your company administrator.`}</Empty>}
          </section>
        ) : null}

        {tab === "activities" ? (
          <section className="mt-5 space-y-5">
            {feature("crm.analytics") ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
              {[
                ["Today", activityDashboard.today],
                ["Overdue", activityDashboard.overdue],
                ["Next 7 days", activityDashboard.upcoming_7d],
                ["Follow-ups", activityDashboard.followups],
                ["Activity 24h", activityDashboard.recent_activity_24h],
                [`New ${pluralTerm("lead", "Lead").toLowerCase()} 24h`, activityDashboard.new_leads_24h],
                ["Unassigned", activityDashboard.unassigned_leads],
              ].map(([label,value])=><article className="rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm" key={String(label)}><p className="text-[11px] text-[var(--muted)]">{label}</p><p className="mt-2 text-2xl font-semibold">{value}</p></article>)}
            </div> : null}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-2xl font-semibold">Company Activity</h2><p className="mt-1 text-sm text-[var(--muted)]">Calls, WhatsApp, email, meetings, follow-ups, tasks and lead log entries across the company.</p></div>{can("crm.activity.manage") ? <button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" onClick={() => setShowActivityForm((value) => !value)} type="button">Add activity</button> : null}</div>
            {showActivityForm ? <form className="grid gap-4 rounded-2xl border border-[var(--border)] bg-white p-5 sm:grid-cols-2 lg:grid-cols-4" onSubmit={submitActivity}><label className="text-sm font-medium">Type<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="activity_type"><option value="follow_up">Follow-up</option><option value="call">Call</option>{feature("crm.whatsapp") ? <option value="whatsapp">WhatsApp</option> : null}<option value="sms">SMS</option>{feature("crm.email") ? <option value="email">Email</option> : null}<option value="meeting">Meeting</option><option value="site_visit">On-site visit</option><option value="task">Task</option><option value="note">Note</option><option value="voice_note">Voice note</option><option value="document">Document</option><option value="photo">Photo</option><option value="video">Video</option></select></label><label className="text-sm font-medium">Status<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="status"><option value="planned">Planned</option><option value="completed">Completed</option></select></label><label className="text-sm font-medium">Priority<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="priority" defaultValue="normal"><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label><label className="text-sm font-medium">CRM record<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="relation" required><option value="">Choose record</option>{leads.map((lead) => <option key={lead.public_id} value={`lead:${lead.public_id}`}>{term("lead", "Lead")} · {lead.title}</option>)}{opportunities.map((opportunity) => <option key={opportunity.public_id} value={`opportunity:${opportunity.public_id}`}>{term("opportunity", "Opportunity")} · {opportunity.name}</option>)}{customers.map((customer) => <option key={customer.public_id} value={`customer:${customer.public_id}`}>{term("customer", "Customer")} · {customer.display_name}</option>)}</select></label><label className="text-sm font-medium">Scheduled for<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="scheduled_for" type="datetime-local" /></label><label className="text-sm font-medium">Follow-up at<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="follow_up_at" type="datetime-local" /></label><label className="text-sm font-medium">Location<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="location" placeholder="Required for on-site visits" /></label><label className="text-sm font-medium sm:col-span-2">Subject<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="subject" required /></label><label className="text-sm font-medium sm:col-span-2">Notes<textarea className="mt-1 w-full rounded-lg border border-[var(--border)] p-3" name="notes" /></label><div className="sm:col-span-2 lg:col-span-4 flex justify-end"><button className="rounded-lg bg-[var(--brand)] px-5 py-2 font-semibold text-white" type="submit">Save activity</button></div></form> : null}
            <div className="grid gap-3 lg:grid-cols-2">{activities.length ? activities.map((activity) => <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" key={activity.public_id}><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-[var(--brand-soft)] px-2 py-1 text-[10px] font-bold uppercase text-[var(--brand)]">{activity.activity_type.replaceAll("_", " ")}</span><span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase ${activity.priority==="urgent"?"bg-red-50 text-red-800":activity.priority==="high"?"bg-amber-50 text-amber-900":"bg-slate-100 text-slate-700"}`}>{activity.priority}</span><span className="ml-auto text-xs text-[var(--muted)]">{activity.status}</span></div><h2 className="mt-3 font-semibold">{activity.subject}</h2><p className="mt-1 text-sm text-[var(--muted)]">{activity.notes || "No notes"}</p><div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--muted)]"><span>{activity.created_by_name || "Build360 user"}</span><span>{formatDate(activity.scheduled_for || activity.completed_at || activity.created_at)}</span>{activity.follow_up_at ? <span>Follow-up {formatDate(activity.follow_up_at)}</span> : null}{activity.attachments.length ? <span>{activity.attachments.length} attachment(s)</span> : null}</div></article>) : <div className="lg:col-span-2"><Empty>No CRM activities are scheduled.</Empty></div>}</div>
          </section>
        ) : null}

        {tab === "automations" && feature("crm.automation") && can("crm.automation.read") ? (
          <section className="mt-5">
            <CrmAutomationPanel canManage={can("crm.automation.manage")} />
          </section>
        ) : null}

        {tab === "setup" && canOpenCrmSetup ? (
          <section className="mt-5">
            <CrmConfigurationPanel configuration={configuration} canManage={canManageCrmSetup} onChanged={setConfiguration} />
          </section>
        ) : null}

      </div>
      <CrmRelationshipDialog contactPublicId={relationshipContactId} features={initial.features} onClose={closeRelationship} permissions={initial.permissions} />
      <Build360Dialog
        description="Add the person and enquiry details. Primary phone is required."
        kicker="New lead"
        onClose={() => setShowLeadForm(false)}
        open={showLeadForm}
        size="large"
        title={`Create ${term("lead", "Lead")}`}
      >
        <form className="grid gap-4 p-4 sm:grid-cols-2 sm:p-6 lg:grid-cols-3" onSubmit={submitLead}>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 sm:col-span-2 lg:col-span-3">
            <p className="text-sm font-semibold text-slate-950">Person details</p>
            <p className="mt-1 text-sm leading-6 text-slate-600">Enter the person and enquiry details. Existing profiles are matched automatically when possible.</p>
          </div>
          <label className="text-sm font-medium">First name <span className="text-red-600">*</span><input autoComplete="given-name" className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="contact_first_name" required /></label>
          <label className="text-sm font-medium">Last name<input autoComplete="family-name" className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="contact_last_name" /></label>
          <label className="text-sm font-medium">Primary phone <span className="text-red-600">*</span><input autoComplete="tel" className="mt-1 w-full rounded-xl border border-slate-200 p-3" inputMode="tel" name="contact_phone" required /></label>
          <label className="text-sm font-medium">Alternate phone <span className="font-normal text-slate-500">(optional)</span><input className="mt-1 w-full rounded-xl border border-slate-200 p-3" inputMode="tel" name="contact_alternate_phone" /></label>
          <label className="text-sm font-medium">Email <span className="font-normal text-slate-500">(optional)</span><input autoComplete="email" className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="contact_email" type="email" /></label>
          <label className="text-sm font-medium">Company <span className="font-normal text-slate-500">(optional)</span><input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="customer_display_name" /></label>
          <label className="text-sm font-medium sm:col-span-2">What is this enquiry about? <span className="text-red-600">*</span><input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="title" placeholder="Example: Annual service requirement" required /></label>
          <label className="text-sm font-medium">Source<select className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="source_code"><option value="">Direct / not specified</option>{configuration.lead_sources.map((source) => <option key={source.public_id} value={source.code}>{source.name}</option>)}</select></label>
          {leadPipelines.length > 1 ? <label className="text-sm font-medium">{term("pipeline", "Pipeline")}<select className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="pipeline_public_id"><option value="">Default</option>{leadPipelines.map((pipeline) => <option key={pipeline.public_id} value={pipeline.public_id}>{pipeline.name}</option>)}</select></label> : null}
          <label className="text-sm font-medium">Estimated value<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" min="0" name="estimated_value" step="0.01" type="number" /></label>
          <label className="text-sm font-medium">Next follow-up<input className="mt-1 w-full rounded-xl border border-slate-200 p-3" name="next_follow_up_at" type="datetime-local" /></label>
          <ConfiguredFieldInputs fields={leadFields} />
          <label className="text-sm font-medium sm:col-span-2 lg:col-span-3">Description<textarea className="mt-1 min-h-24 w-full rounded-xl border border-slate-200 p-3" name="description" /></label>
          <div className="grid gap-2 sm:col-span-2 sm:flex sm:justify-end lg:col-span-3"><button className="rounded-xl border border-slate-200 px-4 py-2.5 font-semibold" onClick={() => setShowLeadForm(false)} type="button">Cancel</button><button className="rounded-xl bg-[var(--brand)] px-5 py-2.5 font-semibold text-white disabled:opacity-50" disabled={busy} type="submit">Save person + create {term("lead", "Lead").toLowerCase()}</button></div>
        </form>
      </Build360Dialog>

      <Build360ErrorDialog message={error} onClose={() => setError("")} open={Boolean(error)} title="CRM action could not be completed" />
      <Build360Toast message={notice} onDismiss={() => setNotice("")} />
    </main>
  );
}
