"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

export type Company = {
  public_id: string;
  code: string;
  display_name: string;
  timezone: string;
  currency: string;
};
export type AISummary = {
  active_providers: number;
  active_policies: number;
  completed_interactions: number;
  pending_reviews: number;
  open_risks: number;
  proposed_actions: number;
};
export type AIPolicy = {
  public_id: string;
  code: string;
  name: string;
  model_name: string;
  purpose: string;
  human_review_required: boolean;
  citations_required: boolean;
  allowed_source_types: string[];
  allowed_tool_codes: string[];
  is_active: boolean;
};
export type AICitation = {
  public_id: string;
  rank: number;
  source_label: string;
  excerpt: string;
  data_classification: string;
};
export type AIInteraction = {
  public_id: string;
  policy: { code: string; name: string };
  prompt_excerpt: string;
  status: string;
  response_text: string;
  confidence: string | null;
  review_status: string;
  citations: AICitation[];
  created_at: string;
};
export type AIExtraction = {
  public_id: string;
  policy_code: string;
  source_type: string;
  schema_code: string;
  requested_fields: string[];
  extracted_payload: Record<string, unknown>;
  confidence_by_field: Record<string, string>;
  status: string;
  created_at: string;
};
export type AIRisk = {
  public_id: string;
  signal_code: string;
  severity: string;
  title: string;
  description: string;
  evidence: Record<string, unknown>;
  status: string;
  created_at: string;
};
export type AIAction = {
  public_id: string;
  interaction_public_id: string;
  action_code: string;
  target_type: string;
  proposed_payload: Record<string, unknown>;
  status: string;
  expires_at: string;
};
export type AIEvaluation = {
  public_id: string;
  policy_code: string;
  suite_code: string;
  status: string;
  scenario_count: number;
  passed_count: number;
  failures: string[];
  completed_at: string;
};

type Props = {
  company: Company;
  permissions: string[];
  initialSummary: AISummary | null;
  initialPolicies: AIPolicy[];
  initialInteractions: AIInteraction[];
  initialExtractions: AIExtraction[];
  initialRisks: AIRisk[];
  initialActions: AIAction[];
  initialEvaluations: AIEvaluation[];
};
type Tab = "assistant" | "extraction" | "risks" | "governance";
type ApiError = { message?: string; detail?: string };

