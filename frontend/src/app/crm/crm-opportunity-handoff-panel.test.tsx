import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CrmOpportunityHandoffPanel } from "./crm-opportunity-handoff-panel";

describe("CrmOpportunityHandoffPanel", () => {
  it("explains the next design and estimation actions without creating another journey", () => {
    render(
      <CrmOpportunityHandoffPanel
        canOpenDesign
        canOpenEstimation
        onClose={vi.fn()}
        result={{
          opportunity_public_id: "opp-1",
          public_id: "project-1",
          code: "PRJ-001",
          name: "Residence",
          created: true,
          mode: "preconstruction",
          message: "Preconstruction workspace created.",
        }}
      />,
    );

    expect(screen.getByText(/PRJ-001/)).not.toBeNull();
    expect(screen.getByRole("link", { name: /Architect \/ Design/ }).getAttribute("href")).toBe("/project360/design?project=project-1");
    expect(screen.getByRole("link", { name: /Estimation & BOQ/ }).getAttribute("href")).toBe("/delivery?tab=estimation&project=project-1");
  });
});
