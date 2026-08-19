"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { Build360ErrorDialog } from "@/components/build360-dialog";
import { Build360Toast } from "@/components/build360-toast";

type AutomationRule = {
  public_id: string;
  code: string;
  name: string;
  description: string;
  trigger_code: string;
  condition_tree: { mode?: "all" | "any"; items?: Array<{ field: string; operator: string; value?: unknown }> };
  actions: Array<Record<string, unknown>>;
  priority: number;
  stop_on_match: boolean;
  is_active: boolean;
  last_triggered_at: string | null;
  version: number;
};

type AutomationExecution = {
  public_id: string;
  rule_public_id: string;
  rule_name: string;
  trigger_code: string;
  entity_type: string;
  entity_public_id: string;
  status: "running" | "succeeded" | "skipped" | "failed";
  matched: boolean;
  action_results: Array<Record<string, unknown>>;
  error_message: string;
  started_at: string;
  completed_at: string | null;
};

type AutomationEnvelope = {
  items: AutomationRule[];
  triggers: Array<{ code: string; label: string }>;
  action_types: Array<{ code: string; label: string }>;
};

type Props = { canManage: boolean };

type ErrorEnvelope = { message?: string; field_errors?: Record<string, string[]> };

async function automationRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/crm/${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as ErrorEnvelope;
    const fieldError = Object.entries(error.field_errors ?? {})
      .flatMap(([field, values]) => values.map((value) => `${field}: ${value}`))
      .join(" ");
    throw new Error(fieldError || error.message || `Automation request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

const CONDITION_FIELDS: Record<string, Array<{ value: string; label: string }>> = {
  "contact.created": [
    { value: "source_code", label: "Source" },
    { value: "consent_status", label: "Consent status" },
    { value: "preferred_channel_code", label: "Preferred channel" },
  ],
  "lead.created": [
    { value: "source_code", label: "Source" },
    { value: "stage.code", label: "Stage code" },
    { value: "estimated_value", label: "Estimated value" },
    { value: "currency", label: "Currency" },
  ],
  "lead.stage_changed": [
    { value: "from_stage", label: "From stage" },
    { value: "to_stage", label: "To stage" },
    { value: "stage.outcome", label: "New stage outcome" },
    { value: "source_code", label: "Source" },
  ],
  "opportunity.created": [
    { value: "stage.code", label: "Stage code" },
    { value: "amount", label: "Amount" },
    { value: "currency", label: "Currency" },
  ],
  "opportunity.stage_changed": [
    { value: "from_stage", label: "From stage" },
    { value: "to_stage", label: "To stage" },
    { value: "stage.outcome", label: "New stage outcome" },
    { value: "amount", label: "Amount" },
  ],
  "activity.completed": [
    { value: "activity_type", label: "Activity type" },
    { value: "outcome_code", label: "Outcome" },
    { value: "direction", label: "Direction" },
    { value: "priority", label: "Priority" },
  ],
};

function formatDate(value: string | null) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function statusClass(status: AutomationExecution["status"]) {
  if (status === "succeeded") return "bg-emerald-50 text-emerald-800";
  if (status === "failed") return "bg-red-50 text-red-800";
  if (status === "skipped") return "bg-slate-100 text-slate-700";
  return "bg-amber-50 text-amber-900";
}

export function CrmAutomationPanel({ canManage }: Readonly<Props>) {
  const [catalog, setCatalog] = useState<AutomationEnvelope>({ items: [], triggers: [], action_types: [] });
  const [executions, setExecutions] = useState<AutomationExecution[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [trigger, setTrigger] = useState("lead.created");
  const [actionType, setActionType] = useState("create_task");

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [rules, history] = await Promise.all([
        automationRequest<AutomationEnvelope>("automations"),
        automationRequest<{ items: AutomationExecution[] }>("automations/executions?limit=30"),
      ]);
      setCatalog(rules);
      setExecutions(history.items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "CRM automations could not be loaded.");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) void load();
    });
    return () => {
      active = false;
    };
  }, [load]);

  const conditionFields = useMemo(() => CONDITION_FIELDS[trigger] ?? [], [trigger]);

  async function createAutomation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    const form = new FormData(event.currentTarget);
    const conditionField = String(form.get("condition_field") || "").trim();
    const conditionOperator = String(form.get("condition_operator") || "eq");
    const conditionValue = String(form.get("condition_value") || "").trim();
    const conditionTree = conditionField
      ? { mode: "all", items: [{ field: conditionField, operator: conditionOperator, value: conditionValue }] }
      : { mode: "all", items: [] };

    const action: Record<string, unknown> = { type: actionType };
    if (["create_task", "schedule_follow_up", "add_note"].includes(actionType)) {
      action.subject = String(form.get("action_subject") || "").trim();
      action.notes = String(form.get("action_notes") || "").trim();
    }
    if (["create_task", "schedule_follow_up", "set_lead_follow_up"].includes(actionType)) {
      action.due_in_hours = Number(form.get("due_in_hours") || 24);
    }
    if (["create_task", "schedule_follow_up"].includes(actionType)) {
      action.priority = String(form.get("priority") || "normal");
    }
    if (actionType === "assign_owner") {
      action.owner_membership_public_id = String(form.get("owner_membership_public_id") || "trigger_actor").trim() || "trigger_actor";
    }

    try {
      await automationRequest<AutomationRule>("automations", {
        method: "POST",
        body: JSON.stringify({
          code: String(form.get("code") || "").trim(),
          name: String(form.get("name") || "").trim(),
          description: String(form.get("description") || "").trim(),
          trigger_code: trigger,
          condition_tree: conditionTree,
          actions: [action],
          priority: Number(form.get("rule_priority") || 100),
          stop_on_match: form.get("stop_on_match") === "on",
          is_active: true,
        }),
      });
      event.currentTarget.reset();
      setTrigger("lead.created");
      setActionType("create_task");
      setNotice("Automation saved. Future matching CRM events will execute it with idempotency and execution evidence.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Automation could not be created.");
      setBusy(false);
    }
  }

  async function toggleRule(rule: AutomationRule) {
    setBusy(true); setError(""); setNotice("");
    try {
      await automationRequest<AutomationRule>(`automations/${rule.public_id}`, {
        method: "PATCH",
        body: JSON.stringify({ expected_version: rule.version, is_active: !rule.is_active }),
      });
      setNotice(`${rule.name} ${rule.is_active ? "paused" : "activated"}.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Automation status could not be changed.");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Universal CRM</p>
            <h2 className="mt-1 text-xl font-semibold">Automation studio</h2>
            <p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">React to CRM events without industry-specific code. Rules create governed tasks, follow-ups, notes or assignments; a failed rule never rolls back the customer action that triggered it.</p>
          </div>
          <button className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold" disabled={busy} onClick={() => void load()} type="button">Refresh</button>
        </div>
      </section>


      {canManage ? (
        <form className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm" onSubmit={createAutomation}>
          <h3 className="font-semibold">Create automation</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">Start with one clear trigger, condition and action. The backend supports multiple conditions/actions for future advanced designer UX.</p>
          <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <label className="text-sm font-medium">Rule code<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="code" pattern="[a-z][a-z0-9_-]*" placeholder="website-follow-up" required /></label>
            <label className="text-sm font-medium">Rule name<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="name" placeholder="Website lead follow-up" required /></label>
            <label className="text-sm font-medium">Trigger<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="trigger_code" onChange={(event) => setTrigger(event.target.value)} value={trigger}>{catalog.triggers.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}</select></label>
            <label className="text-sm font-medium">Condition field<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="condition_field"><option value="">Always match</option>{conditionFields.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}<option value="custom_fields.segment">Custom field example: segment</option></select></label>
            <label className="text-sm font-medium">Operator<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="condition_operator"><option value="eq">Equals</option><option value="neq">Does not equal</option><option value="contains">Contains</option><option value="in">In list</option><option value="gt">Greater than</option><option value="gte">Greater than or equal</option><option value="lt">Less than</option><option value="lte">Less than or equal</option><option value="is_empty">Is empty</option><option value="not_empty">Is not empty</option></select></label>
            <label className="text-sm font-medium">Condition value<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="condition_value" placeholder="website / no_answer / 500000" /></label>
            <label className="text-sm font-medium">Action<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="action_type" onChange={(event) => setActionType(event.target.value)} value={actionType}>{catalog.action_types.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}</select></label>
            {["create_task", "schedule_follow_up", "add_note"].includes(actionType) ? <label className="text-sm font-medium">Action subject<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="action_subject" placeholder="Follow up with customer" required /></label> : null}
            {["create_task", "schedule_follow_up", "set_lead_follow_up"].includes(actionType) ? <label className="text-sm font-medium">Due in hours<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" defaultValue="24" min="0" name="due_in_hours" type="number" /></label> : null}
            {["create_task", "schedule_follow_up"].includes(actionType) ? <label className="text-sm font-medium">Priority<select className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" defaultValue="normal" name="priority"><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label> : null}
            {actionType === "assign_owner" ? <label className="text-sm font-medium">Owner membership ID<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="owner_membership_public_id" placeholder="trigger_actor or membership UUID" /></label> : null}
            <label className="text-sm font-medium md:col-span-2">Description<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" name="description" placeholder="Why this automation exists" /></label>
            <label className="text-sm font-medium">Priority order<input className="mt-1 w-full rounded-lg border border-[var(--border)] p-2.5" defaultValue="100" min="0" name="rule_priority" type="number" /></label>
            <label className="flex items-center gap-2 self-end pb-2 text-sm font-medium"><input name="stop_on_match" type="checkbox" /> Stop later rules after a match</label>
          </div>
          {["create_task", "schedule_follow_up", "add_note"].includes(actionType) ? <label className="mt-4 block text-sm font-medium">Action notes<textarea className="mt-1 min-h-20 w-full rounded-lg border border-[var(--border)] p-2.5" name="action_notes" /></label> : null}
          <div className="mt-4 flex justify-end"><button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" disabled={busy} type="submit">Save automation</button></div>
        </form>
      ) : null}

      <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
        <h3 className="font-semibold">Rules</h3>
        <div className="mt-4 space-y-3">
          {catalog.items.length ? catalog.items.map((rule) => {
            const firstCondition = rule.condition_tree.items?.[0];
            const firstAction = rule.actions[0];
            return <article className="rounded-xl border border-[var(--border)] p-4" key={rule.public_id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><div className="flex flex-wrap items-center gap-2"><h4 className="font-semibold">{rule.name}</h4><span className={`rounded-full px-2 py-1 text-[11px] font-bold uppercase ${rule.is_active ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{rule.is_active ? "Active" : "Paused"}</span></div><p className="mt-1 text-xs text-[var(--muted)]">{rule.trigger_code} · priority {rule.priority} · last run {formatDate(rule.last_triggered_at)}</p></div>
                {canManage ? <button className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-semibold" disabled={busy} onClick={() => void toggleRule(rule)} type="button">{rule.is_active ? "Pause" : "Activate"}</button> : null}
              </div>
              <div className="mt-3 grid gap-2 text-sm md:grid-cols-2"><div className="rounded-lg bg-slate-50 p-3"><span className="font-semibold">IF</span> {firstCondition ? `${firstCondition.field} ${firstCondition.operator} ${String(firstCondition.value ?? "")}` : "Always"}</div><div className="rounded-lg bg-slate-50 p-3"><span className="font-semibold">THEN</span> {String(firstAction?.type ?? "No action")}</div></div>
            </article>;
          }) : <p className="rounded-xl border border-dashed border-[var(--border)] p-5 text-sm text-[var(--muted)]">No CRM automations configured yet.</p>}
        </div>
      </section>

      <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
        <h3 className="font-semibold">Execution history</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">Every matched, skipped or failed evaluation is tenant-scoped evidence. Failed rules do not undo the originating CRM transaction.</p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm"><thead><tr className="border-b border-[var(--border)] text-xs uppercase tracking-wide text-[var(--muted)]"><th className="py-2 pr-4">Time</th><th className="py-2 pr-4">Rule</th><th className="py-2 pr-4">Trigger</th><th className="py-2 pr-4">Record</th><th className="py-2">Status</th></tr></thead><tbody>{executions.map((item) => <tr className="border-b border-slate-100" key={item.public_id}><td className="py-3 pr-4">{formatDate(item.started_at)}</td><td className="py-3 pr-4"><div className="font-medium">{item.rule_name}</div>{item.error_message ? <div className="mt-1 max-w-sm text-xs text-red-700">{item.error_message}</div> : null}</td><td className="py-3 pr-4">{item.trigger_code}</td><td className="py-3 pr-4">{item.entity_type}<div className="text-xs text-[var(--muted)]">{item.entity_public_id.slice(0, 8)}…</div></td><td className="py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-bold uppercase ${statusClass(item.status)}`}>{item.status}</span></td></tr>)}</tbody></table>
        </div>
      </section>
      <Build360ErrorDialog message={error} onClose={() => setError("")} open={Boolean(error)} title="CRM automation action could not be completed" />
      <Build360Toast message={notice} onDismiss={() => setNotice("")} />
    </div>
  );
}
