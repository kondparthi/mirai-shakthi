// Visual editor for rule conditions. Covers "all of / any of" simple rows; nested conditions use the JSON view.
import { useEffect, useState } from "react";

type Cond = Record<string, unknown> | null;
type Row = { field: string; op: string; value: unknown };
type FieldDef = { label: string; kind: "select" | "number" | "list" | "bool" | "text"; options?: [string | number, string][] };

const REGS: [string, string][] = [["udyam", "Udyam"], ["gst", "GST"], ["fssai", "FSSAI"], ["trade", "Trade licence"], ["iec", "IEC"], ["shop_est", "Shop & Est."]];
export const FIELDS: Record<string, FieldDef> = {
  stage: { label: "Stage", kind: "select", options: [["planning", "Planning"], ["lt1", "< 1 year"], ["1to3", "1–3 years"], ["gt3", "> 3 years"]] },
  business_type: { label: "Business type", kind: "select", options: [["manufacturing", "Manufacturing"], ["trading", "Trading"], ["services", "Services"]] },
  sector: { label: "Sector", kind: "select", options: ["food", "agriculture", "dairy & livestock", "fisheries", "forest products", "handloom & textiles", "crafts",
    "repairs & services", "beauty & wellness", "mobility & logistics", "tourism", "digital services", "other"].map((s) => [s, s]) },
  ownership: { label: "Ownership", kind: "select", options: [["proprietor", "Proprietor"], ["partnership", "Partnership"], ["llp", "LLP"], ["company", "Company"], ["shg", "SHG"]] },
  turnover_band: { label: "Turnover band", kind: "number", options: [[0, "Nil"], [1, "≤ ₹10 L"], [2, "₹10–40 L"], [3, "₹40 L–1 Cr"], [4, "₹1–5 Cr"], [5, "> ₹5 Cr"]] },
  employees: { label: "People working", kind: "number" },
  registrations: { label: "Registrations held", kind: "list", options: REGS },
  channels: { label: "Sells through", kind: "list", options: [["local", "Local"], ["wholesale", "Wholesale"], ["online", "Online"], ["government", "Government"], ["interstate", "Other states"], ["export", "Export"]] },
  books_kept: { label: "Accounts kept in", kind: "select", options: [["none", "No records"], ["notebook", "Notebook"], ["excel", "Excel"], ["software", "Software"]] },
  flags: { label: "Flags", kind: "list", options: [["women_led", "Women-led"], ["sc_st", "SC / ST"], ["first_gen", "First-generation"]] },
  has_loan: { label: "Has a loan", kind: "bool" },
  district: { label: "District", kind: "text" },
};
const OPS: Record<FieldDef["kind"], [string, string][]> = {
  select: [["eq", "is"], ["ne", "is not"], ["in", "is one of"], ["not_in", "is none of"]],
  text: [["eq", "is"], ["ne", "is not"]],
  number: [["gte", "≥"], ["lte", "≤"], ["gt", ">"], ["lt", "<"], ["eq", "="]],
  list: [["contains", "includes"], ["not_contains", "does not include"], ["contains_any", "includes any of"]],
  bool: [["eq", "is"]],
};
const MULTI = new Set(["in", "not_in", "contains_any"]);
const OP_KEYS = ["eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "contains", "not_contains", "contains_any"];

function leafToRow(c: Record<string, unknown>): Row | null {
  const field = c.field as string;
  const op = OP_KEYS.find((k) => k in c);
  if (!field || !op || !(field in FIELDS) || Object.keys(c).length !== 2) return null;
  return { field, op, value: c[op] };
}

/** Returns rows if the condition fits the simple editor, otherwise null (use JSON). */
function parse(cond: Cond): { mode: "all" | "any"; rows: Row[] } | null {
  if (!cond) return { mode: "all", rows: [] };
  if ("field" in cond) { const r = leafToRow(cond); return r ? { mode: "all", rows: [r] } : null; }
  const mode = "all" in cond ? "all" : "any" in cond ? "any" : null;
  if (!mode) return null;
  const rows = (cond[mode] as Record<string, unknown>[]).map((c) => ("field" in c ? leafToRow(c) : null));
  return rows.every(Boolean) ? { mode, rows: rows as Row[] } : null;
}

function build(mode: "all" | "any", rows: Row[]): Cond {
  const leaves = rows.map((r) => ({ field: r.field, [r.op]: r.value }));
  if (leaves.length === 0) return null;
  if (leaves.length === 1) return leaves[0];
  return { [mode]: leaves };
}

function defaultValue(field: string, op: string): unknown {
  const f = FIELDS[field];
  if (MULTI.has(op)) return [];
  if (f.kind === "number") return 0;
  if (f.kind === "bool") return true;
  return f.options?.[0]?.[0] ?? "";
}

function ValueInput({ row, onChange }: { row: Row; onChange: (v: unknown) => void }) {
  const f = FIELDS[row.field];
  if (MULTI.has(row.op)) {
    const arr = (row.value as (string | number)[]) ?? [];
    return (
      <div className="chips small-chips">
        {(f.options ?? []).map(([v, l]) => {
          const on = arr.includes(v);
          return <button type="button" key={String(v)} className={`chip ${on ? "on" : ""}`}
            onClick={() => onChange(on ? arr.filter((x) => x !== v) : [...arr, v])}>{l}</button>;
        })}
      </div>
    );
  }
  if (f.kind === "bool") return (
    <select className="input" value={String(row.value)} onChange={(e) => onChange(e.target.value === "true")}>
      <option value="true">Yes</option><option value="false">No</option>
    </select>
  );
  if (f.options) return (
    <select className="input" value={String(row.value)} onChange={(e) => onChange(f.kind === "number" ? Number(e.target.value) : e.target.value)}>
      {f.options.map(([v, l]) => <option key={String(v)} value={String(v)}>{l}</option>)}
    </select>
  );
  if (f.kind === "number") return <input className="input" type="number" value={Number(row.value)} onChange={(e) => onChange(Number(e.target.value))} />;
  return <input className="input" value={String(row.value ?? "")} onChange={(e) => onChange(e.target.value)} />;
}

export default function ConditionBuilder({ value, onChange, emptyLabel }: { value: Cond; onChange: (c: Cond) => void; emptyLabel: string }) {
  const parsed = parse(value);
  const [json, setJson] = useState(!parsed);
  const [text, setText] = useState(JSON.stringify(value ?? null, null, 2));
  const [jsonError, setJsonError] = useState<string | null>(null);

  useEffect(() => { if (json) setText(JSON.stringify(value ?? null, null, 2)); }, [json]); // eslint-disable-line react-hooks/exhaustive-deps

  if (json || !parsed) {
    return (
      <div className="cond">
        <textarea className="input mono" rows={6} value={text} onChange={(e) => {
          setText(e.target.value);
          try { onChange(JSON.parse(e.target.value || "null")); setJsonError(null); } catch { setJsonError("Not valid JSON yet"); }
        }} />
        {jsonError && <small className="warn-text">{jsonError}</small>}
        {parse(value) && <button type="button" className="btn ghost small" onClick={() => setJson(false)}>Use simple editor</button>}
      </div>
    );
  }

  const { mode, rows } = parsed;
  const update = (i: number, patch: Partial<Row>) => {
    const next = rows.map((r, j) => (j === i ? { ...r, ...patch } : r));
    onChange(build(mode, next));
  };

  return (
    <div className="cond">
      {rows.length === 0 && <div className="small muted">{emptyLabel}</div>}
      {rows.length > 1 && (
        <div className="small">Match&nbsp;
          <select className="input inline" value={mode} onChange={(e) => onChange(build(e.target.value as "all" | "any", rows))}>
            <option value="all">all of these</option><option value="any">any of these</option>
          </select>
        </div>
      )}
      {rows.map((r, i) => (
        <div className="cond-row" key={i}>
          <select className="input" value={r.field} onChange={(e) => {
            const field = e.target.value; const op = OPS[FIELDS[field].kind][0][0];
            update(i, { field, op, value: defaultValue(field, op) });
          }}>
            {Object.entries(FIELDS).map(([k, f]) => <option key={k} value={k}>{f.label}</option>)}
          </select>
          <select className="input" value={r.op} onChange={(e) => update(i, { op: e.target.value, value: defaultValue(r.field, e.target.value) })}>
            {OPS[FIELDS[r.field].kind].map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <div className="cond-value"><ValueInput row={r} onChange={(v) => update(i, { value: v })} /></div>
          <button type="button" className="btn ghost" aria-label="Remove condition" onClick={() => onChange(build(mode, rows.filter((_, j) => j !== i)))}>✕</button>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="btn ghost small" onClick={() => onChange(build(mode, [...rows, { field: "registrations", op: "contains", value: "udyam" }]))}>+ Add condition</button>
        <button type="button" className="btn ghost small" onClick={() => setJson(true)}>Edit as JSON</button>
      </div>
    </div>
  );
}

/** Plain-language summary of a condition, for lists. */
export function describe(cond: Cond): string {
  if (!cond) return "Always";
  if ("all" in cond || "any" in cond) {
    const mode = "all" in cond ? "all" : "any";
    return (cond[mode] as Cond[]).map(describe).join(mode === "all" ? " and " : " or ");
  }
  if ("not" in cond) return `not (${describe(cond.not as Cond)})`;
  const r = leafToRow(cond);
  if (!r) return JSON.stringify(cond);
  const f = FIELDS[r.field];
  const label = (v: unknown) => f.options?.find(([k]) => k === v)?.[1] ?? String(v);
  const val = Array.isArray(r.value) ? r.value.map(label).join(", ") : label(r.value);
  const op = OPS[f.kind].find(([k]) => k === r.op)?.[1] ?? r.op;
  return `${f.label} ${op} ${val}`;
}
