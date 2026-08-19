"use client";

import { useState } from "react";

export type DemoCredential = {
  label: string;
  email: string;
  password: string;
  note?: string;
};

function setInputValue(input: HTMLInputElement | null, value: string) {
  if (!input) return;
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

export function DemoLoginCredentials({
  title,
  credentials,
}: Readonly<{
  title: string;
  credentials: DemoCredential[];
}>) {
  const [copied, setCopied] = useState("");

  async function copyCredential(item: DemoCredential) {
    await navigator.clipboard?.writeText(
      `Email: ${item.email}\nPassword: ${item.password}`,
    );
    setCopied(item.label);
    window.setTimeout(() => setCopied(""), 1600);
  }

  function useCredential(item: DemoCredential) {
    const email = document.querySelector<HTMLInputElement>('input[name="email"]');
    const password = document.querySelector<HTMLInputElement>('input[name="password"]');
    setInputValue(email, item.email);
    setInputValue(password, item.password);
    email?.focus();
  }

  return (
    <aside
      aria-label={title}
      className="fixed bottom-4 left-4 right-4 z-[120] max-h-[46vh] overflow-auto rounded-2xl border border-violet-200 bg-white/95 p-4 shadow-2xl backdrop-blur sm:left-auto sm:w-[430px]"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-violet-700">
            Demo access only
          </p>
          <h2 className="mt-1 text-base font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            These fake credentials are rendered only when Build360 runs in the DEMO environment.
          </p>
        </div>
        <span className="rounded-full bg-violet-100 px-2.5 py-1 text-[10px] font-bold text-violet-800">
          v1.0.0
        </span>
      </div>

      <div className="mt-3 space-y-2">
        {credentials.map((item) => (
          <article className="rounded-xl border border-slate-200 bg-slate-50 p-3" key={item.label}>
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-bold uppercase tracking-wide text-slate-700">{item.label}</p>
              <div className="flex gap-1.5">
                <button
                  className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-700"
                  onClick={() => useCredential(item)}
                  type="button"
                >
                  Use
                </button>
                <button
                  className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-700"
                  onClick={() => void copyCredential(item)}
                  type="button"
                >
                  {copied === item.label ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
            <p className="mt-2 break-all font-mono text-xs text-slate-800">{item.email}</p>
            <p className="mt-1 break-all font-mono text-xs text-slate-800">{item.password}</p>
            {item.note ? <p className="mt-1.5 text-[11px] leading-4 text-slate-500">{item.note}</p> : null}
          </article>
        ))}
      </div>
    </aside>
  );
}
