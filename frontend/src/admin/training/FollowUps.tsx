// Form 4.5 – mentor follow-ups at 30 / 90 / 180 days after certification.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { Field, Modal } from "../ui";
import { fmtDate } from "./Batches";

type Due = { trainee_id: number; point: number; due: string; overdue: boolean; name: string; mobile: string; entrepreneur_id: number; village_name: string | null; course: string; batch: string };
const STATUS: Record<string, string> = { started: "Enterprise started", in_process: "In process (DPR or loan)", not_started: "Not started", employed: "Employed elsewhere", dropped: "Dropped out" };
const SUPPORT: Record<string, string> = { refresher: "Refresher training", finance: "Finance", market: "Market linkage", equipment: "Equipment", mentoring: "More mentoring" };

function FollowUpForm({ d, onSaved }: { d: Due; onSaved: () => void }) {
  const [f, setF] = useState({ status: "", skills_used: "", support: [] as string[], next_action: "", next_date: "" });
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setError(null);
    try {
      await api(`/training/trainees/${d.trainee_id}/followups`, { body: { point: d.point, ...f, next_action: f.next_action || null, next_date: f.next_date || null } });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const chip = (on: boolean, label: string, onClick: () => void) => <button type="button" key={label} className={`chip ${on ? "on" : ""}`} aria-pressed={on} onClick={onClick}>{label}</button>;
  return (
    <div className="stack">
      <p className="small muted" style={{ margin: 0 }}>{d.course} · batch {d.batch} · call {d.mobile}</p>
      <Field label="Where are they now?"><div className="chips small-chips">{Object.entries(STATUS).map(([k, v]) => chip(f.status === k, v, () => setF({ ...f, status: k })))}</div></Field>
      <Field label="Are they using the skills?"><div className="chips small-chips">{[["yes", "Yes"], ["partly", "Partly"], ["no", "No"]].map(([k, v]) => chip(f.skills_used === k, v, () => setF({ ...f, skills_used: k })))}</div></Field>
      <Field label="Support needed"><div className="chips small-chips">{Object.entries(SUPPORT).map(([k, v]) => chip(f.support.includes(k), v, () => setF({ ...f, support: f.support.includes(k) ? f.support.filter((x) => x !== k) : [...f.support, k] })))}</div></Field>
      <div className="grid-2">
        <Field label="Next action"><input className="input" value={f.next_action} onChange={(e) => setF({ ...f, next_action: e.target.value })} /></Field>
        <Field label="By when"><input className="input" type="date" value={f.next_date} onChange={(e) => setF({ ...f, next_date: e.target.value })} /></Field>
      </div>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" disabled={!f.status || !f.skills_used} onClick={save}>Save follow-up</button></div>
    </div>
  );
}

export default function FollowUps() {
  const [rows, setRows] = useState<Due[] | null>(null);
  const [open, setOpen] = useState<Due | null>(null);
  const load = useCallback(() => api<Due[]>("/training/followups").then(setRows).catch(() => setRows([])), []);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <div className="stack">
      <div><h1>Training follow-ups</h1><p className="muted small" style={{ margin: 0 }}>Call each trained person 30, 90 and 180 days after certification (Form 4.5). Shown here from 7 days before the due date.</p></div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Person</th><th>Training</th><th>Follow-up</th><th>Due</th><th /></tr></thead>
          <tbody>
            {rows?.map((d) => (
              <tr key={`${d.trainee_id}-${d.point}`}>
                <td><Link to={`/admin/entrepreneurs/${d.entrepreneur_id}`}><b>{d.name}</b></Link><div className="small muted">{d.mobile} · {d.village_name}</div></td>
                <td className="small">{d.course}<div className="muted">{d.batch}</div></td>
                <td>{d.point} days</td>
                <td><span className={`tag ${d.overdue ? "alert" : "amber"}`}>{fmtDate(d.due)}</span></td>
                <td><button className="btn small" onClick={() => setOpen(d)}>Record</button></td>
              </tr>
            ))}
            {rows && rows.length === 0 && <tr><td colSpan={5} className="muted">No follow-ups due. 🎉</td></tr>}
          </tbody>
        </table>
      </div>
      {open && <Modal title={`${open.point}-day follow-up – ${open.name}`} onClose={() => setOpen(null)}><FollowUpForm d={open} onSaved={() => { setOpen(null); load(); }} /></Modal>}
    </div>
  );
}
