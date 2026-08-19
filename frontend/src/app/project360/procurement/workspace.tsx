"use client";

import Link from "next/link";
import { ChangeEvent, useEffect, useState } from "react";

export type Project = { public_id: string; code: string; name: string };
type Req = {
  public_id: string;
  request_number: string;
  title: string;
  required_by_date: string | null;
  currency: string;
  estimated_total: string;
  stage_name: string;
  current_step: string;
  status: string;
  next_action: string;
  counts: { rfqs: number; quotes: number; purchase_orders: number; receipts: number };
  purchase_orders: {
    public_id: string;
    po_number: string;
    vendor_name: string;
    total_amount: string;
    currency: string;
    stage_name: string;
    receipt_count: number;
  }[];
};
type Payload = {
  project: Project;
  summary: {
    requests: number;
    rfqs: number;
    quotes: number;
    purchase_orders: number;
    receipts: number;
    action_required: number;
    po_value: string;
    currency: string;
  };
  requests: Req[];
};

const stepStyle: Record<string, string> = {
  COMPLETE: "bg-emerald-50 text-emerald-800",
  ACTION: "bg-red-50 text-red-800",
  WAITING: "bg-amber-50 text-amber-900",
};

export function ProcurementFlowWorkspace({
  initialProjects,
  initialProject,
}: Readonly<{ initialProjects: Project[]; initialProject: string }>) {
  const first = initialProjects.some((project) => project.public_id === initialProject)
    ? initialProject
    : initialProjects[0]?.public_id ?? "";
  const [project, setProject] = useState(first);
  const [payload, setPayload] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(Boolean(first));
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!project) return;
    const controller = new AbortController();
    void fetch(`/api/project360/projects/${project}/procurement-flow`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = await response.json() as Payload & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Procurement flow could not load.");
        return body;
      })
      .then((body) => {
        if (!controller.signal.aborted) {
          setPayload(body);
          setLoading(false);
        }
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setMessage(caught instanceof Error ? caught.message : "Procurement flow could not load.");
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [project]);

  function selectProject(event: ChangeEvent<HTMLSelectElement>) {
    const nextProject = event.target.value;
    setProject(nextProject);
    setPayload(null);
    setMessage("");
    setLoading(Boolean(nextProject));
  }

  return (
    <main className="min-h-screen bg-[var(--background)] px-4 py-6 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1500px] space-y-6">
        <header className="rounded-[30px] border border-[var(--border)] bg-white p-6 shadow-sm lg:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[.2em] text-[var(--brand)]">Project 360 · Procurement</p>
              <h1 className="mt-2 text-3xl font-semibold">Request → RFQ → Quote → PO → Receipt.</h1>
              <p className="mt-2 text-sm text-[var(--muted)]">A visual trace over the existing procurement records — not a second procurement database.</p>
            </div>
            <select
              className="rounded-2xl border border-[var(--border)] bg-white px-4 py-3 text-sm font-semibold lg:w-[380px]"
              value={project}
              onChange={selectProject}
            >
              <option value="">Select project</option>
              {initialProjects.map((item) => <option key={item.public_id} value={item.public_id}>{item.code} · {item.name}</option>)}
            </select>
          </div>
          {payload ? (
            <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {[
                ["Requests", payload.summary.requests],
                ["RFQs", payload.summary.rfqs],
                ["Quotes", payload.summary.quotes],
                ["POs", payload.summary.purchase_orders],
                ["Receipts", payload.summary.receipts],
                ["Action needed", payload.summary.action_required],
              ].map(([label, value]) => (
                <div className="rounded-2xl bg-slate-50 p-4" key={String(label)}>
                  <p className="text-[11px] font-semibold text-[var(--muted)]">{label}</p>
                  <p className="mt-2 text-2xl font-semibold">{value}</p>
                </div>
              ))}
            </div>
          ) : null}
        </header>

        {message ? <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{message}</div> : null}
        {loading ? <div className="h-52 animate-pulse rounded-[28px] bg-slate-200" /> : null}
        {payload ? (
          <section className="grid gap-4 xl:grid-cols-2">
            {payload.requests.map((request) => (
              <article className="rounded-[28px] border border-[var(--border)] bg-white p-5 shadow-sm sm:p-6" key={request.public_id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[.14em] text-[var(--muted)]">{request.request_number}</p>
                    <h2 className="mt-1 text-xl font-semibold">{request.title}</h2>
                    <p className="mt-1 text-xs text-[var(--muted)]">
                      {request.required_by_date ? `Required ${request.required_by_date}` : "No required date"} · {request.currency} {Number(request.estimated_total).toLocaleString("en-IN")}
                    </p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-[10px] font-bold ${stepStyle[request.status] ?? "bg-slate-100"}`}>{request.current_step}</span>
                </div>
                <div className="mt-5 grid grid-cols-4 gap-2">
                  {[
                    ["RFQ", request.counts.rfqs],
                    ["Quotes", request.counts.quotes],
                    ["PO", request.counts.purchase_orders],
                    ["Receipt", request.counts.receipts],
                  ].map(([label, value]) => (
                    <div className="rounded-2xl bg-slate-50 p-3 text-center" key={String(label)}>
                      <p className="text-xl font-semibold">{value}</p>
                      <p className="text-[10px] text-[var(--muted)]">{label}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-4 rounded-2xl bg-[var(--brand-soft)] p-4">
                  <p className="text-[10px] font-bold uppercase tracking-[.14em] text-[var(--brand)]">Next action</p>
                  <p className="mt-1 text-sm font-semibold">{request.next_action}</p>
                </div>
                {request.purchase_orders.length ? (
                  <div className="mt-4 space-y-2">
                    {request.purchase_orders.map((purchaseOrder) => (
                      <div className="rounded-2xl border border-[var(--border)] p-3" key={purchaseOrder.public_id}>
                        <div className="flex justify-between gap-3">
                          <div>
                            <p className="font-semibold">{purchaseOrder.po_number}</p>
                            <p className="text-xs text-[var(--muted)]">{purchaseOrder.vendor_name} · {purchaseOrder.stage_name}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-semibold">{purchaseOrder.currency} {Number(purchaseOrder.total_amount).toLocaleString("en-IN")}</p>
                            <p className="text-xs text-[var(--muted)]">{purchaseOrder.receipt_count} receipt(s)</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
                <Link className="mt-4 inline-flex text-xs font-semibold text-[var(--brand)]" href="/supply">Open governed supply workspace →</Link>
              </article>
            ))}
            {!payload.requests.length ? (
              <div className="rounded-[28px] border border-dashed border-slate-300 bg-white p-12 text-center text-sm text-[var(--muted)] xl:col-span-2">
                No purchase requests are linked to this project.
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </main>
  );
}
