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

export default function SuperAdminSignInLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <>
      {children}
      {isDemoEnvironment() ? (
        <DemoLoginCredentials
          credentials={[
            {
              label: "Super Admin",
              email: "demo.superadmin@mpsqre.example",
              password: "Build360SuperAdmin@2026",
              note: "Platform Operator only. This identity is separate from tenant Company Admin.",
            },
          ]}
          title="Build360 Demo Super Admin login"
        />
      ) : null}
    </>
  );
}
