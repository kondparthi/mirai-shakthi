import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Field, Modal, StatusTag, toList } from "./ui";

type Expert = {
  id?: number; name: string; organisation: string | null; expert_type: string; services: string[]; reg_no: string | null;
  districts: string[]; languages: string[]; fee_note: string | null; response_hours: number; rating?: number | null; status: string; login_email?: string | null;
};
const TYPES: [string, string][] = [["ca", "Chartered Accountant"], ["cs", "Company Secretary"], ["bdsp", "Business Development Service Provider"],
  ["bank", "Bank"], ["nbfc", "NBFC"], ["specialist", "Sector specialist"], ["govt", "Government office"], ["trainer", "Trainer / training desk"]];
const EMPTY: Expert = { name: "", organisation: "", expert_type: "ca", services: [], reg_no: "", districts: [], languages: ["te", "en"], fee_note: "", response_hours: 48, status: "pending" };

function PortalLogin({ expert }: { expert: Expert }) {
  const [email, setEmail] = useState(expert.login_email ?? "");
  const [password, setPassword] = useState("");
  const [current, setCurrent] = useState(expert.login_email ?? null);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setError(null);
    setMsg(null);
    try {
      const r = await api<Expert>(`/admin/experts/${expert.id}/login`, { body: { email: email.trim(), password } });
      setCurrent(r.login_email ?? email.trim());
      setPassword("");
      setMsg("Saved. Share the email and password with the expert privately. They sign in at #/expert.");
    } catch (err) { setError((err as Error).message); }
  };
  return (
    <div className="card stack" style={{ background: "var(--bg)", marginTop: 12 }}>
      <b>Expert workspace login</b>
      <div className="small muted">{current ? <>Login: <b>{current}</b>. Enter a new password to reset it.</> : "No login yet. Create one so this expert can accept and update cases."}</div>
      <div className="form-grid">
        <Field label="Login email"><input className="input" type="email" value={email} onChange={(x) => setEmail(x.target.value)} /></Field>
        <Field label={current ? "New password" : "Password"} hint="At least 8 characters"><input className="input" type="password" autoComplete="new-password" value={password} onChange={(x) => setPassword(x.target.value)} /></Field>
      </div>
      {error && <div className="error">{error}</div>}
      {msg && <div className="insight good small">{msg}</div>}
      <div><button className="btn secondary" disabled={!email || password.length < 8} onClick={save}>{current ? "Reset login" : "Create login"}</button></div>
    </div>
  );
}

