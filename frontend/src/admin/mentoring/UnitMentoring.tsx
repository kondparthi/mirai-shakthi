// A unit's two years of handholding (M10): mentor and history, 24-month timeline, what the mentor should know from training
// and the plan, the books (M9), monthly reviews (Form 10.1), field visits with geo-tagged photos, support tickets (Form 10.2),
// growth plans (Form 10.3) and the final assessment.
import { Camera, ClipboardCheck, Flag, LifeBuoy, MapPin, Plus, Sprout, Trash2, UserRoundCog } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, apiUpload, apiUrl } from "../../api";
import { Field, Modal } from "../ui";
import { fmtDay, inr, today } from "../dpr/common";
import { HEALTH } from "../dpr/common";
import { HealthDot, type Ticket, TicketView, monthLabel, useMentoringMeta } from "./common";

type Action = { text: string; due: string | null; done: boolean; done_on?: string | null; by?: string };
type Review = { id: number; month: string; sales: number; expenses: number; profit: number; corrected: boolean; books: { sales: number; expenses: number; profit: number; entries: number; days_recorded: number } | null;
  repayment: string; jobs_family: number; jobs_hired: number; health: "green" | "amber" | "red"; scores: Record<string, number>; issues: string[]; actions: Action[];
  training: string[]; training_done: boolean; note: string | null; mentor: string | null; visit_id: number | null; at: string | null };
type Visit = { id: number; on: string; purpose: string; notes: string; lat: number | null; lng: number | null; distance_m: number | null;
  photos: { name: string; url: string; lat: number | null; lng: number | null; source: string | null; at: string }[]; next_visit: string | null; by: string | null };
type Growth = { id: number; goal: string; goal_label: string; target: string; target_date: string; support: string[]; status: string; progress: { on: string; text: string; by: string }[]; overdue: boolean };
type Page = {
  unit: { id: number; code: string; name: string; status: string; launch_date: string | null; district_name: string | null; place: string; model: string | null; lat: number | null; lng: number | null };
  mentorship: { id: number; mentor: { id: number; name: string } | null; status: string; start_date: string; end_date: string;
    history: { mentor_id: number | null; name?: string | null; from: string; to?: string; by: string; reason: string }[]; closed_on: string | null; outcome: string | null;
    final_score: number | null; final: Record<string, number | string | null> | null };
  timeline: { months: { n: number; month: string; past: boolean; health: string | null; reviewed: boolean; visits: number }[]; month_no: number; total: number; can_close?: boolean };
  profile: { entrepreneur: { id: number; name: string; mobile: string; education: string | null; stage: number } | null; group: { id: number; name: string } | null;
    training: { course: string; batch: string; result: string | null; quiz: number | null; business_plan: number | null; certificate: string | null }[];
    skill_gaps: string[]; skills: Record<string, number> | null; readiness: { score: number; gaps: string[]; strengths: string[] } | null;
    plan: { dpr_id: number | null; dpr_code: string | null; monthly_sales: number | null; monthly_profit: number | null; loan: number | null; emi: number | null; project_cost: number | null } };
  books: { months: { month: string; sales: number; expenses: number; profit: number; days_recorded: number; alerts: { code: string; level: string; text: string }[]; note: string | null }[];
    current: { month: string; sales: number; expenses: number; profit: number; entries: number; days_recorded: number } | null };
  reviews: Review[]; visits: Visit[]; tickets: Ticket[]; growth: Growth[];
  can: { write: boolean; assign: boolean; close: boolean };
};
type Draft = { month: string; books: { sales: number; expenses: number; profit: number; entries: number; days_recorded: number; frozen: boolean; alerts: { code: string; text: string }[]; note: string | null };
  sales: number; expenses: number; repayment: string; jobs_family: number; jobs_hired: number; health: string; issues: string[]; carry_actions: Action[];
  plan: { monthly_sales: number | null; monthly_profit: number | null }; existing: Review | null };

const SCORE_KEYS: [string, string][] = [["records", "Keeps records"], ["sales", "Sales & customers"], ["operations", "Running the unit"], ["money", "Money & repayment"]];
const PURPOSES: [string, string][] = [["review", "Monthly review"], ["support", "Support / problem"], ["audit", "Hygiene / safety audit"], ["training", "On-site training"], ["other", "Other"]];
const REPAY: [string, string][] = [["on_time", "On time"], ["delayed", "Delayed"], ["default", "Default"], ["none", "No loan / not due"]];
const SKILL: Record<string, string> = { costing: "Costing", bookkeeping: "Bookkeeping", marketing: "Marketing", digital: "Digital", banking: "Banking" };

function monthsSince(launch: string | null): string[] {
  const out: string[] = [];
  const d = new Date(); d.setDate(1);
  const stop = launch ? launch.slice(0, 7) : null;
  for (let k = 0; k < 24; k++) {
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (stop && key < stop) break;
    out.push(key); d.setMonth(d.getMonth() - 1);
  }
  return out;
}

