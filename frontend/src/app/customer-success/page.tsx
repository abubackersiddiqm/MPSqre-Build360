import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import { CustomerSuccessWorkspace, type SuccessopsPortfolio } from "./workspace";

export const metadata: Metadata = {
  title: "Customer success and billing",
};

export default async function CustomerSuccessPage() {
  const result = await tenantBackendRequest<SuccessopsPortfolio>(
    "/customer-success/portfolio",
  );
  if (!result.ok) redirect(result.status === 401 ? "/sign-in" : "/platform");
  return <CustomerSuccessWorkspace initialData={result.data} />;
}
