import { describe, expect, it } from "vitest";

import {
  normalizeRequestHost,
  shouldResolveTenantDomainBrand,
} from "./domain-host";

describe("domain host resolution guard", () => {
  it("normalizes forwarded hosts without trusting ports or later proxy values", () => {
    expect(normalizeRequestHost("Customer.Example.com:443, proxy.internal")).toBe(
      "customer.example.com",
    );
    expect(normalizeRequestHost("[::1]:3000")).toBe("::1");
  });

  it("does not query tenant-domain resolution for local development", () => {
    expect(shouldResolveTenantDomainBrand("localhost:3000", {})).toBe(false);
    expect(shouldResolveTenantDomainBrand("127.0.0.1:3000", {})).toBe(false);
    expect(shouldResolveTenantDomainBrand("[::1]:3000", {})).toBe(false);
  });

  it("does not query the resolver for the canonical Build360 frontend", () => {
    expect(
      shouldResolveTenantDomainBrand("mpsqre-build360.vercel.app", {
        build360PublicWebUrl: "https://mpsqre-build360.vercel.app",
      }),
    ).toBe(false);
  });

  it("does not query Vercel deployment host aliases", () => {
    expect(
      shouldResolveTenantDomainBrand("build360-git-main-example.vercel.app", {
        vercelUrl: "build360-git-main-example.vercel.app",
      }),
    ).toBe(false);
    expect(
      shouldResolveTenantDomainBrand("build360-production.vercel.app", {
        vercelProjectProductionUrl: "build360-production.vercel.app",
      }),
    ).toBe(false);
  });

  it("continues resolving real customer custom domains", () => {
    expect(
      shouldResolveTenantDomainBrand("erp.customer-builders.com", {
        build360PublicWebUrl: "https://mpsqre-build360.vercel.app",
        vercelUrl: "build360-git-main-example.vercel.app",
      }),
    ).toBe(true);
  });

  it("uses exact host matching and does not suppress lookalike domains", () => {
    expect(
      shouldResolveTenantDomainBrand("mpsqre-build360.vercel.app.example.com", {
        build360PublicWebUrl: "https://mpsqre-build360.vercel.app",
      }),
    ).toBe(true);
  });
});
