import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { platformBackendRequest } from "@/lib/auth/platform-backend";
import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import { WorkspaceCatalog } from "./workspace-catalog";

export const metadata: Metadata = { title: "All workspaces" };

type Company = {
  public_id: string;
  code: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
};
type CapabilityResponse = { permissions: string[] };
type OperatorResponse = { is_operator: boolean };

export default async function WorkspacesPage() {
  const companyResult = await tenantBackendRequest<Company>("/companies/current");
  if (!companyResult.ok) {
    redirect(companyResult.status === 401 ? "/sign-in" : "/select-company");
  }
  const capabilityResult = await tenantBackendRequest<CapabilityResponse>(
    "/companies/current/capabilities",
  );
  if (!capabilityResult.ok) {
    redirect(capabilityResult.status === 401 ? "/sign-in" : "/select-company");
  }
  const operatorResult = await platformBackendRequest<OperatorResponse>(
    "/control-plane/me",
  );

  return (
    <WorkspaceCatalog
      company={companyResult.data}
      permissions={capabilityResult.data.permissions}
      platformOperator={operatorResult.ok && operatorResult.data.is_operator}
    />
  );
}
