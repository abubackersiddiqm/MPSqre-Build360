import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import {
  CommunicationWorkspace,
  type ChannelPolicy,
  type CommunicationRequest,
  type CommunicationSummary,
  type Company,
  type Notification,
  type NotificationRule,
  type NotificationSummary,
  type Preference,
  type Provider,
  type Template,
} from "./workspace";

export const metadata: Metadata = { title: "Communications and notifications" };
type CapabilityResponse = { permissions: string[] };
type ListResponse<T> = { items: T[] };

export default async function CommunicationsPage() {
  const companyResult = await tenantBackendRequest<Company>("/companies/current");
  if (!companyResult.ok) redirect(companyResult.status === 401 ? "/sign-in" : "/select-company");
  const capabilityResult = await tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities");
  if (!capabilityResult.ok) redirect(capabilityResult.status === 401 ? "/sign-in" : "/select-company");
  const permissions = capabilityResult.data.permissions;
  if (!permissions.includes("communication.dashboard.read")) redirect("/platform");
  const [communicationSummary, notificationSummary, policies, providers, templates, requests, notifications, preferences, rules] = await Promise.all([
    tenantBackendRequest<CommunicationSummary>("/communications/summary"),
    tenantBackendRequest<NotificationSummary>("/notifications/summary"),
    tenantBackendRequest<ListResponse<ChannelPolicy>>("/communications/policies"),
    tenantBackendRequest<ListResponse<Provider>>("/communications/providers"),
    tenantBackendRequest<ListResponse<Template>>("/communications/templates"),
    tenantBackendRequest<ListResponse<CommunicationRequest>>("/communications/requests"),
    tenantBackendRequest<ListResponse<Notification>>("/notifications/items"),
    tenantBackendRequest<ListResponse<Preference>>("/notifications/preferences"),
    tenantBackendRequest<ListResponse<NotificationRule>>("/notifications/rules"),
  ]);
  return (
    <CommunicationWorkspace
      company={companyResult.data}
      permissions={permissions}
      initialCommunicationSummary={communicationSummary.ok ? communicationSummary.data : null}
      initialNotificationSummary={notificationSummary.ok ? notificationSummary.data : null}
      initialPolicies={policies.ok ? policies.data.items : []}
      initialProviders={providers.ok ? providers.data.items : []}
      initialTemplates={templates.ok ? templates.data.items : []}
      initialRequests={requests.ok ? requests.data.items : []}
      initialNotifications={notifications.ok ? notifications.data.items : []}
      initialPreferences={preferences.ok ? preferences.data.items : []}
      initialRules={rules.ok ? rules.data.items : []}
    />
  );
}
