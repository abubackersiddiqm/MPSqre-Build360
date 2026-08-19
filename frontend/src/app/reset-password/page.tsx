import type { Metadata } from "next";
import { Suspense } from "react";

import { ResetPasswordForm } from "./reset-password-form";

export const metadata: Metadata = { title: "Reset password · MPSqre Build360" };

export default function ResetPasswordPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-5 py-10">
      <section className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-7 shadow-xl">
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-emerald-900">MPSqre Build360</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">Reset password</h1>
        <p className="mt-2 leading-6 text-slate-500">Choose a new password. Completing the reset revokes existing sessions.</p>
        <Suspense fallback={<p className="mt-6 text-sm text-slate-500">Loading reset link…</p>}><ResetPasswordForm /></Suspense>
      </section>
    </main>
  );
}
