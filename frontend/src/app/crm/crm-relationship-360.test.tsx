import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AiSalesCopilotPanel, CrmMyWorkPanel } from "./crm-relationship-360";

describe("CRM Relationship 360 daily queue", () => {
  it("shows overdue work first and opens the person instead of another CRM page", () => {
    const onOpenPerson = vi.fn();
    render(
      <CrmMyWorkPanel
        initial={{
          generated_at: "2026-08-17T08:00:00Z",
          counts: { overdue: 1, today: 1, tomorrow: 0, this_week: 2, callback_requested: 1, no_next_action: 2, new_uncontacted: 3 },
          queue: [
            {
              action_at: "2026-08-17T07:00:00Z",
              is_overdue: true,
              is_today: true,
              subject: "Call about revised quotation",
              reason: "Callback requested",
              priority: "high",
              person: { public_id: "person-1", display_name: "Ravi Kumar", phone_masked: "••••3210", email_masked: null },
              company: { public_id: "account-1", display_name: "ABC Industries" },
              lead_public_id: "lead-1",
              activity_public_id: "activity-1",
              activity_type: "call",
            },
          ],
        }}
        onOpenPerson={onOpenPerson}
      />,
    );

    expect(screen.getByText("What needs your attention now?")).not.toBeNull();
    expect(screen.getByText("Ravi Kumar")).not.toBeNull();
    expect(screen.getByText("Call about revised quotation")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Ravi Kumar/ }));
    expect(onOpenPerson).toHaveBeenCalledWith("person-1");
  });

  it("shows next-call prep in English and switches to practical Tanglish", () => {
    const onLanguageChange = vi.fn();
    render(
      <AiSalesCopilotPanel
        busy={false}
        insight={{
          lead_public_id: "lead-1",
          feature_access: { summary: true, recommendation: true },
          exists: true,
          stale: false,
          generated_at: "2026-08-17T08:00:00Z",
          override_active: false,
          advisory_notice: "AI advice only.",
          citations: [{ public_id: "citation-1", rank: 1, source_label: "Lead · Service enquiry", excerpt: "Latest customer history" }],
          effective: {
            summary: "The customer asked for a callback after reviewing the proposal.",
            summary_tanglish: "Customer proposal review pannitu callback kekkaranga.",
            recommended_next_action: {
              action_code: "FOLLOW_UP_NOW",
              label: "Call the customer now",
              reason: "The callback is overdue.",
              suggested_due_at: "2026-08-17T08:00:00Z",
              confidence: "0.95",
            },
            call_preparation: {
              english: {
                objective: "Confirm the decision status.",
                opening_line: "Hi Ravi, I’m following up on the proposal.",
                talking_points: ["Confirm what changed."],
                questions: ["What is blocking the next decision?"],
                closing_line: "Can we agree the next step?",
              },
              tanglish: {
                objective: "Decision status enna nu confirm pannunga.",
                opening_line: "Hi Ravi, proposal pathi follow-up panna call pannuren.",
                talking_points: ["Enna change aachu nu confirm pannunga."],
                questions: ["Next decision-ku main blocker enna?"],
                closing_line: "Next step confirm pannalama?",
              },
              grounded_context: "Customer asked for a callback.",
              safety_note: "Verify commitments.",
            },
            message_drafts: {
              whatsapp: { english: "Hi Ravi, following up.", tanglish: "Hi Ravi, follow-up pannuren." },
              email: { subject: "Follow-up", english: "Hi Ravi", tanglish: "Hi Ravi" },
            },
            attention_signals: [{ code: "CALLBACK", severity: "high", label: "Callback requested", reason: "Recorded outcome." }],
            data_gaps: [],
          },
        }}
        language="english"
        onGenerate={vi.fn()}
        onLanguageChange={onLanguageChange}
      />,
    );

    expect(screen.getByText("What to say on the next call")).not.toBeNull();
    expect(screen.getByText("Hi Ravi, I’m following up on the proposal.")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Tanglish" }));
    expect(onLanguageChange).toHaveBeenCalledWith("tanglish");
  });
});
