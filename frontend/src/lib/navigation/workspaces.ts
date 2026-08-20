import type { Route } from "next";

export type WorkspaceKey =
  | "platform"
  | "today"
  | "search"
  | "release-evidence"
  | "crm"
  | "project360"
  | "executive"
  | "approvals"
  | "delivery"
  | "supply"
  | "field"
  | "finance"
  | "communications"
  | "operations"
  | "ai"
  | "adminops"
  | "controlplane"
  | "integrations"
  | "pilot"
  | "compliance"
  | "cloudops"
  | "success"
  | "people"
  | "brand";

export type WorkspaceDefinition = {
  key: WorkspaceKey;
  title: string;
  shortTitle: string;
  description: string;
  href: Route;
  badge: string;
  permissions?: string[];
  requireAllPermissions?: boolean;
  features?: string[];
  requireAllFeatures?: boolean;
  platformOperatorOnly?: boolean;
  mobilePrimary?: boolean;
};

export const WORKSPACES: readonly WorkspaceDefinition[] = [
  {
    key: "platform",
    title: "Operating overview",
    shortTitle: "Home",
    description: "Company controls, approvals, configuration and subscription status.",
    href: "/platform",
    badge: "OV",
    mobilePrimary: true,
  },
  {
    key: "today",
    title: "Today",
    shortTitle: "Today",
    description: "Permission-aware work, follow-ups, approvals, collections and procurement attention.",
    href: "/today",
    badge: "TD",
    permissions: [
      "project.dashboard.read",
      "crm.dashboard.read",
      "workflow.approve",
      "design.review.decide",
      "finance.dashboard.read",
      "procurement.dashboard.read",
    ],
    mobilePrimary: true,
  },
  {
    key: "search",
    title: "Search Build360",
    shortTitle: "Search",
    description: "Find projects, customers, leads, designs, purchase records, invoices and handover assets.",
    href: "/search",
    badge: "SE",
    permissions: [
      "project.dashboard.read",
      "crm.dashboard.read",
      "design.document.read",
      "design.dashboard.read",
      "procurement.dashboard.read",
      "finance.dashboard.read",
      "digitaltwin.view",
      "digitaltwin.handover",
    ],
  },
  {
    key: "release-evidence",
    title: "Release evidence",
    shortTitle: "Release",
    description: "Visual proof of release gates, UAT, automated readiness and restore-tested backups.",
    href: "/release-evidence",
    badge: "RE",
    platformOperatorOnly: true,
    permissions: ["release.view"],
  },
  {
    key: "crm",
    title: "CRM and customers",
    shortTitle: "CRM",
    description: "Customers, protected contacts, leads, opportunities and activities.",
    href: "/crm",
    badge: "CR",
    permissions: ["crm.dashboard.read"],
    features: ["crm.core"],
    mobilePrimary: true,
  },
  {
    key: "project360",
    title: "Project 360",
    shortTitle: "Projects",
    description: "Visual project journey, next actions, health and commercial context.",
    href: "/project360",
    badge: "P3",
    permissions: ["project.dashboard.read"],
    mobilePrimary: true,
    features: ["module.delivery"],
  },
  {
    key: "executive",
    title: "Executive portfolio",
    shortTitle: "Executive",
    description: "Portfolio health, schedule attention and permission-aware commercial exposure.",
    href: "/executive",
    badge: "EX",
    permissions: ["project.dashboard.read"],
    features: ["module.delivery"],
  },
  {
    key: "approvals",
    title: "My approvals",
    shortTitle: "Approvals",
    description: "One governed inbox for workflow decisions and design reviews.",
    href: "/approvals",
    badge: "AP",
    permissions: ["workflow.approve", "design.review.decide"],
  },
  {
    key: "delivery",
    title: "Project delivery",
    shortTitle: "Delivery",
    description: "Projects, WBS, design control, estimates and BOQ baselines.",
    href: "/delivery",
    badge: "DL",
    permissions: ["project.dashboard.read"],
    features: ["module.delivery"],
  },
  {
    key: "supply",
    title: "Supply chain",
    shortTitle: "Supply",
    description: "Vendors, procurement, RFQs, purchase orders and inventory.",
    href: "/supply",
    badge: "SC",
    permissions: [
      "vendor.dashboard.read",
      "procurement.dashboard.read",
      "inventory.dashboard.read",
    ],
    features: ["module.supply"],
  },
  {
    key: "field",
    title: "Field operations",
    shortTitle: "Field",
    description: "Labour, equipment, quality, safety and controlled offline work.",
    href: "/field-operations",
    badge: "FO",
    permissions: ["field.dashboard.read"],
    mobilePrimary: true,
    features: ["module.field"],
  },
  {
    key: "finance",
    title: "Finance and commercial",
    shortTitle: "Finance",
    description: "Budgets, variations, invoices, payments and commercial ledger.",
    href: "/finance",
    badge: "FN",
    permissions: ["finance.dashboard.read"],
    features: ["module.finance"],
  },
  {
    key: "communications",
    title: "Communications",
    shortTitle: "Comms",
    description: "Notifications, templates, consent, channels and delivery evidence.",
    href: "/communications",
    badge: "CM",
    permissions: ["communication.dashboard.read"],
    features: ["module.communication"],
  },
  {
    key: "operations",
    title: "Reports and operations",
    shortTitle: "Reports",
    description: "Reports, portals, imports, privacy, retention and recovery evidence.",
    href: "/operations",
    badge: "RP",
    permissions: ["reporting.dashboard.read"],
    features: ["module.reporting"],
  },
  {
    key: "ai",
    title: "Governed AI",
    shortTitle: "AI",
    description: "Grounded summaries, extraction review, risk signals and AI policies.",
    href: "/ai-control",
    badge: "AI",
    permissions: ["ai.dashboard.read"],
    features: ["module.ai"],
  },
  {
    key: "adminops",
    title: "Enterprise administration",
    shortTitle: "Admin",
    description: "Release governance, reliability, incidents and operational controls.",
    href: "/enterprise-admin",
    badge: "EA",
    platformOperatorOnly: true,
    permissions: ["adminops.dashboard.read"],
  },
  {
    key: "controlplane",
    title: "SaaS control plane",
    shortTitle: "SaaS",
    description: "Tenant lifecycle, plans, subscriptions, quotas and support access.",
    href: "/control-plane",
    badge: "CP",
    platformOperatorOnly: true,
  },
  {
    key: "integrations",
    title: "Globalization and integrations",
    shortTitle: "Integrations",
    description: "Localization packs, API clients, connectors, webhooks and mappings.",
    href: "/integrations",
    badge: "GI",
    permissions: ["integration.dashboard.read"],
    features: ["module.integrations"],
  },
  {
    key: "pilot",
    title: "Pilot readiness",
    shortTitle: "Launch",
    description: "Onboarding, master data, training, adoption and governed go-live.",
    href: "/pilot-readiness",
    badge: "PL",
    platformOperatorOnly: true,
    permissions: ["pilot.dashboard.read"],
  },
  {
    key: "compliance",
    title: "Security and compliance",
    shortTitle: "Compliance",
    description: "Controls, assessments, risks, exceptions and access reviews.",
    href: "/compliance",
    badge: "SC",
    permissions: ["compliance.dashboard.read"],
    features: ["module.compliance"],
  },
  {
    key: "cloudops",
    title: "Cloud launch",
    shortTitle: "Cloud",
    description: "Deployment targets, promotion pipelines, backups, restores and secret rotation.",
    href: "/cloud-launch",
    badge: "CL",
    platformOperatorOnly: true,
    permissions: ["cloudops.dashboard.read"],
  },
  {
    key: "people",
    title: "People operations",
    shortTitle: "People",
    description: "Employees, departments, leave, timesheets and payroll evidence.",
    href: "/people-operations",
    badge: "HR",
    permissions: ["people.dashboard.read"],
    features: ["module.people"],
  },
  {
    key: "brand",
    title: "White Label",
    shortTitle: "White Label",
    description: "Company identity, domains and verified white-label email delivery.",
    href: "/brand-domain",
    badge: "WL",
    permissions: ["tenant.branding.read", "tenant.domain.read"],
    features: ["tenant.white_label", "tenant.custom_domain"],
  },
  {
    key: "success",
    title: "Customer success and billing",
    shortTitle: "Success",
    description: "Account health, subscription billing, support SLAs, adoption and renewals.",
    href: "/customer-success",
    badge: "CS",
    platformOperatorOnly: true,
    permissions: ["success.dashboard.read"],
  },
] as const;

