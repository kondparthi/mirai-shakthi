// A unit's shop (M8), used by the entrepreneur in the app (English / Telugu) and by staff in the portal:
// today's view, orders and bookings, quick sale entry, products & services, customers with follow-ups, posters and
// messages, and buyer enquiries sent to the unit.
import { Camera, Copy, ImagePlus, MessageCircle, Plus, Share2, ShoppingBag, Sparkles, Store, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiUpload, apiUrl } from "../../api";

type Lang = "en" | "te";
type Listing = { id: number; kind: "product" | "service"; name: string; name_te: string | null; label: string; description: string | null;
  photos: { name: string; url: string }[]; price: number; price_unit: string; available: boolean; daily_capacity: number | null;
  slots: { label: string; capacity: number | null }[]; sort: number };
type Order = { id: number; code: string; kind: string; lines: { listing_id: number; name: string; name_te?: string | null; qty: number; price: number; unit: string }[];
  amount: number; date: string | null; slot: string | null; status: string; status_label: string; payment_mode: string | null; source: string;
  note: string | null; rating: number | null; rating_comment: string | null; outstanding: boolean; created_at: string | null;
  customer: { id: number; name: string; mobile: string; kind: string; village: string | null; organisation: string | null } };
type Summary = { unit: { id: number; code: string; name: string; status: string; shop_url: string }; today: number; month: number; month_orders: number;
  new_orders: number; upcoming_bookings: number; outstanding: number; customers: number; repeat_customers: number; rating: number | null; ratings: number;
  daily: { date: string; amount: number }[]; top_items: { name: string; amount: number }[] };
type Cust = { id: number; name: string; mobile: string; kind: string; village: string | null; organisation: string | null; orders: number; spend: number; last: string | null; outstanding: number };
type Follow = { customer_id: number; name: string; mobile: string; orders: number; last: string; days: number; wa_link: string };
type Promo = { id: number; lang: string; title: string; tagline: string | null; message: string; poster_url: string; source: string; at: string; share_link: string };
type Enq = { id: number; code: string; need: string; quantity: string | null; needed_by: string | null; budget: number | null; status: string;
  buyer: { name: string; organisation: string | null; kind: string; mobile: string }; route: { id: number; status: string; quote_amount: number | null; reply: string | null } };

