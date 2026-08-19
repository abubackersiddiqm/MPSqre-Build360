"use client";

import { useEffect } from "react";

type ToastTone = "success" | "info" | "warning";

export function Build360Toast({
  message,
  onDismiss,
  tone = "success",
  durationMs = 4500,
}: Readonly<{
  message: string;
  onDismiss: () => void;
  tone?: ToastTone;
  durationMs?: number;
}>) {
  useEffect(() => {
    if (!message || durationMs <= 0) return;
    const timer = window.setTimeout(onDismiss, durationMs);
    return () => window.clearTimeout(timer);
  }, [durationMs, message, onDismiss]);

  if (!message) return null;
  const toneClass = tone === "warning"
    ? "border-amber-200 bg-amber-50 text-amber-950"
    : tone === "info"
      ? "border-sky-200 bg-sky-50 text-sky-950"
      : "border-emerald-200 bg-emerald-50 text-emerald-950";

  return (
    <div className="pointer-events-none fixed inset-x-3 bottom-4 z-[160] flex justify-center sm:inset-x-auto sm:right-5 sm:justify-end" role="status">
      <div className={`pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-2xl border p-4 shadow-xl ${toneClass}`}>
        <div className="min-w-0 flex-1 text-sm font-medium leading-6">{message}</div>
        <button aria-label="Dismiss notification" className="shrink-0 rounded-lg px-2 py-1 text-sm font-bold opacity-70 hover:opacity-100" onClick={onDismiss} type="button">×</button>
      </div>
    </div>
  );
}
