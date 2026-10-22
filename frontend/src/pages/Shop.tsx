// Public shop page (no login): a launched unit's products and services; customers order or book with name and mobile.
import { Minus, Plus, ShoppingBag, Star } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, apiUrl } from "../api";
import Logo from "../components/Logo";

type Listing = { id: number; kind: string; name: string; name_te: string | null; label: string; description: string | null; photos: { url: string }[];
  price: number; price_unit: string; slots: { label: string; capacity: number | null }[]; daily_capacity: number | null };
type ShopData = { code: string; name: string; model: string | null; place: string; rating: number | null; ratings: number; listings: Listing[] };
const T = {
  order: ["Place order", "ఆర్డర్ చేయండి"], book: ["Book", "బుక్ చేయండి"], name: ["Your name", "మీ పేరు"], mobile: ["Mobile number", "మొబైల్ నంబర్"],
  village: ["Village / area", "గ్రామం / ప్రాంతం"], address: ["Delivery address (optional)", "చిరునామా (ఐచ్ఛికం)"], date: ["Date", "తేదీ"], slot: ["Time", "సమయం"],
  total: ["Total", "మొత్తం"], left: ["left", "మిగిలింది"], full: ["full", "నిండిపోయింది"], thanks: ["Order sent! The shop will call you to confirm.", "ఆర్డర్ పంపబడింది! షాప్ వారు ఫోన్ చేసి నిర్ధారిస్తారు."],
  track: ["Track your order", "మీ ఆర్డర్ స్థితి చూడండి"], closed: ["This shop is not open.", "ఈ షాప్ తెరిచి లేదు."], note: ["Note for the shop", "షాప్‌కు గమనిక"],
  pay: ["Pay cash or UPI when you receive it.", "అందుకున్నప్పుడు నగదు లేదా యూపీఐతో చెల్లించండి."],
};

