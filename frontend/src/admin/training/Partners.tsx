// Form 4.4 – training partners: institutes, individual trainers and host units.
import { useCallback, useEffect, useState } from "react";
import { api, type Track } from "../../api";
import { useMaster } from "../../components/masters";
import { Field, Modal } from "../ui";

type P = { id: number; name: string; kind: string; contact_name: string | null; mobile: string | null; email: string | null; accreditation: string | null;
  tracks: Track[]; sectors: string[]; districts: string[]; languages: string[]; rate_batch: number | null; rate_trainee: number | null; status: string;
  rating: number | null; ratings: number };
const KINDS: Record<string, string> = { institute: "Institute", trainer: "Individual trainer", host_unit: "Host unit (on-the-job)" };
const TRACKS: [Track, string][] = [["awareness", "Awareness EDP"], ["core", "Core EDP"], ["skill", "Skill-based"], ["ojt", "On-the-job"], ["exposure", "Exposure"], ["refresher", "Refresher"]];

function Multi({ items, value, onChange }: { items: [string, string][]; value: string[]; onChange: (v: string[]) => void }) {
  return <div className="chips small-chips">{items.map(([k, l]) => {
    const on = value.includes(k);
    return <button type="button" key={k} className={`chip ${on ? "on" : ""}`} aria-pressed={on} onClick={() => onChange(on ? value.filter((x) => x !== k) : [...value, k])}>{l}</button>;
  })}</div>;
}

function PartnerForm({ p, onSaved }: { p?: P; onSaved: () => void }) {
  const [f, setF] = useState({ name: p?.name ?? "", kind: p?.kind ?? "institute", contact_name: p?.contact_name ?? "", mobile: p?.mobile ?? "", email: p?.email ?? "",
    accreditation: p?.accreditation ?? "", tracks: (p?.tracks ?? []) as string[], sectors: p?.sectors ?? [], districts: p?.districts ?? [],
    languages: p?.languages ?? ["te"], rate_batch: p?.rate_batch ?? "", rate_trainee: p?.rate_trainee ?? "", status: p?.status ?? "active" });
  const [error, setError] = useState<string | null>(null);
  const sectors = useMaster("sector");
  const districts = useMaster("district");
  const save = async () => {
    setError(null);
    try {
      const n = (v: string | number) => (v === "" ? null : Number(v));
      await api(p ? `/training/partners/${p.id}` : "/training/partners", { method: p ? "PUT" : "POST",
        body: { ...f, contact_name: f.contact_name || null, mobile: f.mobile || null, email: f.email || null, accreditation: f.accreditation || null,
          rate_batch: n(f.rate_batch), rate_trainee: n(f.rate_trainee) } });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Type"><select className="input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Contact person"><input className="input" value={f.contact_name} onChange={(e) => setF({ ...f, contact_name: e.target.value })} /></Field>
        <Field label="Mobile"><input className="input" inputMode="numeric" value={f.mobile} onChange={(e) => setF({ ...f, mobile: e.target.value })} /></Field>
        <Field label="Email"><input className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Accreditation" hint="e.g. Govt empanelment, DGCA-approved RPTO"><input className="input" value={f.accreditation} onChange={(e) => setF({ ...f, accreditation: e.target.value })} /></Field>
        <Field label="Rate per batch (₹)"><input className="input" type="number" value={f.rate_batch} onChange={(e) => setF({ ...f, rate_batch: e.target.value })} /></Field>
        <Field label="Rate per trainee (₹)"><input className="input" type="number" value={f.rate_trainee} onChange={(e) => setF({ ...f, rate_trainee: e.target.value })} /></Field>
      </div>
      <Field label="Tracks offered"><Multi items={TRACKS} value={f.tracks} onChange={(v) => setF({ ...f, tracks: v })} /></Field>
      <Field label="Sectors"><Multi items={sectors.map((s) => [s.code, s.name_en])} value={f.sectors} onChange={(v) => setF({ ...f, sectors: v })} /></Field>
      <Field label="Districts"><Multi items={districts.map((s) => [s.code, s.name_en])} value={f.districts} onChange={(v) => setF({ ...f, districts: v })} /></Field>
      <Field label="Languages"><Multi items={[["te", "Telugu"], ["en", "English"], ["hi", "Hindi"], ["ur", "Urdu"]]} value={f.languages} onChange={(v) => setF({ ...f, languages: v })} /></Field>
      <label className="check"><input type="checkbox" checked={f.status === "active"} onChange={(e) => setF({ ...f, status: e.target.checked ? "active" : "inactive" })} /><span>Active</span></label>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" onClick={save}>Save partner</button></div>
    </div>
  );
}

export default function Partners() {
  const [rows, setRows] = useState<P[] | null>(null);
  const [edit, setEdit] = useState<P | "new" | null>(null);
  const load = useCallback(() => api<P[]>("/training/partners").then(setRows).catch(() => setRows([])), []);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Training partners</h1><p className="muted small" style={{ margin: 0 }}>Empanelled institutes, trainers and host units (Form 4.4). Ratings come from trainee feedback.</p></div>
        <button className="btn" onClick={() => setEdit("new")}>+ Add partner</button>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Partner</th><th>Tracks</th><th>Districts</th><th>Rating</th><th>Status</th></tr></thead>
          <tbody>
            {rows?.map((p) => (
              <tr key={p.id} className={`clickable ${p.status === "active" ? "" : "dim"}`} onClick={() => setEdit(p)}>
                <td><b>{p.name}</b><div className="small muted">{KINDS[p.kind]}{p.contact_name ? ` · ${p.contact_name}` : ""}{p.mobile ? ` · ${p.mobile}` : ""}</div></td>
                <td className="small">{p.tracks.map((t) => TRACKS.find(([k]) => k === t)?.[1]).join(", ")}</td>
                <td className="small">{p.districts.length || "—"}</td>
                <td>{p.rating ? <span>★ {p.rating} <small className="muted">({p.ratings})</small></span> : <span className="muted small">—</span>}</td>
                <td><span className={`tag ${p.status === "active" ? "ok" : "grey"}`}>{p.status}</span></td>
              </tr>
            ))}
            {rows && rows.length === 0 && <tr><td colSpan={5} className="muted">No partners yet.</td></tr>}
          </tbody>
        </table>
      </div>
      {edit && <Modal title={edit === "new" ? "Add training partner" : edit.name} wide onClose={() => setEdit(null)}><PartnerForm p={edit === "new" ? undefined : edit} onSaved={() => { setEdit(null); load(); }} /></Modal>}
    </div>
  );
}
