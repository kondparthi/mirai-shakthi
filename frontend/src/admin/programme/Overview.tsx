import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";

type Stats = {
  total: number; verified: number; pending_consent: number; women: number; groups: number; assessed: number;
  avg_readiness: number | null; ready: number;
  by_stage: { stage: number; name: string; count: number }[];
  by_district: { district: string; name: string; count: number }[];
  by_source: Record<string, number>;
};
const SOURCES: Record<string, string> = { self: "Self (app)", navigator: "Field navigator", import: "Bulk import", partner: "Partner", campaign: "Campaign" };
const WRITE = ["admin", "programme_manager", "coordinator", "federation_staff"];

export default function Overview() {
  const { user } = useAuth();
  const [s, setS] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Stats>("/programme/stats").then(setS).catch((e) => setError(e.message));
  }, []);
  if (error) return <div className="error">{error}</div>;
  if (!s) return <div className="muted">Loading…</div>;
  const max = Math.max(1, ...s.by_stage.map((x) => x.count));
  const scope = user?.scope?.districts?.length ? `Your area: ${user.scope.districts.length} district(s)` : ["admin", "programme_manager"].includes(user?.role ?? "") ? "All districts" : "Records you enrolled";
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Programme</h1><p className="muted small" style={{ margin: 0 }}>Enrolment and readiness – {scope}</p></div>
        {WRITE.includes(user?.role ?? "") && (
          <div className="row-gap">
            <Link className="btn" to="/admin/entrepreneurs/new">+ Enrol entrepreneur</Link>
            <Link className="btn secondary" to="/admin/groups?new=1">+ Enrol group</Link>
          </div>
        )}
      </div>
      <div className="kpis">
        <div><span>Entrepreneurs</span><b>{s.total}</b></div>
        <div><span>Women</span><b>{s.total ? Math.round((100 * s.women) / s.total) : 0}%</b></div>
        <div><span>Verified</span><b>{s.verified}</b></div>
        <div><span>Waiting for consent</span><b>{s.pending_consent}</b></div>
        <div><span>Readiness assessed</span><b>{s.assessed}</b></div>
        <div><span>Average readiness</span><b>{s.avg_readiness ?? "—"}</b></div>
        <div><span>Ready (70+)</span><b>{s.ready}</b></div>
        <div><span>Groups</span><b>{s.groups}</b></div>
      </div>
      <div className="grid-2">
        <div className="card">
          <h2>Lifecycle stage</h2>
          {s.by_stage.map((x) => (
            <Link key={x.stage} to={`/admin/entrepreneurs?stage=${x.stage}`} className="bar-row">
              <span>{x.stage}. {x.name}</span>
              <span className="bar"><span style={{ width: `${(100 * x.count) / max}%` }} /></span>
              <b>{x.count}</b>
            </Link>
          ))}
        </div>
        <div className="card">
          <h2>By district</h2>
          {s.by_district.length === 0 && <p className="muted small">No entrepreneurs yet.</p>}
          {s.by_district.slice(0, 12).map((x) => (
            <Link key={x.district} to={`/admin/entrepreneurs?district=${x.district}`} className="row-between small"><span>{x.name}</span><b>{x.count}</b></Link>
          ))}
          <h2 style={{ marginTop: 18 }}>How they joined</h2>
          {Object.entries(s.by_source).map(([k, v]) => <div key={k} className="row-between small"><span>{SOURCES[k] ?? k}</span><b>{v}</b></div>)}
        </div>
      </div>
    </div>
  );
}
