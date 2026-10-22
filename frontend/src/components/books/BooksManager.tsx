// A unit's books (M9), used by the entrepreneur in the app (English / Telugu, typing or speaking) and by staff in the portal:
// today / week / month summaries, sale and expense entry (Form 9.1), entries list with receipts, money to collect with
// WhatsApp reminders, stock with low-stock alerts, loan EMI tracker and monthly summaries sent to the mentor.
import { AlertTriangle, Camera, Check, FileText, MessageCircle, Minus, PackagePlus, Plus, Receipt, Send, Trash2, TrendingDown, TrendingUp, Wand2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiUpload, apiUrl } from "../../api";
import MicButton from "../MicButton";

type Lang = "en" | "te";
type Cat = { code: string; label: string; label_te?: string };
type Stock = { id: number; name: string; name_en: string; name_te: string | null; measure: string; qty: number; reorder_level: number; cost: number | null;
  active: boolean; low: boolean; moves: { kind: string; qty: number; on: string; note: string | null }[] };
type Meta = { unit: { id: number; code: string; name: string; status: string; upi_id: string | null; launch_date: string | null };
  categories: { sale: Cat[]; expense: Cat[] }; non_operating: string[]; stock: Stock[]; can_write: boolean };
type Entry = { id: number; kind: "sale" | "expense"; on: string; amount: number; category: string; category_label: string; stock_item_id: number | null;
  stock_item: string | null; qty: number | null; payment_mode: string; customer: { id: number; name: string; mobile: string } | null; due_date: string | null;
  collected_on: string | null; outstanding: boolean; overdue: boolean; order_id: number | null; note: string | null; source: string; has_photo: boolean;
  reminder_link?: string };
type Emi = { status: string; emi: number | null; bank: string; paid: number; total: number; balance: number;
  next: { id: number; n: number; due_date: string; amount: number; state: string } | null; overdue: { id: number; n: number; due_date: string; amount: number }[];
  schedule?: { id: number; n: number; due_date: string; amount: number; paid_on: string | null; state: string }[] };
type Sum = { period: string; start: string; end: string; sales: number; expenses: number; profit: number; emi_paid: number; drawings: number; entries: number;
  days_recorded: number; previous: { sales: number; expenses: number; profit: number; entries: number };
  by_category: { key: string; label: string; kind: string; amount: number }[]; by_mode: Record<string, number>; daily: { date: string; sales: number; expenses: number }[];
  to_collect: number; overdue: number; low_stock: Stock[]; emi: Emi | null; recorded_today: boolean };
type Month = { id: number; month: string; sales: number; expenses: number; profit: number; emi_paid: number; drawings: number; receivables: number; entries: number;
  days_recorded: number; emi_status: string; alerts: { code: string; level: string; text: string }[]; note: string | null; submitted_by: string;
  submitted_at: string | null; reviewed: boolean; review_note: string | null };

