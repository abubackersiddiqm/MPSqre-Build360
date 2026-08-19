import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import { CloudLaunchWorkspace, type CloudopsPortfolio } from "./workspace";

export const metadata: Metadata = {
  title: "Cloud launch and deployment",
};

export default async function CloudLaunchPage() {
  const result = await tenantBackendRequest<CloudopsPortfolio>("/cloudops/portfolio");
  if (!result.ok) {
    redirect(result.status === 401 ? "/sign-in" : "/platform");
  }
  return <CloudLaunchWorkspace initialData={result.data} />;
}
