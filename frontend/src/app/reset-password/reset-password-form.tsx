"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

export function ResetPasswordForm() {
  const params = useSearchParams();
  const uid = params.get("uid") || "";
  const token = params.get("token") || "";
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") || "");
    const confirm = String(form.get("confirm") || "");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    const response = await fetch("/api/auth/password-reset/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid, token, password }),
    }).catch(() => null);
    setBusy(false);
    if (!response?.ok) {
      const payload = (await response?.json().catch(() => null)) as { message?: string } | null;
      setError(payload?.message || "Password could not be updated.");
      return;
    }
    setSuccess(true);
  }

  if (!uid || !token) {
    return <p className="mt-6 rounded-xl bg-red-50 p-3 text-sm text-red-800">This password reset link is incomplete.</p>;
  }
  if (success) {
    return <div className="mt-6"><p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">Password updated. Existing sessions were revoked for security.</p><Link className="mt-4 inline-flex font-semibold text-emerald-900" href="/sign-in">Continue to sign in</Link></div>;
  }
  return (
    <form className="mt-7 space-y-5" onSubmit={submit}>
      <div><label className="block text-sm font-medium" htmlFor="new-password">New password</label><input autoComplete="new-password" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-3" id="new-password" minLength={12} name="password" required type="password" /></div>
      <div><label className="block text-sm font-medium" htmlFor="confirm-password">Confirm password</label><input autoComplete="new-password" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-3" id="confirm-password" minLength={12} name="confirm" required type="password" /></div>
      <p className="text-xs leading-5 text-slate-500">Use at least 12 characters with upper case, lower case and a number.</p>
      {error ? <p className="text-sm text-red-700" role="alert">{error}</p> : null}
      <button className="w-full rounded-lg bg-emerald-950 px-4 py-3 font-semibold text-white disabled:opacity-60" disabled={busy} type="submit">{busy ? "Updating password…" : "Update password"}</button>
    </form>
  );
}
