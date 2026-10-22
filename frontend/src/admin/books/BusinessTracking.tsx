// Business tracking (M9): one line per launched unit for a month – sales, costs, profit, EMI status, how regularly they
// record – with rule-based alerts for the mentor (falling sales, rising costs, missed EMIs, no entries) and a review note.
import { AlertTriangle, BookOpenCheck, IndianRupee, NotebookPen, TrendingUp } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { Panel, StatTile } from "../../components/charts";
import { inr, inrShort } from "../dpr/common";

type Row = { id: number | null; unit: { id: number; code: string; name: string; owner: string; district_name: string | null; model: string | null };
  sales: number; expenses: number; profit: number; entries: number; days_recorded: number; emi_status: string; alerts: { code: string; level: string; text: string }[];
  submitted_by: string | null; note: string | null; reviewed: boolean; review_note: string | null };
type R = { month: string; live: boolean; units: number; totals: { sales: number; expenses: number; profit: number }; recording: number; flagged: number; rows: Row[] };
const EMI: Record<string, [string, string]> = { on_time: ["On time", "ok"], delayed: ["Delayed", "amber"], default: ["Overdue 3+", "red"], none: ["No loan / not due", "grey"] };
const SUB: Record<string, string> = { auto: "Auto", owner: "By entrepreneur", staff: "By staff" };

const monthKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
function lastMonths(n: number) {
  const out: string[] = [];
  const d = new Date(); d.setDate(1);
  for (let k = 0; k < n; k++) { out.push(monthKey(d)); d.setMonth(d.getMonth() - 1); }
  return out;
}
const label = (k: string) => new Date(`${k}-01`).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

export default function BusinessTracking() {
  const { user } = useAuth();
  const months = lastMonths(12);
  const [month, setMonth] = useState(months[1]);
  const [r, setR] = useState<R | null>(null);
  const [only, setOnly] = useState(false);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => api<R>(`/books/reports/months?month=${month}`).then(setR).catch((e) => setErr(e.message)), [month]);
  useEffect(() => { setR(null); load(); }, [load]);
  const rows = (r?.rows ?? []).filter((x) => !only || x.alerts.length);
  return (
    <div className="stack">
      <div className="welcome"><h1>Business tracking</h1><p>{["admin", "programme_manager"].includes(user?.role ?? "") ? "All districts" : "Your districts"} · launched units' monthly accounts and alerts for mentors.</p></div>
      <div className="row-gap">
        <select className="input" style={{ width: 220 }} aria-label="Month" value={month} onChange={(e) => setMonth(e.target.value)}>
          {months.map((m, k) => <option key={m} value={m}>{label(m)}{k === 0 ? " (so far)" : ""}</option>)}</select>
        <label className="check"><input type="checkbox" checked={only} onChange={(e) => setOnly(e.target.checked)} /> Only units with alerts</label>
      </div>
      {err && <div className="error">{err}</div>}
      {!r ? <div className="muted">Loading…</div> : (
        <>
          <div className="stats">
            <StatTile icon={<IndianRupee />} label="Sales" value={inrShort(r.totals.sales)} note={`${r.units} launched units`} />
            <StatTile icon={<TrendingUp />} tone="teal" label="Profit" value={inrShort(r.totals.profit)} note={`Costs ${inrShort(r.totals.expenses)}`} warn={r.totals.profit < 0} />
            <StatTile icon={<NotebookPen />} tone="blue" label="Keeping books" value={`${r.recording}/${r.units}`} ratio={r.units ? r.recording / r.units : 0} note="Units with entries this month" />
            <StatTile icon={<AlertTriangle />} tone="amber" label="Need attention" value={r.flagged} warn={r.flagged > 0} note={r.live ? "Alerts appear when the month closes" : "Units with alerts"} />
          </div>
          <Panel title={`${label(r.month)}${r.live ? " – running month, live figures" : ""}`}>
            <div className="table-wrap">
              <table className="table compact">
                <thead><tr><th>Unit</th><th className="num">Sales</th><th className="num">Costs</th><th className="num">Profit</th><th className="num">Days</th><th>EMI</th><th>Alerts and review</th></tr></thead>
                <tbody>
                  {rows.map((x) => (
                    <tr key={x.unit.id}>
                      <td><Link to={`/admin/books/units/${x.unit.id}`}><b>{x.unit.name}</b></Link><div className="small muted">{x.unit.owner} · {x.unit.district_name ?? ""}{x.unit.model ? ` · ${x.unit.model}` : ""}</div>
                        {x.submitted_by && <div className="small muted">{SUB[x.submitted_by] ?? x.submitted_by}</div>}</td>
                      <td className="num">{inr(x.sales)}</td><td className="num">{inr(x.expenses)}</td>
                      <td className={`num ${x.profit < 0 ? "neg" : ""}`}>{inr(x.profit)}</td>
                      <td className="num">{x.days_recorded}</td>
                      <td><span className={`tag ${EMI[x.emi_status]?.[1] ?? "grey"}`}>{EMI[x.emi_status]?.[0] ?? x.emi_status}</span></td>
                      <td style={{ minWidth: 260 }}>
                        {x.alerts.map((a) => <div key={a.code} className={`alert-line ${a.level}`}><AlertTriangle size={13} /> {a.text}</div>)}
                        {x.note && <div className="small">Entrepreneur: “{x.note}”</div>}
                        {x.review_note && <div className="small review-note"><BookOpenCheck size={13} /> {x.review_note}</div>}
                        {x.id && !x.reviewed && (
                          <div className="row-gap" style={{ marginTop: 4 }}>
                            <input className="input" style={{ flex: 1, minWidth: 120 }} aria-label={`Review note for ${x.unit.name}`} placeholder="Review / action" value={notes[x.id] ?? ""} onChange={(e) => setNotes({ ...notes, [x.id!]: e.target.value })} />
                            <button className="btn small" disabled={(notes[x.id] ?? "").trim().length < 2} onClick={async () => {
                              try { await api(`/books/months/${x.id}/review`, { body: { note: notes[x.id!] } }); load(); } catch (e) { setErr((e as Error).message); } }}>Reviewed</button>
                          </div>)}
                      </td>
                    </tr>))}
                  {!rows.length && <tr><td colSpan={7} className="muted">No launched units {only ? "with alerts " : ""}for this month.</td></tr>}
                </tbody>
              </table>
            </div>
          </Panel>
        </>)}
    </div>
  );
}
