// Peer cohorts: each training batch stays together and meets in a monthly mentor-led session during handholding.
import { Plus, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../api";
import { Field, Modal } from "../ui";
import { fmtDay, today } from "../dpr/common";
import { useMentoringMeta } from "./common";

type B = { id: number; code: string; course: string; end_date: string; status: string; trainees: { id: number; name: string }[];
  sessions: { id: number; on: string; topic: string; mode: string; attended: number; attendees: number[]; notes: string | null }[]; due: boolean };
const MODES: Record<string, string> = { in_person: "In person", phone: "Phone", video: "Video call" };

export default function PeerSessions() {
  const meta = useMentoringMeta();
  const [rows, setRows] = useState<B[] | null>(null);
  const [add, setAdd] = useState<B | null>(null);
  const [f, setF] = useState({ on: today(), topic: "", mode: "in_person", attendees: [] as number[], notes: "" });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<B[]>("/mentoring/batches").then(setRows).catch(() => setRows([])); }, []);
  const save = async () => {
    if (!add) return;
    setErr(null);
    try { setRows(await api<B[]>(`/mentoring/batches/${add.id}/peer-sessions`, { body: { ...f, notes: f.notes || null } })); setAdd(null); }
    catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="stack">
      <div className="welcome"><h1>Peer cohorts</h1><p>Each training batch meets once a month with its mentor to share what is working – sales ideas, suppliers, problems.</p></div>
      {!rows ? <div className="muted">Loading…</div> : !rows.length ? <div className="card muted">No running or completed batches here.</div> : (
        <div className="stack">
          {rows.map((b) => (
            <div key={b.id} className="card stack">
              <div className="row-between wrap">
                <div><b>{b.code}</b> · {b.course}<div className="small muted">{b.trainees.length} people · ended {fmtDay(b.end_date)}</div></div>
                <span className="row-gap">{b.due && <span className="tag amber">session due this month</span>}
                  {meta?.can.write && <button className="btn small secondary" onClick={() => { setF({ on: today(), topic: "", mode: "in_person", attendees: [], notes: "" }); setAdd(b); }}><Plus size={14} /> Session</button>}</span>
              </div>
              {b.sessions.map((s) => (
                <div key={s.id} className="small peer-row"><UsersRound size={14} /> <b>{fmtDay(s.on)}</b> · {s.topic} · {MODES[s.mode]} · {s.attended}/{b.trainees.length} came{s.notes ? <div className="muted">{s.notes}</div> : null}</div>))}
              {!b.sessions.length && <div className="small muted">No peer session yet.</div>}
            </div>))}
        </div>)}
      {add && (
        <Modal title={`Peer session · ${add.code}`} onClose={() => setAdd(null)}>
          <div className="stack">
            <div className="grid-2">
              <Field label="Date"><input className="input" type="date" value={f.on} onChange={(e) => setF({ ...f, on: e.target.value })} /></Field>
              <Field label="How"><select className="input" value={f.mode} onChange={(e) => setF({ ...f, mode: e.target.value })}>{Object.entries(MODES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            </div>
            <Field label="Topic"><input className="input" value={f.topic} placeholder="e.g. Festival orders and pricing" onChange={(e) => setF({ ...f, topic: e.target.value })} /></Field>
            <Field label="Who came">
              <div className="chips">{add.trainees.map((t) => <button key={t.id} type="button" className={`chip ${f.attendees.includes(t.id) ? "on" : ""}`}
                onClick={() => setF({ ...f, attendees: f.attendees.includes(t.id) ? f.attendees.filter((x) => x !== t.id) : [...f.attendees, t.id] })}>{t.name}</button>)}</div></Field>
            <Field label="Notes"><textarea className="input" rows={3} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
            {err && <div className="error">{err}</div>}
            <div><button className="btn" disabled={f.topic.trim().length < 3} onClick={save}>Save session</button></div>
          </div>
        </Modal>)}
    </div>
  );
}
