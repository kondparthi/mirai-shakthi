// One unit: purchases (Form 7.2), registrations, readiness checklist and launch (Form 7.3), asset register.
import { Camera, CheckCircle2, Circle, FileUp, Plus, Rocket } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, apiUpload, apiUrl } from "../../api";
import { StatTile } from "../../components/charts";
import { fmtDay, inr, Num, today } from "../dpr/common";
import { Field, Modal } from "../ui";
import { type Asset, P_TAG, REG_TAG, type Registration, UNIT_TAG, type UnitDetail as U, useSetupMeta } from "./common";

type Sugg = { id: number; name: string; matches: string[]; covers: number; of: number; rates: Record<string, number>; has_login: boolean };
type Item = { item: string; spec: string; qty: number; est_rate: number; pick: boolean; extra?: boolean };

function NewPurchase({ u, onDone }: { u: U; onDone: (id: number) => void }) {
  const bought = new Set(u.purchase_list.filter((p) => p.status !== "cancelled").flatMap((p) => p.items.map((i) => i.item)));
  const [items, setItems] = useState<Item[]>(u.dpr_items.map((i) => ({ ...i, spec: i.spec ?? "", pick: !bought.has(i.item) })));
  const [title, setTitle] = useState("Equipment");
  const [sugg, setSugg] = useState<Sugg[]>([]);
  const [invited, setInvited] = useState<number[]>([]);
  const [by, setBy] = useState(new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10));
  const [error, setError] = useState<string | null>(null);
  const picked = items.filter((i) => i.pick && i.item.trim());
  const key = picked.map((i) => i.item).join("|");
  useEffect(() => {
    if (!key) return setSugg([]);
    api<Sugg[]>(`/setup/units/${u.id}/suppliers?items=${encodeURIComponent(key)}`).then((s) => {
      setSugg(s);
      setInvited((cur) => cur.filter((id) => s.some((x) => x.id === id)));
    }).catch(() => {});
  }, [key, u.id]);
  const save = async () => {
    setError(null);
    try {
      const r = await api<{ id: number }>(`/setup/units/${u.id}/purchases`, { body: { title, items: picked.map(({ pick: _p, extra: _e, ...i }) => i), invited, quote_by: by || null } });
      onDone(r.id);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Purchase name"><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        <Field label="Quotations by"><input className="input" type="date" min={today()} value={by} onChange={(e) => setBy(e.target.value)} /></Field>
      </div>
      <b className="small">Items (from the approved DPR – untick what is bought separately)</b>
      <div className="table-wrap">
        <table className="table compact edit-table">
          <thead><tr><th /><th>Item</th><th>Specification</th><th className="num">Qty</th><th className="num">DPR rate</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={i} className={bought.has(it.item) ? "muted" : ""}>
              <td><input type="checkbox" aria-label={`Include ${it.item}`} checked={it.pick} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, pick: e.target.checked } : x)))} /></td>
              <td>{it.extra
                ? <input className="input" aria-label="Item name" placeholder="Item name" value={it.item} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, item: e.target.value } : x)))} />
                : <>{it.item}{bought.has(it.item) && <div className="small">already in a purchase</div>}</>}</td>
              <td><input className="input" aria-label="Specification" value={it.spec} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, spec: e.target.value } : x)))} /></td>
              <td className="num"><Num width={70} value={it.qty} onChange={(v) => setItems(items.map((x, j) => (j === i ? { ...x, qty: v } : x)))} /></td>
              <td className="num">{it.extra ? <Num label="Estimated rate" width={100} value={it.est_rate} onChange={(v) => setItems(items.map((x, j) => (j === i ? { ...x, est_rate: v } : x)))} /> : inr(it.est_rate)}</td>
            </tr>))}</tbody>
        </table>
      </div>
      <div><button className="btn ghost small" onClick={() => setItems([...items, { item: "", spec: "", qty: 1, est_rate: 0, pick: true, extra: true }])}><Plus size={14} /> Other item</button></div>
      <b className="small">Ask these suppliers to quote (approved, serving {u.district_name})</b>
      <div className="pick-list" style={{ maxHeight: 220 }}>
        {sugg.map((s) => (
          <label key={s.id} className={`pick ${invited.includes(s.id) ? "on" : ""}`} style={{ flexDirection: "row", gap: 10, alignItems: "flex-start" }}>
            <input type="checkbox" checked={invited.includes(s.id)} onChange={(e) => setInvited(e.target.checked ? [...invited, s.id] : invited.filter((x) => x !== s.id))} />
            <span><b>{s.name}</b><small style={{ display: "block" }}>{s.covers} of {s.of} items{Object.keys(s.rates).length ? ` · rate card: ${Object.entries(s.rates).map(([k, v]) => `${k} ${inr(v)}`).join(", ")}` : ""}
              {s.has_login ? " · quotes online" : " · enter their quote by hand"}</small></span>
          </label>))}
        {!sugg.length && <p className="small muted">No approved supplier deals in these items here. Add one under Suppliers.</p>}
      </div>
      {invited.length === 1 && <div className="notice small">Ask at least two suppliers so the quotations can be compared.</div>}
      {error && <div className="error">{error}</div>}
      <div><button className="btn" disabled={!picked.length || !title.trim()} onClick={save}>{invited.length ? `Ask ${invited.length} supplier${invited.length > 1 ? "s" : ""} to quote` : "Save as draft"}</button></div>
    </div>
  );
}

