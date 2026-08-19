import { describe, expect, it } from "vitest";

import { joinBackendUrl, resolveBackendBaseUrl } from "./backend-url";

describe("backend URL resolution", () => {
  it("uses the explicit internal API URL and removes trailing slashes", () => {
    expect(
      resolveBackendBaseUrl(" http://api:8000/api/v1/ ", "production"),
    ).toBe("http://api:8000/api/v1");
  });

  it("maps the Docker-only api hostname to localhost for host development", () => {
    expect(resolveBackendBaseUrl("http://api:8000/api/v1", "development")).toBe(
      "http://127.0.0.1:8000/api/v1",
    );
  });

  it("uses the host-local Django API when no local override exists", () => {
    expect(resolveBackendBaseUrl(undefined, "development")).toBe(
      "http://127.0.0.1:8000/api/v1",
    );
  });

  it("fails closed in production when the internal API URL is absent", () => {
    expect(() => resolveBackendBaseUrl(undefined, "production")).toThrow(
      "INTERNAL_API_BASE_URL is not configured",
    );
  });

  it("joins paths without duplicate separators", () => {
    expect(joinBackendUrl("http://127.0.0.1:8000/api/v1/", "/auth/token")).toBe(
      "http://127.0.0.1:8000/api/v1/auth/token",
    );
  });
});
