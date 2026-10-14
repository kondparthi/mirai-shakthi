// Small API client. VITE_API_BASE is empty in dev (Vite proxy) and set to the server URL in the Android build.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";
const TOKEN_KEY = "mirai_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable – session lasts until reload */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T = unknown>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/v1${path}`, {
      method: options.method ?? (options.body ? "POST" : "GET"),
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "No internet connection. Please check your network and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401) setToken(null);
    const detail = (data as { detail?: unknown }).detail;
    const message = Array.isArray(detail)
      ? detail.map((d: { msg?: string }) => d.msg?.replace(/^Value error, /, "")).join(", ")
      : typeof detail === "string"
        ? detail
        : "Something went wrong. Please try again.";
    throw new ApiError(res.status, message);
  }
  return data as T;
}

/** Upload a file (multipart form). Same error handling as api(). */
export async function apiUpload<T = unknown>(path: string, form: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/v1${path}`, { method: "POST", headers, body: form });
  } catch {
    throw new ApiError(0, "No internet connection. Please check your network and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401) setToken(null);
    const detail = (data as { detail?: unknown }).detail;
    throw new ApiError(res.status, typeof detail === "string" ? detail : res.status === 413 ? "The file is too large." : "Something went wrong. Please try again.");
  }
  return data as T;
}

// ---- Types shared with the backend ----
export type User = { id: number; name: string | null; mobile: string | null; role: string; language: "en" | "te"; has_profile: boolean };

export type Profile = {
  owner_name: string;
  business_name?: string | null;
  stage: string;
  business_type: string;
  sector: string;
  product: string;
  district: string;
  mandal?: string | null;
  ownership: string;
  turnover_band: number;
  employees: number;
  registrations: string[];
  channels: string[];
  books_kept: string;
  has_loan?: boolean | null;
  flags: string[];
  summary?: string[];
};

export type Option = [string | number, string];
export type ProfileOptions = {
  stage: Option[]; business_type: Option[]; sector: string[]; ownership: Option[]; turnover_band: Option[];
  registrations: Option[]; channels: Option[]; books_kept: Option[]; flags: Option[]; districts: string[];
  labels?: Record<string, string>;
};

export type GapItem = { code: string; title: string; why?: string | null; order: number; documents?: string | null; time?: string | null; cost?: string | null; link?: string | null; n?: number };
export type Source = { n: number; title: string; url: string | null; verified_on: string | null; verified_by: string | null };
export type ExpertCard = { id: number; name: string; organisation: string | null; type: string; fee_note: string | null; response_hours: number; rating: number | null; languages: string[] };

export type GuidanceResult = {
  session_id?: number;
  message_id?: number;
  current_step: number;
  message?: string;
  understanding: {
    module: string | null; module_label: string | null; intent_code: string | null; intent_title: string | null;
    confidence: number; method: string; profile_summary: string[]; missing_profile_fields: string[];
    related?: { code: string; title: string; question: string }[];
  };
  identification?: { have: GapItem[]; missing: GapItem[] };
  information?: { answer: string; method: string; grounded: boolean; sources: Source[] };
  guidance?: { steps: GapItem[] };
  connect?: { service: string; suggested: boolean; reason: string; experts: ExpertCard[] };
};

export type ModuleCard = { code: string; name: string; name_te: string; area: string; area_te?: string; topics: { code: string; title: string; title_te: string | null }[]; popular_questions: string[] };
export type SessionSummary = { id: number; title: string; module: string | null; current_step: number; updated_at: string | null };
export type SessionDetail = SessionSummary & {
  messages: { id: number; role: "user" | "assistant"; content: string; payload: GuidanceResult | null; rating: number | null }[];
  gaps: { code: string; title: string; status: string }[];
};

// ---- Documents (Sprint 3) ----
export type ArtefactSummary = { id: number; kind: "roadmap" | "checklist" | "cashflow" | "jd"; title: string; session_id: number | null; created_at: string | null };
export type Artefact = ArtefactSummary & { inputs: Record<string, unknown> | null; outputs: Record<string, unknown> | null };

/** Get a short-lived download link and open it (works in the browser and the Android app). */
export async function downloadArtefact(id: number) {
  const r = await api<{ url: string }>(`/artefacts/${id}/link`, { method: "POST" });
  const url = `${BASE}${r.url}`;
  // Pop-up blockers can stop window.open after an await; the file is an attachment, so the fallback just downloads it.
  if (!window.open(url, "_blank")) window.location.href = url;
}

// ---- Handholding (Sprint 4) ----
export type ConnectUpdate = { id: number; role: "msme" | "expert" | "admin" | "system"; kind: string; status: string | null;
  status_label: string | null; text: string | null; amount: number | null; at: string | null };
export type ConnectRequest = {
  id: number; status: string; status_label: string; service: string; service_label: string; created_at: string | null;
  updated_at: string | null; session_id: number | null; last_update: string | null;
  expert: { id: number; name: string; organisation: string | null; type: string; fee_note: string | null; response_hours: number; rating: number | null } | null;
  quote: { amount: number; note: string | null; at: string | null } | null;
  rating: { stars: number; comment: string | null } | null;
  respond_by: string | null; overdue: boolean; response_hours: number;
  client?: { name: string | null; business: string | null; district: string | null; language: string; mobile: string | null; profile: string[] };
  summary?: string; preferred_contact?: string | null; budget?: string | null;
  shared_documents?: { id: number; kind: string; title: string }[];
  updates?: ConnectUpdate[]; actions?: string[];
};

export const SERVICE_LABELS: Record<string, string> = {
  registration_filing: "Registration filing", gst_filing: "GST registration / filing", export_facilitation: "Export facilitation",
  ecommerce_onboarding: "Online selling set-up", gem_onboarding: "GeM onboarding", marketing_support: "Marketing support",
  sector_advice: "Sector advice", accounting: "Accounting / bookkeeping", loan_application: "Loan application",
  legal_recovery: "Payment recovery", hr_support: "HR and labour compliance", training: "Training (EDP / skills)",
  dpr_preparation: "DPR / project report", general_advice: "General advice",
};

/** Open a download URL returned by the API (expert document links). */
export function openDownload(url: string) {
  const full = `${BASE}${url}`;
  if (!window.open(full, "_blank")) window.location.href = full;
}