function RegistrationForm({ r, onSave }: { r: Registration; onSave: (body: object) => Promise<void> }) {
  const [f, setF] = useState({ status: r.status, number: r.number ?? "", applied_on: r.applied_on ?? "", issued_on: r.issued_on ?? "", valid_until: r.valid_until ?? "", note: r.note ?? "" });
  return (
    <div className="stack">
      <Field label="Status"><select className="input" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value as Registration["status"] })}>
        {Object.entries(REG_TAG).map(([k, [, l]]) => <option key={k} value={k}>{l}</option>)}</select></Field>
      <div className="grid-2">
        <Field label="Number"><input className="input" value={f.number} onChange={(e) => setF({ ...f, number: e.target.value })} /></Field>
        <Field label="Applied on"><input className="input" type="date" max={today()} value={f.applied_on} onChange={(e) => setF({ ...f, applied_on: e.target.value })} /></Field>
        <Field label="Issued on"><input className="input" type="date" max={today()} value={f.issued_on} onChange={(e) => setF({ ...f, issued_on: e.target.value })} /></Field>
        <Field label="Valid until"><input className="input" type="date" value={f.valid_until} onChange={(e) => setF({ ...f, valid_until: e.target.value })} /></Field>
      </div>
      <Field label="Note"><input className="input" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
      <div><button className="btn" onClick={() => onSave({ ...f, number: f.number || null, applied_on: f.applied_on || null, issued_on: f.issued_on || null,
        valid_until: f.valid_until || null, note: f.note || null })}>Save</button></div>
    </div>
  );
}

function AssetForm({ a, onSave }: { a: Partial<Asset> | null; onSave: (body: object) => Promise<void> }) {
  const [f, setF] = useState({ item: a?.item ?? "", spec: a?.spec ?? "", qty: a?.qty ?? 1, value: a?.value ?? 0, serial_no: a?.serial_no ?? "",
    warranty_until: a?.warranty_until ?? "", insurance_policy: a?.insurance_policy ?? "", insurance_until: a?.insurance_until ?? "", shared: a?.shared ?? false,
    status: a?.status ?? "working" });
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Item"><input className="input" value={f.item} onChange={(e) => setF({ ...f, item: e.target.value })} /></Field>
        <Field label="Specification"><input className="input" value={f.spec} onChange={(e) => setF({ ...f, spec: e.target.value })} /></Field>
        <Field label="Serial number"><input className="input" value={f.serial_no} onChange={(e) => setF({ ...f, serial_no: e.target.value })} /></Field>
        <Field label="Value (₹)"><Num value={f.value} onChange={(v) => setF({ ...f, value: v })} /></Field>
        <Field label="Warranty until"><input className="input" type="date" value={f.warranty_until} onChange={(e) => setF({ ...f, warranty_until: e.target.value })} /></Field>
        <Field label="Status"><select className="input" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
          <option value="working">Working</option><option value="repair">Under repair</option><option value="disposed">Disposed</option></select></Field>
        <Field label="Insurance policy"><input className="input" value={f.insurance_policy} onChange={(e) => setF({ ...f, insurance_policy: e.target.value })} /></Field>
        <Field label="Insurance until"><input className="input" type="date" value={f.insurance_until} onChange={(e) => setF({ ...f, insurance_until: e.target.value })} /></Field>
      </div>
      <label className="check"><input type="checkbox" checked={f.shared} onChange={(e) => setF({ ...f, shared: e.target.checked })} /> Shared asset (used by the group's members)</label>
      <div><button className="btn" disabled={f.item.trim().length < 2} onClick={() => onSave({ ...f, spec: f.spec || null, serial_no: f.serial_no || null, warranty_until: f.warranty_until || null,
        insurance_policy: f.insurance_policy || null, insurance_until: f.insurance_until || null })}>Save</button></div>
    </div>
  );
}

