// Buyer enquiries from institutions and market partners, routed to launched units; units answer in their app.
import { Plus, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { useMaster } from "../../components/masters";
import { fmtDay, inr, useDprMeta } from "../dpr/common";
import { Field, Modal } from "../ui";

type Route = { id: number; unit_id: number; unit: string; unit_code: string; status: string; quote_amount: number | null; reply: string | null };
type E = { id: number; code: string; need: string; sector: string | null; sector_name: string | null; model_code: string | null; district_name: string | null;
  quantity: string | null; needed_by: string | null; budget: number | null; source: string; status: string; note: string | null; routes: Route[];
  buyer: { name: string; organisation: string | null; kind: string; mobile: string }; created_at: string | null;
  suggested?: { id: number; code: string; name: string; district_name: string | null; model: string | null; same_district: boolean; listings: number; rating: number | null }[] };
const TAG: Record<string, string> = { open: "amber", routed: "", won: "ok", lost: "grey", closed: "grey", sent: "grey", interested: "amber", declined: "grey" };

export default function Enquiries() {
  const dmeta = useDprMeta();
  const sectors = useMaster("sector");
  const districts = useMaster("district");
  const [res, setRes] = useState<{ counts: Record<string, number>; rows: E[] } | null>(null);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<E | null>(null);
  const [creating, setCreating] = useState(false);
  const [pick, setPick] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [f, setF] = useState({ name: "", mobile: "", organisation: "", kind: "institution", need: "", sector: "food", model_code: "", district: "", quantity: "", needed_by: "", budget: "", source: "call" });
  const load = useCallback(() => api<{ counts: Record<string, number>; rows: E[] }>(`/market/enquiries${status ? `?status=${status}` : ""}`).then(setRes).catch(() => {}), [status]);
  useEffect(() => { load(); }, [load]);
  const openOne = async (id: number) => { setError(null); setPick([]); setOpen(await api<E>(`/market/enquiries/${id}`)); };
  const create = async () => {
    setError(null);
    try {
      const e = await api<E>("/market/enquiries", { body: { customer: { name: f.name, mobile: f.mobile, kind: f.kind, organisation: f.organisation || null }, need: f.need,
        sector: f.sector || null, model_code: f.model_code || null, district: f.district || null, quantity: f.quantity || null, needed_by: f.needed_by || null,
        budget: f.budget ? Number(f.budget) : null, source: f.source } });
      setCreating(false); load(); openOne(e.id);
    } catch (x) { setError((x as Error).message); }
  };
  const c = res?.counts ?? {};
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Buyer enquiries</h1><p className="muted small" style={{ margin: 0 }}>Schools, offices, hostels, caterers and market partners. Send each enquiry to units that can supply; they answer in their app.</p></div>
        <button className="btn" onClick={() => { setCreating(true); setError(null); }}><Plus size={16} /> New enquiry</button>
      </div>
      <div className="tabs">{[["", "All"], ["open", `Open (${c.open ?? 0})`], ["routed", `Sent to units (${c.routed ?? 0})`], ["won", `Won (${c.won ?? 0})`], ["lost", "Lost"]].map(([k, l]) => (
        <button key={k} className={status === k ? "on" : ""} onClick={() => setStatus(k)}>{l}</button>))}</div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Buyer</th><th>Needs</th><th>Where / when</th><th>Units</th><th>Status</th></tr></thead>
          <tbody>
            {res?.rows.map((e) => (
              <tr key={e.id} className="clickable" onClick={() => openOne(e.id)}>
                <td><b>{e.buyer.organisation || e.buyer.name}</b><div className="small muted">{e.buyer.name} · {e.buyer.mobile} · {e.code}</div></td>
                <td className="small">{e.need}{e.quantity ? <div className="muted">{e.quantity}</div> : null}</td>
                <td className="small">{e.district_name ?? "—"}<div className="muted">{e.needed_by ? `by ${fmtDay(e.needed_by)}` : ""}</div></td>
                <td className="small">{e.routes.length ? e.routes.map((r) => <div key={r.id}>{r.unit} <span className={`tag ${TAG[r.status]}`}>{r.status}</span>{r.quote_amount ? ` ${inr(r.quote_amount)}` : ""}</div>) : "—"}</td>
                <td><span className={`tag ${TAG[e.status]}`}>{e.status}</span></td>
              </tr>))}
            {res && !res.rows.length && <tr><td colSpan={5} className="muted">No enquiries.</td></tr>}
          </tbody>
        </table>
      </div>
      {creating && (
        <Modal title="New buyer enquiry" wide onClose={() => setCreating(false)}>
          <div className="stack">
            <div className="grid-2">
              <Field label="Organisation"><input className="input" value={f.organisation} onChange={(e) => setF({ ...f, organisation: e.target.value })} /></Field>
              <Field label="Contact person"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
              <Field label="Mobile"><input className="input" inputMode="numeric" maxLength={10} value={f.mobile} onChange={(e) => setF({ ...f, mobile: e.target.value.replace(/\D/g, "") })} /></Field>
              <Field label="Buyer type"><select className="input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>
                {[["institution", "Institution"], ["shop", "Shop / retailer"], ["event", "Event / caterer"], ["farmer", "Farmer / FPO"], ["household", "Household"], ["other", "Other"]].map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            </div>
            <Field label="What do they need?"><textarea className="input" rows={2} value={f.need} onChange={(e) => setF({ ...f, need: e.target.value })} /></Field>
            <div className="grid-3">
              <Field label="Sector"><select className="input" value={f.sector} onChange={(e) => setF({ ...f, sector: e.target.value })}><option value="">Any</option>{sectors.map((s) => <option key={s.code} value={s.code}>{s.name_en}</option>)}</select></Field>
              <Field label="Enterprise model"><select className="input" value={f.model_code} onChange={(e) => setF({ ...f, model_code: e.target.value })}><option value="">Any</option>{dmeta?.models.map((m) => <option key={m.code} value={m.code}>{m.name_en}</option>)}</select></Field>
              <Field label="District"><select className="input" value={f.district} onChange={(e) => setF({ ...f, district: e.target.value })}><option value="">—</option>{districts.map((d) => <option key={d.code} value={d.code}>{d.name_en}</option>)}</select></Field>
              <Field label="Quantity"><input className="input" value={f.quantity} placeholder="e.g. 120 plates a week" onChange={(e) => setF({ ...f, quantity: e.target.value })} /></Field>
              <Field label="Needed by"><input className="input" type="date" value={f.needed_by} onChange={(e) => setF({ ...f, needed_by: e.target.value })} /></Field>
              <Field label="Budget (₹)"><input className="input" inputMode="decimal" value={f.budget} onChange={(e) => setF({ ...f, budget: e.target.value })} /></Field>
            </div>
            <Field label="Came through"><select className="input" value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })}>
              {[["call", "Phone call"], ["visit", "Field visit"], ["campaign", "Campaign / fair"], ["partner", "Market partner"], ["online", "Online"]].map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            {error && <div className="error">{error}</div>}
            <div><button className="btn" disabled={f.name.length < 2 || f.mobile.length !== 10 || f.need.length < 5} onClick={create}>Save enquiry</button></div>
          </div>
        </Modal>)}
      {open && (
        <Modal title={`${open.buyer.organisation || open.buyer.name} – ${open.code}`} wide onClose={() => { setOpen(null); load(); }}>
          <div className="stack">
            <p style={{ margin: 0 }}>{open.need}</p>
            <div className="small muted">{[open.quantity, open.district_name, open.needed_by && `by ${fmtDay(open.needed_by)}`, open.budget && `budget ${inr(open.budget)}`, `${open.buyer.name} · ${open.buyer.mobile}`].filter(Boolean).join(" · ")}</div>
            {open.routes.length > 0 && (<div className="stack" style={{ gap: 6 }}><b className="small">Sent to</b>{open.routes.map((r) => (
              <div key={r.id} className="row-between small"><span>{r.unit} <span className="muted">{r.unit_code}</span>{r.reply ? <div className="muted">“{r.reply}”</div> : null}</span>
                <span><span className={`tag ${TAG[r.status]}`}>{r.status}</span> {r.quote_amount ? inr(r.quote_amount) : ""}</span></div>))}</div>)}
            {["open", "routed"].includes(open.status) && (
              <>
                <b className="small">Suggested units (launched, matching, same district first)</b>
                <div className="pick-list">
                  {open.suggested?.map((u) => (
                    <label key={u.id} className={`pick ${pick.includes(u.id) ? "on" : ""}`} style={{ flexDirection: "row", gap: 10 }}>
                      <input type="checkbox" checked={pick.includes(u.id)} onChange={(e) => setPick(e.target.checked ? [...pick, u.id] : pick.filter((x) => x !== u.id))} />
                      <span><b>{u.name}</b><small style={{ display: "block" }}>{u.model} · {u.district_name} · {u.listings} items{u.rating ? ` · ★ ${u.rating}` : ""}</small></span>
                    </label>))}
                  {!open.suggested?.length && <p className="small muted">No other launched unit matches.</p>}
                </div>
                {error && <div className="error">{error}</div>}
                <div className="row-gap">
                  <button className="btn" disabled={!pick.length} onClick={async () => { try { setOpen(await api<E>(`/market/enquiries/${open.id}/route`, { body: { unit_ids: pick } })); setPick([]); } catch (x) { setError((x as Error).message); } }}><Send size={15} /> Send to {pick.length || ""} unit{pick.length === 1 ? "" : "s"}</button>
                  <button className="btn ghost" onClick={async () => setOpen(await api<E>(`/market/enquiries/${open.id}/status`, { body: { status: "lost", note: "Buyer did not go ahead" } }))}>Mark lost</button>
                </div>
              </>)}
          </div>
        </Modal>)}
    </div>
  );
}
