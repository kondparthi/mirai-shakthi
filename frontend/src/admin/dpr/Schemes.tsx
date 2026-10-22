// Scheme library (M6): eligibility rules, subsidy and own-contribution rates, and document checklists. Rules only – no AI.
import { ExternalLink, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { useMaster } from "../../components/masters";
import { Field, Modal } from "../ui";
import { Num, type Scheme, fmtDay, inr, useDprMeta } from "./common";

const ACTS: [string, string][] = [["manufacturing", "Manufacturing"], ["service", "Service"], ["trading", "Trading"], ["agri_allied", "Agri-allied"]];
const CATS: [string, string][] = [["women", "Women"], ["sc", "SC"], ["st", "ST"], ["obc", "OBC"], ["minority", "Minority"]];
const EDU: [string, string][] = [["", "No rule"], ["primary", "Up to 5th"], ["secondary", "6th–10th (VIII pass)"], ["intermediate", "Intermediate"], ["graduate", "Graduate"]];
type R = {
  min_age?: number; max_age?: number; activities?: string[]; sectors?: string[]; requires_any?: string[]; new_unit_only?: boolean;
  max_project_cost?: Record<string, number> | number; min_project_cost?: number; min_loan?: number; max_loan?: number; min_education?: string;
  education_above_cost?: Record<string, number> | number; own_pct?: { general?: number; special?: number };
  subsidy_pct?: { general_urban?: number; general_rural?: number; special_urban?: number; special_rural?: number }; subsidy_on?: string; subsidy_cap?: number;
  tiers?: { name: string; max: number }[]; notes?: string;
};

function rulesSummary(r: R): string[] {
  const out: string[] = [];
  if (r.min_age || r.max_age) out.push(`Age ${r.min_age ?? 0}${r.max_age ? `–${r.max_age}` : "+"}`);
  if (r.requires_any?.length) out.push(`Only ${r.requires_any.join(" / ").toUpperCase()}`);
  if (r.activities?.length) out.push(r.activities.map((a) => a.replace("_", " ")).join(", "));
  if (r.sectors?.length) out.push(`Sectors: ${r.sectors.join(", ")}`);
  if (r.max_project_cost) out.push(`Max cost ${typeof r.max_project_cost === "number" ? inr(r.max_project_cost) : Object.entries(r.max_project_cost).map(([k, v]) => `${k.replace("_", " ")} ${inr(v)}`).join(", ")}`);
  if (r.min_loan || r.max_loan) out.push(`Loan ${inr(r.min_loan ?? 0)}–${r.max_loan ? inr(r.max_loan) : "any"}`);
  if (r.subsidy_pct) out.push(`Subsidy ${Math.min(...Object.values(r.subsidy_pct).map(Number))}–${Math.max(...Object.values(r.subsidy_pct).map(Number))}%${r.subsidy_cap ? ` (max ${inr(r.subsidy_cap)})` : ""}`);
  if (r.own_pct) out.push(`Own ${r.own_pct.special ?? r.own_pct.general}–${r.own_pct.general}%`);
  if (r.tiers?.length) out.push(r.tiers.map((t) => `${t.name} ≤ ${inr(t.max)}`).join(" · "));
  return out;
}

function Chips({ options, value, onChange }: { options: [string, string][]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="chips small-chips">{options.map(([k, l]) => (
      <button type="button" key={k} className={`chip ${value.includes(k) ? "on" : ""}`} aria-pressed={value.includes(k)}
        onClick={() => onChange(value.includes(k) ? value.filter((x) => x !== k) : [...value, k])}>{l}</button>))}</div>
  );
}

function SchemeForm({ s, onSaved }: { s: Scheme | null; onSaved: () => void }) {
  const sectors = useMaster("sector");
  const [f, setF] = useState({
    code: s?.code ?? "", name: s?.name ?? "", name_te: s?.name_te ?? "", kind: s?.kind ?? "central", agency: s?.agency ?? "", description: s?.description ?? "",
    url: s?.url ?? "", active: s?.active ?? true, verified_on: s?.verified_on ?? "", documents: s?.documents ?? [],
  });
  const [r, setR] = useState<R>(structuredClone((s?.rules as R) ?? {}));
  const [error, setError] = useState<string | null>(null);
  const perAct = (v: R["max_project_cost"], k: string) => (typeof v === "number" ? v : v?.[k] ?? 0);
  const setPerAct = (key: "max_project_cost" | "education_above_cost", k: string, n: number) => {
    const cur = r[key];
    const obj: Record<string, number> = typeof cur === "number" ? Object.fromEntries(ACTS.map(([a]) => [a, cur])) : { ...(cur ?? {}) };
    if (n) obj[k] = n; else delete obj[k];
    setR({ ...r, [key]: Object.keys(obj).length ? obj : undefined });
  };
  const clean = (x: R) => JSON.parse(JSON.stringify(x, (_k, v) => (v === "" ? undefined : v))) as R;
  const save = async () => {
    setError(null);
    try {
      const rules = clean(r);
      for (const k of ["min_age", "max_age", "min_loan", "max_loan", "min_project_cost", "subsidy_cap"] as const) if (!rules[k]) delete rules[k];
      if (!rules.min_education) delete rules.min_education;
      await api(s ? `/dpr/schemes/${s.id}` : "/dpr/schemes", { method: s ? "PUT" : "POST", body: { ...f, name_te: f.name_te || null, agency: f.agency || null,
        description: f.description || null, url: f.url || null, verified_on: f.verified_on || null, rules } });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Code"><input className="input" disabled={!!s} value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "") })} /></Field>
        <Field label="Type"><select className="input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>
          <option value="central">Central government</option><option value="state">State government</option><option value="bank">Bank product</option><option value="csr">CSR</option></select></Field>
        <Field label="Name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Name in Telugu"><input className="input" value={f.name_te} onChange={(e) => setF({ ...f, name_te: e.target.value })} /></Field>
        <Field label="Agency"><input className="input" value={f.agency} onChange={(e) => setF({ ...f, agency: e.target.value })} /></Field>
        <Field label="Official website"><input className="input" value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} /></Field>
      </div>
      <Field label="Description"><textarea className="input" rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>

      <h3 style={{ marginBottom: 0 }}>Eligibility rules</h3>
      <div className="grid-3">
        <Field label="Minimum age"><Num value={r.min_age ?? 0} max={100} onChange={(v) => setR({ ...r, min_age: v })} /></Field>
        <Field label="Maximum age" hint="0 = no limit"><Num value={r.max_age ?? 0} max={100} onChange={(v) => setR({ ...r, max_age: v })} /></Field>
        <Field label="New units only"><label className="check"><input type="checkbox" checked={!!r.new_unit_only} onChange={(e) => setR({ ...r, new_unit_only: e.target.checked })} /> Greenfield only</label></Field>
      </div>
      <Field label="Activities covered" hint="None ticked = all"><Chips options={ACTS} value={r.activities ?? []} onChange={(v) => setR({ ...r, activities: v })} /></Field>
      <Field label="Sectors covered" hint="None ticked = all"><Chips options={sectors.map((x) => [x.code, x.name_en])} value={r.sectors ?? []} onChange={(v) => setR({ ...r, sectors: v })} /></Field>
      <Field label="Only for" hint="None ticked = everyone"><Chips options={CATS} value={r.requires_any ?? []} onChange={(v) => setR({ ...r, requires_any: v })} /></Field>
      <Field label="Maximum project cost by activity (₹, 0 = no limit)">
        <div className="grid-4">{ACTS.map(([k, l]) => <label key={k} className="field"><span className="small">{l}</span><Num value={perAct(r.max_project_cost, k)} onChange={(v) => setPerAct("max_project_cost", k, v)} /></label>)}</div></Field>
      <div className="grid-3">
        <Field label="Minimum project cost (₹)"><Num value={r.min_project_cost ?? 0} onChange={(v) => setR({ ...r, min_project_cost: v })} /></Field>
        <Field label="Minimum loan (₹)"><Num value={r.min_loan ?? 0} onChange={(v) => setR({ ...r, min_loan: v })} /></Field>
        <Field label="Maximum loan (₹)" hint="0 = no limit"><Num value={r.max_loan ?? 0} onChange={(v) => setR({ ...r, max_loan: v })} /></Field>
      </div>
      <div className="grid-2">
        <Field label="Minimum education"><select className="input" value={r.min_education ?? ""} onChange={(e) => setR({ ...r, min_education: e.target.value })}>
          {EDU.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
      </div>
      {r.min_education && <Field label="…when the project cost is above (₹, by activity; 0 = always)">
        <div className="grid-4">{ACTS.map(([k, l]) => <label key={k} className="field"><span className="small">{l}</span><Num value={perAct(r.education_above_cost, k)} onChange={(v) => setPerAct("education_above_cost", k, v)} /></label>)}</div></Field>}

      <h3 style={{ marginBottom: 0 }}>Money</h3>
      <div className="grid-4">
        <Field label="Own %, general"><Num value={r.own_pct?.general ?? 0} max={100} onChange={(v) => setR({ ...r, own_pct: { ...r.own_pct, general: v } })} /></Field>
        <Field label="Own %, special category"><Num value={r.own_pct?.special ?? 0} max={100} onChange={(v) => setR({ ...r, own_pct: { ...r.own_pct, special: v } })} /></Field>
        <Field label="Subsidy on"><select className="input" value={r.subsidy_on ?? "project_cost"} onChange={(e) => setR({ ...r, subsidy_on: e.target.value })}>
          <option value="project_cost">Project cost</option><option value="capital">Equipment only</option></select></Field>
        <Field label="Subsidy cap (₹)" hint="0 = no cap"><Num value={r.subsidy_cap ?? 0} onChange={(v) => setR({ ...r, subsidy_cap: v })} /></Field>
      </div>
      <div className="grid-4">
        {(["general_urban", "general_rural", "special_urban", "special_rural"] as const).map((k) => (
          <Field key={k} label={`Subsidy %, ${k.replace("_", " ")}`}><Num value={r.subsidy_pct?.[k] ?? 0} max={100} onChange={(v) => setR({ ...r, subsidy_pct: { ...r.subsidy_pct, [k]: v } })} /></Field>))}
      </div>
      <Field label="Notes shown with the check"><textarea className="input" rows={2} value={r.notes ?? ""} onChange={(e) => setR({ ...r, notes: e.target.value })} /></Field>

      <h3 style={{ marginBottom: 0 }}>Documents</h3>
      {f.documents.map((d, i) => (
        <div key={i} className="row-gap">
          <input className="input" aria-label="Document" style={{ flex: 2, minWidth: 180 }} value={d.label} onChange={(e) => { const x = [...f.documents]; x[i] = { ...d, label: e.target.value, code: d.code || e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 40) }; setF({ ...f, documents: x }); }} />
          <select className="input" aria-label="When needed" style={{ flex: 1 }} value={d.when} onChange={(e) => { const x = [...f.documents]; x[i] = { ...d, when: e.target.value }; setF({ ...f, documents: x }); }}>
            <option value="always">Always</option><option value="special">Special category only</option><option value="rural">Rural units only</option></select>
          <button className="btn ghost small danger" aria-label="Remove document" onClick={() => setF({ ...f, documents: f.documents.filter((_, j) => j !== i) })}><Trash2 size={15} /></button>
        </div>))}
      <div><button className="btn secondary small" onClick={() => setF({ ...f, documents: [...f.documents, { code: "", label: "", when: "always" }] })}><Plus size={14} /> Add document</button></div>

      <div className="grid-2">
        <Field label="Verified against the current guidelines on" hint="Setting this removes the 'starter data' label">
          <input className="input" type="date" max={new Date().toISOString().slice(0, 10)} value={f.verified_on} onChange={(e) => setF({ ...f, verified_on: e.target.value })} /></Field>
        <Field label="Status"><label className="check"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /> Active (used in eligibility checks)</label></Field>
      </div>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" disabled={!f.code || f.name.length < 3} onClick={save}>Save scheme</button></div>
    </div>
  );
}

export default function Schemes() {
  const meta = useDprMeta();
  const [rows, setRows] = useState<Scheme[] | null>(null);
  const [edit, setEdit] = useState<Scheme | "new" | null>(null);
  const load = useCallback(() => api<Scheme[]>("/dpr/schemes").then(setRows).catch(() => setRows([])), []);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Scheme library</h1><p className="muted small" style={{ margin: 0 }}>Eligibility is checked with these rules only, with the reason for each result. Keep them in line with the current guidelines.</p></div>
        {meta?.can.schemes && <button className="btn" onClick={() => setEdit("new")}>+ New scheme</button>}
      </div>
      <div className="scheme-cards">
        {rows?.map((s) => (
          <div key={s.id} className="card stack scheme-card">
            <div className="row-between"><span className="chips"><span className="tag grey">{s.kind}</span>{!s.active && <span className="tag alert">inactive</span>}
              {s.sample ? <span className="tag amber">starter data – verify</span> : <span className="tag ok">verified {fmtDay(s.verified_on)}</span>}</span>
              {meta?.can.schemes && <button className="btn ghost small" onClick={() => setEdit(s)}>Edit</button>}</div>
            <div><b>{s.name}</b>{s.name_te && <div className="small muted">{s.name_te}</div>}</div>
            <p className="small" style={{ margin: 0 }}>{s.description}</p>
            <div className="chips small-chips">{rulesSummary(s.rules as R).map((x) => <span key={x} className="tag grey">{x}</span>)}</div>
            <div className="small muted">{s.documents.length} documents · {s.agency}</div>
            {s.url && <a className="small" href={s.url} target="_blank" rel="noreferrer"><ExternalLink size={13} /> Official site</a>}
          </div>
        ))}
      </div>
      {edit && (
        <Modal title={edit === "new" ? "New scheme" : `Edit – ${edit.name.split(" – ")[0]}`} wide onClose={() => setEdit(null)}>
          <SchemeForm s={edit === "new" ? null : edit} onSaved={() => { setEdit(null); load(); }} />
        </Modal>
      )}
    </div>
  );
}
