// Shared types and small pieces for the DPR & finance screens (M5, M6).
import { useEffect, useState } from "react";
import { api } from "../../api";

export type CapItem = { item: string; spec: string; qty: number; rate: number; amount?: number };
export type SalesItem = { name: string; unit: string; units_per_day: number; price: number };
export type Inputs = {
  capital_items: CapItem[]; preoperative: number; contingency_pct: number; working_capital: number;
  finance: { own: number; subsidy: number; grant: number };
  sales: { items: SalesItem[]; working_days: number; monthly_growth_pct: number; yearly_growth_pct: number };
  expenses: { raw_material_pct: number; salaries: number; rent: number; fuel: number; maintenance: number; other: number; yearly_increase_pct: number };
  loan: { interest_pct: number; tenure_months: number; moratorium_months: number };
  depreciation_pct: number; tax_pct: number; drawings_monthly: number; years: number;
};
export type Summary = {
  project_cost: number; capital: number; contingency: number; preoperative: number; working_capital: number; own: number; subsidy: number;
  grant: number; loan: number; excess_funding: number; own_pct: number; loan_pct: number; emi: number; emi_months: number;
  monthly_sales_start: number; monthly_sales_y1: number; monthly_profit_y1: number; sales_y1: number; pat_y1: number;
  avg_dscr: number | null; min_dscr: number | null; bep_pct_y1: number | null; bep_sales_y1: number | null; payback_months: number | null; min_cash: number;
};
export type PL = { year: number; sales: number; raw_material: number; gross_margin: number; fixed: number; fixed_heads: Record<string, number>; ebitda: number;
  depreciation: number; interest: number; pbt: number; tax: number; pat: number; pat_pct: number };
export type Warning = { level: "error" | "warn" | "info"; code: string; text: string };
export type Result = {
  summary: Summary; pl: PL[]; warnings: Warning[];
  cash_flow: { year: number; opening: number; cash_accrual: number; principal: number; drawings: number; closing: number }[];
  dscr: { year: number; available: number; debt_service: number; dscr: number | null; bep_sales: number | null; bep_pct: number | null }[];
  repayment_yearly: { year: number; opening: number; interest: number; principal: number; payment: number; closing: number }[];
  monthly_y1: { month: number; sales: number; profit: number }[];
  cost_table: { head: string; spec: string; qty: number; rate: number; amount: number }[];
};
export type SchemeCheck = {
  code: string; name: string; name_te: string | null; kind: string; url: string | null; eligible: boolean; needs_check: boolean;
  checks: { ok: boolean | null; text: string }[]; own_pct: number; own_amount: number; subsidy_pct: number; subsidy: number; subsidy_on: string;
  tier: string | null; category: string; area: string; sample: boolean; verified_on: string | null; notes: string | null;
};
export type Owner = { type: "entrepreneur" | "group" | null; id: number | null; name: string; mobile?: string | null; stage?: number; district_name?: string | null };
export type Headline = { project_cost?: number; loan?: number; own?: number; subsidy?: number; emi?: number; sales_y1?: number; pat_y1?: number;
  avg_dscr?: number | null; min_dscr?: number | null; bep_pct_y1?: number | null; payback_months?: number | null; errors?: number };
