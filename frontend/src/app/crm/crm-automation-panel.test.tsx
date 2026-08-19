import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CrmAutomationPanel } from "./crm-automation-panel";

const jsonResponse = (value: unknown) => Promise.resolve({ ok: true, json: async () => value }) as Promise<Response>;

describe("CrmAutomationPanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("executions")) return jsonResponse({ items: [] });
      return jsonResponse({
        items: [],
        triggers: [{ code: "lead.created", label: "Lead created" }],
        action_types: [{ code: "create_task", label: "Create task" }],
      });
    }));
  });

  it("shows the universal automation studio and managed rule builder", async () => {
    render(<CrmAutomationPanel canManage />);
    expect(await screen.findByText("Automation studio")).not.toBeNull();
    expect(screen.getByText("Create automation")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Save automation" })).not.toBeNull();
  });

  it("hides the rule builder for read-only users", async () => {
    render(<CrmAutomationPanel canManage={false} />);
    expect(await screen.findByText("Automation studio")).not.toBeNull();
    expect(screen.queryByText("Create automation")).toBeNull();
  });
});
