// M14 – Master data: geography, context tags, sectors (with activation status), skills and other lists.
import { useCallback, useEffect, useState } from "react";
import { api, apiDownload } from "../../api";
import { clearMasterCache, useMaster } from "../../components/masters";
import CsvImport from "../CsvImport";
import { Field, Modal } from "../ui";

type Kind = { kind: string; label: string; parent: string | null };
type Item = { id: number; kind: string; code: string; name_en: string; name_te: string | null; parent_code: string | null; parent_name: string | null;
  data: Record<string, unknown>; active: boolean; sort: number };
const ACT: Record<string, string> = { catalogue: "Catalogue only", pilot: "Pilot", active: "Active" };

function ItemForm({ kind, parentKind, item, onSaved }: { kind: string; parentKind: string | null; item?: Item; onSaved: () => void }) {
  const [f, setF] = useState({
    code: item?.code ?? "", name_en: item?.name_en ?? "", name_te: item?.name_te ?? "", parent_code: item?.parent_code ?? "",
    active: item?.active ?? true, sort: item?.sort ?? 100, data: { ...(item?.data ?? (kind === "sector" ? { activation: "catalogue" } : {})) } as Record<string, unknown>,
  });
  const [error, setError] = useState<string | null>(null);
  const grand = parentKind === "mandal" ? "district" : null;
  const [gp, setGp] = useState("");
  const grandItems = useMaster("district", null, !!grand);
  const parents = useMaster(parentKind ?? "district", grand ? gp : null, !!parentKind && (!grand || !!gp));
  const setD = (k: string, v: unknown) => setF({ ...f, data: { ...f.data, [k]: v } });

  const save = async () => {
    setError(null);
    try {
      const body = { kind, ...f, name_te: f.name_te || null, parent_code: f.parent_code || null };
      await api(item ? `/admin/masters/${item.id}` : "/admin/masters", { method: item ? "PUT" : "POST", body });
      clearMasterCache();
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Code" hint="Lower-case letters, numbers and _ . Cannot be changed later.">
          <input className="input" value={f.code} disabled={!!item} onChange={(e) => setF({ ...f, code: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })} /></Field>
        <Field label="Sort order"><input className="input" type="number" value={f.sort} onChange={(e) => setF({ ...f, sort: Number(e.target.value) })} /></Field>
        <Field label="Name (English)"><input className="input" value={f.name_en} onChange={(e) => setF({ ...f, name_en: e.target.value })} /></Field>
        <Field label="Name (Telugu)"><input className="input" lang="te" value={f.name_te} onChange={(e) => setF({ ...f, name_te: e.target.value })} /></Field>
        {grand && (
          <Field label="District"><select className="input" value={gp} onChange={(e) => { setGp(e.target.value); setF({ ...f, parent_code: "" }); }}>
            <option value="">—</option>{grandItems.map((d) => <option key={d.code} value={d.code}>{d.name_en}</option>)}</select></Field>
        )}
        {parentKind && (
          <Field label={parentKind === "district" ? "District" : "Mandal"} hint={item?.parent_name ? `Now: ${item.parent_name}` : undefined}>
            <select className="input" value={f.parent_code} onChange={(e) => setF({ ...f, parent_code: e.target.value })}>
              <option value="">{item?.parent_code && !parents.some((p) => p.code === item.parent_code) ? item.parent_name ?? "—" : "—"}</option>
              {parents.map((p) => <option key={p.code} value={p.code}>{p.name_en}</option>)}</select></Field>
        )}
        {(kind === "district" || kind === "village") && (
          <Field label="Context tag"><select className="input" value={(f.data.context_tag as string) ?? ""} onChange={(e) => setD("context_tag", e.target.value || undefined)}>
            <option value="">—</option>{["rural", "urban", "tribal", "coastal"].map((t) => <option key={t}>{t}</option>)}</select></Field>
        )}
        {kind === "sector" && (<>
          <Field label="Activation" hint="Catalogue only = listed, no workflows. Pilot = selected districts. Active = full workflows.">
            <select className="input" value={(f.data.activation as string) ?? "catalogue"} onChange={(e) => setD("activation", e.target.value)}>
              {Object.entries(ACT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          <Field label="Pilot districts (codes, comma separated)">
            <input className="input" value={((f.data.pilot_districts as string[]) ?? []).join(", ")} onChange={(e) => setD("pilot_districts", e.target.value.split(",").map((x) => x.trim()).filter(Boolean))} /></Field>
          <Field label="Example activities"><input className="input" value={(f.data.description as string) ?? ""} onChange={(e) => setD("description", e.target.value)} /></Field>
          <Field label="Typical context tags (comma separated)">
            <input className="input" value={((f.data.context_tags as string[]) ?? []).join(", ")} onChange={(e) => setD("context_tags", e.target.value.split(",").map((x) => x.trim()).filter(Boolean))} /></Field>
        </>)}
      </div>
      <label className="check"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /><span>Active (shown in forms)</span></label>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" disabled={!f.code || !f.name_en} onClick={save}>Save</button></div>
    </div>
  );
}

export default function Masters() {
  const [kinds, setKinds] = useState<Kind[]>([]);
  const [kind, setKind] = useState("district");
  const [q, setQ] = useState("");
  const [parent, setParent] = useState("");
  const [rows, setRows] = useState<Item[] | null>(null);
  const [edit, setEdit] = useState<Item | "new" | null>(null);
  const [importing, setImporting] = useState(false);
  const cur = kinds.find((k) => k.kind === kind);
  const parentOpts = useMaster(cur?.parent ?? "district", null, cur?.parent === "district");

  useEffect(() => {
    api<Kind[]>("/admin/masters/kinds").then(setKinds).catch(() => {});
  }, []);
  const load = useCallback(() => {
    const p = new URLSearchParams({ kind });
    if (q.trim()) p.set("q", q.trim());
    if (parent) p.set("parent", parent);
    api<Item[]>(`/admin/masters?${p}`).then(setRows).catch(() => setRows([]));
  }, [kind, q, parent]);
  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
  }, [load]);

  return (
    <div className="stack">
      <div><h1>Master data</h1><p className="muted small" style={{ margin: 0 }}>Lists used by every form. Load the full village list from the Local Government Directory (lgdirectory.gov.in) with Import CSV.</p></div>
      <div className="tabs" role="tablist">
        {kinds.map((k) => (
          <button key={k.kind} role="tab" aria-selected={k.kind === kind} className={k.kind === kind ? "on" : ""}
            onClick={() => { setKind(k.kind); setParent(""); setQ(""); }}>{k.label}</button>
        ))}
      </div>
      <div className="filters">
        <input className="input" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
        {cur?.parent === "district" && (
          <select className="input" value={parent} onChange={(e) => setParent(e.target.value)} aria-label="District">
            <option value="">All districts</option>{parentOpts.map((d) => <option key={d.code} value={d.code}>{d.name_en}</option>)}</select>
        )}
        {cur?.parent === "mandal" && <input className="input" placeholder="Mandal code" value={parent} onChange={(e) => setParent(e.target.value.trim())} />}
        <div className="spacer" style={{ flex: 1 }} />
        <button className="btn secondary small" onClick={() => apiDownload(`/admin/masters/export?kind=${kind}`, `${kind}.csv`)}>Export CSV</button>
        <button className="btn secondary small" onClick={() => setImporting(true)}>Import CSV</button>
        <button className="btn small" onClick={() => setEdit("new")}>+ Add</button>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Code</th><th>English</th><th>Telugu</th>{cur?.parent && <th>{cur.parent}</th>}<th>Details</th><th>Active</th></tr></thead>
          <tbody>
            {rows?.map((r) => (
              <tr key={r.id} className={`clickable ${r.active ? "" : "dim"}`} onClick={() => setEdit(r)}>
                <td><code>{r.code}</code></td><td>{r.name_en}</td><td lang="te">{r.name_te ?? <span className="muted">—</span>}</td>
                {cur?.parent && <td className="small">{r.parent_name}</td>}
                <td className="small">
                  {typeof r.data.context_tag === "string" && <span className="tag grey">{r.data.context_tag}</span>}
                  {typeof r.data.activation === "string" && <span className={`tag ${r.data.activation === "active" ? "ok" : r.data.activation === "pilot" ? "amber" : "grey"}`}>{ACT[r.data.activation]}</span>}
                </td>
                <td>{r.active ? "yes" : "no"}</td>
              </tr>
            ))}
            {rows && rows.length === 0 && <tr><td colSpan={6} className="muted">Nothing in this list yet.</td></tr>}
          </tbody>
        </table>
      </div>
      {rows && <span className="small muted">{rows.length} items{rows.length >= 500 ? " (first 500 – use search)" : ""}</span>}
      {edit && (
        <Modal title={edit === "new" ? `Add to ${cur?.label}` : `${cur?.label}: ${edit.name_en}`} wide onClose={() => setEdit(null)}>
          <ItemForm kind={kind} parentKind={cur?.parent ?? null} item={edit === "new" ? undefined : edit} onSaved={() => { setEdit(null); load(); }} />
        </Modal>
      )}
      {importing && (
        <Modal title={`Import ${cur?.label}`} wide onClose={() => setImporting(false)}>
          <p className="small muted">Columns: <code>code, name_en, name_te, parent_code, context_tag, active</code>. Existing codes are updated, new ones added; nothing is deleted.
            {cur?.parent && <> <b>parent_code</b> is the {cur.parent} code.</>} Tip: Export first to get the format.</p>
          <CsvImport path={`/admin/masters/import?kind=${kind}`} onDone={() => { clearMasterCache(); load(); }}
            columns={[["code", "Code"], ["name_en", "English"], ["name_te", "Telugu"], ["parent_code", "Parent"], ["context_tag", "Tag"], ["action", "Action"]]} />
        </Modal>
      )}
    </div>
  );
}
