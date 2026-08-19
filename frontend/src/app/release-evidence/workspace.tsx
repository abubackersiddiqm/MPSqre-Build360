"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

type EvidenceAttachment = { file_public_id: string; version_public_id?: string; original_name?: string; content_type?: string; sha256?: string; note?: string; attached_at?: string; attached_by_public_id?: string };
type Evidence = Record<string, unknown> & { attachments?: EvidenceAttachment[] };
type Gate = { public_id: string; code: string; name: string; category: string; required: boolean; status: string; notes: string; evidence: Evidence; version: number };
type Scenario = { public_id: string; code: string; title: string; module: string; persona: string; required: boolean; steps: string[]; expected_result: string; execution: null | { public_id: string; status: string; notes: string; defect_reference: string; evidence: Evidence; version: number } };
type Backup = { public_id: string; reference: string; type: string; status: string; restore_tested: boolean; captured_at: string; release_code: string | null; target_code: string | null };
type ReadinessRun = { public_id: string; status: string; checks_total: number; checks_passed: number; checks_failed: number; results: { code: string; passed: boolean; critical: boolean; detail: string }[]; started_at: string; completed_at: string | null; release_code: string | null };
export type ReleaseOverview = {
  company: { public_id: string; name: string; currency: string; timezone: string };
  metrics: { targets: number; release_candidates: number; required_gates_passed: number; required_gates_total: number; uat_passed: number; uat_total: number; available_backups: number; failed_readiness_checks: number };
  current_release: null | { public_id: string; release_code: string; version_label: string; title: string; summary: string; status: string; planned_at: string | null; approved_at: string | null; published_at: string | null; target: null | { public_id: string; code: string; name: string } };
  gates: Gate[];
  scenarios: Scenario[];
  backups: Backup[];
  readiness_runs: ReadinessRun[];
  capabilities?: {
    can_manage: boolean; can_target: boolean; can_gate: boolean; can_uat: boolean; can_backup: boolean;
    can_approve: boolean; can_publish: boolean; can_export: boolean;
  };
};

async function openEvidenceFile(filePublicId: string) {
  const response = await fetch(`/api/files/${filePublicId}/download`, { cache: "no-store" }).catch(() => null);
  if (!response?.ok) return;
  const body = await response.json().catch(() => null) as { download_url?: string } | null;
  if (body?.download_url) window.open(body.download_url, "_blank", "noopener,noreferrer");
}

const statusClass = (status: string) => {
  if (["PASSED", "APPROVED", "PUBLISHED", "AVAILABLE"].includes(status)) return "bg-emerald-50 text-emerald-800 border-emerald-200";
  if (["FAILED", "BLOCKED", "REJECTED"].includes(status)) return "bg-red-50 text-red-800 border-red-200";
  return "bg-amber-50 text-amber-900 border-amber-200";
};

