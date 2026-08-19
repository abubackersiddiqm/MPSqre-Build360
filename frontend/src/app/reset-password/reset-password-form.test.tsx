import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ResetPasswordForm } from "./reset-password-form";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("uid=user&token=token"),
}));

describe("ResetPasswordForm", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("submits a matching new password and directs the user back to sign in", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ message: "Password updated." }) }));
    render(<ResetPasswordForm />);
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "New-password-42!" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "New-password-42!" } });
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));
    await waitFor(() => expect(screen.getByText(/Existing sessions were revoked/)).toBeTruthy());
    expect(screen.getByRole("link", { name: "Continue to sign in" }).getAttribute("href")).toBe("/sign-in");
  });
});
