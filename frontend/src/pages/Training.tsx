// Entrepreneur app – My training: recommended tracks, my batches (attendance, result, certificate, feedback),
// batches I can join, check-in with a code, and uploading outside certificates. English / Telugu.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUpload, apiUrl, openLink, type CourseLite, type ExternalCert } from "../api";
import { pt } from "../components/programmeText";
import { useLang } from "../i18n";

type MyBatch = {
  trainee_id: number; status: string; batch_status: string; code: string; course: CourseLite; start_date: string; end_date: string; mode: string;
  venue: string | null; district_name: string | null; attended: number; held: number; total: number; attendance_pct: number; result: string | null;
  certificate_no: string | null; verify_url: string | null; feedback_rating: number | null;
  sessions: { n: number; date: string | null; topic: string; done: boolean; present: boolean; checkin_open: boolean }[];
};
type OpenBatch = { id: number; code: string; course: CourseLite; start_date: string; end_date: string; mode: string; venue: string | null;
  district_name: string | null; seats_left: number; recommended: boolean; sponsor: string | null };
type Me = { enrolled: boolean; recommended?: { track: string; label: string }[]; batches?: MyBatch[]; open_batches?: OpenBatch[]; external?: ExternalCert[] };

const dt = (d: string, lang: string) => new Date(d + "T00:00:00").toLocaleDateString(lang === "te" ? "te-IN" : "en-IN", { day: "numeric", month: "short" });

function CodeCheckin({ onDone }: { onDone: () => void }) {
  const { lang } = useLang();
  const t = pt(lang);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const send = async () => {
    setMsg(null);
    try {
      const r = await api<{ session: string; n: number }>(`/training/me/checkin?lang=${lang}`, { body: { code } });
      setMsg({ ok: true, text: `${t("checkedIn")} – ${r.n}. ${r.session}` });
      setCode("");
      onDone();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  };
  return (
    <div className="card stack checkin-card">
      <div><b>{t("checkIn")}</b><div className="small">{t("checkInHint")}</div></div>
      <div className="row-gap">
        <input className="input code-input" style={{ flex: 1, minWidth: 0 }} inputMode="numeric" maxLength={6} placeholder="000000" aria-label="Check-in code"
          value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
        <button className="btn" disabled={code.length !== 6} onClick={send}>{t("checkInBtn")}</button>
      </div>
      {msg && <div className={msg.ok ? "notice ok-notice" : "error"}>{msg.text}</div>}
    </div>
  );
}

function Feedback({ b, onDone }: { b: MyBatch; onDone: () => void }) {
  const { lang } = useLang();
  const t = pt(lang);
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const send = async () => {
    await api("/training/me/feedback", { body: { trainee_id: b.trainee_id, rating, text: text || null } }).catch((e) => alert((e as Error).message));
    onDone();
  };
  return (
    <div className="stack" style={{ gap: 6 }}>
      <span className="small"><b>{t("rateTraining")}</b></span>
      <div className="stars" role="radiogroup" aria-label={t("rateTraining")}>
        {[1, 2, 3, 4, 5].map((n) => <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={`${n}`} className={n <= rating ? "on" : ""} onClick={() => setRating(n)}>★</button>)}
      </div>
      {rating > 0 && (<>
        <textarea className="input" rows={2} placeholder={t("feedbackPlaceholder")} value={text} onChange={(e) => setText(e.target.value)} />
        <div><button className="btn small" onClick={send}>{t("sendFeedback")}</button></div>
      </>)}
    </div>
  );
}

function UploadCert({ onDone }: { onDone: () => void }) {
  const { lang } = useLang();
  const t = pt(lang);
  const [f, setF] = useState({ kind: "dgca_rpc", title: "", number: "", issuer: "", issued_on: "" });
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const kinds: [string, string][] = [["dgca_rpc", "DGCA Remote Pilot"], ["fssai", "FSSAI"], ["partner", lang === "te" ? "భాగస్వామి శిక్షణ" : "Partner training"], ["other", lang === "te" ? "ఇతర" : "Other"]];
  const send = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      Object.entries(f).forEach(([k, v]) => v && fd.append(k, v));
      fd.append("file", file);
      await apiUpload("/training/me/external", fd);
      setF({ kind: "dgca_rpc", title: "", number: "", issuer: "", issued_on: "" });
      setFile(null);
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="stack">
      <div className="field"><span>{t("certKind")}</span>
        <div className="chips">{kinds.map(([k, l]) => <button key={k} type="button" className={`chip ${f.kind === k ? "on" : ""}`} onClick={() => setF({ ...f, kind: k, title: f.title || (k === "dgca_rpc" ? "DGCA Remote Pilot Certificate" : k === "fssai" ? "FSSAI" : "") })}>{l}</button>)}</div></div>
      <label className="field"><span>{t("certTitle")}</span><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></label>
      <label className="field"><span>{t("certNumber")}</span><input className="input" value={f.number} onChange={(e) => setF({ ...f, number: e.target.value })} /></label>
      <label className="field"><span>{t("certIssuer")}</span><input className="input" value={f.issuer} onChange={(e) => setF({ ...f, issuer: e.target.value })} /></label>
      <label className="field"><span>{t("certDate")}</span><input className="input" type="date" max={new Date().toISOString().slice(0, 10)} value={f.issued_on} onChange={(e) => setF({ ...f, issued_on: e.target.value })} /></label>
      <label className="field"><span>{t("certFile")}</span><input type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
      {error && <div className="error">{error}</div>}
      <button className="btn" disabled={busy || !file || f.title.trim().length < 2} onClick={send}>{busy ? t("saving") : t("upload")}</button>
    </div>
  );
}

