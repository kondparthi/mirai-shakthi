// M14 – Staff logins, roles and data scope (districts / sectors).
import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { useMaster } from "../../components/masters";
import { Field, Modal } from "../ui";

type Staff = { id: number; name: string; email: string; role: string; role_label: string; districts: string[]; sectors: string[]; active: boolean; created_at: string | null };
type Role = { role: string; label: string };

const ROLE_NOTE: Record<string, string> = {
  admin: "Everything, including users and data requests.",
  programme_manager: "All districts; master data, readiness formula, audit log.",
  coordinator: "Enrols and manages entrepreneurs and groups in their districts.",
  federation_staff: "Enrols SHG groups and members in their districts.",
  mentor: "Sees entrepreneurs in scope; records readiness.",
  reviewer: "AI assistant answer review and knowledge library.",
};

function Multi({ items, value, onChange }: { items: { code: string; name_en: string }[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="chips small-chips">
      {items.map((i) => {
        const on = value.includes(i.code);
        return <button type="button" key={i.code} className={`chip ${on ? "on" : ""}`} aria-pressed={on}
          onClick={() => onChange(on ? value.filter((x) => x !== i.code) : [...value, i.code])}>{i.name_en}</button>;
      })}
    </div>
  );
}

function StaffForm({ s, roles, onSaved }: { s?: Staff; roles: Role[]; onSaved: () => void }) {
  const [f, setF] = useState({ name: s?.name ?? "", email: s?.email ?? "", role: s?.role ?? "coordinator", districts: s?.districts ?? [],
    sectors: s?.sectors ?? [], active: s?.active ?? true, password: "" });
  const [error, setError] = useState<string | null>(null);
  const districts = useMaster("district");
  const sectors = useMaster("sector");
  const allScope = ["admin", "programme_manager"].includes(f.role);
  const save = async () => {
    setError(null);
    try {
      await api(s ? `/admin/staff/${s.id}` : "/admin/staff", { method: s ? "PUT" : "POST", body: { ...f, password: f.password || null } });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Email (login)"><input className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Role" hint={ROLE_NOTE[f.role]}>
          <select className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
            {roles.map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}</select></Field>
        <Field label={s ? "New password (leave blank to keep)" : "Password"} hint="At least 8 characters. Share it privately.">
          <input className="input" type="text" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
      </div>
      <Field label="Districts" hint={allScope ? "This role sees all districts." : "Records outside these districts are hidden. None = only records this person enrolled."}>
        <Multi items={districts} value={f.districts} onChange={(v) => setF({ ...f, districts: v })} /></Field>
      <Field label="Sectors"><Multi items={sectors} value={f.sectors} onChange={(v) => setF({ ...f, sectors: v })} /></Field>
      <label className="check"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /><span>Login active</span></label>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" onClick={save}>{s ? "Save" : "Create login"}</button></div>
    </div>
  );
}

export default function StaffPage() {
  const [rows, setRows] = useState<Staff[] | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [edit, setEdit] = useState<Staff | "new" | null>(null);
  const districts = useMaster("district");
  const dn = (c: string) => districts.find((d) => d.code === c)?.name_en ?? c;
  const load = useCallback(() => api<Staff[]>("/admin/staff").then(setRows).catch(() => setRows([])), []);
  useEffect(() => {
    load();
    api<Role[]>("/admin/roles").then(setRoles).catch(() => {});
  }, [load]);
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Staff & access</h1><p className="muted small" style={{ margin: 0 }}>Staff log in at the admin portal with email and password. Their role decides the menu; districts decide which records they see.</p></div>
        <button className="btn" onClick={() => setEdit("new")}>+ Add staff</button>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Name</th><th>Role</th><th>Districts</th><th>Sectors</th><th>Status</th></tr></thead>
          <tbody>
            {rows?.map((s) => (
              <tr key={s.id} className={`clickable ${s.active ? "" : "dim"}`} onClick={() => setEdit(s)}>
                <td><b>{s.name}</b><div className="small muted">{s.email}</div></td>
                <td className="small">{s.role_label}</td>
                <td className="small">{["admin", "programme_manager"].includes(s.role) ? "All" : s.districts.map(dn).join(", ") || <span className="muted">own records only</span>}</td>
                <td className="small">{s.sectors.join(", ") || "—"}</td>
                <td>{s.active ? <span className="tag ok">active</span> : <span className="tag grey">disabled</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {edit && (
        <Modal title={edit === "new" ? "Add staff" : edit.name} wide onClose={() => setEdit(null)}>
          <StaffForm s={edit === "new" ? undefined : edit} roles={roles} onSaved={() => { setEdit(null); load(); }} />
        </Modal>
      )}
    </div>
  );
}