const L = {
  today: ["Today", "ఈరోజు"], orders: ["Orders", "ఆర్డర్లు"], sale: ["New sale", "కొత్త అమ్మకం"], items: ["Products & services", "వస్తువులు & సేవలు"],
  customers: ["Customers", "కస్టమర్లు"], promote: ["Promote", "ప్రచారం"], enquiries: ["Buyer enquiries", "కొనుగోలుదారుల విచారణలు"],
  salesToday: ["Sales today", "ఈరోజు అమ్మకాలు"], month: ["This month", "ఈ నెల"], newOrders: ["New orders", "కొత్త ఆర్డర్లు"], credit: ["Money to collect", "రావలసిన డబ్బు"],
  bookings: ["Coming bookings", "రాబోయే బుకింగ్‌లు"], rating: ["Rating", "రేటింగ్"], last30: ["Last 30 days", "గత 30 రోజులు"], top: ["Best sellers", "ఎక్కువగా అమ్ముడైనవి"],
  noOrders: ["No orders here.", "ఇక్కడ ఆర్డర్లు లేవు."], open: ["Open", "పెండింగ్"], upcoming: ["Upcoming", "రాబోయేవి"], all: ["All", "అన్నీ"], creditTab: ["Credit", "అప్పు"],
  confirm: ["Confirm", "నిర్ధారించండి"], deliver: ["Delivered", "అందించారు"], paidCash: ["Paid – cash", "చెల్లించారు – నగదు"], paidUpi: ["Paid – UPI", "చెల్లించారు – యూపీఐ"],
  onCredit: ["Delivered on credit", "అప్పుగా అందించారు"], cancel: ["Cancel", "రద్దు"], why: ["Why is it cancelled?", "ఎందుకు రద్దు చేస్తున్నారు?"],
  mobile: ["Customer mobile", "కస్టమర్ మొబైల్"], name: ["Customer name", "కస్టమర్ పేరు"], village: ["Village / area", "గ్రామం / ప్రాంతం"], type: ["Customer type", "కస్టమర్ రకం"],
  qty: ["Qty", "సంఖ్య"], date: ["Date", "తేదీ"], slot: ["Time slot", "సమయం"], left: ["left", "మిగిలింది"], total: ["Total", "మొత్తం"],
  paidNow: ["Paid now", "ఇప్పుడే చెల్లించారు"], laterPay: ["Delivered, to be paid", "అందించారు, తర్వాత చెల్లిస్తారు"], booked: ["Booked / to deliver", "బుక్ చేశారు / అందించాలి"],
  saveItem: ["Save", "సేవ్ చేయండి"], campaign: ["Sold at a campaign / mela?", "ప్రచారం / మేళాలో అమ్మారా?"], cash: ["Cash", "నగదు"], upi: ["UPI", "యూపీఐ"], save: ["Save sale", "అమ్మకం సేవ్ చేయండి"], saved: ["Saved", "సేవ్ అయింది"], note: ["Note", "గమనిక"],
  addItem: ["Add product / service", "వస్తువు / సేవ జోడించండి"], fromPlan: ["Start from my business plan", "నా వ్యాపార ప్రణాళిక నుండి మొదలుపెట్టండి"],
  product: ["Product", "వస్తువు"], service: ["Service (booking)", "సేవ (బుకింగ్)"], price: ["Price (₹)", "ధర (₹)"], per: ["per", "ఒక్కో"],
  nameEn: ["Name (English)", "పేరు (ఇంగ్లీష్)"], nameTe: ["Name (Telugu)", "పేరు (తెలుగు)"], desc: ["Description", "వివరణ"], available: ["Available now", "ఇప్పుడు అందుబాటులో ఉంది"],
  daily: ["Can do per day (blank = no limit)", "రోజుకు ఎంత (ఖాళీ = పరిమితి లేదు)"], slots: ["Time slots and capacity", "సమయాలు, సామర్థ్యం"], photo: ["Photo", "ఫోటో"],
  follow: ["Call back these customers", "ఈ కస్టమర్లకు మళ్లీ ఫోన్ చేయండి"], followNote: ["Bought before, no order for", "ముందు కొన్నారు, ఆర్డర్ లేదు"], days: ["days", "రోజులు"],
  done: ["Done", "అయింది"], spend: ["Spent", "ఖర్చు"], ordersN: ["orders", "ఆర్డర్లు"], due: ["to collect", "రావాలి"],
  makePoster: ["Make poster & message", "పోస్టర్ & సందేశం తయారు చేయండి"], occasion: ["Occasion", "సందర్భం"], language: ["Language", "భాష"],
  share: ["Share on WhatsApp", "వాట్సాప్‌లో పంపండి"], copy: ["Copy message", "సందేశం కాపీ"], copied: ["Copied", "కాపీ అయింది"], download: ["Download poster", "పోస్టర్ డౌన్‌లోడ్"],
  shopLink: ["Your online shop", "మీ ఆన్‌లైన్ షాప్"], notLaunched: ["The online shop opens when the unit is launched.", "వ్యాపారం ప్రారంభమైన తర్వాత ఆన్‌లైన్ షాప్ తెరుచుకుంటుంది."],
  interested: ["Interested – send quote", "ఆసక్తి ఉంది – ధర పంపండి"], decline: ["Not now", "ఇప్పుడు కాదు"], quote: ["Your price (₹)", "మీ ధర (₹)"], reply: ["Message", "సందేశం"],
  makeOrder: ["Buyer agreed – make order", "కొనుగోలుదారు ఒప్పుకున్నారు – ఆర్డర్ చేయండి"], noEnq: ["No enquiries yet. MIRAI sends buyer enquiries here.", "ఇంకా విచారణలు లేవు. మిరాయ్ కొనుగోలుదారుల విచారణలు ఇక్కడ పంపుతుంది."],
  need: ["Needs", "కావాలి"], by: ["by", "తేదీ"],
};
const KINDS: [string, string, string][] = [["household", "Household", "ఇంటి కస్టమర్"], ["shop", "Shop", "షాప్"], ["institution", "Institution", "సంస్థ"],
  ["farmer", "Farmer", "రైతు"], ["event", "Event / caterer", "వేడుక"], ["other", "Other", "ఇతర"]];
const OCC: [string, string, string][] = [["daily", "Today's special", "ఈరోజు ప్రత్యేకం"], ["launch", "Now open", "కొత్తగా ప్రారంభం"], ["festival", "Festival", "పండుగ"],
  ["bulk", "Bulk orders", "పెద్ద ఆర్డర్లు"], ["booking", "Book now", "బుక్ చేసుకోండి"]];
const UNITS = ["each", "plate", "glass", "cup", "pack", "piece", "kg", "litre", "acre", "hour", "day", "trip"];
const TAG: Record<string, string> = { new: "amber", confirmed: "", delivered: "amber", paid: "ok", cancelled: "grey" };
const inr = (n: number | null | undefined) => (n == null ? "—" : `₹${Math.round(n).toLocaleString("en-IN")}`);
const isoToday = () => new Date().toISOString().slice(0, 10);

function Bars({ data }: { data: { date: string; amount: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.amount));
  return (
    <div className="spark-bars" role="img" aria-label={data.filter((d) => d.amount).map((d) => `${d.date}: ${inr(d.amount)}`).join(", ") || "No sales"}>
      {data.map((d) => <span key={d.date} title={`${d.date} · ${inr(d.amount)}`} style={{ height: `${Math.max(2, (100 * d.amount) / max)}%` }} className={d.amount ? "" : "zero"} />)}
    </div>
  );
}

