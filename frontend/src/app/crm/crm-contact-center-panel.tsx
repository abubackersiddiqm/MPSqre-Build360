"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { Build360Dialog, Build360ErrorDialog } from "@/components/build360-dialog";
import { Build360Toast } from "@/components/build360-toast";

type Contact = {
  public_id: string;
  customer_public_id: string | null;
  display_name: string;
  job_title: string;
  email_masked: string | null;
  phone_masked: string | null;
  consent_status: string;
  preferred_channel_code: string;
  source_code: string;
  tags: string[];
  communication_actions: { email: boolean; phone: boolean };
};

type Activity = {
  public_id: string;
  activity_type: string;
  status: string;
  direction: string;
  outcome_code: string;
  duration_seconds: number | null;
  channel_metadata: Record<string, unknown>;
  subject: string;
  notes: string;
  contact_public_id: string | null;
  customer_public_id: string | null;
  lead_public_id: string | null;
  opportunity_public_id: string | null;
  scheduled_for: string | null;
  follow_up_at: string | null;
  occurred_at: string | null;
  completed_at: string | null;
  created_at: string;
  version: number;
};

type Props = {
  contacts: Contact[];
  permissions: string[];
  features: Record<string, boolean>;
};

type ErrorEnvelope = {
  message?: string;
  detail?: string;
  non_field_errors?: string[];
};

type ActiveInteraction = {
  activity: Activity;
  contact: Contact;
  channel: "call" | "whatsapp" | "email";
};

async function crmApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/crm/${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });
  const payload = (await response.json().catch(() => ({}))) as T & ErrorEnvelope;
  if (!response.ok) {
    const nonField = payload.non_field_errors?.join(" ");
    throw new Error(nonField || payload.message || payload.detail || `CRM request failed (${response.status})`);
  }
  return payload as T;
}

function formatWhen(value: string | null) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function toIso(value: FormDataEntryValue | null) {
  const raw = String(value || "").trim();
  if (!raw) return undefined;
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed.toISOString();
}

function outcomeOptions(channel: ActiveInteraction["channel"]): Array<[string, string]> {
  if (channel === "call") {
    return [
      ["connected", "Connected"],
      ["no_answer", "No answer"],
      ["busy", "Busy"],
      ["callback_requested", "Callback requested"],
      ["wrong_number", "Wrong number"],
    ];
  }
  if (channel === "whatsapp") {
    return [
      ["replied", "Replied"],
      ["message_sent", "Message sent"],
      ["no_response", "No response"],
      ["callback_requested", "Callback requested"],
    ];
  }
  return [
    ["email_sent", "Email sent"],
    ["replied", "Replied"],
    ["follow_up_required", "Follow-up required"],
    ["bounced", "Bounced"],
  ];
}

