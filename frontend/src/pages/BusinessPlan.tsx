// Entrepreneur app – "My business plan & loan": DPR key figures, approved DPR (PDF), loan status with history,
// documents still needed (photo / PDF upload from the phone) and the EMI schedule. English and Telugu.
import { Camera, CheckCircle2, Download, FileText } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUpload, openLink } from "../api";
import { useLang } from "../i18n";

type Figures = { project_cost: number; own: number; loan: number; subsidy: number; grant: number; emi: number; emi_months: number;
  monthly_sales_start: number; monthly_profit_y1: number; bep_pct_y1: number | null; payback_months: number | null };
type Plan = { id: number; code: string; unit_name: string; version: number; status: string; status_label: string; model: string | null;
  scheme_code: string | null; can_download: boolean; figures: Figures };
type App = {
  id: number; code: string; bank_name: string; branch: string; scheme_code: string | null; status: string; status_label: string; amount_requested: number;
  sanctioned_amount: number | null; subsidy_amount: number | null; disbursed_amount: number | null; emi_amount: number | null; tenure_months: number | null;
  documents: { code: string; label: string; have: boolean; note: string | null }[];
  events: { id: number; kind: string; status: string | null; status_label: string | null; text: string | null; on: string | null }[];
  schedule: { id: number; n: number; due_date: string; amount: number; paid_on: string | null; state: string }[];
  repayment: { paid: number; total: number; overdue: number; overdue_amount: number; next: { n: number; due_date: string; amount: number } | null } | null;
};
type Me = { enrolled: boolean; stage?: number; dprs: Plan[]; applications: App[] };

const T = {
  title: ["My business plan & loan", "నా వ్యాపార ప్రణాళిక & రుణం"],
  none: ["Your project report (DPR) is not ready yet. After your training, the DPR officer prepares it with you: equipment, sales, expenses and the loan you need.",
    "మీ ప్రాజెక్టు నివేదిక (డీపీఆర్) ఇంకా సిద్ధం కాలేదు. శిక్షణ తర్వాత డీపీఆర్ అధికారి మీతో కలిసి తయారు చేస్తారు: పరికరాలు, అమ్మకాలు, ఖర్చులు, కావాల్సిన రుణం."],
  notEnrolled: ["Join the MIRAI programme first.", "ముందుగా మిరాయ్ కార్యక్రమంలో చేరండి."],
  join: ["Join the programme", "కార్యక్రమంలో చేరండి"],
  cost: ["Project cost", "ప్రాజెక్టు వ్యయం"], own: ["Your share", "మీ వాటా"], loan: ["Bank loan", "బ్యాంకు రుణం"], subsidy: ["Subsidy", "సబ్సిడీ"],
  emi: ["Monthly EMI", "నెలవారీ వాయిదా (EMI)"], sales: ["Sales a month", "నెలకు అమ్మకాలు"], profit: ["Profit a month (year 1)", "నెలకు లాభం (1వ సంవత్సరం)"],
  bep: ["Break-even", "లాభనష్టరహిత స్థాయి"], ofSales: ["of sales", "అమ్మకాల్లో"], months: ["months", "నెలలు"],
  download: ["Download DPR (PDF)", "డీపీఆర్ డౌన్‌లోడ్ (PDF)"], wait: ["You can download the DPR after the DPR officer approves it.", "డీపీఆర్ అధికారి ఆమోదించిన తర్వాత డౌన్‌లోడ్ చేసుకోవచ్చు."],
  loanApp: ["Loan application", "రుణ దరఖాస్తు"], requested: ["Asked for", "కోరిన మొత్తం"], sanctioned: ["Sanctioned", "మంజూరు"],
  docs: ["Documents still needed", "ఇంకా కావాల్సిన పత్రాలు"], allDocs: ["All documents are in.", "అన్ని పత్రాలు అందాయి."],
  upload: ["Upload", "అప్‌లోడ్"], uploaded: ["Uploaded – staff will check", "అప్‌లోడ్ అయింది – సిబ్బంది పరిశీలిస్తారు"],
  history: ["What happened", "ఏం జరిగింది"], next: ["Next EMI", "తదుపరి వాయిదా"], overdue: ["overdue", "బకాయి"],
  schedule: ["EMI schedule", "వాయిదాల పట్టిక"], paidOf: ["paid of", "చెల్లించారు, మొత్తం"],
  state: { paid: ["paid", "చెల్లించారు"], late: ["paid late", "ఆలస్యంగా చెల్లించారు"], overdue: ["overdue", "బకాయి"], due: ["due", "చెల్లించాలి"], upcoming: ["upcoming", "రాబోయే"] } as Record<string, [string, string]>,
  query: ["Bank query", "బ్యాంకు ప్రశ్న"], response: ["Answered", "సమాధానం ఇచ్చారు"],
  sample: ["Telugu text is a first draft for MIRAI to review.", "తెలుగు పాఠం మిరాయ్ సమీక్ష కోసం మొదటి ముసాయిదా."],
};
const STATE_TAG: Record<string, string> = { paid: "ok", late: "amber", overdue: "alert", due: "amber", upcoming: "grey" };
const inr = (n: number | null | undefined) => (n == null ? "—" : `₹${Math.round(n).toLocaleString("en-IN")}`);

