import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CrmContactCenterPanel } from "./crm-contact-center-panel";

const contact = {
  public_id: "contact-1",
  customer_public_id: null,
  display_name: "Asha Kumar",
  job_title: "Purchase Manager",
  email_masked: "a***@example.com",
  phone_masked: "******3210",
  consent_status: "granted",
  preferred_channel_code: "phone",
  source_code: "website",
  tags: ["priority"],
  communication_actions: { email: true, phone: true },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CrmContactCenterPanel", () => {
  it("renders universal contact actions and loads contact history", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ contact, items: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CrmContactCenterPanel
        contacts={[contact]}
        features={{ "crm.whatsapp": true, "crm.email": true }}
        permissions={["crm.contact.read", "crm.contact.reveal", "crm.activity.read", "crm.activity.manage"]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Call, WhatsApp, email, outcome, follow-up" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Call now" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "WhatsApp" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Email" })).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/crm/contacts/contact-1/timeline?limit=100", expect.any(Object)));
  });
});
