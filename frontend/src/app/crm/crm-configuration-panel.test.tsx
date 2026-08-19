import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CrmConfigurationPanel, type CrmConfiguration } from "./crm-configuration-panel";

const configuration: CrmConfiguration = {
  profile: {
    public_id: "profile-1",
    industry_code: "financial_services",
    terminology: {
      customer: "Customer",
      contact: "Contact",
      lead: "Applicant",
      opportunity: "Application",
      pipeline: "Pipeline",
      quote: "Quote",
    },
    settings: {},
    version: 2,
  },
  industry_packs: [
    { code: "general", name: "General Business", description: "Neutral CRM" },
    { code: "financial_services", name: "Financial Services", description: "Loan and financial CRM" },
  ],
  pipelines: [
    {
      public_id: "pipeline-1",
      entity_type: "lead",
      code: "default-lead",
      name: "Lead Pipeline",
      description: "",
      is_default: true,
      sort_order: 10,
      stage_count: 1,
    },
  ],
  stages: [
    {
      public_id: "stage-1",
      pipeline_public_id: "pipeline-1",
      entity_type: "lead",
      code: "new",
      name: "New",
      outcome: "open",
      sort_order: 10,
      probability_percent: 5,
      allowed_next_codes: [],
      is_initial: true,
      allows_conversion: false,
    },
  ],
  custom_fields: [
    {
      public_id: "field-1",
      entity_type: "lead",
      code: "requested_amount",
      label: "Requested amount",
      field_type: "currency",
      help_text: "",
      is_required: false,
      options: [],
      sort_order: 100,
      source_pack_code: "financial_services",
    },
  ],
  lead_sources: [
    { public_id: "source-1", code: "website", name: "Website", channel_type: "website", sort_order: 10, source_pack_code: "general" },
  ],
};

describe("CrmConfigurationPanel", () => {
  it("renders industry adaptation, governed fields and pipeline stages", () => {
    render(<CrmConfigurationPanel canManage={false} configuration={configuration} onChanged={vi.fn()} />);

    expect(screen.getAllByText("Financial Services").length).toBeGreaterThan(0);
    expect(screen.getByText("Requested amount")).toBeTruthy();
    expect(screen.getByText("Pipeline stages")).toBeTruthy();
    expect(screen.getByText("New · initial")).toBeTruthy();
  });
});