const L = {
  today: ["Summary", "సారాంశం"], add: ["Add entry", "నమోదు చేయండి"], entries: ["Entries", "నమోదులు"], collect: ["To collect", "రావలసినవి"],
  stock: ["Stock", "సరుకు"], loan: ["Loan EMI", "రుణ వాయిదా"], months: ["Monthly summary", "నెలవారీ సారాంశం"],
  day: ["Today", "ఈరోజు"], week: ["This week", "ఈ వారం"], month: ["This month", "ఈ నెల"],
  sales: ["Sales", "అమ్మకాలు"], expenses: ["Expenses", "ఖర్చులు"], profit: ["Profit", "లాభం"], loss: ["Loss", "నష్టం"],
  vsPrev: ["vs before", "గతంతో పోలిస్తే"], toCollect: ["Money to collect", "రావలసిన డబ్బు"], overdue: ["overdue", "గడువు దాటింది"],
  emiPaid: ["Loan EMI paid", "చెల్లించిన రుణ వాయిదా"], drawings: ["Taken home", "ఇంటికి తీసుకున్నది"], notProfit: ["(not counted as business expenses)", "(వ్యాపార ఖర్చుల్లో లెక్కించరు)"],
  noToday: ["Nothing recorded today yet. Add today's sales and expenses – it takes a minute.", "ఈరోజు ఇంకా ఏమీ నమోదు చేయలేదు. ఈరోజు అమ్మకాలు, ఖర్చులు నమోదు చేయండి – ఒక్క నిమిషం పడుతుంది."],
  lowStock: ["Low stock – buy soon", "సరుకు తక్కువగా ఉంది – త్వరగా కొనండి"], byCat: ["Where the money came from and went", "డబ్బు ఎక్కడి నుండి వచ్చింది, ఎక్కడికి వెళ్లింది"],
  sale: ["Sale", "అమ్మకం"], expense: ["Expense", "ఖర్చు"], amount: ["Amount (₹)", "మొత్తం (₹)"], category: ["What for", "దేనికి"], date: ["Date", "తేదీ"],
  mode: ["Paid how", "ఎలా చెల్లించారు"], cash: ["Cash", "నగదు"], upi: ["UPI", "యూపీఐ"], credit: ["Credit (pay later)", "అప్పు (తర్వాత చెల్లిస్తారు)"],
  custName: ["Customer name", "కస్టమర్ పేరు"], custMobile: ["Customer mobile", "కస్టమర్ మొబైల్"], dueBy: ["Will pay by", "ఎప్పటికి చెల్లిస్తారు"],
  item: ["Stock item (optional)", "సరుకు (ఐచ్ఛికం)"], none: ["—", "—"], qty: ["Quantity", "పరిమాణం"], note: ["Note", "గమనిక"], billPhoto: ["Bill photo", "బిల్లు ఫోటో"],
  save: ["Save", "సేవ్ చేయండి"], saved: ["Saved", "సేవ్ అయింది"], speak: ["Say it: “sold 40 plates for 1600 rupees cash”", "చెప్పండి: “40 ప్లేట్లు 1600 రూపాయలకు అమ్మాను, నగదు”"],
  fill: ["Fill the form", "ఫారం నింపండి"], check: ["Check and save", "చూసి సేవ్ చేయండి"], speakHint: ["Speak or type in Telugu or English, then check the form below.", "తెలుగు లేదా ఇంగ్లీష్‌లో చెప్పండి లేదా టైప్ చేయండి, తర్వాత కింద ఫారం చూడండి."],
  receipt: ["Receipt", "రసీదు"], sendReceipt: ["Send receipt", "రసీదు పంపండి"], remind: ["Remind on WhatsApp", "వాట్సాప్‌లో గుర్తు చేయండి"], gotCash: ["Got it – cash", "వచ్చింది – నగదు"],
  gotUpi: ["Got it – UPI", "వచ్చింది – యూపీఐ"], due: ["due", "గడువు"], nothingToCollect: ["Nobody owes you money. ", "మీకు ఎవరూ బాకీ లేరు."], fromOrder: ["from order", "ఆర్డర్ నుండి"],
  noEntries: ["No entries in these days.", "ఈ రోజుల్లో నమోదులు లేవు."], del: ["Remove", "తీసేయండి"], sureDel: ["Remove this entry?", "ఈ నమోదు తీసేయాలా?"],
  inStock: ["in stock", "ఉంది"], reorder: ["buy at", "కొనాల్సింది"], used: ["Used", "వాడారు"], got: ["Received", "వచ్చింది"], counted: ["Counted", "లెక్కించారు"],
  newItem: ["Add stock item", "సరుకు జోడించండి"], name: ["Name", "పేరు"], nameTe: ["Name (Telugu)", "పేరు (తెలుగు)"], measure: ["Measured in", "కొలత"],
  reorderAt: ["Alert when below", "ఇంతకంటే తగ్గితే హెచ్చరిక"], stockHint: ["Buying stock as an expense adds it here; selling with a stock item takes it out.", "సరుకు కొన్నప్పుడు ఖర్చుగా నమోదు చేస్తే ఇక్కడ పెరుగుతుంది; అమ్మినప్పుడు తగ్గుతుంది."],
  noLoan: ["No bank loan is linked to this business.", "ఈ వ్యాపారానికి బ్యాంకు రుణం లింక్ కాలేదు."], emi: ["EMI", "వాయిదా"], nextEmi: ["Next EMI", "తదుపరి వాయిదా"],
  paidOf: ["paid of", "చెల్లించారు, మొత్తం"], balance: ["Loan left", "మిగిలిన రుణం"], iPaid: ["I paid this EMI", "ఈ వాయిదా చెల్లించాను"], late: ["Overdue EMIs", "గడువు దాటిన వాయిదాలు"],
  onTime: ["On time", "సమయానికి"], delayed: ["Delayed", "ఆలస్యం"], default: ["Overdue 3+", "3+ బాకీ"],
  monthsHint: ["Each month's summary goes to your mentor. Past months are sent automatically; you can add a note.", "ప్రతి నెల సారాంశం మీ మెంటార్‌కు వెళ్తుంది. గడిచిన నెలలు ఆటోమేటిక్‌గా పంపబడతాయి; మీరు గమనిక జోడించవచ్చు."],
  sendMonth: ["Send with note", "గమనికతో పంపండి"], sendThis: ["Send this month now", "ఈ నెల ఇప్పుడే పంపండి"], mentorSaid: ["Mentor", "మెంటార్"], auto: ["sent automatically", "ఆటోమేటిక్‌గా పంపబడింది"],
  owner: ["sent by you", "మీరు పంపారు"], staff: ["sent by staff", "సిబ్బంది పంపారు"], daysRec: ["Days recorded", "రోజులు నమోదు"], noMonths: ["No finished months yet.", "ఇంకా పూర్తయిన నెలలు లేవు."],
  upiId: ["Your UPI ID (shown as a QR on receipts)", "మీ యూపీఐ ఐడి (రసీదులపై QR గా వస్తుంది)"],
};
const MEASURES = ["kg", "litre", "pcs", "pack", "cylinder", "bag", "box", "dozen"];
const inr = (n: number | null | undefined) => (n == null ? "—" : `${n < 0 ? "−" : ""}₹${Math.abs(Math.round(n)).toLocaleString("en-IN")}`);
const isoToday = () => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
const addDays = (iso: string, n: number) => { const d = new Date(iso); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };
const day = (iso: string, lang: Lang) => new Date(iso).toLocaleDateString(lang === "te" ? "te-IN" : "en-IN", { day: "numeric", month: "short" });
const monthName = (k: string, lang: Lang) => new Date(`${k}-01`).toLocaleDateString(lang === "te" ? "te-IN" : "en-IN", { month: "long", year: "numeric" });