export default function Shop() {
  const { code = "" } = useParams();
  const [lang, setLang] = useState<"en" | "te">("te");
  const i = lang === "te" ? 1 : 0;
  const [s, setS] = useState<ShopData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [qty, setQty] = useState<Record<number, number>>({});
  const [f, setF] = useState({ name: "", mobile: "", village: "", address: "", date: new Date(Date.now() + 864e5).toISOString().slice(0, 10), slot: "", note: "" });
  const [avail, setAvail] = useState<{ date: string; slots: { label: string | null; left: number | null }[] }[]>([]);
  const [done, setDone] = useState<{ code: string; track_url: string; amount: number } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api<ShopData>(`/public/shop/${code}?lang=${lang}`).then(setS).catch((e) => setError(e.message));
  }, [code, lang]);
  const picked = useMemo(() => (s?.listings ?? []).filter((l) => (qty[l.id] ?? 0) > 0), [s, qty]);
  const service = picked.find((l) => l.kind === "service");
  useEffect(() => {
    if (service) api<typeof avail>(`/public/shop/${code}/availability/${service.id}`).then(setAvail).catch(() => {});
  }, [service, code]);
  const total = picked.reduce((a, l) => a + l.price * qty[l.id], 0);
  const day = avail.find((d) => d.date === f.date);
  const send = async () => {
    setBusy(true); setError(null);
    try {
      setDone(await api(`/public/shop/${code}/orders`, { body: { name: f.name, mobile: f.mobile, village: f.village || null, address: f.address || null, note: f.note || null,
        lines: picked.map((l) => ({ listing_id: l.id, qty: qty[l.id] })), date: service ? f.date : null, slot: service?.slots.length ? f.slot : null } }));
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="public-shop">
      <header className="pub-top"><Logo tone="light" size={30} /><div className="spacer" />
        <div className="lang-toggle" role="group" aria-label="Language"><button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button><button className={lang === "te" ? "on" : ""} onClick={() => setLang("te")}>తె</button></div></header>
      <main className="page stack">
        {error && !s && <div className="card">{T.closed[i]}</div>}
        {s && (
          <>
            <div className="plan-hero"><h2 style={{ marginTop: 0 }}>{s.name}</h2><div className="small">{s.model} · {s.place}</div>
              {s.rating && <div className="small" style={{ marginTop: 6 }}><Star size={14} fill="#ffd27a" color="#ffd27a" /> {s.rating} ({s.ratings})</div>}</div>
            {done ? (
              <div className="card stack"><b>{T.thanks[i]}</b><div>{done.code} · ₹{done.amount.toLocaleString("en-IN")}</div><div className="small muted">{T.pay[i]}</div>
                <Link className="btn" to={done.track_url}>{T.track[i]}</Link></div>
            ) : (
              <>
                <div className="stack">{s.listings.map((l) => (
                  <div key={l.id} className={`sale-item ${(qty[l.id] ?? 0) > 0 ? "on" : ""}`}>
                    {l.photos[0] ? <img src={apiUrl(l.photos[0].url)} alt="" /> : <span className="ph"><ShoppingBag size={20} /></span>}
                    <div style={{ flex: 1, minWidth: 0 }}><b>{l.label}</b><small>₹{l.price.toLocaleString("en-IN")} / {l.price_unit}</small>{l.description && <small className="muted">{l.description}</small>}</div>
                    <div className="stepper">
                      <button aria-label="Less" onClick={() => setQty({ ...qty, [l.id]: Math.max(0, (qty[l.id] ?? 0) - 1) })}><Minus size={14} /></button>
                      <input aria-label={`Quantity ${l.name}`} inputMode="decimal" value={qty[l.id] ?? 0} onChange={(e) => setQty({ ...qty, [l.id]: Number(e.target.value) || 0 })} />
                      <button aria-label="More" onClick={() => setQty({ ...qty, [l.id]: (qty[l.id] ?? 0) + 1 })}><Plus size={14} /></button>
                    </div>
                  </div>))}</div>
                {picked.length > 0 && (
                  <div className="card stack">
                    <div className="row-between"><b>{T.total[i]}</b><b>₹{total.toLocaleString("en-IN")}</b></div>
                    {service && (
                      <div className="grid-2">
                        <label className="field"><span>{T.date[i]}</span><select className="input" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value, slot: "" })}>
                          {avail.map((d) => <option key={d.date} value={d.date}>{new Date(d.date + "T00:00:00").toLocaleDateString(lang === "te" ? "te-IN" : "en-IN", { weekday: "short", day: "numeric", month: "short" })}</option>)}</select></label>
                        {service.slots.length > 0 && <label className="field"><span>{T.slot[i]}</span><select className="input" value={f.slot} onChange={(e) => setF({ ...f, slot: e.target.value })}>
                          <option value="">—</option>{day?.slots.map((x) => <option key={x.label} value={x.label ?? ""} disabled={x.left != null && x.left <= 0}>{x.label}{x.left != null ? ` (${x.left > 0 ? `${x.left} ${T.left[i]}` : T.full[i]})` : ""}</option>)}</select></label>}
                      </div>)}
                    <label className="field"><span>{T.name[i]}</span><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
                    <label className="field"><span>{T.mobile[i]}</span><input className="input" inputMode="numeric" maxLength={10} value={f.mobile} onChange={(e) => setF({ ...f, mobile: e.target.value.replace(/\D/g, "") })} /></label>
                    <label className="field"><span>{T.village[i]}</span><input className="input" value={f.village} onChange={(e) => setF({ ...f, village: e.target.value })} /></label>
                    <label className="field"><span>{T.address[i]}</span><input className="input" value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></label>
                    <label className="field"><span>{T.note[i]}</span><input className="input" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></label>
                    {error && <div className="error">{error}</div>}
                    <button className="btn block" disabled={busy || f.name.trim().length < 2 || f.mobile.length !== 10 || (!!service?.slots.length && !f.slot)} onClick={send}>
                      {service ? T.book[i] : T.order[i]} · ₹{total.toLocaleString("en-IN")}</button>
                    <small className="muted">{T.pay[i]}</small>
                  </div>)}
              </>)}
          </>)}
        <p className="small muted" style={{ textAlign: "center" }}>MIRAI Shakthi</p>
      </main>
    </div>
  );
}
