import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ControlPlaneWorkspace } from "./workspace";

describe("ControlPlaneWorkspace", () => {
  it("renders tenant and subscription governance", () => {
    render(
      <ControlPlaneWorkspace
        operator={{
          is_operator: true,
          user: { public_id: "user-1", email: "admin@example.test", display_name: "Platform Admin" },
          roles: [{ public_id: "role-1", code: "PLATFORM_ADMIN", name: "Platform administrator" }],
          permissions: ["controlplane.dashboard.read", "controlplane.tenant.read"],
        }}
        initialSummary={{
          total_tenants: 1,
          active_tenants: 1,
          suspended_tenants: 0,
          active_subscriptions: 1,
          quota_breaches: 0,
          open_support_requests: 0,
        }}
        initialTenants={[
          {
            public_id: "tenant-1",
            company: {
              public_id: "company-1",
              code: "MPSQRE",
              legal_name: "MPSqre Technologies Private Limited",
              display_name: "MPSqre Technologies",
              locale: "en-IN",
              timezone: "Asia/Kolkata",
              currency: "INR",
              is_active: true,
            },
            lifecycle_status: "pilot",
            onboarding_status: "live",
            segment_code: "construction",
            deployment_region: "local",
            data_residency: "local-development",
            pilot_started_at: null,
            activated_at: null,
            grace_until: null,
            suspended_at: null,
            closed_at: null,
            lifecycle_reason: "",
            subscription: null,
            latest_usage: null,
            version: 1,
          },
        ]}
        initialPlans={[]}
        initialSubscriptions={[]}
        initialUsage={[]}
        initialSupportRequests={[]}
      />,
    );
    expect(screen.getByText("Tenant lifecycle and subscription operations")).toBeTruthy();
    expect(screen.getByText("MPSqre Technologies")).toBeTruthy();
    expect(screen.getByText("Phase 13 active")).toBeTruthy();
  });
});
