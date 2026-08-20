"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import styles from "./phase-workspace-nav.module.css";

type OperationWorkspace = {
  phase: number;
  code: string;
  label: string;
  href: Route;
  feature: string;
  permissions: readonly string[];
};

const OPERATIONS: readonly OperationWorkspace[] = [
  { phase: 21, code: "PY", label: "Payroll operations", href: "/platform/payroll-operations", feature: "module.payroll", permissions: ["payroll.view"] },
  { phase: 22, code: "WP", label: "Workforce planning", href: "/platform/workforce-planning", feature: "module.workforce", permissions: ["workforce.view"] },
  { phase: 23, code: "EQ", label: "Equipment operations", href: "/platform/equipment-operations", feature: "module.equipment", permissions: ["equipment.view"] },
  { phase: 24, code: "HS", label: "HSE & safety", href: "/platform/safety-operations", feature: "module.hse", permissions: ["safety.view"] },
  { phase: 25, code: "QA", label: "Quality & QA/QC", href: "/platform/quality-operations", feature: "module.quality", permissions: ["quality.view"] },
  { phase: 26, code: "DC", label: "Document control", href: "/platform/document-control", feature: "module.documents", permissions: ["document.view"] },
  { phase: 27, code: "CO", label: "Contracts & claims", href: "/platform/commercial-operations", feature: "module.commercial", permissions: ["commercial.view"] },
  { phase: 30, code: "PW", label: "Project & work", href: "/platform/project-work", feature: "module.delivery", permissions: ["work.view"] },
  { phase: 32, code: "XC", label: "External collaboration", href: "/platform/external-collaboration", feature: "module.partner", permissions: ["collaboration.view"] },
  { phase: 38, code: "ES", label: "Sustainability & ESG", href: "/platform/sustainability-operations", feature: "module.sustainability", permissions: ["sustainability.view"] },
  { phase: 39, code: "DT", label: "BIM & digital twin", href: "/platform/digital-twin-operations", feature: "module.digital_twin", permissions: ["digitaltwin.view"] },
  { phase: 40, code: "FM", label: "Facilities & asset lifecycle", href: "/platform/facilities-operations", feature: "module.facilities", permissions: ["facility.view"] },
  { phase: 41, code: "PL", label: "Property & lease operations", href: "/platform/property-lease-operations", feature: "module.property", permissions: ["lease.view"] },
  { phase: 42, code: "RS", label: "Development sales & booking", href: "/platform/development-sales-operations", feature: "module.sales", permissions: ["sales.view"] },
  { phase: 43, code: "LA", label: "Land acquisition & feasibility", href: "/platform/land-acquisition-operations", feature: "module.land", permissions: ["land.view"] },
  { phase: 44, code: "CF", label: "Capital, JV & investors", href: "/platform/capital-investment-operations", feature: "module.capital", permissions: ["capital.view"] },
  { phase: 45, code: "RT", label: "Insurance, bonds & risk transfer", href: "/platform/risk-transfer-operations", feature: "module.risk_transfer", permissions: ["risktransfer.view"] },
] as const;

type NavigationAccess = {
  is_platform_operator: boolean;
  can_manage_access: boolean;
  can_manage_people: boolean;
  can_use_my_work: boolean;
  can_use_partner_portal: boolean;
  permissions: string[];
  features: Record<string, boolean>;
};

const EMPTY_ACCESS: NavigationAccess = {
  is_platform_operator: false,
  can_manage_access: false,
  can_manage_people: false,
  can_use_my_work: false,
  can_use_partner_portal: false,
  permissions: [],
  features: {},
};

const accessCache = new Map<"internal" | "partner", NavigationAccess>();
const pendingAccess = new Map<"internal" | "partner", Promise<NavigationAccess>>();

async function loadNavigationAccess(mode: "internal" | "partner"): Promise<NavigationAccess> {
  const cached = accessCache.get(mode);
  if (cached) return cached;
  const pending = pendingAccess.get(mode);
  if (pending) return pending;

  const request = fetch(`/api/navigation/access?mode=${mode}`, { cache: "no-store" })
    .then(async (response) => {
      if (!response.ok) return EMPTY_ACCESS;
      return (await response.json()) as NavigationAccess;
    })
    .catch(() => EMPTY_ACCESS)
    .then((payload) => {
      accessCache.set(mode, payload);
      pendingAccess.delete(mode);
      return payload;
    });
  pendingAccess.set(mode, request);
  return request;
}

