import type { Metadata } from "next";

import { ForgotPasswordForm } from "./forgot-password-form";

export const metadata: Metadata = { title: "Forgot password · MPSqre Build360" };

export default function ForgotPasswordPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-5 py-10">
      <section className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-7 shadow-xl">
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-emerald-900">MPSqre Build360</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">Forgot password</h1>
        <p className="mt-2 leading-6 text-slate-500">Enter your account email. If the account is eligible, we’ll send a secure password reset link to the registered email address. For your security, we never confirm whether an account exists.</p>
        <ForgotPasswordForm />
      </section>
    </main>
  );
}
