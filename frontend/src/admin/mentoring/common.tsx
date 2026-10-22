// Shared pieces for mentoring & support (M10): types, meta, tags and the ticket view used by the queue and the unit page.
import { ArrowRightLeft, MessageSquare, Share2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, apiUrl } from "../../api";
import { Field } from "../ui";

export type Opt = { code: string; label: string };
export type MentoringMeta = { mentors: { id: number; name: string; units: number; districts: string[] }[]; staff: { id: number; name: string; role: string }[];
  issues: Opt[]; categories: Opt[]; goals: Opt[]; support: Opt[]; training: Opt[]; outcomes: Opt[];
  can: { write: boolean; assign: boolean; supervise: boolean }; me: { id: number; role: string } };
export type Ticket = { id: number; code: string; unit: { id: number; name: string; code: string }; category: string; category_label: string; description: string;
  photo_url: string | null; priority: "low" | "medium" | "high"; channel: string; status: "open" | "in_progress" | "resolved" | "closed";
  assigned_to: { id: number; name: string } | null; due_by: string | null; overdue: boolean; resolution: string | null; hours: number | null;
  resolved_at: string | null; rating: number | null; referrals: { kind: string; to: string; user_id?: number | null; note?: string | null; at: string; by: string }[];
  events: { at: string; by: string; kind: string; text: string }[]; raised_by: string | null; created_at: string | null };
export type CaseRow = { unit: { id: number; code: string; name: string; status: string; launch_date: string | null; owner: string; mobile: string | null;
  district_name?: string; model: string | null }; mentor: { id: number; name: string } | null; status: string | null; month_no: number; end_date: string | null;
  health: "green" | "amber" | "red" | null; last_review: string | null; review_due: boolean; review_month: string; last_visit: string | null;
  next_visit: string | null; tickets_open: number; tickets_high: number; tickets_overdue: number; actions_overdue: number;
  alerts: { code: string; level: string; text: string }[]; growth_plans: number };

let cached: MentoringMeta | null = null;
export function useMentoringMeta() {
  const [m, setM] = useState<MentoringMeta | null>(cached);
  useEffect(() => {
    if (!cached) api<MentoringMeta>("/mentoring/meta").then((r) => { cached = r; setM(r); }).catch(() => {});
  }, []);
  return m;
}

export const HEALTH_TAG: Record<string, [string, string]> = { green: ["ok", "Green"], amber: ["amber", "Amber"], red: ["alert", "Red"] };
export const T_STATUS: Record<string, [string, string]> = { open: ["amber", "Open"], in_progress: ["", "In progress"], resolved: ["ok", "Resolved"], closed: ["grey", "Closed"] };
export const PRIORITY: Record<string, [string, string]> = { high: ["alert", "High"], medium: ["amber", "Medium"], low: ["grey", "Low"] };
export const REFER_KINDS: [string, string][] = [["sector_expert", "Sector expert"], ["bdsp", "Business development service provider"], ["ca_cs", "CA / CS"],
  ["bank", "Bank"], ["supplier", "Supplier / service engineer"], ["government", "Government department"], ["other", "Other"]];
export const monthLabel = (k: string | null | undefined) => (k ? new Date(`${k}-01`).toLocaleDateString("en-IN", { month: "short", year: "numeric" }) : "—");
export const ago = (iso: string | null) => (iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "");

export function HealthDot({ h }: { h: string | null }) {
  return h ? <span className={`tag ${HEALTH_TAG[h][0]}`}>{HEALTH_TAG[h][1]}</span> : <span className="tag grey">Not reviewed</span>;
}

