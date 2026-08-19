import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FinanceWorkspace } from "./workspace";

describe("FinanceWorkspace", () => {
  it("renders the Phase 8 commercial spine", () => {
    render(<FinanceWorkspace company={{public_id:"1",code:"MPSQRE",display_name:"MPSqre",currency:"INR",timezone:"Asia/Kolkata"}} permissions={["finance.dashboard.read"]} initialSummary={null} initialPeriods={[]} initialBudgets={[]} initialVariations={[]} initialInvoices={[]} initialPayments={[]} initialAdjustments={[]} initialLedger={[]} projects={[]} />);
    expect(screen.getByText("Finance and commercial controls")).toBeTruthy();
    expect(screen.getByText("Phase 8 active")).toBeTruthy();
  });
});