export function CrmContactCenterPanel({ contacts, permissions, features }: Readonly<Props>) {
  const can = (permission: string) => permissions.includes(permission);
  const feature = (code: string) => features[code] === true;
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(contacts[0]?.public_id ?? "");
  const [timeline, setTimeline] = useState<Activity[]>([]);
  const [activeInteraction, setActiveInteraction] = useState<ActiveInteraction | null>(null);
  const [outcomeCode, setOutcomeCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const filteredContacts = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return contacts;
    return contacts.filter((contact) =>
      [contact.display_name, contact.job_title, contact.source_code, ...contact.tags]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [contacts, query]);

  const selected = contacts.find((contact) => contact.public_id === selectedId) ?? contacts[0] ?? null;

  async function loadTimeline(contactId: string) {
    if (!contactId || !can("crm.activity.read")) {
      setTimeline([]);
      return;
    }
    try {
      const payload = await crmApi<{ items: Activity[] }>(`contacts/${contactId}/timeline?limit=100`);
      setTimeline(payload.items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Contact timeline could not be loaded.");
    }
  }

  useEffect(() => {
    const contactId = selected?.public_id;
    if (!contactId) return;
    let active = true;
    queueMicrotask(() => {
      if (active) void loadTimeline(contactId);
    });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.public_id]);

  async function reveal(contact: Contact, reasonCode: string) {
    return crmApi<{ phone?: string; email?: string }>(`contacts/${contact.public_id}/reveal`, {
      method: "POST",
      body: JSON.stringify({ reason_code: reasonCode }),
    });
  }

  async function createInteraction(contact: Contact, channel: ActiveInteraction["channel"], subject: string) {
    if (!can("crm.activity.manage")) return null;
    return crmApi<Activity>("activities", {
      method: "POST",
      body: JSON.stringify({
        contact_public_id: contact.public_id,
        ...(contact.customer_public_id ? { customer_public_id: contact.customer_public_id } : {}),
        activity_type: channel,
        status: "planned",
        direction: "outbound",
        outcome_code: "started",
        subject,
        occurred_at: new Date().toISOString(),
        notes: "Started from the Build360 CRM Contact Center. Record the outcome and next follow-up after the interaction.",
        channel_metadata: {
          source: "crm_contact_center",
          launch_mode: "device_handoff",
        },
      }),
    });
  }

  async function startCall(contact: Contact) {
    if (!can("crm.contact.reveal")) {
      setError("You do not have permission to reveal the protected phone number for calling.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const endpoints = await reveal(contact, "crm_call");
      const phone = (endpoints.phone ?? "").trim();
      if (!phone) throw new Error("This contact does not have a callable phone number.");
      const activity = await createInteraction(contact, "call", `Call ${contact.display_name}`);
      if (activity) { setActiveInteraction({ activity, contact, channel: "call" }); setOutcomeCode(""); }
      window.location.assign(`tel:${phone.replace(/[^+0-9]/g, "")}`);
      setNotice("Device dialer opened. After the call, record the outcome below so the next person knows exactly what happened.");
      await loadTimeline(contact.public_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The call could not be started.");
    } finally {
      setBusy(false);
    }
  }

  async function startWhatsApp(contact: Contact) {
    if (!feature("crm.whatsapp")) {
      setError("WhatsApp is not enabled in this company's CRM package.");
      return;
    }
    if (!can("crm.contact.reveal")) {
      setError("You do not have permission to reveal the protected phone number for WhatsApp.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const endpoints = await reveal(contact, "crm_whatsapp");
      const digits = (endpoints.phone ?? "").replace(/\D/g, "");
      if (!digits) throw new Error("This contact does not have a WhatsApp-capable phone number.");
      const activity = await createInteraction(contact, "whatsapp", `WhatsApp ${contact.display_name}`);
      if (activity) { setActiveInteraction({ activity, contact, channel: "whatsapp" }); setOutcomeCode(""); }
      const greeting = encodeURIComponent(`Hi ${contact.display_name},`);
      window.open(`https://wa.me/${digits}?text=${greeting}`, "_blank", "noopener,noreferrer");
      setNotice("WhatsApp opened in a new tab. Record the conversation outcome and follow-up below.");
      await loadTimeline(contact.public_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "WhatsApp could not be opened.");
    } finally {
      setBusy(false);
    }
  }

  async function startEmail(contact: Contact) {
    if (!feature("crm.email")) {
      setError("Email is not enabled in this company's CRM package.");
      return;
    }
    if (!can("crm.contact.reveal")) {
      setError("You do not have permission to reveal the protected email address.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const endpoints = await reveal(contact, "crm_email");
      const email = (endpoints.email ?? "").trim();
      if (!email) throw new Error("This contact does not have an email address.");
      const activity = await createInteraction(contact, "email", `Email ${contact.display_name}`);
      if (activity) { setActiveInteraction({ activity, contact, channel: "email" }); setOutcomeCode(""); }
      window.location.assign(`mailto:${encodeURIComponent(email)}`);
      setNotice("Your email app opened. Record the outcome and next follow-up below.");
      await loadTimeline(contact.public_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Email could not be opened.");
    } finally {
      setBusy(false);
    }
  }

  async function saveOutcome(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeInteraction) return;
    const form = new FormData(event.currentTarget);
    const selectedOutcome = String(form.get("outcome_code") || "").trim();
    if (!selectedOutcome) {
      setError("Choose an interaction outcome before saving.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const durationRaw = String(form.get("duration_seconds") || "").trim();
      const followUpAt = toIso(form.get("follow_up_at"));
      const updated = await crmApi<Activity>(`activities/${activeInteraction.activity.public_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_version: activeInteraction.activity.version,
          status: "completed",
          outcome_code: selectedOutcome,
          duration_seconds: durationRaw ? Number(durationRaw) : null,
          notes: form.get("notes"),
          ...(followUpAt ? { follow_up_at: followUpAt } : {}),
          channel_metadata: {
            source: "crm_contact_center",
            launch_mode: "device_handoff",
            outcome_recorded: true,
          },
        }),
      });
      setActiveInteraction(null);
      setOutcomeCode("");
      setNotice(`${updated.activity_type.replaceAll("_", " ")} outcome saved. CRM history is now ready for the next follow-up.`);
      await loadTimeline(activeInteraction.contact.public_id);
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Interaction outcome could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  if (!contacts.length) {
    return (
      <section className="mt-5 rounded-2xl border border-dashed border-[var(--border)] bg-white p-6">
        <h2 className="text-2xl font-semibold">CRM Contact Center</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">Save a contact first. Calling, WhatsApp, email and interaction history will then be available here.</p>
      </section>
    );
  }

  return (
    <section className="mt-5 space-y-5">
      <div className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm sm:p-6">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--brand)]">Universal CRM Contact Center</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-2xl font-semibold">Call, WhatsApp, email, outcome, follow-up</h2>
            <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">Simple workflow: choose a contact → start the channel → speak/send → record the outcome → schedule the next follow-up. Protected phone/email values are revealed only for the authorized action and are never written into activity metadata.</p>
          </div>
          <div className="rounded-xl bg-slate-50 px-4 py-3 text-xs text-slate-700">
            <strong>Current mode:</strong> device hand-off. Build360 opens your dialer, WhatsApp or email app and keeps the CRM evidence trail.
          </div>
        </div>
      </div>


      <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm">
          <label className="text-sm font-medium">Find contact
            <input className="mt-2 w-full rounded-lg border border-[var(--border)] p-3" onChange={(event) => setQuery(event.target.value)} placeholder="Name, tag, source…" value={query} />
          </label>
          <div className="mt-4 max-h-[620px] space-y-2 overflow-y-auto pr-1">
            {filteredContacts.map((contact) => (
              <button
                className={`w-full rounded-xl border p-3 text-left transition ${selected?.public_id === contact.public_id ? "border-[var(--brand)] bg-[var(--brand-soft)]" : "border-[var(--border)] hover:bg-slate-50"}`}
                key={contact.public_id}
                onClick={() => { setSelectedId(contact.public_id); setActiveInteraction(null); setOutcomeCode(""); setNotice(""); setError(""); }}
                type="button"
              >
                <p className="font-semibold">{contact.display_name}</p>
                <p className="mt-1 text-xs text-[var(--muted)]">{contact.job_title || "Contact"}</p>
                <p className="mt-2 text-xs text-[var(--muted)]">{contact.phone_masked || "No phone"} · {contact.email_masked || "No email"}</p>
              </button>
            ))}
          </div>
        </aside>

        {selected ? (
          <div className="space-y-5">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm sm:p-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h3 className="text-2xl font-semibold">{selected.display_name}</h3>
                  <p className="mt-1 text-sm text-[var(--muted)]">{selected.job_title || "Contact"}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold uppercase">{selected.consent_status}</span>
                    {selected.preferred_channel_code ? <span className="rounded-full bg-[var(--brand-soft)] px-2.5 py-1 font-semibold text-[var(--brand)]">Preferred: {selected.preferred_channel_code}</span> : null}
                    {selected.source_code ? <span className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold">Source: {selected.source_code}</span> : null}
                  </div>
                </div>
                <div className="text-sm text-[var(--muted)] sm:text-right">
                  <p>{selected.phone_masked || "No phone"}</p>
                  <p className="mt-1">{selected.email_masked || "No email"}</p>
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <button className="rounded-xl bg-slate-950 px-4 py-3 font-semibold text-white disabled:opacity-50" disabled={busy || !selected.communication_actions.phone || !can("crm.contact.reveal")} onClick={() => void startCall(selected)} type="button">Call now</button>
                <button className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 font-semibold text-emerald-800 disabled:opacity-50" disabled={busy || !selected.communication_actions.phone || !feature("crm.whatsapp") || !can("crm.contact.reveal")} onClick={() => void startWhatsApp(selected)} type="button">WhatsApp</button>
                <button className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 font-semibold text-sky-800 disabled:opacity-50" disabled={busy || !selected.communication_actions.email || !feature("crm.email") || !can("crm.contact.reveal")} onClick={() => void startEmail(selected)} type="button">Email</button>
              </div>
              <p className="mt-3 text-xs text-[var(--muted)]">WhatsApp and Email buttons follow the company’s SaaS add-ons. Call uses the protected CRM contact reveal and the device dialer; provider-connected telephony can be layered on later without changing the CRM record model.</p>
            </article>



            <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm sm:p-6">
              <div className="flex items-center justify-between gap-3">
                <div><h3 className="text-lg font-semibold">Contact interaction history</h3><p className="mt-1 text-sm text-[var(--muted)]">Calls, WhatsApp, email and follow-ups stay attached to this contact even before a lead or customer record is created.</p></div>
                <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold" disabled={busy} onClick={() => void loadTimeline(selected.public_id)} type="button">Refresh</button>
              </div>
              <div className="mt-4 space-y-3">
                {timeline.length ? timeline.map((activity) => (
                  <div className="rounded-xl border border-[var(--border)] p-4" key={activity.public_id}>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="font-semibold">{activity.subject}</p>
                        <p className="mt-1 text-xs text-[var(--muted)]">{activity.activity_type.replaceAll("_", " ")} · {activity.direction} · {activity.status}</p>
                      </div>
                      <p className="text-xs text-[var(--muted)]">{formatWhen(activity.occurred_at || activity.created_at)}</p>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      {activity.outcome_code ? <span className="rounded-full bg-emerald-50 px-2.5 py-1 font-semibold text-emerald-800">{activity.outcome_code.replaceAll("_", " ")}</span> : null}
                      {activity.duration_seconds !== null ? <span className="rounded-full bg-slate-100 px-2.5 py-1">{activity.duration_seconds}s</span> : null}
                      {activity.follow_up_at ? <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-900">Follow-up {formatWhen(activity.follow_up_at)}</span> : null}
                    </div>
                    {activity.notes ? <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{activity.notes}</p> : null}
                  </div>
                )) : <p className="rounded-xl border border-dashed border-[var(--border)] p-5 text-sm text-[var(--muted)]">No communication history for this contact yet.</p>}
              </div>
            </article>
          </div>
        ) : null}
      </div>

      <Build360Dialog
        description={activeInteraction ? `Capture the result for ${activeInteraction.contact.display_name}. This updates the CRM timeline and keeps the next follow-up visible to the team.` : undefined}
        footer={activeInteraction ? (
          <div className="flex flex-wrap justify-end gap-2">
            <button className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold" onClick={() => { setActiveInteraction(null); setOutcomeCode(""); }} type="button">Skip for now</button>
            <button className="rounded-xl bg-[var(--brand)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={busy || !outcomeCode} form="crm-interaction-outcome-form" type="submit">{busy ? "Saving…" : "Save outcome"}</button>
          </div>
        ) : undefined}
        kicker="Record interaction outcome"
        onClose={() => { setActiveInteraction(null); setOutcomeCode(""); }}
        open={Boolean(activeInteraction)}
        size="medium"
        title={activeInteraction?.channel === "call" ? "What happened on the call?" : activeInteraction ? `What happened on ${activeInteraction.channel}?` : "Record interaction outcome"}
      >
        {activeInteraction ? (
          <form className="grid gap-5 p-5 sm:grid-cols-2 sm:p-6" id="crm-interaction-outcome-form" onSubmit={saveOutcome}>
            <div className="sm:col-span-2">
              <p className="text-sm font-semibold text-slate-900">Choose an outcome</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {outcomeOptions(activeInteraction.channel).map(([value, label]) => (
                  <button
                    aria-pressed={outcomeCode === value}
                    className={`rounded-xl border px-4 py-3 text-left text-sm font-semibold transition ${outcomeCode === value ? "border-[var(--brand)] bg-[var(--brand-soft)] text-[var(--brand)] ring-2 ring-[var(--brand)]/10" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}
                    key={value}
                    onClick={() => setOutcomeCode(value)}
                    type="button"
                  >
                    {label}
                  </button>
                ))}
              </div>
              <input name="outcome_code" type="hidden" value={outcomeCode} />
              {!outcomeCode ? <p className="mt-2 text-xs text-slate-500">Select one outcome before saving.</p> : null}
            </div>
            {activeInteraction.channel === "call" ? (
              <label className="text-sm font-medium">Duration in seconds <span className="font-normal text-slate-500">(optional)</span>
                <input className="mt-2 w-full rounded-xl border border-slate-200 bg-white p-3 outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/10" min="0" name="duration_seconds" type="number" />
              </label>
            ) : null}
            <label className="text-sm font-medium">Next follow-up <span className="font-normal text-slate-500">{outcomeCode === "callback_requested" || outcomeCode === "follow_up_required" ? "(required)" : "(optional)"}</span>
              <input className="mt-2 w-full rounded-xl border border-slate-200 bg-white p-3 outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/10" name="follow_up_at" required={outcomeCode === "callback_requested" || outcomeCode === "follow_up_required"} type="datetime-local" />
            </label>
            <label className="text-sm font-medium sm:col-span-2">Notes
              <textarea className="mt-2 min-h-28 w-full rounded-xl border border-slate-200 bg-white p-3 outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand)]/10" name="notes" placeholder="Customer response, requirement, objection, next step…" />
            </label>
            {!outcomeCode ? <button className="hidden" disabled type="submit" /> : null}
          </form>
        ) : null}
      </Build360Dialog>

      <Build360ErrorDialog message={error} onClose={() => setError("")} open={Boolean(error)} title="CRM action could not be completed" />
      <Build360Toast message={notice} onDismiss={() => setNotice("")} />

    </section>
  );
}