export type WorkspaceAccessContext = {
  permissions: readonly string[];
  features?: Readonly<Record<string, boolean>>;
  platformOperator: boolean;
};

export type WorkspaceAccessLevel = "NONE" | "VIEW" | "EDIT" | "FULL";

export function canAccessWorkspace(
  workspace: WorkspaceDefinition,
  context: WorkspaceAccessContext,
): boolean {
  if (workspace.platformOperatorOnly && !context.platformOperator) {
    return false;
  }
  if (workspace.features?.length) {
    const featureAccess = workspace.requireAllFeatures
      ? workspace.features.every((code) => context.features?.[code] === true)
      : workspace.features.some((code) => context.features?.[code] === true);
    if (!featureAccess) return false;
  }
  if (!workspace.permissions?.length) {
    return true;
  }
  const permissionSet = new Set(context.permissions);
  return workspace.requireAllPermissions
    ? workspace.permissions.every((permission) => permissionSet.has(permission))
    : workspace.permissions.some((permission) => permissionSet.has(permission));
}

const WORKSPACE_READ_TERMS = new Set(["read", "view", "list"]);
const WORKSPACE_EDIT_TERMS = new Set([
  "manage",
  "create",
  "update",
  "write",
  "edit",
  "add",
  "upload",
  "comment",
  "record",
  "complete",
  "schedule",
  "submit",
  "send",
  "respond",
  "acknowledge",
]);
const WORKSPACE_SENSITIVE_TERMS = new Set([
  "approve",
  "approval",
  "reject",
  "delete",
  "remove",
  "reveal",
  "assign",
  "transition",
  "convert",
  "override",
  "publish",
  "void",
  "refund",
  "impersonate",
  "rotate",
  "restore",
  "admin",
  "permission",
  "role",
]);

