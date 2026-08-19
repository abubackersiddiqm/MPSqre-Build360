"use client";

import type { Route } from "next";
import Link from "next/link";
import { useMemo, useState } from "react";

export type ApprovalCenterItem = {
  kind: "WORKFLOW" | "DESIGN_REVIEW";
  public_id: string;
  title: string;
  eyebrow: string;
  subject_type: string;
  subject_public_id: string;
  transition_code: string;
  from_state_code: string;
  to_state_code: string;
  due_at: string | null;
  requested_at: string;
  overdue: boolean;
  revision_code?: string;
  stage_name?: string;
  record_version?: number;
  decision_endpoint: string;
  detail_href: Route | null;
};

export type ApprovalCenterPayload = {
  items: ApprovalCenterItem[];
  summary: {
    pending: number;
    overdue: number;
    workflow: number;
    design_reviews: number;
  };
};

type DecisionDraft = {
  item: ApprovalCenterItem;
  approved: boolean;
};

function formatDate(value: string | null) {
  if (!value) return "No due date";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function ApprovalCenterWorkspace({
  initialPayload,
}: Readonly<{ initialPayload: ApprovalCenterPayload }>) {
  const [payload, setPayload] = useState(initialPayload);
  const [filter, setFilter] = useState<"ALL" | "OVERDUE" | "WORKFLOW" | "DESIGN_REVIEW">("ALL");
  const [decision, setDecision] = useState<DecisionDraft | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  const visible = useMemo(
    () =>
      payload.items.filter((item) => {
        if (filter === "ALL") return true;
        if (filter === "OVERDUE") return item.overdue;
        return item.kind === filter;
      }),
    [filter, payload.items],
  );

  async function refresh() {
    const response = await fetch("/api/approvals/center", {
      cache: "no-store",
      credentials: "same-origin",
    }).catch(() => null);
    if (!response?.ok) return;
    setPayload((await response.json()) as ApprovalCenterPayload);
  }

  async function submitDecision() {
    if (!decision) return;
    setSubmitting(true);
    setMessage("");
    const isDesign = decision.item.kind === "DESIGN_REVIEW";
    const body = isDesign
      ? {
          decision: decision.approved ? "approved" : "rejected",
          comments: comment,
          expected_version: decision.item.record_version ?? 1,
        }
      : {
          approved: decision.approved,
          comment,
        };
    const response = await fetch(decision.item.decision_endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(body),
    }).catch(() => null);
    setSubmitting(false);
    if (!response?.ok) {
      const data = (await response?.json().catch(() => null)) as
        | { message?: string; details?: string[]; field_errors?: Record<string, string[]> }
        | null;
      setMessage(
        data?.details?.[0] ||
          data?.message ||
          "The approval decision could not be completed. Reload and try again.",
      );
      return;
    }
    setDecision(null);
    setComment("");
    await refresh();
  }

  return (
    <main className="min-h-screen bg-[var(--background)] px-4 py-6 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1450px] space-y-6">
        <header className="overflow-hidden rounded-[30px] border border-[var(--border)] bg-white p-6 shadow-sm lg:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--brand)]">
                Build360 · My approvals
              </p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
                One inbox for decisions.
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
                Workflow approvals and design reviews stay governed by their owning modules,
                while your actionable decisions appear in one simple workspace.
              </p>
            </div>
            <Link
              className="inline-flex rounded-xl border border-[var(--border)] bg-white px-4 py-3 text-sm font-semibold hover:border-[var(--brand)]"
              href="/project360"
            >
              Back to Project 360
            </Link>
          </div>
        </header>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {([
            ["Pending", payload.summary.pending, "ALL"],
            ["Overdue", payload.summary.overdue, "OVERDUE"],
            ["Workflow", payload.summary.workflow, "WORKFLOW"],
            ["Design reviews", payload.summary.design_reviews, "DESIGN_REVIEW"],
          ] as const).map(([label, value, key]) => (
            <button
              className={`rounded-3xl border p-5 text-left shadow-sm transition ${
                filter === key
                  ? "border-[var(--brand)] bg-[var(--brand-soft)]"
                  : "border-[var(--border)] bg-white hover:border-[var(--brand)]"
              }`}
              key={label}
              onClick={() => setFilter(key)}
              type="button"
            >
              <span className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--muted)]">
                {label}
              </span>
              <strong className="mt-2 block text-3xl">{value}</strong>
            </button>
          ))}
        </section>

        {message ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800">
            {message}
          </div>
        ) : null}

        <section className="space-y-3">
          {visible.length ? (
            visible.map((item) => (
              <article
                className={`rounded-[26px] border bg-white p-5 shadow-sm sm:p-6 ${
                  item.overdue ? "border-red-200" : "border-[var(--border)]"
                }`}
                key={`${item.kind}-${item.public_id}`}
              >
                <div className="flex flex-col gap-5 xl:flex-row xl:items-center">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${
                          item.kind === "DESIGN_REVIEW"
                            ? "bg-violet-50 text-violet-800"
                            : "bg-sky-50 text-sky-800"
                        }`}
                      >
                        {item.kind === "DESIGN_REVIEW" ? "DESIGN REVIEW" : "WORKFLOW"}
                      </span>
                      {item.overdue ? (
                        <span className="rounded-full bg-red-50 px-2.5 py-1 text-[10px] font-bold text-red-800">
                          OVERDUE
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-4 text-xs font-bold uppercase tracking-[0.14em] text-[var(--muted)]">
                      {item.eyebrow}
                    </p>
                    <h2 className="mt-1 text-xl font-semibold">{item.title}</h2>
                    <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-[var(--muted)]">
                      {item.kind === "DESIGN_REVIEW" ? (
                        <>
                          <span>Revision {item.revision_code}</span>
                          <span>{item.stage_name}</span>
                        </>
                      ) : (
                        <>
                          <span>{item.from_state_code} → {item.to_state_code}</span>
                          <span>{item.transition_code}</span>
                        </>
                      )}
                      <span>Due: {formatDate(item.due_at)}</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {item.detail_href ? (
                      <Link
                        className="rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-semibold hover:border-[var(--brand)]"
                        href={item.detail_href}
                      >
                        View context
                      </Link>
                    ) : null}
                    <button
                      className="rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-semibold text-red-800 hover:bg-red-100"
                      onClick={() => {
                        setDecision({ item, approved: false });
                        setComment("");
                        setMessage("");
                      }}
                      type="button"
                    >
                      Reject
                    </button>
                    <button
                      className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--brand-strong)]"
                      onClick={() => {
                        setDecision({ item, approved: true });
                        setComment("");
                        setMessage("");
                      }}
                      type="button"
                    >
                      Approve
                    </button>
                  </div>
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-[28px] border border-dashed border-slate-300 bg-white p-12 text-center">
              <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-emerald-50 text-2xl text-emerald-700">
                ✓
              </div>
              <h2 className="mt-4 text-2xl font-semibold">Nothing is waiting here</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">
                There are no actionable approvals for the selected filter.
              </p>
            </div>
          )}
        </section>
      </div>

      {decision ? (
        <div className="fixed inset-0 z-[90] grid place-items-center px-4">
          <button
            aria-label="Close approval decision"
            className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm"
            onClick={() => !submitting && setDecision(null)}
            type="button"
          />
          <div
            aria-modal="true"
            className="relative w-full max-w-lg rounded-[28px] border border-white/20 bg-white p-6 shadow-2xl"
            role="dialog"
          >
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--brand)]">
              {decision.approved ? "Approve" : "Reject"}
            </p>
            <h2 className="mt-2 text-2xl font-semibold">{decision.item.title}</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Your decision is executed by the owning governed workflow and remains auditable.
            </p>
            <label className="mt-5 block">
              <span className="text-sm font-semibold">Comment</span>
              <textarea
                className="mt-2 min-h-28 w-full rounded-2xl border border-[var(--border)] px-4 py-3 text-sm"
                onChange={(event) => setComment(event.target.value)}
                placeholder="Add decision context…"
                value={comment}
              />
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                className="rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-semibold"
                disabled={submitting}
                onClick={() => setDecision(null)}
                type="button"
              >
                Cancel
              </button>
              <button
                className={`rounded-xl px-4 py-2.5 text-sm font-semibold text-white ${
                  decision.approved ? "bg-[var(--brand)]" : "bg-red-700"
                } disabled:opacity-60`}
                disabled={submitting}
                onClick={() => void submitDecision()}
                type="button"
              >
                {submitting
                  ? "Saving…"
                  : decision.approved
                    ? "Confirm approval"
                    : "Confirm rejection"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
