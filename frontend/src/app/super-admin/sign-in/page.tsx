import type { Metadata } from "next";

import { PlatformSignInForm } from "./platform-sign-in-form";

export const metadata: Metadata = {
  title: "Super Admin sign in · MPSqre Build360",
};

export default function SuperAdminSignInPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-5 py-10">
      <section className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-7 shadow-xl">
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-emerald-900">MPSqre Build360</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">Super Admin sign in</h1>
        <p className="mt-2 leading-6 text-slate-500">Platform Operator session. This sign-in is isolated from company-user sessions in the same browser.</p>
        <PlatformSignInForm />
      </section>
    </main>
  );
}