export default function BusinessPlan() {
  const { lang } = useLang();
  const i = lang === "te" ? 1 : 0;
  const t = (k: Exclude<keyof typeof T, "state">) => (T[k] as [string, string])[i];
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const target = useRef<{ aid: number; code: string } | null>(null);

  const load = useCallback(() => api<Me>(`/dpr/me?lang=${lang}`).then(setMe).catch((e) => setError(e.message)), [lang]);
  useEffect(() => {
    load();
  }, [load]);
  const date = (d: string | null) => (d ? new Date(d + "T00:00:00").toLocaleDateString(lang === "te" ? "te-IN" : "en-IN", { day: "numeric", month: "short", year: "numeric" }) : "");

  const upload = async (f?: File) => {
    const tg = target.current;
    if (!f || !tg) return;
    setBusy(tg.code);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      setMe(await apiUpload<Me>(`/dpr/me/applications/${tg.aid}/documents/${tg.code}`, fd));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  if (!me) return error ? <div className="error">{error}</div> : <div className="muted">…</div>;
  return (
    <div className="stack">
      <Link to="/programme" className="small">← {lang === "te" ? "కార్యక్రమం" : "Programme"}</Link>
      <h1 style={{ margin: 0 }}>{t("title")}</h1>
      {error && <div className="error">{error}</div>}
      {!me.enrolled && <div className="card stack"><p style={{ margin: 0 }}>{t("notEnrolled")}</p><Link to="/programme" className="btn">{t("join")}</Link></div>}
      {me.enrolled && me.dprs.length === 0 && <div className="card"><FileText aria-hidden="true" /> <p style={{ marginBottom: 0 }}>{t("none")}</p></div>}
      <input ref={fileRef} type="file" accept="image/*,application/pdf" hidden onChange={(e) => upload(e.target.files?.[0])} />

      {me.dprs.map((d) => (
        <div key={d.id} className="plan-hero">
          <div className="row-between"><span className="tag">{d.status_label}</span><small>{d.code} · v{d.version}</small></div>
          <h2>{d.unit_name}</h2>
          {d.model && <div className="small">{d.model}{d.scheme_code ? ` · ${d.scheme_code.toUpperCase()}` : ""}</div>}
          <div className="plan-figs">
            <div><small>{t("cost")}</small><b>{inr(d.figures.project_cost)}</b></div>
            <div><small>{t("own")}</small><b>{inr(d.figures.own)}</b></div>
            <div><small>{t("loan")}</small><b>{inr(d.figures.loan)}</b></div>
            {d.figures.subsidy > 0 && <div><small>{t("subsidy")}</small><b>{inr(d.figures.subsidy)}</b></div>}
            {d.figures.loan > 0 && <div><small>{t("emi")}</small><b>{inr(d.figures.emi)}</b> <small>× {d.figures.emi_months}</small></div>}
            <div><small>{t("sales")}</small><b>{inr(d.figures.monthly_sales_start)}</b></div>
            <div><small>{t("profit")}</small><b>{inr(d.figures.monthly_profit_y1)}</b></div>
            {d.figures.bep_pct_y1 != null && <div><small>{t("bep")}</small><b>{Math.round(d.figures.bep_pct_y1)}%</b> <small>{t("ofSales")}</small></div>}
          </div>
          <div style={{ marginTop: 12 }}>
            {d.can_download
              ? <button className="btn" onClick={() => openLink(`/dpr/me/dprs/${d.id}/pdf-link`).catch((e) => setError(e.message))}><Download size={16} /> {t("download")}</button>
              : <small>{t("wait")}</small>}
          </div>
        </div>
      ))}

      {me.applications.map((a) => {
        const missing = a.documents.filter((x) => !x.have);
        return (
          <div key={a.id} className="card stack">
            <div className="row-between"><b>{t("loanApp")}: {a.bank_name}</b><span className={`tag ${a.status === "rejected" ? "alert" : ["sanctioned", "disbursed"].includes(a.status) ? "ok" : a.status === "query" ? "amber" : ""}`}>{a.status_label}</span></div>
            <div className="small muted">{a.branch}{a.scheme_code ? ` · ${a.scheme_code.toUpperCase()}` : ""} · {a.code}</div>
            <div className="kv"><span>{t("requested")}</span><b>{inr(a.amount_requested)}</b></div>
            {a.sanctioned_amount != null && <div className="kv"><span>{t("sanctioned")}</span><b>{inr(a.sanctioned_amount)}{a.subsidy_amount ? ` + ${t("subsidy")} ${inr(a.subsidy_amount)}` : ""}</b></div>}

            {a.repayment?.next && (
              <div className="emi-next"><div><small>{t("next")}</small><div><b>{inr(a.repayment.next.amount)}</b> · {date(a.repayment.next.due_date)}</div></div>
                {a.repayment.overdue > 0 && <span className="tag alert">{a.repayment.overdue} {t("overdue")} · {inr(a.repayment.overdue_amount)}</span>}</div>)}

            {!["disbursed", "rejected", "withdrawn"].includes(a.status) && (
              <div className="stack" style={{ gap: 6 }}>
                <b className="small">{missing.length ? t("docs") : t("allDocs")}</b>
                {missing.map((x) => (
                  <div key={x.code} className="row-between small">
                    <span>{x.label}</span>
                    <button className="btn small secondary" disabled={busy === x.code} onClick={() => { target.current = { aid: a.id, code: x.code }; fileRef.current?.click(); }}>
                      <Camera size={14} /> {t("upload")}</button>
                  </div>))}
                {a.documents.filter((x) => x.have && x.note?.includes("entrepreneur")).map((x) => (
                  <div key={x.code} className="small" style={{ color: "var(--ok)" }}><CheckCircle2 size={14} /> {x.label} – {t("uploaded")}</div>))}
              </div>
            )}

            <details>
              <summary className="small"><b>{t("history")}</b></summary>
              <ol className="loan-timeline" style={{ marginTop: 10 }}>
                {[...a.events].reverse().map((e) => (
                  <li key={e.id} className={e.kind}>
                    <div className="row-between small"><b>{e.kind === "status" ? e.status_label : e.kind === "query" ? t("query") : t("response")}</b><span className="muted">{date(e.on)}</span></div>
                    {e.text && <div className="small">{e.text}</div>}
                  </li>))}
              </ol>
            </details>

            {a.schedule.length > 0 && a.repayment && (
              <details>
                <summary className="small"><b>{t("schedule")}</b> · {a.repayment.paid} {t("paidOf")} {a.repayment.total}</summary>
                <div className="stack" style={{ gap: 4, marginTop: 8 }}>
                  {a.schedule.map((r) => (
                    <div key={r.id} className="row-between small"><span>{r.n}. {date(r.due_date)}</span>
                      <span>{inr(r.amount)} <span className={`tag ${STATE_TAG[r.state]}`}>{T.state[r.state]?.[i] ?? r.state}</span></span></div>))}
                </div>
              </details>
            )}
          </div>
        );
      })}
      {lang === "te" && <p className="small muted">{t("sample")}</p>}
    </div>
  );
}
