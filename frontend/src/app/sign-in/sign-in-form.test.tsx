import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SignInForm } from "./sign-in-form";

const replace = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, refresh }),
}));

describe("SignInForm", () => {
  beforeEach(() => {
    replace.mockReset();
    refresh.mockReset();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("provides accessible credential fields without client token storage", () => {
    render(<SignInForm />);

    expect(screen.getByLabelText("Email address").getAttribute("autocomplete")).toBe(
      "username",
    );
    expect(screen.getByLabelText("Password").getAttribute("autocomplete")).toBe(
      "current-password",
    );
    expect(
      (screen.getByRole("button", { name: "Sign in" }) as HTMLButtonElement).disabled,
    ).toBe(false);
    expect(screen.getByRole("link", { name: "Forgot password?" }).getAttribute("href")).toBe("/forgot-password");
  });

  it("enters the tenant directly when login auto-selects the only company", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ company_selected: true, membership_count: 1 }),
      }),
    );

    render(<SignInForm />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "admin@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });

  it("uses company selection only when more than one company is available", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ company_selected: false, membership_count: 2 }),
      }),
    );

    render(<SignInForm />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "shared@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/select-company"));
  });


});
