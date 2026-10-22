// Mentoring dashboard (M10): units under handholding, reviews done for last month, health, tickets and resolution time,
// visits, mentor workload, training needs from reviews and closed handholding outcomes.
import { ClipboardCheck, HeartPulse, LifeBuoy, MapPin, Timer, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { Donut, HBars, Panel, StatTile } from "../../components/charts";
import { monthLabel, useMentoringMeta } from "./common";

type S = { units: number; mentored: number; no_mentor: number; review_month: string; reviews_due: number; reviewed: number; health: Record<string, number>;
  tickets: { open: number; overdue: number; high: number; resolved: number; avg_hours: number | null; rating: number | null; by_category: { code: string; label: string; open: number; total: number }[] };
  visits_month: number; by_mentor: { mentor_id: number; name: string; units: number; reviewed: number; red: number }[];
  training_needs: { review_id: number; unit: { id: number; name: string }; month: string; training: string[]; entrepreneur_id: number | null }[];
  closed: { count: number; outcomes: Record<string, number> } };

export default function MentoringDashboard() {
  const meta = useMentoringMeta();
  const [s, setS] = useState<S | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const load = () => api<S>("/mentoring/reports/summary").then(setS).catch(() => {});
  useEffect(() => { load(); }, []);
  if (!s) return <div className="muted">Loading…</div>;
  const hrs = s.tickets.avg_hours;
  return (
    <div className="stack">
      <div className="welcome"><h1>Mentoring & support</h1><p>Two years of handholding for every launched unit – monthly reviews, visits and support tickets.</p></div>
      <div className="stats six">
        <StatTile icon={<UsersRound />} label="Units in handholding" value={s.mentored} note={s.no_mentor ? `${s.no_mentor} without a mentor` : "All have a mentor"} warn={s.no_mentor > 0} to="/admin/mentoring" />
        <StatTile icon={<ClipboardCheck />} tone="blue" label={`Reviews for ${monthLabel(s.review_month)}`} value={`${s.reviewed}/${s.reviews_due}`} ratio={s.reviews_due ? s.reviewed / s.reviews_due : 0} />
        <StatTile icon={<HeartPulse />} tone="red" label="Red units" value={s.health.red ?? 0} warn={(s.health.red ?? 0) > 0} note={`${s.health.amber ?? 0} amber · ${s.health.green ?? 0} green`} />
        <StatTile icon={<LifeBuoy />} tone="amber" label="Open tickets" value={s.tickets.open} warn={s.tickets.overdue > 0} note={`${s.tickets.overdue} overdue · ${s.tickets.high} high`} to="/admin/mentoring/tickets" />
        <StatTile icon={<Timer />} tone="teal" label="Time to resolve" value={hrs == null ? "—" : hrs < 48 ? `${hrs} h` : `${(hrs / 24).toFixed(1)} d`} note={`${s.tickets.resolved} resolved${s.tickets.rating ? ` · ★ ${s.tickets.rating}` : ""}`} />
        <StatTile icon={<MapPin />} tone="violet" label="Field visits this month" value={s.visits_month} />
      </div>
      <div className="dash-grid">
        <Panel title="Health from the latest review" className="span-5">
          <Donut centerLabel="units" slices={[{ key: "green", label: "Green", value: s.health.green ?? 0, color: "#2f9e6e" }, { key: "amber", label: "Amber", value: s.health.amber ?? 0, color: "#e2a33a" }, { key: "red", label: "Red", value: s.health.red ?? 0, color: "#d0543b" }]} />
        </Panel>
        <Panel title="Tickets by category" className="span-7">
          <HBars empty="No tickets yet." rows={s.tickets.by_category.filter((c) => c.total).map((c) => ({ key: c.code, label: c.label, value: c.total, hint: `${c.open} open of ${c.total}`, color: "#d9873a" }))} />
        </Panel>
        <Panel title="Mentors" className="span-7">
          <div className="table-wrap"><table className="table compact">
            <thead><tr><th>Mentor</th><th className="num">Units</th><th className="num">Reviewed {monthLabel(s.review_month)}</th><th className="num">Red</th></tr></thead>
            <tbody>{s.by_mentor.map((m) => (
              <tr key={m.mentor_id}><td>{m.mentor_id ? m.name : <span className="tag amber">No mentor</span>}</td><td className="num">{m.units}</td>
                <td className="num">{m.reviewed}/{m.units}</td><td className={`num ${m.red ? "neg" : ""}`}>{m.red}</td></tr>))}
              {!s.by_mentor.length && <tr><td colSpan={4} className="muted">No units in handholding yet.</td></tr>}</tbody>
          </table></div>
        </Panel>
        <Panel title="Training asked for in reviews" className="span-5">
          {!s.training_needs.length && <p className="small muted" style={{ margin: 0 }}>Nothing pending.</p>}
          {s.training_needs.map((t) => (
            <div key={t.review_id} className="row-between small" style={{ padding: "4px 0" }}>
              <span><Link to={`/admin/mentoring/units/${t.unit.id}`}>{t.unit.name}</Link> · {t.training.map((x) => meta?.training.find((m) => m.code === x)?.label ?? x).join(", ")} <span className="muted">({monthLabel(t.month)})</span></span>
              {meta?.can.assign && <button className="btn ghost small" disabled={busy === t.review_id} onClick={async () => { setBusy(t.review_id); await api(`/mentoring/reviews/${t.review_id}/training-done`, { method: "POST" }); setBusy(null); load(); }}>Arranged</button>}
            </div>))}
        </Panel>
        {s.closed.count > 0 && (
          <Panel title={`Handholding completed (${s.closed.count})`} className="span-12">
            <HBars rows={Object.entries(s.closed.outcomes).filter(([, v]) => v).map(([k, v]) => ({ key: k, label: meta?.outcomes.find((o) => o.code === k)?.label ?? k, value: v }))} />
          </Panel>)}
      </div>
    </div>
  );
}