function permissionTerms(code: string): Set<string> {
  return new Set(
    code
      .replaceAll("-", ".")
      .split(".")
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean),
  );
}

function intersects(left: Set<string>, right: Set<string>): boolean {
  for (const item of left) {
    if (right.has(item)) return true;
  }
  return false;
}

export function workspaceAccessLevel(
  workspace: WorkspaceDefinition,
  context: WorkspaceAccessContext,
): WorkspaceAccessLevel {
  if (!canAccessWorkspace(workspace, context)) return "NONE";

  // Workspaces without a tenant permission contract are shell/admin surfaces.
  // If canAccessWorkspace() admitted the caller, do not invent a weaker level.
  if (!workspace.permissions?.length) return "FULL";

  const namespaces = new Set(
    workspace.permissions
      .map((permission) => permission.split(".", 1)[0]?.trim())
      .filter((value): value is string => Boolean(value)),
  );
  const relevantPermissions = context.permissions.filter((permission) => {
    const namespace = permission.split(".", 1)[0]?.trim();
    return Boolean(namespace && namespaces.has(namespace));
  });

  if (
    relevantPermissions.some((permission) =>
      intersects(permissionTerms(permission), WORKSPACE_SENSITIVE_TERMS),
    )
  ) {
    return "FULL";
  }
  if (
    relevantPermissions.some((permission) =>
      intersects(permissionTerms(permission), WORKSPACE_EDIT_TERMS),
    )
  ) {
    return "EDIT";
  }
  if (
    relevantPermissions.some((permission) =>
      intersects(permissionTerms(permission), WORKSPACE_READ_TERMS),
    )
  ) {
    return "VIEW";
  }

  // canAccessWorkspace() already proved at least one declared capability. Some
  // decision-only workspaces use verbs such as "decide"; treat those as FULL
  // rather than incorrectly labelling them as read-only.
  return "FULL";
}

export function visibleWorkspaces(
  context: WorkspaceAccessContext,
): WorkspaceDefinition[] {
  return WORKSPACES.filter(
    (workspace) => !workspace.platformOperatorOnly && canAccessWorkspace(workspace, context),
  );
}

export function workspaceForPath(pathname: string): WorkspaceDefinition | undefined {
  return WORKSPACES.find(
    (workspace) =>
      pathname === workspace.href || pathname.startsWith(`${workspace.href}/`),
  );
}

export const PROTECTED_ROUTE_PREFIXES = [
  "/platform",
  "/workspaces",
  ...WORKSPACES.filter((workspace) => workspace.href !== "/platform").map(
    (workspace) => workspace.href,
  ),
] as const;

export function isProtectedWorkspacePath(pathname: string): boolean {
  return PROTECTED_ROUTE_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}