export default function Training() {
  const { lang } = useLang();
  const t = pt(lang);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [upload, setUpload] = useState(false);
  const load = useCallback(() => api<Me>(`/training/me?lang=${lang}`).then(setMe).catch((e) => setError(e.message)), [lang]);
  useEffect(() => {
    load();
  }, [load]);
  if (error) return <div className="error">{error}</div>;
  if (!me) return <div className="muted">…</div>;
  if (!me.enrolled)
    return (
      <div className="stack">
        <h1 style={{ margin: 0 }}>{t("myTraining")}</h1>
        <div className="card">{t("joinIntro")}</div>
        <Link to="/programme" className="btn block">{t("joinBtn")}</Link>
      </div>
    );

  const act = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
    } catch (e) {
      alert((e as Error).message);
    }
    load();
  };
  const status: Record<string, string> = { requested: t("requested"), confirmed: t("confirmed"), completed: t("completedT"), withdrawn: t("withdrawn") };
  const active = (me.batches ?? []).filter((b) => b.status !== "withdrawn");
  const inBatch = active.some((b) => b.status === "confirmed");

  return (
    <div className="stack">
      <div><h1 style={{ margin: 0 }}>{t("myTraining")}</h1><p className="muted small" style={{ margin: "4px 0 0" }}>{t("trainingIntro")}</p></div>
      {me.recommended && me.recommended.length > 0 && (
        <div className="small">{t("recommendedForYou")}: <span className="chips" style={{ display: "inline-flex", marginTop: 4 }}>{me.recommended.map((r) => <span key={r.track} className="tag">{r.label}</span>)}</span></div>
      )}
      {inBatch && <CodeCheckin onDone={load} />}

      {active.length > 0 && <h2 style={{ marginBottom: 0 }}>{t("myBatches")}</h2>}
      {active.map((b) => (
        <div key={b.trainee_id} className="card train-card">
          <div className="row-between"><b>{b.course.name}</b><span className={`tag ${b.status === "completed" ? "ok" : b.status === "requested" ? "amber" : ""}`}>{status[b.status]}</span></div>
          <span className="small muted">{b.code} · {b.course.track_label} · {dt(b.start_date, lang)} – {dt(b.end_date, lang)} · {b.mode === "online" ? t("online") : `${b.venue ?? ""}${b.district_name ? `, ${b.district_name}` : ""}`}</span>
          {b.status !== "requested" && (<>
            <div className="small">{t("attendance")}: <b>{b.attended}/{b.total}</b> {t("sessionsT")} ({b.attendance_pct}%)</div>
            <div className="session-dots" aria-hidden="true">
              {b.sessions.map((s) => <span key={s.n} title={s.topic} className={s.present ? "ok" : s.done ? "held" : ""}>{s.n}</span>)}
            </div>
          </>)}
          {b.result && <div className="small">{t("result")}: <b>{t(b.result as "pass" | "reassess" | "fail")}</b></div>}
          {b.certificate_no && <button className="btn" onClick={() => act(() => openLink(`/training/me/certificate/${b.trainee_id}/link`))}>📜 {t("certificate")}</button>}
          {b.verify_url && <span className="small muted">{b.certificate_no} · <a href={b.verify_url} target="_blank" rel="noreferrer">{lang === "te" ? "ధృవీకరణ లింక్" : "Verification link"}</a></span>}
          {b.status === "requested" && <div><button className="btn ghost small" onClick={() => act(() => api("/training/me/withdraw", { body: { trainee_id: b.trainee_id } }))}>{t("cancelRequest")}</button></div>}
          {b.attended > 0 && !b.feedback_rating && <Feedback b={b} onDone={load} />}
          {b.feedback_rating && <span className="small muted">{t("thanksFeedback")} {"★".repeat(b.feedback_rating)}</span>}
        </div>
      ))}

      <h2 style={{ marginBottom: 0 }}>{t("openBatches")}</h2>
      {(me.open_batches ?? []).length === 0 && <div className="card small muted">{t("noOpenBatches")}</div>}
      {me.open_batches?.map((b) => (
        <div key={b.id} className="card train-card">
          <div className="row-between"><b>{b.course.name}</b>{b.recommended && <span className="tag ok">{t("recommendedForYou")}</span>}</div>
          <small className="muted">{b.code}</small>
          {b.course.description && <span className="small">{b.course.description}</span>}
          <span className="small muted">{b.course.track_label} · {dt(b.start_date, lang)} – {dt(b.end_date, lang)} · {b.mode === "online" ? t("online") : `${b.venue ?? ""}${b.district_name ? `, ${b.district_name}` : ""}`}</span>
          <span className="small">{b.seats_left} {t("seatsLeft")}{b.sponsor && <> · {t("sponsoredBy")} {b.sponsor}</>}</span>
          <div><button className="btn secondary" onClick={() => act(() => api("/training/me/request", { body: { batch_id: b.id } }))}>{t("requestSeat")}</button></div>
        </div>
      ))}

      <h2 style={{ marginBottom: 0 }}>{t("otherCerts")}</h2>
      <p className="small muted" style={{ margin: 0 }}>{t("otherCertsHint")}</p>
      {me.external?.map((x) => (
        <div key={x.id} className="card row-between small">
          <span><b>{x.title}</b>{x.number && ` · ${x.number}`}{x.note && <div className="muted">{x.note}</div>}{x.file_url && <> · <a href={apiUrl(x.file_url)} target="_blank" rel="noreferrer">PDF / photo</a></>}</span>
          <span className={`tag ${x.status === "verified" ? "ok" : x.status === "rejected" ? "alert" : "amber"}`}>{x.status === "verified" ? t("verifiedC") : x.status === "rejected" ? t("rejectedC") : t("pending")}</span>
        </div>
      ))}
      {upload ? <div className="card"><UploadCert onDone={() => { setUpload(false); load(); }} /></div>
        : <div><button className="btn secondary" onClick={() => setUpload(true)}>+ {t("upload")}</button></div>}
    </div>
  );
}

/** Opened from the trainer's QR code: #/checkin/<token>. */
export function Checkin({ token }: { token: string }) {
  const { lang } = useLang();
  const t = pt(lang);
  const [state, setState] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    api<{ course: string; session: string; n: number }>(`/training/me/checkin?lang=${lang}`, { body: { token } })
      .then((r) => setState({ ok: true, text: `${r.course} – ${r.n}. ${r.session}` }))
      .catch((e) => setState({ ok: false, text: (e as Error).message }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  return (
    <div className="stack" style={{ textAlign: "center", paddingTop: 24 }}>
      {!state && <div className="muted">{t("checkingIn")}</div>}
      {state && (<>
        <div className="verify-badge" style={{ background: state.ok ? "var(--ok)" : "var(--danger)" }}>{state.ok ? "✓" : "!"}</div>
        <h1 style={{ margin: 0 }}>{state.ok ? t("checkedIn") : "—"}</h1>
        <p className={state.ok ? "" : "error"}>{state.text}</p>
      </>)}
      <Link to="/training" className="btn secondary">{t("goTraining")}</Link>
    </div>
  );
}
