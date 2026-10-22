// Collective marketing campaigns (Form 8.3): fairs, festivals, WhatsApp and institutional drives across units, with results.
import { FileUp, Plus, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiUpload, apiUrl } from "../../api";
import { useMaster } from "../../components/masters";
import { fmtDay, inr, inrShort } from "../dpr/common";
import { Field, Modal } from "../ui";

type C = { id: number; name: string; start_date: string; end_date: string; sectors: string[]; sector_names: string[]; unit_ids: number[]; channels: string[];
  venue: string | null; district: string | null; district_name: string | null; budget: number | null; state: string;
  results: { enquiries: number; orders: number; sales: number; app_orders: number; app_sales: number }; enquiries: number | null; manual_orders: number | null; manual_sales: number | null;
  message_en?: string | null; message_te?: string | null; note?: string | null; materials?: { file: string; title: string; url: string }[];
  units?: { id: number; name: string; code: string | null; orders: number; sales: number }[] };
type U = { id: number; name: string; code: string; model: string | null; district_name: string | null };
const CH: [string, string][] = [["fair", "Fair / mela"], ["whatsapp", "WhatsApp"], ["social", "Social media"], ["institutional", "Institutional buyers"]];

export default function Campaigns() {
  const sectors = useMaster("sector");
  const districts = useMaster("district");
  const [rows, setRows] = useState<C[] | null>(null);
  const [units, setUnits] = useState<U[]>([]);
  const [edit, setEdit] = useState<C | "new" | null>(null);
  const [view, setView] = useState<C | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const today = new Date().toISOString().slice(0, 10);
  const [f, setF] = useState<Record<string, unknown>>({});
  const load = useCallback(() => api<C[]>("/market/campaigns").then(setRows).catch(() => setRows([])), []);
  useEffect(() => { load(); api<{ rows: U[] }>("/setup/units?status=launched").then((r) => setUnits(r.rows)).catch(() => {}); }, [load]);
  const startEdit = (c: C | "new") => {
    setError(null); setEdit(c);
    setF(c === "new" ? { name: "", start_date: today, end_date: today, sectors: ["food"], unit_ids: [], channels: ["fair"], venue: "", district: "", budget: "" }
      : { ...c, venue: c.venue ?? "", district: c.district ?? "", budget: c.budget ?? "", enquiries: c.enquiries ?? "", manual_orders: c.manual_orders ?? "", manual_sales: c.manual_sales ?? "" });
  };
  const arr = (k: string) => (f[k] as (string | number)[]) ?? [];
  const tog = (k: string, v: string | number) => setF({ ...f, [k]: arr(k).includes(v) ? arr(k).filter((x) => x !== v) : [...arr(k), v] });
  const save = async () => {
    setError(null);
    const num = (v: unknown) => (v === "" || v == null ? null : Number(v));
    const body = { name: f.name, start_date: f.start_date, end_date: f.end_date, sectors: f.sectors, unit_ids: f.unit_ids, channels: f.channels, venue: f.venue || null,
      district: f.district || null, budget: num(f.budget), enquiries: num(f.enquiries), manual_orders: num(f.manual_orders), manual_sales: num(f.manual_sales),
      message_en: (f.message_en as string) || null, message_te: (f.message_te as string) || null, note: (f.note as string) || null };
    try { const c = await api<C>(edit === "new" ? "/market/campaigns" : `/market/campaigns/${(edit as C).id}`, { method: edit === "new" ? "POST" : "PUT", body }); setEdit(null); load(); setView(c); }
    catch (e) { setError((e as Error).message); }
  };
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Marketing campaigns</h1><p className="muted small" style={{ margin: 0 }}>Form 8.3. Orders units tag with a campaign count in its results automatically; add fair counts by hand.</p></div>
        <button className="btn" onClick={() => startEdit("new")}><Plus size={16} /> New campaign</button>
      </div>
      <div className="scheme-cards">
        {rows?.map((c) => (
          <button key={c.id} className="card stack scheme-card" style={{ textAlign: "left" }} onClick={async () => setView(await api<C>(`/market/campaigns/${c.id}`))}>
            <div className="row-between"><span className={`tag ${c.state === "running" ? "ok" : c.state === "upcoming" ? "amber" : "grey"}`}>{c.state}</span><small className="muted">{fmtDay(c.start_date)} – {fmtDay(c.end_date)}</small></div>
            <b>{c.name}</b>
            <span className="small muted">{c.channels.map((x) => CH.find((y) => y[0] === x)?.[1]).join(", ")} · {c.unit_ids.length} units{c.venue ? ` · ${c.venue}` : ""}</span>
            <div className="shop-tiles mini"><div><small>Enquiries</small><b>{c.results.enquiries}</b></div><div><small>Orders</small><b>{c.results.orders}</b></div><div><small>Sales</small><b>{inrShort(c.results.sales)}</b></div></div>
          </button>))}
        {rows && !rows.length && <div className="card muted">No campaigns yet.</div>}
      </div>
      {view && (
        <Modal title={view.name} wide onClose={() => setView(null)}>
          <div className="stack">
            <div className="small muted">{fmtDay(view.start_date)} – {fmtDay(view.end_date)} · {view.sector_names.join(", ")}{view.venue ? ` · ${view.venue}` : ""}{view.budget ? ` · budget ${inr(view.budget)}` : ""}</div>
            <div className="shop-tiles"><div><small>Enquiries</small><b>{view.results.enquiries}</b></div><div><small>Orders</small><b>{view.results.orders}</b><small>{view.results.app_orders} in the app</small></div>
              <div><small>Sales</small><b>{inr(view.results.sales)}</b><small>{inr(view.results.app_sales)} in the app</small></div></div>
            <table className="table compact"><thead><tr><th>Unit</th><th className="num">Orders</th><th className="num">Sales</th></tr></thead>
              <tbody>{view.units?.map((u) => <tr key={u.id}><td>{u.name} <span className="small muted">{u.code}</span></td><td className="num">{u.orders}</td><td className="num">{inr(u.sales)}</td></tr>)}</tbody></table>
            <div className="row-between"><b>Message</b><button className="btn small secondary" onClick={async () => { try { setView(await api<C>(`/market/campaigns/${view.id}/message`, { method: "POST" })); } catch (e) { setError((e as Error).message); } }}><Sparkles size={14} /> Draft from the units' products</button></div>
            {error && <div className="error">{error}</div>}
            {view.message_te && <pre className="promo-msg">{view.message_te}</pre>}
            {view.message_en && <pre className="promo-msg">{view.message_en}</pre>}
            <div className="row-between"><b>Materials</b>
              <input ref={fileRef} type="file" accept="application/pdf,image/*" hidden onChange={async (e) => { const x = e.target.files?.[0]; if (!x) return; const fd = new FormData(); fd.append("file", x); setView(await apiUpload<C>(`/market/campaigns/${view.id}/files`, fd)); }} />
              <button className="btn small ghost" onClick={() => fileRef.current?.click()}><FileUp size={14} /> Upload</button></div>
            <div className="photo-row">{view.materials?.map((m, k) => m.file.endsWith(".pdf") ? <a key={k} href={apiUrl(m.url)} target="_blank" rel="noreferrer">{m.title}</a>
              : <a key={k} href={apiUrl(m.url)} target="_blank" rel="noreferrer"><img src={apiUrl(m.url)} alt={m.title} /></a>)}</div>
            <div><button className="btn secondary" onClick={() => { const c = view; setView(null); startEdit(c); }}>Edit / enter results</button></div>
          </div>
        </Modal>)}
      {edit && (
        <Modal title={edit === "new" ? "New campaign" : "Edit campaign"} wide onClose={() => setEdit(null)}>
          <div className="stack">
            <Field label="Name"><input className="input" value={f.name as string} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
            <div className="grid-3">
              <Field label="Starts"><input className="input" type="date" value={f.start_date as string} onChange={(e) => setF({ ...f, start_date: e.target.value })} /></Field>
              <Field label="Ends"><input className="input" type="date" value={f.end_date as string} onChange={(e) => setF({ ...f, end_date: e.target.value })} /></Field>
              <Field label="Budget (₹)"><input className="input" inputMode="decimal" value={f.budget as string} onChange={(e) => setF({ ...f, budget: e.target.value })} /></Field>
              <Field label="Venue"><input className="input" value={f.venue as string} onChange={(e) => setF({ ...f, venue: e.target.value })} /></Field>
              <Field label="District"><select className="input" value={f.district as string} onChange={(e) => setF({ ...f, district: e.target.value })}><option value="">—</option>{districts.map((d) => <option key={d.code} value={d.code}>{d.name_en}</option>)}</select></Field>
            </div>
            <Field label="Channels"><div className="chips small-chips">{CH.map(([k, l]) => <button type="button" key={k} className={`chip ${arr("channels").includes(k) ? "on" : ""}`} onClick={() => tog("channels", k)}>{l}</button>)}</div></Field>
            <Field label="Sectors"><div className="chips small-chips">{sectors.map((s) => <button type="button" key={s.code} className={`chip ${arr("sectors").includes(s.code) ? "on" : ""}`} onClick={() => tog("sectors", s.code)}>{s.name_en}</button>)}</div></Field>
            <Field label="Units taking part (launched)"><div className="chips small-chips">{units.map((u) => <button type="button" key={u.id} className={`chip ${arr("unit_ids").includes(u.id) ? "on" : ""}`} onClick={() => tog("unit_ids", u.id)}>{u.name}</button>)}
              {!units.length && <span className="small muted">No launched units yet.</span>}</div></Field>
            {edit !== "new" && (
              <div className="grid-3">
                <Field label="Enquiries at the event" hint="Not entered in the app"><input className="input" inputMode="numeric" value={f.enquiries as string} onChange={(e) => setF({ ...f, enquiries: e.target.value })} /></Field>
                <Field label="Orders (not in the app)"><input className="input" inputMode="numeric" value={f.manual_orders as string} onChange={(e) => setF({ ...f, manual_orders: e.target.value })} /></Field>
                <Field label="Sales ₹ (not in the app)"><input className="input" inputMode="decimal" value={f.manual_sales as string} onChange={(e) => setF({ ...f, manual_sales: e.target.value })} /></Field>
              </div>)}
            {error && <div className="error">{error}</div>}
            <div><button className="btn" onClick={save}>Save campaign</button></div>
          </div>
        </Modal>)}
    </div>
  );
}
