// Training reports by course, sponsor and district, with the trainee-level CSV for sponsor reporting.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiDownload, apiUrl, type ExternalCert } from "../../api";
import { useAuth } from "../../auth";

type G = { key: string; batches: number; trainees: number; completed: number; certified: number; cert_rate: number; rating: number | null };
type S = { batches: number; running: number; upcoming: number; trainees: number; women: number; certified: number; by_course: G[]; by_sponsor: G[]; by_district: G[] };
type X = ExternalCert & { entrepreneur: { id: number; full_name: string; district_name: string | null } };

function Table({ title, rows }: { title: string; rows: G[] }) {
  return (
    <div className="card table-wrap">
      <h2 style={{ padding: "12px 14px 0", margin: 0 }}>{title}</h2>
      <table className="table compact">
        <thead><tr><th /><th className="num">Batches</th><th className="num">Trainees</th><th className="num">Certified</th><th className="num">Rate</th><th className="num">Rating</th></tr></thead>
        <tbody>{rows.map((g) => (
          <tr key={g.key}><td>{g.key}</td><td className="num">{g.batches}</td><td className="num">{g.trainees}</td><td className="num">{g.certified}</td>
            <td className="num">{g.cert_rate}%</td><td className="num">{g.rating ? `★ ${g.rating}` : "—"}</td></tr>
        ))}{rows.length === 0 && <tr><td colSpan={6} className="muted">No data yet.</td></tr>}</tbody>
      </table>
    </div>
  );
}

export function ExternalQueue() {
  const [rows, setRows] = useState<X[] | null>(null);
  const [status, setStatus] = useState("pending");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<X[]>(`/training/external-certificates?status=${status}`).then(setRows).catch(() => setRows([])), [status]);
  useEffect(() => {
    load();
  }, [load]);
  const decide = async (x: X, s: "verified" | "rejected") => {
    const note = s === "rejected" ? window.prompt("Why is it rejected? (shown to the person)") : null;
    if (s === "rejected" && !note) return;
    setError(null);
    try {
      await api(`/training/external-certificates/${x.id}/verify`, { body: { status: s, note } });
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div><h1>Uploaded certificates</h1><p className="muted small" style={{ margin: 0 }}>DGCA Remote Pilot, FSSAI and partner certificates uploaded by entrepreneurs. Open the file, check it, then verify or reject.</p></div>
      <div className="tabs">{["pending", "verified", "rejected"].map((s) => <button key={s} className={s === status ? "on" : ""} onClick={() => setStatus(s)}>{s}</button>)}</div>
      {error && <div className="error">{error}</div>}
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Person</th><th>Certificate</th><th>File</th><th /></tr></thead>
          <tbody>
            {rows?.map((x) => (
              <tr key={x.id}>
                <td><Link to={`/admin/entrepreneurs/${x.entrepreneur.id}`}><b>{x.entrepreneur.full_name}</b></Link><div className="small muted">{x.entrepreneur.district_name}</div></td>
                <td><b>{x.title}</b><div className="small muted">{[x.number, x.issuer, x.issued_on].filter(Boolean).join(" · ")}</div>{x.note && <div className="small">{x.note}</div>}</td>
                <td>{x.file_url && <a href={apiUrl(x.file_url)} target="_blank" rel="noreferrer">Open file</a>}</td>
                <td>{x.status === "pending" && <span className="row-gap"><button className="btn small" onClick={() => decide(x, "verified")}>Verify</button>
                  <button className="btn ghost small danger" onClick={() => decide(x, "rejected")}>Reject</button></span>}</td>
              </tr>
            ))}
            {rows && rows.length === 0 && <tr><td colSpan={4} className="muted">Nothing {status}.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Reports() {
  const { user } = useAuth();
  const [s, setS] = useState<S | null>(null);
  const [sponsor, setSponsor] = useState("");
  useEffect(() => {
    api<S>("/training/reports/summary").then(setS).catch(() => {});
  }, []);
  if (!s) return <div className="muted">Loading…</div>;
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Training reports</h1><p className="muted small" style={{ margin: 0 }}>{["admin", "programme_manager"].includes(user?.role ?? "") ? "All districts" : "Your area"} · cancelled batches are left out.</p></div>
        <div className="row-gap" style={{ alignItems: "flex-end" }}>
          <select className="input" value={sponsor} onChange={(e) => setSponsor(e.target.value)} aria-label="Sponsor">
            <option value="">All sponsors</option>{s.by_sponsor.map((g) => <option key={g.key} value={g.key.replace(/ \((CSR|GOVT)\)$/, "")}>{g.key}</option>)}</select>
          <button className="btn secondary" onClick={() => apiDownload(`/training/reports/trainees.csv${sponsor ? `?sponsor=${encodeURIComponent(sponsor)}` : ""}`, "training_trainees.csv")}>Download trainee list (CSV)</button>
        </div>
      </div>
      <div className="kpis">
        <div><span>Batches</span><b>{s.batches}</b></div><div><span>Running now</span><b>{s.running}</b></div><div><span>Upcoming</span><b>{s.upcoming}</b></div>
        <div><span>Trainees</span><b>{s.trainees}</b></div><div><span>Women</span><b>{s.trainees ? Math.round((100 * s.women) / s.trainees) : 0}%</b></div>
        <div><span>Certified</span><b>{s.certified}</b></div>
      </div>
      <Table title="By course" rows={s.by_course} />
      <Table title="By sponsor" rows={s.by_sponsor} />
      <Table title="By district" rows={s.by_district} />
    </div>
  );
}
