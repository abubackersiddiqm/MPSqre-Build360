import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { platformBackendRequest } from "@/lib/auth/platform-backend";

import {
  ControlPlaneWorkspace,
  type ControlPlaneSummary,
  type OperatorProfile,
  type Plan,
  type Subscription,
  type SupportRequest,
  type TenantAccount,
  type UsageSnapshot,
} from "./workspace";

export const metadata: Metadata = { title: "SaaS control plane" };
type ListResponse<T> = { items: T[] };

export default async function ControlPlanePage() {
  const operator = await platformBackendRequest<OperatorProfile>("/control-plane/me");
  if (!operator.ok) {
    redirect(operator.status === 401 ? "/sign-in" : "/platform");
  }
  if (!operator.data.permissions.includes("controlplane.dashboard.read")) {
    redirect("/platform");
  }
  const [summary, tenants, plans, subscriptions, usage, support] = await Promise.all([
    platformBackendRequest<ControlPlaneSummary>("/control-plane/summary"),
    platformBackendRequest<ListResponse<TenantAccount>>("/control-plane/tenants"),
    platformBackendRequest<ListResponse<Plan>>("/control-plane/plans"),
    platformBackendRequest<ListResponse<Subscription>>("/control-plane/subscriptions"),
    platformBackendRequest<ListResponse<UsageSnapshot>>("/control-plane/usage"),
    platformBackendRequest<ListResponse<SupportRequest>>("/control-plane/support-requests"),
  ]);
  return (
    <ControlPlaneWorkspace
      operator={operator.data}
      initialSummary={summary.ok ? summary.data : null}
      initialTenants={tenants.ok ? tenants.data.items : []}
      initialPlans={plans.ok ? plans.data.items : []}
      initialSubscriptions={subscriptions.ok ? subscriptions.data.items : []}
      initialUsage={usage.ok ? usage.data.items : []}
      initialSupportRequests={support.ok ? support.data.items : []}
    />
  );
}
