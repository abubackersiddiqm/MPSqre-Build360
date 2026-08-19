import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CrmWorkspace } from "./crm-workspace";

const baseProps = {
  activities: [],
  company: {
    public_id: "company-1",
    code: "MPSQRE",
    display_name: "MPSqre Technologies",
    currency: "INR",
    timezone: "Asia/Kolkata",
  },
  configuration: {
    profile: { public_id: "profile-1", industry_code: "general", terminology: { customer: "Customer", contact: "Contact", lead: "Lead", opportunity: "Opportunity", pipeline: "Pipeline", quote: "Quote" }, settings: {}, version: 1 },
    industry_packs: [], pipelines: [], stages: [], custom_fields: [], lead_sources: [],
  },
  contacts: [], customers: [], leads: [], opportunities: [], stages: [],
  activityDashboard: { generated_at: "", today: 0, overdue: 0, upcoming_7d: 0, followups: 0, recent_activity_24h: 0, new_leads_24h: 0, unassigned_leads: 0, by_type: [] },
  summary: { customers: 3, contacts: 4, leads: 5, opportunities: 2, overdue_followups: 1, pipeline_total: "1000000", weighted_pipeline: "450000", currency: "INR", lead_stages: [], opportunity_stages: [] },
  myWork: {
    generated_at: "",
    counts: { overdue: 3, today: 5, tomorrow: 2, this_week: 8, callback_requested: 1, no_next_action: 4, new_uncontacted: 6 },
    queue: [],
  },
};

describe("CrmWorkspace relationship-first UX", () => {
  it("opens on My Work and makes the next-action operating model obvious", () => {
    render(
      <CrmWorkspace
        {...baseProps}
        permissions={["crm.dashboard.read", "crm.lead.manage", "crm.contact.read", "crm.customer.read", "crm.opportunity.read", "crm.activity.read"]}
        features={{ "crm.core": true, "crm.analytics": true, "crm.whatsapp": true, "crm.email": true, "crm.file_attachments": true }}
      />,
    );

    expect(screen.getByText("Customer relationships & revenue")).toBeTruthy();
    expect(screen.getByRole("button", { name: "My Work" })).not.toBeNull();
    expect(screen.getByRole("button", { name: "People" })).not.toBeNull();
    expect(screen.getByText("What needs your attention now?")).toBeTruthy();
    expect(screen.getByText("No next action")).toBeTruthy();
    expect(screen.getByText("New Lead")).toBeTruthy();
  });

  it("keeps setup and automation governed by explicit permissions", () => {
    render(
      <CrmWorkspace
        {...baseProps}
        permissions={["crm.dashboard.read", "crm.stage.read", "crm.contact.read", "crm.activity.read"]}
        features={{ "crm.core": true, "crm.automation": true }}
      />,
    );
    expect(screen.queryByRole("button", { name: "CRM setup" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Automations" })).toBeNull();
    expect(screen.getByRole("button", { name: "People" })).not.toBeNull();
  });

  it("shows CRM setup only to company administrators with explicit CRM configuration access", () => {
    const { unmount } = render(
      <CrmWorkspace
        {...baseProps}
        permissions={[
          "crm.dashboard.read",
          "crm.configuration.read",
          "crm.automation.read",
          "crm.contact.read",
          "crm.activity.read",
        ]}
        features={{ "crm.core": true, "crm.automation": true }}
      />,
    );
    expect(screen.queryByRole("button", { name: "CRM setup" })).toBeNull();
    expect(screen.getByRole("button", { name: "Automations" })).not.toBeNull();
    unmount();

    render(
      <CrmWorkspace
        {...baseProps}
        permissions={[
          "crm.dashboard.read",
          "crm.configuration.read",
          "crm.configuration.manage",
          "crm.automation.read",
          "crm.contact.read",
          "crm.activity.read",
          "access.user.manage",
        ]}
        features={{ "crm.core": true, "crm.automation": true }}
      />,
    );
    expect(screen.getByRole("button", { name: "CRM setup" })).not.toBeNull();
    expect(screen.getByRole("button", { name: "Automations" })).not.toBeNull();
  });
  it("creates leads through a person-first mobile-safe form with primary and alternate phone", () => {
    render(
      <CrmWorkspace
        {...baseProps}
        permissions={["crm.dashboard.read", "crm.lead.manage", "crm.contact.read"]}
        features={{ "crm.core": true }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "New Lead" }));
    expect(screen.getByText("Person details")).not.toBeNull();
    expect((screen.getByLabelText(/Primary phone/) as HTMLInputElement).required).toBe(true);
    expect((screen.getByLabelText(/Alternate phone/) as HTMLInputElement).required).toBe(false);
    expect(screen.getByRole("button", { name: /Save person \+ create lead/i })).not.toBeNull();
  });

});
