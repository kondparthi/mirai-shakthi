// Supplier portal (limited): quotation requests, submit a quotation with a file, confirm orders and report delivery.
import { Download, FileUp, PackageCheck, Truck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiUpload, openLink, type User } from "../api";
import { useAuth } from "../auth";
import Logo from "../components/Logo";
import UserMenu from "../components/UserMenu";

type Rfq = {
  id: number; title: string; unit: string; unit_code: string; district: string | null; items: { item: string; spec: string; qty: number }[];
  quote_by: string | null; status: string; status_label: string; won: boolean;
  my_quote: { amount: number; lines: { item: string; qty: number; rate: number }[]; delivery_days: number | null; warranty_months: number | null;
    valid_till: string | null; note: string | null; file_url: string | null } | null;
  po_number?: string; po_date?: string; po_amount?: number; expected_delivery?: string | null; confirmed?: boolean; deliver_to?: string; contact?: string;
  delivered_on?: string | null; installed_on?: string | null;
};
type Me = { supplier: { id: number; name: string; items: string[]; districts: string[] }; open: Rfq[]; orders: Rfq[]; closed: Rfq[] };
const inr = (n: number | null | undefined) => (n == null ? "—" : `₹${Math.round(n).toLocaleString("en-IN")}`);
const day = (d?: string | null) => (d ? new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—");
const today = () => new Date().toISOString().slice(0, 10);

function SupplierLogin() {
  const { signIn } = useAuth();
  const [f, setF] = useState({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="login">
      <div className="hero"><div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}><Logo tone="light" size={46} /></div>
        <h1>Supplier portal</h1><p className="muted">Quotations, orders and deliveries for MIRAI Shakthi units.</p></div>
      <form className="card stack" onSubmit={async (e) => { e.preventDefault(); setError(null);
        try { const r = await api<{ token: string; user: User }>("/auth/staff/login", { body: f }); signIn(r.token, r.user); } catch (x) { setError((x as Error).message); } }}>
        <label className="field"><span>Email</span><input className="input" type="email" autoComplete="username" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
        <label className="field"><span>Password</span><input className="input" type="password" autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></label>
        {error && <div className="error">{error}</div>}
        <button className="btn block" disabled={!f.email || !f.password}>Sign in</button>
      </form>
      <p className="small muted" style={{ textAlign: "center", marginTop: 16 }}>Your login is created by MIRAI's procurement team.</p>
    </div>
  );
}

function QuoteBox({ r, onDone }: { r: Rfq; onDone: (m: Me) => void }) {
  const [rates, setRates] = useState<Record<string, number>>(Object.fromEntries(r.items.map((i) => [i.item, r.my_quote?.lines.find((l) => l.item === i.item)?.rate ?? 0])));
  const [f, setF] = useState({ delivery_days: r.my_quote?.delivery_days ?? 7, warranty_months: r.my_quote?.warranty_months ?? 12, valid_till: r.my_quote?.valid_till ?? "", note: r.my_quote?.note ?? "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const total = r.items.reduce((a, i) => a + i.qty * (rates[i.item] || 0), 0);
  const send = async () => {
    setBusy(true); setError(null);
    try {
      onDone(await api<Me>(`/supplier/rfqs/${r.id}/quote`, { body: { lines: r.items.map((i) => ({ item: i.item, qty: i.qty, rate: rates[i.item] })),
        delivery_days: f.delivery_days, warranty_months: f.warranty_months, valid_till: f.valid_till || null, note: f.note || null } }));
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <table className="table compact">
        <thead><tr><th>Item</th><th className="num">Qty</th><th className="num">Your rate (₹, incl. GST)</th><th className="num">Amount</th></tr></thead>
        <tbody>{r.items.map((i) => (
          <tr key={i.item}><td>{i.item}<div className="small muted">{i.spec}</div></td><td className="num">{i.qty}</td>
            <td className="num"><input className="input" type="number" min={0} aria-label={`Rate for ${i.item}`} style={{ width: 120 }} value={rates[i.item] || ""}
              onChange={(e) => setRates({ ...rates, [i.item]: Number(e.target.value) })} /></td><td className="num">{inr(i.qty * (rates[i.item] || 0))}</td></tr>))}
          <tr className="total-row"><td colSpan={3}>Total</td><td className="num">{inr(total)}</td></tr></tbody>
      </table>
      <div className="grid-3">
        <label className="field"><span>Delivery (days)</span><input className="input" type="number" min={0} value={f.delivery_days} onChange={(e) => setF({ ...f, delivery_days: Number(e.target.value) })} /></label>
        <label className="field"><span>Warranty (months)</span><input className="input" type="number" min={0} value={f.warranty_months} onChange={(e) => setF({ ...f, warranty_months: Number(e.target.value) })} /></label>
        <label className="field"><span>Valid till</span><input className="input" type="date" min={today()} value={f.valid_till} onChange={(e) => setF({ ...f, valid_till: e.target.value })} /></label>
      </div>
      <label className="field"><span>Note</span><input className="input" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></label>
      {error && <div className="error">{error}</div>}
      <div className="row-gap">
        <button className="btn" disabled={busy || r.items.some((i) => !(rates[i.item] > 0))} onClick={send}>{r.my_quote ? "Update quotation" : "Send quotation"}</button>
        {r.my_quote && <>
          <input ref={fileRef} type="file" accept="application/pdf,image/*" hidden onChange={async (e) => {
            const file = e.target.files?.[0]; if (!file) return; const fd = new FormData(); fd.append("file", file);
            try { onDone(await apiUpload<Me>(`/supplier/rfqs/${r.id}/quote/file`, fd)); } catch (x) { setError((x as Error).message); } }} />
          <button className="btn secondary" onClick={() => fileRef.current?.click()}><FileUp size={15} /> {r.my_quote.file_url ? "Replace" : "Attach"} signed quotation</button></>}
      </div>
    </div>
  );
}

export default function SupplierApp() {
  const { user, signOut } = useAuth();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"open" | "orders" | "closed">("open");
  const [openId, setOpenId] = useState<number | null>(null);
  const [dates, setDates] = useState<Record<number, string>>({});
  const load = useCallback(() => api<Me>("/supplier/me").then(setMe).catch((e) => setError(e.message)), []);
  useEffect(() => {
    if (user?.role === "supplier") load();
  }, [user, load]);
  if (!user || user.role !== "supplier") return <SupplierLogin />;
  const act = async (fn: () => Promise<Me>) => { setError(null); try { setMe(await fn()); } catch (e) { setError((e as Error).message); } };
  const list = me ? me[tab] : [];
  return (
    <div className="shell no-side">
      <header className="topbar"><div className="brand"><Logo tone="light" size={32} /></div><div className="spacer" />
        <UserMenu name={me?.supplier.name ?? user.name ?? "Supplier"} sub="Supplier" detail={user.email ?? undefined} onSignOut={signOut} /></header>
      <main className="page stack">
        <h1 style={{ margin: 0 }}>{me?.supplier.name ?? "Supplier portal"}</h1>
        {error && <div className="error">{error}</div>}
        <div className="tabs">{([["open", `Quotation requests (${me?.open.length ?? 0})`], ["orders", `Orders (${me?.orders.length ?? 0})`], ["closed", "Closed"]] as const).map(([k, l]) => (
          <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>))}</div>
        {me && list.length === 0 && <div className="card muted">{tab === "open" ? "No open requests. MIRAI will ask you when a unit needs your items." : "Nothing here yet."}</div>}
        {list.map((r) => (
          <div key={r.id} className="card stack">
            <div className="row-between"><b>{r.title} – {r.unit}</b><span className={`tag ${r.won ? "ok" : r.status === "rfq" ? "amber" : "grey"}`}>{r.status_label}</span></div>
            <div className="small muted">{r.unit_code} · {r.district}{r.quote_by && tab === "open" ? ` · quote by ${day(r.quote_by)}` : ""}{r.my_quote ? ` · your quotation ${inr(r.my_quote.amount)}` : ""}</div>
            {tab === "open" && (openId === r.id ? <QuoteBox r={r} onDone={(m) => { setMe(m); setOpenId(null); }} />
              : <div className="row-gap"><span className="small">{r.items.map((i) => `${i.item} × ${i.qty}`).join(" · ")}</span>
                <button className="btn small" onClick={() => setOpenId(r.id)}>{r.my_quote ? "Change quotation" : "Quote"}</button></div>)}
            {tab === "orders" && (
              <>
                <div className="kv"><span>Purchase order</span><b>{r.po_number} · {day(r.po_date)} · {inr(r.po_amount)}</b></div>
                <div className="kv"><span>Deliver to</span><b>{r.deliver_to}</b></div>
                <div className="kv"><span>Contact</span><b>{r.contact}</b></div>
                <div className="kv"><span>Deliver by</span><b>{day(r.expected_delivery)}{r.confirmed ? " (confirmed)" : ""}</b></div>
                <div className="row-gap">
                  <button className="btn secondary small" onClick={() => openLink(`/supplier/orders/${r.id}/po-link`).catch((e) => setError(e.message))}><Download size={14} /> PO (PDF)</button>
                  {r.status === "ordered" && <>
                    <input className="input" type="date" aria-label="Delivery date" min={today()} style={{ width: 170 }} value={dates[r.id] ?? r.expected_delivery ?? ""} onChange={(e) => setDates({ ...dates, [r.id]: e.target.value })} />
                    <button className="btn small" disabled={!(dates[r.id] ?? r.expected_delivery)} onClick={() => act(() => api<Me>(`/supplier/orders/${r.id}/confirm`, { body: { expected_delivery: dates[r.id] ?? r.expected_delivery } }))}>
                      <PackageCheck size={14} /> {r.confirmed ? "Change date" : "Confirm order"}</button>
                    <button className="btn small secondary" onClick={() => window.confirm("Mark as delivered today?") && act(() => api<Me>(`/supplier/orders/${r.id}/delivered`, { body: { on: today() } }))}><Truck size={14} /> Delivered</button></>}
                  {r.delivered_on && <span className="tag ok">delivered {day(r.delivered_on)}</span>}
                  {r.installed_on && <span className="tag ok">installed {day(r.installed_on)}</span>}
                </div>
              </>)}
          </div>))}
      </main>
    </div>
  );
}
