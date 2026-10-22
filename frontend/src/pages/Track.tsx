// Public order tracking (link sent to the customer): status history and a rating after delivery.
import { Star } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import Logo from "../components/Logo";

type O = { code: string; amount: number; status: string; status_label: string; date: string | null; slot: string | null; can_rate: boolean; rating: number | null;
  lines: { name: string; name_te?: string | null; qty: number; price: number }[]; unit: { name: string; code: string }; events: { status: string; label: string; at: string }[] };

export default function Track() {
  const { code = "" } = useParams();
  const [sp] = useSearchParams();
  const t = sp.get("t") ?? "";
  const [lang, setLang] = useState<"en" | "te">("te");
  const [o, setO] = useState<O | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stars, setStars] = useState(0);
  const [comment, setComment] = useState("");
  const [thanks, setThanks] = useState(false);
  useEffect(() => {
    api<O>(`/public/orders/${code}?t=${encodeURIComponent(t)}&lang=${lang}`).then(setO).catch((e) => setError(e.message));
  }, [code, t, lang, thanks]);
  const te = lang === "te";
  return (
    <div className="public-shop">
      <header className="pub-top"><Logo tone="light" size={30} /><div className="spacer" />
        <div className="lang-toggle" role="group" aria-label="Language"><button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button><button className={lang === "te" ? "on" : ""} onClick={() => setLang("te")}>తె</button></div></header>
      <main className="page stack">
        {error && <div className="card">{error}</div>}
        {o && (
          <>
            <div className="card stack">
              <div className="row-between"><b>{o.unit.name}</b><span className={`tag ${o.status === "paid" || o.status === "delivered" ? "ok" : o.status === "cancelled" ? "grey" : "amber"}`}>{o.status_label}</span></div>
              <div className="small muted">{o.code}{o.date ? ` · ${o.date}` : ""}{o.slot ? ` · ${o.slot}` : ""}</div>
              {o.lines.map((l, k) => <div key={k} className="row-between small"><span>{te ? l.name_te || l.name : l.name} × {l.qty}</span><span>₹{(l.qty * l.price).toLocaleString("en-IN")}</span></div>)}
              <div className="row-between"><b>{te ? "మొత్తం" : "Total"}</b><b>₹{o.amount.toLocaleString("en-IN")}</b></div>
            </div>
            <ol className="loan-timeline card">{[...o.events].reverse().map((e, k) => <li key={k}><b>{e.label}</b><small className="muted">{new Date(e.at).toLocaleString(te ? "te-IN" : "en-IN")}</small></li>)}</ol>
            {o.can_rate && !thanks && (
              <div className="card stack">
                <b>{te ? "మీ అనుభవం ఎలా ఉంది?" : "How was it?"}</b>
                <div className="stars">{[1, 2, 3, 4, 5].map((n) => <button key={n} aria-label={`${n} stars`} onClick={() => setStars(n)}><Star size={30} fill={n <= stars ? "#f6a821" : "none"} color="#f6a821" /></button>)}</div>
                <input className="input" placeholder={te ? "ఏదైనా చెప్పాలనుకుంటున్నారా?" : "Anything to add?"} value={comment} onChange={(e) => setComment(e.target.value)} />
                <button className="btn" disabled={!stars} onClick={async () => { await api(`/public/orders/${code}/rate?t=${encodeURIComponent(t)}`, { body: { stars, comment: comment || null } }); setThanks(true); }}>{te ? "పంపండి" : "Send"}</button>
              </div>)}
            {(thanks || o.rating) && <div className="notice ok-notice">{te ? "ధన్యవాదాలు!" : "Thank you!"} {"★".repeat(o.rating ?? stars)}</div>}
          </>)}
      </main>
    </div>
  );
}
