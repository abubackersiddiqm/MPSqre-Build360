"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

type ResetResponse = { message?: string; development_reset_url?: string };

export function ForgotPasswordForm() {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [developmentUrl, setDevelopmentUrl] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    setDevelopmentUrl("");
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/auth/password-reset/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: form.get("email") }),
    }).catch(() => null);
    setBusy(false);
    if (!response?.ok) {
      const payload = (await response?.json().catch(() => null)) as ResetResponse | null;
      setError(payload?.message || "Password reset could not be requested.");
      return;
    }
    const payload = (await response.json()) as ResetResponse;
    setMessage(payload.message || "If the account is eligible, password reset instructions have been sent.");
    setDevelopmentUrl(payload.development_reset_url || "");
  }

  return (
    <form className="mt-7 space-y-5" onSubmit={submit}>
      <div>
        <label className="block text-sm font-medium" htmlFor="reset-email">Email address</label>
        <input autoComplete="email" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-3" id="reset-email" name="email" required type="email" />
      </div>
      {message ? <p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">{message}</p> : null}
      {developmentUrl ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          <p className="font-semibold">Secure reset link</p>
          <a className="mt-2 block break-all font-medium underline" href={developmentUrl}>{developmentUrl}</a>
        </div>
      ) : null}
      {error ? <p className="text-sm text-red-700" role="alert">{error}</p> : null}
      <button className="w-full rounded-lg bg-emerald-950 px-4 py-3 font-semibold text-white disabled:opacity-60" disabled={busy} type="submit">
        {busy ? "Preparing reset…" : "Send reset instructions"}
      </button>
      <p className="text-center text-sm"><Link className="font-semibold text-emerald-900" href="/sign-in">Back to sign in</Link></p>
    </form>
  );
}
