// Entrepreneur app – "Join MIRAI programme" (Form 1.1), photo, readiness check (Form 1.3) and status.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUpload, apiUrl, type Assessment, type Entrepreneur } from "../api";
import { useAuth } from "../auth";
import EnrolForm, { type EnrolBody } from "../components/EnrolForm";
import { pt } from "../components/programmeText";
import { ReadinessForm, ReadinessResult } from "../components/Readiness";
import { useLang } from "../i18n";

type Me = { enrolled: boolean; needs_consent: boolean; entrepreneur?: Entrepreneur & { assessments: Assessment[] } };
const STAGES = 8;
const JOURNEY = ["Enrol & assess", "Train & certify", "DPR & finance", "Set up enterprise"];
const JOURNEY_TE = ["నమోదు & అంచనా", "శిక్షణ & ధృవీకరణ", "డీపీఆర్ & ఆర్థిక సహాయం", "వ్యాపారం ఏర్పాటు"];

export default function Programme() {
  const { lang } = useLang();
  const t = pt(lang);
  const { refresh } = useAuth();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"view" | "form" | "readiness">("view");
  const [latest, setLatest] = useState<Assessment | null>(null);
  const [photoBusy, setPhotoBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api<Me>(`/enrol/me?lang=${lang}`).then(setMe).catch((e) => setError(e.message)), [lang]);
  useEffect(() => {
    load();
  }, [load]);

  if (error) return <div className="error">{error}</div>;
  if (!me) return <div className="muted">…</div>;
  const e = me.entrepreneur;

  const save = async (body: EnrolBody) => {
    const r = await api<Me>(`/enrol/me?lang=${lang}`, { method: "PUT", body: { ...body, consent: true } });
    setMe(r);
    setMode("view");
    refresh();
    window.scrollTo(0, 0);
  };

  const uploadPhoto = async (f: File | undefined) => {
    if (!f) return;
    setPhotoBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      setMe(await apiUpload<Me>(`/enrol/me/photo?lang=${lang}`, fd));
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setPhotoBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  // ---- Not enrolled yet, or imported by staff and waiting for consent
  if (!me.enrolled || me.needs_consent || mode === "form") {
    if (mode !== "form")
      return (
        <div className="stack">
          <div className="join-hero">
            <h1>{t("joinTitle")}</h1>
            <p>{t("joinIntro")}</p>
            <ol className="journey">
              {(lang === "te" ? JOURNEY_TE : JOURNEY).map((s, i) => <li key={s}><span>{i + 1}</span>{s}</li>)}
            </ol>
          </div>
          {me.needs_consent && e && <div className="notice small">{t("importedNote")}</div>}
          <div className="card small">{t("joinNeed")}</div>
          <button className="btn block" onClick={() => setMode("form")}>{t("joinBtn")}</button>
        </div>
      );
    return (
      <div className="stack">
        <div className="row-between">
          <h1 style={{ margin: 0 }}>{me.enrolled && !me.needs_consent ? t("editDetails") : t("joinTitle")}</h1>
          <button className="btn ghost" onClick={() => setMode("view")}>✕</button>
        </div>
        <EnrolForm lang={lang} stepped initial={e} consent={!me.enrolled || me.needs_consent} onSubmit={save} />
      </div>
    );
  }

  // ---- Readiness questions
  if (mode === "readiness")
    return (
      <div className="stack">
        <div className="row-between">
          <h1 style={{ margin: 0 }}>{t("readiness")}</h1>
          <button className="btn ghost" onClick={() => setMode("view")}>✕</button>
        </div>
        <p className="muted small" style={{ margin: 0 }}>{t("readinessIntro")}</p>
        <ReadinessForm lang={lang} formPath={`/enrol/readiness/form?lang=${lang}`} submitPath={`/enrol/me/readiness?lang=${lang}`}
          onDone={(a) => { setLatest(a); setMode("view"); load(); window.scrollTo(0, 0); }} />
      </div>
    );

  // ---- Enrolled: status
  const last = latest ?? e!.assessments[0] ?? null;
  const missing = e!.missing.filter((m) => m !== "consent");
  return (
    <div className="stack">
      <h1 style={{ margin: 0 }}>{t("myProgramme")}</h1>
      <div className="card enrol-card">
        <div className="enrol-photo">
          {e!.photo_url ? <img src={apiUrl(e!.photo_url)} alt={t("photo")} /> : <span aria-hidden="true">{e!.full_name.slice(0, 1)}</span>}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <b>{e!.full_name}</b>
          <div className="small muted">{[e!.village_name, e!.mandal_name, e!.district_name].filter(Boolean).join(", ")}</div>
          <div className="chips" style={{ marginTop: 6 }}>
            <span className={`tag ${e!.verified ? "ok" : "amber"}`}>{e!.verified ? t("verified") : t("notVerified")}</span>
            {e!.interest_names.map((s) => <span key={s} className="tag grey">{s}</span>)}
          </div>
        </div>
      </div>

      <div className="card">
        <b className="small">{t("journey")}</b>
        <div className="stage-bar" aria-label={`${t("stage")} ${e!.stage} / ${STAGES}`}>
          {Array.from({ length: STAGES }, (_, i) => <span key={i} className={i < e!.stage ? "on" : ""} />)}
        </div>
        <div className="small">{t("stage")} {e!.stage}: <b>{e!.stage_name}</b></div>
      </div>

      {(missing.length > 0 || !e!.photo_url) && (
        <div className="card stack">
          {missing.length > 0 && (
            <div className="small"><b>{t("stillNeeded")}:</b> {missing.map((m) => ({ photo: t("photo"), aadhaar: t("aadhaar"), bank_account: t("bankAccount") } as Record<string, string>)[m] ?? m.replace(/_/g, " ")).join(", ")}</div>
          )}
          {!e!.photo_url && <small className="muted">{t("photoHint")}</small>}
        </div>
      )}
      <div className="row-gap">
        <input ref={fileRef} type="file" accept="image/*" capture="user" hidden onChange={(ev) => uploadPhoto(ev.target.files?.[0])} />
        <button className="btn secondary" disabled={photoBusy} onClick={() => fileRef.current?.click()}>
          {photoBusy ? t("saving") : e!.photo_url ? t("changePhoto") : t("addPhoto")}</button>
        <button className="btn secondary" onClick={() => setMode("form")}>{t("editDetails")}</button>
      </div>

      <Link to="/training" className="card programme-card">
        <div><b>{t("myTraining")}</b><div className="small">{t("trainingIntro")}</div></div>
        <span aria-hidden="true">→</span>
      </Link>
      {e!.stage >= 3 && (
        <Link to="/business-plan" className="card programme-card">
          <div><b>{t("myPlan")}</b><div className="small">{t("planIntro")}</div></div>
          <span aria-hidden="true">→</span>
        </Link>
      )}
      {e!.stage >= 4 && (
        <Link to="/my-mentor" className="card programme-card">
          <div><b>{t("myMentor")}</b><div className="small">{t("mentorIntro")}</div></div>
          <span aria-hidden="true">→</span>
        </Link>
      )}
      {e!.stage >= 4 && (
        <Link to="/my-books" className="card programme-card">
          <div><b>{t("myBooks")}</b><div className="small">{t("booksIntro")}</div></div>
          <span aria-hidden="true">→</span>
        </Link>
      )}
      {e!.stage >= 5 && (
        <Link to="/my-shop" className="card programme-card">
          <div><b>{t("myShop")}</b><div className="small">{t("shopIntro")}</div></div>
          <span aria-hidden="true">→</span>
        </Link>
      )}
      {e!.stage >= 4 && (
        <Link to="/my-unit" className="card programme-card">
          <div><b>{t("myUnit")}</b><div className="small">{t("unitIntro")}</div></div>
          <span aria-hidden="true">→</span>
        </Link>
      )}

      <div className="card stack">
        <h2 style={{ margin: 0 }}>{t("readiness")}</h2>
        {last ? <ReadinessResult a={last} lang={lang} /> : <p className="small muted" style={{ margin: 0 }}>{t("readinessIntro")}</p>}
        <button className="btn" onClick={() => setMode("readiness")}>{last ? t("retake") : t("takeCheck")}</button>
      </div>

      {e!.groups.length > 0 && (
        <div className="card">
          <b className="small">{t("myGroups")}</b>
          {e!.groups.map((g) => <div key={g.id} className="row-between small"><span>{g.name}</span><span className="tag grey">{g.role}</span></div>)}
        </div>
      )}
      <Link to="/my-data" className="small">{t("myData")} →</Link>
    </div>
  );
}
