import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Lead } from "./crm-workspace";
import { LeadLogbookPanel } from "./lead-logbook-panel";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const lead: Lead = {
  public_id: "lead-1",
  title: "Log book regression lead",
  description: "",
  source_code: "website",
  pipeline_public_id: null,
  pipeline_name: "",
  custom_fields: {},
  stage: {
    public_id: "stage-1",
    entity_type: "lead",
    pipeline_public_id: null,
    pipeline_code: "default",
    pipeline_name: "Default",
    code: "qualified",
    name: "Qualified",
    outcome: "open",
    sort_order: 1,
    probability_percent: 50,
    allowed_next_codes: [],
    is_initial: false,
    allows_conversion: false,
  },
  available_transitions: [],
  customer: null,
  primary_contact: null,
  owner_membership_public_id: "membership-1",
  owner_display_name: "Owner",
  activity_count: 0,
  last_activity_at: null,
  next_activity_at: null,
  estimated_value: null,
  currency: "INR",
  next_follow_up_at: null,
  version: 1,
  created_at: "2026-08-13T10:00:00Z",
  converted_at: null,
};

const initialTimeline = {
  lead: {
    public_id: lead.public_id,
    title: lead.title,
    source_code: lead.source_code,
    stage: { code: "qualified", name: "Qualified", outcome: "open" },
  },
  items: [],
  count: 0,
};

const updatedTimeline = {
  ...initialTimeline,
  items: [
    {
      kind: "activity",
      public_id: "activity-1",
      occurred_at: "2026-08-13T10:05:00Z",
      activity_type: "note",
      status: "completed",
      priority: "normal",
      subject: "Customer confirmed next step",
      description: "Start next week",
      scheduled_for: null,
      follow_up_at: null,
      created_by_public_id: "user-1",
      created_by_name: "CRM User",
      attachments: [],
    },
  ],
  count: 1,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LeadLogbookPanel", () => {
  it("keeps a stable form reference across async save and refreshes the timeline", async () => {
    let timelineReads = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes(`/api/crm/leads/${lead.public_id}/timeline`)) {
        timelineReads += 1;
        return jsonResponse(timelineReads === 1 ? initialTimeline : updatedTimeline);
      }
      if (url === "/api/crm/activities" && init?.method === "POST") {
        return jsonResponse({ public_id: "activity-1" }, 201);
      }
      throw new Error(`Unexpected request: ${init?.method || "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const onChanged = vi.fn().mockResolvedValue(undefined);
    render(
      <LeadLogbookPanel
        lead={lead}
        permissions={["crm.activity.manage", "crm.activity.read"]}
        features={{ "crm.file_attachments": true, "crm.whatsapp": true, "crm.email": true }}
        onClose={() => undefined}
        onChanged={onChanged}
      />,
    );

    await screen.findByText("0 timeline entries");
    expect(screen.getByRole("dialog", { name: lead.title })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add interaction" }));
    const subject = screen.getByPlaceholderText(/Called customer/);
    fireEvent.change(subject, { target: { value: "Customer confirmed next step" } });
    fireEvent.change(screen.getByPlaceholderText(/What happened/), { target: { value: "Start next week" } });
    fireEvent.click(screen.getByRole("button", { name: "Save interaction" }));

    await screen.findByText("Log entry saved.");
    await screen.findByText("1 timeline entries");
    await screen.findByText("Customer confirmed next step");
    expect(screen.queryByText(/Cannot read properties of null/i)).toBeNull();
    expect((subject as HTMLInputElement).value).toBe("");
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  });
});
