import { useState } from "react";
import RequestHelp from "./RequestHelp";
import { Link } from "react-router-dom";
import { api, downloadArtefact, type GuidanceResult } from "../api";
import { useLang, type StringKey } from "../i18n";

const STEP_KEYS: StringKey[] = ["stepUnderstanding", "stepIdentification", "stepInformation", "stepGuidance", "stepConnect"];

export function StepIndicator({ current }: { current: number }) {
  const { t } = useLang();
  return (
    <div className="steps" aria-label={`Step ${current} of 5`}>
      {STEP_KEYS.map((k, i) => (
        <div key={k} className={`s${i + 1} ${i < current ? "done" : ""}`}>{t(k)}</div>
      ))}
    </div>
  );
}

// Turn "[1]" citations into superscripts.
function AnswerText({ text }: { text: string }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <div className="answer">
      {parts.map((part, i) => (/^\[\d+\]$/.test(part) ? <sup key={i}>{part}</sup> : <span key={i}>{part}</span>))}
    </div>
  );
}

type Props = {
  result: GuidanceResult;
  onAsk?: (question: string) => void;
  sessionId?: number;
  messageId?: number;
  rating?: number | null;
  doneCodes: Set<string>;
  onToggleDone: (code: string, done: boolean) => void;
};

export default function GuidanceView({ result, onAsk, sessionId, messageId, rating, doneCodes, onToggleDone }: Props) {
  const { t } = useLang();
  const [rated, setRated] = useState<number | null>(rating ?? null);
  const [helpFor, setHelpFor] = useState<number | null>(null);
  const [making, setMaking] = useState<string | null>(null);
  const [docError, setDocError] = useState<string | null>(null);

  const makeDoc = async (kind: "roadmap" | "checklist") => {
    if (!sessionId) return;
    setMaking(kind);
    setDocError(null);
    try {
      const a = await api<{ id: number }>(`/artefacts/${kind}`, { body: { session_id: sessionId } });
      await downloadArtefact(a.id);
    } catch (e) {
      setDocError((e as Error).message);
    } finally {
      setMaking(null);
    }
  };
  const u = result.understanding;

  if (result.current_step === 1 && u.missing_profile_fields.length) {
    return (
      <div className="card stack">
        <StepIndicator current={1} />
        <p style={{ margin: 0 }}>{result.message}</p>
        <Link to="/profile" className="btn" style={{ textDecoration: "none", textAlign: "center" }}>{t("completeProfile")}</Link>
      </div>
    );
  }

  const idn = result.identification!;
  const info = result.information!;
  const steps = result.guidance!.steps;
  const connect = result.connect!;

  const rate = async (v: 1 | -1) => {
    if (!messageId) return;
    setRated(v);
    await api(`/guidance/messages/${messageId}/rate`, { body: { rating: v } }).catch(() => setRated(null));
  };

  return (
    <div className="card stack gv">
      <StepIndicator current={result.current_step} />

      {/* Left column on desktop: what applies to me and what to do */}
      <div className="gv-col gv-left">
      {/* 1. Understanding */}
      <div className="section s1">
        <div className="section-title">1 · {t("stepUnderstanding")}</div>
        <div style={{ fontWeight: 600 }}>
          {u.intent_title ?? "General question"} {u.module_label && <span className="tag">{u.module_label}</span>}
        </div>
        <div className="summary-chips" style={{ marginTop: 8 }}>
          {u.profile_summary.map((s) => <span key={s} className="tag" style={{ background: "#eef2f9", color: "#3d5a8f" }}>{s}</span>)}
        </div>
      </div>

      {/* 2. Identification */}
      {(idn.have.length > 0 || idn.missing.length > 0) && (
        <div className="section s2">
          <div className="section-title">2 · {t("stepIdentification")}</div>
          <div className="gapgrid">
            <div className="gapcol have">
              <h3>✓ {t("youHave")}</h3>
              {idn.have.length ? <ul>{idn.have.map((h) => <li key={h.code}>{h.title}</li>)}</ul> : <span className="small muted">—</span>}
            </div>
            <div className="gapcol missing">
              <h3>! {t("missing")}</h3>
              {idn.missing.length ? <ul>{idn.missing.map((m) => <li key={m.code}>{m.title}</li>)}</ul> : <span className="small">{t("allDone")}</span>}
            </div>
          </div>
        </div>
      )}

      {/* 4. Guidance */}
      {steps.length > 0 && (
        <div className="section s4">
          <div className="section-title">4 · {t("nextSteps")}</div>
          {steps.map((s) => {
            const done = doneCodes.has(s.code);
            return (
              <div key={s.code} className={`stepitem ${done ? "done" : ""}`}>
                <div className="stepnum">{done ? "✓" : s.n}</div>
                <div style={{ flex: 1 }}>
                  <div className="steptitle">{s.title}</div>
                  {s.why && <div className="stepmeta">{s.why}</div>}
                  <div className="stepmeta">
                    {s.documents && <div><b>{t("documents")}:</b> {s.documents}</div>}
                    {s.time && <span><b>{t("time")}:</b> {s.time}</span>}
                    {s.time && s.cost && " · "}
                    {s.cost && <span><b>{t("cost")}:</b> {s.cost}</span>}
                    {s.link && <div><a href={s.link} target="_blank" rel="noreferrer">{t("officialSite")} ↗</a></div>}
                  </div>
                </div>
                {sessionId && (
                  <label className="stepdone small">
                    <input type="checkbox" checked={done} onChange={(e) => onToggleDone(s.code, e.target.checked)} aria-label={`Mark ${s.title} done`} />
                  </label>
                )}
              </div>
            );
          })}
          {sessionId && (
            <div className="doc-actions">
              <button className="btn secondary small" disabled={!!making} onClick={() => makeDoc("roadmap")}>
                {making === "roadmap" ? t("makingDoc") : `⤓ ${t("downloadRoadmap")}`}</button>
              {steps.some((s) => s.documents) && (
                <button className="btn secondary small" disabled={!!making} onClick={() => makeDoc("checklist")}>
                  {making === "checklist" ? t("makingDoc") : `⤓ ${t("downloadChecklist")}`}</button>
              )}
            </div>
          )}
          {docError && <div className="error small">{docError}</div>}
        </div>
      )}

      {/* Tools linked to the topic */}
      {u.module === "microfin" && <Link className="tool-link microfin" to="/tools/cashflow">{t("openCashflowTool")} →</Link>}
      {(u.intent_code === "hire_staff" || u.intent_code === "labour_compliance") && <Link className="tool-link skillspro" to="/tools/jd">{t("openJdTool")} →</Link>}

      </div>

      {/* Right column on desktop: verified information and experts */}
      <div className="gv-col gv-right">
      {/* 3. Information */}
      <div className="section s3">
        <div className="section-title">3 · {t("stepInformation")}</div>
        <AnswerText text={info.answer} />
        {info.method !== "ai" && <div className="small muted" style={{ marginTop: 6 }}>{t("demoNote")}</div>}
        {info.sources.length > 0 && (
          <ul className="sources">
            {info.sources.map((s) => (
              <li key={s.n}>
                <b>[{s.n}]</b> {s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> : s.title}
                {s.verified_by?.startsWith("Sample") ? (
                  <span className="tag amber" style={{ marginLeft: 6 }}>{t("sample")}</span>
                ) : s.verified_on ? (
                  <span className="muted"> · {t("verified")} {s.verified_on}</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 5. Connect */}
      {connect.experts.length > 0 && (
        <div className="section s5">
          <div className="section-title">5 · {t("talkExpert")}</div>
          {connect.suggested && <div className="small muted" style={{ marginBottom: 6 }}>{connect.reason}</div>}
          {connect.experts.map((e) => (
            <div key={e.id}>
              <div className="expert">
                <div className="avatar">{e.name.replace(/^Sample /, "").slice(0, 1)}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600 }}>{e.name}</div>
                  <div className="small muted">
                    {e.organisation} · {e.type.toUpperCase()} {e.rating ? `· ★ ${e.rating}` : ""}
                  </div>
                  <div className="small muted">{e.fee_note} · {t("replyIn")} {e.response_hours} {t("hours")}</div>
                </div>
                <button className="btn secondary" style={{ minHeight: 38, padding: "8px 12px" }} onClick={() => setHelpFor(e.id)}>
                  {t("requestHelp")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      </div>

      {onAsk && u.related && u.related.length > 0 && (
        <div className="gv-rel">
          <div className="small muted" style={{ marginBottom: 6 }}>{t("alsoAsk")}</div>
          <div className="chips">
            {u.related.map((r) => <button key={r.code} className="chip" onClick={() => onAsk(r.question)}>{r.title}</button>)}
          </div>
        </div>
      )}

      {messageId && (
        <div className="rating">
          {rated ? t("thanks") : (<>
            {t("helpful")}
            <button onClick={() => rate(1)} aria-label="Helpful">👍</button>
            <button onClick={() => rate(-1)} aria-label="Not helpful">👎</button>
          </>)}
        </div>
      )}
      {helpFor !== null && <RequestHelp expertId={helpFor} sessionId={sessionId} onClose={() => setHelpFor(null)} />}
    </div>
  );
}
