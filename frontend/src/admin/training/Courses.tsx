// Curriculum master: courses in tracks A–F with sessions, outcomes and assessment rules.
import { useCallback, useEffect, useState } from "react";
import { api, type CourseFull, type Track } from "../../api";
import { useMaster } from "../../components/masters";
import { Field, Modal } from "../ui";

const TRACKS: [Track, string][] = [["awareness", "Awareness EDP"], ["core", "Core EDP"], ["skill", "Skill-based"], ["ojt", "On-the-job"], ["exposure", "Exposure visit"], ["refresher", "Refresher"]];

function CourseForm({ c, onSaved }: { c?: CourseFull; onSaved: () => void }) {
  const [f, setF] = useState({
    code: c?.code ?? "", track: c?.track ?? ("core" as Track), name_en: c?.name_en ?? "", name_te: c?.name_te ?? "", description_en: c?.description_en ?? "",
    description_te: c?.description_te ?? "", sectors: c?.sectors ?? [], duration_days: c?.duration_days ?? 1, pass_mark: c?.pass_mark ?? 60,
    min_attendance: c?.min_attendance ?? 75, business_plan_score: c?.business_plan_score ?? false, external_certificate: c?.external_certificate ?? "",
    active: c?.active ?? true, outcomes: (c?.outcomes ?? []).join("\n"), practical_checklist: (c?.practical_checklist ?? []).join("\n"),
  });
  const [sessions, setSessions] = useState(c?.sessions.map((s) => ({ ...s, topic_te: s.topic_te ?? "", hours: s.hours ?? "" })) ?? [{ topic_en: "", topic_te: "", hours: 3 as number | string }]);
  const [error, setError] = useState<string | null>(null);
  const sectors = useMaster("sector");
  const save = async () => {
    setError(null);
    try {
      await api(c ? `/training/courses/${c.id}` : "/training/courses", {
        method: c ? "PUT" : "POST",
        body: { ...f, name_te: f.name_te || null, description_en: f.description_en || null, description_te: f.description_te || null,
          external_certificate: f.external_certificate || null, outcomes: f.outcomes.split("\n").map((x) => x.trim()).filter(Boolean),
          practical_checklist: f.practical_checklist.split("\n").map((x) => x.trim()).filter(Boolean),
          sessions: sessions.filter((s) => s.topic_en.trim()).map((s) => ({ topic_en: s.topic_en, topic_te: s.topic_te || null, hours: s.hours === "" ? null : Number(s.hours) })) },
      });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Code" hint="Lower-case letters, numbers and _ ; cannot change later"><input className="input" disabled={!!c} value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })} /></Field>
        <Field label="Track"><select className="input" value={f.track} onChange={(e) => setF({ ...f, track: e.target.value as Track })}>{TRACKS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Name (English)"><input className="input" value={f.name_en} onChange={(e) => setF({ ...f, name_en: e.target.value })} /></Field>
        <Field label="Name (Telugu)"><input className="input" lang="te" value={f.name_te} onChange={(e) => setF({ ...f, name_te: e.target.value })} /></Field>
        <Field label="Description (English)"><textarea className="input" rows={2} value={f.description_en} onChange={(e) => setF({ ...f, description_en: e.target.value })} /></Field>
        <Field label="Description (Telugu)"><textarea className="input" lang="te" rows={2} value={f.description_te} onChange={(e) => setF({ ...f, description_te: e.target.value })} /></Field>
        <Field label="Duration (days)"><input className="input" type="number" min={1} value={f.duration_days} onChange={(e) => setF({ ...f, duration_days: Number(e.target.value) })} /></Field>
        <Field label="Pass mark (quiz %)" hint="0 = no quiz"><input className="input" type="number" min={0} max={100} value={f.pass_mark} onChange={(e) => setF({ ...f, pass_mark: Number(e.target.value) })} /></Field>
        <Field label="Minimum attendance (%)"><input className="input" type="number" min={0} max={100} value={f.min_attendance} onChange={(e) => setF({ ...f, min_attendance: Number(e.target.value) })} /></Field>
        <Field label="External certificate needed" hint="e.g. DGCA Remote Pilot Certificate"><input className="input" value={f.external_certificate} onChange={(e) => setF({ ...f, external_certificate: e.target.value })} /></Field>
      </div>
      <Field label="Sectors (none = all)"><div className="chips small-chips">{sectors.map((s) => {
        const on = f.sectors.includes(s.code);
        return <button key={s.code} type="button" className={`chip ${on ? "on" : ""}`} onClick={() => setF({ ...f, sectors: on ? f.sectors.filter((x) => x !== s.code) : [...f.sectors, s.code] })}>{s.name_en}</button>;
      })}</div></Field>
      <h3 style={{ marginBottom: 0 }}>Sessions</h3>
      <div className="table-wrap"><table className="table compact"><thead><tr><th>#</th><th>Topic (English)</th><th>Topic (Telugu)</th><th>Hours</th><th /></tr></thead><tbody>
        {sessions.map((s, i) => (
          <tr key={i}><td>{i + 1}</td>
            <td><input className="input" aria-label="Topic" value={s.topic_en} onChange={(e) => setSessions(sessions.map((x, j) => (j === i ? { ...x, topic_en: e.target.value } : x)))} /></td>
            <td><input className="input" lang="te" aria-label="Telugu topic" value={s.topic_te} onChange={(e) => setSessions(sessions.map((x, j) => (j === i ? { ...x, topic_te: e.target.value } : x)))} /></td>
            <td><input className="input num-input" type="number" aria-label="Hours" value={s.hours} onChange={(e) => setSessions(sessions.map((x, j) => (j === i ? { ...x, hours: e.target.value } : x)))} /></td>
            <td><button className="btn ghost small danger" aria-label="Remove session" onClick={() => setSessions(sessions.filter((_, j) => j !== i))}>✕</button></td></tr>
        ))}</tbody></table></div>
      <div><button className="btn secondary small" onClick={() => setSessions([...sessions, { topic_en: "", topic_te: "", hours: 3 }])}>+ Add session</button></div>
      <div className="grid-2">
        <Field label="Learning outcomes (one per line)"><textarea className="input" rows={3} value={f.outcomes} onChange={(e) => setF({ ...f, outcomes: e.target.value })} /></Field>
        <Field label="Practical checklist (one item per line)" hint="Every item must be signed off to pass"><textarea className="input" rows={3} value={f.practical_checklist} onChange={(e) => setF({ ...f, practical_checklist: e.target.value })} /></Field>
      </div>
      <label className="check"><input type="checkbox" checked={f.business_plan_score} onChange={(e) => setF({ ...f, business_plan_score: e.target.checked })} /><span>Score a business-plan presentation (Core EDP)</span></label>
      <label className="check"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /><span>Active (can be used for new batches)</span></label>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" onClick={save}>Save course</button></div>
    </div>
  );
}

export default function Courses() {
  const [rows, setRows] = useState<CourseFull[] | null>(null);
  const [edit, setEdit] = useState<CourseFull | "new" | null>(null);
  const load = useCallback(() => api<CourseFull[]>("/training/courses?all=true").then(setRows).catch(() => setRows([])), []);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Courses</h1><p className="muted small" style={{ margin: 0 }}>Curriculum master for every track: sessions, learning outcomes and how trainees pass.</p></div>
        <button className="btn" onClick={() => setEdit("new")}>+ New course</button>
      </div>
      {TRACKS.map(([k, label]) => {
        const list = rows?.filter((c) => c.track === k) ?? [];
        if (!list.length) return null;
        return (
          <div key={k} className="stack" style={{ gap: 8 }}>
            <h2 style={{ margin: "8px 0 0" }}>{label}</h2>
            <div className="batch-grid">
              {list.map((c) => (
                <button key={c.id} className={`card batch-card ${c.active ? "" : "dim"}`} onClick={() => setEdit(c)}>
                  <b>{c.name_en}</b><span className="small muted" lang="te">{c.name_te}</span>
                  <span className="small">{c.duration_days} day(s) · {c.sessions.length} sessions · pass {c.pass_mark}% · attendance {c.min_attendance}%</span>
                  {c.practical_checklist.length > 0 && <span className="small muted">{c.practical_checklist.length} practical checks</span>}
                  {c.external_certificate && <span className="tag amber">{c.external_certificate}</span>}
                  {!c.active && <span className="tag grey">inactive</span>}
                </button>
              ))}
            </div>
          </div>
        );
      })}
      {edit && <Modal title={edit === "new" ? "New course" : edit.name_en} wide onClose={() => setEdit(null)}><CourseForm c={edit === "new" ? undefined : edit} onSaved={() => { setEdit(null); load(); }} /></Modal>}
    </div>
  );
}