export function ReleaseEvidenceWorkspace({ payload }: Readonly<{ payload: ReleaseOverview }>) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function attachEvidence(kind: "gate" | "uat", publicId: string, version: number) {
    const filePublicId = window.prompt("Paste a FINALIZED + CLEAN governed File public ID");
    if (!filePublicId) return;
    const note = window.prompt("Evidence note (optional)") ?? "";
    const path = kind === "gate"
      ? `gates/${publicId}/evidence-files`
      : `uat/${publicId}/evidence-files`;
    setBusy(true); setMessage("");
    const response = await fetch(`/api/platform/release-readiness/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_public_id: filePublicId.trim(), note, expected_version: version }),
    }).catch(() => null);
    const body = await response?.json().catch(() => ({})) as { message?: string; detail?: string };
    setBusy(false);
    if (!response?.ok) {
      setMessage(body.message ?? body.detail ?? "Evidence attachment failed.");
      return;
    }
    setMessage("Governed evidence attached.");
    router.refresh();
  }
  const gatePercent = payload.metrics.required_gates_total ? Math.round(payload.metrics.required_gates_passed / payload.metrics.required_gates_total * 100) : 0;
  const uatPercent = payload.metrics.uat_total ? Math.round(payload.metrics.uat_passed / payload.metrics.uat_total * 100) : 0;
  const restoreTested = payload.backups.filter((item) => item.restore_tested).length;
  const latestRun = payload.readiness_runs[0] ?? null;
  const blockers = [
    ...payload.gates.filter((item) => item.required && item.status !== "PASSED").map((item) => ({ code: item.code, title: item.name, kind: "GATE" as const, status: item.status, public_id: item.public_id, version: item.version })),
    ...payload.scenarios.filter((item) => item.required && item.execution?.status !== "PASSED").map((item) => ({ code: item.code, title: item.title, kind: "UAT" as const, status: item.execution?.status ?? "NOT_RUN", public_id: item.execution?.public_id ?? "", version: item.execution?.version ?? 0 })),
  ];
  const modules = Array.from(new Set(payload.scenarios.map((item) => item.module))).sort();

  return <main className="min-h-screen bg-[var(--background)] px-4 py-6 sm:px-7 lg:px-10"><div className="mx-auto max-w-[1550px] space-y-6">
    <header className="overflow-hidden rounded-[30px] border border-[var(--border)] bg-white shadow-sm">
      <div className="grid gap-6 p-6 lg:grid-cols-[1.2fr_.8fr] lg:p-8">
        <div><p className="text-xs font-bold uppercase tracking-[.2em] text-[var(--brand)]">Release evidence</p><h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">One view of what is proven — and what is still blocking release.</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)]">This is a read-only visual projection over the governed Release Operations records. It never marks a gate or UAT as passed automatically.</p></div>
        <div className="rounded-[24px] p-5 text-white" style={{background:"linear-gradient(145deg,var(--brand),var(--brand-strong))"}}><p className="text-xs font-bold uppercase tracking-[.16em] text-white/70">Current release</p><p className="mt-2 text-2xl font-semibold">{payload.current_release?.release_code ?? "No candidate"}</p><p className="mt-1 text-sm text-white/70">{payload.current_release?.version_label ?? "Create a governed release candidate first"}</p><p className="mt-6 text-4xl font-semibold">{blockers.length}</p><p className="text-xs text-white/65">required blocker(s) remaining</p></div>
      </div>
      <div className="grid border-t border-[var(--border)] sm:grid-cols-2 lg:grid-cols-4">
        {[["Release gates",`${gatePercent}%`],["UAT",`${uatPercent}%`],["Restore-tested backups",restoreTested],["Latest automated scan",latestRun?`${latestRun.checks_passed}/${latestRun.checks_total}`:"Not run"]].map(([label,value],index)=><div className={`${index ? "border-t sm:border-l sm:border-t-0" : ""} border-[var(--border)] p-5`} key={String(label)}><p className="text-xs text-[var(--muted)]">{label}</p><p className="mt-2 text-2xl font-semibold">{value}</p></div>)}
      </div>
    </header>
    {message ? <div className="rounded-2xl border border-[var(--border)] bg-white p-4 text-sm font-semibold">{message}</div> : null}

    <section className="grid gap-5 xl:grid-cols-[.42fr_.58fr]">
      <article className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm">
        <div className="flex items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Blockers</p><h2 className="mt-1 text-2xl font-semibold">Required evidence still open</h2></div><span className="rounded-full bg-red-50 px-3 py-1 text-xs font-bold text-red-800">{blockers.length}</span></div>
        <div className="mt-5 space-y-3">{blockers.slice(0,16).map((item)=><div className="rounded-2xl border border-red-100 bg-red-50 p-4" key={`${item.kind}-${item.code}`}><div className="flex items-center justify-between gap-3"><span className="text-[10px] font-bold uppercase tracking-[.12em] text-red-700">{item.kind} · {item.code}</span><span className="rounded-full border border-red-200 px-2 py-1 text-[10px] font-bold text-red-800">{item.status}</span></div><p className="mt-2 text-sm font-semibold text-red-950">{item.title}</p>{item.public_id && ((item.kind==="GATE"&&payload.capabilities?.can_gate)||(item.kind==="UAT"&&payload.capabilities?.can_uat))?<button className="mt-3 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-semibold text-red-900 disabled:opacity-50" disabled={busy} onClick={()=>attachEvidence(item.kind==="GATE"?"gate":"uat",item.public_id,item.version)} type="button">Attach CLEAN evidence file</button>:null}</div>)}{!blockers.length?<p className="rounded-2xl bg-emerald-50 p-5 text-sm font-semibold text-emerald-800">No required gate/UAT blocker is currently recorded.</p>:null}</div>
      </article>

      <article className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm">
        <div className="flex items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Automated readiness</p><h2 className="mt-1 text-2xl font-semibold">Latest control evidence</h2></div><Link className="text-xs font-semibold text-[var(--brand)]" href="/platform/release-readiness">Open control room →</Link></div>
        {latestRun?<div className="mt-5 grid gap-3 sm:grid-cols-2">{latestRun.results.map((item)=><div className={`rounded-2xl border p-4 ${item.passed?"border-emerald-200 bg-emerald-50":"border-red-200 bg-red-50"}`} key={item.code}><div className="flex items-center justify-between gap-3"><span className="text-[10px] font-bold uppercase">{item.code}</span><span className="text-[10px] font-bold">{item.passed?"PASS":"FAIL"}</span></div><p className="mt-2 text-xs leading-5 opacity-80">{item.detail}</p></div>)}</div>:<p className="mt-5 rounded-2xl bg-slate-50 p-5 text-sm text-[var(--muted)]">No automated readiness run has been recorded.</p>}
      </article>
    </section>

    <section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">UAT coverage</p><h2 className="mt-1 text-2xl font-semibold">Business journey evidence by module</h2></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{payload.metrics.uat_passed}/{payload.metrics.uat_total} passed</span></div>
      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{modules.map((module)=>{const rows=payload.scenarios.filter((item)=>item.module===module);const passed=rows.filter((item)=>item.execution?.status==="PASSED").length;return <article className="rounded-2xl border border-[var(--border)] p-4" key={module}><div className="flex items-center justify-between gap-3"><p className="font-semibold">{module.replaceAll("_"," ")}</p><span className="text-xs font-bold text-[var(--brand)]">{passed}/{rows.length}</span></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-[var(--brand)]" style={{width:`${rows.length?Math.round(passed/rows.length*100):0}%`}}/></div><div className="mt-3 space-y-2">{rows.map((row)=><div className="flex items-center gap-2 text-xs" key={row.code}><span className={`h-2 w-2 rounded-full ${row.execution?.status==="PASSED"?"bg-emerald-500":row.execution?.status==="FAILED"||row.execution?.status==="BLOCKED"?"bg-red-500":"bg-amber-400"}`}/><span className="font-semibold">{row.code}</span><span className="min-w-0 flex-1 truncate text-[var(--muted)]">{row.title}</span></div>)}</div></article>})}</div>
    </section>

    <section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Evidence attachments</p><h2 className="mt-1 text-2xl font-semibold">Governed files linked to release proof</h2><p className="mt-1 text-sm text-[var(--muted)]">Attachments are references to existing FINALIZED + CLEAN Files records.</p></div></div>
      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {[...payload.gates.flatMap((gate)=>(gate.evidence.attachments??[]).map((file)=>({owner:`Gate ${gate.code}`,file}))), ...payload.scenarios.flatMap((scenario)=>(scenario.execution?.evidence.attachments??[]).map((file)=>({owner:`UAT ${scenario.code}`,file})))].map(({owner,file},index)=><article className="rounded-2xl border border-[var(--border)] p-4" key={`${owner}-${file.file_public_id}-${index}`}><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[var(--brand)]">{owner}</p><p className="mt-2 truncate text-sm font-semibold">{file.original_name??file.file_public_id}</p>{file.note?<p className="mt-1 text-xs text-[var(--muted)]">{file.note}</p>:null}<button className="mt-3 rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold" onClick={()=>openEvidenceFile(file.file_public_id)} type="button">Open governed evidence</button></article>)}
        {payload.gates.every((gate)=>!(gate.evidence.attachments??[]).length) && payload.scenarios.every((scenario)=>!(scenario.execution?.evidence.attachments??[]).length) ? <p className="md:col-span-2 xl:col-span-3 rounded-2xl bg-slate-50 p-6 text-sm text-[var(--muted)]">No file evidence attached yet.</p> : null}
      </div>
    </section>

    <section className="rounded-[28px] border border-[var(--border)] bg-white p-6 shadow-sm">
      <div className="flex items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Recovery evidence</p><h2 className="mt-1 text-2xl font-semibold">Backups and restore proof</h2></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{restoreTested} restore-tested</span></div>
      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{payload.backups.slice(0,12).map((item)=><article className="rounded-2xl border border-[var(--border)] p-4" key={item.public_id}><div className="flex items-center justify-between gap-3"><p className="font-semibold">{item.reference}</p><span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${statusClass(item.restore_tested?"PASSED":item.status)}`}>{item.restore_tested?"RESTORE TESTED":item.status}</span></div><p className="mt-2 text-xs text-[var(--muted)]">{item.type} · {new Date(item.captured_at).toLocaleString()}</p><p className="mt-1 text-[10px] text-[var(--muted)]">{item.release_code ?? "General recovery point"} · {item.target_code ?? "No target"}</p></article>)}{!payload.backups.length?<p className="md:col-span-2 xl:col-span-3 rounded-2xl bg-slate-50 p-6 text-sm text-[var(--muted)]">No backup evidence recorded.</p>:null}</div>
    </section>
  </div></main>;
}
