"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function PlatformSignInForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/platform-auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.get("email"),
        password: form.get("password"),
        device_id: crypto.randomUUID(),
        device_name: `Super Admin · ${navigator.userAgent.slice(0, 160)}`,
      }),
    }).catch(() => null);
    setSubmitting(false);
    if (!response?.ok) {
      const body = (await response?.json().catch(() => null)) as { message?: string } | null;
      setError(body?.message || "Super Admin sign in could not be completed.");
      return;
    }
    router.replace("/super-admin");
    router.refresh();
  }

  return (
    <form className="mt-7 space-y-5" onSubmit={submit}>
      <div>
        <label className="block text-sm font-medium" htmlFor="platform-email">Email address</label>
        <input autoComplete="username" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-3" id="platform-email" name="email" required type="email" />
      </div>
      <div>
        <label className="block text-sm font-medium" htmlFor="platform-password">Password</label>
        <input autoComplete="current-password" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-3" id="platform-password" name="password" required type="password" />
      </div>
      {error ? <p className="text-sm text-red-700" role="alert">{error}</p> : null}
      <button className="w-full rounded-lg bg-emerald-950 px-4 py-3 font-semibold text-white disabled:opacity-60" disabled={submitting} type="submit">
        {submitting ? "Signing in…" : "Sign in to Super Admin"}
      </button>
    </form>
  );
}
