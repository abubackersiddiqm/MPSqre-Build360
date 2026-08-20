import { describe, expect, it } from "vitest";

import {
  canAccessWorkspace,
  isProtectedWorkspacePath,
  visibleWorkspaces,
  WORKSPACES,
  workspaceAccessLevel,
  workspaceForPath,
} from "./workspaces";

describe("workspace registry", () => {
  it("shows only capability-authorized workspaces", () => {
    const visible = visibleWorkspaces({
      permissions: ["crm.dashboard.read", "finance.dashboard.read"],
      features: { "crm.core": true, "module.finance": true },
      platformOperator: false,
    });

    expect(visible.map((workspace) => workspace.key)).toEqual([
      "platform",
      "today",
      "search",
      "crm",
      "finance",
    ]);
  });





  it("keeps a CRM-only tenant focused on CRM even when the user has broader permissions", () => {
    const visible = visibleWorkspaces({
      permissions: [
        "crm.dashboard.read",
        "project.dashboard.read",
        "finance.dashboard.read",
        "release.view",
        "cloudops.dashboard.read",
      ],
      features: {
        "crm.core": true,
        "module.delivery": false,
        "module.finance": false,
      },
      platformOperator: false,
    });

    const keys = visible.map((workspace) => workspace.key);
    expect(keys).toContain("crm");
    expect(keys).not.toContain("project360");
    expect(keys).not.toContain("finance");
    expect(keys).not.toContain("release-evidence");
    expect(keys).not.toContain("cloudops");
  });

  it("shows Brand to a Company Administrator only when white-label or custom-domain is purchased", () => {
    const visible = visibleWorkspaces({
      permissions: [
        "crm.dashboard.read",
        "tenant.branding.read",
        "tenant.branding.manage",
        "tenant.domain.read",
        "tenant.domain.manage",
      ],
      features: { "crm.core": true, "tenant.white_label": true, "tenant.custom_domain": false },
      platformOperator: false,
    });
    expect(visible.map((workspace) => workspace.key)).toContain("brand");

    const disabled = visibleWorkspaces({
      permissions: ["tenant.branding.read", "tenant.domain.read"],
      features: { "tenant.white_label": false, "tenant.custom_domain": false },
      platformOperator: false,
    });
    expect(disabled.map((workspace) => workspace.key)).not.toContain("brand");
  });

  it("hides subscription-disabled workspaces even when permissions exist", () => {
    const crm = WORKSPACES.find((workspace) => workspace.key === "crm");
    const brand = WORKSPACES.find((workspace) => workspace.key === "brand");
    expect(crm).toBeDefined();
    expect(brand).toBeDefined();
    expect(canAccessWorkspace(crm!, { permissions: ["crm.dashboard.read"], features: { "crm.core": false }, platformOperator: false })).toBe(false);
    expect(canAccessWorkspace(brand!, { permissions: ["tenant.branding.read", "tenant.domain.read"], features: { "tenant.white_label": false, "tenant.custom_domain": false }, platformOperator: false })).toBe(false);
    expect(canAccessWorkspace(brand!, { permissions: ["tenant.branding.read"], features: { "tenant.white_label": true, "tenant.custom_domain": false }, platformOperator: false })).toBe(true);
  });

  it("exposes the unified approvals workspace only to users who can decide", () => {
    const visible = visibleWorkspaces({
      permissions: ["design.review.decide"],
      platformOperator: false,
    });

    expect(visible.map((workspace) => workspace.key)).toEqual([
      "platform",
      "today",
      "approvals",
    ]);
  });


  it("never leaks platform operations into the tenant workspace list, even for a platform operator", () => {
    const visible = visibleWorkspaces({
      permissions: ["release.view", "cloudops.dashboard.read", "adminops.dashboard.read"],
      features: {},
      platformOperator: true,
    });
    const keys = visible.map((workspace) => workspace.key);
    expect(keys).not.toContain("release-evidence");
    expect(keys).not.toContain("adminops");
    expect(keys).not.toContain("controlplane");
    expect(keys).not.toContain("pilot");
    expect(keys).not.toContain("cloudops");
    expect(keys).not.toContain("success");
  });
  it("requires platform operator context for the SaaS control plane", () => {
    const controlPlane = WORKSPACES.find(
      (workspace) => workspace.key === "controlplane",
    );
    expect(controlPlane).toBeDefined();
    expect(
      canAccessWorkspace(controlPlane!, {
        permissions: [],
        platformOperator: false,
      }),
    ).toBe(false);
    expect(
      canAccessWorkspace(controlPlane!, {
        permissions: [],
        platformOperator: true,
      }),
    ).toBe(true);
  });

  it("classifies managed workspace access consistently", () => {
    const crm = WORKSPACES.find((workspace) => workspace.key === "crm");
    const finance = WORKSPACES.find((workspace) => workspace.key === "finance");
    expect(crm).toBeDefined();
    expect(finance).toBeDefined();

    expect(
      workspaceAccessLevel(crm!, {
        permissions: ["crm.dashboard.read", "crm.contact.read"],
        features: { "crm.core": true },
        platformOperator: false,
      }),
    ).toBe("VIEW");

    expect(
      workspaceAccessLevel(crm!, {
        permissions: ["crm.dashboard.read", "crm.contact.read", "crm.contact.manage"],
        features: { "crm.core": true },
        platformOperator: false,
      }),
    ).toBe("EDIT");

    expect(
      workspaceAccessLevel(crm!, {
        permissions: ["crm.dashboard.read", "crm.contact.read", "crm.lead.convert"],
        features: { "crm.core": true },
        platformOperator: false,
      }),
    ).toBe("FULL");

    expect(
      workspaceAccessLevel(crm!, {
        permissions: ["finance.dashboard.read"],
        features: { "crm.core": true, "module.finance": true },
        platformOperator: false,
      }),
    ).toBe("NONE");

    expect(
      workspaceAccessLevel(crm!, {
        permissions: ["crm.dashboard.read"],
        features: { "crm.core": false },
        platformOperator: false,
      }),
    ).toBe("NONE");

    expect(
      workspaceAccessLevel(finance!, {
        permissions: ["finance.dashboard.read", "finance.invoice.manage"],
        features: { "module.finance": true },
        platformOperator: false,
      }),
    ).toBe("EDIT");
  });

  it("resolves nested routes and protects only operating workspaces", () => {
    expect(workspaceForPath("/field-operations/quality")?.key).toBe("field");
    expect(isProtectedWorkspacePath("/integrations")).toBe(true);
    expect(workspaceForPath("/today")?.key).toBe("today");
    expect(workspaceForPath("/search")?.key).toBe("search");
    expect(workspaceForPath("/release-evidence")?.key).toBe("release-evidence");
    expect(workspaceForPath("/executive")?.key).toBe("executive");
    expect(isProtectedWorkspacePath("/sign-in")).toBe(false);
    expect(isProtectedWorkspacePath("/portal/accept")).toBe(false);
  });
});