export default function UnitDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const meta = useSetupMeta();
  const [u, setU] = useState<U | null>(null);
  const [tab, setTab] = useState<"purchases" | "registrations" | "readiness" | "assets">("purchases");
  const [modal, setModal] = useState<null | "purchase" | "launch" | { reg: Registration } | { asset: Partial<Asset> | null }>(null);
  const [launchDate, setLaunchDate] = useState(today());
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const target = useRef<{ kind: "reg" | "tick"; id: string | number } | null>(null);

  const load = useCallback(() => api<U>(`/setup/units/${id}`).then(setU).catch((e) => setMsg({ ok: false, text: e.message })), [id]);
  useEffect(() => {
    load();
  }, [load]);
  const call = async (fn: () => Promise<U>, ok?: string) => {
    setMsg(null);
    try {
      setU(await fn());
      setModal(null);
      if (ok) setMsg({ ok: true, text: ok });
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  };
  const upload = async (f?: File) => {
    const t = target.current;
    if (!f || !t || !u) return;
    const fd = new FormData();
    fd.append("file", f);
    await call(() => apiUpload<U>(t.kind === "reg" ? `/setup/registrations/${t.id}/file` : `/setup/units/${u.id}/readiness/${t.id}/photo`, fd));
    if (fileRef.current) fileRef.current.value = "";
  };
  if (!u || !meta) return msg ? <div className="error">{msg.text}</div> : <div className="muted">Loading…</div>;
  const w = meta.can.write;
  const allDone = u.checklist.every((i) => i.done);
  const pick = (kind: "reg" | "tick", key: string | number, accept: string) => {
    target.current = { kind, id: key };
    if (fileRef.current) { fileRef.current.accept = accept; fileRef.current.click(); }
  };

  return (
    <div className="stack">
      <Link to="/admin/setup/units" className="small">← Units</Link>
      <input ref={fileRef} type="file" hidden onChange={(e) => upload(e.target.files?.[0])} />
      <div className="card detail-head">
        <div style={{ flex: 1, minWidth: 240 }}>
          <div className="chips" style={{ marginBottom: 6 }}><span className={`tag ${UNIT_TAG[u.status][0]}`}>{UNIT_TAG[u.status][1]}</span><span className="tag grey">{u.code}</span>
            {u.is_group && <span className="tag">group unit – shared assets</span>}</div>
          <h1 style={{ margin: 0 }}>{u.name}</h1>
          <div className="small muted">
            {u.owner.type === "entrepreneur" ? <Link to={`/admin/entrepreneurs/${u.owner.id}`}>{u.owner.name}</Link> : u.owner.name}
            {" · "}{u.model ?? "—"} · {u.location}{u.dpr_id && <> · <Link to={`/admin/finance/dprs/${u.dpr_id}`}>{u.dpr_code}</Link></>}
            {u.launch_date && ` · launched ${fmtDay(u.launch_date)}`}
          </div>
        </div>
        <div className="row-gap">
          {meta.can.procure && u.status !== "closed" && <button className="btn secondary" onClick={() => setModal("purchase")}><Plus size={16} /> New purchase</button>}
          {meta.can.launch && u.status === "setting_up" && <button className="btn" disabled={!allDone} title={allDone ? "" : "Complete the readiness checklist first"} onClick={() => setModal("launch")}><Rocket size={16} /> Launch</button>}
        </div>
      </div>
      {msg && <div className={msg.ok ? "notice ok-notice" : "error"}>{msg.text}</div>}

      <div className="stats">
        <StatTile icon={<CheckCircle2 />} label="Readiness" value={`${u.readiness.done}/${u.readiness.total}`} ratio={u.readiness.done / Math.max(1, u.readiness.total)} note={allDone ? "Ready to launch" : "Items left"} />
        <StatTile icon={<Plus />} tone="blue" label="Purchases installed" value={`${u.purchases.installed}/${u.purchases.total}`} note={`${inr(u.purchases.ordered_value)} ordered`} />
        <StatTile icon={<FileUp />} tone="amber" label="Registrations" value={`${u.registrations.done}/${u.registrations.total}`} ratio={u.registrations.done / Math.max(1, u.registrations.total)} />
        <StatTile icon={<Camera />} tone="violet" label="Assets" value={u.assets.length} note={inr(u.assets.reduce((a, x) => a + x.value, 0))} />
      </div>

      <div className="tabs">{([["purchases", "Purchases"], ["registrations", "Registrations"], ["readiness", "Readiness & launch"], ["assets", "Assets"]] as const).map(([k, l]) => (
        <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>))}</div>

      {tab === "purchases" && (
        <div className="card table-wrap">
          <table className="table">
            <thead><tr><th>Purchase</th><th>Quotations</th><th>Supplier / PO</th><th className="num">Amount</th><th>Status</th></tr></thead>
            <tbody>
              {u.purchase_list.map((p) => (
                <tr key={p.id} className="clickable" onClick={() => navigate(`/admin/setup/units/purchase/${p.id}`)}>
                  <td><b>{p.title}</b><div className="small muted">{p.items.length} items · estimate {inr(p.estimate)}</div></td>
                  <td className="small">{p.quotes_count} of {p.invited.length} received{p.quote_by && p.status === "rfq" ? <div className="muted">by {fmtDay(p.quote_by)}</div> : null}</td>
                  <td className="small">{p.supplier ?? "—"}{p.po_number && <div className="muted">{p.po_number}</div>}</td>
                  <td className="num">{inr(p.po_amount ?? p.lowest ?? p.estimate)}</td>
                  <td><span className={`tag ${P_TAG[p.status]}`}>{p.status_label}</span>{p.late && <div><span className="tag alert">delivery late</span></div>}
                    {p.expected_delivery && p.status === "ordered" && <div className="small muted">due {fmtDay(p.expected_delivery)}</div>}</td>
                </tr>))}
              {!u.purchase_list.length && <tr><td colSpan={5} className="muted">No purchase yet. "New purchase" starts with the items in the approved DPR.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {tab === "registrations" && (
        <div className="card stack">
          {u.registration_list.map((r) => (
            <div key={r.id} className="row-between reg-row">
              <div><b>{r.label}</b> <span className={`tag ${REG_TAG[r.status][0]}`}>{REG_TAG[r.status][1]}</span>{r.expiring && <span className="tag alert" style={{ marginLeft: 4 }}>renew soon</span>}
                <div className="small muted">{[r.number, r.issued_on && `issued ${fmtDay(r.issued_on)}`, r.valid_until && `valid till ${fmtDay(r.valid_until)}`, r.note].filter(Boolean).join(" · ") || "—"}</div></div>
              <div className="row-gap">
                {r.file_url && <a className="small" href={apiUrl(r.file_url)} target="_blank" rel="noreferrer">Document</a>}
                {w && <button className="btn ghost small" aria-label={`Upload ${r.label}`} onClick={() => pick("reg", r.id, "application/pdf,image/*")}><FileUp size={14} /></button>}
                {w && <button className="btn small secondary" onClick={() => setModal({ reg: r })}>Update</button>}
              </div>
            </div>))}
          {w && (
            <div className="row-gap"><select className="input" style={{ maxWidth: 280 }} aria-label="Add registration" value="" onChange={(e) => e.target.value && call(() => api<U>(`/setup/units/${u.id}/registrations?kind=${e.target.value}`, { method: "POST" }))}>
              <option value="">+ Add a registration…</option>
              {meta.registrations.filter((x) => !u.registration_list.some((r) => r.kind === x.code)).map((x) => <option key={x.code} value={x.code}>{x.label}</option>)}</select></div>)}
        </div>
      )}

      {tab === "readiness" && (
        <div className="card stack">
          <p className="small muted" style={{ margin: 0 }}>Form 7.3. Equipment, registrations and training are checked automatically; tick the rest after checking at the unit (add a photo where useful).</p>
          <ul className="readiness">
            {u.checklist.map((i) => (
              <li key={i.key} className={i.done ? "done" : ""}>
                {i.done ? <CheckCircle2 className="ok-icon" /> : <Circle className="todo-icon" />}
                <div style={{ flex: 1 }}><b>{i.label}</b>{i.kind === "auto" && <span className="tag grey" style={{ marginLeft: 6 }}>automatic</span>}
                  {i.note && <div className="small muted">{i.note}</div>}{i.by && i.kind === "manual" && <div className="small muted">{i.by} · {fmtDay(i.at)}</div>}</div>
                {i.photo_url && <a href={apiUrl(i.photo_url)} target="_blank" rel="noreferrer"><img src={apiUrl(i.photo_url)} alt="" className="thumb" /></a>}
                {w && i.kind === "manual" && u.status === "setting_up" && (
                  <span className="row-gap">
                    <button className="btn ghost small" aria-label={`Photo for ${i.label}`} onClick={() => pick("tick", i.key, "image/*")}><Camera size={14} /></button>
                    <button className={`btn small ${i.done ? "ghost" : "secondary"}`} onClick={() => call(() => api<U>(`/setup/units/${u.id}/readiness/${i.key}`, { method: "PUT", body: { done: !i.done } }))}>{i.done ? "Undo" : "Done"}</button>
                  </span>)}
              </li>))}
          </ul>
          {u.status === "setting_up" && meta.can.launch && <div><button className="btn" disabled={!allDone} onClick={() => setModal("launch")}><Rocket size={16} /> Launch the unit</button></div>}
        </div>
      )}

      {tab === "assets" && (
        <div className="card table-wrap">
          <table className="table compact">
            <thead><tr><th>Item</th><th>Serial no.</th><th className="num">Value</th><th>Warranty</th><th>Insurance</th><th>Status</th><th /></tr></thead>
            <tbody>
              {u.assets.map((a) => (
                <tr key={a.id}>
                  <td><b>{a.item}</b>{a.qty !== 1 && ` × ${a.qty}`}<div className="small muted">{a.supplier ?? "own"}{a.shared ? " · shared" : ""}</div></td>
                  <td className="small">{a.serial_no ?? <span className="muted">—</span>}</td><td className="num">{inr(a.value)}</td>
                  <td className="small">{fmtDay(a.warranty_until)}</td><td className="small">{a.insurance_policy ? `${a.insurance_policy} · ${fmtDay(a.insurance_until)}` : "—"}</td>
                  <td><span className={`tag ${a.status === "working" ? "ok" : a.status === "repair" ? "amber" : "grey"}`}>{a.status}</span></td>
                  <td>{w && <button className="btn ghost small" onClick={() => setModal({ asset: a })}>Edit</button>}</td>
                </tr>))}
              {!u.assets.length && <tr><td colSpan={7} className="muted">Assets are added when a purchase is installed.</td></tr>}
            </tbody>
          </table>
          {w && <div style={{ padding: 12 }}><button className="btn ghost small" onClick={() => setModal({ asset: null })}><Plus size={14} /> Add an asset (e.g. own equipment)</button></div>}
        </div>
      )}

      {modal === "purchase" && <Modal title="New purchase – request for quotation" wide onClose={() => setModal(null)}><NewPurchase u={u} onDone={(pid) => navigate(`/admin/setup/units/purchase/${pid}`)} /></Modal>}
      {modal === "launch" && (
        <Modal title={`Launch ${u.name}`} onClose={() => setModal(null)}>
          <div className="stack">
            <p className="small" style={{ margin: 0 }}>Every readiness item is done. Launching moves {u.owner.name} to stage 5 – Sell & deliver.</p>
            <Field label="Launch date"><input className="input" type="date" value={launchDate} onChange={(e) => setLaunchDate(e.target.value)} /></Field>
            <div><button className="btn" onClick={() => call(() => api<U>(`/setup/units/${u.id}/launch`, { body: { launch_date: launchDate } }), "Launched.")}><Rocket size={16} /> Launch</button></div>
          </div>
        </Modal>
      )}
      {modal && typeof modal === "object" && "reg" in modal && (
        <Modal title={modal.reg.label} onClose={() => setModal(null)}>
          <RegistrationForm r={modal.reg} onSave={(body) => call(() => api<U>(`/setup/registrations/${modal.reg.id}`, { method: "PUT", body }))} />
          {msg && !msg.ok && <div className="error" style={{ marginTop: 10 }}>{msg.text}</div>}
        </Modal>
      )}
      {modal && typeof modal === "object" && "asset" in modal && (
        <Modal title={modal.asset ? `Asset – ${modal.asset.item}` : "Add an asset"} onClose={() => setModal(null)}>
          <AssetForm a={modal.asset} onSave={(body) => call(() => modal.asset?.id ? api<U>(`/setup/assets/${modal.asset.id}`, { method: "PUT", body }) : api<U>(`/setup/units/${u.id}/assets`, { body }))} />
        </Modal>
      )}
    </div>
  );
}
