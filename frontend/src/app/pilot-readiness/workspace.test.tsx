import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PilotReadinessWorkspace, type PilotPortfolio } from "./workspace";

const data: PilotPortfolio = {
  program: {
    public_id: "00000000-0000-0000-0000-000000000001",
    cohort_code: "PILOT_TEST",
    name: "Controlled pilot",
    status: "preparing",
    owner: { display_name: "Pilot Owner", email: "owner@example.test" },
    target_start_date: "2026-08-01",
    target_go_live_at: null,
    actual_go_live_at: null,
    version: 1,
  },
  readiness: {
    score_percent: 35,
    ready: false,
    checklist: { completed: 2, total: 10 },
    master_data: { ready: 3, total: 8 },
    training: { completed: 1, total: 7 },
    signoffs: { approved: 0, total: 6 },
    critical_blockers: [],
    warnings: [],
  },
  checklist: [],
  master_data: [],
  training_modules: [],
  training_completions: [],
  latest_assessment: null,
  go_live_plan: null,
  adoption: [],
};

describe("PilotReadinessWorkspace", () => {
  it("shows the governed pilot score and portfolio", () => {
    render(<PilotReadinessWorkspace initialData={data} />);
    expect(screen.getByText("Pilot launch and go-live readiness")).toBeTruthy();
    expect(screen.getByText("35%")).toBeTruthy();
    expect(screen.getByText("Phase 16 active")).toBeTruthy();
  });
});
