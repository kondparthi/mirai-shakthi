// Supplier register (Form 7.1): items supplied (matched with enterprise-model equipment), rate card, districts, approval,
// delivery record, and the supplier's limited portal login.
import { KeyRound, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { useMaster } from "../../components/masters";
import { type EModel, inr, Num } from "../dpr/common";
import { Field, Modal, toList } from "../ui";
import { type Supplier, useSetupMeta } from "./common";

function SupplierForm({ s, models, onSaved }: { s: Supplier | null; models: EModel[]; onSaved: () => void }) {
  const districts = useMaster("district");
  const [f, setF] = useState({ name: s?.name ?? "", gstin: s?.gstin ?? "", contact_name: s?.contact_name ?? "", mobile: s?.mobile ?? "", email: s?.email ?? "",
    address: s?.address ?? "", categories: (s?.categories ?? []).join(", "), items: (s?.items ?? []).join("\n"), models: s?.models ?? [], districts: s?.districts ?? [],
    rate_card: s?.rate_card ?? [], approved: s?.approved ?? false, note: s?.note ?? "" });
  const [error, setError] = useState<string | null>(null);
  const modelItems = [...new Set(models.filter((m) => f.models.includes(m.code)).flatMap((m) => m.equipment.map((e) => e.item)))];
  const toggle = (k: "models" | "districts", v: string) => setF({ ...f, [k]: f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v] });
  const save = async () => {
    setError(null);
    try {
      await api(s ? `/setup/suppliers/${s.id}` : "/setup/suppliers", { method: s ? "PUT" : "POST", body: { ...f, gstin: f.gstin || null, email: f.email || null, note: f.note || null,
        categories: toList(f.categories), items: f.items.split("\n").map((x) => x.trim()).filter(Boolean),
        rate_card: f.rate_card.filter((r) => r.item && r.rate > 0).map((r) => ({ ...r, valid_till: r.valid_till || null })) } });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Supplier name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="GSTIN"><input className="input" maxLength={15} value={f.gstin} onChange={(e) => setF({ ...f, gstin: e.target.value.toUpperCase() })} /></Field>
        <Field label="Contact person"><input className="input" value={f.contact_name} onChange={(e) => setF({ ...f, contact_name: e.target.value })} /></Field>
        <Field label="Mobile"><input className="input" inputMode="numeric" value={f.mobile} onChange={(e) => setF({ ...f, mobile: e.target.value })} /></Field>
        <Field label="Email"><input className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Address"><input className="input" value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></Field>
      </div>
      <Field label="Categories" hint="Comma separated, e.g. Kitchen equipment, Drones"><input className="input" value={f.categories} onChange={(e) => setF({ ...f, categories: e.target.value })} /></Field>
      <Field label="Enterprise models supplied"><div className="chips small-chips">{models.map((m) => (
        <button type="button" key={m.code} className={`chip ${f.models.includes(m.code) ? "on" : ""}`} onClick={() => toggle("models", m.code)}>{m.name_en}</button>))}</div></Field>
      <Field label="Items supplied" hint="One per line. Use the same names as the model's equipment list so suppliers are matched automatically.">
        <textarea className="input" rows={5} value={f.items} onChange={(e) => setF({ ...f, items: e.target.value })} /></Field>
      {modelItems.length > 0 && (
        <div className="chips small-chips"><span className="small muted">Add from models:</span>{modelItems.filter((i) => !f.items.split("\n").includes(i)).map((i) => (
          <button type="button" key={i} className="chip" onClick={() => setF({ ...f, items: (f.items.trim() ? f.items.trim() + "\n" : "") + i })}>+ {i}</button>))}</div>)}
      <Field label="Districts served" hint="None selected = all districts"><div className="chips small-chips">{districts.map((d) => (
        <button type="button" key={d.code} className={`chip ${f.districts.includes(d.code) ? "on" : ""}`} onClick={() => toggle("districts", d.code)}>{d.name_en}</button>))}</div></Field>
      <b className="small">Rate card</b>
      {f.rate_card.map((r, i) => (
        <div key={i} className="row-gap">
          <input className="input" aria-label="Item" style={{ flex: 2, minWidth: 180 }} value={r.item} list="sup-items" onChange={(e) => setF({ ...f, rate_card: f.rate_card.map((x, j) => (j === i ? { ...x, item: e.target.value } : x)) })} />
          <Num label="Rate" width={110} value={r.rate} onChange={(v) => setF({ ...f, rate_card: f.rate_card.map((x, j) => (j === i ? { ...x, rate: v } : x)) })} />
          <input className="input" aria-label="Valid till" type="date" style={{ width: 160 }} value={r.valid_till ?? ""} onChange={(e) => setF({ ...f, rate_card: f.rate_card.map((x, j) => (j === i ? { ...x, valid_till: e.target.value } : x)) })} />
          <button className="btn ghost small danger" aria-label="Remove rate" onClick={() => setF({ ...f, rate_card: f.rate_card.filter((_, j) => j !== i) })}><Trash2 size={15} /></button>
        </div>))}
      <datalist id="sup-items">{f.items.split("\n").filter(Boolean).map((i) => <option key={i} value={i} />)}</datalist>
      <div><button className="btn ghost small" onClick={() => setF({ ...f, rate_card: [...f.rate_card, { item: "", rate: 0, unit: "each", valid_till: null }] })}><Plus size={14} /> Add rate</button></div>
      <label className="check"><input type="checkbox" checked={f.approved} onChange={(e) => setF({ ...f, approved: e.target.checked })} /> Approved – can be asked for quotations</label>
      <Field label="Note"><input className="input" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" onClick={save}>Save supplier</button></div>
    </div>
  );
}

export default function Suppliers() {
  const meta = useSetupMeta();
  const [rows, setRows] = useState<Supplier[] | null>(null);
  const [models, setModels] = useState<EModel[]>([]);
  const [q, setQ] = useState("");
  const [edit, setEdit] = useState<Supplier | "new" | null>(null);
  const [login, setLogin] = useState<Supplier | null>(null);
  const [lf, setLf] = useState({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<Supplier[]>(`/setup/suppliers${q ? `?q=${encodeURIComponent(q)}` : ""}`).then(setRows).catch(() => setRows([])), [q]);
  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
  }, [load]);
  useEffect(() => {
    api<EModel[]>("/dpr/models").then(setModels).catch(() => {});
  }, []);
  const can = meta?.can.procure;
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Suppliers</h1><p className="muted small" style={{ margin: 0 }}>Form 7.1. Only approved suppliers are asked for quotations. Delivery record comes from purchase orders.</p></div>
        {can && <button className="btn" onClick={() => setEdit("new")}>+ New supplier</button>}
      </div>
      <div className="filters row-gap"><input className="input" type="search" placeholder="Search name, item or GSTIN" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" /></div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Supplier</th><th>Items</th><th>Districts</th><th className="num">Orders</th><th className="num">On time</th><th>Status</th><th /></tr></thead>
          <tbody>
            {rows?.map((s) => (
              <tr key={s.id}>
                <td><b>{s.name}</b><div className="small muted">{s.contact_name} · {s.mobile}{s.gstin ? ` · ${s.gstin}` : ""}</div></td>
                <td className="small">{s.items.slice(0, 3).join(", ")}{s.items.length > 3 ? ` +${s.items.length - 3}` : ""}</td>
                <td className="small">{s.districts.length ? `${s.districts.length} districts` : "All"}</td>
                <td className="num">{s.orders ?? 0}<div className="small muted">{inr(s.value ?? 0)}</div></td>
                <td className="num">{s.delivered ? `${Math.round((100 * (s.on_time ?? 0)) / s.delivered)}%` : "—"}</td>
                <td><span className={`tag ${s.approved ? "ok" : "amber"}`}>{s.approved ? "approved" : "pending"}</span>{s.sample && <div><span className="tag grey">sample</span></div>}
                  {s.has_login && <div className="small muted">portal login</div>}</td>
                <td className="row-gap" style={{ justifyContent: "flex-end" }}>
                  {can && <button className="btn ghost small" onClick={() => setEdit(s)}>Edit</button>}
                  {can && s.approved && <button className="btn ghost small" aria-label={`Portal login for ${s.name}`} onClick={() => { setLogin(s); setLf({ email: s.email ?? "", password: "" }); setError(null); }}><KeyRound size={14} /></button>}
                </td>
              </tr>))}
            {rows && !rows.length && <tr><td colSpan={7} className="muted">No suppliers found.</td></tr>}
          </tbody>
        </table>
      </div>
      {edit && <Modal title={edit === "new" ? "New supplier" : `Edit – ${edit.name}`} wide onClose={() => setEdit(null)}>
        <SupplierForm s={edit === "new" ? null : edit} models={models} onSaved={() => { setEdit(null); load(); }} /></Modal>}
      {login && (
        <Modal title={`Portal login – ${login.name}`} onClose={() => setLogin(null)}>
          <div className="stack">
            <p className="small muted" style={{ margin: 0 }}>The supplier signs in at <b>#/supplier</b> to send quotations and confirm orders and deliveries. They see only what they were asked to quote for.</p>
            <Field label="Email"><input className="input" type="email" value={lf.email} onChange={(e) => setLf({ ...lf, email: e.target.value })} /></Field>
            <Field label="Password" hint="At least 8 characters; share it with the supplier securely"><input className="input" value={lf.password} onChange={(e) => setLf({ ...lf, password: e.target.value })} /></Field>
            {error && <div className="error">{error}</div>}
            <div><button className="btn" disabled={!lf.email || lf.password.length < 8} onClick={async () => {
              try { await api(`/setup/suppliers/${login.id}/login`, { body: lf }); setLogin(null); load(); } catch (e) { setError((e as Error).message); }
            }}>{login.has_login ? "Reset login" : "Create login"}</button></div>
          </div>
        </Modal>)}
    </div>
  );
}