/** Ticket detail with the actions the viewer may take. */
export function TicketView({ t, meta, onChange }: { t: Ticket; meta: MentoringMeta; onChange: (t: Ticket) => void }) {
  const [res, setRes] = useState("");
  const [comment, setComment] = useState("");
  const [to, setTo] = useState<number | "">("");
  const [refer, setRefer] = useState<{ kind: string; to: string; user_id: number | ""; note: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const call = async (path: string, body: object) => {
    setErr(null);
    try { onChange(await api<Ticket>(`/mentoring/tickets/${t.id}/${path}`, { body })); } catch (e) { setErr((e as Error).message); }
  };
  const active = t.status === "open" || t.status === "in_progress";
  return (
    <div className="stack ticket-view">
      <div className="row-gap">
        <span className={`tag ${T_STATUS[t.status][0]}`}>{T_STATUS[t.status][1]}</span>
        <span className={`tag ${PRIORITY[t.priority][0]}`}>{PRIORITY[t.priority][1]} priority</span>
        <span className="tag grey">{t.category_label}</span>
        {t.overdue && <span className="tag alert">Overdue – due {t.due_by}</span>}
      </div>
      <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{t.description}</p>
      {t.photo_url && <img className="ticket-photo" src={apiUrl(t.photo_url)} alt="Photo with the request" />}
      <div className="small muted">{t.code} · {t.unit.name} · raised by {t.raised_by ?? "—"} ({t.channel}) · {ago(t.created_at)} · assigned to <b>{t.assigned_to?.name ?? "nobody"}</b>
        {t.due_by && active ? ` · due ${t.due_by}` : ""}{t.hours != null ? ` · resolved in ${t.hours < 48 ? `${t.hours} h` : `${Math.round(t.hours / 24)} days`}` : ""}
        {t.rating ? ` · ${"★".repeat(t.rating)}` : ""}</div>
      {t.resolution && <div className="notice ok-notice"><b>Resolution:</b> {t.resolution}</div>}
      {t.referrals.length > 0 && <div className="small">{t.referrals.map((r, i) => <div key={i}><Share2 size={12} /> Referred to <b>{r.to}</b> ({REFER_KINDS.find(([k]) => k === r.kind)?.[1] ?? r.kind}){r.note ? ` – ${r.note}` : ""} · {r.by}</div>)}</div>}
      <ol className="ticket-events">{t.events.map((e, i) => <li key={i} className={e.kind}><b>{e.by}</b> {e.text}<small>{ago(e.at)}</small></li>)}</ol>
      {err && <div className="error">{err}</div>}
      {active && (
        <div className="card stack soft-card">
          <div className="row-gap">
            {t.status === "open" && <button className="btn small secondary" onClick={() => call("status", { status: "in_progress" })}>Start working on it</button>}
            <button className="btn small ghost" onClick={() => setRefer(refer ? null : { kind: "sector_expert", to: "", user_id: "", note: "" })}><Share2 size={14} /> Refer</button>
          </div>
          <Field label="Resolution"><textarea className="input" rows={2} value={res} onChange={(e) => setRes(e.target.value)} placeholder="What was done to solve it" /></Field>
          <div><button className="btn small" disabled={res.trim().length < 3} onClick={() => call("status", { status: "resolved", resolution: res })}>Mark resolved</button></div>
          {refer && (
            <div className="grid-2">
              <Field label="Referral to"><select className="input" value={refer.kind} onChange={(e) => setRefer({ ...refer, kind: e.target.value })}>{REFER_KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
              <Field label="Staff with a login (optional)"><select className="input" value={refer.user_id} onChange={(e) => {
                const s = meta.staff.find((x) => x.id === Number(e.target.value)); setRefer({ ...refer, user_id: e.target.value ? Number(e.target.value) : "", to: s ? s.name : refer.to });
              }}><option value="">—</option>{meta.staff.filter((s) => s.role === "sector_expert" || s.role === "mentor" || s.role === "dpr_officer").map((s) => <option key={s.id} value={s.id}>{s.name} ({s.role.replace("_", " ")})</option>)}</select></Field>
              <Field label="Name / organisation"><input className="input" value={refer.to} onChange={(e) => setRefer({ ...refer, to: e.target.value })} /></Field>
              <Field label="Note"><input className="input" value={refer.note} onChange={(e) => setRefer({ ...refer, note: e.target.value })} /></Field>
              <div><button className="btn small" disabled={refer.to.trim().length < 2} onClick={async () => { await call("refer", { ...refer, user_id: refer.user_id || null, note: refer.note || null }); setRefer(null); }}>Save referral</button></div>
            </div>)}
          {(meta.can.supervise || t.assigned_to?.id === meta.me.id) && (
            <div className="row-gap">
              <select className="input" style={{ flex: 1, minWidth: 180 }} aria-label="Pass to" value={to} onChange={(e) => setTo(e.target.value ? Number(e.target.value) : "")}>
                <option value="">Pass to…</option>{meta.staff.filter((s) => s.id !== t.assigned_to?.id).map((s) => <option key={s.id} value={s.id}>{s.name} ({s.role.replace("_", " ")})</option>)}</select>
              <button className="btn small ghost" disabled={!to} onClick={async () => { await call("assign", { user_id: to }); setTo(""); }}><ArrowRightLeft size={14} /> Assign</button>
            </div>)}
        </div>)}
      {t.status !== "closed" && (
        <div className="row-gap">
          <input className="input" style={{ flex: 1, minWidth: 0 }} aria-label="Comment" placeholder="Add a note for the team" value={comment} onChange={(e) => setComment(e.target.value)} />
          <button className="btn small ghost" disabled={comment.trim().length < 2} onClick={async () => { await call("comment", { text: comment }); setComment(""); }}><MessageSquare size={14} /> Add</button>
        </div>)}
    </div>
  );
}
