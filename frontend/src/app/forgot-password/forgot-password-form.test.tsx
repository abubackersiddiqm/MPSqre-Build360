import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ForgotPasswordForm } from "./forgot-password-form";

describe("ForgotPasswordForm", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows the local one-time reset link without disclosing account existence in the message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        message: "If an active Build360 account exists for this email, password reset instructions are available.",
        development_reset_url: "http://localhost:3000/reset-password?uid=u&token=t",
      }),
    }));
    render(<ForgotPasswordForm />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "admin@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset instructions" }));
    await waitFor(() => expect(screen.getByText(/If an active Build360 account exists/)).toBeTruthy());
    expect(screen.getByRole("link", { name: /localhost:3000\/reset-password/ }).getAttribute("href")).toContain("reset-password");
  });
});