async function api<T>(path: string, init?: RequestInit) {
  const response = await fetch(`/api/ai/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = (await response.json().catch(() => ({}))) as T & ApiError;
  if (!response.ok) throw new Error(body.message ?? body.detail ?? "The AI request failed.");
  return body as T;
}

function Card({ label, value, note }: { label: string; value: number | string; note?: string }) {
  return (
    <article className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
      <p className="text-sm text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
      {note ? <p className="mt-2 text-xs text-[var(--muted)]">{note}</p> : null}
    </article>
  );
}

function Pill({ value }: { value: string }) {
  return (
    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-slate-700">
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function AIWorkspace(props: Readonly<Props>) {
  const [tab, setTab] = useState<Tab>("assistant");
  const [summary, setSummary] = useState(
    props.initialSummary ?? {
      active_providers: 0,
      active_policies: 0,
      completed_interactions: 0,
      pending_reviews: 0,
      open_risks: 0,
      proposed_actions: 0,
    },
  );
  const [policies, setPolicies] = useState(props.initialPolicies);
  const [interactions, setInteractions] = useState(props.initialInteractions);
  const [extractions, setExtractions] = useState(props.initialExtractions);
  const [risks, setRisks] = useState(props.initialRisks);
  const [actions, setActions] = useState(props.initialActions);
  const [evaluations, setEvaluations] = useState(props.initialEvaluations);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const metricCodes = useMemo(
    () =>
      [
        "PROJECTS_ACTIVE",
        "PROJECT_TASKS_OVERDUE",
        "SAFETY_INCIDENTS_OPEN",
        "FINANCE_APPROVED_BUDGET",
        "FINANCE_OUTSTANDING",
      ].join(", "),
    [],
  );

  async function refresh() {
    const [s, p, i, e, r, a, v] = await Promise.all([
      api<AISummary>("summary"),
      api<{ items: AIPolicy[] }>("policies"),
      api<{ items: AIInteraction[] }>("interactions"),
      api<{ items: AIExtraction[] }>("extractions"),
      api<{ items: AIRisk[] }>("risks"),
      api<{ items: AIAction[] }>("actions"),
      api<{ items: AIEvaluation[] }>("evaluations"),
    ]);
    setSummary(s);
    setPolicies(p.items);
    setInteractions(i.items);
    setExtractions(e.items);
    setRisks(r.items);
    setActions(a.items);
    setEvaluations(v.items);
  }

  async function run(action: () => Promise<void>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh();
      setNotice(message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The AI request failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createSummary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const codes = String(form.get("metric_codes") ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    await run(async () => {
      await api("interactions", {
        method: "POST",
        body: JSON.stringify({
          policy_code: "BUILD360_ASSISTANT",
          prompt: form.get("prompt"),
          metric_codes: codes,
          idempotency_key: `ui-${crypto.randomUUID()}`,
        }),
      });
    }, "Grounded summary completed with source citations.");
  }

  async function createExtraction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const fields = String(form.get("requested_fields") ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    await run(async () => {
      await api("extractions", {
        method: "POST",
        body: JSON.stringify({
          policy_code: "BUILD360_EXTRACTION",
          source_type: "document.text",
          source_text: form.get("source_text"),
          schema_code: form.get("schema_code"),
          requested_fields: fields,
          idempotency_key: `ui-${crypto.randomUUID()}`,
        }),
      });
    }, "Extraction completed and queued for human review.");
  }

  async function scanRisks() {
    await run(async () => {
      await api("risks", {
        method: "POST",
        body: JSON.stringify({ policy_code: "BUILD360_RISK" }),
      });
    }, "Governed risk scan completed. Signals remain advisory until reviewed.");
  }

  async function runEvaluation(policyCode: string) {
    await run(async () => {
      await api("evaluations", {
        method: "POST",
        body: JSON.stringify({ policy_code: policyCode, suite_code: "FOUNDATION_GUARDRAILS" }),
      });
    }, "AI guardrail evaluation completed.");
  }

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
              MPSqre Build360 · Governed AI
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              Permission-aware AI controls
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {props.company.display_name} · cited · review-gated · tenant-safe
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-900">
              Phase 11 active
            </span>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/operations">
              Operations
            </Link>
            <Link className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold" href="/platform">
              Platform
            </Link>
          </div>
        </header>

        <section className="grid gap-4 py-7 sm:grid-cols-2 xl:grid-cols-6">
          <Card label="Active providers" value={summary.active_providers} />
          <Card label="Active policies" value={summary.active_policies} />
          <Card label="AI interactions" value={summary.completed_interactions} />
          <Card label="Pending reviews" value={summary.pending_reviews} />
          <Card label="Open risk signals" value={summary.open_risks} />
          <Card label="Tool proposals" value={summary.proposed_actions} note="Never auto-executed" />
        </section>

        <nav className="mb-6 flex flex-wrap gap-2">
          {(["assistant", "extraction", "risks", "governance"] as Tab[]).map((item) => (
            <button
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === item ? "bg-[var(--brand)] text-white" : "border border-[var(--border)] bg-white"}`}
              key={item}
              onClick={() => setTab(item)}
              type="button"
            >
              {item === "assistant" ? "Grounded assistant" : item === "extraction" ? "Extraction review" : item === "risks" ? "Risk signals" : "Governance"}
            </button>
          ))}
        </nav>

        {error ? <p className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p> : null}
        {notice ? <p className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</p> : null}

        {tab === "assistant" ? (
          <section className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createSummary}>
              <h2 className="text-xl font-semibold">Create grounded summary</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">Only authorized governed metrics are retrieved. Every value is cited.</p>
              <textarea className="mt-5 min-h-28 w-full rounded-xl border border-[var(--border)] p-3 text-sm" defaultValue="Summarize the current delivery, safety and commercial position." name="prompt" required />
              <textarea className="mt-3 min-h-24 w-full rounded-xl border border-[var(--border)] p-3 text-sm" defaultValue={metricCodes} name="metric_codes" required />
              <button className="mt-4 rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={busy} type="submit">Generate cited summary</button>
            </form>
            <div className="space-y-4">
              {interactions.length ? interactions.map((item) => (
                <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" key={item.public_id}>
                  <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">{item.policy.name}</h2><Pill value={item.review_status} /></div>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{item.response_text}</p>
                  <div className="mt-4 space-y-2 border-t border-[var(--border)] pt-4">
                    {item.citations.map((citation) => <p className="text-xs text-[var(--muted)]" key={citation.public_id}>[{citation.rank}] {citation.source_label}: {citation.excerpt} · {citation.data_classification}</p>)}
                  </div>
                </article>
              )) : <article className="rounded-2xl border border-[var(--border)] bg-white p-6">No AI interaction has been created.</article>}
            </div>
          </section>
        ) : null}

        {tab === "extraction" ? (
          <section className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
            <form className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={createExtraction}>
              <h2 className="text-xl font-semibold">Local extraction preview</h2>
              <input className="mt-4 w-full rounded-xl border border-[var(--border)] p-3 text-sm" defaultValue="CONTRACT_HEADER" name="schema_code" required />
              <input className="mt-3 w-full rounded-xl border border-[var(--border)] p-3 text-sm" defaultValue="contract_number, vendor_name, contract_value" name="requested_fields" required />
              <textarea className="mt-3 min-h-44 w-full rounded-xl border border-[var(--border)] p-3 text-sm" defaultValue={"contract_number: CNT-001\nvendor_name: Example Vendor\ncontract_value: 1250000"} name="source_text" required />
              <button className="mt-4 rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={busy} type="submit">Extract for review</button>
            </form>
            <div className="space-y-4">
              {extractions.map((item) => <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" key={item.public_id}><div className="flex justify-between gap-3"><h2 className="font-semibold">{item.schema_code}</h2><Pill value={item.status} /></div><pre className="mt-4 overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-100">{JSON.stringify(item.extracted_payload, null, 2)}</pre></article>)}
            </div>
          </section>
        ) : null}

        {tab === "risks" ? (
          <section>
            <div className="mb-4 flex justify-end"><button className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={busy} onClick={scanRisks} type="button">Run governed risk scan</button></div>
            <div className="grid gap-4 md:grid-cols-2">
              {risks.length ? risks.map((item) => <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm" key={item.public_id}><div className="flex flex-wrap justify-between gap-3"><h2 className="font-semibold">{item.title}</h2><div className="flex gap-2"><Pill value={item.severity} /><Pill value={item.status} /></div></div><p className="mt-3 text-sm text-[var(--muted)]">{item.description}</p><pre className="mt-4 overflow-auto rounded-xl bg-slate-50 p-3 text-xs">{JSON.stringify(item.evidence, null, 2)}</pre></article>) : <p className="rounded-2xl border border-[var(--border)] bg-white p-6">No risk signal is open.</p>}
            </div>
          </section>
        ) : null}

        {tab === "governance" ? (
          <section className="grid gap-6 lg:grid-cols-2">
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Model policies</h2><div className="mt-4 space-y-3">{policies.map((item) => <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}><div className="flex justify-between gap-3"><div><p className="font-semibold">{item.name}</p><p className="mt-1 text-xs text-[var(--muted)]">{item.code} · {item.model_name}</p></div><Pill value={item.purpose} /></div><p className="mt-3 text-xs text-[var(--muted)]">Citations: {String(item.citations_required)} · Human review: {String(item.human_review_required)}</p><button className="mt-3 rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold disabled:opacity-60" disabled={busy} onClick={() => runEvaluation(item.code)} type="button">Run guardrail evaluation</button></div>)}</div></article>
            <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm"><h2 className="text-xl font-semibold">Evaluation evidence</h2><div className="mt-4 space-y-3">{evaluations.map((item) => <div className="rounded-xl border border-[var(--border)] p-4" key={item.public_id}><div className="flex justify-between gap-3"><p className="font-semibold">{item.policy_code}</p><Pill value={item.status} /></div><p className="mt-2 text-sm">{item.passed_count}/{item.scenario_count} controls passed</p>{item.failures.length ? <p className="mt-2 text-xs text-red-700">Failures: {item.failures.join(", ")}</p> : null}</div>)}</div><div className="mt-6 border-t border-[var(--border)] pt-5"><h3 className="font-semibold">Tool proposals</h3><p className="mt-2 text-sm text-[var(--muted)]">Confirmed proposals remain proposals. Phase 11 does not execute financial, contractual, safety, access, deletion, communication, or workflow actions.</p><p className="mt-3 text-sm">Recorded proposals: {actions.length}</p></div></article>
          </section>
        ) : null}
      </div>
    </main>
  );
}