function ListingForm({ li, lang, onSave, onClose }: { li: Partial<Listing> | null; lang: Lang; onSave: (b: object) => Promise<void>; onClose: () => void }) {
  const i = lang === "te" ? 1 : 0;
  const [f, setF] = useState({ kind: li?.kind ?? "product", name: li?.name ?? "", name_te: li?.name_te ?? "", description: li?.description ?? "", price: li?.price ?? 0,
    price_unit: li?.price_unit ?? "each", available: li?.available ?? true, daily_capacity: li?.daily_capacity ?? null as number | null,
    slots: li?.slots ?? [] as { label: string; capacity: number | null }[], sort: li?.sort ?? 100 });
  return (
    <div className="sheet" role="dialog" aria-modal="true">
      <div className="sheet-body stack">
        <div className="row-between"><b>{li?.id ? f.name : L.addItem[i]}</b><button className="btn ghost small" onClick={onClose} aria-label="Close">✕</button></div>
        <div className="tabs">{(["product", "service"] as const).map((k) => <button key={k} className={f.kind === k ? "on" : ""} onClick={() => setF({ ...f, kind: k })}>{L[k][i]}</button>)}</div>
        <label className="field"><span>{L.nameEn[i]}</span><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
        <label className="field"><span>{L.nameTe[i]}</span><input className="input" value={f.name_te} onChange={(e) => setF({ ...f, name_te: e.target.value })} /></label>
        <div className="row-gap">
          <label className="field" style={{ flex: 1 }}><span>{L.price[i]}</span><input className="input" type="number" inputMode="decimal" min={0} value={f.price || ""} onChange={(e) => setF({ ...f, price: Number(e.target.value) })} /></label>
          <label className="field" style={{ flex: 1 }}><span>{L.per[i]}</span><select className="input" value={f.price_unit} onChange={(e) => setF({ ...f, price_unit: e.target.value })}>{UNITS.map((u) => <option key={u}>{u}</option>)}</select></label>
        </div>
        <label className="field"><span>{L.desc[i]}</span><input className="input" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></label>
        <label className="field"><span>{L.daily[i]}</span><input className="input" type="number" min={0} value={f.daily_capacity ?? ""} onChange={(e) => setF({ ...f, daily_capacity: e.target.value ? Number(e.target.value) : null })} /></label>
        {f.kind === "service" && (
          <div className="stack" style={{ gap: 6 }}>
            <b className="small">{L.slots[i]}</b>
            {f.slots.map((s, j) => (
              <div key={j} className="row-gap">
                <input className="input" aria-label="Slot" style={{ flex: 2 }} value={s.label} placeholder="6–10 AM" onChange={(e) => setF({ ...f, slots: f.slots.map((x, k) => (k === j ? { ...x, label: e.target.value } : x)) })} />
                <input className="input" aria-label="Capacity" type="number" min={0} style={{ width: 100 }} value={s.capacity ?? ""} placeholder="∞" onChange={(e) => setF({ ...f, slots: f.slots.map((x, k) => (k === j ? { ...x, capacity: e.target.value ? Number(e.target.value) : null } : x)) })} />
                <button className="btn ghost small danger" aria-label="Remove slot" onClick={() => setF({ ...f, slots: f.slots.filter((_, k) => k !== j) })}><Trash2 size={14} /></button>
              </div>))}
            <div><button className="btn ghost small" onClick={() => setF({ ...f, slots: [...f.slots, { label: "", capacity: null }] })}><Plus size={14} /> {L.slot[i]}</button></div>
          </div>)}
        <label className="check"><input type="checkbox" checked={f.available} onChange={(e) => setF({ ...f, available: e.target.checked })} /> {L.available[i]}</label>
        <button className="btn block" disabled={f.name.trim().length < 2 || !(f.price > 0)} onClick={() => onSave({ ...f, name_te: f.name_te || null, description: f.description || null,
          slots: f.slots.filter((s) => s.label.trim()) })}>{L.saveItem[i]}</button>
      </div>
    </div>
  );
}

