import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { IntegrationWorkspace } from "./workspace";

describe("IntegrationWorkspace", () => {
  it("shows the governed Phase 14 regional and connector controls", () => {
    render(
      <IntegrationWorkspace
        company={{ public_id: "company-1", code: "MPSQRE", display_name: "MPSqre Technologies", locale: "en-IN", timezone: "Asia/Kolkata", currency: "INR" }}
        permissions={["integration.dashboard.read", "integration.localization.read"]}
        features={{ "platform.api_access": true }}
        initialSummary={{ published_localization_packs: 1, active_connectors: 1, active_api_clients: 0, active_webhooks: 0, failed_deliveries: 0, open_sync_runs: 0 }}
        initialPacks={[{ public_id: "pack-1", code: "INDIA_EN", version: 1, name: "India English", country_code: "IN", locale: "en-IN", currency: "INR", timezone: "Asia/Kolkata", unit_system_code: "metric", date_format: "DD/MM/YYYY", time_format: "24h", status: "PUBLISHED", is_default: true, checksum_sha256: "a".repeat(64) }]}
        initialRates={[]}
        initialConnectors={[]}
        initialClients={[]}
        initialWebhooks={[]}
        initialMappings={[]}
        initialSyncRuns={[]}
        initialProviders={[]}
      />,
    );
    expect(screen.getByText("Regional rollout and ecosystem connectivity")).toBeTruthy();
    expect(screen.getByText("Phase 14 active")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Regions & FX" }));

    expect(screen.getByText("India English")).toBeTruthy();
  });
});