function ReviewForm({ page, month: m0, onSaved, onClose }: { page: Page; month: string; onSaved: () => void; onClose: () => void }) {
  const meta = useMentoringMeta();
  const months = monthsSince(page.unit.launch_date);
  const [month, setMonth] = useState(m0);
  const [d, setD] = useState<Draft | null>(null);
  const [f, setF] = useState<{ sales: number; expenses: number; repayment: string; jobs_family: number; jobs_hired: number; health: string; scores: Record<string, number>;
    issues: string[]; actions: Action[]; training: string[]; note: string; visit_id: number | "" } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setD(null); setF(null);
    api<Draft>(`/mentoring/units/${page.unit.id}/review-draft?month=${month}`).then((r) => {
      setD(r);
      const e = r.existing;
      setF(e ? { sales: e.sales, expenses: e.expenses, repayment: e.repayment, jobs_family: e.jobs_family, jobs_hired: e.jobs_hired, health: e.health, scores: e.scores,
        issues: e.issues, actions: e.actions, training: e.training, note: e.note ?? "", visit_id: e.visit_id ?? "" }
        : { sales: r.sales, expenses: r.expenses, repayment: r.repayment, jobs_family: r.jobs_family, jobs_hired: r.jobs_hired, health: r.health, scores: {},
          issues: r.issues, actions: r.carry_actions.map((a) => ({ ...a, done: false })), training: [], note: "", visit_id: "" });
    }).catch((e) => setErr(e.message));
  }, [month, page.unit.id]);
  const toggle = (k: "issues" | "training", v: string) => f && setF({ ...f, [k]: f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v] });
  const corrected = d && f && (Math.abs(f.sales - d.books.sales) > 0.5 || Math.abs(f.expenses - d.books.expenses) > 0.5);
  const save = async () => {
    if (!f) return;
    setErr(null);
    try {
      await api(`/mentoring/units/${page.unit.id}/reviews`, { body: { month, ...f, note: f.note || null, visit_id: f.visit_id || null,
        actions: f.actions.filter((a) => a.text.trim().length >= 3).map((a) => ({ ...a, due: a.due || null })) } });
      onSaved();
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <Modal title={`Monthly review – ${page.unit.name}`} onClose={onClose} wide>
      <div className="stack">
        <Field label="Month"><select className="input" value={month} onChange={(e) => setMonth(e.target.value)}>{months.map((k) => <option key={k} value={k}>{monthLabel(k)}</option>)}</select></Field>
        {!d || !f ? <div className="muted">Loading…</div> : (
          <>
            <div className="notice soft">
              <b>From the books:</b> sales {inr(d.books.sales)} · expenses {inr(d.books.expenses)} · profit {inr(d.books.profit)} · {d.books.entries} entries on {d.books.days_recorded} days
              {d.books.frozen ? " · monthly summary" : " · month still open"}{d.plan.monthly_sales ? ` · plan: sales ${inr(d.plan.monthly_sales)} a month` : ""}
              {d.books.alerts.length > 0 && <div className="small">{d.books.alerts.map((a) => a.text).join(" · ")}</div>}
              {d.books.note && <div className="small">Entrepreneur: “{d.books.note}”</div>}
            </div>
            <div className="grid-3">
              <Field label="Sales (₹)"><input className="input" inputMode="decimal" value={f.sales} onChange={(e) => setF({ ...f, sales: Number(e.target.value.replace(/[^\d.]/g, "")) || 0 })} /></Field>
              <Field label="Expenses (₹)"><input className="input" inputMode="decimal" value={f.expenses} onChange={(e) => setF({ ...f, expenses: Number(e.target.value.replace(/[^\d.]/g, "")) || 0 })} /></Field>
              <Field label="Profit"><div className={`input readonly ${f.sales - f.expenses < 0 ? "neg" : ""}`}>{inr(f.sales - f.expenses)}</div></Field>
            </div>
            {corrected && <div className="small amber-text">Corrected from the books – say why in the note.</div>}
            <div className="grid-3">
              <Field label="Loan repayment"><select className="input" value={f.repayment} onChange={(e) => setF({ ...f, repayment: e.target.value })}>{REPAY.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
              <Field label="Jobs – family"><input className="input" type="number" min={0} value={f.jobs_family} onChange={(e) => setF({ ...f, jobs_family: Number(e.target.value) || 0 })} /></Field>
              <Field label="Jobs – hired"><input className="input" type="number" min={0} value={f.jobs_hired} onChange={(e) => setF({ ...f, jobs_hired: Number(e.target.value) || 0 })} /></Field>
            </div>
            <Field label="Health rating">
              <div className="chips health-chips">{(["green", "amber", "red"] as const).map((h) => <button key={h} type="button" className={`chip h-${h} ${f.health === h ? "on" : ""}`} onClick={() => setF({ ...f, health: h })}>{h[0].toUpperCase() + h.slice(1)}</button>)}</div></Field>
            <Field label="Mentor scores (1 = weak, 5 = strong)">
              <div className="score-grid">{SCORE_KEYS.map(([k, l]) => (
                <div key={k} className="score-row"><span>{l}</span><span className="score-dots">{[1, 2, 3, 4, 5].map((n) => (
                  <button key={n} type="button" aria-label={`${l} ${n}`} className={(f.scores[k] ?? 0) >= n ? "on" : ""} onClick={() => setF({ ...f, scores: { ...f.scores, [k]: n } })}>{n}</button>))}</span></div>))}</div></Field>
            <Field label="Issues"><div className="chips">{meta?.issues.map((i) => <button key={i.code} type="button" className={`chip ${f.issues.includes(i.code) ? "on" : ""}`} onClick={() => toggle("issues", i.code)}>{i.label}</button>)}</div></Field>
            <Field label="Actions agreed" hint={f.health === "red" ? "A red rating needs at least one action." : undefined}>
              <div className="stack" style={{ gap: 6 }}>
                {f.actions.map((a, i) => (
                  <div key={i} className="row-gap">
                    <input className="input" style={{ flex: 3, minWidth: 180 }} aria-label={`Action ${i + 1}`} value={a.text} placeholder="What will be done, by whom" onChange={(e) => setF({ ...f, actions: f.actions.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)) })} />
                    <input className="input" style={{ width: 160 }} type="date" aria-label={`Due ${i + 1}`} value={a.due ?? ""} onChange={(e) => setF({ ...f, actions: f.actions.map((x, j) => (j === i ? { ...x, due: e.target.value } : x)) })} />
                    <button className="btn ghost small danger" aria-label="Remove action" onClick={() => setF({ ...f, actions: f.actions.filter((_, j) => j !== i) })}><Trash2 size={14} /></button>
                  </div>))}
                <div><button type="button" className="btn ghost small" onClick={() => setF({ ...f, actions: [...f.actions, { text: "", due: null, done: false }] })}><Plus size={14} /> Action</button></div>
              </div></Field>
            <Field label="Training needed (sent to the training team)"><div className="chips">{meta?.training.map((i) => <button key={i.code} type="button" className={`chip ${f.training.includes(i.code) ? "on" : ""}`} onClick={() => toggle("training", i.code)}>{i.label}</button>)}</div></Field>
            <div className="grid-2">
              <Field label="Field visit (optional)"><select className="input" value={f.visit_id} onChange={(e) => setF({ ...f, visit_id: e.target.value ? Number(e.target.value) : "" })}>
                <option value="">—</option>{page.visits.map((v) => <option key={v.id} value={v.id}>{fmtDay(v.on)} · {PURPOSES.find(([k]) => k === v.purpose)?.[1]}</option>)}</select></Field>
            </div>
            <Field label="Note"><textarea className="input" rows={3} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
            {err && <div className="error">{err}</div>}
            <div><button className="btn" onClick={save}>{d.existing ? "Update review" : "Save review"}</button></div>
          </>)}
        {err && !f && <div className="error">{err}</div>}
      </div>
    </Modal>
  );
}

