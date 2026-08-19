import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Project360Workspace } from "./workspace";

const company = {
  public_id: "company-1",
  code: "MPSQRE",
  display_name: "MPSqre Technologies",
  currency: "INR",
  timezone: "Asia/Kolkata",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Project360Workspace direct project creation", () => {
  it("lets an authorized user create the first project and selects it", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/projects/items" && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            public_id: "project-1",
            code: "PRJ-001",
            name: "Direct Project",
            stage: { code: "planning", name: "Planning", outcome: "open" },
            approved_budget: "250000.0000",
            currency: "INR",
            planned_start_date: null,
            planned_end_date: null,
            location: {},
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url === "/api/project360/projects/project-1/experience") {
        return new Response(
          JSON.stringify({ configured: false, message: "Lifecycle setup is pending." }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <Project360Workspace
        company={company}
        initialProjects={[]}
        permissions={["project.dashboard.read", "project.project.read", "project.project.manage"]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Create first project" }));
    fireEvent.change(screen.getByLabelText("Project code"), { target: { value: "PRJ-001" } });
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "Direct Project" } });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/projects/items",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText(/PRJ-001 · Direct Project created/)).not.toBeNull();
    expect((screen.getByRole("combobox", { name: "Project" }) as HTMLSelectElement).value).toBe("project-1");
  });

  it("does not expose direct project creation without project manage permission", () => {
    render(
      <Project360Workspace
        company={company}
        initialProjects={[]}
        permissions={["project.dashboard.read", "project.project.read"]}
      />,
    );

    expect(screen.queryByRole("button", { name: /New project/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Create first project" })).toBeNull();
    expect(screen.getByRole("link", { name: "Open CRM" })).not.toBeNull();
  });
});
