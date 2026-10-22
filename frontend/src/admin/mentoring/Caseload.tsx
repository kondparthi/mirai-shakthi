// Mentor caseload (M10): units a mentor looks after – review due, health, tickets, actions, visits and business alerts.
// Coordinators and managers see units in scope and can filter by mentor or find units without a mentor.
import { AlertTriangle, ClipboardCheck, HeartPulse, LifeBuoy, UserRoundX } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { StatTile } from "../../components/charts";
import { fmtDay } from "../dpr/common";
import { type CaseRow, HealthDot, monthLabel, useMentoringMeta } from "./common";

type Res = { rows: CaseRow[]; counts: { units: number; review_due: number; red: number; amber: number; tickets_open: number; no_mentor: number } };

export default function Caseload() {
  const { user } = useAuth();
  const meta = useMentoringMeta();
  const navigate = useNavigate();
  const [mentor, setMentor] = useState<string>("");
  const [res, setRes] = useState<Res | null>(null);
  const [only, setOnly] = useState<"" | "due" | "red" | "tickets">("");
  useEffect(() => {
    setRes(null);
    api<Res>(`/mentoring/caseload${mentor !== "" ? `?mentor_id=${mentor}` : ""}`).then(setRes).catch(() => setRes({ rows: [], counts: { units: 0, review_due: 0, red: 0, amber: 0, tickets_open: 0, no_mentor: 0 } }));
  }, [mentor]);
  const isMentor = user?.role === "mentor";
  const c = res?.counts;
  const rows = (res?.rows ?? []).filter((r) => !only || (only === "due" ? r.review_due : only === "red" ? r.health === "red" : r.tickets_open > 0));
  return (
    <div className="stack">
      <div className="welcome"><h1>{isMentor ? "My caseload" : "Mentoring caseload"}</h1>
        <p>{isMentor ? "Your units over their two years of handholding – monthly reviews, visits and support." : "Units in your districts, their mentors, reviews and support."}</p></div>
      <div className="stats">
        <StatTile icon={<ClipboardCheck />} label="Units" value={c?.units ?? "…"} note={`Review month ${monthLabel(res?.rows[0]?.review_month)}`} />
        <StatTile icon={<AlertTriangle />} tone="amber" label="Reviews due" value={c?.review_due ?? "…"} warn={!!c?.review_due} />
        <StatTile icon={<HeartPulse />} tone="red" label="Red / amber" value={c ? `${c.red} / ${c.amber}` : "…"} warn={!!c?.red} note="From the last review" />
        {isMentor ? <StatTile icon={<LifeBuoy />} tone="blue" label="Open tickets" value={c?.tickets_open ?? "…"} to="/admin/mentoring/tickets" />
          : <StatTile icon={<UserRoundX />} tone="violet" label="No mentor yet" value={c?.no_mentor ?? "…"} warn={!!c?.no_mentor} />}
      </div>
      <div className="filters row-gap">
        {!isMentor && meta && (
          <select className="input" style={{ width: 260 }} aria-label="Mentor" value={mentor} onChange={(e) => setMentor(e.target.value)}>
            <option value="">All mentors</option><option value="0">Without a mentor</option>
            {meta.mentors.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.units})</option>)}</select>)}
        <div className="tabs">{([["", "All"], ["due", "Review due"], ["red", "Red"], ["tickets", "Open tickets"]] as const).map(([k, l]) => (
          <button key={k} className={only === k ? "on" : ""} onClick={() => setOnly(k)}>{l}</button>))}</div>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Unit</th>{!isMentor && <th>Mentor</th>}<th>Month</th><th>Health</th><th>Review</th><th>Visit</th><th>Support</th><th>Alerts</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.unit.id} className="clickable" onClick={() => navigate(`/admin/mentoring/units/${r.unit.id}`)}>
                <td><b>{r.unit.name}</b><div className="small muted">{r.unit.owner} · {r.unit.district_name ?? ""}{r.unit.model ? ` · ${r.unit.model}` : ""}</div></td>
                {!isMentor && <td>{r.mentor?.name ?? <span className="tag amber">none</span>}</td>}
                <td className="small">{r.month_no ? `${r.month_no} of 24` : <span className="muted">{r.unit.status === "setting_up" ? "setting up" : "—"}</span>}</td>
                <td><HealthDot h={r.health} /></td>
                <td className="small">{r.review_due ? <span className="tag amber">{monthLabel(r.review_month)} due</span> : r.last_review ? monthLabel(r.last_review) : "—"}
                  {r.actions_overdue > 0 && <div className="neg">{r.actions_overdue} action{r.actions_overdue > 1 ? "s" : ""} late</div>}</td>
                <td className="small">{r.last_visit ? fmtDay(r.last_visit) : "—"}{r.next_visit && <div className="muted">next {fmtDay(r.next_visit)}</div>}</td>
                <td className="small">{r.tickets_open ? <>{r.tickets_open} open{r.tickets_high ? <span className="tag alert" style={{ marginLeft: 4 }}>{r.tickets_high} high</span> : null}
                  {r.tickets_overdue ? <div className="neg">{r.tickets_overdue} overdue</div> : null}</> : "—"}</td>
                <td className="small">{r.alerts.slice(0, 2).map((a) => <div key={a.code} className={`alert-line ${a.level}`}><AlertTriangle size={12} /> {a.text}</div>)}</td>
              </tr>))}
            {res && !rows.length && <tr><td colSpan={8} className="muted">No units here.</td></tr>}
            {!res && <tr><td colSpan={8} className="muted">Loading…</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