function Change({ now, before, i, good = "up" }: { now: number; before: number; i: number; good?: "up" | "down" }) {
  if (!before) return null;
  const pct = Math.round((100 * (now - before)) / Math.abs(before));
  if (!pct) return null;
  const up = pct > 0;
  const ok = good === "up" ? up : !up;
  return <small className={ok ? "chg ok" : "chg bad"}>{up ? <TrendingUp size={12} /> : <TrendingDown size={12} />} {Math.abs(pct)}% {L.vsPrev[i]}</small>;
}

function PairBars({ data, lang }: { data: { date: string; sales: number; expenses: number }[]; lang: Lang }) {
  const max = Math.max(1, ...data.map((d) => Math.max(d.sales, d.expenses)));
  return (
    <div className="books-bars" role="img" aria-label={data.filter((d) => d.sales || d.expenses).map((d) => `${d.date}: ${inr(d.sales)} / ${inr(d.expenses)}`).join(", ") || "No entries"}>
      {data.map((d) => (
        <div key={d.date} title={`${day(d.date, lang)} · ${inr(d.sales)} · ${inr(d.expenses)}`}>
          <span className="s" style={{ height: `${(100 * d.sales) / max}%` }} /><span className="e" style={{ height: `${(100 * d.expenses) / max}%` }} />
        </div>))}
    </div>
  );
}

type Draft = { kind: "sale" | "expense"; amount: string; category: string; on: string; payment_mode: "cash" | "upi" | "credit"; name: string; mobile: string;
  due_date: string; stock_item_id: string; qty: string; note: string; source: "manual" | "voice" };
const blank = (kind: "sale" | "expense" = "sale"): Draft => ({ kind, amount: "", category: "", on: isoToday(), payment_mode: "cash", name: "", mobile: "",
  due_date: addDays(isoToday(), 7), stock_item_id: "", qty: "", note: "", source: "manual" });

