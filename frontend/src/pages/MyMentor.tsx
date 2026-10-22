// Entrepreneur app – "My mentor & support" (M10): who my mentor is (call / WhatsApp), where I am in the two years of
// handholding, the actions we agreed, asking for help (Form 10.2 – speak or type, add a photo), and my growth plans.
import { Camera, LifeBuoy, MessageCircle, Phone, Star } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUpload, apiUrl } from "../api";
import MicButton from "../components/MicButton";
import { useLang } from "../i18n";

type Act = { i: number; text: string; due: string | null; done: boolean };
type Tk = { id: number; code: string; category_label: string; description: string; photo_url: string | null; priority: string; status: string;
  assigned_to: { name: string } | null; due_by: string | null; resolution: string | null; rating: number | null; created_at: string | null;
  events: { at: string; by: string; kind: string; text: string }[] };
type UnitBlock = { unit: { id: number; name: string; code: string; status: string };
  mentor: { name: string; mobile: string | null; whatsapp: string | null } | null;
  handholding: { status: string; month_no: number; total: number; end: string; outcome: string | null }; next_visit: string | null;
  reviews: { id: number; month: string; health: string; note: string | null; actions: Act[] }[]; tickets: Tk[];
  growth: { id: number; goal_label: string; target: string; target_date: string; status: string; overdue: boolean }[] };
type Me = { units: UnitBlock[]; categories: { code: string; label: string }[] };

const L = {
  title: ["My mentor & support", "నా మెంటార్ & సహాయం"], back: ["Programme", "కార్యక్రమం"], none: ["Your mentor is assigned when your enterprise is set up.", "మీ వ్యాపారం ఏర్పాటైనప్పుడు మెంటార్‌ను కేటాయిస్తారు."],
  mentor: ["Your mentor", "మీ మెంటార్"], noMentor: ["A mentor will be assigned soon.", "త్వరలో మెంటార్‌ను కేటాయిస్తారు."], call: ["Call", "ఫోన్"], wa: ["WhatsApp", "వాట్సాప్"],
  month: ["Month", "నెల"], of: ["of", "లో"], startsAtLaunch: ["Two years of support start when your business is launched.", "మీ వ్యాపారం ప్రారంభమైనప్పటి నుండి రెండు సంవత్సరాల సహాయం."],
  done2: ["Handholding complete", "సహాయ కాలం పూర్తయింది"], nextVisit: ["Next visit", "తదుపరి సందర్శన"],
  actions: ["What we agreed", "మనం అనుకున్న పనులు"], noActions: ["No open actions.", "చేయవలసిన పనులు లేవు."], due: ["by", "తేదీ"],
  help: ["Ask for help", "సహాయం అడగండి"], cat: ["What is it about?", "దేని గురించి?"], prio: ["How urgent?", "ఎంత అత్యవసరం?"],
  high: ["Urgent – business stopped", "అత్యవసరం – వ్యాపారం ఆగిపోయింది"], medium: ["Soon", "త్వరలో"], low: ["When you can", "వీలున్నప్పుడు"],
  desc: ["Tell us the problem", "సమస్య చెప్పండి"], photo: ["Add a photo", "ఫోటో జోడించండి"], send: ["Send", "పంపండి"], sent: ["Sent. We will get back to you.", "పంపబడింది. మేము మిమ్మల్ని సంప్రదిస్తాము."],
  requests: ["My requests", "నా అభ్యర్థనలు"], noReq: ["No requests yet.", "ఇంకా అభ్యర్థనలు లేవు."], with: ["With", "ఎవరి దగ్గర"],
  open: ["Received", "అందింది"], in_progress: ["Being worked on", "పని జరుగుతోంది"], resolved: ["Solved – please check", "పరిష్కరించారు – చూడండి"], closed: ["Closed", "ముగిసింది"],
  fixed: ["Yes, it is fixed", "అవును, సరైంది"], notFixed: ["Not fixed yet", "ఇంకా సరి కాలేదు"], whatWrong: ["What is still wrong?", "ఇంకా ఏమి సరిగా లేదు?"], rate: ["How was the help?", "సహాయం ఎలా ఉంది?"],
  growth: ["My growth plans", "నా వృద్ధి ప్రణాళికలు"], achieved: ["achieved", "సాధించారు"],
  green: ["Doing well", "బాగుంది"], amber: ["Needs attention", "శ్రద్ధ అవసరం"], red: ["Needs help", "సహాయం అవసరం"],
};