function WorkspaceLink({ href, code, label, meta, pathname }: { href: Route; code: string; label: string; meta: string; pathname: string }) {
  const isActive = pathname === href || pathname.startsWith(`${href}/`);
  return (
    <Link href={href} className={`${styles.link} ${isActive ? styles.active : ""}`} aria-current={isActive ? "page" : undefined} data-phase-link title={label}>
      <span className={styles.icon} aria-hidden="true">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">
          <path d="M4 5h16v14H4Z" />
          <path d="M8 9h8M8 13h5" />
        </svg>
      </span>
      <span className={styles.copy} data-phase-copy><strong>{label}</strong><small>{meta}</small></span>
    </Link>
  );
}

export function PhaseWorkspaceNav() {
  const pathname = usePathname();
  const isPartnerRoute = pathname === "/partner" || pathname.startsWith("/partner/");
  const mode: "internal" | "partner" = isPartnerRoute ? "partner" : "internal";
  const [access, setAccess] = useState<NavigationAccess>(() => accessCache.get(mode) ?? EMPTY_ACCESS);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void loadNavigationAccess(mode).then((payload) => {
        if (active) setAccess(payload);
      });
    }, 100);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [mode]);

  const enabledOperations = useMemo(() => {
    const permissionSet = new Set(access.permissions);
    return OPERATIONS.filter(
      (workspace) =>
        access.features[workspace.feature] === true &&
        workspace.permissions.some((permission) => permissionSet.has(permission)),
    );
  }, [access.features, access.permissions]);
  const permissionSet = useMemo(() => new Set(access.permissions), [access.permissions]);
  const canManageBrand =
    (access.features["tenant.white_label"] === true && permissionSet.has("tenant.branding.read")) ||
    (access.features["tenant.custom_domain"] === true && permissionSet.has("tenant.domain.read"));

  if (isPartnerRoute) {
    return access.can_use_partner_portal ? (
      <section className={styles.section} aria-label="External partner workspace">
        <div className={styles.heading}><span>Partner portal</span><small>External</small></div>
        <div className={styles.links}>
          <WorkspaceLink href="/partner" code="EP" label="External partner desk" meta="Requests, submissions & messages" pathname={pathname} />
        </div>
      </section>
    ) : null;
  }

  return (
    <>
      {access.can_manage_access || canManageBrand || (access.can_manage_people && access.features["module.people"] === true) ? (
        <section className={styles.section} aria-label="Administration workspaces">
          <div className={styles.heading}><span>Administration</span><small>Role-aware</small></div>
          <div className={styles.links}>
            {access.can_manage_access ? <WorkspaceLink href="/platform/access-control" code="US" label="Users" meta="Invite, suspend & remove company users" pathname={pathname} /> : null}
            {canManageBrand ? <WorkspaceLink href="/brand-domain" code="WB" label="Brand & domains" meta="White-label identity and tenant domains" pathname={pathname} /> : null}
            {access.can_manage_people && access.features["module.people"] === true ? <WorkspaceLink href="/platform/people-organization" code="HR" label="People & organization" meta="People operations" pathname={pathname} /> : null}
          </div>
        </section>
      ) : null}

      {access.can_use_my_work ? (
        <section className={styles.section} aria-label="Personal employee workspace">
          <div className={styles.heading}><span>Personal</span><small>My work</small></div>
          <div className={styles.links}>
            <WorkspaceLink href="/platform/my-work" code="MW" label="My work" meta="Today, time & approvals" pathname={pathname} />
          </div>
        </section>
      ) : null}

      {enabledOperations.length ? (
        <section className={styles.section} aria-label="Enabled operations modules">
          <div className={styles.heading}><span>Enabled modules</span><small>{enabledOperations.length}</small></div>
          <div className={styles.links}>
            {enabledOperations.map((workspace) => (
              <WorkspaceLink key={workspace.href} href={workspace.href} code={workspace.code} label={workspace.label} meta={`Phase ${workspace.phase}`} pathname={pathname} />
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
