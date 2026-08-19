"use client";

import { KeyboardEvent as ReactKeyboardEvent, ReactNode, useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

type DialogSize = "small" | "medium" | "large" | "workspace";

type Build360DialogProps = {
  open: boolean;
  title: string;
  kicker?: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  closeLabel?: string;
  size?: DialogSize;
  preventBackdropClose?: boolean;
};

const SIZE_CLASSES: Record<DialogSize, string> = {
  small: "max-w-lg",
  medium: "max-w-3xl",
  large: "max-w-5xl",
  workspace: "max-w-[1480px]",
};

const FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function Build360Dialog({
  open,
  title,
  kicker,
  description,
  children,
  footer,
  onClose,
  closeLabel = "Close",
  size = "medium",
  preventBackdropClose = false,
}: Readonly<Build360DialogProps>) {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousActiveElementRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusTimer = window.setTimeout(() => {
      const panel = panelRef.current;
      if (!panel) return;
      const firstFocusable = panel.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      (firstFocusable ?? panel).focus();
    }, 0);

    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = previousOverflow;
      previousActiveElementRef.current?.focus();
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  function handleKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
      (element) => !element.hasAttribute("hidden") && element.getAttribute("aria-hidden") !== "true",
    );
    if (!focusable.length) {
      event.preventDefault();
      panel.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return createPortal(
    <div
      className={`fixed inset-0 z-[120] flex bg-slate-950/45 backdrop-blur-[2px] ${size === "workspace" ? "items-stretch p-0 sm:items-center sm:p-5" : "items-end p-0 sm:items-center sm:p-5"}`}
      data-build360-dialog-overlay="true"
      onMouseDown={(event) => {
        if (preventBackdropClose || event.target !== event.currentTarget) return;
        onClose();
      }}
    >
      <div
        aria-describedby={description ? descriptionId : undefined}
        aria-labelledby={titleId}
        aria-modal="true"
        className={`relative flex w-full flex-col overflow-hidden bg-white shadow-2xl outline-none ${SIZE_CLASSES[size]} ${
          size === "workspace"
            ? "h-[100dvh] rounded-none sm:h-[min(92dvh,980px)] sm:rounded-[30px]"
            : "max-h-[92dvh] rounded-t-[28px] sm:rounded-[28px]"
        }`}
        onKeyDown={handleKeyDown}
        ref={panelRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4 sm:px-6 sm:py-5">
          <div className="min-w-0">
            {kicker ? <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-[var(--brand)]">{kicker}</p> : null}
            <h2 className="mt-1 text-xl font-semibold text-slate-950 sm:text-2xl" id={titleId}>{title}</h2>
            {description ? <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600" id={descriptionId}>{description}</p> : null}
          </div>
          <button
            aria-label={closeLabel}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-slate-200 bg-white text-lg font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/30"
            onClick={onClose}
            type="button"
          >
            ×
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        {footer ? <footer className="shrink-0 border-t border-slate-200 bg-white px-5 py-4 sm:px-6">{footer}</footer> : null}
      </div>
    </div>,
    document.body,
  );
}


type Build360DrawerProps = {
  open: boolean;
  title: string;
  kicker?: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  closeLabel?: string;
  expanded?: boolean;
  headerActions?: ReactNode;
};

export function Build360Drawer({
  open,
  title,
  kicker,
  description,
  children,
  onClose,
  closeLabel = "Close",
  expanded = false,
  headerActions,
}: Readonly<Build360DrawerProps>) {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousActiveElementRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusTimer = window.setTimeout(() => {
      const panel = panelRef.current;
      if (!panel) return;
      const firstFocusable = panel.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      (firstFocusable ?? panel).focus();
    }, 0);
    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = previousOverflow;
      previousActiveElementRef.current?.focus();
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  function handleKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
      (element) => !element.hasAttribute("hidden") && element.getAttribute("aria-hidden") !== "true",
    );
    if (!focusable.length) {
      event.preventDefault();
      panel.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[118] bg-slate-950/20"
      data-build360-drawer-overlay="true"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        aria-describedby={description ? descriptionId : undefined}
        aria-labelledby={titleId}
        aria-modal="true"
        className={`absolute inset-y-0 right-0 flex w-full flex-col overflow-hidden bg-white shadow-2xl outline-none transition-[width] duration-200 ${expanded ? "sm:w-[min(94vw,1180px)] xl:w-[min(88vw,1320px)] 2xl:w-[min(82vw,1480px)]" : "sm:w-[min(86vw,620px)] xl:w-[min(48vw,760px)] 2xl:w-[min(46vw,820px)]"}`}
        onKeyDown={handleKeyDown}
        ref={panelRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 bg-white px-4 py-4 sm:px-5">
          <div className="min-w-0 flex-1">
            {kicker ? <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-[var(--brand)]">{kicker}</p> : null}
            <h2 className="mt-1 truncate text-xl font-semibold text-slate-950 sm:text-2xl" id={titleId}>{title}</h2>
            {description ? <p className="mt-1 line-clamp-2 text-sm leading-5 text-slate-600" id={descriptionId}>{description}</p> : null}
            {headerActions ? <div className="mt-3 flex flex-wrap items-center gap-2">{headerActions}</div> : null}
          </div>
          <button
            aria-label={closeLabel}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-slate-200 bg-white text-lg font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/30"
            onClick={onClose}
            type="button"
          >
            ×
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

type ErrorDialogProps = {
  open: boolean;
  title?: string;
  message: string;
  details?: string[];
  onClose: () => void;
  primaryAction?: { label: string; onClick: () => void };
};

export function Build360ErrorDialog({
  open,
  title = "We could not complete that action",
  message,
  details = [],
  onClose,
  primaryAction,
}: Readonly<ErrorDialogProps>) {
  return (
    <Build360Dialog
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <button className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold" onClick={onClose} type="button">Close</button>
          {primaryAction ? <button className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white" onClick={primaryAction.onClick} type="button">{primaryAction.label}</button> : null}
        </div>
      }
      kicker="Action needs attention"
      onClose={onClose}
      open={open}
      size="small"
      title={title}
    >
      <div className="p-5 sm:p-6">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-900" role="alert">
          {message}
        </div>
        {details.length ? (
          <ul className="mt-4 space-y-2 rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
            {details.map((detail) => <li className="flex gap-2" key={detail}><span aria-hidden="true">•</span><span>{detail}</span></li>)}
          </ul>
        ) : null}
      </div>
    </Build360Dialog>
  );
}

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "default" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
};

export function Build360ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel = "Keep editing",
  tone = "default",
  onConfirm,
  onCancel,
}: Readonly<ConfirmDialogProps>) {
  return (
    <Build360Dialog
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <button className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold" onClick={onCancel} type="button">{cancelLabel}</button>
          <button className={`${tone === "danger" ? "bg-red-700" : "bg-[var(--brand)]"} rounded-xl px-4 py-2.5 text-sm font-semibold text-white`} onClick={onConfirm} type="button">{confirmLabel}</button>
        </div>
      }
      kicker="Please confirm"
      onClose={onCancel}
      open={open}
      size="small"
      title={title}
    >
      <div className="p-5 text-sm leading-6 text-slate-700 sm:p-6">{message}</div>
    </Build360Dialog>
  );
}
