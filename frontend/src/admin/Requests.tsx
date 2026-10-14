// Admin screen A5 – Handholding request queue: watch SLAs, reassign declined or overdue cases.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ConnectRequest } from "../api";
import { MessageBox, StatusSteps, StatusTag, Timeline, when } from "../components/Timeline";
import { Field, Modal } from "./ui";

type ExpertRow = { id: number; name: string; organisation: string | null; services: string[]; districts: string[]; response_hours: number; status: string };

function RequestModal({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const [r, setR] = useState<ConnectRequest | null>(null);
  const [experts, setExperts] = useState<ExpertRow[]>([]);
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");
  const [cancelNote, setCancelNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api<ConnectRequest>(`/admin/requests/${id}`).then(setR).catch((e) => setError(e.message)); }, [id]);
  useEffect(() => { api<ExpertRow[]>("/admin/experts?status=approved").then(setExperts).catch(() => {}); }, []);

  const act = async (path: string, body: unknown) => {
    setError(null);
    try { setR(await api<ConnectRequest>(`/admin/requests/${id}/${path}`, { body })); onChanged(); }
    catch (e) { setError((e as Error).message); }
  };

  const can = (a: string) => r?.actions?.includes(a);
  const options = r ? experts.filter((e) => e.services.includes(r.service) && e.id !== r.expert?.id) : [];

  return (
    <Modal title={r ? `Request #${r.id} · ${r.service_label}` : "Request"} onClose={onClose} wide>
      {!r && <div className="muted">{error ?? "Loading…"}</div>}
      {r && (
        <div className="stack">
          <StatusSteps status={r.status} />
          <div className="grid-2">
            <div className="stack">
              <div className="small">
                <b>{r.client?.business || r.client?.name}</b> · {r.client?.district} · {r.client?.mobile}<br />
                Expert: <b>{r.expert?.name}</b> ({r.expert?.organisation}) · replies in {r.response_hours} h<br />
                Sent {when(r.created_at)}{r.respond_by ? ` · reply due ${when(r.respond_by)}` : ""} · <StatusTag r={r} />
              </div>
              <details><summary className="small"><b>Case summary</b></summary><pre className="summary-text">{r.summary}</pre></details>
              {can("reassign") && (
                <div className="card stack" style={{ background: "var(--bg)" }}>
                  <b>Reassign to another expert</b>
                  {options.length === 0 ? <div className="small muted">No other approved expert offers this service.</div> : (<>
                    <Field label="Expert">
                      <select className="input" value={to} onChange={(e) => setTo(e.target.value)}>
                        <option value="">Choose…</option>
                        {options.map((e) => <option key={e.id} value={e.id}>{e.name} – {e.districts.join(", ")} ({e.response_hours} h)</option>)}
                      </select>
                    </Field>
                    <Field label="Note to the user (optional)"><input className="input" value={note} onChange={(e) => setNote(e.target.value)} /></Field>
                    <div><button className="btn" disabled={!to} onClick={() => act("reassign", { expert_id: Number(to), note: note || null })}>Reassign</button></div>
                  </>)}
                </div>
              )}
              {can("cancel") && (
                <div className="row-between" style={{ gap: 8, padding: 0 }}>
                  <input className="input" placeholder="Reason for cancelling" value={cancelNote} onChange={(e) => setCancelNote(e.target.value)} />
                  <button className="btn ghost danger" style={{ whiteSpace: "nowrap" }} disabled={!cancelNote.trim()} onClick={() => act("cancel", { text: cancelNote.trim() })}>Cancel request</button>
                </div>
              )}
            </div>
            <div className="stack">
              <b>Updates</b>
              <Timeline updates={r.updates ?? []} me="admin" />
              {can("message") && <MessageBox placeholder="Message both sides as MIRAI" onSend={(text) => act("message", { text })} />}
            </div>
          </div>
          {error && <div className="error">{error}</div>}
        </div>
      )}
    </Modal>
  );
}

export default function RequestsQueue() {
  const [filter, setFilter] = useState("attention");
  const [rows, setRows] = useState<ConnectRequest[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const latest = useRef(0);
  const load = useCallback(() => {
    // Ignore replies to an earlier filter that arrive after a newer one.
    const n = ++latest.current;
    const q = filter === "attention" ? "?attention=true" : filter ? `?status=${filter}` : "";
    api<ConnectRequest[]>(`/admin/requests${q}`).then((r) => n === latest.current && setRows(r))
      .catch(() => n === latest.current && setRows([]));
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="stack">
      <div><h1>Expert requests</h1>
        <p className="muted small">Cases MSMEs sent through Handholding (screen A5). “Needs attention” shows cases declined by the expert or past the reply time – reassign them so no one is left waiting.</p></div>
      <div className="filters">
        <select className="input" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter requests">
          <option value="attention">Needs attention</option><option value="open">All open</option><option value="done">Completed</option>
          <option value="cancelled">Cancelled</option><option value="">All requests</option>
        </select>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>#</th><th>Business</th><th>Service</th><th>Expert</th><th>Last update</th><th>Status</th></tr></thead>
          <tbody>
            {rows === null && <tr><td colSpan={6} className="muted">Loading…</td></tr>}
            {rows?.length === 0 && <tr><td colSpan={6} className="muted">{filter === "attention" ? "Nothing needs attention right now." : "No requests."}</td></tr>}
            {rows?.map((r) => (
              <tr key={r.id} className="clickable" onClick={() => setOpen(r.id)}>
                <td>{r.id}</td>
                <td><b>{r.client?.business || r.client?.name || "—"}</b><div className="small muted">{r.client?.district}</div></td>
                <td className="small">{r.service_label}</td>
                <td className="small">{r.expert?.name}</td>
                <td className="small">{when(r.last_update ?? r.created_at)}</td>
                <td><StatusTag r={r} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open !== null && <RequestModal id={open} onClose={() => setOpen(null)} onChanged={load} />}
    </div>
  );
}