function VisitForm({ unitId, onSaved, onClose }: { unitId: number; onSaved: () => void; onClose: () => void }) {
  const [f, setF] = useState({ on: today(), purpose: "review", notes: "", next_visit: "" });
  const [pos, setPos] = useState<{ lat: number; lng: number } | null>(null);
  const [geoMsg, setGeoMsg] = useState<string>("");
  const [files, setFiles] = useState<File[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!navigator.geolocation) { setGeoMsg("Location is not available on this device – photo locations will be read from the camera if present."); return; }
    navigator.geolocation.getCurrentPosition((p) => { setPos({ lat: p.coords.latitude, lng: p.coords.longitude }); setGeoMsg(`Location ${p.coords.latitude.toFixed(5)}, ${p.coords.longitude.toFixed(5)} (±${Math.round(p.coords.accuracy)} m)`); },
      () => setGeoMsg("Location not shared – photo locations will be read from the camera if present."), { enableHighAccuracy: true, timeout: 8000 });
  }, []);
  const save = async () => {
    setBusy(true); setErr(null);
    try {
      const v = await api<Visit>(`/mentoring/units/${unitId}/visits`, { body: { ...f, next_visit: f.next_visit || null, lat: pos?.lat ?? null, lng: pos?.lng ?? null } });
      for (const file of files) {
        const fd = new FormData(); fd.append("file", file);
        if (pos) { fd.append("lat", String(pos.lat)); fd.append("lng", String(pos.lng)); }
        await apiUpload(`/mentoring/visits/${v.id}/photos`, fd);
      }
      onSaved();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <Modal title="Field visit" onClose={onClose}>
      <div className="stack">
        <div className="grid-2">
          <Field label="Date"><input className="input" type="date" max={today()} value={f.on} onChange={(e) => setF({ ...f, on: e.target.value })} /></Field>
          <Field label="Purpose"><select className="input" value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })}>{PURPOSES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        </div>
        <Field label="What you saw and discussed"><textarea className="input" rows={4} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
        <Field label="Photos (up to 8)" hint={geoMsg}>
          <input className="input" type="file" accept="image/*" capture="environment" multiple onChange={(e) => setFiles(Array.from(e.target.files ?? []).slice(0, 8))} /></Field>
        <Field label="Next visit (optional)"><input className="input" type="date" min={f.on} value={f.next_visit} onChange={(e) => setF({ ...f, next_visit: e.target.value })} /></Field>
        {err && <div className="error">{err}</div>}
        <div><button className="btn" disabled={busy || f.notes.trim().length < 5} onClick={save}>{busy ? "Saving…" : "Save visit"}</button></div>
      </div>
    </Modal>
  );
}

