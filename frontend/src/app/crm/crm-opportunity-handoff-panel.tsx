"use client";

import type { Route } from "next";
import Link from "next/link";

export type OpportunityHandoffResult = {
  opportunity_public_id: string;
  public_id: string;
  code: string;
  name: string;
  created: boolean;
  mode: "preconstruction" | "award";
  message: string;
};

type Props = {
  result: OpportunityHandoffResult;
  canOpenDesign: boolean;
  canOpenEstimation: boolean;
  onClose: () => void;
};

export function CrmOpportunityHandoffPanel({
  result,
  canOpenDesign,
  canOpenEstimation,
  onClose,
}: Readonly<Props>) {
  const projectHref = `/project360?project=${result.public_id}` as Route;
  const designHref = `/project360/design?project=${result.public_id}` as Route;
  const estimationHref = `/delivery?tab=estimation&project=${result.public_id}` as Route;

  return (
    <section className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-5" aria-label="CRM opportunity handoff">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-800">
            {result.created ? "Workspace created" : "Existing workspace reused"}
          </p>
          <h3 className="mt-1 text-xl font-semibold text-emerald-950">
            {result.code} · {result.name}
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-emerald-900">{result.message}</p>
          <p className="mt-2 text-xs font-medium text-emerald-800">
            CRM stays the sales source. Design, estimation and delivery continue on this one governed project.
          </p>
        </div>
        <button
          className="rounded-lg border border-emerald-300 px-3 py-2 text-xs font-semibold text-emerald-900"
          onClick={onClose}
          type="button"
        >
          Close
        </button>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Link className="rounded-xl bg-emerald-950 px-4 py-3 text-sm font-semibold text-white" href={projectHref}>
          1. Open Project 360 →
        </Link>
        {canOpenDesign ? (
          <Link className="rounded-xl border border-emerald-300 bg-white px-4 py-3 text-sm font-semibold text-emerald-950" href={designHref}>
            2. Architect / Design →
          </Link>
        ) : (
          <div className="rounded-xl border border-dashed border-emerald-300 px-4 py-3 text-sm text-emerald-900">
            2. Design access not assigned
          </div>
        )}
        {canOpenEstimation ? (
          <Link className="rounded-xl border border-emerald-300 bg-white px-4 py-3 text-sm font-semibold text-emerald-950" href={estimationHref}>
            3. Estimation & BOQ →
          </Link>
        ) : (
          <div className="rounded-xl border border-dashed border-emerald-300 px-4 py-3 text-sm text-emerald-900">
            3. Estimation access not assigned
          </div>
        )}
        <Link className="rounded-xl border border-emerald-300 bg-white px-4 py-3 text-sm font-semibold text-emerald-950" href="/platform/operational-flow">
          View full process →
        </Link>
      </div>
    </section>
  );
}