function TicketCard({ t, i, onChange }: { t: Tk; i: number; onChange: () => void }) {
  const [why, setWhy] = useState("");
  const [ask, setAsk] = useState(false);
  const [stars, setStars] = useState(0);
  const st = (L as Record<string, string[]>)[t.status]?.[i] ?? t.status;
  return (
    <div className={`order-card ticket-${t.status}`}>
      <div className="row-between"><b>{t.category_label}</b><span className={`tag ${t.status === "resolved" ? "ok" : t.status === "closed" ? "grey" : "amber"}`}>{st}</span></div>
      <div className="small" style={{ whiteSpace: "pre-wrap" }}>{t.description}</div>
      {t.photo_url && <img className="ticket-photo" src={apiUrl(t.photo_url)} alt="" />}
      <div className="small muted">{t.code}{t.assigned_to ? ` · ${L.with[i]}: ${t.assigned_to.name}` : ""}{t.created_at ? ` · ${new Date(t.created_at).toLocaleDateString()}` : ""}</div>
      {t.resolution && <div className="notice ok-notice small">{t.resolution}</div>}
      {t.status === "resolved" && (
        <div className="stack" style={{ gap: 6 }}>
          <div className="small">{L.rate[i]}</div>
          <div className="stars">{[1, 2, 3, 4, 5].map((n) => <button key={n} aria-label={`${n}`} onClick={() => setStars(n)}><Star size={26} fill={n <= stars ? "#e8a317" : "none"} color="#e8a317" /></button>)}</div>
          <div className="row-gap">
            <button className="btn small" disabled={!stars} onClick={async () => { await api(`/mentoring/tickets/${t.id}/rate`, { body: { rating: stars } }); onChange(); }}>{L.fixed[i]}</button>
            <button className="btn small ghost" onClick={() => setAsk(!ask)}>{L.notFixed[i]}</button>
          </div>
          {ask && <div className="row-gap"><input className="input" style={{ flex: 1, minWidth: 0 }} aria-label={L.whatWrong[i]} placeholder={L.whatWrong[i]} value={why} onChange={(e) => setWhy(e.target.value)} />
            <button className="btn small" disabled={why.trim().length < 2} onClick={async () => { await api(`/mentoring/tickets/${t.id}/status`, { body: { status: "open", note: why } }); onChange(); }}>{L.send[i]}</button></div>}
        </div>)}
      {t.rating ? <div className="small">{"★".repeat(t.rating)}</div> : null}
    </div>
  );
}

