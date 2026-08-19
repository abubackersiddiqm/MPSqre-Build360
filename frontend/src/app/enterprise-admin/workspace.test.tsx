import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EnterpriseAdminWorkspace } from "./workspace";

describe("EnterpriseAdminWorkspace", () => {
  it("shows governed readiness evidence", () => {
    render(
      <EnterpriseAdminWorkspace
        company={{
          public_id: "company-1",
          code: "MPSQRE",
          display_name: "MPSqre Technologies",
          timezone: "Asia/Kolkata",
          currency: "INR",
        }}
        permissions={["adminops.dashboard.read"]}
        initialSummary={{
          active_environments: 2,
          pending_releases: 1,
          failed_checks: 0,
          active_slos: 4,
          open_incidents: 0,
          enabled_flags: 2,
          planned_maintenance: 0,
        }}
        initialEnvironments={[]}
        initialReleases={[]}
        initialObjectives={[]}
        initialHealth={[]}
        initialIncidents={[]}
        initialRunbooks={[]}
        initialFlags={[]}
        initialMaintenance={[]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Production readiness and reliability" })).toBeTruthy();
    expect(screen.getByText("Phase 12 active")).toBeTruthy();
    expect(screen.getByText("Active environments").parentElement?.textContent).toContain("2");
  });
});
