import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CommunicationWorkspace } from "./workspace";

const company = { public_id: "company", code: "MPSQRE", display_name: "MPSqre Technologies", locale: "en-IN", timezone: "Asia/Kolkata", currency: "INR" };

describe("CommunicationWorkspace", () => {
  it("renders the governed notification inbox", () => {
    render(
      <CommunicationWorkspace
        company={company}
        permissions={["communication.dashboard.read", "notification.read"]}
        initialCommunicationSummary={{ policies: 5, enabled_channels: 1, active_providers: 1, published_templates: 4, queued: 0, sent: 0, delivered: 0, failed: 0, suppressed: 0, inbound_review: 0 }}
        initialNotificationSummary={{ total: 1, unread: 1, critical_unread: 0, preferences: 0, active_rules: 4, delivery_failures: 0, delivery_suppressed: 0 }}
        initialPolicies={[]}
        initialProviders={[]}
        initialTemplates={[]}
        initialRequests={[]}
        initialNotifications={[{ public_id: "notification", event_code: "system.welcome", title: "Welcome", body: "Phase 9 is active.", severity: "success", action_path: "/communications", read_at: null, created_at: "2026-07-31T00:00:00Z", deliveries: [{ channel: "in_app", status: "delivered", failure_code: "", delivered_at: "2026-07-31T00:00:00Z" }] }]}
        initialPreferences={[]}
        initialRules={[]}
      />,
    );
    expect(screen.getByRole("heading", { name: "Communications and notifications" })).toBeTruthy();
    expect(screen.getByText("Welcome")).toBeTruthy();
    expect(screen.getByText("Phase 9 active")).toBeTruthy();
  });
});
