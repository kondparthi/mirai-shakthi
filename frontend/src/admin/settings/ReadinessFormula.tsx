// Form 1.3 – the readiness score formula. Plain weighted points that MIRAI can see and change; no AI is involved.
import { useEffect, useState } from "react";
import { api } from "../../api";

type Q = { label: string; label_te?: string; kind?: "text" | "investment"; max: number; points_if_given?: number;
  options?: Record<string, [string, string, number]>; bands?: [number, number][]; gap?: string; gap_te?: string; training?: string | null };
type Formula = { version: number; questions: Record<string, Q>; bands: [number, string, string][] };
const ORDER = ["motivation", "experience", "time", "family_support", "work_space", "digital", "credit_history", "risk", "investment"];

export default function ReadinessFormula() {
  const [f, setF] = useState<Formula | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    api<Formula>("/admin/settings/readiness").then(setF).catch((e) => setMsg({ ok: false, text: e.message }));
  }, []);
  if (!f) return msg ? <div className="error">{msg.text}</div> : <div className="muted">Loading…</div>;
  const total = ORDER.reduce((s, k) => s + Number(f.questions[k]?.max ?? 0), 0);
  const setQ = (code: string, patch: Partial<Q>) => setF({ ...f, questions: { ...f.questions, [code]: { ...f.questions[code], ...patch } } });

  const save = async () => {
    setMsg(null);
    try {
      const r = await api<Formula>("/admin/settings/readiness", { method: "PUT", body: f });
      setF(r);
      setMsg({ ok: true, text: `Saved as version ${r.version}. New assessments use it; old scores are kept as they were.` });
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  };
  const reset = async () => {
    if (!window.confirm("Go back to the default formula?")) return;
    const r = await api<Formula>("/admin/settings/readiness/reset", { method: "POST" });
    setF(r);
    setMsg({ ok: true, text: `Default formula restored (version ${r.version}).` });
  };

  return (
    <div className="stack" style={{ maxWidth: 1000 }}>
      <div><h1>Readiness formula</h1>
        <p className="muted small" style={{ margin: 0 }}>Each question has a weight; each answer earns points up to that weight. Weights must add up to 100.
          Answers scoring 70%+ of the weight are shown as strengths, below 50% as gaps with the advice and training below. Version {f.version}.</p></div>
      <div className={`tag ${Math.round(total) === 100 ? "ok" : "alert"}`} style={{ alignSelf: "flex-start" }}>Total weight: {total} / 100</div>
      {ORDER.map((code) => {
        const q = f.questions[code];
        if (!q) return null;
        return (
          <div key={code} className="card stack formula-q">
            <div className="row-between">
              <b>{q.label}</b>
              <label className="row-gap small" style={{ alignItems: "center" }}>Weight
                <input className="input num-input" type="number" min={0} max={100} value={q.max} onChange={(e) => setQ(code, { max: Number(e.target.value) })} /></label>
            </div>
            {q.kind === "text" && <div className="small muted">Text answer: full points when they write at least a sentence (10+ characters).</div>}
            {q.kind === "investment" && (
              <div className="small">Own funds from the profile (group corpus for groups):
                {q.bands?.map(([limit, pts], i) => (
                  <span key={i} className="row-gap" style={{ display: "inline-flex", margin: "4px 8px" }}>≥ ₹
                    <input className="input num-input" type="number" value={limit} onChange={(e) => setQ(code, { bands: q.bands!.map((b, j) => (j === i ? [Number(e.target.value), b[1]] : b)) as [number, number][] })} />
                    →<input className="input num-input" type="number" value={pts} onChange={(e) => setQ(code, { bands: q.bands!.map((b, j) => (j === i ? [b[0], Number(e.target.value)] : b)) as [number, number][] })} /> pts
                  </span>
                ))}
              </div>
            )}
            {q.options && (
              <div className="chips">
                {Object.entries(q.options).map(([oc, [en, te, pts]]) => (
                  <span key={oc} className="opt-pill">{en} <small className="muted">{te}</small>
                    <input className="input num-input" type="number" min={0} max={q.max} value={pts} aria-label={`Points for ${en}`}
                      onChange={(e) => setQ(code, { options: { ...q.options!, [oc]: [en, te, Number(e.target.value)] } })} /></span>
                ))}
              </div>
            )}
            <div className="grid-2">
              <label className="field"><span>Gap advice (English)</span><input className="input" value={q.gap ?? ""} onChange={(e) => setQ(code, { gap: e.target.value })} /></label>
              <label className="field"><span>Gap advice (Telugu)</span><input className="input" lang="te" value={q.gap_te ?? ""} onChange={(e) => setQ(code, { gap_te: e.target.value })} /></label>
              <label className="field"><span>Training to recommend for this gap</span>
                <select className="input" value={q.training ?? ""} onChange={(e) => setQ(code, { training: e.target.value || null })}>
                  <option value="">None</option>{["Awareness EDP", "Core EDP", "Sector EDP", "Refresher"].map((t) => <option key={t}>{t}</option>)}</select></label>
            </div>
          </div>
        );
      })}
      <div className="card">
        <b>Score bands</b>
        {f.bands.map(([min, en, te], i) => (
          <div key={i} className="row-gap small" style={{ alignItems: "center", marginTop: 6 }}>
            from <input className="input num-input" type="number" value={min} disabled={min === 0}
              onChange={(e) => setF({ ...f, bands: f.bands.map((b, j) => (j === i ? [Number(e.target.value), b[1], b[2]] : b)) as Formula["bands"] })} />
            <b>{en}</b> <span lang="te">{te}</span>
          </div>
        ))}
      </div>
      {msg && <div className={msg.ok ? "notice ok-notice" : "error"}>{msg.text}</div>}
      <div className="row-gap"><button className="btn" disabled={Math.round(total) !== 100} onClick={save}>Save formula</button>
        <button className="btn ghost" onClick={reset}>Restore default</button></div>
    </div>
  );
}
