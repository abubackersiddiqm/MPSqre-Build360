import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import { ApprovalCenterWorkspace, type ApprovalCenterPayload } from "./workspace";

export const metadata: Metadata = { title: "My approvals" };

type CapabilityResponse = { permissions: string[] };

export default async function ApprovalsPage() {
  const capabilities = await tenantBackendRequest<CapabilityResponse>(
    "/companies/current/capabilities",
  );
  if (!capabilities.ok) {
    redirect(capabilities.status === 401 ? "/sign-in" : "/select-company");
  }
  const canApprove =
    capabilities.data.permissions.includes("workflow.approve") ||
    capabilities.data.permissions.includes("design.review.decide");
  if (!canApprove) redirect("/project360");

  const inbox = await tenantBackendRequest<ApprovalCenterPayload>("/workflow/approval-center");
  return (
    <ApprovalCenterWorkspace
      initialPayload={
        inbox.ok
          ? inbox.data
          : { items: [], summary: { pending: 0, overdue: 0, workflow: 0, design_reviews: 0 } }
      }
    />
  );
}