export type DprRow = {
  id: number; code: string; unit_name: string; owner: Owner; status: "draft" | "reviewed" | "approved"; version: number; model_id: number | null;
  model: string | null; sector: string | null; activity: string; scheme_code: string | null; district: string | null; district_name: string | null;
  results: Headline; prepared_by: string | null; reviewed_by: string | null; approved_by: string | null; approved_at: string | null; updated_at: string | null;
};
export type AppRow = {
  id: number; code: string; dpr_id: number; dpr_code: string | null; dpr_version: number; unit_name: string | null; owner: Owner; scheme_code: string | null;
  bank: string; bank_name: string; branch: string; ifsc: string | null; district_name: string | null; amount_requested: number; app_number: string | null;
  portal: string | null; submitted_on: string | null; status: string; status_label: string; next: string[]; sanctioned_amount: number | null;
  subsidy_amount: number | null; sanctioned_on: string | null; disbursed_on: string | null; disbursed_amount: number | null; interest_pct: number | null;
  emi_amount: number | null; tenure_months: number | null; first_emi_date: string | null; rejection_reason: string | null; rejection_label: string | null;
  rejection_note: string | null; docs_total: number; docs_have: number; missing_docs: string[];
  repayment: { total: number; paid: number; on_time: number; late: number; overdue: number; overdue_amount: number; paid_amount: number;
    next: { n: number; due_date: string; amount: number } | null; health: "on_time" | "delayed" | "default" } | null;
  updated_at: string | null;
};
export type AppDetail = AppRow & {
  documents: { code: string; label: string; have: boolean; file: string | null; note: string | null; url: string | null }[];
  events: { id: number; kind: string; status: string | null; status_label: string | null; text: string | null; on: string | null; by: string | null; at: string | null }[];
  schedule: { id: number; n: number; due_date: string; amount: number; principal: number; interest: number; balance: number; paid_amount: number | null;
    paid_on: string | null; note: string | null; state: "paid" | "late" | "overdue" | "due" | "upcoming" }[];
  can: { write: boolean };
};
export type DprDetail = DprRow & {
  mandal: string | null; village: string | null; address: string | null; lat: number | null; lng: number | null; location: string;
  inputs: Inputs; narrative: Record<string, string>; narrative_notes: Record<string, string>; narrative_source: string | null;
  sections: { key: string; label: string }[]; note_fields: { key: string; label: string; hint: string }[];
  versions: { id: number; version: number; status: string; note: string | null; by: string | null; at: string | null }[];
  result: Result; eligibility: SchemeCheck[]; applications: AppRow[]; can: { edit: boolean; approve: boolean; apply: boolean };
};
export type EModel = {
  id: number; code: string; sector: string; name_en: string; name_te: string | null; description: string | null; activity: string; context_tags: string[];
  investment_min: number | null; investment_max: number | null; working_capital: number; equipment: (CapItem & { suppliers?: string })[]; equipment_total: number;
  infrastructure: string[]; skills: string[]; schemes: string[]; sales_template: Partial<Inputs["sales"]>; expense_template: Partial<Inputs["expenses"]>;
  expected_monthly_sales: number | null; jobs: number | null; payback_months: number | null; status: string;
};
export type Scheme = {
  id: number; code: string; name: string; name_te: string | null; kind: string; agency: string | null; description: string | null; url: string | null;
  rules: Record<string, unknown>; documents: { code: string; label: string; when: string }[]; active: boolean; verified_on: string | null; sample: boolean;
};
export type DprMeta = {
  models: EModel[]; schemes: Scheme[]; banks: { code: string; name: string }[]; activities: { code: string; label: string }[];
  statuses: { code: string; label: string }[]; flow: Record<string, string[]>; rejection_reasons: { code: string; label: string }[];
  sections: { key: string; label: string }[]; can: { write: boolean; approve: boolean; models: boolean; schemes: boolean }; ai: boolean;
};

export function useDprMeta() {
  const [meta, setMeta] = useState<DprMeta | null>(null);
  useEffect(() => {
    api<DprMeta>("/dpr/meta").then(setMeta).catch(() => {});
  }, []);
  return meta;
}

/** ₹ with Indian grouping, no decimals. */
export const inr = (n: number | null | undefined) => (n == null || Number.isNaN(n) ? "—" : `₹${Math.round(n).toLocaleString("en-IN")}`);
/** Short form for tiles: ₹2.81 L, ₹1.2 Cr. */
export const inrShort = (n: number | null | undefined) => {
  if (n == null) return "—";
  const a = Math.abs(n);
  if (a >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (a >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  return inr(n);
};
export const ratio = (n: number | null | undefined) => (n == null ? "—" : n.toFixed(2));
export const pct = (n: number | null | undefined, d = 0) => (n == null ? "—" : `${n.toFixed(d)}%`);
export const fmtDay = (d: string | null | undefined) =>
  d ? new Date(d.length === 10 ? d + "T00:00:00" : d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";
export const today = () => new Date().toISOString().slice(0, 10);

export const DPR_TAG: Record<string, string> = { draft: "grey", reviewed: "amber", approved: "ok" };
export const APP_TAG: Record<string, string> = { draft: "grey", submitted: "", query: "amber", sanctioned: "ok", disbursed: "ok", rejected: "alert", withdrawn: "grey" };
export const STATE_TAG: Record<string, [string, string]> = {
  paid: ["ok", "paid"], late: ["amber", "paid late"], overdue: ["alert", "overdue"], due: ["amber", "due"], upcoming: ["grey", "upcoming"],
};
export const HEALTH: Record<string, [string, string]> = { on_time: ["ok", "On time"], delayed: ["amber", "Delayed"], default: ["alert", "Default risk"] };

/** Number input that keeps an empty box while typing and reports numbers. */
export function Num({ value, onChange, min = 0, max, step, disabled, label, width }: {
  value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; disabled?: boolean; label?: string; width?: number;
}) {
  const [text, setText] = useState(String(value ?? 0));
  useEffect(() => {
    if (Number(text) !== value) setText(String(value ?? 0));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return (
    <input className="input" type="number" inputMode="decimal" aria-label={label} min={min} max={max} step={step ?? "any"} disabled={disabled}
      style={width ? { width } : undefined} value={text}
      onChange={(e) => { setText(e.target.value); const v = Number(e.target.value); if (e.target.value !== "" && !Number.isNaN(v)) onChange(v); }}
      onBlur={() => { if (text === "" || Number.isNaN(Number(text))) { setText("0"); onChange(0); } }} />
  );
}
