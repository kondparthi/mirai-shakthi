// Shared types for enterprise set-up and procurement (M7).
import { useEffect, useState } from "react";
import { api } from "../../api";

export type Owner = { type: "entrepreneur" | "group" | null; id: number | null; name: string; mobile?: string | null; stage?: number };
export type UnitRow = {
  id: number; code: string; name: string; owner: Owner; status: "setting_up" | "launched" | "paused" | "closed"; dpr_id: number | null; dpr_code: string | null;
  model: string | null; model_code: string | null; district: string | null; district_name: string | null; location: string; launch_date: string | null;
  readiness: { done: number; total: number }; purchases: { total: number; installed: number; ordered_value: number };
  registrations: { total: number; done: number }; updated_at: string | null;
};
export type CheckItem = { key: string; label: string; kind: "auto" | "manual"; done: boolean; note: string | null; photo_url: string | null; at: string | null; by: string | null };
export type PurchaseRow = {
  id: number; unit_id: number; title: string; items: { item: string; spec: string; qty: number; est_rate: number }[]; estimate: number; status: string;
  status_label: string; invited: number[]; quote_by: string | null; quotes_count: number; lowest: number | null; supplier: string | null;
  supplier_id: number | null; selected_quote_id: number | null; selection_reason: string | null; po_number: string | null; po_date: string | null;
  po_amount: number | null; payment_source: string | null; payment_label: string | null; expected_delivery: string | null; supplier_confirmed: boolean;
  delivered_on: string | null; installed_on: string | null; handover_note: string | null; late: boolean;
  photos: { url: string; caption: string | null; at: string | null }[];
};
export type Quote = {
  id: number; supplier_id: number; supplier: string; lines: { item: string; qty: number; rate: number }[]; amount: number; gst_included: boolean;
  delivery_days: number | null; warranty_months: number | null; valid_till: string | null; file_url: string | null; note: string | null;
  source: string; lowest: boolean; vs_estimate_pct: number | null; at: string | null;
};
export type PurchaseDetail = PurchaseRow & { quotes: Quote[]; invited_suppliers: { id: number; name: string; quoted: boolean }[]; unit: { id: number; code: string; name: string } };
export type Registration = { id: number; kind: string; label: string; status: "todo" | "applied" | "done" | "not_needed"; number: string | null;
  applied_on: string | null; issued_on: string | null; valid_until: string | null; file_url: string | null; note: string | null; expiring: boolean };
export type Asset = { id: number; item: string; spec: string | null; qty: number; value: number; serial_no: string | null; warranty_until: string | null;
  insurance_policy: string | null; insurance_until: string | null; shared: boolean; status: string; photo_url: string | null; purchase_id: number | null; supplier: string | null };
export type UnitDetail = UnitRow & {
  mandal: string | null; village: string | null; address: string | null; checklist: CheckItem[]; purchase_list: PurchaseRow[]; assets: Asset[];
  registration_list: Registration[]; dpr_items: { item: string; spec: string; qty: number; est_rate: number }[]; is_group: boolean;
  members: { name: string; role: string }[];
};
export type Supplier = {
  id: number; name: string; gstin: string | null; contact_name: string; mobile: string; email: string | null; address: string; categories: string[];
  items: string[]; models: string[]; districts: string[]; rate_card: { item: string; rate: number; unit: string; valid_till: string | null }[];
  approved: boolean; note: string | null; has_login: boolean; sample: boolean; login_email?: string | null;
  orders?: number; delivered?: number; on_time?: number; value?: number;
};
export type SetupMeta = { registrations: { code: string; label: string }[]; purchase_status: { code: string; label: string }[];
  payment_sources: { code: string; label: string }[]; can: { write: boolean; procure: boolean; launch: boolean } };

export function useSetupMeta() {
  const [m, setM] = useState<SetupMeta | null>(null);
  useEffect(() => {
    api<SetupMeta>("/setup/meta").then(setM).catch(() => {});
  }, []);
  return m;
}

export const UNIT_TAG: Record<string, [string, string]> = {
  setting_up: ["amber", "setting up"], launched: ["ok", "launched"], paused: ["grey", "paused"], closed: ["grey", "closed"],
};
export const P_TAG: Record<string, string> = { draft: "grey", rfq: "amber", ordered: "", delivered: "", installed: "ok", cancelled: "grey" };
export const REG_TAG: Record<string, [string, string]> = { todo: ["alert", "to do"], applied: ["amber", "applied"], done: ["ok", "done"], not_needed: ["grey", "not needed"] };
