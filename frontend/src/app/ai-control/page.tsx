import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import {
  AIWorkspace,
  type AIAction,
  type AIEvaluation,
  type AIExtraction,
  type AIInteraction,
  type AIPolicy,
  type AIRisk,
  type AISummary,
  type Company,
} from "./workspace";

export const metadata: Metadata = { title: "Governed AI controls" };
type CapabilityResponse = { permissions: string[] };
type ListResponse<T> = { items: T[] };

export default async function AIControlPage() {
  const company = await tenantBackendRequest<Company>("/companies/current");
  if (!company.ok) redirect(company.status === 401 ? "/sign-in" : "/select-company");
  const capabilities = await tenantBackendRequest<CapabilityResponse>(
    "/companies/current/capabilities",
  );
  if (!capabilities.ok) redirect(capabilities.status === 401 ? "/sign-in" : "/select-company");
  const permissions = capabilities.data.permissions;
  if (!permissions.includes("ai.dashboard.read")) redirect("/platform");

  const [summary, policies, interactions, extractions, risks, actions, evaluations] =
    await Promise.all([
      tenantBackendRequest<AISummary>("/ai/summary"),
      tenantBackendRequest<ListResponse<AIPolicy>>("/ai/policies"),
      tenantBackendRequest<ListResponse<AIInteraction>>("/ai/interactions"),
      tenantBackendRequest<ListResponse<AIExtraction>>("/ai/extractions"),
      tenantBackendRequest<ListResponse<AIRisk>>("/ai/risks"),
      tenantBackendRequest<ListResponse<AIAction>>("/ai/actions"),
      tenantBackendRequest<ListResponse<AIEvaluation>>("/ai/evaluations"),
    ]);

  return (
    <AIWorkspace
      company={company.data}
      permissions={permissions}
      initialSummary={summary.ok ? summary.data : null}
      initialPolicies={policies.ok ? policies.data.items : []}
      initialInteractions={interactions.ok ? interactions.data.items : []}
      initialExtractions={extractions.ok ? extractions.data.items : []}
      initialRisks={risks.ok ? risks.data.items : []}
      initialActions={actions.ok ? actions.data.items : []}
      initialEvaluations={evaluations.ok ? evaluations.data.items : []}
    />
  );
}
