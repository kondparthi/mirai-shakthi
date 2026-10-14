// Training section on the entrepreneur page: recommended tracks, training-needs assessment (Form 4.3),
// batches and results, and uploaded external certificates.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUrl, openLink, type ExternalCert, type TraineeRow, type Track } from "../../api";
import { useAuth } from "../../auth";
import { Field, Modal } from "../ui";

type Needs = { id: number; enterprise_model: string; business_skills: Record<string, number>; technical_level: number; prior_training: { course: string; institute?: string; year?: number }[];
  preferred_mode: string; preferred_timing: string; constraints: string[]; recommended_tracks: Track[]; by: string | null; at: string | null };
type Summary = { recommended: { track: Track; label: string }[]; needs: Needs[]; external: ExternalCert[];
  trainings: (TraineeRow & { batch: { id: number; code: string; status: string; course: string; track: string; start_date: string }; followups: { point: number; status: string }[] })[] };
const AREAS: [string, string][] = [["costing", "Costing"], ["bookkeeping", "Bookkeeping"], ["marketing", "Marketing"], ["digital", "Digital"], ["banking", "Banking"]];
const TRACKS: [Track, string][] = [["awareness", "Awareness EDP"], ["core", "Core EDP"], ["skill", "Skill-based"], ["ojt", "On-the-job"], ["exposure", "Exposure visit"], ["refresher", "Refresher"]];
const NEEDS_ROLES = ["admin", "programme_manager", "coordinator", "mentor"];

