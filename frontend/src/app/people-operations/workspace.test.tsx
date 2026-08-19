import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PeopleOperationsWorkspace, type PeopleopsPortfolio } from "./workspace";

const data: PeopleopsPortfolio = {
  current_user_public_id: "00000000-0000-0000-0000-000000000001",
  current_membership_public_id: "00000000-0000-0000-0000-000000000002",
  summary: { employees: 1, active_contracts: 1, departments: 4, pending_leave_requests: 0, pending_timesheets: 0, available_leave_days: "36.00", payroll_runs: 1, latest_payroll_status: "draft", latest_payroll_net: "0.00", currency: "INR" },
  employees: [{ public_id: "e", user_public_id: "00000000-0000-0000-0000-000000000003", employee_number: "EMP-1", display_name: "Administrator", email: "admin@example.test", job_title: "Administrator" }],
  departments: [],
  contracts: [],
  leave_policies: [],
  leave_balances: [],
  leave_requests: [],
  timesheets: [],
  payroll_runs: [],
};

describe("PeopleOperationsWorkspace", () => {
  it("shows Phase 20 people operations metrics", () => {
    render(<PeopleOperationsWorkspace initialData={data} />);
    expect(screen.getByText("Phase 20 active")).toBeTruthy();
    expect(screen.getByText("Employees")).toBeTruthy();
    expect(screen.getByText("36.00")).toBeTruthy();
  });
});
