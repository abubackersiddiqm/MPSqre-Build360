import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import { TodayWorkspace, type GuidedWorkbench } from "./workspace";

export const metadata: Metadata = { title: "Today" };

type CapabilityResponse = { permissions: string[] };

export default async function TodayPage() {
  const capabilities = await tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities");
  if (!capabilities.ok) redirect(capabilities.status === 401 ? "/sign-in" : "/select-company");
  const supported = new Set([
    "project.dashboard.read",
    "crm.dashboard.read",
    "workflow.approve",
    "design.review.decide",
    "finance.dashboard.read",
    "procurement.dashboard.read",
  ]);
  if (!capabilities.data.permissions.some((item) => supported.has(item))) redirect("/platform");
  const result = await tenantBackendRequest<GuidedWorkbench>("/projects/workbench");
  return <TodayWorkspace initialPayload={result.ok ? result.data : { generated_at: "", attention_count: 0, summary: { my_tasks: 0, crm_followups: 0, approvals: 0, overdue_invoices: 0, procurement_due: 0 }, sections: [], quick_actions: [] }} />;
}
