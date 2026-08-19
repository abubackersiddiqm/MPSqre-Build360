import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import { PeopleOperationsWorkspace, type PeopleopsPortfolio } from "./workspace";

export const metadata: Metadata = {
  title: "People operations",
};

export default async function PeopleOperationsPage() {
  const result = await tenantBackendRequest<PeopleopsPortfolio>("/people/portfolio");
  if (!result.ok) redirect(result.status === 401 ? "/sign-in" : "/platform");
  return <PeopleOperationsWorkspace initialData={result.data} />;
}
