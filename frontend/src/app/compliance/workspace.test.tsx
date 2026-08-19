import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ComplianceWorkspace, type CompliancePortfolio } from "./workspace";

const data: CompliancePortfolio = {
  current_membership_public_id: "00000000-0000-0000-0000-000000000001",
  summary: {
    published_frameworks: 3,
    latest_assessment_score: null,
    open_risks: 1,
    high_risks: 0,
    active_exceptions: 0,
    pending_access_reviews: 0,
  },
  frameworks: [
    {
      public_id: "00000000-0000-0000-0000-000000000002",
      code: "BUILD360_SECURITY_BASELINE",
      name: "Build360 Security Baseline",
      framework_type: "internal",
      jurisdiction: "Global",
      version_label: "2026.1",
      status: "published",
      control_count: 1,
      controls: [
        {
          public_id: "00000000-0000-0000-0000-000000000003",
          code: "IAM-01",
          title: "Tenant-scoped access",
          domain: "access",
          severity: "critical",
          status: "active",
          version: 1,
        },
      ],
    },
  ],
  assessments: [],
  risks: [],
  exceptions: [],
  access_reviews: [],
};

describe("ComplianceWorkspace", () => {
  it("shows evidence-backed compliance posture", () => {
    render(<ComplianceWorkspace initialData={data} />);
    expect(screen.getByText("Security posture, risk and assurance")).toBeTruthy();
    expect(screen.getByText("Phase 17 active")).toBeTruthy();
    expect(screen.getByText("Build360 Security Baseline")).toBeTruthy();
    expect(screen.getByText("IAM-01")).toBeTruthy();
  });
});
