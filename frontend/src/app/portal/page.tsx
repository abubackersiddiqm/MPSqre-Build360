import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import { PortalView, type Company, type Grant, type PortalShare } from "./portal-view";

export const metadata: Metadata = { title: "External portal" };
type ListResponse<T> = { items: T[] };

export default async function PortalPage() {
  const company = await tenantBackendRequest<Company>("/companies/current");
  if (!company.ok) redirect(company.status === 401 ? "/sign-in" : "/select-company");
  const [grants, shares] = await Promise.all([
    tenantBackendRequest<ListResponse<Grant>>("/portal/me"),
    tenantBackendRequest<ListResponse<PortalShare>>("/portal/me/shares"),
  ]);
  if (!grants.ok) redirect(grants.status === 401 ? "/sign-in" : "/platform");
  return <PortalView company={company.data} grants={grants.data.items} shares={shares.ok ? shares.data.items : []} />;
}
