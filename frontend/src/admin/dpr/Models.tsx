// Enterprise models (Form 3.1) – each is the DPR template for its sector: equipment list, working capital, sales and expense defaults,
// eligible schemes, jobs and payback.
import { Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { useMaster } from "../../components/masters";
import { Field, Modal, toList } from "../ui";
import { type EModel, Num, inr, useDprMeta } from "./common";

const TAGS = ["rural", "urban", "tribal", "coastal"];
const EXP: [string, string][] = [["salaries", "Salaries"], ["rent", "Rent"], ["fuel", "Fuel / power / gas"], ["maintenance", "Maintenance"], ["other", "Other"]];
const STATUS_TAG: Record<string, string> = { active: "ok", pilot: "amber", catalogue: "grey" };

function ModelForm({ m, onSaved }: { m: EModel | null; onSaved: () => void }) {
  const meta = useDprMeta();
  const sectors = useMaster("sector");
  const skills = useMaster("skill");
  const [f, setF] = useState<EModel>(m ? structuredClone(m) : {
    id: 0, code: "", sector: "food", name_en: "", name_te: "", description: "", activity: "service", context_tags: ["rural"], investment_min: 0, investment_max: 0,
    working_capital: 0, equipment: [{ item: "", spec: "", qty: 1, rate: 0 }], equipment_total: 0, infrastructure: [], skills: [], schemes: [],
    sales_template: { items: [{ name: "", unit: "unit", units_per_day: 0, price: 0 }], working_days: 26, monthly_growth_pct: 1, yearly_growth_pct: 5 },
    expense_template: { raw_material_pct: 40, salaries: 0, rent: 0, fuel: 0, maintenance: 0, other: 0, yearly_increase_pct: 5 },
    expected_monthly_sales: 0, jobs: 1, payback_months: 24, status: "catalogue",
  });
  const [infra, setInfra] = useState((m?.infrastructure ?? []).join("\n"));
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof EModel>(k: K, v: EModel[K]) => setF({ ...f, [k]: v });
  const items = f.sales_template.items ?? [];
  const exp = f.expense_template as Record<string, number>;
  const toggle = (k: "context_tags" | "skills" | "schemes", v: string) => set(k, f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v]);
  const save = async () => {
    setError(null);
    const { id: _id, equipment_total: _t, ...body } = f;
    try {
      await api(m ? `/dpr/models/${m.id}` : "/dpr/models", { method: m ? "PUT" : "POST", body: { ...body, infrastructure: toList(infra), name_te: f.name_te || null,
        equipment: f.equipment.map((e) => ({ item: e.item, spec: e.spec || "", qty: e.qty, rate: e.rate, suppliers: e.suppliers || null })) } });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const total = f.equipment.reduce((a, e) => a + e.qty * e.rate, 0);
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Code"><input className="input" disabled={!!m} value={f.code} onChange={(e) => set("code", e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))} /></Field>
        <Field label="Sector"><select className="input" value={f.sector} onChange={(e) => set("sector", e.target.value)}>{sectors.map((s) => <option key={s.code} value={s.code}>{s.name_en}</option>)}</select></Field>
        <Field label="Name (English)"><input className="input" value={f.name_en} onChange={(e) => set("name_en", e.target.value)} /></Field>
        <Field label="Name (Telugu)"><input className="input" value={f.name_te ?? ""} onChange={(e) => set("name_te", e.target.value)} /></Field>
        <Field label="Activity"><select className="input" value={f.activity} onChange={(e) => set("activity", e.target.value)}>
          {meta?.activities.map((a) => <option key={a.code} value={a.code}>{a.label}</option>)}</select></Field>
        <Field label="Workflow status"><select className="input" value={f.status} onChange={(e) => set("status", e.target.value)}>
          <option value="catalogue">Catalogue only</option><option value="pilot">Pilot</option><option value="active">Active</option></select></Field>
      </div>
      <Field label="Description"><textarea className="input" rows={2} value={f.description ?? ""} onChange={(e) => set("description", e.target.value)} /></Field>
      <Field label="Context"><div className="chips small-chips">{TAGS.map((t) => <button type="button" key={t} className={`chip ${f.context_tags.includes(t) ? "on" : ""}`} onClick={() => toggle("context_tags", t)}>{t}</button>)}</div></Field>

      <h3 style={{ marginBottom: 0 }}>Equipment (pre-fills the DPR)</h3>
      {f.equipment.map((e, i) => (
        <div key={i} className="row-gap equip-row">
          <input className="input" aria-label="Item" placeholder="Item" style={{ flex: 2, minWidth: 160 }} value={e.item} onChange={(x) => { const q = [...f.equipment]; q[i] = { ...e, item: x.target.value }; set("equipment", q); }} />
          <input className="input" aria-label="Specification" placeholder="Specification" style={{ flex: 2, minWidth: 140 }} value={e.spec} onChange={(x) => { const q = [...f.equipment]; q[i] = { ...e, spec: x.target.value }; set("equipment", q); }} />
          <Num label="Quantity" width={70} value={e.qty} onChange={(v) => { const q = [...f.equipment]; q[i] = { ...e, qty: v }; set("equipment", q); }} />
          <Num label="Rate" width={110} value={e.rate} onChange={(v) => { const q = [...f.equipment]; q[i] = { ...e, rate: v }; set("equipment", q); }} />
          <button className="btn ghost small danger" aria-label="Remove" onClick={() => set("equipment", f.equipment.filter((_, j) => j !== i))}><Trash2 size={15} /></button>
        </div>))}
      <div className="row-between"><button className="btn secondary small" onClick={() => set("equipment", [...f.equipment, { item: "", spec: "", qty: 1, rate: 0 }])}><Plus size={14} /> Add item</button>
        <span className="small">Equipment total <b>{inr(total)}</b></span></div>
      <div className="grid-3">
        <Field label="Working capital (₹)"><Num value={f.working_capital} onChange={(v) => set("working_capital", v)} /></Field>
        <Field label="Investment from (₹)"><Num value={f.investment_min ?? 0} onChange={(v) => set("investment_min", v)} /></Field>
        <Field label="Investment to (₹)"><Num value={f.investment_max ?? 0} onChange={(v) => set("investment_max", v)} /></Field>
      </div>

      <h3 style={{ marginBottom: 0 }}>Sales template</h3>
      {items.map((it, i) => (
        <div key={i} className="row-gap">
          <input className="input" aria-label="Product" placeholder="Product / service" style={{ flex: 2, minWidth: 160 }} value={it.name} onChange={(x) => { const q = [...items]; q[i] = { ...it, name: x.target.value }; set("sales_template", { ...f.sales_template, items: q }); }} />
          <input className="input" aria-label="Unit" placeholder="unit" style={{ width: 90 }} value={it.unit} onChange={(x) => { const q = [...items]; q[i] = { ...it, unit: x.target.value }; set("sales_template", { ...f.sales_template, items: q }); }} />
          <Num label="Units a day" width={80} value={it.units_per_day} onChange={(v) => { const q = [...items]; q[i] = { ...it, units_per_day: v }; set("sales_template", { ...f.sales_template, items: q }); }} />
          <Num label="Price" width={90} value={it.price} onChange={(v) => { const q = [...items]; q[i] = { ...it, price: v }; set("sales_template", { ...f.sales_template, items: q }); }} />
          <button className="btn ghost small danger" aria-label="Remove" onClick={() => set("sales_template", { ...f.sales_template, items: items.filter((_, j) => j !== i) })}><Trash2 size={15} /></button>
        </div>))}
      <div><button className="btn secondary small" onClick={() => set("sales_template", { ...f.sales_template, items: [...items, { name: "", unit: "unit", units_per_day: 0, price: 0 }] })}><Plus size={14} /> Add product</button></div>
      <div className="grid-3">
        <Field label="Working days a month"><Num value={f.sales_template.working_days ?? 26} max={31} onChange={(v) => set("sales_template", { ...f.sales_template, working_days: v })} /></Field>
        <Field label="Growth a month, year 1 (%)"><Num value={f.sales_template.monthly_growth_pct ?? 0} min={-20} max={20} onChange={(v) => set("sales_template", { ...f.sales_template, monthly_growth_pct: v })} /></Field>
        <Field label="Growth a year after (%)"><Num value={f.sales_template.yearly_growth_pct ?? 5} min={-50} max={50} onChange={(v) => set("sales_template", { ...f.sales_template, yearly_growth_pct: v })} /></Field>
      </div>
      <h3 style={{ marginBottom: 0 }}>Expense template (₹ a month)</h3>
      <div className="grid-4">
        <Field label="Raw material (% of sales)"><Num value={exp.raw_material_pct ?? 0} max={100} onChange={(v) => set("expense_template", { ...f.expense_template, raw_material_pct: v })} /></Field>
        {EXP.map(([k, l]) => <Field key={k} label={l}><Num value={exp[k] ?? 0} onChange={(v) => set("expense_template", { ...f.expense_template, [k]: v })} /></Field>)}
        <Field label="Rise a year (%)"><Num value={exp.yearly_increase_pct ?? 5} max={50} onChange={(v) => set("expense_template", { ...f.expense_template, yearly_increase_pct: v })} /></Field>
      </div>
      <div className="grid-3">
        <Field label="Expected sales a month (₹)"><Num value={f.expected_monthly_sales ?? 0} onChange={(v) => set("expected_monthly_sales", v)} /></Field>
        <Field label="Jobs"><Num value={f.jobs ?? 0} step={1} onChange={(v) => set("jobs", Math.round(v))} /></Field>
        <Field label="Payback (months)"><Num value={f.payback_months ?? 0} step={1} onChange={(v) => set("payback_months", Math.round(v))} /></Field>
      </div>
      <Field label="Eligible schemes"><div className="chips small-chips">{meta?.schemes.map((s) => (
        <button type="button" key={s.code} className={`chip ${f.schemes.includes(s.code) ? "on" : ""}`} onClick={() => toggle("schemes", s.code)}>{s.name.split(" – ")[0]}</button>))}</div></Field>
      <Field label="Skills required"><div className="chips small-chips">{skills.map((s) => (
        <button type="button" key={s.code} className={`chip ${f.skills.includes(s.code) ? "on" : ""}`} onClick={() => toggle("skills", s.code)}>{s.name_en}</button>))}</div></Field>
      <Field label="Infrastructure and licences" hint="One per line"><textarea className="input" rows={3} value={infra} onChange={(e) => setInfra(e.target.value)} /></Field>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" onClick={save}>Save model</button></div>
    </div>
  );
}

export default function Models() {
  const meta = useDprMeta();
  const sectors = useMaster("sector");
  const [rows, setRows] = useState<EModel[] | null>(null);
  const [edit, setEdit] = useState<EModel | "new" | null>(null);
  const load = useCallback(() => api<EModel[]>("/dpr/models").then(setRows).catch(() => setRows([])), []);
  useEffect(() => {
    load();
  }, [load]);
  const sectorName = (c: string) => sectors.find((s) => s.code === c)?.name_en ?? c;
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Enterprise models</h1><p className="muted small" style={{ margin: 0 }}>Form 3.1. Each model is the DPR template for its sector: equipment, working capital, sales and expense defaults, and schemes.</p></div>
        {meta?.can.models && <button className="btn" onClick={() => setEdit("new")}>+ New model</button>}
      </div>
      <div className="scheme-cards">
        {rows?.map((m) => (
          <div key={m.id} className="card stack scheme-card">
            <div className="row-between"><span className="chips"><span className={`tag ${STATUS_TAG[m.status]}`}>{m.status}</span><span className="tag grey">{sectorName(m.sector)}</span></span>
              {meta?.can.models && <button className="btn ghost small" onClick={() => setEdit(m)}>Edit</button>}</div>
            <div><b>{m.name_en}</b>{m.name_te && <div className="small muted">{m.name_te}</div>}</div>
            <p className="small" style={{ margin: 0 }}>{m.description}</p>
            <div className="kv"><span>Equipment + working capital</span><b>{inr(m.equipment_total)} + {inr(m.working_capital)}</b></div>
            <div className="kv"><span>Expected sales a month</span><b>{inr(m.expected_monthly_sales)}</b></div>
            <div className="kv"><span>Jobs · payback</span><b>{m.jobs ?? "—"} · {m.payback_months ?? "—"} months</b></div>
            <div className="chips small-chips">{m.schemes.map((s) => <span key={s} className="tag grey">{s.toUpperCase()}</span>)}</div>
          </div>
        ))}
      </div>
      {edit && (
        <Modal title={edit === "new" ? "New enterprise model" : `Edit – ${edit.name_en}`} wide onClose={() => setEdit(null)}>
          <ModelForm m={edit === "new" ? null : edit} onSaved={() => { setEdit(null); load(); }} />
        </Modal>
      )}
    </div>
  );
}
