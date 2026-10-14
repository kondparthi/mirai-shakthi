// Training batches (Form 4.1). Trainers see only their own batches ("My batches").
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, type BatchRow, type TrainingMeta } from "../../api";
import { useAuth } from "../../auth";
import { useMaster } from "../../components/masters";
import { Field, Modal } from "../ui";

export const STATUS_TAG: Record<string, string> = { planned: "grey", open: "amber", ongoing: "", completed: "ok", cancelled: "grey" };
export const MODES: Record<string, string> = { classroom: "Classroom", online: "Online", blended: "Blended", ojt: "On-the-job" };
export const fmtDate = (d: string | null) => (d ? new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—");
const PLAN = ["admin", "programme_manager", "coordinator"];

export function useTrainingMeta() {
  const [meta, setMeta] = useState<TrainingMeta | null>(null);
  useEffect(() => {
    api<TrainingMeta>("/training/meta").then(setMeta).catch(() => {});
  }, []);
  return meta;
}

export function BatchForm({ batch, meta, onSaved }: { batch?: BatchRow; meta: TrainingMeta; onSaved: (b: { id: number }) => void }) {
  const { user } = useAuth();
  const [f, setF] = useState({
    course_id: batch?.course.id ?? meta.courses[0]?.id ?? 0, partner_id: batch?.partner_id ?? null as number | null,
    trainer_ids: batch?.trainer_ids ?? [] as number[], mentor_ids: batch?.mentor_ids ?? [] as number[], mode: batch?.mode ?? "classroom",
    start_date: batch?.start_date ?? "", end_date: batch?.end_date ?? "", venue: batch?.venue ?? "", host_unit: batch?.host_unit ?? "",
    district: batch?.district ?? (user?.scope?.districts?.length === 1 ? user.scope.districts[0] : ""), seats: batch?.seats ?? 30,
    sponsor_type: batch?.sponsor_type ?? "self", sponsor_name: batch?.sponsor_name ?? "", pass_mark: batch?.pass_mark ?? (null as number | null),
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const districts = useMaster("district");
  const course = meta.courses.find((c) => c.id === f.course_id);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF({ ...f, [k]: v });
  const toggle = (k: "trainer_ids" | "mentor_ids", id: number) => set(k, f[k].includes(id) ? f[k].filter((x) => x !== id) : [...f[k], id]);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = { ...f, venue: f.venue || null, host_unit: f.host_unit || null, district: f.district || null, sponsor_name: f.sponsor_name || null };
      onSaved(await api<{ id: number }>(batch ? `/training/batches/${batch.id}` : "/training/batches", { method: batch ? "PUT" : "POST", body }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Course" hint={course ? `${course.track_label} · ${course.duration_days} day(s) · ${course.sessions_count} sessions` : undefined}>
          <select className="input" value={f.course_id} onChange={(e) => set("course_id", Number(e.target.value))}>
            {meta.tracks.map((t) => (
              <optgroup key={t.code} label={t.label}>
                {meta.courses.filter((c) => c.track === t.code).map((c) => <option key={c.id} value={c.id}>{c.name_en}</option>)}
              </optgroup>
            ))}
          </select></Field>
        <Field label="Training partner"><select className="input" value={f.partner_id ?? ""} onChange={(e) => set("partner_id", e.target.value ? Number(e.target.value) : null)}>
          <option value="">—</option>{meta.partners.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
        <Field label="Mode"><select className="input" value={f.mode} onChange={(e) => set("mode", e.target.value)}>
          {Object.entries(MODES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Seats"><input className="input" type="number" min={1} value={f.seats} onChange={(e) => set("seats", Number(e.target.value))} /></Field>
        <Field label="Start date"><input className="input" type="date" value={f.start_date} onChange={(e) => set("start_date", e.target.value)} /></Field>
        <Field label="End date"><input className="input" type="date" value={f.end_date} min={f.start_date} onChange={(e) => set("end_date", e.target.value)} /></Field>
        <Field label="District"><select className="input" value={f.district} onChange={(e) => set("district", e.target.value)}>
          <option value="">{f.mode === "online" ? "Online – any district" : "—"}</option>
          {districts.filter((d) => !user?.scope?.districts?.length || ["admin", "programme_manager"].includes(user.role) || user.scope.districts.includes(d.code))
            .map((d) => <option key={d.code} value={d.code}>{d.name_en}</option>)}</select></Field>
        {f.mode === "ojt"
          ? <Field label="Host unit"><input className="input" value={f.host_unit} onChange={(e) => set("host_unit", e.target.value)} /></Field>
          : <Field label="Venue"><input className="input" value={f.venue} placeholder={f.mode === "online" ? "Link or platform (optional)" : ""} onChange={(e) => set("venue", e.target.value)} /></Field>}
        <Field label="Sponsor"><select className="input" value={f.sponsor_type} onChange={(e) => set("sponsor_type", e.target.value)}>
          <option value="self">Self-funded</option><option value="csr">CSR</option><option value="govt">Government scheme</option></select></Field>
        {f.sponsor_type !== "self" && <Field label="Sponsor name"><input className="input" value={f.sponsor_name} onChange={(e) => set("sponsor_name", e.target.value)} /></Field>}
        <Field label="Pass mark (%)" hint="Leave blank to use the course's pass mark">
          <input className="input" type="number" min={0} max={100} value={f.pass_mark ?? ""} onChange={(e) => set("pass_mark", e.target.value === "" ? null : Number(e.target.value))} /></Field>
      </div>
      <Field label="Trainers" hint={meta.trainers.length ? undefined : "Create staff logins with the Trainer role first (Settings → Staff & access)"}>
        <div className="chips small-chips">{meta.trainers.map((t) => (
          <button type="button" key={t.id} className={`chip ${f.trainer_ids.includes(t.id) ? "on" : ""}`} aria-pressed={f.trainer_ids.includes(t.id)} onClick={() => toggle("trainer_ids", t.id)}>{t.name}</button>
        ))}</div></Field>
      <Field label="Mentors attached (shared among trainees)">
        <div className="chips small-chips">{meta.mentors.map((t) => (
          <button type="button" key={t.id} className={`chip ${f.mentor_ids.includes(t.id) ? "on" : ""}`} aria-pressed={f.mentor_ids.includes(t.id)} onClick={() => toggle("mentor_ids", t.id)}>{t.name}</button>
        ))}{!meta.mentors.length && <span className="small muted">No mentor logins yet.</span>}</div></Field>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" disabled={busy || !f.course_id} onClick={save}>{batch ? "Save batch" : "Create batch"}</button></div>
    </div>
  );
}

export default function Batches() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [sp, setSp] = useSearchParams();
  const meta = useTrainingMeta();
  const [rows, setRows] = useState<BatchRow[] | null>(null);
  const [status, setStatus] = useState(sp.get("status") ?? "");
  const [track, setTrack] = useState("");
  const trainer = user?.role === "trainer";
  const load = useCallback(() => {
    const p = new URLSearchParams();
    if (status) p.set("status", status);
    if (track) p.set("track", track);
    api<BatchRow[]>(`/training/batches?${p}`).then(setRows).catch(() => setRows([]));
  }, [status, track]);
  useEffect(load, [load]);

  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>{trainer ? "My batches" : "Training batches"}</h1>
          <p className="muted small" style={{ margin: 0 }}>EDP and skill-based training (Form 4.1). Open a batch to add trainees, take attendance and enter results.</p></div>
        {PLAN.includes(user?.role ?? "") && <button className="btn" onClick={() => setSp({ new: "1" })}>+ New batch</button>}
      </div>
      <div className="filters">
        <select className="input" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
          <option value="">All statuses</option>{Object.keys(STATUS_TAG).map((s) => <option key={s} value={s}>{s}</option>)}</select>
        <select className="input" value={track} onChange={(e) => setTrack(e.target.value)} aria-label="Track">
          <option value="">All tracks</option>{meta?.tracks.map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}</select>
      </div>
      <div className="batch-grid">
        {rows?.map((b) => (
          <button key={b.id} className="card batch-card" onClick={() => navigate(`/admin/training/batches/${b.id}`)}>
            <div className="row-between"><span className={`tag ${STATUS_TAG[b.status]}`}>{b.status}</span><small className="muted">{b.code}</small></div>
            <b>{b.course.name_en}</b>
            <span className="small muted">{b.course.track_label} · {MODES[b.mode]}</span>
            <span className="small">{fmtDate(b.start_date)} – {fmtDate(b.end_date)}</span>
            <span className="small muted">{b.venue || b.host_unit || "Online"}{b.district_name ? `, ${b.district_name}` : ""}</span>
            <div className="seat-bar" aria-label={`${b.filled} of ${b.seats} seats`}><span style={{ width: `${Math.min(100, (100 * b.filled) / b.seats)}%` }} /></div>
            <div className="row-between small"><span>{b.filled}/{b.seats} trainees{b.requested ? ` · ${b.requested} requests` : ""}</span>
              <span>{b.sessions_done}/{b.sessions_total} sessions</span></div>
            {b.sponsor_type !== "self" && <span className="tag grey">{b.sponsor_name}</span>}
          </button>
        ))}
      </div>
      {rows && rows.length === 0 && <div className="card muted">{trainer ? "No batches assigned to you yet." : "No batches yet. Create the first one."}</div>}
      {sp.get("new") && meta && (
        <Modal title="New training batch" wide onClose={() => setSp({})}>
          <BatchForm meta={meta} onSaved={(b) => navigate(`/admin/training/batches/${b.id}`)} />
        </Modal>
      )}
    </div>
  );
}
