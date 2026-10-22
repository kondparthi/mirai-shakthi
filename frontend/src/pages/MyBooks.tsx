// Entrepreneur app – "My accounts": daily sales and expenses (speak or type), money to collect, stock, loan EMIs and
// monthly summaries for the unit(s) they run (M9).
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import BooksManager from "../components/books/BooksManager";
import { useLang } from "../i18n";

type U = { id: number; code: string; name: string; status: string; model: string | null };

export default function MyBooks() {
  const { lang } = useLang();
  const [units, setUnits] = useState<U[] | null>(null);
  const [uid, setUid] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<U[]>(`/market/my-units?lang=${lang}`).then((r) => { setUnits(r); setUid((cur) => cur ?? r[0]?.id ?? null); }).catch((e) => setError(e.message));
  }, [lang]);
  if (error) return <div className="error">{error}</div>;
  if (!units) return <div className="muted">…</div>;
  const te = lang === "te";
  return (
    <div className="stack">
      <Link to="/programme" className="small">← {te ? "కార్యక్రమం" : "Programme"}</Link>
      <h1 style={{ margin: 0 }}>{te ? "నా లెక్కలు" : "My accounts"}</h1>
      {!units.length && <div className="card">{te ? "మీ వ్యాపారం ఏర్పాటైన తర్వాత ఇక్కడ రోజువారీ అమ్మకాలు, ఖర్చులు నమోదు చేయవచ్చు." : "Once your enterprise is set up, keep your daily sales and expenses here."}</div>}
      {units.length > 1 && <select className="input" aria-label="Unit" value={uid ?? ""} onChange={(e) => setUid(Number(e.target.value))}>{units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select>}
      {uid && <BooksManager key={uid} unitId={uid} lang={lang} />}
    </div>
  );
}
