import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiRequest", () => {
  it("returns typed JSON for a successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(apiRequest<{ status: string }>("/health/live")).resolves.toEqual({
      status: "ok",
    });
  });

  it("normalizes API error envelopes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "API-403-PERMISSION",
            message: "Permission denied.",
            request_id: "request-1",
          }),
          { status: 403, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(apiRequest("/restricted")).rejects.toEqual(
      new ApiError(403, "API-403-PERMISSION", "Permission denied.", "request-1"),
    );
  });
});

