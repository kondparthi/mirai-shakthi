// One training batch: trainees and nominations, sessions with attendance (trainer list or QR check-in),
// results (Form 4.2) and certificates. Works on a trainer's phone as well as a desktop.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, apiUpload, apiUrl, openLink, type BatchDetail as BD, type SessionRow, type TraineeRow } from "../../api";
import { Modal } from "../ui";
import { Avatar } from "../programme/Entrepreneurs";
import { BatchForm, fmtDate, MODES, STATUS_TAG, useTrainingMeta } from "./Batches";

type Cand = { id: number; full_name: string; mobile: string; village_name: string | null; district_name: string | null; stage: number; recommended: boolean; sector_fit: boolean };

function AddTrainees({ b, onDone }: { b: BD; onDone: (d: BD) => void }) {
  const [q, setQ] = useState("");
  const [all, setAll] = useState(false);
  const [rows, setRows] = useState<Cand[] | null>(null);
  const [pick, setPick] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const t = setTimeout(() => api<Cand[]>(`/training/batches/${b.id}/candidates?q=${encodeURIComponent(q)}&all_districts=${all}`).then(setRows).catch(() => setRows([])), 250);
    return () => clearTimeout(t);
  }, [b.id, q, all]);
  const left = b.seats - b.filled;
  const add = async () => {
    setError(null);
    try {
      onDone(await api<BD>(`/training/batches/${b.id}/trainees`, { body: { entrepreneur_ids: pick } }));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div className="filters">
        <input className="input" placeholder="Search name or mobile" value={q} onChange={(e) => setQ(e.target.value)} />
        {b.district && <label className="check"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /><span>Show other districts</span></label>}
      </div>
      <p className="small muted" style={{ margin: 0 }}>{left} seat(s) left. “Recommended” = their readiness or needs assessment points to {b.course.track_label}.</p>
      <div className="table-wrap card">
        <table className="table compact">
          <tbody>
            {rows?.map((c) => (
              <tr key={c.id} className="clickable" onClick={() => setPick(pick.includes(c.id) ? pick.filter((x) => x !== c.id) : [...pick, c.id])}>
                <td style={{ width: 32 }}><input type="checkbox" readOnly checked={pick.includes(c.id)} aria-label={`Select ${c.full_name}`} /></td>
                <td><b>{c.full_name}</b><div className="small muted">{c.mobile} · {c.village_name}, {c.district_name}</div></td>
                <td>{c.recommended && <span className="tag ok">recommended</span>} {c.sector_fit && b.course.sectors.length > 0 && <span className="tag">sector fit</span>}</td>
              </tr>
            ))}
            {rows && rows.length === 0 && <tr><td className="muted">No one found. Only enrolled people who gave consent can be added.</td></tr>}
          </tbody>
        </table>
      </div>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" disabled={!pick.length || pick.length > left} onClick={add}>Add {pick.length || ""} to batch</button></div>
    </div>
  );
}

