// One purchase (Form 7.2): quotations side by side, selection with reason, purchase order (PDF), delivery,
// installation photos and handover (adds the items to the asset register).
import { Camera, Download, FileUp, PackageCheck, Truck, Wrench, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, apiUpload, apiUrl, openLink } from "../../api";
import { fmtDay, inr, Num, today } from "../dpr/common";
import { Field, Modal } from "../ui";
import { P_TAG, type PurchaseDetail as PD, type Supplier, useSetupMeta } from "./common";

function QuoteForm({ p, suppliers, supplierId, onSave }: { p: PD; suppliers: Supplier[]; supplierId?: number; onSave: (b: object) => Promise<void> }) {
  const existing = p.quotes.find((q) => q.supplier_id === supplierId);
  const [sid, setSid] = useState<number>(supplierId ?? p.invited_suppliers.find((x) => !x.quoted)?.id ?? suppliers[0]?.id ?? 0);
  const [lines, setLines] = useState(p.items.map((i) => ({ item: i.item, qty: i.qty, rate: existing?.lines.find((l) => l.item === i.item)?.rate ?? 0 })));
  const [f, setF] = useState({ delivery_days: existing?.delivery_days ?? 7, warranty_months: existing?.warranty_months ?? 12, valid_till: existing?.valid_till ?? "",
    gst_included: existing?.gst_included ?? true, note: existing?.note ?? "" });
  const total = lines.reduce((a, l) => a + l.qty * l.rate, 0);
  return (
    <div className="stack">
      <Field label="Supplier"><select className="input" value={sid} onChange={(e) => setSid(Number(e.target.value))}>
        {suppliers.filter((s) => s.approved).map((s) => <option key={s.id} value={s.id}>{s.name}{p.invited.includes(s.id) ? "" : " (not asked yet)"}</option>)}</select></Field>
      <table className="table compact edit-table">
        <thead><tr><th>Item</th><th className="num">Qty</th><th className="num">Rate (₹)</th><th className="num">Amount</th></tr></thead>
        <tbody>{lines.map((l, i) => (
          <tr key={l.item}><td>{l.item}</td><td className="num">{l.qty}</td>
            <td className="num"><Num label={`Rate for ${l.item}`} width={110} value={l.rate} onChange={(v) => setLines(lines.map((x, j) => (j === i ? { ...x, rate: v } : x)))} /></td>
            <td className="num">{inr(l.qty * l.rate)}</td></tr>))}
          <tr className="total-row"><td colSpan={3}>Total</td><td className="num">{inr(total)}</td></tr></tbody>
      </table>
      <div className="grid-3">
        <Field label="Delivery (days)"><Num value={f.delivery_days} step={1} onChange={(v) => setF({ ...f, delivery_days: Math.round(v) })} /></Field>
        <Field label="Warranty (months)"><Num value={f.warranty_months} step={1} onChange={(v) => setF({ ...f, warranty_months: Math.round(v) })} /></Field>
        <Field label="Valid till"><input className="input" type="date" min={today()} value={f.valid_till} onChange={(e) => setF({ ...f, valid_till: e.target.value })} /></Field>
      </div>
      <label className="check"><input type="checkbox" checked={f.gst_included} onChange={(e) => setF({ ...f, gst_included: e.target.checked })} /> Prices include GST</label>
      <Field label="Note"><input className="input" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
      <div><button className="btn" disabled={!sid || lines.some((l) => l.rate <= 0)} onClick={() => onSave({ supplier_id: sid, lines: lines.map((l) => ({ ...l, rate: l.rate })),
        ...f, valid_till: f.valid_till || null, note: f.note || null })}>Save quotation</button></div>
    </div>
  );
}