function SaleForm({ unitId, listings, lang, onDone }: { unitId: number; listings: Listing[]; lang: Lang; onDone: (o: Order) => void }) {
  const i = lang === "te" ? 1 : 0;
  const [cust, setCust] = useState({ mobile: "", name: "", village: "", kind: "household" });
  const [qty, setQty] = useState<Record<number, number>>({});
  const [day, setDay] = useState(isoToday());
  const [slot, setSlot] = useState("");
  const [status, setStatus] = useState<"paid" | "delivered" | "confirmed">("paid");
  const [mode, setMode] = useState<"cash" | "upi">("cash");
  const [note, setNote] = useState("");
  const [camps, setCamps] = useState<{ id: number; name: string }[]>([]);
  const [camp, setCamp] = useState<number | "">("");
  const [avail, setAvail] = useState<Record<string, number | null>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const live = listings.filter((l) => l.available);
  const picked = live.filter((l) => (qty[l.id] ?? 0) > 0);
  const service = picked.find((l) => l.kind === "service");
  const total = picked.reduce((a, l) => a + l.price * qty[l.id], 0);
  useEffect(() => {
    api<{ id: number; name: string }[]>(`/market/units/${unitId}/campaigns`).then(setCamps).catch(() => {});
  }, [unitId]);
  useEffect(() => {
    if (cust.mobile.length !== 10) return;
    api<{ found: boolean; name: string | null; village: string | null; kind: string | null }>(`/market/customers/lookup?mobile=${cust.mobile}`)
      .then((r) => r.found && setCust((c) => ({ ...c, name: c.name || r.name || "", village: c.village || r.village || "", kind: r.kind || c.kind }))).catch(() => {});
  }, [cust.mobile]);
  useEffect(() => {
    if (!service) return;
    api<{ date: string; slots: { label: string | null; left: number | null }[] }[]>(`/market/listings/${service.id}/availability?start=${day}&days=1`)
      .then((r) => setAvail(Object.fromEntries((r[0]?.slots ?? []).map((s) => [s.label ?? "", s.left])))).catch(() => {});
  }, [service, day]);
  useEffect(() => {
    if (service && status === "paid" && day > isoToday()) setStatus("confirmed");
  }, [service, day, status]);
  const save = async () => {
    setBusy(true); setError(null);
    try {
      const o = await api<Order>(`/market/units/${unitId}/orders`, { body: { customer: { name: cust.name, mobile: cust.mobile, village: cust.village || null, kind: cust.kind },
        lines: picked.map((l) => ({ listing_id: l.id, qty: qty[l.id] })), date: service || status === "confirmed" ? day : null, slot: service?.slots.length ? slot : null,
        status, payment_mode: status === "paid" ? mode : status === "delivered" ? "credit" : null, note: note || null, campaign_id: camp || null } });
      onDone(o);
      setQty({}); setNote(""); setCust({ mobile: "", name: "", village: "", kind: "household" });
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <div className="sale-items">
        {live.map((l) => (
          <div key={l.id} className={`sale-item ${(qty[l.id] ?? 0) > 0 ? "on" : ""}`}>
            {l.photos[0] ? <img src={apiUrl(l.photos[0].url)} alt="" /> : <span className="ph"><ShoppingBag size={20} /></span>}
            <div style={{ flex: 1, minWidth: 0 }}><b>{lang === "te" ? l.name_te || l.name : l.name}</b><small>{inr(l.price)} / {l.price_unit}</small></div>
            <div className="stepper">
              <button aria-label="Less" onClick={() => setQty({ ...qty, [l.id]: Math.max(0, (qty[l.id] ?? 0) - 1) })}>−</button>
              <input aria-label={`${L.qty[i]} ${l.name}`} inputMode="decimal" value={qty[l.id] ?? 0} onChange={(e) => setQty({ ...qty, [l.id]: Number(e.target.value) || 0 })} />
              <button aria-label="More" onClick={() => setQty({ ...qty, [l.id]: (qty[l.id] ?? 0) + 1 })}>+</button>
            </div>
          </div>))}
      </div>
      <div className="row-between total-line"><b>{L.total[i]}</b><b>{inr(total)}</b></div>
      <div className="grid-2">
        <label className="field"><span>{L.mobile[i]}</span><input className="input" inputMode="numeric" maxLength={10} value={cust.mobile} onChange={(e) => setCust({ ...cust, mobile: e.target.value.replace(/\D/g, "") })} /></label>
        <label className="field"><span>{L.name[i]}</span><input className="input" value={cust.name} onChange={(e) => setCust({ ...cust, name: e.target.value })} /></label>
        <label className="field"><span>{L.village[i]}</span><input className="input" value={cust.village} onChange={(e) => setCust({ ...cust, village: e.target.value })} /></label>
        <label className="field"><span>{L.type[i]}</span><select className="input" value={cust.kind} onChange={(e) => setCust({ ...cust, kind: e.target.value })}>{KINDS.map(([k, en, te]) => <option key={k} value={k}>{lang === "te" ? te : en}</option>)}</select></label>
      </div>
      {(service || status === "confirmed") && (
        <div className="grid-2">
          <label className="field"><span>{L.date[i]}</span><input className="input" type="date" value={day} onChange={(e) => setDay(e.target.value)} /></label>
          {service && service.slots.length > 0 && (
            <label className="field"><span>{L.slot[i]}</span><select className="input" value={slot} onChange={(e) => setSlot(e.target.value)}>
              <option value="">—</option>{service.slots.map((s) => <option key={s.label} value={s.label}>{s.label}{avail[s.label] != null ? ` (${avail[s.label]} ${L.left[i]})` : ""}</option>)}</select></label>)}
          {service && !service.slots.length && avail[""] != null && <p className="small muted">{avail[""]} {service.price_unit} {L.left[i]}</p>}
        </div>)}
      <div className="tabs">{([["paid", L.paidNow[i]], ["delivered", L.laterPay[i]], ["confirmed", L.booked[i]]] as const).map(([k, l]) => (
        <button key={k} className={status === k ? "on" : ""} onClick={() => setStatus(k)}>{l}</button>))}</div>
      {status === "paid" && <div className="tabs">{(["cash", "upi"] as const).map((k) => <button key={k} className={mode === k ? "on" : ""} onClick={() => setMode(k)}>{L[k][i]}</button>)}</div>}
      <label className="field"><span>{L.note[i]}</span><input className="input" value={note} onChange={(e) => setNote(e.target.value)} /></label>
      {camps.length > 0 && <label className="field"><span>{L.campaign[i]}</span><select className="input" value={camp} onChange={(e) => setCamp(e.target.value ? Number(e.target.value) : "")}>
        <option value="">—</option>{camps.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>}
      {error && <div className="error">{error}</div>}
      <button className="btn block" disabled={busy || !picked.length || cust.mobile.length !== 10 || cust.name.trim().length < 2} onClick={save}>{L.save[i]} · {inr(total)}</button>
    </div>
  );
}

export default function ShopManager({ unitId, lang }: { unitId: number; lang: Lang }) {
  const i = lang === "te" ? 1 : 0;
  const [tab, setTab] = useState<"today" | "orders" | "sale" | "items" | "customers" | "promote" | "enquiries">("today");
  const [sum, setSum] = useState<Summary | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [orders, setOrders] = useState<{ counts: Record<string, number>; rows: Order[] } | null>(null);
  const [filter, setFilter] = useState<"open" | "upcoming" | "credit" | "">("open");
  const [custs, setCusts] = useState<Cust[]>([]);
  const [follow, setFollow] = useState<Follow[]>([]);
  const [promos, setPromos] = useState<Promo[]>([]);
  const [enqs, setEnqs] = useState<Enq[]>([]);
  const [edit, setEdit] = useState<Partial<Listing> | null | false>(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [occ, setOcc] = useState("daily");
  const [plang, setPlang] = useState<Lang>(lang);
  useEffect(() => setPlang(lang), [lang]);
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState<Record<number, { quote: string; text: string }>>({});
  const [enqOrder, setEnqOrder] = useState<Record<number, Record<number, number>>>({});
  const photoRef = useRef<HTMLInputElement>(null);
  const photoFor = useRef<number | null>(null);
  const base = `/market/units/${unitId}`;

  const loadSum = useCallback(() => api<Summary>(`${base}/summary`).then(setSum).catch((e) => setMsg({ ok: false, text: e.message })), [base]);
  const loadListings = useCallback(() => api<Listing[]>(`${base}/listings?lang=${lang}`).then(setListings).catch(() => {}), [base, lang]);
  const loadOrders = useCallback(() => api<{ counts: Record<string, number>; rows: Order[] }>(`${base}/orders?lang=${lang}${filter ? `&when=${filter}` : ""}`).then(setOrders).catch(() => {}), [base, lang, filter]);
  useEffect(() => { loadSum(); loadListings(); }, [loadSum, loadListings]);
  useEffect(() => { if (tab === "orders" || tab === "today") loadOrders(); }, [tab, loadOrders]);
  useEffect(() => {
    if (tab === "customers") { api<Cust[]>(`${base}/customers`).then(setCusts).catch(() => {}); api<Follow[]>(`${base}/followups?lang=${lang}`).then(setFollow).catch(() => {}); }
    if (tab === "promote") api<Promo[]>(`${base}/promo`).then(setPromos).catch(() => {});
    if (tab === "enquiries") api<Enq[]>(`${base}/enquiries`).then(setEnqs).catch(() => {});
  }, [tab, base, lang]);

  const act = async (o: Order, body: object) => {
    setMsg(null);
    try { await api(`/market/orders/${o.id}/status`, { body }); loadOrders(); loadSum(); } catch (e) { setMsg({ ok: false, text: (e as Error).message }); }
  };
  const label = (l: { name: string; name_te?: string | null }) => (lang === "te" ? l.name_te || l.name : l.name);
  const launched = sum?.unit.status === "launched";
  const newCount = orders?.counts.new ?? sum?.new_orders ?? 0;

  const orderCard = (o: Order) => (
    <div key={o.id} className="order-card">
      <div className="row-between"><b>{o.customer.name}</b><span className={`tag ${TAG[o.status]}`}>{o.status_label}{o.outstanding ? ` · ${L.due[i]}` : ""}</span></div>
      <div className="small">{o.lines.map((l) => `${label(l)} × ${l.qty}`).join(", ")}</div>
      <div className="small muted">{o.code} · <a href={`tel:${o.customer.mobile}`}>{o.customer.mobile}</a>{o.date ? ` · ${o.date}` : ""}{o.slot ? ` · ${o.slot}` : ""}{o.source === "online" ? " · online" : o.source === "enquiry" ? " · enquiry" : ""}</div>
      {o.note && <div className="small muted">“{o.note}”</div>}
      {o.rating && <div className="small">{"★".repeat(o.rating)}{o.rating_comment ? ` “${o.rating_comment}”` : ""}</div>}
      <div className="row-between"><b>{inr(o.amount)}</b>
        <span className="row-gap">
          {o.status === "new" && <button className="btn small" onClick={() => act(o, { status: "confirmed" })}>{L.confirm[i]}</button>}
          {["new", "confirmed"].includes(o.status) && <button className="btn small secondary" onClick={() => act(o, { status: "paid", payment_mode: "cash" })}>{L.paidCash[i]}</button>}
          {["new", "confirmed"].includes(o.status) && <button className="btn small secondary" onClick={() => act(o, { status: "paid", payment_mode: "upi" })}>{L.paidUpi[i]}</button>}
          {["new", "confirmed"].includes(o.status) && <button className="btn small ghost" onClick={() => act(o, { status: "delivered", payment_mode: "credit" })}>{L.onCredit[i]}</button>}
          {o.status === "delivered" && <button className="btn small" onClick={() => act(o, { status: "paid", payment_mode: "cash" })}>{L.paidCash[i]}</button>}
          {o.status === "delivered" && <button className="btn small secondary" onClick={() => act(o, { status: "paid", payment_mode: "upi" })}>{L.paidUpi[i]}</button>}
          {!["paid", "cancelled"].includes(o.status) && <button className="btn small ghost danger" onClick={() => { const r = window.prompt(L.why[i]); if (r) act(o, { status: "cancelled", reason: r }); }}>{L.cancel[i]}</button>}
        </span></div>
    </div>);

  return (
    <div className="stack shop">
      <input ref={photoRef} type="file" accept="image/*" hidden onChange={async (e) => {
        const f = e.target.files?.[0]; if (!f || !photoFor.current) return; const fd = new FormData(); fd.append("file", f);
        try { await apiUpload(`/market/listings/${photoFor.current}/photo`, fd); loadListings(); } catch (x) { setMsg({ ok: false, text: (x as Error).message }); }
        if (photoRef.current) photoRef.current.value = ""; }} />
      <div className="tabs shop-tabs">{([["today", L.today[i]], ["orders", `${L.orders[i]}${newCount ? ` (${newCount})` : ""}`], ["sale", L.sale[i]], ["items", L.items[i]],
        ["customers", L.customers[i]], ["promote", L.promote[i]], ["enquiries", L.enquiries[i]]] as const).map(([k, l]) => (
        <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>))}</div>
      {msg && <div className={msg.ok ? "notice ok-notice" : "error"}>{msg.text}</div>}

      {tab === "today" && sum && (
        <div className="stack">
          <div className="shop-tiles">
            <div><small>{L.salesToday[i]}</small><b>{inr(sum.today)}</b></div>
            <div><small>{L.month[i]}</small><b>{inr(sum.month)}</b><small>{sum.month_orders} {L.ordersN[i]}</small></div>
            <div className={sum.new_orders ? "hot" : ""}><small>{L.newOrders[i]}</small><b>{sum.new_orders}</b></div>
            <div><small>{L.bookings[i]}</small><b>{sum.upcoming_bookings}</b></div>
            <div className={sum.outstanding ? "warn" : ""}><small>{L.credit[i]}</small><b>{inr(sum.outstanding)}</b></div>
            <div><small>{L.rating[i]}</small><b>{sum.rating ? `★ ${sum.rating}` : "—"}</b><small>{sum.ratings}</small></div>
          </div>
          <div className="card stack"><b className="small">{L.last30[i]}</b><Bars data={sum.daily} /></div>
          {sum.top_items.length > 0 && <div className="card stack"><b className="small">{L.top[i]}</b>{sum.top_items.map((t) => <div key={t.name} className="row-between small"><span>{t.name}</span><b>{inr(t.amount)}</b></div>)}</div>}
          {orders && orders.rows.filter((o) => ["new", "confirmed"].includes(o.status)).slice(0, 5).map(orderCard)}
          {launched ? <div className="card small"><Store size={16} /> {L.shopLink[i]}: <a href={sum.unit.shop_url} target="_blank" rel="noreferrer">{sum.unit.shop_url}</a></div>
            : <div className="notice small">{L.notLaunched[i]}</div>}
        </div>)}

      {tab === "orders" && (
        <div className="stack">
          <div className="tabs">{([["open", L.open[i]], ["upcoming", L.upcoming[i]], ["credit", L.creditTab[i]], ["", L.all[i]]] as const).map(([k, l]) => (
            <button key={k} className={filter === k ? "on" : ""} onClick={() => setFilter(k)}>{l}</button>))}</div>
          {orders?.rows.map(orderCard)}
          {orders && !orders.rows.length && <div className="card muted">{L.noOrders[i]}</div>}
        </div>)}

      {tab === "sale" && (listings.length ? <div className="card"><SaleForm unitId={unitId} listings={listings} lang={lang} onDone={(o) => { setMsg({ ok: true, text: `${L.saved[i]}: ${o.code} · ${inr(o.amount)}` }); loadSum(); }} /></div>
        : <div className="card stack"><p style={{ margin: 0 }}>{L.addItem[i]}</p><button className="btn" onClick={async () => { await api(`${base}/listings/from-model`, { method: "POST" }); loadListings(); }}>{L.fromPlan[i]}</button></div>)}

      {tab === "items" && (
        <div className="stack">
          <div className="row-gap">
            <button className="btn" onClick={() => setEdit(null)}><Plus size={16} /> {L.addItem[i]}</button>
            {!listings.length && <button className="btn secondary" onClick={async () => { await api(`${base}/listings/from-model`, { method: "POST" }); loadListings(); }}>{L.fromPlan[i]}</button>}
          </div>
          <div className="listing-grid">
            {listings.map((l) => (
              <div key={l.id} className={`card listing ${l.available ? "" : "off"}`}>
                <div className="listing-photo">{l.photos[0] ? <img src={apiUrl(l.photos[0].url)} alt="" /> : <ImagePlus />}</div>
                <div className="stack" style={{ gap: 4 }}>
                  <b>{label(l)}</b><span className="small">{inr(l.price)} / {l.price_unit}{l.kind === "service" ? ` · ${L.service[i]}` : ""}</span>
                  {l.slots.length > 0 && <span className="small muted">{l.slots.map((s) => `${s.label}${s.capacity ? ` (${s.capacity})` : ""}`).join(" · ")}</span>}
                  {!l.available && <span className="tag grey">off</span>}
                  <div className="row-gap">
                    <button className="btn ghost small" onClick={() => setEdit(l)}>Edit</button>
                    <button className="btn ghost small" aria-label={`${L.photo[i]} ${l.name}`} onClick={() => { photoFor.current = l.id; photoRef.current?.click(); }}><Camera size={14} /></button>
                    {l.photos.length > 0 && <button className="btn ghost small danger" aria-label="Remove photo" onClick={async () => { await api(`/market/listings/${l.id}/photo/0`, { method: "DELETE" }); loadListings(); }}><Trash2 size={14} /></button>}
                  </div>
                </div>
              </div>))}
          </div>
        </div>)}

      {tab === "customers" && (
        <div className="stack">
          {follow.length > 0 && (
            <div className="card stack">
              <b>{L.follow[i]}</b>
              {follow.map((f) => (
                <div key={f.customer_id} className="row-between small">
                  <span><b>{f.name}</b> · {f.orders} {L.ordersN[i]}<div className="muted">{L.followNote[i]} {f.days} {L.days[i]}</div></span>
                  <span className="row-gap">
                    <a className="btn small" href={f.wa_link} target="_blank" rel="noreferrer"><MessageCircle size={14} /> WhatsApp</a>
                    <button className="btn small ghost" onClick={async () => { await api(`${base}/followups`, { body: { customer_id: f.customer_id } }); setFollow(follow.filter((x) => x.customer_id !== f.customer_id)); }}>{L.done[i]}</button>
                  </span>
                </div>))}
            </div>)}
          <div className="card table-wrap">
            <table className="table compact">
              <thead><tr><th>{L.customers[i]}</th><th className="num">{L.ordersN[i]}</th><th className="num">{L.spend[i]}</th><th className="num">{L.due[i]}</th></tr></thead>
              <tbody>{custs.map((c) => (
                <tr key={c.id}><td><b>{c.name}</b><div className="small muted"><a href={`tel:${c.mobile}`}>{c.mobile}</a>{c.organisation ? ` · ${c.organisation}` : ""}{c.village ? ` · ${c.village}` : ""}</div></td>
                  <td className="num">{c.orders}</td><td className="num">{inr(c.spend)}</td><td className="num">{c.outstanding ? inr(c.outstanding) : "—"}</td></tr>))}
                {!custs.length && <tr><td colSpan={4} className="muted">—</td></tr>}</tbody>
            </table>
          </div>
        </div>)}

      {tab === "promote" && (
        <div className="stack">
          <div className="card stack">
            <div className="grid-2">
              <label className="field"><span>{L.occasion[i]}</span><select className="input" value={occ} onChange={(e) => setOcc(e.target.value)}>{OCC.map(([k, en, te]) => <option key={k} value={k}>{lang === "te" ? te : en}</option>)}</select></label>
              <label className="field"><span>{L.language[i]}</span><select className="input" value={plang} onChange={(e) => setPlang(e.target.value as Lang)}><option value="te">తెలుగు</option><option value="en">English</option></select></label>
            </div>
            <button className="btn" disabled={busy} onClick={async () => { setBusy(true); setMsg(null);
              try { const p = await api<Promo>(`${base}/promo`, { body: { lang: plang, occasion: occ } }); setPromos([p, ...promos]); } catch (e) { setMsg({ ok: false, text: (e as Error).message }); } finally { setBusy(false); } }}>
              <Sparkles size={16} /> {busy ? "…" : L.makePoster[i]}</button>
          </div>
          {promos.map((p) => (
            <div key={p.id} className="card promo">
              <a href={apiUrl(p.poster_url)} target="_blank" rel="noreferrer"><img src={apiUrl(p.poster_url)} alt={p.title} /></a>
              <div className="stack" style={{ gap: 8 }}>
                <pre className="promo-msg">{p.message}</pre>
                <div className="row-gap">
                  <a className="btn small" href={p.share_link} target="_blank" rel="noreferrer"><Share2 size={14} /> {L.share[i]}</a>
                  <button className="btn small secondary" onClick={() => navigator.clipboard?.writeText(p.message).then(() => setMsg({ ok: true, text: L.copied[i] }))}><Copy size={14} /> {L.copy[i]}</button>
                  <a className="btn small ghost" href={apiUrl(p.poster_url)} download={`poster-${p.id}.png`}>{L.download[i]}</a>
                </div>
                <small className="muted">{p.source === "ai" ? "AI" : "Template"} · {new Date(p.at).toLocaleString()}</small>
              </div>
            </div>))}
        </div>)}

      {tab === "enquiries" && (
        <div className="stack">
          {!enqs.length && <div className="card muted">{L.noEnq[i]}</div>}
          {enqs.map((e) => {
            const r = reply[e.route.id] ?? { quote: e.route.quote_amount ? String(e.route.quote_amount) : "", text: e.route.reply ?? "" };
            const q = enqOrder[e.route.id] ?? {};
            return (
              <div key={e.id} className="card stack">
                <div className="row-between"><b>{e.buyer.organisation || e.buyer.name}</b><span className={`tag ${e.route.status === "won" ? "ok" : e.route.status === "interested" ? "amber" : "grey"}`}>{e.route.status}</span></div>
                <div className="small">{L.need[i]}: {e.need}{e.quantity ? ` · ${e.quantity}` : ""}{e.needed_by ? ` · ${L.by[i]} ${e.needed_by}` : ""}</div>
                <div className="small muted">{e.code} · {e.buyer.name} · {e.buyer.mobile.includes("x") ? e.buyer.mobile : <a href={`tel:${e.buyer.mobile}`}>{e.buyer.mobile}</a>}</div>
                {["sent", "interested"].includes(e.route.status) && (
                  <>
                    <div className="row-gap">
                      <input className="input" aria-label={L.quote[i]} placeholder={L.quote[i]} inputMode="decimal" style={{ width: 140 }} value={r.quote} onChange={(x) => setReply({ ...reply, [e.route.id]: { ...r, quote: x.target.value } })} />
                      <input className="input" aria-label={L.reply[i]} placeholder={L.reply[i]} style={{ flex: 1, minWidth: 160 }} value={r.text} onChange={(x) => setReply({ ...reply, [e.route.id]: { ...r, text: x.target.value } })} />
                    </div>
                    <div className="row-gap">
                      <button className="btn small" onClick={async () => setEnqs(await api<Enq[]>(`/market/routes/${e.route.id}/reply`, { body: { status: "interested", quote_amount: Number(r.quote) || null, reply: r.text || null } }))}>{L.interested[i]}</button>
                      {e.route.status === "sent" && <button className="btn small ghost" onClick={async () => setEnqs(await api<Enq[]>(`/market/routes/${e.route.id}/reply`, { body: { status: "declined", reply: r.text || null } }))}>{L.decline[i]}</button>}
                    </div>
                  </>)}
                {e.route.status === "interested" && (
                  <div className="stack" style={{ gap: 6 }}>
                    <b className="small">{L.makeOrder[i]}</b>
                    {listings.filter((l) => l.available).map((l) => (
                      <div key={l.id} className="row-between small"><span>{label(l)} · {inr(l.price)}</span>
                        <input className="input" aria-label={`${L.qty[i]} ${l.name}`} inputMode="decimal" style={{ width: 90 }} value={q[l.id] ?? ""} onChange={(x) => setEnqOrder({ ...enqOrder, [e.route.id]: { ...q, [l.id]: Number(x.target.value) || 0 } })} /></div>))}
                    <div><button className="btn small" disabled={!Object.values(q).some((v) => v > 0)} onClick={async () => {
                      try { await api(`/market/routes/${e.route.id}/order`, { body: { lines: Object.entries(q).filter(([, v]) => v > 0).map(([id, v]) => ({ listing_id: Number(id), qty: v })) } });
                        setEnqs(await api<Enq[]>(`${base}/enquiries`)); setMsg({ ok: true, text: L.saved[i] }); loadSum(); } catch (x) { setMsg({ ok: false, text: (x as Error).message }); } }}>{L.makeOrder[i]}</button></div>
                  </div>)}
              </div>);
          })}
        </div>)}

      {edit !== false && <ListingForm li={edit} lang={lang} onClose={() => setEdit(false)} onSave={async (b) => {
        try { await api(edit?.id ? `/market/listings/${edit.id}` : `${base}/listings`, { method: edit?.id ? "PUT" : "POST", body: b }); setEdit(false); loadListings(); }
        catch (e) { setMsg({ ok: false, text: (e as Error).message }); setEdit(false); } }} />}
    </div>
  );
}
