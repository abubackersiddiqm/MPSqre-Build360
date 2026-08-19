import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlatformSummary } from "./platform-summary";

describe("PlatformSummary", () => {
  it("shows governed controls without exposing a protected payload", () => {
    render(
      <PlatformSummary
        approvals={[]}
        company={{
          public_id: "company-1",
          code: "MPS",
          display_name: "MPSqre Construction",
          locale: "en-IN",
          timezone: "Asia/Kolkata",
          currency: "INR",
        }}
        configurations={[
          {
            public_id: "configuration-1",
            definition_code: "provider.credentials",
            name: "Provider credentials",
            version: 2,
            status: "PUBLISHED",
            is_secret: true,
          },
        ]}
        entitlements={{
          subscription_status: "ACTIVE",
          plan_code: "foundation",
          plan_version: 1,
          entitlements: { "platform.phase3": true },
          limits: {},
        }}
        features={{}}
        permissions={["configuration.read", "subscription.read"]}
        platformOperator={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "MPSqre Construction" })).toBeTruthy();
    expect(screen.getByText("Protected")).toBeTruthy();
    expect(screen.getByText("foundation v1")).toBeTruthy();
    expect(screen.getByText("PHASE 45 INSURANCE, BONDS, GUARANTEES & RISK TRANSFER OPERATIONS ACTIVE")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Workspace launcher" })).toBeTruthy();
  });
});
