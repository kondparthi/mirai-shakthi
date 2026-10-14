import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, apiUrl, type EntrepreneurRow } from "../../api";
import { useAuth } from "../../auth";
import { useMaster } from "../../components/masters";
import { bandOf } from "../../components/Readiness";

type Page = { total: number; page: number; pages: number; rows: EntrepreneurRow[] };
const STAGES = ["Enrol & assess", "Train & certify", "DPR & finance", "Set up enterprise", "Sell & deliver", "Track business", "Mentor & resolve", "Grow & sustain"];
const WRITE = ["admin", "programme_manager", "coordinator", "federation_staff"];

export const Avatar = ({ url, name, size = 36 }: { url: string | null; name: string; size?: number }) => (
  <span className="avatar" style={{ width: size, height: size, fontSize: size / 2.4 }}>
    {url ? <img src={apiUrl(url)} alt="" /> : name.slice(0, 1)}
  </span>
);

export default function Entrepreneurs() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") ?? "");
  const [data, setData] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);
  const districts = useMaster("district");
  const sectors = useMaster("sector");
  const allowed = user?.scope?.districts?.length && !["admin", "programme_manager"].includes(user.role) ? user.scope.districts : null;

  const setParam = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(k, v);
    else n.delete(k);
    if (k !== "page") n.delete("page");
    setSp(n, { replace: true });
  };
  useEffect(() => {
    const tm = setTimeout(() => q !== (sp.get("q") ?? "") && setParam("q", q.trim()), 300);
    return () => clearTimeout(tm);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);
  useEffect(() => {
    api<Page>(`/programme/entrepreneurs?${sp.toString()}`).then(setData).catch((e) => setError(e.message));
  }, [sp]);

  const page = Number(sp.get("page") ?? 1);
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Entrepreneurs</h1><p className="muted small" style={{ margin: 0 }}>Form 1.1 profiles. Aadhaar and bank numbers are always masked.</p></div>
        {WRITE.includes(user?.role ?? "") && <Link className="btn" to="/admin/entrepreneurs/new">+ Enrol entrepreneur</Link>}
      </div>
      <div className="filters">
        <input className="input" placeholder="Search name or mobile" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="input" value={sp.get("district") ?? ""} onChange={(e) => setParam("district", e.target.value)} aria-label="District">
          <option value="">All districts</option>
          {districts.filter((d) => !allowed || allowed.includes(d.code)).map((d) => <option key={d.code} value={d.code}>{d.name_en}</option>)}
        </select>
        <select className="input" value={sp.get("stage") ?? ""} onChange={(e) => setParam("stage", e.target.value)} aria-label="Stage">
          <option value="">All stages</option>
          {STAGES.map((s, i) => <option key={s} value={i + 1}>{i + 1}. {s}</option>)}
        </select>
        <select className="input" value={sp.get("sector") ?? ""} onChange={(e) => setParam("sector", e.target.value)} aria-label="Sector">
          <option value="">All sectors</option>
          {sectors.map((s) => <option key={s.code} value={s.code}>{s.name_en}</option>)}
        </select>
        <select className="input" value={sp.get("tag") ?? ""} onChange={(e) => setParam("tag", e.target.value)} aria-label="Area type">
          <option value="">All areas</option>
          {["rural", "urban", "tribal", "coastal"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select className="input" value={sp.get("source") ?? ""} onChange={(e) => setParam("source", e.target.value)} aria-label="Source">
          <option value="">Any source</option>
          {["self", "navigator", "import", "partner", "campaign"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select className="input" value={sp.get("verified") ?? ""} onChange={(e) => setParam("verified", e.target.value)} aria-label="Verified">
          <option value="">Verified or not</option><option value="true">Verified</option><option value="false">Not verified</option>
        </select>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Name</th><th>Place</th><th>Interests</th><th>Stage</th><th>Readiness</th><th>Status</th></tr></thead>
          <tbody>
            {data?.rows.map((e) => (
              <tr key={e.id} className="clickable" onClick={() => navigate(`/admin/entrepreneurs/${e.id}`)}>
                <td><div className="row-gap" style={{ alignItems: "center", flexWrap: "nowrap" }}><Avatar url={e.photo_url} name={e.full_name} />
                  <div><b>{e.full_name}</b><div className="small muted">{e.mobile} · {e.source}</div></div></div></td>
                <td className="small">{e.village_name}<div className="muted">{e.mandal_name}, {e.district_name}</div></td>
                <td className="small">{e.interest_names.join(", ")}</td>
                <td className="small">{e.stage}. {e.stage_name}</td>
                <td>{e.readiness ? <span className={`tag ${bandOf(e.readiness.score)}`}>{e.readiness.score}</span> : <span className="muted small">—</span>}</td>
                <td>
                  {e.verified ? <span className="tag ok">verified</span> : <span className="tag amber">not verified</span>}
                  {!e.consent && <div><span className="tag grey">no consent yet</span></div>}
                  {e.status !== "active" && <div><span className="tag grey">{e.status}</span></div>}
                </td>
              </tr>
            ))}
            {data && data.rows.length === 0 && <tr><td colSpan={6} className="muted">No entrepreneurs match.</td></tr>}
          </tbody>
        </table>
      </div>
      {data && data.pages > 1 && (
        <div className="row-gap" style={{ alignItems: "center" }}>
          <button className="btn secondary small" disabled={page <= 1} onClick={() => setParam("page", String(page - 1))}>‹ Previous</button>
          <span className="small muted">Page {page} of {data.pages} · {data.total} people</span>
          <button className="btn secondary small" disabled={page >= data.pages} onClick={() => setParam("page", String(page + 1))}>Next ›</button>
        </div>
      )}
      {data && data.pages <= 1 && <span className="small muted">{data.total} people</span>}
    </div>
  );
}
