// Enterprise units being set up (M7). Units start when a loan is sanctioned (or an own-funds DPR is approved);
// approved DPRs without a unit are listed so staff can start set-up by hand.
import { Factory, PackageCheck, Rocket, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { StatTile } from "../../components/charts";
import { fmtDay, inr } from "../dpr/common";
import { UNIT_TAG, type UnitRow, useSetupMeta } from "./common";

type Res = { counts: Record<string, number>; rows: UnitRow[]; waiting: { dpr_id: number; code: string; unit_name: string; owner: string; loan: number; sanctioned: boolean }[] };

export default function Units() {
  const navigate = useNavigate();
  const meta = useSetupMeta();
  const [res, setRes] = useState<Res | null>(null);
  const [status, setStatus] = useState("setting_up");
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    const p = new URLSearchParams();
    if (status) p.set("status", status);
    if (q) p.set("q", q);
    api<Res>(`/setup/units?${p}`).then(setRes).catch(() => setRes({ counts: {}, rows: [], waiting: [] }));
  }, [status, q]);
  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
  }, [load]);
  const start = async (dpr_id: number) => {
    setError(null);
    try {
      const u = await api<{ id: number }>("/setup/units", { body: { dpr_id } });
      navigate(`/admin/setup/units/${u.id}`);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const c = res?.counts ?? {};
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Enterprise set-up</h1><p className="muted small" style={{ margin: 0 }}>Quotations, purchase, installation, registrations and the readiness check, until each unit is launched.</p></div>
      </div>
      <div className="stats">
        <StatTile icon={<Wrench />} tone="amber" label="Setting up" value={c.setting_up ?? 0} />
        <StatTile icon={<Rocket />} label="Launched" value={c.launched ?? 0} />
        <StatTile icon={<Factory />} tone="blue" label="Waiting to start" value={res?.waiting.length ?? 0} note="Approved DPRs without a unit" />
        <StatTile icon={<PackageCheck />} tone="violet" label="Paused / closed" value={(c.paused ?? 0) + (c.closed ?? 0)} />
      </div>
      {error && <div className="error">{error}</div>}
      {!!res?.waiting.length && (
        <div className="card stack">
          <h2 style={{ margin: 0 }}>Approved DPRs waiting for set-up</h2>
          {res.waiting.map((w) => (
            <div key={w.dpr_id} className="row-between">
              <span><b>{w.unit_name}</b> <span className="small muted">{w.owner} · {w.code} · loan {inr(w.loan)}</span>
                {w.sanctioned ? <span className="tag ok" style={{ marginLeft: 6 }}>sanctioned</span> : w.loan > 0 ? <span className="tag amber" style={{ marginLeft: 6 }}>loan not sanctioned</span> : null}</span>
              {meta?.can.write && <button className="btn small secondary" onClick={() => start(w.dpr_id)}>Start set-up</button>}
            </div>))}
        </div>
      )}
      <div className="filters row-gap">
        <input className="input" type="search" placeholder="Search unit, person, code" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
        <div className="tabs">{[["setting_up", "Setting up"], ["launched", "Launched"], ["", "All"]].map(([k, l]) => (
          <button key={k} className={status === k ? "on" : ""} onClick={() => setStatus(k)}>{l}</button>))}</div>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Unit</th><th>Entrepreneur / group</th><th>Purchases</th><th>Registrations</th><th>Readiness</th><th>Status</th></tr></thead>
          <tbody>
            {res?.rows.map((u) => (
              <tr key={u.id} className="clickable" onClick={() => navigate(`/admin/setup/units/${u.id}`)}>
                <td><b>{u.name}</b><div className="small muted">{u.code} · {u.model ?? "—"}</div></td>
                <td>{u.owner.name}<div className="small muted">{u.district_name}</div></td>
                <td className="small">{u.purchases.installed}/{u.purchases.total} installed<div className="muted">{inr(u.purchases.ordered_value)} ordered</div></td>
                <td className="small">{u.registrations.done}/{u.registrations.total}</td>
                <td style={{ minWidth: 120 }}><div className="seat-bar" aria-label={`${u.readiness.done} of ${u.readiness.total}`}>
                  <span style={{ width: `${(100 * u.readiness.done) / Math.max(1, u.readiness.total)}%` }} /></div>
                  <span className="small muted">{u.readiness.done} of {u.readiness.total}</span></td>
                <td><span className={`tag ${UNIT_TAG[u.status][0]}`}>{UNIT_TAG[u.status][1]}</span>{u.launch_date && <div className="small muted">{fmtDay(u.launch_date)}</div>}</td>
              </tr>))}
            {res && !res.rows.length && <tr><td colSpan={6} className="muted">No units {status ? `that are ${status.replace("_", " ")}` : "yet"}. A unit starts when a loan is sanctioned.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
