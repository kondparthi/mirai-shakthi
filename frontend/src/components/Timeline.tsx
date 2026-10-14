// Request timeline shared by the MSME app, the expert workspace and the admin queue.
import { useState } from "react";
import type { ConnectRequest, ConnectUpdate } from "../api";

const WHO: Record<string, string> = { msme: "Business owner", expert: "Expert", admin: "MIRAI team", system: "System" };
const STEPS: [string, string][] = [["sent", "Sent"], ["accepted", "Accepted"], ["quoted", "Quote"], ["in_progress", "In progress"], ["done", "Done"]];

export const rupees = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
export const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");

export function StatusSteps({ status }: { status: string }) {
  if (status === "declined" || status === "cancelled") return <div className={`req-status ${status}`}>{status === "declined" ? "Declined by the expert" : "Cancelled"}</div>;
  const idx = STEPS.findIndex(([s]) => s === status);
  return (
    <div className="req-steps" aria-label={`Status: ${status}`}>
      {STEPS.map(([s, label], i) => <div key={s} className={i <= idx ? "on" : ""}><span />{label}</div>)}
    </div>
  );
}

export function StatusTag({ r }: { r: Pick<ConnectRequest, "status" | "status_label" | "overdue"> }) {
  const cls = r.overdue ? "alert" : ["done"].includes(r.status) ? "ok" : ["declined", "cancelled"].includes(r.status) ? "grey" : r.status === "quoted" ? "amber" : "";
  return <span className={`tag ${cls}`}>{r.overdue ? "Overdue – no reply" : r.status_label}</span>;
}

export function Timeline({ updates, me }: { updates: ConnectUpdate[]; me: "msme" | "expert" | "admin" }) {
  return (
    <ol className="timeline">
      {updates.map((u) => (
        <li key={u.id} className={`tl k-${u.kind} ${u.role === me ? "mine" : ""}`}>
          <div className="tl-head">
            <b>{u.role === me ? "You" : WHO[u.role] ?? u.role}</b>
            {u.kind === "status" && u.status_label && <span className="tag">{u.status_label}</span>}
            {u.kind === "quote" && <span className="tag amber">Quote {u.amount != null ? rupees(u.amount) : ""}</span>}
            {u.kind === "rating" && <span className="tag ok">{"★".repeat(u.amount ?? 0)}{"☆".repeat(5 - (u.amount ?? 0))}</span>}
            <span className="small muted">{when(u.at)}</span>
          </div>
          {u.text && <div className="tl-text">{u.text}</div>}
        </li>
      ))}
    </ol>
  );
}

export function MessageBox({ onSend, placeholder = "Write a message" }: { onSend: (text: string) => Promise<void>; placeholder?: string }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form className="askbox" onSubmit={async (e) => {
      e.preventDefault();
      if (!text.trim()) return;
      setBusy(true);
      try { await onSend(text.trim()); setText(""); } finally { setBusy(false); }
    }}>
      <input className="input" value={text} placeholder={placeholder} onChange={(e) => setText(e.target.value)} />
      <button className="btn" disabled={busy || !text.trim()}>Send</button>
    </form>
  );
}
