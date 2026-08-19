import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { platformBackendRequest } from "@/lib/auth/platform-backend";
import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import { PlatformSummary, type PlatformSummaryProps } from "./platform-summary";

export const metadata: Metadata = {
  title: "Platform controls",
};

type CapabilityResponse = { permissions: string[]; features: Record<string, boolean> };
type ConfigurationResponse = { items: PlatformSummaryProps["configurations"] };
type ApprovalResponse = { items: PlatformSummaryProps["approvals"] };
type OperatorResponse = { is_operator: boolean };

export default async function PlatformPage() {
  const companyResult = await tenantBackendRequest<PlatformSummaryProps["company"]>(
    "/companies/current",
  );
  if (!companyResult.ok) {
    redirect(companyResult.status === 401 ? "/sign-in" : "/select-company");
  }

  const capabilityResult = await tenantBackendRequest<CapabilityResponse>(
    "/companies/current/capabilities",
  );
  if (!capabilityResult.ok) {
    redirect(capabilityResult.status === 401 ? "/sign-in" : "/select-company");
  }
  const permissions = capabilityResult.data.permissions;
  const features = capabilityResult.data.features ?? {};

  const [entitlementResult, configurationResult, approvalResult, operatorResult] = await Promise.all([
    permissions.includes("subscription.read")
      ? tenantBackendRequest<PlatformSummaryProps["entitlements"]>(
          "/subscriptions/effective",
        )
      : Promise.resolve({ ok: false as const, status: 403 }),
    permissions.includes("configuration.read")
      ? tenantBackendRequest<ConfigurationResponse>("/configurations/")
      : Promise.resolve({ ok: false as const, status: 403 }),
    permissions.includes("workflow.approve")
      ? tenantBackendRequest<ApprovalResponse>("/workflows/approvals")
      : Promise.resolve({ ok: false as const, status: 403 }),
    platformBackendRequest<OperatorResponse>("/control-plane/me"),
  ]);

  return (
    <PlatformSummary
      approvals={approvalResult.ok ? approvalResult.data.items : []}
      company={companyResult.data}
      configurations={configurationResult.ok ? configurationResult.data.items : []}
      entitlements={entitlementResult.ok ? entitlementResult.data : null}
      features={features}
      permissions={permissions}
      platformOperator={operatorResult.ok && operatorResult.data.is_operator}
    />
  );
}
