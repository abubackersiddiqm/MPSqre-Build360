import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import { PilotReadinessWorkspace, type PilotPortfolio } from "./workspace";

export const metadata: Metadata = {
  title: "Pilot readiness",
};

export default async function PilotReadinessPage() {
  const result = await tenantBackendRequest<PilotPortfolio>("/pilotops/portfolio");
  if (!result.ok) {
    redirect(result.status === 401 ? "/sign-in" : "/platform");
  }
  return <PilotReadinessWorkspace initialData={result.data} />;
}
