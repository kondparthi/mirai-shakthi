import { Fragment, useEffect, useState } from "react";
import { api } from "../../api";

type Row = { id: number; at: string | null; action: string; entity: string | null; entity_id: number | null; detail: unknown; user: string | null; user_role: string | null };
type Page = { total: number; page: number; actions: string[]; rows: Row[] };

export default function Audit() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  useEffect(() => {
    api<Page>(`/admin/audit?page=${page}${action ? `&action=${action}` : ""}`).then(setData).catch(() => {});
  }, [page, action]);
  const pages = data ? Math.max(1, Math.ceil(data.total / 50)) : 1;
  return (
    <div className="stack">
      <div><h1>Audit log</h1><p className="muted small" style={{ margin: 0 }}>Every change to records, settings and access – who, what and when. Entries cannot be edited.</p></div>
      <div className="filters">
        <select className="input" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} aria-label="Action">
          <option value="">All actions</option>{data?.actions.map((a) => <option key={a} value={a}>{a.replace(/_/g, " ")}</option>)}</select>
      </div>
      <div className="card table-wrap">
        <table className="table compact">
          <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Record</th></tr></thead>
          <tbody>
            {data?.rows.map((r) => (
              <Fragment key={r.id}>
                <tr className="clickable" onClick={() => setOpen(open === r.id ? null : r.id)}>
                  <td className="small">{r.at ? new Date(r.at).toLocaleString() : ""}</td>
                  <td className="small">{r.user ?? <span className="muted">system / removed</span>}{r.user_role && <div className="muted">{r.user_role}</div>}</td>
                  <td>{r.action.replace(/_/g, " ")}</td>
                  <td className="small">{r.entity}{r.entity_id ? ` #${r.entity_id}` : ""}</td>
                </tr>
                {open === r.id && r.detail != null && <tr className="detail-row"><td colSpan={4}><pre className="json">{JSON.stringify(r.detail, null, 2)}</pre></td></tr>}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <div className="row-gap" style={{ alignItems: "center" }}>
        <button className="btn secondary small" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹ Newer</button>
        <span className="small muted">Page {page} of {pages} · {data?.total ?? 0} entries</span>
        <button className="btn secondary small" disabled={page >= pages} onClick={() => setPage(page + 1)}>Older ›</button>
      </div>
    </div>
  );
}
