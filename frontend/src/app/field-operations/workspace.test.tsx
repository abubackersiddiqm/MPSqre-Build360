import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FieldOperationsWorkspace } from "./workspace";

describe("FieldOperationsWorkspace", () => {
  it("renders the Phase 7 field spine", () => {
    render(
      <FieldOperationsWorkspace
        company={{ public_id: "1", code: "MPSQRE", display_name: "MPSqre", currency: "INR", timezone: "Asia/Kolkata" }}
        permissions={["field.dashboard.read"]}
        initialLabourSummary={null}
        initialEquipmentSummary={null}
        initialQualitySummary={null}
        initialSafetySummary={null}
        initialSyncSummary={null}
        initialWorkers={[]}
        initialAssets={[]}
        initialInspections={[]}
        initialIncidents={[]}
        projects={[]}
      />,
    );
    expect(screen.getByText("Labour, equipment, quality and safety")).toBeTruthy();
    expect(screen.getByText("Phase 7 active")).toBeTruthy();
  });
});
