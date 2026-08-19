import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import {
  CrmWorkspace,
  type Activity,
  type ActivityDashboard,
  type Contact,
  type CrmSummary,
  type Customer,
  type Lead,
  type Opportunity,
  type PipelineStage,
} from "./crm-workspace";
import type { CrmConfiguration } from "./crm-configuration-panel";
import type { CrmMyWorkPayload } from "./crm-relationship-360";

export const metadata: Metadata = { title: "CRM workspace" };

type Company = {
  public_id: string;
  code: string;
  display_name: string;
  currency: string;
  timezone: string;
};
type CapabilityResponse = { permissions: string[]; features: Record<string, boolean> };
type ListResponse<T> = { items: T[] };

type PageProps = { searchParams: Promise<{ tab?: string }> };

export default async function CrmPage({ searchParams }: Readonly<PageProps>) {
  const query = await searchParams;
  const [companyResult, capabilityResult] = await Promise.all([
    tenantBackendRequest<Company>("/companies/current"),
    tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities"),
  ]);
  if (!companyResult.ok || !capabilityResult.ok) {
    const status = !companyResult.ok ? companyResult.status : capabilityResult.status;
    redirect(status === 401 ? "/sign-in" : "/select-company");
  }
  const permissions = capabilityResult.data.permissions;
  const features = capabilityResult.data.features ?? {};
  if (!permissions.includes("crm.dashboard.read") || features["crm.core"] !== true) redirect("/platform");

  const [summary, contacts, leads, customers, opportunities, stages, activities, activityDashboard, configuration, myWork] = await Promise.all([
    tenantBackendRequest<CrmSummary>("/crm/summary"),
    permissions.includes("crm.contact.read")
      ? tenantBackendRequest<ListResponse<Contact>>("/crm/contacts?limit=100")
      : Promise.resolve({ ok: true as const, status: 200, data: { items: [] } }),
    permissions.includes("crm.lead.read")
      ? tenantBackendRequest<ListResponse<Lead>>("/crm/leads?limit=100")
      : Promise.resolve({ ok: true as const, status: 200, data: { items: [] } }),
    permissions.includes("crm.customer.read")
      ? tenantBackendRequest<ListResponse<Customer>>("/crm/customers?limit=100")
      : Promise.resolve({ ok: true as const, status: 200, data: { items: [] } }),
    permissions.includes("crm.opportunity.read")
      ? tenantBackendRequest<ListResponse<Opportunity>>("/crm/opportunities?limit=100")
      : Promise.resolve({ ok: true as const, status: 200, data: { items: [] } }),
    permissions.includes("crm.stage.read")
      ? tenantBackendRequest<ListResponse<PipelineStage>>("/crm/stages")
      : Promise.resolve({ ok: true as const, status: 200, data: { items: [] } }),
    permissions.includes("crm.activity.read")
      ? tenantBackendRequest<ListResponse<Activity>>("/crm/activities?limit=100")
      : Promise.resolve({ ok: true as const, status: 200, data: { items: [] } }),
    permissions.includes("crm.activity.read") && features["crm.analytics"] === true
      ? tenantBackendRequest<ActivityDashboard>("/crm/activities/dashboard")
      : Promise.resolve({
          ok: true as const,
          status: 200,
          data: { generated_at: "", today: 0, overdue: 0, upcoming_7d: 0, followups: 0, recent_activity_24h: 0, new_leads_24h: 0, unassigned_leads: 0, by_type: [] },
        }),
    permissions.includes("crm.configuration.read")
      ? tenantBackendRequest<CrmConfiguration>("/crm/configuration")
      : Promise.resolve({
          ok: true as const,
          status: 200,
          data: {
            profile: { public_id: "", industry_code: "general", terminology: { customer: "Customer", contact: "Contact", lead: "Lead", opportunity: "Opportunity", pipeline: "Pipeline", quote: "Quote" }, settings: {}, version: 1 },
            industry_packs: [], pipelines: [], stages: [], custom_fields: [], lead_sources: [],
          } satisfies CrmConfiguration,
        }),
    tenantBackendRequest<CrmMyWorkPayload>("/crm/my-work"),
  ]);
  if (!summary.ok) redirect(summary.status === 401 ? "/sign-in" : "/platform");

  return (
    <CrmWorkspace
      activities={activities.ok ? activities.data.items : []}
      activityDashboard={activityDashboard.ok ? activityDashboard.data : { generated_at: "", today: 0, overdue: 0, upcoming_7d: 0, followups: 0, recent_activity_24h: 0, new_leads_24h: 0, unassigned_leads: 0, by_type: [] }}
      company={companyResult.data}
      configuration={configuration.ok ? configuration.data : { profile: { public_id: "", industry_code: "general", terminology: { customer: "Customer", contact: "Contact", lead: "Lead", opportunity: "Opportunity", pipeline: "Pipeline", quote: "Quote" }, settings: {}, version: 1 }, industry_packs: [], pipelines: [], stages: [], custom_fields: [], lead_sources: [] }}
      contacts={contacts.ok ? contacts.data.items : []}
      defaultTab={query.tab}
      customers={customers.ok ? customers.data.items : []}
      leads={leads.ok ? leads.data.items : []}
      myWork={myWork.ok ? myWork.data : { generated_at: "", counts: { overdue: 0, today: 0, tomorrow: 0, this_week: 0, callback_requested: 0, no_next_action: 0, new_uncontacted: 0 }, queue: [] }}
      opportunities={opportunities.ok ? opportunities.data.items : []}
      permissions={permissions}
      features={features}
      stages={stages.ok ? stages.data.items : []}
      summary={summary.data}
    />
  );
}