export default function UnitMentoring() {
  const { id } = useParams();
  const meta = useMentoringMeta();
  const [p, setP] = useState<Page | null>(null);
  const [tab, setTab] = useState<"overview" | "reviews" | "visits" | "support" | "growth">("overview");
  const [modal, setModal] = useState<"review" | "visit" | "ticket" | "growth" | "assign" | "close" | null>(null);
  const [reviewMonth, setReviewMonth] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [tk, setTk] = useState({ category: "equipment", description: "", priority: "medium", channel: "mentor" });
  const [gp, setGp] = useState({ goal: "increase_sales", target: "", target_date: "", support: [] as string[] });
  const [as, setAs] = useState<{ mentor_id: number | ""; reason: string }>({ mentor_id: "", reason: "" });
  const [cl, setCl] = useState({ outcome: "stable", final_score: 3, jobs: 1, note: "" });
  const [gnote, setGnote] = useState<Record<number, string>>({});
  const load = useCallback(() => api<Page>(`/mentoring/units/${id}`).then(setP).catch((e) => setErr(e.message)), [id]);
  useEffect(() => { load(); }, [load]);
  if (err && !p) return <div className="error">{err}</div>;
  if (!p || !meta) return <div className="muted">Loading…</div>;
  const ms = p.mentorship;
  const lastMonth = (() => { const d = new Date(); d.setDate(0); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; })();
  const running = ["launched", "paused"].includes(p.unit.status);
  const done = (fn: () => void) => () => { setModal(null); fn(); };
  const post = async (path: string, body: object, method = "POST") => {
    setErr(null);
    try { await api(path, { method, body }); setModal(null); load(); } catch (e) { setErr((e as Error).message); }
  };
  const activeTickets = p.tickets.filter((t) => t.status === "open" || t.status === "in_progress").length;
  const owner = p.profile.entrepreneur;

  return (
    <div className="stack">
      <Link to="/admin/mentoring" className="small">← Caseload</Link>
      <div className="row-between wrap">
        <div>
          <h1 style={{ margin: 0 }}>{p.unit.name}</h1>
          <div className="small muted">{p.unit.code} · {owner ? <Link to={`/admin/entrepreneurs/${owner.id}`}>{owner.name}</Link> : p.profile.group?.name} · {p.unit.model ?? "—"} · {p.unit.place}{p.unit.district_name ? `, ${p.unit.district_name}` : ""}
            {p.unit.launch_date ? ` · launched ${fmtDay(p.unit.launch_date)}` : " · setting up"} · <Link to={`/admin/setup/units/${p.unit.id}`}>Unit</Link> · <Link to={`/admin/books/units/${p.unit.id}`}>Accounts</Link></div>
        </div>
        <div className="row-gap">
          {p.can.write && running && <button className="btn" onClick={() => { setReviewMonth(lastMonth >= (p.unit.launch_date ?? "").slice(0, 7) ? lastMonth : (p.unit.launch_date ?? today()).slice(0, 7)); setModal("review"); }}><ClipboardCheck size={16} /> Monthly review</button>}
          {p.can.write && <button className="btn secondary" onClick={() => setModal("visit")}><MapPin size={16} /> Field visit</button>}
          {ms.status === "active" && <button className="btn secondary" onClick={() => setModal("ticket")}><LifeBuoy size={16} /> Support ticket</button>}
        </div>
      </div>
      {err && <div className="error">{err}</div>}

      <div className="card mentor-strip">
        <div><small>Mentor</small><b>{ms.mentor?.name ?? <span className="tag amber">Not assigned</span>}</b>
          {p.can.assign && ms.status === "active" && <button className="link-btn small" onClick={() => { setAs({ mentor_id: ms.mentor?.id ?? "", reason: "" }); setModal("assign"); }}><UserRoundCog size={12} /> {ms.mentor ? "Change" : "Assign"}</button>}</div>
        <div><small>Handholding</small><b>{ms.status === "closed" ? `Closed ${fmtDay(ms.closed_on)}` : p.timeline.month_no ? `Month ${p.timeline.month_no} of ${p.timeline.total}` : "Starts at launch"}</b>
          <span className="small muted">{fmtDay(ms.start_date)} – {fmtDay(ms.end_date)}</span></div>
        <div><small>Last review</small><b>{p.reviews[0] ? <HealthDot h={p.reviews[0].health} /> : "—"}</b><span className="small muted">{p.reviews[0] ? monthLabel(p.reviews[0].month) : ""}</span></div>
        <div><small>Open tickets</small><b>{activeTickets}</b></div>
        {p.can.close && <div><button className="btn small secondary" onClick={() => setModal("close")}><Flag size={14} /> Final assessment</button></div>}
      </div>

      <div className="tl24" role="img" aria-label="24-month handholding timeline">
        {p.timeline.months.map((m) => (
          <div key={m.month} className={`tl24-m ${m.past ? "past" : ""} ${m.health ? `h-${m.health}` : ""} ${m.n === p.timeline.month_no ? "now" : ""}`} title={`Month ${m.n} · ${monthLabel(m.month)}${m.health ? ` · ${m.health}` : m.past ? " · not reviewed" : ""}${m.visits ? ` · ${m.visits} visit(s)` : ""}`}>
            <span>{m.n}</span>{m.visits > 0 && <i />}
          </div>))}
      </div>

      <div className="tabs">{([["overview", "Overview"], ["reviews", `Reviews (${p.reviews.length})`], ["visits", `Visits (${p.visits.length})`], ["support", `Support (${p.tickets.length})`], ["growth", `Growth (${p.growth.length})`]] as const).map(([k, l]) => (
        <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>))}</div>

      {tab === "overview" && (
        <div className="dash-grid">
          <div className="card stack span-6">
            <h3 style={{ margin: 0 }}>From training and the plan</h3>
            {p.profile.training.map((t) => (
              <div key={t.batch} className="small"><b>{t.course}</b> · {t.batch} · {t.result ?? "in training"}{t.quiz != null ? ` · quiz ${t.quiz}%` : ""}{t.business_plan != null ? ` · business plan ${t.business_plan}/10` : ""}{t.certificate ? ` · ${t.certificate}` : ""}</div>))}
            {!p.profile.training.length && <div className="small muted">No training record.</div>}
            {p.profile.skill_gaps.length > 0 && <div className="small"><b>Skill gaps:</b> {p.profile.skill_gaps.map((s) => SKILL[s] ?? s).join(", ")}</div>}
            {p.profile.readiness && <div className="small"><b>Readiness {p.profile.readiness.score}/100</b>{p.profile.readiness.gaps?.length ? ` · gaps: ${p.profile.readiness.gaps.join(", ")}` : ""}</div>}
            {p.profile.plan.dpr_code && <div className="small"><b>Plan</b> <Link to={`/admin/finance/dprs/${p.profile.plan.dpr_id}`}>{p.profile.plan.dpr_code}</Link> · cost {inr(p.profile.plan.project_cost)} · loan {inr(p.profile.plan.loan)} · EMI {inr(p.profile.plan.emi)}
              {p.profile.plan.monthly_sales ? ` · expected sales ${inr(p.profile.plan.monthly_sales)} a month` : ""}</div>}
          </div>
          <div className="card stack span-6">
            <h3 style={{ margin: 0 }}>Books (M9)</h3>
            {p.books.current && <div className="small">This month so far: sales <b>{inr(p.books.current.sales)}</b> · expenses {inr(p.books.current.expenses)} · profit <b className={p.books.current.profit < 0 ? "neg" : ""}>{inr(p.books.current.profit)}</b> · {p.books.current.days_recorded} days recorded</div>}
            <table className="table compact">
              <thead><tr><th>Month</th><th className="num">Sales</th><th className="num">Expenses</th><th className="num">Profit</th><th className="num">Days</th></tr></thead>
              <tbody>{p.books.months.map((m) => (
                <tr key={m.month}><td>{monthLabel(m.month)}{m.alerts.length > 0 && <span className="tag amber" style={{ marginLeft: 6 }} title={m.alerts.map((a) => a.text).join("\n")}>{m.alerts.length}</span>}</td>
                  <td className="num">{inr(m.sales)}</td><td className="num">{inr(m.expenses)}</td><td className={`num ${m.profit < 0 ? "neg" : ""}`}>{inr(m.profit)}</td><td className="num">{m.days_recorded}</td></tr>))}
                {!p.books.months.length && <tr><td colSpan={5} className="muted">No finished months yet.</td></tr>}</tbody>
            </table>
          </div>
          <div className="card stack span-6">
            <h3 style={{ margin: 0 }}>Open actions</h3>
            {p.reviews.flatMap((r) => r.actions.map((a, i) => ({ r, a, i }))).filter(({ a }) => !a.done).slice(0, 8).map(({ r, a, i }) => (
              <label key={`${r.id}-${i}`} className="check"><input type="checkbox" disabled={!p.can.write} onChange={async () => { await api(`/mentoring/reviews/${r.id}/actions/${i}`, { method: "PUT", body: { done: true } }); load(); }} />
                <span>{a.text}<span className={`small ${a.due && a.due < today() ? "neg" : "muted"}`}> · {a.due ? `due ${fmtDay(a.due)}` : "no date"} · {monthLabel(r.month)}</span></span></label>))}
            {!p.reviews.some((r) => r.actions.some((a) => !a.done)) && <div className="small muted">Nothing open.</div>}
          </div>
          <div className="card stack span-6">
            <h3 style={{ margin: 0 }}>Mentor history</h3>
            {ms.history.map((h, i) => <div key={i} className="small">{h.name ?? (h.mentor_id ? meta.mentors.find((m) => m.id === h.mentor_id)?.name : null) ?? "No mentor"} · from {fmtDay(h.from)}{h.to ? ` to ${fmtDay(h.to)}` : ""} · {h.reason || "—"} <span className="muted">({h.by})</span></div>)}
            {ms.status === "closed" && ms.final && (
              <div className="notice ok-notice small"><b>Final assessment:</b> {meta.outcomes.find((o) => o.code === ms.outcome)?.label} · score {ms.final_score}/5 · {String(ms.final.jobs)} jobs
                {ms.final.sales_first3 != null && ` · sales ${inr(Number(ms.final.sales_first3))} → ${inr(Number(ms.final.sales_last3))} a month`}<div>{String(ms.final.note)}</div></div>)}
          </div>
        </div>)}

      {tab === "reviews" && (
        <div className="stack">
          {!p.reviews.length && <div className="card muted">No reviews yet.{running ? " Reviews are monthly, built on the unit's books." : ""}</div>}
          {p.reviews.map((r) => (
            <div key={r.id} className="card stack review-card">
              <div className="row-between"><b>{monthLabel(r.month)}</b><span className="row-gap"><HealthDot h={r.health} />{p.can.write && <button className="btn ghost small" onClick={() => { setReviewMonth(r.month); setModal("review"); }}>Edit</button>}</span></div>
              <div className="small">Sales {inr(r.sales)} · expenses {inr(r.expenses)} · profit <b className={r.profit < 0 ? "neg" : ""}>{inr(r.profit)}</b>{r.corrected && r.books ? <span className="amber-text"> · corrected (books: {inr(r.books.sales)} / {inr(r.books.expenses)})</span> : ""}
                {" · "}repayment <span className={`tag ${HEALTH[r.repayment]?.[0] ?? "grey"}`}>{REPAY.find(([k]) => k === r.repayment)?.[1]}</span> · jobs {r.jobs_family} family + {r.jobs_hired} hired</div>
              {Object.keys(r.scores).length > 0 && <div className="small muted">{SCORE_KEYS.filter(([k]) => r.scores[k]).map(([k, l]) => `${l} ${r.scores[k]}/5`).join(" · ")}</div>}
              {r.issues.length > 0 && <div className="row-gap">{r.issues.map((i) => <span key={i} className="tag grey">{meta.issues.find((x) => x.code === i)?.label ?? i}</span>)}</div>}
              {r.actions.map((a, i) => <div key={i} className={`small ${a.done ? "muted" : ""}`}>{a.done ? "✓" : "○"} {a.text}{a.due ? ` · due ${fmtDay(a.due)}` : ""}{a.done && a.by ? ` · done by ${a.by}` : ""}</div>)}
              {r.training.length > 0 && <div className="small">Training: {r.training.map((x) => meta.training.find((t) => t.code === x)?.label ?? x).join(", ")} {r.training_done ? <span className="tag ok">arranged</span> : <span className="tag amber">to arrange</span>}</div>}
              {r.note && <div className="small" style={{ whiteSpace: "pre-wrap" }}>{r.note}</div>}
              <div className="small muted">{r.mentor} · {r.at ? fmtDay(r.at) : ""}</div>
            </div>))}
        </div>)}

      {tab === "visits" && (
        <div className="stack">
          {!p.visits.length && <div className="card muted">No field visits yet.</div>}
          {p.visits.map((v) => (
            <div key={v.id} className="card stack">
              <div className="row-between"><b>{fmtDay(v.on)} · {PURPOSES.find(([k]) => k === v.purpose)?.[1]}</b>
                <span className="small muted">{v.by}{v.lat != null ? <> · <a href={`https://maps.google.com/?q=${v.lat},${v.lng}`} target="_blank" rel="noreferrer"><MapPin size={12} /> {v.lat.toFixed(4)}, {v.lng?.toFixed(4)}</a></> : " · no location"}
                  {v.distance_m != null && <span className={v.distance_m > 1000 ? "neg" : ""}> · {v.distance_m < 1000 ? `${Math.round(v.distance_m)} m` : `${(v.distance_m / 1000).toFixed(1)} km`} from the unit</span>}</span></div>
              <div className="small" style={{ whiteSpace: "pre-wrap" }}>{v.notes}</div>
              {v.photos.length > 0 && <div className="photo-row">{v.photos.map((ph) => (
                <a key={ph.name} href={apiUrl(ph.url)} target="_blank" rel="noreferrer" className="geo-photo"><img src={apiUrl(ph.url)} alt={`Visit photo ${fmtDay(v.on)}`} />
                  <small>{ph.lat != null ? <><MapPin size={10} /> {ph.source === "exif" ? "camera" : "phone"}</> : "no location"}</small></a>))}</div>}
              {p.can.write && (
                <label className="btn ghost small" style={{ alignSelf: "flex-start" }}><Camera size={14} /> Add photo
                  <input type="file" accept="image/*" capture="environment" hidden onChange={async (e) => {
                    const file = e.target.files?.[0]; if (!file) return;
                    const send = async (lat?: number, lng?: number) => { const fd = new FormData(); fd.append("file", file); if (lat != null) { fd.append("lat", String(lat)); fd.append("lng", String(lng)); }
                      try { await apiUpload(`/mentoring/visits/${v.id}/photos`, fd); load(); } catch (x) { setErr((x as Error).message); } };
                    if (navigator.geolocation) navigator.geolocation.getCurrentPosition((g) => send(g.coords.latitude, g.coords.longitude), () => send(), { timeout: 6000 }); else send();
                  }} /></label>)}
              {v.next_visit && <div className="small muted">Next visit {fmtDay(v.next_visit)}</div>}
            </div>))}
        </div>)}

      {tab === "support" && (
        <div className="stack">
          {!p.tickets.length && <div className="card muted">No support tickets.</div>}
          {p.tickets.map((t) => <div key={t.id} className="card"><TicketView t={t} meta={meta} onChange={() => load()} /></div>)}
        </div>)}

      {tab === "growth" && (
        <div className="stack">
          {p.can.write && running && <div><button className="btn secondary" onClick={() => setModal("growth")}><Sprout size={16} /> New growth plan</button></div>}
          {!p.growth.length && <div className="card muted">No growth plans yet.</div>}
          {p.growth.map((g) => (
            <div key={g.id} className="card stack">
              <div className="row-between"><b>{g.goal_label}</b><span className={`tag ${g.status === "achieved" ? "ok" : g.status === "dropped" ? "grey" : g.overdue ? "alert" : "amber"}`}>{g.status === "active" && g.overdue ? "past target date" : g.status}</span></div>
              <div className="small">{g.target} · by {fmtDay(g.target_date)}{g.support.length ? ` · support: ${g.support.map((s) => meta.support.find((x) => x.code === s)?.label ?? s).join(", ")}` : ""}</div>
              {g.progress.map((x, i) => <div key={i} className="small muted">{fmtDay(x.on)} · {x.text} ({x.by})</div>)}
              {p.can.write && g.status === "active" && (
                <div className="row-gap">
                  <input className="input" style={{ flex: 1, minWidth: 160 }} aria-label="Progress note" placeholder="Progress note" value={gnote[g.id] ?? ""} onChange={(e) => setGnote({ ...gnote, [g.id]: e.target.value })} />
                  <button className="btn small ghost" disabled={!(gnote[g.id] ?? "").trim()} onClick={() => post(`/mentoring/growth/${g.id}`, { note: gnote[g.id] }, "PUT").then(() => setGnote({ ...gnote, [g.id]: "" }))}>Add</button>
                  <button className="btn small" onClick={() => post(`/mentoring/growth/${g.id}`, { status: "achieved", note: gnote[g.id] || null }, "PUT")}>Achieved</button>
                  <button className="btn small ghost" onClick={() => post(`/mentoring/growth/${g.id}`, { status: "dropped", note: gnote[g.id] || null }, "PUT")}>Drop</button>
                </div>)}
            </div>))}
        </div>)}

      {modal === "review" && <ReviewForm page={p} month={reviewMonth} onClose={() => setModal(null)} onSaved={done(load)} />}
      {modal === "visit" && <VisitForm unitId={p.unit.id} onClose={() => setModal(null)} onSaved={done(load)} />}
      {modal === "ticket" && (
        <Modal title="Support ticket" onClose={() => setModal(null)}>
          <div className="stack">
            <div className="grid-2">
              <Field label="Category" hint="Assigned automatically by category"><select className="input" value={tk.category} onChange={(e) => setTk({ ...tk, category: e.target.value })}>{meta.categories.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}</select></Field>
              <Field label="Priority"><select className="input" value={tk.priority} onChange={(e) => setTk({ ...tk, priority: e.target.value })}><option value="high">High – 2 days</option><option value="medium">Medium – 5 days</option><option value="low">Low – 10 days</option></select></Field>
              <Field label="How it came in"><select className="input" value={tk.channel} onChange={(e) => setTk({ ...tk, channel: e.target.value })}><option value="mentor">Mentor</option><option value="call">Phone call</option><option value="navigator">Field navigator</option><option value="review">Monthly review</option></select></Field>
            </div>
            <Field label="Problem"><textarea className="input" rows={4} value={tk.description} onChange={(e) => setTk({ ...tk, description: e.target.value })} /></Field>
            <div><button className="btn" disabled={tk.description.trim().length < 5} onClick={() => post(`/mentoring/units/${p.unit.id}/tickets`, tk).then(() => { setTk({ ...tk, description: "" }); setTab("support"); })}>Raise ticket</button></div>
          </div>
        </Modal>)}
      {modal === "growth" && (
        <Modal title="Growth plan" onClose={() => setModal(null)}>
          <div className="stack">
            <Field label="Goal"><select className="input" value={gp.goal} onChange={(e) => setGp({ ...gp, goal: e.target.value })}>{meta.goals.map((g) => <option key={g.code} value={g.code}>{g.label}</option>)}</select></Field>
            <div className="grid-2">
              <Field label="Target"><input className="input" value={gp.target} placeholder="e.g. ₹60,000 sales a month" onChange={(e) => setGp({ ...gp, target: e.target.value })} /></Field>
              <Field label="By"><input className="input" type="date" min={today()} value={gp.target_date} onChange={(e) => setGp({ ...gp, target_date: e.target.value })} /></Field>
            </div>
            <Field label="Support needed"><div className="chips">{meta.support.map((s) => <button key={s.code} type="button" className={`chip ${gp.support.includes(s.code) ? "on" : ""}`}
              onClick={() => setGp({ ...gp, support: gp.support.includes(s.code) ? gp.support.filter((x) => x !== s.code) : [...gp.support, s.code] })}>{s.label}</button>)}</div></Field>
            <div><button className="btn" disabled={gp.target.trim().length < 3 || !gp.target_date} onClick={() => post(`/mentoring/units/${p.unit.id}/growth`, gp).then(() => setTab("growth"))}>Save plan</button></div>
          </div>
        </Modal>)}
      {modal === "assign" && (
        <Modal title="Mentor" onClose={() => setModal(null)}>
          <div className="stack">
            <Field label="Mentor"><select className="input" value={as.mentor_id} onChange={(e) => setAs({ ...as, mentor_id: e.target.value ? Number(e.target.value) : "" })}>
              <option value="">— none —</option>{meta.mentors.map((m) => <option key={m.id} value={m.id}>{m.name} · {m.units} units</option>)}</select></Field>
            <Field label="Reason"><input className="input" value={as.reason} placeholder="e.g. mentor moved district" onChange={(e) => setAs({ ...as, reason: e.target.value })} /></Field>
            <div><button className="btn" onClick={() => post(`/mentoring/units/${p.unit.id}/mentor`, { mentor_id: as.mentor_id || null, reason: as.reason || null }, "PUT")}>Save</button></div>
          </div>
        </Modal>)}
      {modal === "close" && (
        <Modal title="Final assessment – close handholding" onClose={() => setModal(null)}>
          <div className="stack">
            <Field label="Where the unit is now"><select className="input" value={cl.outcome} onChange={(e) => setCl({ ...cl, outcome: e.target.value })}>{meta.outcomes.map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}</select></Field>
            <div className="grid-2">
              <Field label="Overall score (1–5)"><select className="input" value={cl.final_score} onChange={(e) => setCl({ ...cl, final_score: Number(e.target.value) })}>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></Field>
              <Field label="Jobs now"><input className="input" type="number" min={0} value={cl.jobs} onChange={(e) => setCl({ ...cl, jobs: Number(e.target.value) || 0 })} /></Field>
            </div>
            <Field label="Assessment" hint="What changed over the two years and what the entrepreneur should keep doing."><textarea className="input" rows={4} value={cl.note} onChange={(e) => setCl({ ...cl, note: e.target.value })} /></Field>
            <div><button className="btn" disabled={cl.note.trim().length < 10} onClick={() => post(`/mentoring/units/${p.unit.id}/close`, cl)}>Close handholding</button></div>
          </div>
        </Modal>)}
    </div>
  );
}
