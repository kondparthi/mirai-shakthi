// Form 1.3 – Enterprise readiness: the questions (from the admin-editable formula) and the result card.
import { useEffect, useState } from "react";
import { api, type Assessment, type ReadinessQuestion } from "../api";
import type { Lang } from "../i18n";
import { pt } from "./programmeText";

export function bandOf(score: number) {
  return score >= 70 ? "ok" : score >= 45 ? "amber" : "alert";
}

export function ScoreRing({ score, size = 76 }: { score: number; size?: number }) {
  const r = 30;
  const c = 2 * Math.PI * r;
  return (
    <svg className={`score-ring ${bandOf(score)}`} width={size} height={size} viewBox="0 0 76 76" role="img" aria-label={`${score} / 100`}>
      <circle cx="38" cy="38" r={r} className="track" />
      <circle cx="38" cy="38" r={r} className="bar" strokeDasharray={`${(c * score) / 100} ${c}`} transform="rotate(-90 38 38)" />
      <text x="38" y="43" textAnchor="middle">{score}</text>
    </svg>
  );
}

export function ReadinessResult({ a, lang, showBreakdown = false }: { a: Assessment; lang: Lang; showBreakdown?: boolean }) {
  const t = pt(lang);
  return (
    <div className="stack readiness-result">
      <div className="row-gap" style={{ alignItems: "center" }}>
        <ScoreRing score={a.score} />
        <div>
          {a.band && <div className={`tag ${bandOf(a.score)}`}>{a.band}</div>}
          {a.at && <div className="small muted">{t("lastChecked")}: {new Date(a.at).toLocaleDateString()}</div>}
        </div>
      </div>
      {a.strengths.length > 0 && (
        <div><b className="small">{t("strengths")}</b>
          <ul className="tick-list">{a.strengths.map((s) => <li key={s}>{s}</li>)}</ul></div>
      )}
      {a.gaps.length > 0 && (
        <div><b className="small">{t("gaps")}</b>
          <ul className="gap-list">{a.gaps.map((g) => <li key={g.code}><b>{g.label}</b>{g.advice && <div className="small muted">{g.advice}</div>}</li>)}</ul></div>
      )}
      <div><b className="small">{t("recommended")}</b>
        <div className="chips" style={{ marginTop: 6 }}>{a.recommended.map((r) => <span key={r} className="tag">{r}</span>)}</div></div>
      {a.remarks && <p className="small" style={{ margin: 0 }}>“{a.remarks}”</p>}
      {showBreakdown && (
        <table className="table compact">
          <tbody>
            {a.breakdown.map((b) => (
              <tr key={b.code}><td>{b.label}<div className="small muted">{b.answer ?? "—"}</div></td><td className="num">{b.points} / {b.max}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function ReadinessForm({ lang, formPath, submitPath, staff = false, onDone }: {
  lang: Lang; formPath: string; submitPath: string; staff?: boolean; onDone: (a: Assessment) => void;
}) {
  const t = pt(lang);
  const [qs, setQs] = useState<ReadinessQuestion[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [remarks, setRemarks] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<{ questions: ReadinessQuestion[] }>(formPath).then((r) => setQs(r.questions)).catch((e) => setError(e.message));
  }, [formPath]);
  if (!qs) return error ? <div className="error">{error}</div> : <div className="muted">…</div>;
  const answered = qs.filter((q) => (answers[q.code] ?? "").trim()).length;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      onDone(await api<Assessment>(submitPath, { body: { answers, remarks: remarks || null } }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack readiness-form">
      {qs.map((q, i) => (
        <div key={q.code} className="field">
          <span>{i + 1}. {q.label}</span>
          {q.kind === "text" ? (
            <>
              <textarea className="input" rows={2} value={answers[q.code] ?? ""} onChange={(e) => setAnswers({ ...answers, [q.code]: e.target.value })} />
              <small className="muted">{t("motivationHint")}</small>
            </>
          ) : (
            <div className="chips">
              {q.options.map(([code, label]) => (
                <button type="button" key={code} className={`chip ${answers[q.code] === code ? "on" : ""}`} aria-pressed={answers[q.code] === code}
                  onClick={() => setAnswers({ ...answers, [q.code]: code })}>{label}</button>
              ))}
            </div>
          )}
        </div>
      ))}
      {staff && (
        <label className="field"><span>{t("remarks")}</span>
          <textarea className="input" rows={2} value={remarks} onChange={(e) => setRemarks(e.target.value)} /></label>
      )}
      {error && <div className="error">{error}</div>}
      <button className="btn" disabled={busy || answered < qs.length} onClick={submit}>
        {t("seeScore")} {answered < qs.length && <small>({answered}/{qs.length})</small>}
      </button>
    </div>
  );
}
