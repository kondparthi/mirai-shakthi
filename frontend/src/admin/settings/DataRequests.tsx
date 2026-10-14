// DPDP Act 2023 – requests from people to export or delete their data.
import { useCallback, useEffect, useState } from "react";
import { api, saveBlob } from "../../api";
import { Modal } from "../ui";

type Req = { id: number; kind: "export" | "delete"; status: string; reason: string | null; resolution: string | null; mobile: string | null;
  name: string | null; created_at: string | null; resolved_at: string | null };

export default function DataRequests() {
  const [status, setStatus] = useState("open");
  const [rows, setRows] = useState<Req[] | null>(null);
  const [act, setAct] = useState<{ r: Req; action: "done" | "reject" | "erase" } | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<Req[]>(`/admin/data-requests?status=${status}`).then(setRows).catch(() => setRows([])), [status]);
  useEffect(() => {
    load();
  }, [load]);

  const exportData = async (r: Req) => {
    const d = await api(`/admin/data-requests/${r.id}/export`);
    saveBlob(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" }), `mirai-data-${r.mobile ?? r.id}.json`);
  };
  const resolve = async () => {
    if (!act) return;
    if (act.action === "erase" && !window.confirm(`Permanently delete ${act.r.name ?? act.r.mobile}'s account and data? This cannot be undone.`)) return;
    setError(null);
    try {
      await api(`/admin/data-requests/${act.r.id}/resolve`, { body: { action: act.action, note } });
      setAct(null);
      setNote("");
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const days = (d: string | null) => (d ? Math.floor((Date.now() - new Date(d).getTime()) / 86400000) : 0);

  return (
    <div className="stack">
      <div><h1>Data requests</h1><p className="muted small" style={{ margin: 0 }}>People can download their data in the app and ask for it to be deleted. Reply within 30 days. Erasing removes the account, enrolment, photo, conversations and documents; the audit log keeps only that it happened.</p></div>
      <div className="tabs">{["open", "done", "rejected"].map((s) => <button key={s} className={s === status ? "on" : ""} onClick={() => setStatus(s)}>{s}</button>)}</div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Person</th><th>Request</th><th>Received</th><th>{status === "open" ? "Actions" : "Outcome"}</th></tr></thead>
          <tbody>
            {rows?.map((r) => (
              <tr key={r.id}>
                <td><b>{r.name ?? "—"}</b><div className="small muted">{r.mobile}</div></td>
                <td>{r.kind === "delete" ? <span className="tag alert">delete</span> : <span className="tag">export</span>}{r.reason && <div className="small muted">{r.reason}</div>}</td>
                <td className="small">{r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}
                  {status === "open" && <div className={days(r.created_at) > 25 ? "tag alert" : "muted"}>{days(r.created_at)} days ago</div>}</td>
                <td>
                  {status === "open" ? (
                    <div className="row-gap">
                      {r.name !== null || r.mobile ? <button className="btn secondary small" onClick={() => exportData(r)}>Download data</button> : null}
                      {r.kind === "delete" && <button className="btn danger small" onClick={() => setAct({ r, action: "erase" })}>Erase now</button>}
                      <button className="btn secondary small" onClick={() => setAct({ r, action: "done" })}>Mark done</button>
                      <button className="btn ghost small" onClick={() => setAct({ r, action: "reject" })}>Reject</button>
                    </div>
                  ) : <span className="small">{r.resolution}</span>}
                </td>
              </tr>
            ))}
            {rows && rows.length === 0 && <tr><td colSpan={4} className="muted">No {status} requests.</td></tr>}
          </tbody>
        </table>
      </div>
      {act && (
        <Modal title={act.action === "erase" ? "Erase this person's data" : act.action === "reject" ? "Reject request" : "Mark as done"} onClose={() => setAct(null)}>
          <div className="stack">
            <label className="field"><span>{act.action === "reject" ? "Reason (shown to the person)" : "Note (shown to the person)"}</span>
              <textarea className="input" rows={3} value={note} onChange={(e) => setNote(e.target.value)}
                placeholder={act.action === "erase" ? "Your account and data were deleted on …" : ""} /></label>
            {act.action === "reject" && <p className="small muted" style={{ margin: 0 }}>Only reject when the law requires MIRAI to keep the data (for example, an active loan or subsidy file), and say which.</p>}
            {error && <div className="error">{error}</div>}
            <button className={`btn ${act.action === "erase" ? "danger" : ""}`} disabled={note.trim().length < 3} onClick={resolve}>Confirm</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
