// Form 1.2 – SHG / group profiles, with exactly one leader, secretary and treasurer.
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type Assessment } from "../../api";
import { useAuth } from "../../auth";
import { useMaster } from "../../components/masters";
import { bandOf, ReadinessForm, ReadinessResult } from "../../components/Readiness";
import { Field, Modal } from "../ui";

type Member = { name: string; mobile: string | null; role: string; contribution: number | null; entrepreneur_id?: number | null };
type Group = {
  id: number; name: string; group_type: string; district: string; district_name: string; mandal: string; mandal_name: string;
  village: string; village_name: string; context_tag: string; stage: number; members_count: number; leader: string | null;
  readiness: { score: number } | null; reg_code?: string | null; federation?: string | null; formation_date?: string | null;
  bank_masked?: string | null; ifsc?: string | null; corpus?: number | null; existing_activity?: string | null; members?: Member[];
  assessments?: Assessment[];
};
const TYPES: Record<string, string> = { shg: "SHG", jlg: "Joint liability group", producer: "Producer group", cooperative: "Cooperative", other: "Other" };
const WRITE = ["admin", "programme_manager", "coordinator", "federation_staff"];
const ROLES = ["leader", "secretary", "treasurer", "member"];

function GroupForm({ g, onSaved }: { g?: Group; onSaved: (g: Group) => void }) {
  const [f, setF] = useState({
    name: g?.name ?? "", group_type: g?.group_type ?? "shg", reg_code: g?.reg_code ?? "", federation: g?.federation ?? "",
    formation_date: g?.formation_date ?? "", district: g?.district ?? "", mandal: g?.mandal ?? "", village: g?.village ?? "",
    context_tag: g?.context_tag ?? "rural", bank_account: "", ifsc: "", corpus: g?.corpus != null ? String(g.corpus) : "",
    existing_activity: g?.existing_activity ?? "",
  });
  const [members, setMembers] = useState<Member[]>(g?.members?.map((m) => ({ ...m })) ?? [
    { name: "", mobile: "", role: "leader", contribution: null }, { name: "", mobile: "", role: "secretary", contribution: null },
    { name: "", mobile: "", role: "treasurer", contribution: null }]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const districts = useMaster("district");
  const mandals = useMaster("mandal", f.district, !!f.district);
  const villages = useMaster("village", f.mandal, mandals.some((m) => m.code === f.mandal));
  const set = (k: keyof typeof f, v: string) => setF({ ...f, [k]: v });
  const setM = (i: number, k: keyof Member, v: string) => setMembers(members.map((m, j) => (j === i ? { ...m, [k]: k === "contribution" ? (v ? Number(v) : null) : v } : m)));

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = {
        ...f, reg_code: f.reg_code || null, federation: f.federation || null, corpus: f.corpus ? Number(f.corpus) : null,
        existing_activity: f.existing_activity || null, bank_account: f.bank_account || null, ifsc: f.bank_account ? f.ifsc.toUpperCase() : null,
        members: members.filter((m) => m.name.trim()).map((m) => ({ name: m.name, mobile: m.mobile || null, role: m.role, contribution: m.contribution })),
      };
      onSaved(await api<Group>(g ? `/programme/groups/${g.id}` : "/programme/groups", { method: g ? "PUT" : "POST", body }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Group name"><input className="input" value={f.name} onChange={(e) => set("name", e.target.value)} /></Field>
        <Field label="Type"><select className="input" value={f.group_type} onChange={(e) => set("group_type", e.target.value)}>
          {Object.entries(TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Registration / SERP code"><input className="input" value={f.reg_code} onChange={(e) => set("reg_code", e.target.value)} /></Field>
        <Field label="Federation (VO / Mandal Samakhya)"><input className="input" value={f.federation} onChange={(e) => set("federation", e.target.value)} /></Field>
        <Field label="Formation date"><input className="input" type="date" value={f.formation_date} onChange={(e) => set("formation_date", e.target.value)} /></Field>
        <Field label="Area type"><select className="input" value={f.context_tag} onChange={(e) => set("context_tag", e.target.value)}>
          {["rural", "urban", "tribal", "coastal"].map((t) => <option key={t}>{t}</option>)}</select></Field>
        <Field label="District"><select className="input" value={f.district} onChange={(e) => setF({ ...f, district: e.target.value, mandal: "", village: "" })}>
          <option value="">—</option>{districts.map((d) => <option key={d.code} value={d.code}>{d.name_en}</option>)}</select></Field>
        <Field label="Mandal" hint="Pick from the list or type a new name">
          <input className="input" list="g-mandals" value={f.mandal} onChange={(e) => setF({ ...f, mandal: e.target.value, village: "" })} />
          <datalist id="g-mandals">{mandals.map((m) => <option key={m.code} value={m.code}>{m.name_en}</option>)}</datalist></Field>
        <Field label="Village"><input className="input" list="g-villages" value={f.village} onChange={(e) => set("village", e.target.value)} />
          <datalist id="g-villages">{villages.map((m) => <option key={m.code} value={m.code}>{m.name_en}</option>)}</datalist></Field>
        <Field label="Group corpus / savings (₹)"><input className="input" inputMode="numeric" value={f.corpus} onChange={(e) => set("corpus", e.target.value.replace(/[^\d.]/g, ""))} /></Field>
        <Field label="Bank account" hint={g?.bank_masked ? `Saved: ${g.bank_masked} (${g.ifsc}). Leave blank to keep.` : "Kept encrypted"}>
          <input className="input" inputMode="numeric" value={f.bank_account} onChange={(e) => set("bank_account", e.target.value.replace(/\D/g, ""))} /></Field>
        {f.bank_account && <Field label="IFSC"><input className="input" value={f.ifsc} maxLength={11} onChange={(e) => set("ifsc", e.target.value.toUpperCase())} /></Field>}
        <Field label="Existing activity"><input className="input" value={f.existing_activity} onChange={(e) => set("existing_activity", e.target.value)} /></Field>
      </div>
      <h3 style={{ marginBottom: 0 }}>Members</h3>
      <p className="small muted" style={{ margin: 0 }}>Exactly one leader, one secretary and one treasurer. Members with a mobile that is already enrolled are linked to their profile.</p>
      <div className="table-wrap">
        <table className="table compact">
          <thead><tr><th>Name</th><th>Mobile</th><th>Role</th><th>Contribution ₹</th><th /></tr></thead>
          <tbody>
            {members.map((m, i) => (
              <tr key={i}>
                <td><input className="input" aria-label="Member name" value={m.name} onChange={(e) => setM(i, "name", e.target.value)} /></td>
                <td><input className="input" aria-label="Member mobile" inputMode="numeric" maxLength={10} value={m.mobile ?? ""} onChange={(e) => setM(i, "mobile", e.target.value.replace(/\D/g, ""))} /></td>
                <td><select className="input" aria-label="Member role" value={m.role} onChange={(e) => setM(i, "role", e.target.value)}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></td>
                <td><input className="input" aria-label="Contribution" inputMode="numeric" value={m.contribution ?? ""} onChange={(e) => setM(i, "contribution", e.target.value.replace(/[^\d.]/g, ""))} /></td>
                <td>{m.entrepreneur_id ? <Link className="small" to={`/admin/entrepreneurs/${m.entrepreneur_id}`}>profile</Link> : null}
                  <button className="btn ghost small danger" aria-label="Remove member" onClick={() => setMembers(members.filter((_, j) => j !== i))}>✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div><button className="btn secondary small" onClick={() => setMembers([...members, { name: "", mobile: "", role: "member", contribution: null }])}>+ Add member</button></div>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" disabled={busy} onClick={save}>{g ? "Save group" : "Enrol group"}</button></div>
    </div>
  );
}

export default function Groups() {
  const { user } = useAuth();
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Group[] | null>(null);
  const [open, setOpen] = useState<Group | null>(null);
  const [mode, setMode] = useState<"view" | "edit" | "assess">("view");
  const canWrite = WRITE.includes(user?.role ?? "");

  const load = useCallback(() => {
    api<{ rows: Group[] }>(`/programme/groups${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`).then((r) => setRows(r.rows)).catch(() => setRows([]));
  }, [q]);
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);
  const show = (id: number) => api<Group>(`/programme/groups/${id}?lang=en`).then((g) => { setOpen(g); setMode("view"); });
  useEffect(() => {
    const o = sp.get("open");
    if (o) show(Number(o));
  }, [sp]);
  const close = () => {
    setOpen(null);
    if (sp.get("open") || sp.get("new")) setSp({}, { replace: true });
  };

  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Groups</h1><p className="muted small" style={{ margin: 0 }}>SHGs, JLGs and producer groups (Form 1.2).</p></div>
        {canWrite && <button className="btn" onClick={() => setSp({ new: "1" })}>+ Enrol group</button>}
      </div>
      <div className="filters"><input className="input" placeholder="Search group name" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Group</th><th>Place</th><th>Members</th><th>Leader</th><th>Readiness</th></tr></thead>
          <tbody>
            {rows?.map((g) => (
              <tr key={g.id} className="clickable" onClick={() => show(g.id)}>
                <td><b>{g.name}</b><div className="small muted">{TYPES[g.group_type] ?? g.group_type}</div></td>
                <td className="small">{g.village_name}<div className="muted">{g.mandal_name}, {g.district_name}</div></td>
                <td>{g.members_count}</td><td>{g.leader}</td>
                <td>{g.readiness ? <span className={`tag ${bandOf(g.readiness.score)}`}>{g.readiness.score}</span> : "—"}</td>
              </tr>
            ))}
            {rows && rows.length === 0 && <tr><td colSpan={5} className="muted">No groups yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {sp.get("new") && canWrite && (
        <Modal title="Enrol a group" wide onClose={close}>
          <GroupForm onSaved={(g) => { close(); load(); show(g.id); }} />
        </Modal>
      )}
      {open && (
        <Modal title={open.name} wide onClose={close}>
          {mode === "edit" ? <GroupForm g={open} onSaved={(g) => { load(); show(g.id); }} />
            : mode === "assess" ? (
              <ReadinessForm lang="en" staff formPath="/programme/readiness/form?lang=en" submitPath={`/programme/groups/${open.id}/readiness?lang=en`}
                onDone={() => { load(); show(open.id); }} />
            ) : (
              <div className="stack">
                <div className="small muted">{TYPES[open.group_type]} · formed {open.formation_date} · {open.village_name}, {open.mandal_name}, {open.district_name}
                  {open.federation && ` · ${open.federation}`}{open.reg_code && ` · code ${open.reg_code}`}</div>
                <div className="small">Corpus: <b>{open.corpus != null ? `₹${open.corpus.toLocaleString("en-IN")}` : "—"}</b> · Bank: <b>{open.bank_masked ?? "—"}</b>
                  {open.existing_activity && <> · Activity: <b>{open.existing_activity}</b></>}</div>
                <table className="table compact"><tbody>
                  {open.members?.map((m, i) => (
                    <tr key={i}><td>{m.entrepreneur_id ? <Link to={`/admin/entrepreneurs/${m.entrepreneur_id}`}>{m.name}</Link> : m.name}</td>
                      <td>{m.mobile ?? ""}</td><td><span className={`tag ${m.role === "member" ? "grey" : ""}`}>{m.role}</span></td>
                      <td className="num">{m.contribution != null ? `₹${m.contribution}` : ""}</td></tr>
                  ))}
                </tbody></table>
                {open.assessments?.[0] ? <ReadinessResult a={open.assessments[0]} lang="en" /> : <p className="small muted">No readiness assessment yet. Own funds are taken from the group corpus.</p>}
                <div className="row-gap">
                  {canWrite && <button className="btn secondary" onClick={() => setMode("edit")}>Edit group</button>}
                  {["admin", "programme_manager", "coordinator", "mentor"].includes(user?.role ?? "") &&
                    <button className="btn" onClick={() => setMode("assess")}>+ Readiness assessment</button>}
                </div>
              </div>
            )}
        </Modal>
      )}
    </div>
  );
}
