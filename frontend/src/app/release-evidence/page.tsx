import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import { ReleaseEvidenceWorkspace, type ReleaseOverview } from "./workspace";

export const metadata: Metadata = { title: "Release evidence" };

type CapabilityResponse = { permissions: string[] };

export default async function ReleaseEvidencePage() {
  const capabilities = await tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities");
  if (!capabilities.ok) redirect(capabilities.status === 401 ? "/sign-in" : "/select-company");
  if (!capabilities.data.permissions.includes("release.view")) redirect("/platform");

  const overview = await tenantBackendRequest<ReleaseOverview>("/release-readiness/overview");
  if (!overview.ok) redirect("/platform/release-readiness");
  return <ReleaseEvidenceWorkspace payload={overview.data} />;
}
