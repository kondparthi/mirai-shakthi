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
  /** Structured detail when the server sends more than a message (e.g. possible duplicates). */
  detail?: Record<string, unknown>;
  constructor(status: number, message: string, detail?: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function errorMessage(status: number, detail: unknown): string {
  if (Array.isArray(detail))
    return detail.map((d: { msg?: string; loc?: (string | number)[] }) => {
      const field = d.loc && d.loc.length > 1 ? String(d.loc[d.loc.length - 1]).replace(/_/g, " ") : "";
      const msg = (d.msg ?? "").replace(/^Value error, /, "");
      return field && !["body", "data"].includes(field) && msg.startsWith("Field required") ? `${field}: required` : msg;
    }).join(", ");
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && typeof (detail as { message?: unknown }).message === "string") return (detail as { message: string }).message;
  return status === 413 ? "The file is too large." : "Something went wrong. Please try again.";
}

/** Full URL for a server path such as a photo link (needed in the Android build where the API is on another host). */
export const apiUrl = (path: string) => `${BASE}${path}`;

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
    throw new ApiError(res.status, errorMessage(res.status, detail),
      detail && typeof detail === "object" && !Array.isArray(detail) ? (detail as Record<string, unknown>) : undefined);
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
    throw new ApiError(res.status, errorMessage(res.status, (data as { detail?: unknown }).detail));
  }
  return data as T;
}

// ---- Types shared with the backend ----
export type User = { id: number; name: string | null; mobile: string | null; email?: string | null; role: string; language: "en" | "te"; has_profile: boolean;
  scope?: { districts?: string[]; sectors?: string[] } };

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

/** Download a file that needs the login header (CSV exports), or save JSON data as a file. */
export async function apiDownload(path: string, filename: string) {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/v1${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw new ApiError(0, "No internet connection. Please check your network and try again.");
  }
  if (!res.ok) throw new ApiError(res.status, "Could not download the file.");
  saveBlob(await res.blob(), filename);
}

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// ---- Phase 1: programme (enrolment, groups, readiness) ----
export type MasterOpt = { code: string; name_en: string; name_te: string | null; data: Record<string, unknown> };
export type Assessment = {
  id: number; score: number; band?: string; at: string | null; remarks: string | null; recommended: string[]; strengths: string[];
  gaps: { code: string; label: string; advice: string | null }[];
  breakdown: { code: string; label: string; answer: string | number | null; points: number; max: number }[];
  answers: Record<string, string | number>;
};
export type EntrepreneurRow = {
  id: number; full_name: string; mobile: string; gender: string | null; district: string | null; district_name: string | null;
  mandal: string | null; mandal_name: string | null; village: string | null; village_name: string | null; context_tag: string | null;
  stage: number; stage_name: string; status: string; verified: boolean; source: string; interests: string[]; interest_names: string[];
  readiness: { score: number; at: string | null } | null; has_photo: boolean; photo_url: string | null; consent: boolean; created_at: string | null;
};
export type Entrepreneur = EntrepreneurRow & {
  dob: string | null; social_category: string | null; education: string | null; aadhaar_masked: string | null; pan: string | null;
  bank_masked: string | null; ifsc: string | null; bank_name: string | null; skills: string[]; skill_names: string[];
  investment_available: number | null; has_loans: boolean | null; emi_amount: number | null; occupation: string | null;
  monthly_income: number | null; consent_version: string | null; consent_at: string | null;
  groups: { id: number; name: string; role: string }[]; missing: string[];
  social_category_name?: string | null; education_name?: string | null; occupation_name?: string | null; bank_label?: string | null;
  enrolled_by?: string | null; linked_account?: boolean; assessments?: Assessment[];
};
export type ReadinessQuestion = { code: string; label: string; kind: "choice" | "text"; options: [string, string][] };
export const PAGE_SIZE = 25;

// ---- Phase 1 Sprint 2: training ----
export type Track = "awareness" | "core" | "skill" | "ojt" | "exposure" | "refresher";
export type CourseLite = { id: number; code: string; track: Track; track_label: string; name: string; name_en: string; name_te: string | null;
  duration_days: number; sectors: string[]; active: boolean; sessions_count: number; external_certificate: string | null; description?: string | null };
export type CourseFull = CourseLite & { description_en: string | null; description_te: string | null; sessions: { topic_en: string; topic_te: string | null; hours: number | null }[];
  outcomes: string[]; pass_mark: number; min_attendance: number; practical_checklist: string[]; business_plan_score: boolean };
export type BatchRow = {
  id: number; code: string; course: CourseLite; partner: string | null; partner_id: number | null; trainer_ids: number[]; mentor_ids: number[];
  trainers: string[]; mentors: string[]; mode: string; start_date: string; end_date: string; venue: string | null; host_unit: string | null;
  district: string | null; district_name: string | null; seats: number; filled: number; requested: number; sponsor_type: string;
  sponsor_name: string | null; pass_mark: number; status: string; sessions_total: number; sessions_done: number; certified: number;
};
export type SessionRow = { id: number; n: number; date: string | null; topic: string; topic_en: string; topic_te: string | null; hours: number | null;
  done: boolean; present: number; present_ids: number[]; photo_url: string | null; lat: number | null; lng: number | null; checkin_open: boolean };
export type TraineeRow = {
  id: number; status: string; source: string; mentor_id: number | null; mentor: string | null;
  entrepreneur: { id: number; full_name: string; mobile: string; village_name: string | null; district_name: string | null; photo_url: string | null; stage: number };
  attended: number; held: number; total: number; attendance_pct: number; quiz_score: number | null; practical: Record<string, boolean>;
  practical_hours: number | null; bp_score: number | null; result: string | null; suggested: string; suggested_why: string[];
  certificate_no: string | null; certified_at: string | null; feedback_rating: number | null; feedback_text: string | null;
};
export type BatchDetail = Omit<BatchRow, "course"> & { course: CourseFull; sessions: SessionRow[]; trainees: TraineeRow[]; can_run: boolean; can_plan: boolean };
export type TrainingMeta = { tracks: { code: Track; label: string; label_te: string }[]; trainers: { id: number; name: string }[];
  mentors: { id: number; name: string }[]; courses: CourseLite[]; partners: { id: number; name: string; kind: string }[] };
export type ExternalCert = { id: number; kind: string; title: string; number: string | null; issuer: string | null; issued_on: string | null;
  status: string; note: string | null; file_url: string | null; at: string | null };

/** Open a short-lived file link (certificate PDF, uploaded document). */
export async function openLink(path: string) {
  const r = await api<{ url: string }>(path, { method: "POST" });
  const url = `${BASE}${r.url}`;
  if (!window.open(url, "_blank")) window.location.href = url;
}
