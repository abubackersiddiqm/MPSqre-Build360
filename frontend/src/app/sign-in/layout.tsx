import type { ReactNode } from "react";

import { DemoLoginCredentials } from "@/components/demo-login-credentials";

export const dynamic = "force-dynamic";

function isDemoEnvironment() {
  const value = (
    process.env.BUILD360_ENVIRONMENT ||
    process.env.APP_ENV ||
    "development"
  ).trim().toLowerCase();
  return value === "demo";
}

export default function TenantSignInLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <>
      {children}
      {isDemoEnvironment() ? (
        <DemoLoginCredentials
          credentials={[
            {
              label: "Company Admin",
              email: "demo.admin@mpsqre.example",
              password: "Build360Demo@2026",
              note: "Tenant administrator across 3 demo companies. Choose CRM Only, Construction Core or Full Build360 after sign-in. No Super Admin privilege.",
            },
            {
              label: "Company User",
              email: "demo.user@mpsqre.example",
              password: "Build360User@2026",
              note: "Normal employee across the same 3 companies. Rights change by purchased package; tenant administration stays hidden.",
            },
          ]}
          title="Build360 Demo tenant logins · 3 companies"
        />
      ) : null}
    </>
  );
}
