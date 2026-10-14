import { Fragment, useEffect, useState } from "react";
import { api } from "../api";

type U = { id: number; name: string | null; mobile: string; language: string; joined: string | null; business_name: string | null;
  district: string | null; sector: string | null; summary: string[]; conversations: number };

const mask = (m: string) => (m ? `${m.slice(0, 2)}xxxxx${m.slice(-3)}` : "");

export default function Users() {
  const [q, setQ] = useState("");
  const [list, setList] = useState<U[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  useEffect(() => {
    const t = setTimeout(() => api<U[]>(`/admin/users${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`).then(setList).catch(() => setList([])), 250);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <div className="stack">
      <div><h1>MSME users</h1><p className="muted small">People using the assistant. Mobile numbers are partly hidden.</p></div>
      <div className="filters"><input className="input" placeholder="Search name, business, district, mobile" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Name</th><th>Business</th><th>District</th><th>Sector</th><th>Conversations</th><th>Joined</th></tr></thead>
          <tbody>
            {list?.map((u) => (
              <Fragment key={u.id}>
                <tr className="clickable" onClick={() => setOpen(open === u.id ? null : u.id)}>
                  <td><b>{u.name ?? "—"}</b><div className="small muted">{mask(u.mobile)} · {u.language.toUpperCase()}</div></td>
                  <td>{u.business_name ?? <span className="muted">—</span>}</td>
                  <td>{u.district ?? "—"}</td>
                  <td>{u.sector ?? "—"}</td>
                  <td>{u.conversations}</td>
                  <td className="small">{u.joined ? new Date(u.joined).toLocaleDateString() : ""}</td>
                </tr>
                {open === u.id && (
                  <tr className="detail-row"><td colSpan={6}>
                    {u.summary.length ? <div className="chips">{u.summary.map((s) => <span key={s} className="tag">{s}</span>)}</div> : <span className="muted small">No business profile yet.</span>}
                  </td></tr>
                )}
              </Fragment>
            ))}
            {list && list.length === 0 && <tr><td colSpan={6} className="muted">No users found.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