function NeedsForm({ eid, last, onSaved }: { eid: number; last?: Needs; onSaved: () => void }) {
  const [f, setF] = useState({
    enterprise_model: last?.enterprise_model ?? "", business_skills: last?.business_skills ?? { costing: 3, bookkeeping: 3, marketing: 3, digital: 3, banking: 3 },
    technical_level: last?.technical_level ?? 2, prior_training: last?.prior_training ?? [], preferred_mode: last?.preferred_mode ?? "classroom",
    preferred_timing: last?.preferred_timing ?? "any", constraints: last?.constraints ?? [],
  });
  const [tracks, setTracks] = useState<Track[]>(last?.recommended_tracks ?? []);
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (touched || f.enterprise_model.length < 2) return;
    const t = setTimeout(() => api<{ tracks: Track[] }>(`/training/needs/suggest?eid=${eid}`, { body: f }).then((r) => setTracks(r.tracks)).catch(() => {}), 300);
    return () => clearTimeout(t);
  }, [f, eid, touched]);
  const save = async () => {
    setError(null);
    try {
      await api(`/training/entrepreneurs/${eid}/needs`, { body: { ...f, recommended_tracks: tracks } });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const chip = (on: boolean, label: string, onClick: () => void) => <button type="button" key={label} className={`chip ${on ? "on" : ""}`} aria-pressed={on} onClick={onClick}>{label}</button>;
  return (
    <div className="stack">
      <Field label="Selected or likely enterprise model"><input className="input" placeholder="e.g. Mobile millet café" value={f.enterprise_model} onChange={(e) => setF({ ...f, enterprise_model: e.target.value })} /></Field>
      <Field label="Business skills (1 = none, 5 = strong)">
        <div className="stack" style={{ gap: 6 }}>{AREAS.map(([k, l]) => (
          <div key={k} className="row-between small"><span>{l}</span>
            <span className="chips small-chips">{[1, 2, 3, 4, 5].map((n) => chip(f.business_skills[k] === n, String(n), () => setF({ ...f, business_skills: { ...f.business_skills, [k]: n } })))}</span></div>
        ))}</div></Field>
      <Field label="Technical skill for this model (1–5)"><div className="chips small-chips">{[1, 2, 3, 4, 5].map((n) => chip(f.technical_level === n, String(n), () => setF({ ...f, technical_level: n })))}</div></Field>
      <Field label="Earlier training / certificates">
        <div className="stack" style={{ gap: 6 }}>
          {f.prior_training.map((p, i) => (
            <div key={i} className="row-gap">
              <input className="input" style={{ flex: 2 }} placeholder="Course" value={p.course} onChange={(e) => setF({ ...f, prior_training: f.prior_training.map((x, j) => (j === i ? { ...x, course: e.target.value } : x)) })} />
              <input className="input" style={{ flex: 2 }} placeholder="Institute" value={p.institute ?? ""} onChange={(e) => setF({ ...f, prior_training: f.prior_training.map((x, j) => (j === i ? { ...x, institute: e.target.value } : x)) })} />
              <input className="input num-input" placeholder="Year" type="number" value={p.year ?? ""} onChange={(e) => setF({ ...f, prior_training: f.prior_training.map((x, j) => (j === i ? { ...x, year: e.target.value ? Number(e.target.value) : undefined } : x)) })} />
              <button className="btn ghost small danger" aria-label="Remove" onClick={() => setF({ ...f, prior_training: f.prior_training.filter((_, j) => j !== i) })}>✕</button>
            </div>
          ))}
          <div><button className="btn secondary small" onClick={() => setF({ ...f, prior_training: [...f.prior_training, { course: "" }] })}>+ Add</button></div>
        </div></Field>
      <div className="grid-2">
        <Field label="Preferred mode"><div className="chips small-chips">{[["classroom", "Classroom"], ["online", "Online"], ["blended", "Blended"]].map(([k, l]) => chip(f.preferred_mode === k, l, () => setF({ ...f, preferred_mode: k })))}</div></Field>
        <Field label="Timing"><div className="chips small-chips">{[["weekdays", "Weekdays"], ["weekends", "Weekends"], ["any", "Any"]].map(([k, l]) => chip(f.preferred_timing === k, l, () => setF({ ...f, preferred_timing: k })))}</div></Field>
      </div>
      <Field label="Constraints"><div className="chips small-chips">{[["travel", "Travel"], ["childcare", "Childcare"], ["phone", "Phone access"], ["language", "Language"]].map(([k, l]) =>
        chip(f.constraints.includes(k), l, () => setF({ ...f, constraints: f.constraints.includes(k) ? f.constraints.filter((x) => x !== k) : [...f.constraints, k] })))}</div></Field>
      <Field label="Recommended tracks" hint={touched ? "Edited by you" : "Suggested from the ratings – tap to change"}>
        <div className="chips small-chips">{TRACKS.map(([k, l]) => chip(tracks.includes(k), l, () => { setTouched(true); setTracks(tracks.includes(k) ? tracks.filter((x) => x !== k) : [...tracks, k]); }))}</div></Field>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" disabled={f.enterprise_model.length < 2 || f.prior_training.some((p) => p.course.trim().length < 2)} onClick={save}>Save needs assessment</button></div>
    </div>
  );
}

export default function EntrepreneurTraining({ eid }: { eid: number }) {
  const { user } = useAuth();
  const [s, setS] = useState<Summary | null>(null);
  const [form, setForm] = useState(false);
  const load = useCallback(() => api<Summary>(`/training/entrepreneurs/${eid}`).then(setS).catch(() => {}), [eid]);
  useEffect(() => {
    load();
  }, [load]);
  if (!s) return null;
  const last = s.needs[0];
  return (
    <div className="card stack">
      <div className="row-between"><h2 style={{ margin: 0 }}>Training</h2>
        {NEEDS_ROLES.includes(user?.role ?? "") && <button className="btn secondary small" onClick={() => setForm(true)}>{last ? "Update needs assessment" : "+ Needs assessment"}</button>}</div>
      <div className="small">Recommended: <span className="chips small-chips" style={{ display: "inline-flex" }}>{s.recommended.map((r) => <span key={r.track} className="tag">{r.label}</span>)}</span>
        <span className="muted"> {last ? `· from needs assessment (${last.enterprise_model})` : "· from the readiness check"}</span></div>
      {s.trainings.length === 0 && <p className="small muted" style={{ margin: 0 }}>Not in any batch yet.</p>}
      {s.trainings.map((t) => (
        <div key={t.id} className="row-between small" style={{ borderTop: "1px solid var(--line)", paddingTop: 8 }}>
          <span><Link to={`/admin/training/batches/${t.batch.id}`}><b>{t.batch.course}</b></Link> · {t.batch.code}
            <div className="muted">{t.status} · attendance {t.attendance_pct}%{t.result ? ` · ${t.result}` : ""}{t.followups.length ? ` · follow-ups: ${t.followups.map((f) => `${f.point}d ${f.status.replace("_", " ")}`).join(", ")}` : ""}</div></span>
          {t.certificate_no && <button className="btn ghost small" onClick={() => openLink(`/training/trainees/${t.id}/certificate/link`)}>{t.certificate_no}</button>}
        </div>
      ))}
      {s.external.length > 0 && (<>
        <b className="small">Uploaded certificates</b>
        {s.external.map((x) => (
          <div key={x.id} className="row-between small"><span>{x.title}{x.number ? ` · ${x.number}` : ""}</span>
            <span>{x.file_url && <a href={apiUrl(x.file_url)} target="_blank" rel="noreferrer">file</a>} <span className={`tag ${x.status === "verified" ? "ok" : x.status === "rejected" ? "alert" : "amber"}`}>{x.status}</span></span></div>
        ))}
      </>)}
      {form && <Modal title="Training needs assessment (Form 4.3)" wide onClose={() => setForm(false)}><NeedsForm eid={eid} last={last} onSaved={() => { setForm(false); load(); }} /></Modal>}
    </div>
  );
}
