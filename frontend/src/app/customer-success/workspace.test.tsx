import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CustomerSuccessWorkspace, type SuccessopsPortfolio } from "./workspace";

const data: SuccessopsPortfolio = {
  current_user_public_id: "00000000-0000-0000-0000-000000000001",
  summary: { accounts: 1, active_accounts: 1, at_risk_accounts: 0, average_health_score: 72, open_tickets: 0, sla_breaches: 0, outstanding_invoices: 0, overdue_invoices: 0, outstanding_amount: "0.00", currency: "INR", adoption_score: 45, engagement_score: 50 },
  memberships: [],
  accounts: [{ public_id: "a", code: "PRIMARY", display_name: "MPSqre", segment: "pilot", status: "active", health_score: 72, risk_level: "low", renewal_on: null, desired_outcomes: [], risk_summary: "" }],
  invoices: [],
  tickets: [],
  success_plans: [],
  adoption_snapshots: [],
};

describe("CustomerSuccessWorkspace", () => {
  it("shows Phase 19 customer success metrics", () => {
    render(<CustomerSuccessWorkspace initialData={data} />);
    expect(screen.getByText("Phase 19 active")).toBeTruthy();
    expect(screen.getByText("Account health")).toBeTruthy();
    expect(screen.getByText("Account health").parentElement?.textContent).toContain("72");
  });
});
