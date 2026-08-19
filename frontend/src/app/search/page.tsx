import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import { SearchWorkspace } from "./workspace";

export const metadata: Metadata = { title: "Search Build360" };

type CapabilityResponse = { permissions: string[] };

export default async function SearchPage() {
  const capabilities = await tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities");
  if (!capabilities.ok) redirect(capabilities.status === 401 ? "/sign-in" : "/select-company");
  return <SearchWorkspace />;
}