export default function PurchaseDetail() {
  const { id } = useParams();
  const meta = useSetupMeta();
  const [p, setP] = useState<PD | null>(null);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [modal, setModal] = useState<null | { quote?: number } | "order" | "delivered" | "installed">(null);
  const [order, setOrder] = useState({ quote_id: 0, reason: "", payment_source: "loan", expected_delivery: "" });
  const [del, setDel] = useState({ on: today(), note: "" });
  const [inst, setInst] = useState<{ on: string; handover_note: string; serials: Record<string, string> }>({ on: today(), handover_note: "", serials: {} });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const quoteFor = useRef<number | null>(null);

  const load = useCallback(() => api<PD>(`/setup/purchases/${id}`).then(setP).catch((e) => setMsg({ ok: false, text: e.message })), [id]);
  useEffect(() => {
    load();
    api<Supplier[]>("/setup/suppliers?approved=true").then(setSuppliers).catch(() => {});
  }, [load]);
  const call = async (fn: () => Promise<PD>, ok?: string) => {
    setMsg(null);
    try {
      setP(await fn());
      setModal(null);
      if (ok) setMsg({ ok: true, text: ok });
      return true;
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
      return false;
    }
  };
  const upload = async (f?: File) => {
    if (!f || !p) return;
    const fd = new FormData();
    fd.append("file", f);
    if (quoteFor.current) await call(() => apiUpload<PD>(`/setup/quotes/${quoteFor.current}/file`, fd));
    else { fd.append("caption", "Installation"); await call(() => apiUpload<PD>(`/setup/purchases/${p.id}/photos`, fd)); }
    if (fileRef.current) fileRef.current.value = "";
  };
  if (!p || !meta) return msg ? <div className="error">{msg.text}</div> : <div className="muted">Loading…</div>;
  const buy = meta.can.procure, w = meta.can.write;
  const open = ["draft", "rfq"].includes(p.status);
  const steps = [["rfq", "Quotations"], ["ordered", "Order placed"], ["delivered", "Delivered"], ["installed", "Installed"]];
  const idx = ["draft", "rfq", "ordered", "delivered", "installed"].indexOf(p.status);
  const lowest = p.quotes.find((q) => q.lowest);
  const chosen = p.quotes.find((q) => q.id === order.quote_id);
  const needReason = chosen && (p.quotes.length < 2 || !chosen.lowest);

  return (
    <div className="stack">
      <Link to={`/admin/setup/units/${p.unit.id}`} className="small">← {p.unit.name}</Link>
      <input ref={fileRef} type="file" hidden onChange={(e) => upload(e.target.files?.[0])} />
      <div className="card detail-head">
        <div style={{ flex: 1, minWidth: 240 }}>
          <div className="chips" style={{ marginBottom: 6 }}><span className={`tag ${P_TAG[p.status]}`}>{p.status_label}</span>{p.po_number && <span className="tag grey">{p.po_number}</span>}
            {p.late && <span className="tag alert">delivery late</span>}{p.supplier_confirmed && <span className="tag ok">supplier confirmed</span>}</div>
          <h1 style={{ margin: 0 }}>{p.title}</h1>
          <div className="small muted">{p.unit.code} · estimate {inr(p.estimate)}{p.quote_by && open ? ` · quotations by ${fmtDay(p.quote_by)}` : ""}
            {p.supplier && ` · ${p.supplier}, ${inr(p.po_amount)} (${p.payment_label})`}</div>
        </div>
        <div className="row-gap">
          {buy && open && <button className="btn secondary" onClick={() => setModal({})}>Enter a quotation</button>}
          {buy && open && p.quotes.length > 0 && <button className="btn" onClick={() => { setOrder({ ...order, quote_id: lowest?.id ?? p.quotes[0].id }); setModal("order"); }}>Choose & place order</button>}
          {p.po_number && <button className="btn secondary" onClick={() => openLink(`/setup/purchases/${p.id}/po-link`).catch((e) => setMsg({ ok: false, text: e.message }))}><Download size={16} /> Purchase order (PDF)</button>}
          {w && p.status === "ordered" && <button className="btn" onClick={() => setModal("delivered")}><Truck size={16} /> Delivered</button>}
          {w && ["ordered", "delivered"].includes(p.status) && <button className="btn secondary" onClick={() => { quoteFor.current = null; if (fileRef.current) { fileRef.current.accept = "image/*"; fileRef.current.click(); } }}><Camera size={16} /> Photo</button>}
          {w && p.status === "delivered" && <button className="btn" onClick={() => setModal("installed")}><Wrench size={16} /> Installed & handed over</button>}
          {buy && ["draft", "rfq", "ordered"].includes(p.status) && <button className="btn ghost small danger" onClick={() => window.confirm("Cancel this purchase?") && call(() => api<PD>(`/setup/purchases/${p.id}/cancel`, { method: "POST" }))}><X size={14} /> Cancel</button>}
        </div>
      </div>
      {msg && <div className={msg.ok ? "notice ok-notice" : "error"}>{msg.text}</div>}
      {p.status !== "cancelled" && <ol className="loan-steps">{steps.map(([k, l], i) => <li key={k} className={idx >= i + 1 ? "done" : ""}><span>{i + 1}</span>{l}</li>)}</ol>}

      <div className="card stack">
        <div className="row-between"><h2 style={{ margin: 0 }}>Quotations</h2>
          <span className="small muted">{p.invited_suppliers.map((s) => `${s.name}${s.quoted ? " ✓" : " – waiting"}`).join(" · ") || "No supplier asked yet"}</span></div>
        {p.quotes.length === 0 ? <p className="small muted" style={{ margin: 0 }}>No quotation yet. Suppliers with a login quote online; enter the others by hand.</p> : (
          <div className="table-wrap">
            <table className="table compact compare">
              <thead><tr><th>Item</th><th className="num">Qty</th><th className="num">DPR rate</th>{p.quotes.map((q) => (
                <th key={q.id} className={`num ${q.id === p.selected_quote_id ? "chosen" : ""}`}>{q.supplier.replace("Sample: ", "")}{q.lowest && <div><span className="tag ok">lowest</span></div>}</th>))}</tr></thead>
              <tbody>
                {p.items.map((it) => {
                  const rates = p.quotes.map((q) => q.lines.find((l) => l.item === it.item)?.rate ?? null);
                  const min = Math.min(...rates.filter((r): r is number => r != null));
                  return (
                    <tr key={it.item}><td>{it.item}<div className="small muted">{it.spec}</div></td><td className="num">{it.qty}</td><td className="num">{inr(it.est_rate)}</td>
                      {rates.map((r, i) => <td key={i} className={`num ${r === min ? "best" : ""} ${p.quotes[i].id === p.selected_quote_id ? "chosen" : ""}`}>{r == null ? "—" : inr(r)}</td>)}</tr>);
                })}
                <tr className="total-row"><td colSpan={2}>Total</td><td className="num">{inr(p.estimate)}</td>{p.quotes.map((q) => (
                  <td key={q.id} className={`num ${q.id === p.selected_quote_id ? "chosen" : ""}`}>{inr(q.amount)}<div className="small">{q.vs_estimate_pct == null ? "" : `${q.vs_estimate_pct > 0 ? "+" : ""}${q.vs_estimate_pct}% vs DPR`}</div></td>))}</tr>
                <tr><td colSpan={3} className="small">Delivery · warranty</td>{p.quotes.map((q) => (
                  <td key={q.id} className="num small">{q.delivery_days ?? "—"} days · {q.warranty_months ?? "—"} mo</td>))}</tr>
                <tr><td colSpan={3} className="small">Quotation</td>{p.quotes.map((q) => (
                  <td key={q.id} className="num small">
                    {q.file_url ? <a href={apiUrl(q.file_url)} target="_blank" rel="noreferrer">file</a> : "no file"}
                    {buy && open && <> · <button className="link-btn" onClick={() => { quoteFor.current = q.id; if (fileRef.current) { fileRef.current.accept = "application/pdf,image/*"; fileRef.current.click(); } }}><FileUp size={12} /> attach</button>
                      {" · "}<button className="link-btn" onClick={() => setModal({ quote: q.supplier_id })}>edit</button></>}
                    <div className="muted">{q.source === "supplier" ? "sent online" : "entered by staff"}{q.valid_till ? ` · valid till ${fmtDay(q.valid_till)}` : ""}</div>
                  </td>))}</tr>
              </tbody>
            </table>
          </div>)}
        {p.selection_reason && <div className="small"><b>Why this supplier:</b> {p.selection_reason}</div>}
      </div>

      {(p.photos.length > 0 || p.handover_note || p.delivered_on) && (
        <div className="card stack">
          <h2 style={{ margin: 0 }}>Delivery and installation</h2>
          <div className="small">{p.delivered_on && <>Delivered {fmtDay(p.delivered_on)}{p.expected_delivery ? ` (due ${fmtDay(p.expected_delivery)})` : ""}. </>}{p.installed_on && <>Installed {fmtDay(p.installed_on)}.</>}</div>
          {p.handover_note && <p className="small" style={{ whiteSpace: "pre-line", margin: 0 }}>{p.handover_note}</p>}
          <div className="photo-row">{p.photos.map((ph, i) => <a key={i} href={apiUrl(ph.url)} target="_blank" rel="noreferrer"><img src={apiUrl(ph.url)} alt={ph.caption ?? "Installation photo"} /></a>)}</div>
        </div>)}

      {modal && typeof modal === "object" && (
        <Modal title="Quotation" wide onClose={() => setModal(null)}>
          <QuoteForm p={p} suppliers={suppliers} supplierId={modal.quote} onSave={async (b) => { await call(() => api<PD>(`/setup/purchases/${p.id}/quotes`, { body: b }), "Quotation saved."); }} />
          {msg && !msg.ok && <div className="error" style={{ marginTop: 8 }}>{msg.text}</div>}
        </Modal>)}
      {modal === "order" && (
        <Modal title="Choose the supplier and place the order" onClose={() => setModal(null)}>
          <div className="stack">
            <Field label="Quotation"><select className="input" value={order.quote_id} onChange={(e) => setOrder({ ...order, quote_id: Number(e.target.value) })}>
              {p.quotes.map((q) => <option key={q.id} value={q.id}>{q.supplier} – {inr(q.amount)}{q.lowest ? " (lowest)" : ""}</option>)}</select></Field>
            <Field label={needReason ? "Reason (needed: not the lowest, or only one quotation)" : "Reason (optional)"}>
              <textarea className="input" rows={2} value={order.reason} onChange={(e) => setOrder({ ...order, reason: e.target.value })} /></Field>
            <div className="grid-2">
              <Field label="Payment from"><select className="input" value={order.payment_source} onChange={(e) => setOrder({ ...order, payment_source: e.target.value })}>
                {meta.payment_sources.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}</select></Field>
              <Field label="Deliver by" hint="Blank = from the supplier's delivery days"><input className="input" type="date" min={today()} value={order.expected_delivery} onChange={(e) => setOrder({ ...order, expected_delivery: e.target.value })} /></Field>
            </div>
            {msg && !msg.ok && <div className="error">{msg.text}</div>}
            <div><button className="btn" disabled={!!needReason && order.reason.trim().length < 10} onClick={() => call(() => api<PD>(`/setup/purchases/${p.id}/order`, { body: { ...order, reason: order.reason || null, expected_delivery: order.expected_delivery || null } }), "Purchase order issued. Download the PDF and send it to the supplier.")}>
              <PackageCheck size={16} /> Place order</button></div>
          </div>
        </Modal>)}
      {modal === "delivered" && (
        <Modal title="Delivery received" onClose={() => setModal(null)}>
          <div className="stack">
            <Field label="Delivered on"><input className="input" type="date" max={today()} value={del.on} onChange={(e) => setDel({ ...del, on: e.target.value })} /></Field>
            <Field label="Note (optional)"><input className="input" value={del.note} onChange={(e) => setDel({ ...del, note: e.target.value })} /></Field>
            {msg && !msg.ok && <div className="error">{msg.text}</div>}
            <div><button className="btn" onClick={() => call(() => api<PD>(`/setup/purchases/${p.id}/delivered`, { body: { on: del.on, note: del.note || null } }), "Delivery recorded.")}>Save</button></div>
          </div>
        </Modal>)}
      {modal === "installed" && (
        <Modal title="Installation and handover" onClose={() => setModal(null)}>
          <div className="stack">
            {p.photos.length === 0 && <div className="notice small">Add at least one installation photo first (the Photo button).</div>}
            <Field label="Installed on"><input className="input" type="date" max={today()} value={inst.on} onChange={(e) => setInst({ ...inst, on: e.target.value })} /></Field>
            <Field label="Handover note" hint="Tested? Owner shown how to use it? Anything pending?"><textarea className="input" rows={3} value={inst.handover_note} onChange={(e) => setInst({ ...inst, handover_note: e.target.value })} /></Field>
            <b className="small">Serial numbers (for the asset register)</b>
            {p.items.map((it) => (
              <label key={it.item} className="field"><span className="small">{it.item}</span>
                <input className="input" value={inst.serials[it.item] ?? ""} onChange={(e) => setInst({ ...inst, serials: { ...inst.serials, [it.item]: e.target.value } })} /></label>))}
            {msg && !msg.ok && <div className="error">{msg.text}</div>}
            <div><button className="btn" disabled={inst.handover_note.trim().length < 5 || !p.photos.length} onClick={() => call(() => api<PD>(`/setup/purchases/${p.id}/installed`, { body: {
              on: inst.on, handover_note: inst.handover_note, assets: Object.entries(inst.serials).filter(([, v]) => v.trim()).map(([item, serial_no]) => ({ item, serial_no })) } }),
              "Installed. The items are now in the unit's asset register.")}>Save</button></div>
          </div>
        </Modal>)}
    </div>
  );
}
