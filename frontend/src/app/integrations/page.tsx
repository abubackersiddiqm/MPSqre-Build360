import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import {
  IntegrationWorkspace,
  type ApiClient,
  type Company,
  type Connector,
  type ExchangeRate,
  type IntegrationSummary,
  type IntegrationProviderCatalogItem,
  type LocalizationPack,
  type MappingProfile,
  type SyncRun,
  type Webhook,
} from "./workspace";

export const metadata: Metadata = { title: "Globalization and Integration Hub" };
type CapabilityResponse = { permissions: string[]; features: Record<string, boolean> };
type ListResponse<T> = { items: T[] };

export default async function IntegrationsPage() {
  const companyResult = await tenantBackendRequest<Company>("/companies/current");
  if (!companyResult.ok) redirect(companyResult.status === 401 ? "/sign-in" : "/select-company");
  const capabilityResult = await tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities");
  if (!capabilityResult.ok) redirect(capabilityResult.status === 401 ? "/sign-in" : "/select-company");
  const permissions = capabilityResult.data.permissions;
  const features = capabilityResult.data.features ?? {};
  if (!permissions.includes("integration.dashboard.read")) redirect("/platform");
  const [summary, providers, packs, rates, connectors, clients, webhooks, mappings, syncRuns] = await Promise.all([
    tenantBackendRequest<IntegrationSummary>("/integrations/summary"),
    tenantBackendRequest<ListResponse<IntegrationProviderCatalogItem>>("/integrations/provider-catalog"),
    tenantBackendRequest<ListResponse<LocalizationPack>>("/integrations/localization-packs"),
    tenantBackendRequest<ListResponse<ExchangeRate>>("/integrations/exchange-rates"),
    tenantBackendRequest<ListResponse<Connector>>("/integrations/connectors"),
    features["platform.api_access"] === true
      ? tenantBackendRequest<ListResponse<ApiClient>>("/integrations/api-clients")
      : Promise.resolve({ ok: true as const, status: 200, data: { items: [] as ApiClient[] } }),
    tenantBackendRequest<ListResponse<Webhook>>("/integrations/webhooks"),
    tenantBackendRequest<ListResponse<MappingProfile>>("/integrations/mappings"),
    tenantBackendRequest<ListResponse<SyncRun>>("/integrations/sync-runs"),
  ]);
  return (
    <IntegrationWorkspace
      company={companyResult.data}
      permissions={permissions}
      features={features}
      initialSummary={summary.ok ? summary.data : null}
      initialProviders={providers.ok ? providers.data.items : []}
      initialPacks={packs.ok ? packs.data.items : []}
      initialRates={rates.ok ? rates.data.items : []}
      initialConnectors={connectors.ok ? connectors.data.items : []}
      initialClients={clients.ok ? clients.data.items : []}
      initialWebhooks={webhooks.ok ? webhooks.data.items : []}
      initialMappings={mappings.ok ? mappings.data.items : []}
      initialSyncRuns={syncRuns.ok ? syncRuns.data.items : []}
    />
  );
}
