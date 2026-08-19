import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import { ExecutiveWorkspace, type ExecutivePayload } from "./workspace";

export const metadata: Metadata = { title: "Executive portfolio" };
type CapabilityResponse = { permissions: string[] };

export default async function ExecutivePage() {
  const capabilities = await tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities");
  if (!capabilities.ok) redirect(capabilities.status === 401 ? "/sign-in" : "/select-company");
  if (!capabilities.data.permissions.includes("project.dashboard.read")) redirect("/platform");
  const result = await tenantBackendRequest<ExecutivePayload>("/projects/executive");
  if (!result.ok) redirect("/project360");
  return <ExecutiveWorkspace payload={result.data} />;
}
