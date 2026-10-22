// Entrepreneur app – "My enterprise set-up": what is being bought and when it arrives, registrations (upload a document
// from the phone), the readiness checklist and the asset list. English and Telugu.
import { Camera, CheckCircle2, Circle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUpload } from "../api";
import { useLang } from "../i18n";

type Item = { key: string; label: string; done: boolean; note: string | null };
type Unit = {
  id: number; code: string; name: string; status: string; model: string | null; location: string; launch_date: string | null;
  readiness: { done: number; total: number }; checklist: Item[];
  purchase_list: { id: number; title: string; status: string; status_label: string; supplier: string | null; expected_delivery: string | null; delivered_on: string | null;
    installed_on: string | null; items: { item: string; qty: number }[] }[];
  registration_list: { id: number; label: string; status: string; number: string | null; note: string | null }[];
  assets: { id: number; item: string; serial_no: string | null; warranty_until: string | null }[];
};
const T = {
  title: ["My enterprise set-up", "నా వ్యాపారం ఏర్పాటు"], none: ["Set-up starts when your loan is sanctioned (or your own-funds plan is approved).", "మీ రుణం మంజూరైన తర్వాత (లేదా సొంత నిధుల ప్రణాళిక ఆమోదం తర్వాత) ఏర్పాటు మొదలవుతుంది."],
  ready: ["Ready to launch", "ప్రారంభానికి సిద్ధం"], launched: ["Launched", "ప్రారంభమైంది"], setting: ["Setting up", "ఏర్పాటు జరుగుతోంది"],
  buying: ["What is being bought", "కొనుగోళ్లు"], due: ["arrives by", "అందే తేదీ"], delivered: ["delivered", "అందింది"], installed: ["installed", "అమర్చారు"],
  regs: ["Registrations", "నమోదులు"], upload: ["Upload", "అప్‌లోడ్"], check: ["Readiness checklist", "సిద్ధత జాబితా"], assets: ["My equipment", "నా పరికరాలు"],
  warranty: ["warranty till", "వారంటీ"], back: ["Programme", "కార్యక్రమం"],
  st: { todo: ["to do", "చేయాలి"], applied: ["applied", "దరఖాస్తు చేశారు"], done: ["done", "పూర్తి"], not_needed: ["not needed", "అవసరం లేదు"] } as Record<string, [string, string]>,
};
const TAG: Record<string, string> = { todo: "alert", applied: "amber", done: "ok", not_needed: "grey" };

export default function MyUnit() {
  const { lang } = useLang();
  const i = lang === "te" ? 1 : 0;
  const t = (k: Exclude<keyof typeof T, "st">) => (T[k] as [string, string])[i];
  const [units, setUnits] = useState<Unit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const target = useRef<number | null>(null);
  const load = useCallback(() => api<{ units: Unit[] }>(`/setup/me?lang=${lang}`).then((r) => setUnits(r.units)).catch((e) => setError(e.message)), [lang]);
  useEffect(() => {
    load();
  }, [load]);
  const day = (d: string | null) => (d ? new Date(d + "T00:00:00").toLocaleDateString(lang === "te" ? "te-IN" : "en-IN", { day: "numeric", month: "short", year: "numeric" }) : "");
  const upload = async (f?: File) => {
    if (!f || !target.current) return;
    const fd = new FormData();
    fd.append("file", f);
    try {
      setUnits((await apiUpload<{ units: Unit[] }>(`/setup/me/registrations/${target.current}/file`, fd)).units);
    } catch (e) {
      setError((e as Error).message);
    }
    if (fileRef.current) fileRef.current.value = "";
  };
  if (!units) return error ? <div className="error">{error}</div> : <div className="muted">…</div>;
  return (
    <div className="stack">
      <Link to="/programme" className="small">← {t("back")}</Link>
      <h1 style={{ margin: 0 }}>{t("title")}</h1>
      {error && <div className="error">{error}</div>}
      <input ref={fileRef} type="file" accept="image/*,application/pdf" hidden onChange={(e) => upload(e.target.files?.[0])} />
      {units.length === 0 && <div className="card">{t("none")}</div>}
      {units.map((u) => {
        const all = u.readiness.done === u.readiness.total;
        return (
          <div key={u.id} className="stack">
            <div className="plan-hero">
              <div className="row-between"><span className="tag">{u.status === "launched" ? t("launched") : all ? t("ready") : t("setting")}</span><small>{u.code}</small></div>
              <h2>{u.name}</h2>
              <div className="small">{u.model} · {u.location}</div>
              <div className="seat-bar" style={{ marginTop: 12, background: "rgba(255,255,255,.2)" }}><span style={{ width: `${(100 * u.readiness.done) / Math.max(1, u.readiness.total)}%`, background: "#ffc85a" }} /></div>
              <small>{u.readiness.done} / {u.readiness.total}{u.launch_date ? ` · ${day(u.launch_date)}` : ""}</small>
            </div>
            {u.purchase_list.filter((p) => p.status !== "cancelled").length > 0 && (
              <div className="card stack">
                <b>{t("buying")}</b>
                {u.purchase_list.filter((p) => p.status !== "cancelled").map((p) => (
                  <div key={p.id} className="row-between small">
                    <span><b>{p.title}</b>{p.supplier ? ` · ${p.supplier.replace("Sample: ", "")}` : ""}<div className="muted">{p.items.map((x) => x.item).join(", ")}</div></span>
                    <span className={`tag ${p.status === "installed" ? "ok" : p.status === "ordered" ? "" : "grey"}`}>
                      {p.installed_on ? `${t("installed")} ${day(p.installed_on)}` : p.delivered_on ? `${t("delivered")} ${day(p.delivered_on)}` : p.expected_delivery ? `${t("due")} ${day(p.expected_delivery)}` : p.status_label}</span>
                  </div>))}
              </div>)}
            <div className="card stack">
              <b>{t("regs")}</b>
              {u.registration_list.map((r) => (
                <div key={r.id} className="row-between small">
                  <span>{r.label}{r.number ? <div className="muted">{r.number}</div> : null}</span>
                  <span className="row-gap" style={{ alignItems: "center" }}>
                    <span className={`tag ${TAG[r.status]}`}>{T.st[r.status]?.[i] ?? r.status}</span>
                    {r.status !== "done" && r.status !== "not_needed" && u.status === "setting_up" &&
                      <button className="btn small secondary" onClick={() => { target.current = r.id; fileRef.current?.click(); }}><Camera size={14} /> {t("upload")}</button>}
                  </span>
                </div>))}
            </div>
            <div className="card stack">
              <b>{t("check")}</b>
              {u.checklist.map((c) => (
                <div key={c.key} className="row-gap small" style={{ alignItems: "center" }}>
                  {c.done ? <CheckCircle2 size={18} color="var(--ok)" /> : <Circle size={18} color="#b9c4be" />}<span>{c.label}</span></div>))}
            </div>
            {u.assets.length > 0 && (
              <div className="card stack">
                <b>{t("assets")}</b>
                {u.assets.map((a) => <div key={a.id} className="row-between small"><span>{a.item}{a.serial_no ? <div className="muted">{a.serial_no}</div> : null}</span>
                  <span className="muted">{a.warranty_until ? `${t("warranty")} ${day(a.warranty_until)}` : ""}</span></div>)}
              </div>)}
          </div>);
      })}
    </div>
  );
}