function ExpertForm({ expert, services, onClose, onSaved }: { expert: Expert; services: string[]; onClose: () => void; onSaved: () => void }) {
  const [e, setE] = useState(expert);
  const [districts, setDistricts] = useState(expert.districts.join(", "));
  const [error, setError] = useState<string | null>(null);
  const toggle = (k: "services" | "languages", v: string) => setE({ ...e, [k]: e[k].includes(v) ? e[k].filter((x) => x !== v) : [...e[k], v] });
  const save = async (status?: string) => {
    setError(null);
    const body = { ...e, status: status ?? e.status, districts: toList(districts), organisation: e.organisation || null,
      reg_no: e.reg_no || null, fee_note: e.fee_note || null, response_hours: Number(e.response_hours) };
    try {
      await api(e.id ? `/admin/experts/${e.id}` : "/admin/experts", { method: e.id ? "PUT" : "POST", body });
      onSaved();
    } catch (err) { setError((err as Error).message); }
  };
  return (
    <Modal title={e.id ? "Edit expert" : "Add expert"} onClose={onClose} wide>
      <div className="form-grid">
        <Field label="Name"><input className="input" value={e.name} onChange={(x) => setE({ ...e, name: x.target.value })} /></Field>
        <Field label="Organisation"><input className="input" value={e.organisation ?? ""} onChange={(x) => setE({ ...e, organisation: x.target.value })} /></Field>
        <Field label="Type"><select className="input" value={e.expert_type} onChange={(x) => setE({ ...e, expert_type: x.target.value })}>
          {TYPES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select></Field>
        <Field label="Registration / membership no." hint="E.g. ICAI or ICSI number – check before approving">
          <input className="input" value={e.reg_no ?? ""} onChange={(x) => setE({ ...e, reg_no: x.target.value })} /></Field>
      </div>
      <div className="field"><span>Services offered</span>
        <div className="chips small-chips">{services.map((s) => (
          <button type="button" key={s} className={`chip ${e.services.includes(s) ? "on" : ""}`} onClick={() => toggle("services", s)}>{s.replace(/_/g, " ")}</button>
        ))}</div></div>
      <div className="form-grid">
        <Field label="Districts served" hint="Comma separated. Use “all” for the whole state.">
          <input className="input" value={districts} onChange={(x) => setDistricts(x.target.value)} /></Field>
        <div className="field"><span>Languages</span><div className="chips small-chips">
          {[["te", "Telugu"], ["en", "English"]].map(([v, l]) => (
            <button type="button" key={v} className={`chip ${e.languages.includes(v) ? "on" : ""}`} onClick={() => toggle("languages", v)}>{l}</button>
          ))}</div></div>
        <Field label="Fee note"><input className="input" placeholder="e.g. ₹1,500–5,000 per service" value={e.fee_note ?? ""} onChange={(x) => setE({ ...e, fee_note: x.target.value })} /></Field>
        <Field label="Responds within (hours)"><input className="input" type="number" min={1} value={e.response_hours} onChange={(x) => setE({ ...e, response_hours: Number(x.target.value) })} /></Field>
      </div>
      {e.id && <PortalLogin expert={e} />}
      {error && <div className="error">{error}</div>}
      <div className="modal-actions">
        <span className="muted small">Status: <StatusTag status={e.status} /></span><span style={{ flex: 1 }} />
        {e.status !== "suspended" && e.id && <button className="btn ghost danger" onClick={() => save("suspended")}>Suspend</button>}
        <button className="btn secondary" onClick={() => save()}>Save</button>
        {e.status !== "approved" && <button className="btn" onClick={() => save("approved")}>Approve</button>}
      </div>
    </Modal>
  );
}

export default function Experts() {
  const [list, setList] = useState<Expert[]>([]);
  const [services, setServices] = useState<string[]>([]);
  const [status, setStatus] = useState("");
  const [editing, setEditing] = useState<Expert | null>(null);
  const load = useCallback(() => { api<Expert[]>(`/admin/experts${status ? `?status=${status}` : ""}`).then(setList).catch(() => {}); }, [status]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api<{ services: string[] }>("/admin/meta").then((m) => setServices(m.services)).catch(() => {}); }, []);
  return (
    <div className="stack">
      <div className="page-head">
        <div><h1>Experts & institutions</h1><p className="muted small">CAs, CSs, BDSPs, banks and specialists shown in Handholding (screen A4). Only approved experts are shown to users.</p></div>
        <button className="btn" onClick={() => setEditing({ ...EMPTY })}>+ Add expert</button>
      </div>
      <div className="filters">
        <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option><option value="pending">Pending</option><option value="approved">Approved</option><option value="suspended">Suspended</option>
        </select>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Name</th><th>Type</th><th>Services</th><th>Districts</th><th>Reply</th><th>Login</th><th>Status</th></tr></thead>
          <tbody>
            {list.map((e) => (
              <tr key={e.id} className="clickable" onClick={() => setEditing(e)}>
                <td><b>{e.name}</b><div className="small muted">{e.organisation}</div></td>
                <td>{e.expert_type.toUpperCase()}</td>
                <td className="small">{e.services.map((s) => s.replace(/_/g, " ")).join(", ")}</td>
                <td className="small">{e.districts.join(", ")}</td>
                <td>{e.response_hours} h</td>
                <td className="small">{e.login_email ? "✓" : "—"}</td>
                <td><StatusTag status={e.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && <ExpertForm expert={editing} services={services} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}