export default function MyMentor() {
  const { lang } = useLang();
  const i = lang === "te" ? 1 : 0;
  const [me, setMe] = useState<Me | null>(null);
  const [uid, setUid] = useState<number | null>(null);
  const [f, setF] = useState({ category: "equipment", priority: "medium", description: "" });
  const [photo, setPhoto] = useState<File | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const load = useCallback(() => api<Me>(`/mentoring/me?lang=${lang}`).then((r) => { setMe(r); setUid((c) => c ?? r.units[0]?.unit.id ?? null); }).catch((e) => setMsg({ ok: false, text: e.message })), [lang]);
  useEffect(() => { load(); }, [load]);
  if (!me) return msg ? <div className="error">{msg.text}</div> : <div className="muted">…</div>;
  const b = me.units.find((x) => x.unit.id === uid);
  const actions = (b?.reviews ?? []).flatMap((r) => r.actions.filter((a) => !a.done).map((a) => ({ ...a, rid: r.id })));
  const send = async () => {
    if (!b) return;
    setBusy(true); setMsg(null);
    try {
      const t = await api<Tk>(`/mentoring/units/${b.unit.id}/tickets`, { body: f });
      if (photo) { const fd = new FormData(); fd.append("file", photo); await apiUpload(`/mentoring/tickets/${t.id}/photo`, fd).catch(() => {}); }
      setF({ ...f, description: "" }); setPhoto(null); setMsg({ ok: true, text: L.sent[i] }); load();
    } catch (e) { setMsg({ ok: false, text: (e as Error).message }); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <Link to="/programme" className="small">← {L.back[i]}</Link>
      <h1 style={{ margin: 0 }}>{L.title[i]}</h1>
      {!me.units.length && <div className="card">{L.none[i]}</div>}
      {me.units.length > 1 && <select className="input" aria-label="Unit" value={uid ?? ""} onChange={(e) => setUid(Number(e.target.value))}>{me.units.map((u) => <option key={u.unit.id} value={u.unit.id}>{u.unit.name}</option>)}</select>}
      {b && (
        <>
          <div className="card stack mentor-card">
            <small className="muted">{L.mentor[i]}</small>
            {b.mentor ? (
              <>
                <b className="mentor-name">{b.mentor.name}</b>
                {b.mentor.mobile && <div className="row-gap">
                  <a className="btn small secondary" href={`tel:${b.mentor.mobile}`}><Phone size={14} /> {L.call[i]}</a>
                  {b.mentor.whatsapp && <a className="btn small" href={b.mentor.whatsapp} target="_blank" rel="noreferrer"><MessageCircle size={14} /> {L.wa[i]}</a>}</div>}
              </>) : <div className="small">{L.noMentor[i]}</div>}
            {b.handholding.status === "closed" ? <div className="small"><b>{L.done2[i]}</b></div> : b.handholding.month_no ? (
              <div className="hh-progress"><div className="row-between small"><span>{L.month[i]} {b.handholding.month_no} {L.of[i]} {b.handholding.total}</span>
                {b.next_visit && <span>{L.nextVisit[i]}: {new Date(b.next_visit).toLocaleDateString(lang === "te" ? "te-IN" : "en-IN", { day: "numeric", month: "short" })}</span>}</div>
                <div className="bar"><span style={{ width: `${(100 * b.handholding.month_no) / b.handholding.total}%` }} /></div></div>) : <div className="small muted">{L.startsAtLaunch[i]}</div>}
            {b.reviews[0] && <div className="small">{new Date(`${b.reviews[0].month}-01`).toLocaleDateString(lang === "te" ? "te-IN" : "en-IN", { month: "long" })}: <span className={`tag ${b.reviews[0].health === "green" ? "ok" : b.reviews[0].health === "red" ? "alert" : "amber"}`}>{L[b.reviews[0].health as "green"][i]}</span>
              {b.reviews[0].note && <div className="muted">{b.reviews[0].note}</div>}</div>}
          </div>

          <div className="card stack">
            <b>{L.actions[i]}</b>
            {!actions.length && <div className="small muted">{L.noActions[i]}</div>}
            {actions.map((a) => (
              <label key={`${a.rid}-${a.i}`} className="check"><input type="checkbox" onChange={async () => { await api(`/mentoring/reviews/${a.rid}/actions/${a.i}`, { method: "PUT", body: { done: true } }); load(); }} />
                <span>{a.text}{a.due ? <span className="muted"> · {L.due[i]} {new Date(a.due).toLocaleDateString(lang === "te" ? "te-IN" : "en-IN", { day: "numeric", month: "short" })}</span> : null}</span></label>))}
          </div>

          {b.handholding.status !== "closed" && (
            <div className="card stack help-card">
              <b><LifeBuoy size={16} /> {L.help[i]}</b>
              <div className="field"><span>{L.cat[i]}</span><div className="chips">{me.categories.map((c) => <button key={c.code} type="button" className={`chip ${f.category === c.code ? "on" : ""}`} onClick={() => setF({ ...f, category: c.code })}>{c.label}</button>)}</div></div>
              <div className="field"><span>{L.prio[i]}</span><div className="chips">{(["high", "medium", "low"] as const).map((p) => <button key={p} type="button" className={`chip ${f.priority === p ? "on" : ""}`} onClick={() => setF({ ...f, priority: p })}>{L[p][i]}</button>)}</div></div>
              <label className="field"><span>{L.desc[i]}</span><textarea className="input" rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></label>
              <div className="row-gap">
                <MicButton value={f.description} onChange={(v) => setF({ ...f, description: v })} onError={(m) => m && setMsg({ ok: false, text: m })} />
                <button type="button" className="btn ghost small" onClick={() => fileRef.current?.click()}><Camera size={14} /> {photo ? photo.name.slice(0, 20) : L.photo[i]}</button>
                <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
              </div>
              {msg && <div className={msg.ok ? "notice ok-notice" : "error"}>{msg.text}</div>}
              <button className="btn block" disabled={busy || f.description.trim().length < 5} onClick={send}>{L.send[i]}</button>
            </div>)}

          <div className="stack">
            <b>{L.requests[i]}</b>
            {!b.tickets.length && <div className="card small muted">{L.noReq[i]}</div>}
            {b.tickets.map((t) => <TicketCard key={t.id} t={t} i={i} onChange={load} />)}
          </div>

          {b.growth.length > 0 && (
            <div className="card stack">
              <b>{L.growth[i]}</b>
              {b.growth.map((g) => <div key={g.id} className="small">{g.goal_label}: {g.target} · {new Date(g.target_date).toLocaleDateString(lang === "te" ? "te-IN" : "en-IN", { month: "short", year: "numeric" })}{g.status === "achieved" ? ` · ✓ ${L.achieved[i]}` : ""}</div>)}
            </div>)}
        </>)}
    </div>
  );
}