export default function BooksManager({ unitId, lang, staffView = false }: { unitId: number; lang: Lang; staffView?: boolean }) {
  const i = lang === "te" ? 1 : 0;
  const base = `/books/units/${unitId}`;
  const [tab, setTab] = useState<"today" | "add" | "entries" | "collect" | "stock" | "loan" | "months">("today");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [period, setPeriod] = useState<"day" | "week" | "month">("day");
  const [sum, setSum] = useState<Sum | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [rec, setRec] = useState<Entry[]>([]);
  const [stock, setStock] = useState<Stock[]>([]);
  const [emi, setEmi] = useState<Emi | null>(null);
  const [months, setMonths] = useState<Month[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [f, setF] = useState<Draft>(blank());
  const [spoken, setSpoken] = useState("");
  const [busy, setBusy] = useState(false);
  const [photo, setPhoto] = useState<File | null>(null);
  const [newItem, setNewItem] = useState<{ name: string; name_te: string; measure: string; reorder_level: string } | null>(null);
  const [moveQty, setMoveQty] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [upi, setUpi] = useState("");
  const photoRef = useRef<HTMLInputElement>(null);
  const write = meta?.can_write ?? false;

  const fail = (e: unknown) => setMsg({ ok: false, text: (e as Error).message });
  const loadMeta = useCallback(() => api<Meta>(`${base}/meta?lang=${lang}`).then((m) => { setMeta(m); setStock(m.stock); setUpi(m.unit.upi_id ?? ""); }).catch(fail), [base, lang]);
  const loadSum = useCallback(() => api<Sum>(`${base}/summary?period=${period}&lang=${lang}`).then(setSum).catch(fail), [base, period, lang]);
  useEffect(() => { loadMeta(); }, [loadMeta]);
  useEffect(() => { loadSum(); }, [loadSum]);
  useEffect(() => {
    if (tab === "entries") api<Entry[]>(`${base}/entries?lang=${lang}&start=${addDays(isoToday(), -31)}`).then(setEntries).catch(fail);
    if (tab === "collect") api<Entry[]>(`${base}/receivables?lang=${lang}`).then(setRec).catch(fail);
    if (tab === "stock") api<Stock[]>(`${base}/stock?lang=${lang}`).then(setStock).catch(fail);
    if (tab === "loan") api<Emi>(`${base}/emi`).then(setEmi).catch(fail);
    if (tab === "months") api<Month[]>(`${base}/months`).then(setMonths).catch(fail);
  }, [tab, base, lang]);
  useEffect(() => { setMsg(null); }, [tab]);

  if (!meta) return msg ? <div className="error">{msg.text}</div> : <div className="muted">…</div>;
  const cats = meta.categories[f.kind];
  const catLabel = (k: string) => cats.find((c) => c.code === k)?.label ?? k;
  const stockName = (s: Stock) => (lang === "te" ? s.name_te || s.name_en : s.name_en);
  const emiLabel = (s: string) => (s === "on_time" ? L.onTime[i] : s === "delayed" ? L.delayed[i] : s === "default" ? L.default[i] : "—");

  const parse = async () => {
    if (spoken.trim().length < 2) return;
    setBusy(true); setMsg(null);
    try {
      const d = await api<{ kind: "sale" | "expense" | null; amount: number | null; qty: number | null; category: string | null; stock_item_id: number | null;
        payment_mode: "cash" | "upi" | "credit"; note: string }>(`${base}/parse`, { body: { text: spoken } });
      setF((x) => ({ ...x, kind: d.kind ?? x.kind, amount: d.amount ? String(d.amount) : x.amount, category: d.category ?? "", qty: d.qty ? String(d.qty) : "",
        stock_item_id: d.stock_item_id ? String(d.stock_item_id) : "", payment_mode: d.kind === "expense" && d.payment_mode === "credit" ? "cash" : d.payment_mode,
        note: d.note, source: "voice" }));
      setMsg({ ok: true, text: L.check[i] });
    } catch (e) { fail(e); } finally { setBusy(false); }
  };

  const save = async () => {
    setBusy(true); setMsg(null);
    try {
      const credit = f.kind === "sale" && f.payment_mode === "credit";
      const e = await api<Entry>(`${base}/entries`, { body: { kind: f.kind, on: f.on, amount: Number(f.amount), category: f.category,
        payment_mode: f.kind === "expense" && f.payment_mode === "credit" ? "cash" : f.payment_mode,
        customer: f.name.trim() && f.mobile.trim() ? { name: f.name.trim(), mobile: f.mobile.trim() } : null, due_date: credit ? f.due_date : null,
        stock_item_id: f.stock_item_id ? Number(f.stock_item_id) : null, qty: f.stock_item_id && f.qty ? Number(f.qty) : null, note: f.note.trim() || null, source: f.source } });
      if (photo) { const fd = new FormData(); fd.append("file", photo); await apiUpload(`/books/entries/${e.id}/photo`, fd).catch(() => {}); }
      setF(blank(f.kind)); setSpoken(""); setPhoto(null);
      setMsg({ ok: true, text: `${L.saved[i]} · ${f.kind === "sale" ? L.sale[i] : L.expense[i]} ${inr(e.amount)}` });
      loadSum(); loadMeta();
    } catch (x) { fail(x); } finally { setBusy(false); }
  };

  const sendReceipt = async (e: Entry) => {
    try { const r = await api<{ url: string; share_link: string }>(`/books/entries/${e.id}/receipt`, { method: "POST" }); window.open(r.share_link, "_blank", "noopener"); }
    catch (x) { fail(x); }
  };
  const openPdf = async (e: Entry) => {
    try { const r = await api<{ url: string }>(`/books/entries/${e.id}/receipt`, { method: "POST" }); window.open(apiUrl(r.url), "_blank", "noopener"); } catch (x) { fail(x); }
  };
  const collect = async (e: Entry, mode: "cash" | "upi") => {
    try { await api(`/books/entries/${e.id}/collect`, { body: { mode } }); setRec(rec.filter((x) => x.id !== e.id)); loadSum(); setMsg({ ok: true, text: L.saved[i] }); } catch (x) { fail(x); }
  };
  const move = async (s: Stock, kind: "in" | "out" | "count") => {
    const q = Number(moveQty[s.id]);
    if (!(q >= 0) || moveQty[s.id] === undefined || moveQty[s.id] === "") return;
    try { setStock(await api<Stock[]>(`/books/stock/${s.id}/move`, { body: { kind, qty: q } })); setMoveQty({ ...moveQty, [s.id]: "" }); loadSum(); } catch (x) { fail(x); }
  };

  const s = sum;
  const tabs = [["today", L.today[i]], ["add", L.add[i]], ["entries", L.entries[i]], ["collect", `${L.collect[i]}${s?.to_collect ? ` (${inr(s.to_collect)})` : ""}`],
    ["stock", `${L.stock[i]}${s?.low_stock.length ? ` (${s.low_stock.length})` : ""}`], ["loan", L.loan[i]], ["months", L.months[i]]] as const;

  return (
    <div className="stack books">
      <input ref={photoRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
      <div className="tabs shop-tabs">{tabs.map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
      {msg && <div className={msg.ok ? "notice ok-notice" : "error"}>{msg.text}</div>}

      {tab === "today" && s && (
        <div className="stack">
          {write && (
            <div className="books-quick">
              <button className="big sale" onClick={() => { setF(blank("sale")); setTab("add"); }}><Plus size={22} /> {L.sale[i]}</button>
              <button className="big expense" onClick={() => { setF(blank("expense")); setTab("add"); }}><Minus size={22} /> {L.expense[i]}</button>
            </div>)}
          {period === "day" && !s.recorded_today && write && <div className="notice">{L.noToday[i]}</div>}
          <div className="tabs" role="tablist">{(["day", "week", "month"] as const).map((p) => <button key={p} role="tab" aria-selected={period === p} className={period === p ? "on" : ""} onClick={() => setPeriod(p)}>{L[p][i]}</button>)}</div>
          <div className="shop-tiles">
            <div><small>{L.sales[i]}</small><b>{inr(s.sales)}</b><Change now={s.sales} before={s.previous.sales} i={i} /></div>
            <div><small>{L.expenses[i]}</small><b>{inr(s.expenses)}</b><Change now={s.expenses} before={s.previous.expenses} i={i} good="down" /></div>
            <div className={s.profit < 0 ? "hot warn" : ""}><small>{s.profit < 0 ? L.loss[i] : L.profit[i]}</small><b>{inr(s.profit)}</b><Change now={s.profit} before={s.previous.profit} i={i} /></div>
            <div className={s.overdue ? "hot warn" : ""}><small>{L.toCollect[i]}</small><b>{inr(s.to_collect)}</b>{s.overdue > 0 && <small className="chg bad">{s.overdue} {L.overdue[i]}</small>}</div>
          </div>
          {(s.emi_paid > 0 || s.drawings > 0) && <div className="small muted">{s.emi_paid > 0 && `${L.emiPaid[i]} ${inr(s.emi_paid)} · `}{s.drawings > 0 && `${L.drawings[i]} ${inr(s.drawings)} `}{L.notProfit[i]}</div>}
          {s.daily.length > 0 && (
            <div className="card stack" style={{ gap: 6 }}>
              <PairBars data={s.daily} lang={lang} />
              <div className="row-between small muted"><span>{day(s.start, lang)}</span><span className="bb-legend"><i className="s" /> {L.sales[i]} <i className="e" /> {L.expenses[i]}</span><span>{day(s.daily[s.daily.length - 1].date, lang)}</span></div>
            </div>)}
          {s.low_stock.length > 0 && (
            <div className="card books-alert"><AlertTriangle size={18} /><div><b>{L.lowStock[i]}</b><div className="small">{s.low_stock.map((x) => `${x.name} ${x.qty} ${x.measure}`).join(" · ")}</div></div></div>)}
          {s.emi?.next && (
            <button className="card books-alert soft link-card" onClick={() => setTab("loan")}><Receipt size={18} /><div><b>{L.nextEmi[i]}: {inr(s.emi.next.amount)}</b>
              <div className="small">{day(s.emi.next.due_date, lang)}{s.emi.overdue.length ? ` · ${s.emi.overdue.length} ${L.overdue[i]}` : ""}</div></div></button>)}
          {s.by_category.length > 0 && (
            <div className="card stack" style={{ gap: 6 }}>
              <b className="small">{L.byCat[i]}</b>
              {s.by_category.map((c) => {
                const max = Math.max(...s.by_category.map((x) => x.amount));
                return <div key={c.key} className="cat-row"><span>{c.label}</span><span className="bar"><span className={c.kind} style={{ width: `${(100 * c.amount) / max}%` }} /></span><b>{inr(c.amount)}</b></div>;
              })}
            </div>)}
        </div>)}

      {tab === "add" && (
        <div className="stack">
          {!write && <div className="notice">Read only</div>}
          <div className="books-quick">
            <button className={`big sale ${f.kind === "sale" ? "on" : "off"}`} onClick={() => setF({ ...f, kind: "sale", category: "" })}><Plus size={22} /> {L.sale[i]}</button>
            <button className={`big expense ${f.kind === "expense" ? "on" : "off"}`} onClick={() => setF({ ...f, kind: "expense", category: "", payment_mode: f.payment_mode === "credit" ? "cash" : f.payment_mode })}><Minus size={22} /> {L.expense[i]}</button>
          </div>
          <div className="card stack voice-box">
            <div className="small muted">{L.speakHint[i]}</div>
            <textarea className="input" rows={2} aria-label={L.speak[i]} placeholder={L.speak[i]} value={spoken} onChange={(e) => setSpoken(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); parse(); } }} />
            <div className="row-gap" style={{ justifyContent: "flex-end" }}>
              <MicButton value={spoken} onChange={setSpoken} onError={(m) => m && setMsg({ ok: false, text: m })} />
              <button className="btn secondary" disabled={busy || spoken.trim().length < 2} onClick={parse}><Wand2 size={16} /> {L.fill[i]}</button>
            </div>
          </div>
          <div className="card stack">
            <label className="field"><span>{L.amount[i]}</span><input className="input big-num" inputMode="decimal" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value.replace(/[^\d.]/g, "") })} /></label>
            <div className="field"><span>{L.category[i]}</span>
              <div className="chips">{cats.map((c) => <button key={c.code} type="button" className={`chip ${f.category === c.code ? "on" : ""}`} onClick={() => setF({ ...f, category: c.code })}>{c.label}</button>)}</div></div>
            <div className="grid-2">
              <label className="field"><span>{L.date[i]}</span><input className="input" type="date" max={isoToday()} value={f.on} onChange={(e) => setF({ ...f, on: e.target.value })} /></label>
              <div className="field"><span>{L.mode[i]}</span>
                <div className="chips">{(f.kind === "sale" ? (["cash", "upi", "credit"] as const) : (["cash", "upi"] as const)).map((m) => (
                  <button key={m} type="button" className={`chip ${f.payment_mode === m ? "on" : ""}`} onClick={() => setF({ ...f, payment_mode: m })}>{L[m][i]}</button>))}</div></div>
            </div>
            {(f.kind === "sale" && f.payment_mode === "credit") && (
              <div className="grid-2">
                <label className="field"><span>{L.custName[i]}</span><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
                <label className="field"><span>{L.custMobile[i]}</span><input className="input" inputMode="numeric" maxLength={10} value={f.mobile} onChange={(e) => setF({ ...f, mobile: e.target.value.replace(/\D/g, "") })} /></label>
                <label className="field"><span>{L.dueBy[i]}</span><input className="input" type="date" min={f.on} value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} /></label>
              </div>)}
            {stock.length > 0 && (
              <div className="grid-2">
                <label className="field"><span>{L.item[i]}</span><select className="input" value={f.stock_item_id} onChange={(e) => setF({ ...f, stock_item_id: e.target.value })}>
                  <option value="">{L.none[i]}</option>{stock.filter((x) => x.active).map((x) => <option key={x.id} value={x.id}>{stockName(x)} ({x.qty} {x.measure})</option>)}</select></label>
                {f.stock_item_id && <label className="field"><span>{L.qty[i]} ({stock.find((x) => String(x.id) === f.stock_item_id)?.measure})</span><input className="input" inputMode="decimal" value={f.qty} onChange={(e) => setF({ ...f, qty: e.target.value.replace(/[^\d.]/g, "") })} /></label>}
              </div>)}
            <label className="field"><span>{L.note[i]}</span><input className="input" value={f.note} maxLength={300} onChange={(e) => setF({ ...f, note: e.target.value })} /></label>
            <div className="row-gap">
              <button type="button" className="btn ghost small" onClick={() => photoRef.current?.click()}><Camera size={14} /> {photo ? photo.name.slice(0, 24) : L.billPhoto[i]}</button>
            </div>
            <button className="btn block" disabled={!write || busy || !(Number(f.amount) > 0) || !f.category || (f.kind === "sale" && f.payment_mode === "credit" && (f.name.trim().length < 2 || f.mobile.length !== 10))
              || (!!f.stock_item_id && !(Number(f.qty) > 0))} onClick={save}><Check size={16} /> {L.save[i]} · {f.kind === "sale" ? L.sale[i] : L.expense[i]} {f.amount ? inr(Number(f.amount)) : ""}{f.category ? ` · ${catLabel(f.category)}` : ""}</button>
          </div>
        </div>)}

      {tab === "entries" && (
        <div className="stack" style={{ gap: 8 }}>
          {!entries.length && <div className="card muted">{L.noEntries[i]}</div>}
          {entries.map((e) => (
            <div key={e.id} className={`entry-row ${e.kind}`}>
              <div className="entry-main">
                <b>{e.category_label}{e.stock_item ? (e.stock_item === e.category_label ? ` · ${e.qty ?? ""}` : ` · ${e.stock_item} ${e.qty ?? ""}`) : ""}</b>
                <span className="small muted">{day(e.on, lang)} · {e.payment_mode === "credit" ? (e.collected_on ? `${L.credit[i]} ✓` : L.credit[i]) : L[e.payment_mode as "cash" | "upi"]?.[i] ?? e.payment_mode}
                  {e.customer ? ` · ${e.customer.name}` : ""}{e.order_id ? ` · ${L.fromOrder[i]}` : ""}{e.source === "voice" ? " · 🎤" : ""}</span>
                {e.note && e.note !== e.category_label && <span className="small muted ellipsis">{e.note}</span>}
              </div>
              <div className="entry-side">
                <b className="amt">{e.kind === "sale" ? "+" : "−"}{inr(e.amount)}</b>
                <span className="entry-actions">
                  {e.kind === "sale" && <button className="btn ghost small" aria-label={L.receipt[i]} title={L.receipt[i]} onClick={() => openPdf(e)}><FileText size={14} /></button>}
                  {e.kind === "sale" && <button className="btn ghost small" aria-label={L.sendReceipt[i]} title={L.sendReceipt[i]} onClick={() => sendReceipt(e)}><Send size={14} /></button>}
                  {write && !e.order_id && <button className="btn ghost small danger" aria-label={L.del[i]} onClick={async () => {
                    if (!window.confirm(L.sureDel[i])) return;
                    try { await api(`/books/entries/${e.id}`, { method: "DELETE" }); setEntries(entries.filter((x) => x.id !== e.id)); loadSum(); } catch (x) { fail(x); } }}><Trash2 size={14} /></button>}
                </span>
              </div>
            </div>))}
        </div>)}

      {tab === "collect" && (
        <div className="stack" style={{ gap: 8 }}>
          {!rec.length && <div className="card muted">{L.nothingToCollect[i]}</div>}
          {rec.map((e) => (
            <div key={e.id} className={`order-card ${e.overdue ? "late" : ""}`}>
              <div className="row-between"><b>{e.customer?.name ?? "—"}</b><b>{inr(e.amount)}</b></div>
              <div className="small muted">{e.category_label} · {day(e.on, lang)} · {L.due[i]} {e.due_date ? day(e.due_date, lang) : "—"}{e.overdue ? ` · ${L.overdue[i]}` : ""}
                {e.customer && <> · <a href={`tel:${e.customer.mobile}`}>{e.customer.mobile}</a></>}</div>
              <div className="row-gap">
                {e.reminder_link && <a className="btn small secondary" href={e.reminder_link} target="_blank" rel="noreferrer"><MessageCircle size={14} /> {L.remind[i]}</a>}
                {write && <button className="btn small" onClick={() => collect(e, "cash")}>{L.gotCash[i]}</button>}
                {write && <button className="btn small" onClick={() => collect(e, "upi")}>{L.gotUpi[i]}</button>}
              </div>
            </div>))}
          {write && (
            <div className="card stack" style={{ gap: 6 }}>
              <label className="field"><span>{L.upiId[i]}</span>
                <div className="row-gap"><input className="input" style={{ flex: 1, minWidth: 0 }} placeholder="9876543210@ybl" value={upi} onChange={(e) => setUpi(e.target.value.trim())} />
                  <button className="btn secondary" onClick={async () => { try { await api(`${base}/settings`, { method: "PUT", body: { upi_id: upi || null } }); setMsg({ ok: true, text: L.saved[i] }); } catch (x) { fail(x); } }}>{L.save[i]}</button></div></label>
            </div>)}
        </div>)}

      {tab === "stock" && (
        <div className="stack" style={{ gap: 8 }}>
          <div className="small muted">{L.stockHint[i]}</div>
          {stock.map((x) => (
            <div key={x.id} className={`stock-row ${x.low ? "low" : ""} ${x.active ? "" : "off"}`}>
              <div className="entry-main">
                <b>{stockName(x)}</b>
                <span className="small muted">{x.reorder_level ? `${L.reorder[i]} ${x.reorder_level} ${x.measure}` : ""}{x.cost ? ` · ₹${x.cost}/${x.measure}` : ""}</span>
              </div>
              <div className="qty"><b>{x.qty}</b><small>{x.measure}</small></div>
              {write && (
                <div className="stock-actions">
                  <input className="input" aria-label={`${L.qty[i]} ${x.name}`} inputMode="decimal" style={{ width: 70 }} value={moveQty[x.id] ?? ""} onChange={(e) => setMoveQty({ ...moveQty, [x.id]: e.target.value.replace(/[^\d.]/g, "") })} />
                  <button className="btn ghost small" onClick={() => move(x, "out")}>{L.used[i]}</button>
                  <button className="btn ghost small" onClick={() => move(x, "in")}>{L.got[i]}</button>
                  <button className="btn ghost small" onClick={() => move(x, "count")}>{L.counted[i]}</button>
                </div>)}
            </div>))}
          {write && (newItem ? (
            <div className="card stack">
              <div className="grid-2">
                <label className="field"><span>{L.name[i]}</span><input className="input" value={newItem.name} onChange={(e) => setNewItem({ ...newItem, name: e.target.value })} /></label>
                <label className="field"><span>{L.nameTe[i]}</span><input className="input" value={newItem.name_te} onChange={(e) => setNewItem({ ...newItem, name_te: e.target.value })} /></label>
                <label className="field"><span>{L.measure[i]}</span><select className="input" value={newItem.measure} onChange={(e) => setNewItem({ ...newItem, measure: e.target.value })}>{MEASURES.map((m) => <option key={m}>{m}</option>)}</select></label>
                <label className="field"><span>{L.reorderAt[i]}</span><input className="input" inputMode="decimal" value={newItem.reorder_level} onChange={(e) => setNewItem({ ...newItem, reorder_level: e.target.value.replace(/[^\d.]/g, "") })} /></label>
              </div>
              <div className="row-gap">
                <button className="btn" disabled={newItem.name.trim().length < 2} onClick={async () => {
                  try { setStock(await api<Stock[]>(`${base}/stock`, { body: { name: newItem.name, name_te: newItem.name_te || null, measure: newItem.measure, reorder_level: Number(newItem.reorder_level) || 0 } })); setNewItem(null); loadMeta(); } catch (x) { fail(x); } }}>{L.save[i]}</button>
                <button className="btn ghost" onClick={() => setNewItem(null)}>✕</button>
              </div>
            </div>) : <div><button className="btn ghost" onClick={() => setNewItem({ name: "", name_te: "", measure: "kg", reorder_level: "" })}><PackagePlus size={16} /> {L.newItem[i]}</button></div>)}
        </div>)}

      {tab === "loan" && emi && (
        !emi.total ? <div className="card muted">{L.noLoan[i]}</div> : (
          <div className="stack">
            <div className="shop-tiles">
              <div><small>{L.emi[i]}</small><b>{inr(emi.emi)}</b><small>{emi.bank?.toUpperCase()}</small></div>
              <div><small>{L.paidOf[i]}</small><b>{emi.paid} / {emi.total}</b></div>
              <div><small>{L.balance[i]}</small><b>{inr(emi.balance)}</b></div>
              <div className={emi.status !== "on_time" && emi.status !== "none" ? "hot warn" : ""}><small>Status</small><b>{emiLabel(emi.status)}</b></div>
            </div>
            <div className="card table-wrap">
              <table className="table compact">
                <thead><tr><th>#</th><th>{L.date[i]}</th><th className="num">{L.amount[i]}</th><th></th></tr></thead>
                <tbody>{(emi.schedule ?? []).filter((r) => !r.paid_on || r.n > emi.paid - 3).slice(0, 8).map((r) => (
                  <tr key={r.id} className={r.state === "overdue" ? "late" : ""}>
                    <td>{r.n}</td><td>{day(r.due_date, lang)}</td><td className="num">{inr(r.amount)}</td>
                    <td>{r.paid_on ? <span className="tag ok">✓ {day(r.paid_on, lang)}</span> : r.state === "overdue" ? <span className="tag amber">{L.overdue[i]}</span> : null}
                      {!r.paid_on && write && (r.state === "overdue" || r.id === emi.next?.id) && (
                        <button className="btn small" style={{ marginLeft: 6 }} onClick={async () => {
                          try { await api(`${base}/emi/${r.id}/paid`, { body: { on: isoToday(), mode: "upi" } }); setEmi(await api<Emi>(`${base}/emi`)); loadSum(); setMsg({ ok: true, text: L.saved[i] }); } catch (x) { fail(x); } }}>{L.iPaid[i]}</button>)}</td>
                  </tr>))}</tbody>
              </table>
            </div>
          </div>))}

      {tab === "months" && (
        <div className="stack">
          <div className="small muted">{L.monthsHint[i]}</div>
          {write && new Date().getDate() >= 25 && !months.some((m) => m.month === isoToday().slice(0, 7)) && (
            <button className="btn secondary" onClick={async () => { try { const m = await api<Month>(`${base}/months/${isoToday().slice(0, 7)}/submit`, { body: {} }); setMonths([m, ...months]); } catch (x) { fail(x); } }}><Send size={16} /> {L.sendThis[i]}</button>)}
          {!months.length && <div className="card muted">{L.noMonths[i]}</div>}
          {months.map((m) => (
            <div key={m.id} className="card stack month-card">
              <div className="row-between"><b>{monthName(m.month, lang)}</b><span className="small muted">{L[m.submitted_by as "auto" | "owner" | "staff"]?.[i] ?? m.submitted_by}</span></div>
              <div className="shop-tiles mini">
                <div><small>{L.sales[i]}</small><b>{inr(m.sales)}</b></div>
                <div><small>{L.expenses[i]}</small><b>{inr(m.expenses)}</b></div>
                <div className={m.profit < 0 ? "hot warn" : ""}><small>{m.profit < 0 ? L.loss[i] : L.profit[i]}</small><b>{inr(m.profit)}</b></div>
                <div><small>{L.daysRec[i]}</small><b>{m.days_recorded}</b></div>
              </div>
              {m.alerts.length > 0 && <div className="stack" style={{ gap: 4 }}>{m.alerts.map((a) => <div key={a.code} className={`alert-line ${a.level}`}><AlertTriangle size={14} /> {a.text}</div>)}</div>}
              {m.note && <div className="small">“{m.note}”</div>}
              {m.review_note && <div className="small review-note"><b>{L.mentorSaid[i]}:</b> {m.review_note}</div>}
              {write && !staffView && (
                <div className="row-gap">
                  <input className="input" style={{ flex: 1, minWidth: 0 }} aria-label={L.note[i]} placeholder={L.note[i]} value={notes[m.month] ?? ""} onChange={(e) => setNotes({ ...notes, [m.month]: e.target.value })} />
                  <button className="btn small" disabled={!(notes[m.month] ?? "").trim()} onClick={async () => {
                    try { const r = await api<Month>(`${base}/months/${m.month}/submit`, { body: { note: notes[m.month] } }); setMonths(months.map((x) => (x.id === r.id ? r : x))); setNotes({ ...notes, [m.month]: "" }); } catch (x) { fail(x); } }}>{L.sendMonth[i]}</button>
                </div>)}
            </div>))}
        </div>)}
    </div>
  );
}
