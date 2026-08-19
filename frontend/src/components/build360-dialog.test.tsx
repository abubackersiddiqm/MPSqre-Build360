import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Build360Dialog, Build360Drawer } from "./build360-dialog";

describe("Build360Dialog", () => {
  it("renders an accessible modal and closes with Escape", () => {
    const onClose = vi.fn();
    render(
      <Build360Dialog onClose={onClose} open title="Record interaction outcome">
        <button type="button">Focusable action</button>
      </Build360Dialog>,
    );

    const dialog = screen.getByRole("dialog", { name: "Record interaction outcome" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("Build360Drawer", () => {
  it("keeps Relationship 360 as an accessible right-side workspace and closes with Escape", () => {
    const onClose = vi.fn();
    render(
      <Build360Drawer
        headerActions={<button type="button">Next →</button>}
        onClose={onClose}
        open
        title="Ravi Kumar"
      >
        <p>Complete relationship timeline</p>
      </Build360Drawer>,
    );

    const drawer = screen.getByRole("dialog", { name: "Ravi Kumar" });
    expect(drawer.getAttribute("aria-modal")).toBe("true");
    expect(screen.getByText("Complete relationship timeline")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Next →" })).not.toBeNull();
    fireEvent.keyDown(drawer, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
