import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import { ComplianceWorkspace, type CompliancePortfolio } from "./workspace";

export const metadata: Metadata = {
  title: "Security and compliance",
};

export default async function CompliancePage() {
  const result = await tenantBackendRequest<CompliancePortfolio>("/compliance/portfolio");
  if (!result.ok) {
    redirect(result.status === 401 ? "/sign-in" : "/platform");
  }
  return <ComplianceWorkspace initialData={result.data} />;
}