function AttendanceSheet({ b, s, onDone }: { b: BD; s: SessionRow; onDone: () => void }) {
  const active = b.trainees.filter((t) => ["confirmed", "completed"].includes(t.status));
  const [present, setPresent] = useState<number[]>(s.present_ids);
  const [checkedIn, setCheckedIn] = useState<number[]>(s.present_ids);
  const [error, setError] = useState<string | null>(null);
  // Re-read the session so people who just checked in with the QR code are already ticked.
  useEffect(() => {
    api<BD>(`/training/batches/${b.id}`).then((d) => {
      const fresh = d.sessions.find((x) => x.id === s.id);
      if (fresh) {
        setCheckedIn(fresh.present_ids);
        setPresent((p) => Array.from(new Set([...p, ...fresh.present_ids])));
      }
    }).catch(() => {});
  }, [b.id, s.id]);
  const save = async () => {
    try {
      await api(`/training/sessions/${s.id}/attendance`, { body: { present } });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div className="row-between small"><span>{present.length} of {active.length} present</span>
        <span className="row-gap"><button className="btn ghost small" onClick={() => setPresent(active.map((t) => t.id))}>All present</button>
          <button className="btn ghost small" onClick={() => setPresent([])}>Clear</button></span></div>
      <div className="att-list">
        {active.map((t) => {
          const on = present.includes(t.id);
          return (
            <button key={t.id} type="button" className={`att-row ${on ? "on" : ""}`} aria-pressed={on}
              onClick={() => setPresent(on ? present.filter((x) => x !== t.id) : [...present, t.id])}>
              <Avatar url={t.entrepreneur.photo_url} name={t.entrepreneur.full_name} size={40} />
              <span><b>{t.entrepreneur.full_name}</b><small className="muted">{t.entrepreneur.village_name}{checkedIn.includes(t.id) && !s.done ? " · checked in" : ""}</small></span>
              <span className="att-mark">{on ? "✓" : ""}</span>
            </button>
          );
        })}
      </div>
      {error && <div className="error">{error}</div>}
      <button className="btn block" onClick={save}>Save attendance</button>
    </div>
  );
}

function CheckinQR({ s, onClose }: { s: SessionRow; onClose: () => void }) {
  const [qr, setQr] = useState<{ url: string; code: string; svg: string } | null>(null);
  const [count, setCount] = useState(s.present);
  const [error, setError] = useState<string | null>(null);
  const { id } = useParams();
  useEffect(() => {
    api<{ url: string; code: string; svg: string }>(`/training/sessions/${s.id}/checkin/open`, { body: { origin: window.location.origin } })
      .then(setQr).catch((e) => setError(e.message));
    const t = setInterval(() => api<BD>(`/training/batches/${id}`).then((d) => setCount(d.sessions.find((x) => x.id === s.id)?.present ?? 0)).catch(() => {}), 4000);
    return () => clearInterval(t);
  }, [s.id, id]);
  const close = async () => {
    await api(`/training/sessions/${s.id}/checkin/close`, { method: "POST" }).catch(() => {});
    onClose();
  };
  return (
    <div className="stack" style={{ alignItems: "center", textAlign: "center" }}>
      {error && <div className="error">{error}</div>}
      {qr && (<>
        <p className="small" style={{ margin: 0 }}>Trainees scan this with their phone camera (they must be logged in to the MIRAI app), or type the code in <b>My training → Check in</b>.</p>
        <div className="qr-box" dangerouslySetInnerHTML={{ __html: qr.svg }} />
        <div className="checkin-code" aria-label="Check-in code">{qr.code.slice(0, 3)} {qr.code.slice(3)}</div>
        <div className="tag ok">{count} checked in</div>
      </>)}
      <button className="btn secondary" onClick={close}>Close check-in</button>
    </div>
  );
}

function ResultRow({ t, b, onSaved }: { t: TraineeRow; b: BD; onSaved: () => void }) {
  const [f, setF] = useState({ quiz_score: t.quiz_score ?? "", bp_score: t.bp_score ?? "", practical_hours: t.practical_hours ?? "", practical: { ...t.practical }, result: t.result ?? "" });
  const [msg, setMsg] = useState<string | null>(null);
  const dirty = JSON.stringify(f) !== JSON.stringify({ quiz_score: t.quiz_score ?? "", bp_score: t.bp_score ?? "", practical_hours: t.practical_hours ?? "", practical: { ...t.practical }, result: t.result ?? "" });
  const num = (v: string | number) => (v === "" ? null : Number(v));
  const save = async () => {
    setMsg(null);
    try {
      await api(`/training/trainees/${t.id}/assessment`, { method: "PUT", body: { quiz_score: num(f.quiz_score), bp_score: num(f.bp_score), practical_hours: num(f.practical_hours), practical: f.practical, result: f.result || null } });
      onSaved();
    } catch (e) {
      setMsg((e as Error).message);
    }
  };
  const ro = !b.can_run;
  return (
    <div className="card result-card">
      <div className="row-between">
        <div className="row-gap" style={{ alignItems: "center", flexWrap: "nowrap" }}>
          <Avatar url={t.entrepreneur.photo_url} name={t.entrepreneur.full_name} size={36} />
          <div><b>{t.entrepreneur.full_name}</b><div className="small muted">Attendance {t.attended}/{t.total} ({t.attendance_pct}%)</div></div>
        </div>
        {t.certificate_no
          ? <button className="btn secondary small" onClick={() => openLink(`/training/trainees/${t.id}/certificate/link`)}>Certificate {t.certificate_no}</button>
          : <span className={`tag ${t.suggested === "pass" ? "ok" : "amber"}`} title={t.suggested_why.join("\n")}>suggested: {t.suggested}</span>}
      </div>
      {t.suggested_why.length > 0 && !t.certificate_no && <div className="small muted">{t.suggested_why.join(" · ")}</div>}
      <div className="row-gap">
        {b.pass_mark > 0 && <label className="field"><span>Quiz / theory %</span><input className="input num-input" type="number" min={0} max={100} disabled={ro} value={f.quiz_score} onChange={(e) => setF({ ...f, quiz_score: e.target.value })} /></label>}
        {b.course.business_plan_score && <label className="field"><span>Business plan %</span><input className="input num-input" type="number" min={0} max={100} disabled={ro} value={f.bp_score} onChange={(e) => setF({ ...f, bp_score: e.target.value })} /></label>}
        {b.course.practical_checklist.length > 0 && <label className="field"><span>Practical hours</span><input className="input num-input" type="number" min={0} disabled={ro} value={f.practical_hours} onChange={(e) => setF({ ...f, practical_hours: e.target.value })} /></label>}
        <label className="field"><span>Result</span>
          <select className="input" disabled={ro} value={f.result} onChange={(e) => setF({ ...f, result: e.target.value })}>
            <option value="">—</option><option value="pass">Pass</option><option value="reassess">Re-assess</option><option value="fail">Fail</option></select></label>
      </div>
      {b.course.practical_checklist.length > 0 && (
        <div className="chips small-chips">{b.course.practical_checklist.map((i) => (
          <button key={i} type="button" disabled={ro} className={`chip ${f.practical[i] ? "on" : ""}`} aria-pressed={!!f.practical[i]}
            onClick={() => setF({ ...f, practical: { ...f.practical, [i]: !f.practical[i] } })}>{f.practical[i] ? "✓ " : ""}{i}</button>
        ))}</div>
      )}
      {t.feedback_rating && <div className="small">Feedback: {"★".repeat(t.feedback_rating)}{"☆".repeat(5 - t.feedback_rating)} {t.feedback_text && <span className="muted">“{t.feedback_text}”</span>}</div>}
      {msg && <div className="error">{msg}</div>}
      {!ro && dirty && <div><button className="btn small" onClick={save}>Save result</button></div>}
    </div>
  );
}

export default function BatchDetail() {
  const { id } = useParams();
  const meta = useTrainingMeta();
  const [b, setB] = useState<BD | null>(null);
  const [tab, setTab] = useState<"trainees" | "sessions" | "results">("trainees");
  const [modal, setModal] = useState<{ kind: "add" | "edit" | "att" | "qr"; s?: SessionRow } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [photoFor, setPhotoFor] = useState<number | null>(null);
  const load = useCallback(() => api<BD>(`/training/batches/${id}`).then(setB).catch((e) => setError(e.message)), [id]);
  useEffect(() => {
    load();
  }, [load]);
  if (error && !b) return <div className="error">{error}</div>;
  if (!b) return <div className="muted">Loading…</div>;

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const setStatus = (status: string) => act(() => api(`/training/batches/${b.id}/status`, { body: { status } }));
  const uploadPhoto = async (file?: File) => {
    if (!file || !photoFor) return;
    const pos = await new Promise<GeolocationPosition | null>((res) =>
      navigator.geolocation ? navigator.geolocation.getCurrentPosition(res, () => res(null), { timeout: 8000 }) : res(null));
    const fd = new FormData();
    fd.append("file", file);
    if (pos) {
      fd.append("lat", String(pos.coords.latitude));
      fd.append("lng", String(pos.coords.longitude));
    }
    await act(() => apiUpload(`/training/sessions/${photoFor}/photo`, fd));
    if (fileRef.current) fileRef.current.value = "";
  };
  const active = b.trainees.filter((t) => ["confirmed", "completed"].includes(t.status));
  const requested = b.trainees.filter((t) => t.status === "requested");
  const closed = ["completed", "cancelled"].includes(b.status);

  return (
    <div className="stack">
      <Link to="/admin/training/batches" className="small">← Batches</Link>
      <div className="card stack" style={{ gap: 8 }}>
        <div className="row-between" style={{ alignItems: "flex-start" }}>
          <div>
            <div className="row-gap" style={{ alignItems: "center" }}><span className={`tag ${STATUS_TAG[b.status]}`}>{b.status}</span><small className="muted">{b.code}</small></div>
            <h1 style={{ margin: "6px 0 2px" }}>{b.course.name_en}</h1>
            <div className="small muted">{b.course.track_label} · {MODES[b.mode]} · {fmtDate(b.start_date)} – {fmtDate(b.end_date)} · {b.venue || b.host_unit || "Online"}{b.district_name ? `, ${b.district_name}` : ""}</div>
            <div className="small">Trainers: <b>{b.trainers.join(", ") || "—"}</b>{b.mentors.length > 0 && <> · Mentors: <b>{b.mentors.join(", ")}</b></>}
              {b.partner && <> · Partner: <b>{b.partner}</b></>}{b.sponsor_type !== "self" && <> · Sponsor: <b>{b.sponsor_name}</b></>}</div>
          </div>
          {b.can_plan && !closed && (
            <div className="row-gap">
              <button className="btn secondary small" onClick={() => setModal({ kind: "edit" })}>Edit</button>
              {b.status === "planned" && <button className="btn small" onClick={() => setStatus("open")}>Open for requests</button>}
              {["planned", "open"].includes(b.status) && <button className="btn secondary small" onClick={() => setStatus("ongoing")}>Start</button>}
              {b.status === "ongoing" && <button className="btn small" onClick={() => setStatus("completed")}>Complete batch</button>}
              <button className="btn ghost small danger" onClick={() => window.confirm("Cancel this batch?") && setStatus("cancelled")}>Cancel</button>
            </div>
          )}
        </div>
        <div className="kpis">
          <div><span>Trainees</span><b>{b.filled}/{b.seats}</b></div>
          <div><span>Sessions held</span><b>{b.sessions_done}/{b.sessions_total}</b></div>
          <div><span>Pass mark</span><b>{b.pass_mark}%</b></div>
          <div><span>Certified</span><b>{b.certified}</b></div>
        </div>
      </div>
      {error && <div className="error">{error}</div>}

      <div className="tabs">
        <button className={tab === "trainees" ? "on" : ""} onClick={() => setTab("trainees")}>Trainees ({active.length}{requested.length ? ` + ${requested.length} requests` : ""})</button>
        <button className={tab === "sessions" ? "on" : ""} onClick={() => setTab("sessions")}>Sessions & attendance</button>
        <button className={tab === "results" ? "on" : ""} onClick={() => setTab("results")}>Results & certificates</button>
      </div>

      {tab === "trainees" && (
        <div className="stack">
          {b.can_plan && !closed && <div><button className="btn" disabled={b.filled >= b.seats} onClick={() => setModal({ kind: "add" })}>+ Add trainees</button></div>}
          {requested.length > 0 && (
            <div className="card stack dup-box">
              <b>Requests from the app</b>
              {requested.map((t) => (
                <div key={t.id} className="row-between small">
                  <span>{b.can_plan ? <Link to={`/admin/entrepreneurs/${t.entrepreneur.id}`}>{t.entrepreneur.full_name}</Link> : t.entrepreneur.full_name} · {t.entrepreneur.village_name}</span>
                  {b.can_plan && <span className="row-gap">
                    <button className="btn small" onClick={() => act(() => api(`/training/trainees/${t.id}`, { method: "PUT", body: { status: "confirmed" } }))}>Confirm</button>
                    <button className="btn ghost small" onClick={() => act(() => api(`/training/trainees/${t.id}`, { method: "PUT", body: { status: "withdrawn" } }))}>Decline</button></span>}
                </div>
              ))}
            </div>
          )}
          <div className="card table-wrap">
            <table className="table">
              <thead><tr><th>Name</th><th>Attendance</th><th>Mentor</th><th>Result</th><th /></tr></thead>
              <tbody>
                {active.map((t) => (
                  <tr key={t.id}>
                    <td><div className="row-gap" style={{ alignItems: "center", flexWrap: "nowrap" }}><Avatar url={t.entrepreneur.photo_url} name={t.entrepreneur.full_name} />
                      <div>{b.can_plan ? <Link to={`/admin/entrepreneurs/${t.entrepreneur.id}`}><b>{t.entrepreneur.full_name}</b></Link> : <b>{t.entrepreneur.full_name}</b>}<div className="small muted">{t.entrepreneur.mobile} · {t.source === "self" ? "requested in app" : "nominated"}</div></div></div></td>
                    <td>{t.attended}/{t.total} <span className="small muted">({t.attendance_pct}%)</span></td>
                    <td>{b.can_plan && !closed && meta ? (
                      <select className="input" aria-label="Mentor" value={t.mentor_id ?? ""} onChange={(e) => act(() => api(`/training/trainees/${t.id}`, { method: "PUT", body: { mentor_id: Number(e.target.value) || 0 } }))}>
                        <option value="">—</option>{meta.mentors.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select>) : (t.mentor ?? "—")}</td>
                    <td>{t.result ? <span className={`tag ${t.result === "pass" ? "ok" : t.result === "fail" ? "alert" : "amber"}`}>{t.result}</span> : <span className="muted small">—</span>}</td>
                    <td>{b.can_plan && !closed && !t.certificate_no && <button className="btn ghost small danger" onClick={() => window.confirm(`Remove ${t.entrepreneur.full_name} from the batch?`) && act(() => api(`/training/trainees/${t.id}`, { method: "PUT", body: { status: "withdrawn" } }))}>Remove</button>}</td>
                  </tr>
                ))}
                {active.length === 0 && <tr><td colSpan={5} className="muted">No trainees yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "sessions" && (
        <div className="stack">
          <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => uploadPhoto(e.target.files?.[0])} />
          {b.sessions.map((s) => (
            <div key={s.id} className={`card session-card ${s.done ? "done" : ""}`}>
              <div className="session-n">{s.n}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <b>{s.topic}</b>
                <div className="small muted">{fmtDate(s.date)}{s.hours ? ` · ${s.hours} h` : ""} · {s.done ? `${s.present}/${active.length} present` : s.present ? `${s.present} checked in` : "not held yet"}
                  {s.lat != null && " · 📍 location recorded"}</div>
              </div>
              {s.photo_url && <a href={apiUrl(s.photo_url)} target="_blank" rel="noreferrer"><img className="session-photo" src={apiUrl(s.photo_url)} alt={`Session ${s.n}`} /></a>}
              {b.can_run && !closed && (
                <div className="row-gap">
                  <button className="btn small" onClick={() => setModal({ kind: "att", s })}>{s.done ? "Edit attendance" : "Attendance"}</button>
                  <button className="btn secondary small" onClick={() => setModal({ kind: "qr", s })}>QR check-in</button>
                  <button className="btn ghost small" onClick={() => { setPhotoFor(s.id); fileRef.current?.click(); }}>{s.photo_url ? "Change photo" : "Photo"}</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "results" && (
        <div className="stack">
          <p className="small muted" style={{ margin: 0 }}>
            Pass needs attendance of at least {b.course.min_attendance}%{b.pass_mark > 0 ? `, quiz ${b.pass_mark}%+` : ""}{b.course.business_plan_score ? ", business-plan score" : ""}{b.course.practical_checklist.length ? " and every practical item signed off" : ""}.
            Choosing Pass issues the certificate{b.course.track === "core" ? " and moves the person to stage 3 (DPR & finance)" : ""}.
            {b.course.external_certificate && <> This course also needs the <b>{b.course.external_certificate}</b>, uploaded by the trainee and verified by staff.</>}
          </p>
          {active.map((t) => <ResultRow key={`${t.id}-${t.result}-${t.quiz_score}-${t.certificate_no}`} t={t} b={b} onSaved={load} />)}
          {active.length === 0 && <div className="card muted">No trainees yet.</div>}
        </div>
      )}

      {modal?.kind === "add" && <Modal title="Add trainees" wide onClose={() => setModal(null)}><AddTrainees b={b} onDone={(d) => { setB(d); setModal(null); }} /></Modal>}
      {modal?.kind === "edit" && meta && <Modal title="Edit batch" wide onClose={() => setModal(null)}><BatchForm batch={b as unknown as import("../../api").BatchRow} meta={meta} onSaved={() => { setModal(null); load(); }} /></Modal>}
      {modal?.kind === "att" && modal.s && <Modal title={`Session ${modal.s.n}: ${modal.s.topic}`} onClose={() => setModal(null)}><AttendanceSheet b={b} s={modal.s} onDone={() => { setModal(null); load(); }} /></Modal>}
      {modal?.kind === "qr" && modal.s && <Modal title={`Check-in – session ${modal.s.n}`} onClose={() => { setModal(null); load(); }}><CheckinQR s={modal.s} onClose={() => { setModal(null); load(); }} /></Modal>}
    </div>
  );
}
