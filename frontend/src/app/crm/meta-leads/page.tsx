import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import { MetaLeadsWorkspace, type MetaLeadOverview } from "./workspace";

export const metadata: Metadata = { title: "Meta Lead Ads" };

type CapabilityResponse = { permissions: string[]; features: Record<string, boolean> };

export default async function MetaLeadsPage() {
  const capabilities = await tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities");
  if (!capabilities.ok) redirect(capabilities.status === 401 ? "/sign-in" : "/select-company");
  if (
    !capabilities.data.permissions.includes("integration.meta_leads.read")
    || capabilities.data.features?.["crm.meta_ads"] !== true
  ) redirect("/crm?tab=leads");

  const result = await tenantBackendRequest<MetaLeadOverview>("/integrations/meta-leads");
  if (!result.ok) redirect("/crm?tab=leads");

  return (
    <MetaLeadsWorkspace
      initial={result.data}
      permissions={capabilities.data.permissions}
    />
  );
}
