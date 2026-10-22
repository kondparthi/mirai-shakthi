// Support tickets (Form 10.2): my queue (assigned to me, my mentees' units, referred to me) or all in scope; open a ticket to work on it.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { Modal } from "../ui";
import { PRIORITY, T_STATUS, type Ticket, TicketView, ago, useMentoringMeta } from "./common";

type Res = { counts: Record<string, number>; overdue: number; rows: Ticket[] };

export default function Tickets() {
  const meta = useMentoringMeta();
  const [view, setView] = useState<"mine" | "all">("mine");
  const [status, setStatus] = useState("active");
  const [category, setCategory] = useState("");
  const [res, setRes] = useState<Res | null>(null);
  const [open, setOpen] = useState<Ticket | null>(null);
  const load = useCallback(() => api<Res>(`/mentoring/tickets?view=${view}&status=${status}${category ? `&category=${category}` : ""}`).then(setRes).catch(() => setRes({ counts: {}, overdue: 0, rows: [] })), [view, status, category]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="stack">
      <div className="welcome"><h1>Support tickets</h1><p>Problems raised by entrepreneurs, navigators and mentors – assigned by category, with a due date by priority.</p></div>
      <div className="filters row-gap">
        <div className="tabs">{([["mine", "My queue"], ["all", "All in my districts"]] as const).map(([k, l]) => <button key={k} className={view === k ? "on" : ""} onClick={() => setView(k)}>{l}</button>)}</div>
        <select className="input" aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="active">Open & in progress{res ? ` (${(res.counts.open ?? 0) + (res.counts.in_progress ?? 0)})` : ""}</option>
          <option value="resolved">Resolved ({res?.counts.resolved ?? 0})</option><option value="closed">Closed ({res?.counts.closed ?? 0})</option><option value="">All</option></select>
        <select className="input" aria-label="Category" value={category} onChange={(e) => setCategory(e.target.value)}><option value="">All categories</option>{meta?.categories.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}</select>
        {res && res.overdue > 0 && <span className="tag alert">{res.overdue} overdue</span>}
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Ticket</th><th>Unit</th><th>Category</th><th>Priority</th><th>Status</th><th>Assigned to</th><th>Due</th></tr></thead>
          <tbody>
            {(res?.rows ?? []).map((t) => (
              <tr key={t.id} className="clickable" onClick={() => setOpen(t)}>
                <td><b>{t.code}</b><div className="small muted ellipsis-2">{t.description}</div></td>
                <td className="small"><Link to={`/admin/mentoring/units/${t.unit.id}`} onClick={(e) => e.stopPropagation()}>{t.unit.name}</Link><div className="muted">{ago(t.created_at)} · {t.channel}</div></td>
                <td className="small">{t.category_label}</td>
                <td><span className={`tag ${PRIORITY[t.priority][0]}`}>{PRIORITY[t.priority][1]}</span></td>
                <td><span className={`tag ${T_STATUS[t.status][0]}`}>{T_STATUS[t.status][1]}</span>{t.referrals.length > 0 && <div className="small muted">referred</div>}</td>
                <td className="small">{t.assigned_to?.name ?? "—"}</td>
                <td className={`small ${t.overdue ? "neg" : ""}`}>{t.due_by ?? "—"}{t.hours != null && <div className="muted">{t.hours < 48 ? `${t.hours} h` : `${Math.round(t.hours / 24)} d`}</div>}</td>
              </tr>))}
            {res && !res.rows.length && <tr><td colSpan={7} className="muted">No tickets here.</td></tr>}
            {!res && <tr><td colSpan={7} className="muted">Loading…</td></tr>}
          </tbody>
        </table>
      </div>
      {open && meta && (
        <Modal title={`${open.code} · ${open.unit.name}`} onClose={() => { setOpen(null); load(); }} wide>
          <TicketView t={open} meta={meta} onChange={(t) => setOpen(t)} />
        </Modal>)}
    </div>
  );
}
